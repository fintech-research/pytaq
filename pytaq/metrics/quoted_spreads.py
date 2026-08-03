from datetime import date, datetime, time
from typing import TYPE_CHECKING, Union

import ibis

from ..cleaning.common import TIMESTAMP_NS_COL, epoch_nanoseconds
from .conventions import DEFAULT_PERCENT_METHOD, PercentMethod, check_percent_method
from .locks_crosses import filter_locks_crosses
from .timestamps import filter_timestamp

if TYPE_CHECKING:
    from ibis.expr.types import Table

NANOSECONDS_PER_SECOND = 1_000_000_000
MICROSECONDS_PER_SECOND = 1_000_000


def compute_quote_inforce(
    table: "Table",
    end_timestamp: datetime,
    groupby_col: str | list[str] = "symbol",
    timestamp_col: str = "timestamp",
    inforce_col: str = "inforce",
    order_col: str | None = TIMESTAMP_NS_COL,
) -> "Table":
    """Compute how long each quote stands, in seconds.

    A quote is in force until the next quote for the same symbol. The day's last
    quote has no successor and stands until `end_timestamp`.

    The result is a real number of seconds, which is what Holden and Jacobsen
    weight by: their `inforce = abs(dif(InterpolatedTime))` differences a time
    measured in fractional seconds. This used to be computed with
    `delta(unit="second")`, which truncates both sides to the second before
    subtracting, so it returned the number of one-second boundaries crossed
    rather than a duration: a quote replaced 900ms later scored 0, and one
    replaced 200ms later scored 1 if it happened to straddle a boundary. Since
    DTAQ NBBO updates are overwhelmingly sub-second, that gave most quotes zero
    weight and left the time-weighted averages riding on the minority that
    straddled a boundary.

    Durations come from the integer nanosecond key when the table carries one,
    which is exact and needs no date arithmetic. Otherwise they come from a
    microsecond difference on `timestamp_col`.

    Args:
        table (Table): Input table
        end_timestamp (datetime): When the last quote of the day stops standing
        groupby_col (Union[str, List[str]]): Column(s) to group by
        timestamp_col (str): Name of timestamp column
        inforce_col (str): Name of inforce column to create
        order_col (str | None): Column giving the true event order, defaulting
            to the nanosecond key. Falls back to `timestamp_col` when absent

    Returns:
        Table: Table with inforce column added, in seconds
    """
    use_ns = order_col is not None and order_col in table.columns

    # Note: ibis.window takes group_by, not partition_by.
    window = ibis.window(
        group_by=groupby_col, order_by=order_col if use_ns else timestamp_col
    )

    if use_ns:
        current = table[order_col]
        to_next = current.lead().over(window) - current
        to_close = ibis.literal(epoch_nanoseconds(end_timestamp), "int64") - current
        divisor = NANOSECONDS_PER_SECOND
    else:
        current = table[timestamp_col]
        to_next = current.lead().over(window).delta(current, unit="microsecond")
        to_close = ibis.timestamp(end_timestamp).delta(current, unit="microsecond")
        divisor = MICROSECONDS_PER_SECOND

    # Cast before dividing: integer division truncates on postgres, which would
    # reintroduce exactly the bug this function used to have.
    seconds_to_next = to_next.cast("float64") / divisor

    # H&J clamp the closing leg at zero, so a quote at or past the close counts
    # for nothing rather than for a negative duration.
    seconds_to_close = ibis.greatest(to_close.cast("float64") / divisor, 0.0)

    return table.mutate(
        **{
            inforce_col: seconds_to_next.isnull().ifelse(
                seconds_to_close, seconds_to_next
            )
        }
    )


def compute_spreads(
    table: "Table",
    percent_method: PercentMethod = DEFAULT_PERCENT_METHOD,
) -> "Table":
    """Compute quoted spreads and depth for a quote table.

    Args:
        table (Table): Quote table carrying `best_bid`, `best_ask` and their
            sizes in shares
        percent_method (PercentMethod): `"ratio"` for the Holden and Jacobsen
            definition, the dollar spread over the midpoint, or `"log"` for the
            log difference

    Returns:
        Table: Input table with spread and depth measures added
    """
    check_percent_method(percent_method)

    dollar = table.best_ask - table.best_bid
    if percent_method == "ratio":
        midpoint = (table.best_ask + table.best_bid) / 2
        percent = dollar / midpoint
    else:
        percent = table.best_ask.log() - table.best_bid.log()

    return table.mutate(
        quoted_spread_dollar=dollar,
        quoted_spread_percent=percent,
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
        # Weighted average: sum(measure * weight) / sum(weight), with both sums
        # restricted to the rows the numerator can actually use. Summing the
        # full weight column while the numerator skips nulls biases the result
        # toward zero in proportion to the weight the missing rows carry.
        observed = table[measure].notnull() & table[inforce_col].notnull()
        weighted_sum = (table[measure] * table[inforce_col]).sum(where=observed)
        weight_sum = table[inforce_col].sum(where=observed)

        # No observed weight means there is nothing to average, not zero.
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
