from datetime import timedelta
from typing import TYPE_CHECKING, Iterable, Tuple

import ibis
from .locks_crosses import filter_locks_crosses
from .signs import BASE_SIGNS, RETAIL_SIGNS

from ..utils.float_approx import correct_float_approx

if TYPE_CHECKING:
    from ibis.expr.types import Column, Table


def dollar_realized_spread(
    sign: "Column",
    price: "Column",
    midpoint_next: "Column",
) -> "Column":
    """Compute dollar realized spread.

    Args:
        sign (Column): Trade sign column
        price (Column): Price column
        midpoint_next (Column): Next midpoint column

    Returns:
        Column: Dollar realized spread
    """
    s = sign * (price - midpoint_next) * 2
    return correct_float_approx(s, price, midpoint_next)


def percent_realized_spread(
    sign: "Column",
    price: "Column",
    midpoint_next: "Column",
) -> "Column":
    """Compute percent realized spread.

    Args:
        sign (Column): Trade sign column
        price (Column): Price column
        midpoint_next (Column): Next midpoint column

    Returns:
        Column: Percent realized spread
    """
    s = sign * (ibis.func.ln(price) - ibis.func.ln(midpoint_next)) * 2
    return correct_float_approx(s, price, midpoint_next)


def dollar_price_impact(
    sign: "Column",
    midpoint: "Column",
    midpoint_next: "Column",
) -> "Column":
    """Compute dollar price impact.

    Args:
        sign (Column): Trade sign column
        midpoint (Column): Current midpoint column
        midpoint_next (Column): Next midpoint column

    Returns:
        Column: Dollar price impact
    """
    s = sign * (midpoint_next - midpoint) * 2
    return correct_float_approx(s, midpoint, midpoint_next)


def percent_price_impact(
    sign: "Column",
    midpoint: "Column",
    midpoint_next: "Column",
) -> "Column":
    """Compute percent price impact.

    Args:
        sign (Column): Trade sign column
        midpoint (Column): Current midpoint column
        midpoint_next (Column): Next midpoint column

    Returns:
        Column: Percent price impact
    """
    s = sign * (ibis.func.ln(midpoint_next) - ibis.func.ln(midpoint)) * 2
    return correct_float_approx(s, midpoint, midpoint_next)


def rs_and_pi(
    table: "Table",
    signs: Iterable[str],
    suffix: str = "",
    sign_col_prefix: str = "BuySell",
    price_col: str = "price",
    midpoint_col: str = "midpoint",
    midpoint_next_col: str = "midpoint_next",
    dollar_realized_spread_prefix: str = "DollarRealizedSpread_",
    percent_realized_spread_prefix: str = "PercentRealizedSpread_",
    dollar_price_impact_prefix: str = "DollarPriceImpact_",
    percent_price_impact_prefix: str = "PercentPriceImpact_",
) -> "Table":
    """Compute realized spreads and price impacts.

    Args:
        table (Table): Input table
        signs (Iterable[str]): Sign suffixes to process
        suffix (str): Suffix for output columns
        sign_col_prefix (str): Prefix for sign columns
        price_col (str): Name of price column
        midpoint_col (str): Name of midpoint column
        midpoint_next_col (str): Name of next midpoint column
        dollar_realized_spread_prefix (str): Prefix for dollar realized spread columns
        percent_realized_spread_prefix (str): Prefix for percent realized spread columns
        dollar_price_impact_prefix (str): Prefix for dollar price impact columns
        percent_price_impact_prefix (str): Prefix for percent price impact columns

    Returns:
        Table: Table with realized spreads and price impacts added
    """
    price = table[price_col]
    midpoint = table[midpoint_col]
    midpoint_next = table[midpoint_next_col]

    result_table = table

    for sign_col_suffix in signs:
        sign = table[f"{sign_col_prefix}{sign_col_suffix}"]

        result_table = result_table.mutate(
            **{
                f"{dollar_realized_spread_prefix}{sign_col_suffix}{suffix}": dollar_realized_spread(
                    sign=sign,
                    price=price,
                    midpoint_next=midpoint_next,
                ),
                f"{percent_realized_spread_prefix}{sign_col_suffix}{suffix}": percent_realized_spread(
                    sign=sign,
                    price=price,
                    midpoint_next=midpoint_next,
                ),
                f"{dollar_price_impact_prefix}{sign_col_suffix}{suffix}": dollar_price_impact(
                    sign=sign,
                    midpoint=midpoint,
                    midpoint_next=midpoint_next,
                ),
                f"{percent_price_impact_prefix}{sign_col_suffix}{suffix}": percent_price_impact(
                    sign=sign,
                    midpoint=midpoint,
                    midpoint_next=midpoint_next,
                ),
            }
        )

    return result_table


