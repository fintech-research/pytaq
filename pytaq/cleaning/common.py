"""Normalisation shared by every cleaning entry point.

TAQ reaches PyTAQ in two shapes, and `time_m` differs between them:

- the **WRDS postgres server** types it as a SQL ``time``
- **local exports** commonly carry it as a ``double`` of seconds since midnight

Both are real and both are in use, so the helpers here dispatch on the column
type rather than assuming one. Getting this wrong is not subtle: the wrong
branch raises rather than producing quiet nonsense.
"""

import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ibis.expr.types import IntegerValue, Table, TimestampValue


def _seconds_since_midnight(t: datetime.time) -> float:
    """Convert a Python time to seconds since midnight."""
    return t.hour * 3600 + t.minute * 60 + t.second + t.microsecond / 1_000_000


def _timestamp_from_time_column(table: "Table") -> "TimestampValue":
    """Combine a date with a SQL ``time`` column.

    Casting a time to an interval is not portable, so the components are added
    separately. Verified to produce identical results on DuckDB and postgres.
    """
    time_m = table.time_m
    seconds: IntegerValue = (
        time_m.hour().cast("int64") * 3600
        + time_m.minute().cast("int64") * 60
        + time_m.second().cast("int64")
    )
    return (
        table.date.cast("timestamp")
        + seconds.cast("interval('s')")
        + time_m.microsecond().cast("int64").cast("interval('us')")
    )


def _timestamp_from_numeric_column(table: "Table") -> "TimestampValue":
    """Combine a date with a numeric seconds-since-midnight column."""
    time_m = table.time_m
    whole_seconds = time_m.floor().cast("int64")
    microseconds = ((time_m - time_m.floor()) * 1_000_000).round().cast("int64")
    return (
        table.date.cast("timestamp")
        + whole_seconds.cast("interval('s')")
        + microseconds.cast("interval('us')")
    )


def merge_datetime(table: "Table") -> "Table":
    """Merge the separate date and time columns into a single timestamp.

    Accepts either shape of ``time_m``: a SQL ``time``, as the WRDS postgres
    server returns, or a numeric count of seconds since midnight, as local
    exports commonly carry.

    Sub-microsecond precision is dropped. WRDS exposes it separately as
    ``time_m_nano`` and PyTAQ does not currently use it.

    Args:
        table (Table): Table with ``date`` and ``time_m`` columns

    Returns:
        Table: The input table with a ``timestamp`` column added

    Raises:
        TypeError: If ``time_m`` is neither a time nor a numeric column
    """
    dtype = table.time_m.type()

    if dtype.is_time():
        timestamp = _timestamp_from_time_column(table)
    elif dtype.is_numeric():
        timestamp = _timestamp_from_numeric_column(table)
    else:
        raise TypeError(
            f"time_m must be a time or a numeric count of seconds since "
            f"midnight, got {dtype}."
        )

    return table.mutate(timestamp=timestamp)


def merge_symbol(table: "Table") -> "Table":
    """Merge the root and suffix into a single symbol column.

    Args:
        table (Table): Table with ``sym_root`` and ``sym_suffix`` columns

    Returns:
        Table: The input table with a ``symbol`` column added
    """
    symbol = table.sym_suffix.isnull().ifelse(
        table.sym_root, table.sym_root + " " + table.sym_suffix
    )
    return table.mutate(symbol=symbol.strip())


def filter_by_time(
    table: "Table",
    start_time: datetime.time | None = None,
    end_time: datetime.time | None = None,
) -> "Table":
    """Restrict a table to a time-of-day window, inclusive at both ends.

    Like :func:`merge_datetime`, this accepts either shape of ``time_m``.

    Args:
        table (Table): Table with a ``time_m`` column
        start_time (datetime.time | None): Lower bound, or None for no bound
        end_time (datetime.time | None): Upper bound, or None for no bound

    Returns:
        Table: The filtered table

    Raises:
        TypeError: If ``time_m`` is neither a time nor a numeric column
    """
    if start_time is None and end_time is None:
        return table

    dtype = table.time_m.type()
    if dtype.is_time():
        lower = start_time
        upper = end_time
    elif dtype.is_numeric():
        lower = _seconds_since_midnight(start_time) if start_time else None
        upper = _seconds_since_midnight(end_time) if end_time else None
    else:
        raise TypeError(
            f"time_m must be a time or a numeric count of seconds since "
            f"midnight, got {dtype}."
        )

    if lower is not None and upper is not None:
        return table.filter(table.time_m.between(lower, upper))
    if lower is not None:
        return table.filter(table.time_m >= lower)
    return table.filter(table.time_m <= upper)
