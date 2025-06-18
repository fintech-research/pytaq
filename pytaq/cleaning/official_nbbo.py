import datetime

import ibis

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
    t: ibis.Table,
    start_time: datetime.time | None = HJ_START_TIME_QUOTES,
    end_time: datetime.time | None = HJ_END_TIME_QUOTES,
) -> ibis.Table:
    t = merge_datetime(merge_symbol(t))
    t = filter_by_time(t, start_time, end_time)
    return t[OFF_NBBO_COLS_CLEAN]