def merge_future_nbbo(
    table: "Table",
    nbbo_table: "Table",
    delay: timedelta,
    symbol_col: str = "symbol",
    timestamp_col: str = "timestamp",
    best_bid_col: str = "best_bid",
    best_ask_col: str = "best_ask",
    midpoint_col: str = "midpoint",
    suffixes: Tuple[str, str] = ("", "_next"),
) -> "Table":
    """Merge future NBBO data with current data.

    Note: This is a simplified implementation. The original pandas merge_asof
    functionality may need more sophisticated handling in Ibis depending on the backend.

    Args:
        table (Table): Main table
        nbbo_table (Table): NBBO table
        delay (timedelta): Delay to apply
        symbol_col (str): Symbol column name
        timestamp_col (str): Timestamp column name
        best_bid_col (str): Best bid column name
        best_ask_col (str): Best ask column name
        midpoint_col (str): Midpoint column name
        suffixes (Tuple[str, str]): Suffixes for merged columns

    Returns:
        Table: Merged table
    """
    # Prepare NBBO table with adjusted timestamps and midpoint
    next_table = nbbo_table.select(
        [timestamp_col, symbol_col, best_bid_col, best_ask_col]
    ).mutate(
        midpoint_next=(nbbo_table[best_bid_col] + nbbo_table[best_ask_col]) / 2,
        timestamp_adjusted=nbbo_table[timestamp_col] - delay,
    )

    # Sort both tables
    table_sorted = table.order_by([timestamp_col, symbol_col])
    next_table_sorted = next_table.order_by(["timestamp_adjusted", symbol_col])

    # Join on symbol and timestamp (simplified - may need window functions for proper asof merge)
    # This is a basic implementation - the actual asof merge logic may need to be more sophisticated
    return table_sorted.join(
        next_table_sorted,
        predicates=[
            table_sorted[symbol_col] == next_table_sorted[symbol_col],
            table_sorted[timestamp_col] >= next_table_sorted.timestamp_adjusted,
        ],
        how="left",
    )


def compute_rs_and_pi(
    trade_and_nbbo_table: "Table",
    off_nbbo_table: "Table",
    delay: timedelta = timedelta(minutes=5),
    suffix: str = "5min",
    track_retail: bool = False,
) -> "Table":
    """Compute realized spreads and price impacts.

    Args:
        trade_and_nbbo_table (Table): Table with trade and NBBO data
        off_nbbo_table (Table): Official NBBO table
        delay (timedelta): Delay for future NBBO lookup
        suffix (str): Suffix for output columns
        track_retail (bool): Whether to track retail trades

    Returns:
        Table: Table with realized spreads and price impacts
    """
    merged_table = merge_future_nbbo(
        table=trade_and_nbbo_table, nbbo_table=off_nbbo_table, delay=delay
    )

    filtered_table = filter_locks_crosses(
        merged_table,
        asks=merged_table["best_ask_next"],
        bids=merged_table["best_bid_next"],
    )

    signs = BASE_SIGNS + RETAIL_SIGNS if track_retail else BASE_SIGNS

    return rs_and_pi(filtered_table, signs=signs, suffix=suffix)
