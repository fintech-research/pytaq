from datetime import time
from typing import TYPE_CHECKING, Union

import ibis
import ibis.expr.types as ir

if TYPE_CHECKING:
    from ibis.expr.types import Column, Table


def filter_timestamp(
    table: "Table",
    timestamp: Union[str, "Column"],
    start_time: time | None = None,
    end_time: time | None = None,
) -> "Table":
    """Filters a table based on timestamp

    Args:
        table (Table): Table to filter
        timestamp (Union[str, Column]): Timestamp column to use for filtering
        start_time (Optional[time], optional): Start time
        end_time (Optional[time], optional): End time

    Returns:
        Table: Filtered table
    """
    if isinstance(timestamp, str):
        timestamp_col = table[timestamp]
    elif isinstance(timestamp, ir.Column):
        timestamp_col = timestamp
    else:
        raise ValueError("timestamp should be an Ibis Column or a column name.")

    # Build filter conditions
    conditions = []

    if start_time is not None:
        conditions.append(timestamp_col.time() >= start_time)

    if end_time is not None:
        conditions.append(timestamp_col.time() < end_time)

    # Apply filters
    if conditions:
        return table.filter(ibis.and_(*conditions))

    return table
