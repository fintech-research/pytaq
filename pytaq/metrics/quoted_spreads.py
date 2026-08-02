from datetime import date, datetime, time
from typing import TYPE_CHECKING, Union

import ibis

from .locks_crosses import filter_locks_crosses
from .timestamps import filter_timestamp

if TYPE_CHECKING:
    from ibis.expr.types import Table


def compute_quote_inforce(
    table: "Table",
    end_timestamp: datetime,
    groupby_col: str | list[str] = "symbol",
    timestamp_col: str = "timestamp",
    inforce_col: str = "inforce",
) -> "Table":
    """Compute time between each quote.

    Args:
        table (Table): Input table
        end_timestamp (datetime): End timestamp for the day
        groupby_col (Union[str, List[str]]): Column(s) to group by
        timestamp_col (str): Name of timestamp column
        inforce_col (str): Name of inforce column to create

    Returns:
        Table: Table with inforce column added
    """
    # Create window for lag operations
    window = ibis.window(
        partition_by=groupby_col, order_by=timestamp_col, preceding=1, following=0
    )

    # Compute time difference between consecutive quotes
    table = table.mutate(
        temp_diff=(
            table[timestamp_col] - table[timestamp_col].over(window)
        ).total_seconds()
    )

    # Shift the difference to get the inforce time for each quote
    window_shift = ibis.window(
        partition_by=groupby_col, order_by=timestamp_col, preceding=0, following=1
    )

    table = table.mutate(temp_inforce=table.temp_diff.over(window_shift))

    # Handle missing values for the last quote of the day
    table = table.mutate(
        inforce=table.temp_inforce.isnull().ifelse(
            ((end_timestamp - table[timestamp_col]).total_seconds()).abs(),
            table.temp_inforce,
        )
    )

    return table.drop("temp_diff", "temp_inforce")


def compute_spreads(table: "Table") -> "Table":
    """Compute spread measures.

    Args:
        table (Table): Input table with bid/ask data

    Returns:
        Table: Table with spread measures added
    """
    return table.mutate(
        quoted_spread_dollar=table.best_ask - table.best_bid,
        quoted_spread_percent=table.best_ask.log() - table.best_bid.log(),
        best_ofr_depth_dollar=table.best_ask * table.best_asksizeshares,
        best_bid_depth_dollar=table.best_bid * table.best_bidsizeshares,
        best_ofr_depth_share=table.best_asksizeshares,
        best_bid_depth_share=table.best_bidsizeshares,
    )


def compute_weighted_averages(
    table: "Table",
    measures: list[str],
    groupby_col: str | list[str] = "symbol",
    inforce_col: str = "inforce",
) -> "Table":
    """Compute weighted averages for measures.

    Args:
        table (Table): Input table
        measures (List[str]): List of measures to compute weighted averages for
        groupby_col (Union[str, List[str]]): Column(s) to group by
        inforce_col (str): Name of inforce column for weighting

    Returns:
        Table: Table with weighted averages
    """
    # Group by the specified columns
    grouped = table.group_by(groupby_col)

    # Build aggregation expressions for weighted averages
    aggregations = {}

    for measure in measures:
        # Weighted average: sum(measure * weight) / sum(weight)
        weighted_sum = (table[measure] * table[inforce_col]).sum()
        weight_sum = table[inforce_col].sum()

        # Handle case where sum of weights is 0 or all weights are null
        aggregations[measure] = (weight_sum == 0).ifelse(
            ibis.null(), weighted_sum / weight_sum
        )

    return grouped.agg(**aggregations)


def compute_weighted_spreads(
    date: date,
    off_nbbo_table: "Table",
    start_time: time,
    end_time: time,
) -> Union["Table", None]:
    """Compute weighted spreads for a given date.

    Args:
        date (date): Date to compute spreads for
        off_nbbo_table (Table): Official NBBO table
        start_time (time): Start time for the day
        end_time (time): End time for the day

    Returns:
        Union[Table, None]: Table with weighted spreads or None if no data
    """
    # Filter by timestamp
    filtered_table = filter_timestamp(
        off_nbbo_table, timestamp=off_nbbo_table.timestamp, start_time=start_time
    )

    # Check if we have any data
    if filtered_table.count().execute() == 0:
        return None

    # Compute quote inforce times
    table_with_inforce = compute_quote_inforce(
        filtered_table, end_timestamp=datetime.combine(date, end_time)
    )

    # Delete locked and crossed quotes
    table_filtered = filter_locks_crosses(
        table_with_inforce,
        asks=table_with_inforce.best_ask,
        bids=table_with_inforce.best_bid,
    )

    # Compute spreads
    table_with_spreads = compute_spreads(table_filtered)

    # Compute daily weighted averages
    return compute_weighted_averages(
        table_with_spreads,
        measures=[
            "quoted_spread_dollar",
            "quoted_spread_percent",
            "best_ofr_depth_dollar",
            "best_bid_depth_dollar",
            "best_ofr_depth_share",
            "best_bid_depth_share",
        ],
    )
