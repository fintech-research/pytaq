"""How a percent liquidity measure is defined.

Two conventions are in circulation, and Holden and Jacobsen have published one
of each:

``"log"``
    Twice the log difference. This is what their **Daily TAQ** code of 16 March
    2018 computes for every percent measure, so it is the default here, since
    DTAQ is what PyTAQ targets::

        wQuotedSpread_Percent = (log(Best_Ask) - log(Best_Bid)) * inforce
        wEffectiveSpread_Percent = abs(log(price) - log(midpoint)) * 2

    It is also additive across periods and symmetric in direction.

``"ratio"``
    Divide the dollar measure by the reference midpoint. This is what their
    earlier **monthly TAQ** code of September 2013 did, and what a large part of
    the empirical literature reports.

The two agree to first order and diverge as spreads widen, so the choice matters
least where spreads are tightest. Both stay available because published results
exist on either footing: pass ``percent_method="ratio"`` to reproduce work built
on the older convention.
"""

from typing import Literal, get_args

PercentMethod = Literal["ratio", "log"]

PERCENT_METHODS: tuple[str, ...] = get_args(PercentMethod)

DEFAULT_PERCENT_METHOD: PercentMethod = "log"


def check_percent_method(method: str) -> None:
    """Raise if `method` is not a recognised percent convention."""
    if method not in PERCENT_METHODS:
        raise ValueError(
            f"percent_method must be one of {PERCENT_METHODS}, got {method!r}."
        )
