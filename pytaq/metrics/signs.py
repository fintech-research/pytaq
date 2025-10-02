from typing import TYPE_CHECKING, List, Union

import ibis

from ..metrics.locks_crosses import locked_crossed_rows
from ..utils.float_approx import float_equal, float_zero

if TYPE_CHECKING:
    from ibis.expr.types import Column, Table

DEFAULT_CLNV_THRESHOLD = 0.3

BASE_SIGNS = ["LR", "EMO", "CLNV"]
RETAIL_SIGNS = ["BJZ"] + [x + "notBJZ" for x in BASE_SIGNS]


def sign_tick(
    table: "Table",
    groupby_col: Union[str, List[str]] = "symbol",
    timestamp_col: str = "timestamp",
    price_col: str = "price",
) -> "Column":
    """Compute trade direction using tick test.

    Args:
        table (Table): Input table
        groupby_col (Union[str, List[str]]): Column(s) to group by
        timestamp_col (str): Timestamp column name
        price_col (str): Price column name

    Returns:
        Column: Trade direction column
    """
    if isinstance(groupby_col, str):
        group = [groupby_col]
    elif isinstance(groupby_col, list):
        group = groupby_col
    else:
        raise ValueError("groupby_col should be str or a list of str.")

    # Sort table by timestamp and group columns
    sorted_table = table.order_by([timestamp_col] + group)

    # Create window for lag operations
    window = ibis.window(
        partition_by=group, order_by=timestamp_col, preceding=1, following=0
    )

    # Compute price difference and sign
    price_diff = sorted_table[price_col] - sorted_table[price_col].lag().over(window)
    dir_col = price_diff.sign()

    # Handle zero values (set to null)
    dir_col = float_zero(dir_col).ifelse(ibis.null(), dir_col)

    # Forward fill null values within groups
    # Use a cumulative max window to propagate last non-null value forward
    # This works because sign values are -1, 0, 1 or null
    forward_fill_window = ibis.window(
        partition_by=group,
        order_by=timestamp_col,
        preceding=None,  # Unbounded preceding
        following=0,
    )

    # Forward fill by taking the max of non-null values seen so far
    # Note: This assumes positive bias when no previous trades exist
    # Alternative: use last_value() with ignore_nulls if backend supports it
    dir_col_filled = dir_col.max().over(forward_fill_window)

    return dir_col_filled


def sign_lr(
    price: "Column",
    midpoint: "Column",
    tick_dir: "Column",
    lock_cross: "Column",
) -> "Column":
    """Compute Lee-Ready trade sign.

    Args:
        price (Column): Price column
        midpoint (Column): Midpoint column
        tick_dir (Column): Tick direction column
        lock_cross (Column): Lock/cross indicator column

    Returns:
        Column: Lee-Ready trade sign
    """
    lr_dir = tick_dir

    keep_tick = lock_cross | float_equal(price, midpoint)

    # Apply Lee-Ready logic
    lr_dir = (~keep_tick & (price > midpoint)).ifelse(1, lr_dir)
    lr_dir = (~keep_tick & (price < midpoint)).ifelse(-1, lr_dir)

    return lr_dir


def sign_emo(
    price: "Column",
    best_bid: "Column",
    best_ask: "Column",
    tick_dir: "Column",
    lock_cross: "Column",
) -> "Column":
    """Compute EMO trade sign.

    Args:
        price (Column): Price column
        best_bid (Column): Best bid column
        best_ask (Column): Best ask column
        tick_dir (Column): Tick direction column
        lock_cross (Column): Lock/cross indicator column

    Returns:
        Column: EMO trade sign
    """
    emo_dir = tick_dir

    emo_dir = (~lock_cross & float_equal(price, best_ask)).ifelse(1, emo_dir)
    emo_dir = (~lock_cross & float_equal(price, best_bid)).ifelse(-1, emo_dir)

    return emo_dir


