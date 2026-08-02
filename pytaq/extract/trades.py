from datetime import date, datetime, time
from typing import TYPE_CHECKING

from ..hj_defaults import HJ_END_TIME_TRADES, HJ_START_TIME_TRADES
from .common import merge_datetime, merge_symbol
from .postgresql import build_sql_query

if TYPE_CHECKING:
    import wrds
    from ibis.expr.types import Table

TRADES_COLS_DB = [
    "date",
    "time_m",
    "ex",
    "sym_root",
    "sym_suffix",
    "size",
    "price",
    "tr_seqnum",
    "tr_scond",
]

TRADES_COLS_CLEAN = [
    "timestamp",
    "symbol",
    "ex",
    "size",
    "price",
    "dollar",
    "tr_seqnum",
    "tr_scond",
]


def get_trade_table(date: datetime | date) -> str:
    """Returns the trade table name for a given date for TAQ in WRDS

    Args:
        date (Union[datetime, date]): The requested date

    Returns:
        str: Trade table name
    """
    return "ctm_" + date.strftime("%Y%m%d")


def get_trades_sql_query(
    date: datetime | date,
    library: str | None = None,
    symbols: list[str] | None = None,
    start_time: datetime | time | None = HJ_START_TIME_TRADES,
    end_time: datetime | time | None = HJ_END_TIME_TRADES,
) -> str:
    """Returns a SQL query to retreive trades from TAQ in WRDS

    Args:
        date (Union[datetime, date]): The requested date
        library (str, optional): WRDS library to use, otherwise uses default.
        symbols (Optional[List[str]], optional): List of symbols to retreive, or None for all symbols.
        start_time (Optional[Union[datetime, time]], optional): Start time for trades.
        end_time (Optional[Union[datetime, time]], optional): End time for trades.

    Returns:
        str: SQL query
    """
    return build_sql_query(
        columns=TRADES_COLS_DB,
        table=get_trade_table(date),
        library=library,
        symbols=symbols,
        start_time=start_time,
        end_time=end_time,
        extra_condition=" AND tr_corr = '00' AND price > 0",
    )


def clean_trade_table(trades: "Table") -> "Table":
    """Cleans a trade table retreived from TAQ in WRDS

    Args:
        trades (Table): Original trades table from TAQ in WRDS

    Returns:
        Table: Cleaned trades table
    """
    cleaned_trades = merge_symbol(merge_datetime(trades))

    # Compute dollar value
    cleaned_trades = cleaned_trades.mutate(dollar=trades.price * trades.size)

    return cleaned_trades.select(TRADES_COLS_CLEAN)


def get_trades(
    date: datetime | date,
    conn: "wrds.sql.Connection",
    library: str | None = None,
    symbols: list[str] | None = None,
    start_time: datetime | time | None = HJ_START_TIME_TRADES,
    end_time: datetime | time | None = HJ_END_TIME_TRADES,
) -> "Table":
    """Retreives and cleans trades from TAQ in WRDS

    Args:
        date (Union[datetime, date]): The requested date
        conn (wrds.sql.Connection): Open connection to WRDS
        library (str, optional): WRDS library to use, otherwise uses default.
        symbols (Optional[List[str]], optional): List of symbols to retreive, or None for all symbols.
        start_time (Optional[Union[datetime, time]], optional): Start time for trades.
        end_time (Optional[Union[datetime, time]], optional): End time for trades.

    Returns:
        Table: Trades table
    """
    # Execute the SQL query to get the raw data
    raw_data = conn.raw_sql(
        get_trades_sql_query(
            date=date,
            library=library,
            symbols=symbols,
            start_time=start_time,
            end_time=end_time,
        )
    )

    # Convert to Ibis table and clean
    return clean_trade_table(raw_data)
