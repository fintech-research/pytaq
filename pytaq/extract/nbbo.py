from collections.abc import Iterable
from datetime import date, datetime, time
from typing import TYPE_CHECKING

import ibis

from ..hj_defaults import (
    HJ_DELETE_ABNORMAL_SPREADS,
    HJ_DELETE_CANCELED_QUOTES,
    HJ_DELETE_EMPTY_QUOTES,
    HJ_END_TIME_QUOTES,
    HJ_KEEP_CHANGES_ONLY,
    HJ_KEEP_QU_COND,
    HJ_MAX_QUOTE_CHANGE,
    HJ_MAX_SPREAD,
    HJ_START_TIME_QUOTES,
)
from .common import merge_symbol
from .postgresql import build_sql_query

if TYPE_CHECKING:
    import wrds
    from ibis.expr.types import Table

NBBO_COLS_DB = [
    "date",
    "time_m",
    "sym_root",
    "sym_suffix",
    "best_bid",
    "best_bidsiz",
    "best_ask",
    "best_asksiz",
    "qu_cond",
    "qu_seqnum",
    "best_askex",
    "best_bidex",
    "qu_cancel",
]

NBBO_COLS_CLEAN = [
    "timestamp",
    "symbol",
    "best_bid",
    "best_bidsizeshares",
    "best_bidex",
    "best_ask",
    "best_asksizeshares",
    "best_askex",
    "qu_seqnum",
]

NBBO_COLS_FLAGS = [
    "qu_cond",
    "qu_cancel",
]


def get_nbbo_table(date: datetime | date) -> str:
    """Returns the NBBO table name for a given date for TAQ in WRDS

    Args:
        date (Union[datetime, date]): The requested date

    Returns:
        str: NBBO table name
    """
    return "nbbom_" + date.strftime("%Y%m%d")


def get_nbbo_sql_query(
    date: datetime | date,
    library: str | None = None,
    symbols: list[str] | None = None,
    start_time: datetime | time | None = HJ_START_TIME_QUOTES,
    end_time: datetime | time | None = HJ_END_TIME_QUOTES,
) -> str:
    """Returns a SQL query to retreive the NBBO from TAQ in WRDS

    Args:
        date (Union[datetime, date]): The requested date
        library (str, optional): WRDS library to use, otherwise uses default.
        symbols (Optional[List[str]], optional): List of symbols to retreive, or None for all symbols.
        start_time (Optional[Union[datetime, time]], optional): Start time for quotes.
        end_time (Optional[Union[datetime, time]], optional): End time for quotes.

    Returns:
        str: SQL query
    """
    return build_sql_query(
        columns=NBBO_COLS_DB,
        table=get_nbbo_table(date),
        library=library,
        symbols=symbols,
        start_time=start_time,
        end_time=end_time,
    )


def filter_empty_quotes(table: "Table") -> "Table":
    """
    Delete if both ask and bid (or their size) are 0 or None

    Args:
        table (Table): Original table

    Returns:
        Table: Cleaned table
    """

    # NOTE: This filtering step follows H&J methodology but may need review.
    # Consider whether empty quotes should be preserved for complete market picture.
    # Delete if both ask and bid (or their size) are 0 or None
    empty_sel = (
        ((table.best_ask <= 0) & (table.best_bid <= 0))
        | ((table.best_asksiz <= 0) & (table.best_bidsiz <= 0))
        | (table.best_ask.isnull() & table.best_bid.isnull())
        | (table.best_asksiz.isnull() & table.best_bidsiz.isnull())
    )

    return table.filter(~empty_sel)


def compute_spreads_best_quotes(table: "Table") -> "Table":
    """
    Compute spreads and best quotes

    Args:
        table (Table): Original table

    Returns:
        Table: Cleaned table
    """

    # Add spread and midpoint columns
    table = table.mutate(
        spread=table.best_ask - table.best_bid,
        midpoint=(table.best_ask + table.best_bid) / 2,
    )

    # If size or price = 0 or null, set price and size to null
    ask_sel = (
        (table.best_ask <= 0)
        | table.best_ask.isnull()
        | (table.best_asksiz <= 0)
        | table.best_asksiz.isnull()
    )

    bid_sel = (
        (table.best_bid <= 0)
        | table.best_bid.isnull()
        | (table.best_bidsiz <= 0)
        | table.best_bidsiz.isnull()
    )

    # Use conditional logic to set values to null
    table = table.mutate(
        best_ask=ask_sel.ifelse(ibis.null(), table.best_ask),
        best_asksiz=ask_sel.ifelse(ibis.null(), table.best_asksiz),
        best_bid=bid_sel.ifelse(ibis.null(), table.best_bid),
        best_bidsiz=bid_sel.ifelse(ibis.null(), table.best_bidsiz),
        # Bid/ask size are in round lots
        best_bidsizeshares=table.best_bidsiz * 100,
        best_asksizeshares=table.best_asksiz * 100,
    )

    return table