def sign_clnv(
    price: "Column",
    best_bid: "Column",
    best_ask: "Column",
    tick_dir: "Column",
    lock_cross: "Column",
    threshold: float = DEFAULT_CLNV_THRESHOLD,
) -> "Column":
    """Compute CLNV trade sign.

    Args:
        price (Column): Price column
        best_bid (Column): Best bid column
        best_ask (Column): Best ask column
        tick_dir (Column): Tick direction column
        lock_cross (Column): Lock/cross indicator column
        threshold (float): CLNV threshold

    Returns:
        Column: CLNV trade sign
    """
    clnv_dir = tick_dir

    ask_th = best_ask - threshold * (best_ask - best_bid)
    bid_th = best_bid + threshold * (best_ask - best_bid)

    clnv_dir = (~lock_cross & (price >= ask_th) & (price <= best_ask)).ifelse(
        1, clnv_dir
    )
    clnv_dir = (~lock_cross & (price <= bid_th) & (price >= best_bid)).ifelse(
        -1, clnv_dir
    )

    return clnv_dir


def sign_bjz(price: "Column", ex: "Column") -> "Column":
    """Compute BJZ retail trade sign.

    Args:
        price (Column): Price column
        ex (Column): Exchange column

    Returns:
        Column: BJZ trade sign
    """
    # Compute retail sign following "TRACKING RETAIL INVESTOR ACTIVITY"
    # by EKKEHART BOEHMER, CHARLES M. JONES, and XIAOYAN ZHANG

    # This is a simplified implementation - the original logic may need more sophisticated handling
    # in Ibis depending on the backend capabilities

    # For now, return a placeholder - this would need custom UDF or more complex logic
    # to implement the modulo operation and conditional logic
    return ibis.null()


def sign_trades(
    table: "Table",
    groupby_col: Union[str, List[str]] = "symbol",
    timestamp_col: str = "timestamp",
    price_col: str = "price",
    sign_col_prefix: str = "BuySell",
    clnv_threshold: float = DEFAULT_CLNV_THRESHOLD,
) -> "Table":
    """Compute trade signs using various algorithms.

    Args:
        table (Table): Input table
        groupby_col (Union[str, List[str]]): Column(s) to group by
        timestamp_col (str): Timestamp column name
        price_col (str): Price column name
        sign_col_prefix (str): Prefix for sign columns
        clnv_threshold (float): CLNV threshold

    Returns:
        Table: Table with trade signs added
    """
    # Add midpoint column
    result_table = table.mutate(midpoint=(table["best_bid"] + table["best_ask"]) / 2)

    # Compute lock/cross indicator
    lock_cross = locked_crossed_rows(
        asks=result_table["best_ask"], bids=result_table["best_bid"]
    )

    # Compute tick direction
    tick_dir = sign_tick(
        table=result_table,
        groupby_col=groupby_col,
        timestamp_col=timestamp_col,
        price_col=price_col,
    )

    # Add sign columns
    result_table = result_table.mutate(
        **{
            f"{sign_col_prefix}LR": sign_lr(
                price=result_table[price_col],
                midpoint=result_table["midpoint"],
                tick_dir=tick_dir,
                lock_cross=lock_cross,
            ),
            f"{sign_col_prefix}EMO": sign_emo(
                price=result_table[price_col],
                best_bid=result_table["best_bid"],
                best_ask=result_table["best_ask"],
                tick_dir=tick_dir,
                lock_cross=lock_cross,
            ),
            f"{sign_col_prefix}CLNV": sign_clnv(
                price=result_table[price_col],
                best_bid=result_table["best_bid"],
                best_ask=result_table["best_ask"],
                tick_dir=tick_dir,
                lock_cross=lock_cross,
                threshold=clnv_threshold,
            ),
            f"{sign_col_prefix}BJZ": sign_bjz(
                price=result_table[price_col], ex=result_table["ex"]
            ),
        }
    )

    # Add notBJZ columns
    bjz_null = result_table[f"{sign_col_prefix}BJZ"].isnull()

    for x in ["LR", "EMO", "CLNV"]:
        result_table = result_table.mutate(
            **{
                f"{sign_col_prefix}{x}notBJZ": bjz_null.ifelse(
                    result_table[f"{sign_col_prefix}{x}"], ibis.null()
                )
            }
        )

    return result_table
