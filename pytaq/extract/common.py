import datetime
from typing import TYPE_CHECKING

import ibis

if TYPE_CHECKING:
    from ibis.expr.types import Table


def merge_datetime(table: "Table") -> "Table":
    """Merges date and time columns into a timestamp column.

    Args:
        table (Table): Original Ibis table with 'date' and 'time_m' columns

    Returns:
        Table: Table with merged timestamp column
    """
    # Cast date to timestamp (midnight)
    base_ts = table.date.cast("timestamp")

    # Break time_m into integer seconds and fractional microseconds
    int_seconds = table.time_m.floor().cast("int64")
    microseconds = (
        ((table.time_m - table.time_m.floor()) * 1_000_000).round().cast("int64")
    )

    # Add separately
    ts_with_seconds = base_ts + int_seconds.cast("interval('s')")
    ts_with_microseconds = ts_with_seconds + microseconds.cast("interval('us')")

    return table.mutate(timestamp=ts_with_microseconds)


def merge_symbol(table: "Table") -> "Table":
    """Merges symbol and sym_root columns.

    Args:
        table (Table): Original Ibis table with 'sym_root' and 'sym_suffix' columns

    Returns:
        Table: Table with merged symbol column
    """
    # Merge symbol using conditional logic
    symbol = table.sym_suffix.isnull().ifelse(
        table.sym_root, table.sym_root + " " + table.sym_suffix
    )
    return table.mutate(symbol=symbol.strip())


def filter_by_time(
    table: "Table",
    start_time: datetime.time | None = None,
    end_time: datetime.time | None = None,
) -> "Table":
    """Filters table by time range.

    Args:
        table (Table): Input table with 'time_m' column (numeric seconds since midnight)
        start_time (datetime.time | None): Start time filter
        end_time (datetime.time | None): End time filter

    Returns:
        Table: Filtered table
    """

    # Convert datetime.time objects to seconds since midnight
    def time_to_seconds(t: datetime.time) -> float:
        return t.hour * 3600 + t.minute * 60 + t.second + t.microsecond / 1_000_000

    if start_time and end_time:
        start_seconds = time_to_seconds(start_time)
        end_seconds = time_to_seconds(end_time)
        table = table.filter(table.time_m.between(start_seconds, end_seconds))
    elif start_time:
        start_seconds = time_to_seconds(start_time)
        table = table.filter(table.time_m >= start_seconds)
    elif end_time:
        end_seconds = time_to_seconds(end_time)
        table = table.filter(table.time_m <= end_seconds)
    return table
