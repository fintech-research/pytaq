from typing import TYPE_CHECKING

from .conventions import DEFAULT_PERCENT_METHOD, PercentMethod, check_percent_method

if TYPE_CHECKING:
    from ibis.expr.types import Table


def compute_effective_spreads(
    trade_and_nbbo_table: "Table",
    percent_method: PercentMethod = DEFAULT_PERCENT_METHOD,
) -> "Table":
    """Compute effective spreads for trades.

    The effective spread is twice the distance between the trade price and the
    prevailing midpoint: what the trader paid relative to the quoted midpoint.

    Trades struck while the market was locked or crossed are excluded, as
    Holden and Jacobsen require, since the midpoint is not meaningful then.

    Args:
        trade_and_nbbo_table (Table): Trades matched to the prevailing NBBO,
            carrying `price`, `midpoint` and the `lock` and `cross` indicators
        percent_method (PercentMethod): `"ratio"` for the Holden and Jacobsen
            definition, the dollar spread over the midpoint, or `"log"` for
            twice the log difference

    Returns:
        Table: Input table with `DollarEffectiveSpread` and
        `PercentEffectiveSpread` added
    """
    check_percent_method(percent_method)

    t = trade_and_nbbo_table.filter(
        ~((trade_and_nbbo_table.cross == 1) | (trade_and_nbbo_table.lock == 1))
    )

    dollar = (t.price - t.midpoint).abs() * 2
    if percent_method == "ratio":
        percent = dollar / t.midpoint
    else:
        percent = (t.price.log() - t.midpoint.log()).abs() * 2

    return t.mutate(
        DollarEffectiveSpread=dollar,
        PercentEffectiveSpread=percent,
    )