def filter_abnormal_spreads(
    table: "Table", max_spread: float, max_quote_change: float
) -> "Table":
    """
    Filter rows if quoted spread or quote change too large.

    Args:
        table (Table): Original table
        max_spread (float): Maximum quoted spread, in dollars
        max_quote_change (float): Maximum quote change, in dollars

    Returns:
        Table: Cleaned table
    """

    # Sort by symbol and timestamp
    table = table.order_by(["symbol", "timestamp"])

    # Get previous midpoint using window function
    window = ibis.window(
        partition_by=table.symbol, order_by=table.timestamp, preceding=1, following=0
    )

    table = table.mutate(lmid=table.midpoint.over(window))

    # If quoted spread > $5 and bid (ask) has decreased (increased) by
    # $2.50 then remove that quote.
    bid_sel = (table.spread > max_spread) & (
        table.best_bid < table.lmid - max_quote_change
    )
    ask_sel = (table.spread > max_spread) & (
        table.best_ask > table.lmid + max_quote_change
    )

    # Use conditional logic to set values to null
    table = table.mutate(
        best_bid=bid_sel.ifelse(ibis.null(), table.best_bid),
        best_bidsizeshares=bid_sel.ifelse(ibis.null(), table.best_bidsizeshares),
        best_ask=ask_sel.ifelse(ibis.null(), table.best_ask),
        best_asksizeshares=ask_sel.ifelse(ibis.null(), table.best_asksizeshares),
    )

    return table


def filter_changes_only(table: "Table") -> "Table":
    """
    Keep only changes, i.e. consecutive entries with different quotes

    Args:
        table (Table): Original table

    Returns:
        Table: Cleaned table
    """

    # Create window for lag operations
    window = ibis.window(
        partition_by=table.symbol, order_by=table.timestamp, preceding=1, following=0
    )

    # Check for changes in quotes
    sel = (
        (table.best_ask != table.best_ask.over(window))
        | (table.best_bid != table.best_bid.over(window))
        | (table.best_bidsizeshares != table.best_bidsizeshares.over(window))
        | (table.best_asksizeshares != table.best_asksizeshares.over(window))
    )

    # Check for all null values in current and previous row
    sel_all_null = (
        table.best_ask.isnull()
        & table.best_bid.isnull()
        & table.best_bidsizeshares.isnull()
        & table.best_asksizeshares.isnull()
        & table.best_ask.over(window).isnull()
        & table.best_bid.over(window).isnull()
        & table.best_bidsizeshares.over(window).isnull()
        & table.best_asksizeshares.over(window).isnull()
    )

    return table.filter(sel | sel_all_null)


