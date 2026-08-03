import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ibis.expr.types import Table

from ..hj_defaults import HJ_END_TIME_QUOTES, HJ_START_TIME_QUOTES
from .common import filter_by_time, merge_datetime, merge_symbol

OFF_NBBO_COLS_CLEAN = [
    "timestamp",
    "symbol",
    "best_bid",
    "best_bidsizeshares",
    "best_ask",
    "best_asksizeshares",
]


def clean_official_complete_nbbo(
    t: "Table",
    start_time: datetime.time | None = HJ_START_TIME_QUOTES,
    end_time: datetime.time | None = HJ_END_TIME_QUOTES,
) -> "Table":
    """Clean WRDS's official complete NBBO table.

    Merges the date and time into a timestamp, the symbol root and suffix into
    a symbol, and restricts to the quote window. No further filtering: the SIP
    has already resolved the NBBO, so the per-venue repairs in `cleaning.quotes`
    do not apply.

    Args:
        t (Table): Raw official complete NBBO table
        start_time (datetime.time | None): Start of the quote window
        end_time (datetime.time | None): End of the quote window

    Returns:
        Table: Cleaned official NBBO
    """
    t = t.rename({col.lower(): col for col in t.columns})
    t = merge_datetime(merge_symbol(t))
    t = filter_by_time(t, start_time, end_time)
    return t[OFF_NBBO_COLS_CLEAN]
