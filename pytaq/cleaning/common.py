import datetime

import ibis


def merge_datetime(t: ibis.Table) -> ibis.Table:
    # Cast date to timestamp (midnight)
    base_ts = t.date.cast("timestamp")

    # Break time_m into integer seconds and fractional microseconds
    int_seconds = t.time_m.floor().cast("int64")
    microseconds = ((t.time_m - t.time_m.floor()) * 1_000_000).round().cast("int64")

    # Add separately
    ts_with_seconds = base_ts + int_seconds.cast("interval('s')")
    ts_with_microseconds = ts_with_seconds + microseconds.cast("interval('us')")

    return t.mutate(timestamp=ts_with_microseconds)


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
