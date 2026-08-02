from collections.abc import Iterable
from datetime import timedelta
from typing import TYPE_CHECKING

from ..utils.float_approx import correct_float_approx
from .conventions import (
    DEFAULT_PERCENT_METHOD,
    PercentMethod,
    check_percent_method,
)
from .locks_crosses import filter_locks_crosses
from .signs import BASE_SIGNS, RETAIL_SIGNS

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
    percent_method: PercentMethod = DEFAULT_PERCENT_METHOD,
) -> "Column":
    """Compute percent realized spread.

    Args:
        sign (Column): Trade sign column
        price (Column): Price column
        midpoint_next (Column): Next midpoint column

    Returns:
        Column: Percent realized spread
    """
    check_percent_method(percent_method)
    if percent_method == "ratio":
        # Holden and Jacobsen divide the dollar measure by the *future*
        # midpoint, the same one the realized spread is measured against.
        s = sign * (price - midpoint_next) * 2 / midpoint_next
    else:
        s = sign * (price.log() - midpoint_next.log()) * 2
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
    percent_method: PercentMethod = DEFAULT_PERCENT_METHOD,
) -> "Column":
    """Compute percent price impact.

    Args:
        sign (Column): Trade sign column
        midpoint (Column): Current midpoint column
        midpoint_next (Column): Next midpoint column

    Returns:
        Column: Percent price impact
    """
    check_percent_method(percent_method)
    if percent_method == "ratio":
        # Equivalent to (dollar effective spread - dollar realized spread)
        # over the future midpoint, which is how H&J write it.
        s = sign * (midpoint_next - midpoint) * 2 / midpoint_next
    else:
        s = sign * (midpoint_next.log() - midpoint.log()) * 2
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
    percent_method: PercentMethod = DEFAULT_PERCENT_METHOD,
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
                    percent_method=percent_method,
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
                    percent_method=percent_method,
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
    suffix: str = "_next",
) -> "Table":
    """Attach the NBBO in force `delay` after each trade.

    Realized spread and price impact compare the trade price against the
    midpoint some horizon later, so each trade needs exactly one future quote:
    the one prevailing at trade time plus `delay`.

    This is an as-of join, not an inequality join. Shifting the quote
    timestamps back by `delay` and joining on "at or before" would match every
    quote from the horizon onward and fan one trade out into thousands of rows.

    Args:
        table (Table): Trades, carrying symbol and timestamp
        nbbo_table (Table): Cleaned NBBO
        delay (timedelta): How far after the trade to read the midpoint
        symbol_col (str): Symbol column name
        timestamp_col (str): Timestamp column name
        best_bid_col (str): Best bid column name
        best_ask_col (str): Best ask column name
        suffix (str): Suffix for the columns brought in from the NBBO

    Returns:
        Table: Input table with the future NBBO and its midpoint attached
    """
    future = nbbo_table.select(
        [timestamp_col, symbol_col, best_bid_col, best_ask_col]
    ).mutate(midpoint=(nbbo_table[best_bid_col] + nbbo_table[best_ask_col]) / 2)

    # Read the quote in force at trade time + delay.
    horizon = table[timestamp_col] + delay

    return table.asof_join(
        future,
        on=horizon >= future[timestamp_col],
        predicates=[table[symbol_col] == future[symbol_col]],
        rname="{name}" + suffix,
    )


def compute_rs_and_pi(
    trade_and_nbbo_table: "Table",
    off_nbbo_table: "Table",
    delay: timedelta = timedelta(minutes=5),
    suffix: str = "5min",
    track_retail: bool = False,
    percent_method: PercentMethod = DEFAULT_PERCENT_METHOD,
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

    return rs_and_pi(
        filtered_table, signs=signs, suffix=suffix, percent_method=percent_method
    )
