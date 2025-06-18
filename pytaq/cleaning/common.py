import datetime

import ibis


def merge_datetime(t: ibis.Table) -> ibis.Table:
    year = t.date.year()
    month = t.date.month()
    day = t.date.day()
    ts = ibis.timestamp(year, month, day, 0, 0, 0) + t.time_m.sub(
        datetime.time(0, 0, 0)
    )
    return t.mutate(timestamp=ts)


def merge_symbol(t: ibis.Table) -> ibis.Table:
    symbol = t.sym_suffix.isnull().ifelse(t.sym_root, t.sym_root + " " + t.sym_suffix)
    return t.mutate(symbol=symbol.strip())


def filter_by_time(
    t: ibis.Table,
    start_time: datetime.time | None = None,
    end_time: datetime.time | None = None,
) -> ibis.Table:
    if start_time and end_time:
        t = t.filter(t.time_m.between(start_time, end_time))
    elif start_time:
        t = t.filter(t.time_m >= start_time)
    elif end_time:
        t = t.filter(t.time_m <= end_time)
    return t
