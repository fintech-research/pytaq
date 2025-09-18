import datetime

import ibis

from ..hj_defaults import HJ_END_TIME_TRADES, HJ_START_TIME_TRADES
from .common import filter_by_time, merge_datetime, merge_symbol

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


def clean_trades(
    t: ibis.Table,
    exclude_corrections: bool = True,
    price_positive_only: bool = True,
    start_time: datetime.time | None = HJ_START_TIME_TRADES,
    end_time: datetime.time | None = HJ_END_TIME_TRADES,
) -> ibis.Table:
    t = t.rename({col.lower(): col for col in t.columns})
    t = merge_datetime(merge_symbol(t))
    t = filter_by_time(t, start_time, end_time)
    if exclude_corrections:
        t = t.filter(t.tr_corr == "00")
    if price_positive_only:
        t = t.filter(t.price > 0)

    t = t.mutate(dollar=t.price * t.size)

    return t[TRADES_COLS_CLEAN]
