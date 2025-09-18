from datetime import date, datetime, time
from typing import TYPE_CHECKING, Iterable, List, Optional, Union

from ..hj_defaults import (
    HJ_END_TIME_QUOTES,
    HJ_KEEP_QU_COND,
    HJ_MAX_SPREAD,
    HJ_START_TIME_QUOTES,
)
from .common import merge_datetime, merge_symbol
from .postgresql import build_sql_query

if TYPE_CHECKING:
    import wrds
    from ibis.expr.types import Table

QUOTES_COLS_DB = [
    "date",
    "time_m",
    "ex",
    "sym_root",
    "sym_suffix",
    "bid",
    "bidsiz",
    "ask",
    "asksiz",
    "qu_cond",
    "qu_seqnum",
    "natbbo_ind",
    "qu_source",
    "qu_cancel",
]

QUOTES_COLS_CLEAN = [
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

QUOTES_COLS_FLAGS = ["qu_cond", "natbbo_ind", "qu_source", "qu_cancel"]


def get_quotes_table(date: Union[datetime, date]) -> str:
    """Returns the quotes table name for a given date for TAQ in WRDS

    Args:
        date (Union[datetime, date]): The requested date

    Returns:
        str: Quotes table name
    """
    return "cqm_" + date.strftime("%Y%m%d")


def get_quotes_sql_query(
    date: Union[datetime, date],
    library: Optional[str] = None,
    symbols: Optional[List[str]] = None,
    start_time: Optional[Union[datetime, time]] = HJ_START_TIME_QUOTES,
    end_time: Optional[Union[datetime, time]] = HJ_END_TIME_QUOTES,
) -> str:
    """Returns a SQL query to retreive the quotes from TAQ in WRDS

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
        columns=QUOTES_COLS_DB,
        table=get_quotes_table(date),
        library=library,
        symbols=symbols,
        start_time=start_time,
        end_time=end_time,
    )


def filter_withdrawned_quotes(quotes: "Table") -> "Table":
    """Filters withdrawned quotes from the quotes table

    NOTE: See H&J (2014) page 11 for details.

    Args:
        quotes (Table): Quotes table

    Returns:
        Table: Quotes table without withdrawned quotes
    """
    return quotes.filter(
        ~(
            quotes.ask.isnull()
            | (quotes.ask <= 0)
            | quotes.asksiz.isnull()
            | (quotes.asksiz <= 0)
            | quotes.bid.isnull()
            | (quotes.bid <= 0)
            | quotes.bidsiz.isnull()
            | (quotes.bidsiz <= 0)
        )
    )


def filter_quote_table(
    quotes: "Table",
    keep_qu_cond: Optional[Iterable[str]] = HJ_KEEP_QU_COND,
    delete_canceled_quotes: bool = True,
    delete_crossed_markets: bool = True,
    delete_withdrawned_quotes: bool = True,
    delete_abnormal_spreads: bool = True,
    max_spread: float = float(HJ_MAX_SPREAD),
    nbbo_only: bool = True,
) -> "Table":
    """Filters the quote table of the TAQ database based on specified criteria.

    Args:
        quotes (Table): The input quote table from the TAQ database.
        keep_qu_cond (Optional[Iterable[str]], default=HJ_KEEP_QU_COND): A list of quote conditions to keep.
        delete_canceled_quotes (bool, default=True): Whether to delete canceled quotes.
        delete_crossed_markets (bool, default=True): Whether to delete quotes with crossed markets.
        delete_withdrawned_quotes (bool, default=True): Whether to delete withdrawned quotes.
        delete_abnormal_spreads (bool, default=True): Whether to delete quotes with abnormal spreads.
        max_spread (float, default=HJ_MAX_SPREAD): The maximum spread allowed for a quote.
        nbbo_only (bool, default=True): Whether to keep only NBBO quotes.

    Returns:
        Table: The filtered quote table.

    """
    filtered_quotes = quotes

    if keep_qu_cond is not None and len(keep_qu_cond) > 0:
        # Quote condition must be normal
        filtered_quotes = filtered_quotes.filter(quotes.qu_cond.isin(keep_qu_cond))

    if delete_canceled_quotes:
        # Delete if canceled
        filtered_quotes = filtered_quotes.filter(quotes.qu_cancel != "B")

    if delete_crossed_markets:
        # Delete abnormal crossed markets
        filtered_quotes = filtered_quotes.filter(quotes.bid <= quotes.ask)

    if delete_abnormal_spreads:
        # Delete abnormal spreads
        filtered_quotes = filtered_quotes.mutate(spread=quotes.ask - quotes.bid)
        filtered_quotes = filtered_quotes.filter(filtered_quotes.spread <= max_spread)

    if delete_withdrawned_quotes:
        # Delete withdrawned quotes
        filtered_quotes = filter_withdrawned_quotes(filtered_quotes)

    # Keep only those to be merged with NBBO file
    if nbbo_only:
        filtered_quotes = filtered_quotes.filter(
            ((quotes.qu_source == "C") & (quotes.natbbo_ind == "1"))
            | ((quotes.qu_source == "N") & (quotes.natbbo_ind == "4"))
        )

    return filtered_quotes


def clean_quote_table(
    quotes: "Table",
    keep_qu_cond: Optional[Iterable[str]] = HJ_KEEP_QU_COND,
    delete_canceled_quotes: bool = True,
    delete_crossed_markets: bool = True,
    delete_withdrawned_quotes: bool = True,
    delete_abnormal_spreads: bool = True,
    max_spread: float = float(HJ_MAX_SPREAD),
    nbbo_only: bool = True,
    output_flags: bool = False,
) -> "Table":
    """Cleans a quote table retreived from TAQ in WRDS

    Args:
        quotes (Table): Original quote table from TAQ in WRDS
        keep_qu_cond (Optional[Iterable[str]], default=HJ_KEEP_QU_COND): A list of quote conditions to keep.
        delete_canceled_quotes (bool, default=True): Whether to delete canceled quotes.
        delete_crossed_markets (bool, default=True): Whether to delete quotes with crossed markets.
        delete_withdrawned_quotes (bool, default=True): Whether to delete withdrawned quotes.
        delete_abnormal_spreads (bool, default=True): Whether to delete quotes with abnormal spreads.
        max_spread (float, default=HJ_MAX_SPREAD): The maximum spread allowed for a quote.
        nbbo_only (bool, default=True): Whether to keep only NBBO quotes.
        output_flags (bool, default=False): Whether to output flags.

    Returns:
        Table: Cleaned quote table

    """
    cleaned_quotes = merge_symbol(merge_datetime(quotes))

    cleaned_quotes = filter_quote_table(
        quotes=cleaned_quotes,
        keep_qu_cond=keep_qu_cond,
        delete_canceled_quotes=delete_canceled_quotes,
        delete_crossed_markets=delete_crossed_markets,
        delete_withdrawned_quotes=delete_withdrawned_quotes,
        delete_abnormal_spreads=delete_abnormal_spreads,
        max_spread=max_spread,
        nbbo_only=nbbo_only,
    )

    # Rename columns and add new ones
    cleaned_quotes = cleaned_quotes.mutate(
        best_ask=cleaned_quotes.ask,
        best_bid=cleaned_quotes.bid,
        best_bidex=cleaned_quotes.ex,
        best_askex=cleaned_quotes.ex,
        # Bid/ask size are in round lots
        best_bidsizeshares=cleaned_quotes.bidsiz * 100,
        best_asksizeshares=cleaned_quotes.asksiz * 100,
    )

    # Select columns based on output_flags
    if output_flags:
        return cleaned_quotes.select(QUOTES_COLS_CLEAN + QUOTES_COLS_FLAGS)
    return cleaned_quotes.select(QUOTES_COLS_CLEAN)


def get_quotes(
    date: Union[datetime, date],
    conn: "wrds.sql.Connection",
    library: Optional[str] = None,
    symbols: Optional[List[str]] = None,
    start_time: Optional[Union[datetime, time]] = HJ_START_TIME_QUOTES,
    end_time: Optional[Union[datetime, time]] = HJ_END_TIME_QUOTES,
    keep_qu_cond: Optional[Iterable[str]] = HJ_KEEP_QU_COND,
    delete_canceled_quotes: bool = True,
    delete_crossed_markets: bool = True,
    delete_withdrawned_quotes: bool = True,
    delete_abnormal_spreads: bool = True,
    max_spread: float = float(HJ_MAX_SPREAD),
    nbbo_only: bool = True,
    output_flags: bool = False,
) -> "Table":
    """Retreives and cleans quotes from TAQ in WRDS

    Args:
        date (Union[datetime, date]): The requested date
        conn (wrds.sql.Connection): WRDS connection
        library (str, optional): WRDS library to use, otherwise uses default.
        symbols (Optional[List[str]], optional): List of symbols to retreive, or None for all symbols.
        start_time (Optional[Union[datetime, time]], optional): Start time for quotes.
        end_time (Optional[Union[datetime, time]], optional): End time for quotes.
        keep_qu_cond (Optional[Iterable[str]], optional): A list of quote conditions to keep. Defaults to HJ_KEEP_QU_COND.
        delete_canceled_quotes (bool, optional): Whether to delete canceled quotes. Defaults to True.
        delete_crossed_markets (bool, optional): Whether to delete quotes with crossed markets. Defaults to True.
        delete_withdrawned_quotes (bool, optional): Whether to delete withdrawned quotes. Defaults to True.
        delete_abnormal_spreads (bool, optional): Whether to delete quotes with abnormal spreads. Defaults to True.
        max_spread (float, optional): The maximum spread allowed for a quote. Defaults to HJ_MAX_SPREAD.
        nbbo_only (bool, optional): Whether to keep only NBBO quotes. Defaults to True.
        output_flags (bool, optional): Whether to output flags. Defaults to False.

    Returns:
        Table: Quotes table

    """
    # Execute the SQL query to get the raw data
    raw_data = conn.raw_sql(
        get_quotes_sql_query(
            date=date,
            library=library,
            symbols=symbols,
            start_time=start_time,
            end_time=end_time,
        )
    )

    # Convert to Ibis table and clean
    return clean_quote_table(
        raw_data,
        keep_qu_cond=keep_qu_cond,
        delete_canceled_quotes=delete_canceled_quotes,
        delete_crossed_markets=delete_crossed_markets,
        delete_withdrawned_quotes=delete_withdrawned_quotes,
        delete_abnormal_spreads=delete_abnormal_spreads,
        max_spread=max_spread,
        nbbo_only=nbbo_only,
        output_flags=output_flags,
    )
