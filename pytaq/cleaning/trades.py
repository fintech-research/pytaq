import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ibis.expr.types import Table

from ..hj_defaults import HJ_END_TIME_TRADES, HJ_START_TIME_TRADES
from .common import TIMESTAMP_NS_COL, filter_by_time, merge_datetime, merge_symbol

# `timestamp_ns` is kept, not dropped. Everything downstream that needs event
# ordering or an exact interval reads it: the trade-to-quote match, the T+horizon
# match, the tick test and the time a quote is in force. Dropping it here silently
# demoted all of those to the microsecond `timestamp`, which is what a postgres
# timestamp can hold but not what TAQ resolves events to.
TRADES_COLS_CLEAN = [
    "timestamp",
    TIMESTAMP_NS_COL,
    "symbol",
    "ex",
    "size",
    "price",
    "dollar",
    "tr_seqnum",
    "tr_scond",
]


def clean_trades(
    t: "Table",
    exclude_corrections: bool = True,
    price_positive_only: bool = True,
    start_time: datetime.time | None = HJ_START_TIME_TRADES,
    end_time: datetime.time | None = HJ_END_TIME_TRADES,
) -> "Table":
    """Clean a raw trade table from TAQ.

    Merges the date and time into a timestamp and the symbol root and suffix
    into a symbol, drops corrected trades and non-positive prices, restricts to
    the trade window, and adds dollar volume.

    Args:
        t (Table): Raw trade table
        exclude_corrections (bool): Drop trades whose correction code is not "00"
        price_positive_only (bool): Drop trades with a non-positive price
        start_time (datetime.time | None): Start of the trade window
        end_time (datetime.time | None): End of the trade window

    Returns:
        Table: Cleaned trades
    """
    t = t.rename({col.lower(): col for col in t.columns})
    t = merge_datetime(merge_symbol(t))
    t = filter_by_time(t, start_time, end_time)
    if exclude_corrections:
        t = t.filter(t.tr_corr == "00")
    if price_positive_only:
        t = t.filter(t.price > 0)

    t = t.mutate(dollar=t.price * t.size)

    return t[TRADES_COLS_CLEAN]