def clean_nbbo_table(
    nbbo: "Table",
    keep_qu_cond: Iterable[str] = HJ_KEEP_QU_COND,
    delete_canceled_quotes: bool = HJ_DELETE_CANCELED_QUOTES,
    delete_empty_quotes: bool = HJ_DELETE_EMPTY_QUOTES,
    delete_abnormal_spreads: bool = HJ_DELETE_ABNORMAL_SPREADS,
    keep_changes_only: bool = HJ_KEEP_CHANGES_ONLY,
    max_spread: float = float(HJ_MAX_SPREAD),
    max_quote_change: float = float(HJ_MAX_QUOTE_CHANGE),
    output_flags: bool = False,
) -> "Table":
    """Cleans a NBBO table retreived from TAQ in WRDS

    Args:
        nbbo (Table): Original NBBO table from TAQ in WRDS
        keep_qu_cond (Iterable[str], optional): Quote conditions to keep, or None for all conditions.
        delete_canceled_quotes (bool, optional): Delete canceled quotes.
        delete_empty_quotes (bool, optional): Delete empty quotes.
        delete_abnormal_spreads (bool, optional): Delete abnormal spreads.
        keep_changes_only (bool, optional): Keep only changes.
        max_spread (float, optional): Maximum quoted spread, in dollars.
        max_quote_change (float, optional): Maximum quote change, in dollars.
        output_flags (bool, optional): Output quote flags.

    Returns:
        Table: Cleaned NBBO table
    """

    cleaned_nbbo = merge_symbol(nbbo)

    if keep_qu_cond is not None:
        # Quote condition must be normal
        cleaned_nbbo = cleaned_nbbo.filter(cleaned_nbbo.qu_cond.isin(keep_qu_cond))

    if delete_canceled_quotes:
        # Delete if canceled
        cleaned_nbbo = cleaned_nbbo.filter(cleaned_nbbo.qu_cancel != "B")

    if delete_empty_quotes:
        cleaned_nbbo = filter_empty_quotes(cleaned_nbbo)

    cleaned_nbbo = compute_spreads_best_quotes(cleaned_nbbo)

    if delete_abnormal_spreads:
        cleaned_nbbo = filter_abnormal_spreads(
            cleaned_nbbo, max_spread=max_spread, max_quote_change=max_quote_change
        )

    if keep_changes_only:
        cleaned_nbbo = filter_changes_only(cleaned_nbbo)

    # Keep only relevant columns
    # Columns to output
    nbbo_out_cols = (
        NBBO_COLS_CLEAN + NBBO_COLS_FLAGS if output_flags else NBBO_COLS_CLEAN
    )

    return cleaned_nbbo.select(nbbo_out_cols)


def get_nbbo(
    date: datetime | date,
    conn: "wrds.sql.Connection",
    library: str | None = None,
    symbols: list[str] | None = None,
    start_time: datetime | time | None = HJ_START_TIME_QUOTES,
    end_time: datetime | time | None = HJ_END_TIME_QUOTES,
    keep_qu_cond: Iterable[str] = HJ_KEEP_QU_COND,
    delete_canceled_quotes: bool = HJ_DELETE_CANCELED_QUOTES,
    delete_empty_quotes: bool = HJ_DELETE_EMPTY_QUOTES,
    delete_abnormal_spreads: bool = HJ_DELETE_ABNORMAL_SPREADS,
    keep_changes_only: bool = HJ_KEEP_CHANGES_ONLY,
    max_spread: float = float(HJ_MAX_SPREAD),
    max_quote_change: float = float(HJ_MAX_QUOTE_CHANGE),
    output_flags: bool = False,
) -> "Table":
    """Retreives and cleans the NBBO from TAQ in WRDS

    Args:
        date (Union[datetime, date]): The requested date
        conn (wrds.sql.Connection): Open connection to WRDS
        library (str, optional): WRDS library to use, otherwise uses default.
        symbols (Optional[List[str]], optional): List of symbols to retreive, or None for all symbols.
        start_time (Optional[Union[datetime, time]], optional): Start time for quotes.
        end_time (Optional[Union[datetime, time]], optional): End time for quotes.
        keep_qu_cond (Iterable[str], optional): Quote conditions to keep, or None for all conditions.
        delete_canceled_quotes (bool, optional): Delete canceled quotes.
        delete_empty_quotes (bool, optional): Delete empty quotes.
        delete_abnormal_spreads (bool, optional): Delete abnormal spreads.
        keep_changes_only (bool, optional): Keep only changes.
        max_spread (float, optional): Maximum quoted spread, in dollars.
        max_quote_change (float, optional): Maximum quote change, in dollars.
        output_flags (bool, optional): Output quote flags.

    Returns:
        Table: NBBO table
    """
    # Execute the SQL query to get the raw data
    raw_data = conn.raw_sql(
        get_nbbo_sql_query(
            date=date,
            library=library,
            symbols=symbols,
            start_time=start_time,
            end_time=end_time,
        )
    )

    # Convert to Ibis table and clean
    return clean_nbbo_table(
        raw_data,
        keep_qu_cond=keep_qu_cond,
        delete_canceled_quotes=delete_canceled_quotes,
        delete_empty_quotes=delete_empty_quotes,
        delete_abnormal_spreads=delete_abnormal_spreads,
        keep_changes_only=keep_changes_only,
        max_spread=max_spread,
        max_quote_change=max_quote_change,
        output_flags=output_flags,
    )
