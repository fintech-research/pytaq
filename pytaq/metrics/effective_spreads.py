from typing import TYPE_CHECKING

import ibis

if TYPE_CHECKING:
    from ibis.expr.types import Table


def compute_effective_spreads(trade_and_nbbo_table: "Table") -> "Table":
    """Computes effective spreads for trades.

    Args:
        trade_and_nbbo_table (Table): Table containing trade and NBBO data

    Returns:
        Table: Table with effective spread calculations
    """
    # Filter out crossed and locked trades
    filtered_table = trade_and_nbbo_table.filter(
        ~((trade_and_nbbo_table.cross == 1) | (trade_and_nbbo_table.lock == 1))
    )

    # Compute effective spreads
    result_table = filtered_table.mutate(
        DollarEffectiveSpread=ibis.func.abs(
            trade_and_nbbo_table.price - trade_and_nbbo_table.midpoint
        )
        * 2,
        PercentEffectiveSpread=(
            ibis.func.abs(
                ibis.func.ln(trade_and_nbbo_table.price)
                - ibis.func.ln(trade_and_nbbo_table.midpoint)
            )
            * 2
        ),
    )

    return result_table
