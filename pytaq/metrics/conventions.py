"""How a percent liquidity measure is defined.

Two conventions are in circulation:

``"ratio"``
    Divide the dollar measure by the reference midpoint, which is what
    Holden and Jacobsen (2014) do and what most of the empirical literature
    reports. This is the default.

``"log"``
    Take twice the log difference. Convenient because it is additive across
    periods and symmetric in direction, and used in parts of the literature.

The two agree to first order and diverge as spreads widen, so the choice
matters least where spreads are tightest. It is exposed rather than fixed
because someone may have existing results built on either.
"""

from typing import Literal, get_args

PercentMethod = Literal["ratio", "log"]

PERCENT_METHODS: tuple[str, ...] = get_args(PercentMethod)

DEFAULT_PERCENT_METHOD: PercentMethod = "ratio"


def check_percent_method(method: str) -> None:
    """Raise if `method` is not a recognised percent convention."""
    if method not in PERCENT_METHODS:
        raise ValueError(
            f"percent_method must be one of {PERCENT_METHODS}, got {method!r}."
        )
