from datetime import date, datetime, time
from typing import TYPE_CHECKING

from ..hj_defaults import HJ_END_TIME_QUOTES, HJ_START_TIME_QUOTES
from .common import merge_symbol
from .postgresql import build_sql_query

if TYPE_CHECKING:
    import wrds
    from ibis.expr.types import Table

OFF_NBBO_COLS_DB = [
    "date",
    "time_m",
    "sym_root",
    "sym_suffix",
    "best_bid",
    "best_bidsizeshares",
    "best_ask",
    "best_asksizeshares",
]

OFF_NBBO_COLS_CLEAN = [
    "timestamp",
    "symbol",
    "best_bid",
    "best_bidsizeshares",
    "best_ask",
    "best_asksizeshares",
]


def get_official_complete_nbbo_table(date: datetime | date) -> str:
    """Returns the Official complete NBBO table name for a given date for TAQ in WRDS

    Args:
        date (Union[datetime, date]): The requested date

    Returns:
        str: Official complete NBBO table name
    """
    return "complete_nbbo_" + date.strftime("%Y%m%d")


def get_official_complete_nbbo_sql_query(
    date: datetime | date,
    library: str | None = None,
    symbols: list[str] | None = None,
    start_time: datetime | time | None = HJ_START_TIME_QUOTES,
    end_time: datetime | time | None = HJ_END_TIME_QUOTES,
) -> str:
    """Returns a SQL query to retreive the official complete NBBO from TAQ in WRDS

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
        columns=OFF_NBBO_COLS_DB,
        table=get_official_complete_nbbo_table(date),
        library=library,
        symbols=symbols,
        start_time=start_time,
        end_time=end_time,
    )


def clean_official_complete_nbbo_table(nbbo: "Table") -> "Table":
    """Cleans the official complete NBBO table

    Args:
        nbbo (Table): Original table

    Returns:
        Table: Cleaned table
    """
    cleaned_nbbo = merge_symbol(nbbo)
    cleaned_nbbo = cleaned_nbbo.order_by(["symbol", "timestamp"])
    return cleaned_nbbo.select(OFF_NBBO_COLS_CLEAN)


def get_official_complete_nbbo(
    date: datetime | date,
    conn: "wrds.sql.Connection",
    library: str | None = None,
    symbols: list[str] | None = None,
    start_time: datetime | time | None = HJ_START_TIME_QUOTES,
    end_time: datetime | time | None = HJ_END_TIME_QUOTES,
) -> "Table":
    """Retreives and cleans the official complete NBBO table from TAQ in WRDS

    Args:
        date (Union[datetime, date]): The requested date
        conn (wrds.sql.Connection): Open connection to WRDS
        library (str, optional): WRDS library to use, otherwise uses default.
        symbols (Optional[List[str]], optional): List of symbols to retreive, or None for all symbols.
        start_time (Optional[Union[datetime, time]], optional): Start time for quotes.
        end_time (Optional[Union[datetime, time]], optional): End time for quotes.

    Returns:
        Table: Official complete NBBO table
    """
    # Execute the SQL query to get the raw data
    raw_data = conn.raw_sql(
        get_official_complete_nbbo_sql_query(
            date=date,
            library=library,
            symbols=symbols,
            start_time=start_time,
            end_time=end_time,
        )
    )

    # Convert to Ibis table and clean
    return clean_official_complete_nbbo_table(raw_data)
