from typing import TYPE_CHECKING

import ibis

from ..metrics.locks_crosses import locked_crossed_rows
from ..utils.float_approx import float_equal, float_zero

if TYPE_CHECKING:
    from ibis.expr.types import BooleanValue, Column, Table, Value

DEFAULT_CLNV_THRESHOLD = 0.3

BASE_SIGNS = ["LR", "EMO", "CLNV"]
RETAIL_SIGNS = ["BJZ"] + [x + "notBJZ" for x in BASE_SIGNS]


def sign_tick(
    table: "Table",
    groupby_col: str | list[str] = "symbol",
    timestamp_col: str = "timestamp",
    price_col: str = "price",
    tick_col: str = "tick_dir",
    order_col: str | None = "timestamp_ns",
) -> "Table":
    """Compute trade direction using the tick test.

    A trade is a buy if the price rose relative to the previous trade and a
    sell if it fell. On a zero return the direction is carried forward from the
    last non-zero move. Trades before any price change have no direction and
    are left null rather than guessed at.

    Returns a table rather than a column: the forward fill has to read a value
    that is itself computed by a window function, and SQL does not allow window
    functions to be nested, so the intermediate result must be materialised.

    Args:
        table (Table): Input table
        groupby_col (str | list[str]): Column(s) to group by
        timestamp_col (str): Timestamp column name
        price_col (str): Price column name
        tick_col (str): Name of the direction column to add
        order_col (str | None): Column giving the true event order. Defaults to
            the nanosecond key, since `timestamp` is only microsecond-resolution
            and consecutive trades routinely share one. Falls back to
            `timestamp_col` when absent

    Returns:
        Table: Input table with the tick direction column added
    """
    if isinstance(groupby_col, str):
        group = [groupby_col]
    elif isinstance(groupby_col, list):
        group = groupby_col
    else:
        raise ValueError("groupby_col should be str or a list of str.")

    # Note: ibis.window takes group_by, not partition_by. The window carries its
    # own ordering, so the table itself must not be re-sorted first: doing that
    # builds the expression against a different relation than the caller passes
    # to mutate(), which ibis rejects.
    order_by = (
        order_col
        if order_col is not None and order_col in table.columns
        else timestamp_col
    )
    window = ibis.window(group_by=group, order_by=order_by)

    # Direction of the price move against the previous trade. A zero return
    # carries no information, so it becomes null and is filled in below.
    price_diff = table[price_col] - table[price_col].lag().over(window)
    raw_dir = price_diff.sign()
    raw_dir = float_zero(raw_dir).ifelse(ibis.null(), raw_dir)

    table = table.mutate(**{tick_col: raw_dir})

    # Forward fill, portably. Counting the non-null directions seen so far
    # labels each run of nulls with the position of the last real direction, so
    # taking the max within that label propagates it forward. Leading nulls get
    # label 0 and stay null, which is what we want: before the first price
    # change there is nothing to carry forward.
    #
    # A cumulative max over the raw directions, which is what this used to do,
    # is not a forward fill. Values are -1 and +1, so the running max latches to
    # +1 for the rest of the group as soon as one uptick appears.
    run_window = ibis.window(
        group_by=group,
        order_by=order_by,
        preceding=None,  # unbounded preceding
        following=0,
    )
    table = table.mutate(_tick_run=table[tick_col].count().over(run_window))

    return table.mutate(
        **{
            tick_col: table[tick_col]
            .max()
            .over(ibis.window(group_by=[*group, "_tick_run"]))
        }
    ).drop("_tick_run")


def sign_lr(
    price: "Column",
    midpoint: "Column",
    tick_dir: "Column",
    lock_cross: "BooleanValue",
) -> "Value":
    """Compute Lee-Ready trade sign.

    Args:
        price (Column): Price column
        midpoint (Column): Midpoint column
        tick_dir (Column): Tick direction column
        lock_cross (BooleanValue): Lock/cross indicator

    Returns:
        Value: Lee-Ready trade sign
    """
    lr_dir = tick_dir

    keep_tick = lock_cross | float_equal(price, midpoint)

    # Apply Lee-Ready logic
    lr_dir = (~keep_tick & (price > midpoint)).ifelse(ibis.literal(1), lr_dir)
    lr_dir = (~keep_tick & (price < midpoint)).ifelse(ibis.literal(-1), lr_dir)

    return lr_dir


def sign_emo(
    price: "Column",
    best_bid: "Column",
    best_ask: "Column",
    tick_dir: "Column",
    lock_cross: "BooleanValue",
) -> "Value":
    """Compute EMO trade sign.

    Args:
        price (Column): Price column
        best_bid (Column): Best bid column
        best_ask (Column): Best ask column
        tick_dir (Column): Tick direction column
        lock_cross (BooleanValue): Lock/cross indicator

    Returns:
        Value: EMO trade sign
    """
    emo_dir = tick_dir

    emo_dir = (~lock_cross & float_equal(price, best_ask)).ifelse(
        ibis.literal(1), emo_dir
    )
    emo_dir = (~lock_cross & float_equal(price, best_bid)).ifelse(
        ibis.literal(-1), emo_dir
    )

    return emo_dir


