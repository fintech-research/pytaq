from typing import TYPE_CHECKING

from .conventions import DEFAULT_PERCENT_METHOD, PercentMethod, check_percent_method
from .locks_crosses import filter_locks_crosses

if TYPE_CHECKING:
    from ibis.expr.types import Table


def compute_effective_spreads(
    trade_and_nbbo_table: "Table",
    percent_method: PercentMethod = DEFAULT_PERCENT_METHOD,
    exclude_locked_crossed: bool = True,
    best_bid_col: str = "best_bid",
    best_ask_col: str = "best_ask",
) -> "Table":
    """Compute effective spreads for trades.

    The effective spread is twice the distance between the trade price and the
    prevailing midpoint: what the trader paid relative to the quoted midpoint.

    Trades struck while the market was locked or crossed are excluded by
    default, as Holden and Jacobsen require, since the midpoint is not
    meaningful then. The indicators are derived from the prevailing bid and ask
    rather than expected as input columns.

    Args:
        trade_and_nbbo_table (Table): Trades matched to the prevailing NBBO,
            carrying `price`, `midpoint` and the best bid and ask
        percent_method (PercentMethod): `"ratio"` for the Holden and Jacobsen
            definition, the dollar spread over the midpoint, or `"log"` for
            twice the log difference
        exclude_locked_crossed (bool): Drop trades whose prevailing quote was
            locked or crossed
        best_bid_col (str): Name of the prevailing bid column
        best_ask_col (str): Name of the prevailing ask column

    Returns:
        Table: Input table with `DollarEffectiveSpread` and
        `PercentEffectiveSpread` added
    """
    check_percent_method(percent_method)

    t = trade_and_nbbo_table
    if exclude_locked_crossed:
        t = filter_locks_crosses(t, asks=t[best_ask_col], bids=t[best_bid_col])

    dollar = (t.price - t.midpoint).abs() * 2
    if percent_method == "ratio":
        percent = dollar / t.midpoint
    else:
        percent = (t.price.log() - t.midpoint.log()).abs() * 2

    return t.mutate(
        DollarEffectiveSpread=dollar,
        PercentEffectiveSpread=percent,
    )