def sign_clnv(
    price: "Column",
    best_bid: "Column",
    best_ask: "Column",
    tick_dir: "Column",
    lock_cross: "BooleanValue",
    threshold: float = DEFAULT_CLNV_THRESHOLD,
) -> "Value":
    """Compute CLNV trade sign.

    Args:
        price (Column): Price column
        best_bid (Column): Best bid column
        best_ask (Column): Best ask column
        tick_dir (Column): Tick direction column
        lock_cross (BooleanValue): Lock/cross indicator
        threshold (float): CLNV threshold

    Returns:
        Value: CLNV trade sign
    """
    clnv_dir = tick_dir

    ask_th = best_ask - threshold * (best_ask - best_bid)
    bid_th = best_bid + threshold * (best_ask - best_bid)

    clnv_dir = (~lock_cross & (price >= ask_th) & (price <= best_ask)).ifelse(
        ibis.literal(1), clnv_dir
    )
    clnv_dir = (~lock_cross & (price <= bid_th) & (price >= best_bid)).ifelse(
        ibis.literal(-1), clnv_dir
    )

    return clnv_dir


def sign_bjz(price: "Column", ex: "Column") -> "Value":
    """Compute BJZ retail trade sign.

    The BJZ (Boehmer, Jones, Zhang) algorithm classifies retail trades based on
    sub-penny price patterns. It only applies to off-exchange trades (ex='D').

    The algorithm:
    1. Computes z = 100 * (price mod 0.01) - extracts sub-cent decimals (3rd & 4th decimal places)
    2. Classifies as:
       - Sell (-1): if 0.0001 <= z < 0.4 (prices ending in .XX01 to .XX39)
       - Buy (+1): if 0.6 <= z < 0.9999 (prices ending in .XX60 to .XX99)
       - Unclassified (null): otherwise (prices ending in .XX00, .XX40-.XX59)

    Examples:
        100.1234 -> z = 34.0 -> Sell (-1)
        100.7568 -> z = 68.0 -> Buy (+1)
        100.5000 -> z = 0.0 -> Unclassified (null)

    Args:
        price (Column): Price column
        ex (Column): Exchange column

    Returns:
        Value: BJZ trade sign (-1 sell, +1 buy, null unclassified or on-exchange)
    """
    # Only apply to off-exchange trades (exchange = 'D')
    is_off_exchange = ex == "D"

    # Compute z = 100 * (price mod 0.01)
    # This extracts the sub-cent decimals (3rd and 4th decimal places)
    # For example: 100.1234 -> (100.1234 - 100.12) * 100 = 0.0034 * 100 = 0.34 * 100 = 34.0
    frac_part = price - price.floor()  # Get fractional part (e.g., 0.1234)
    cents_shifted = frac_part * 100  # Shift to cents (e.g., 12.34)
    sub_cent = cents_shifted - cents_shifted.floor()  # Get sub-cent part (e.g., 0.34)
    z = sub_cent * 100  # Scale to 0-100 range (e.g., 34.0)

    # Define thresholds (z is scaled to 0-100 range)
    epsilon = 0.01  # Small epsilon for floating point comparison

    # Classify based on z value
    # Sell: 0.01 <= z < 40
    is_sell = (z >= epsilon) & (z < 40)
    # Buy: 60 <= z < 99.99
    is_buy = (z >= 60) & (z < (100 - epsilon))

    # Compute sign: -1 for sell, +1 for buy, null otherwise
    bjz_sign = ibis.null().cast("int8")
    bjz_sign = is_sell.ifelse(ibis.literal(-1), bjz_sign)
    bjz_sign = is_buy.ifelse(ibis.literal(1), bjz_sign)

    # Only return sign for off-exchange trades, null for others
    result = is_off_exchange.ifelse(bjz_sign, ibis.null().cast("int8"))

    return result


def sign_trades(
    table: "Table",
    groupby_col: str | list[str] = "symbol",
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

    # Compute tick direction. This materialises an intermediate column, so it
    # has to happen before any expression that reads from result_table.
    tick_col = f"{sign_col_prefix}Tick"
    result_table = sign_tick(
        table=result_table,
        groupby_col=groupby_col,
        timestamp_col=timestamp_col,
        price_col=price_col,
        tick_col=tick_col,
    )
    tick_dir = result_table[tick_col]

    # Compute lock/cross indicator
    lock_cross = locked_crossed_rows(
        asks=result_table["best_ask"], bids=result_table["best_bid"]
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
