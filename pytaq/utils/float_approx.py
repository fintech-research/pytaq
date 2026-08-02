from typing import TYPE_CHECKING

import ibis

if TYPE_CHECKING:
    from ibis.expr.types import BooleanValue, Column, NumericValue

"""
    Notes:
    In rare cases, trade prices and midpoints or two quotes can be the same, but
    comparison and arithmetic operations don't work as expected because of floating
    point approximation error.

    Ibis' `isclose()` function can be used to deal with these situations.
"""

DEFAULT_ATOL = 0.000001


def float_equal(
    s1: "NumericValue", s2: "NumericValue", atol: float = DEFAULT_ATOL
) -> "BooleanValue":
    """Compares two numeric expressions for approximate equality.

    Args:
        s1 (NumericValue): First expression to compare
        s2 (NumericValue): Second expression to compare
        atol (float, optional): Absolute tolerance for comparison. Defaults to 0.000001.

    Returns:
        BooleanValue: Boolean expression indicating approximate equality
    """
    # Implement isclose manually: |s1 - s2| <= atol
    # Handle NaN: both NaN should be considered equal
    diff = (s1 - s2).abs()
    within_tol = diff <= atol

    # Check if both are null/NaN and treat as equal
    both_null = s1.isnull() & s2.isnull()

    return both_null | within_tol


def float_zero(s: "NumericValue", atol: float = DEFAULT_ATOL) -> "BooleanValue":
    """Compares a numeric expression for approximate equality with zero.

    Args:
        s (NumericValue): Expression to compare with zero.
        atol (float, optional): Absolute tolerance for comparison. Defaults to 0.000001.

    Returns:
        BooleanValue: Boolean expression indicating approximate equality with zero
    """
    return float_equal(s, ibis.literal(0.0), atol=atol)


def correct_float_approx(
    series: "Column",
    s1: "NumericValue",
    s2: "NumericValue",
    atol: float = DEFAULT_ATOL,
) -> "Column":
    """Changes values of a column to null when the corresponding entries in the two other
    columns are numerically very close.

    Args:
        series (Column): Column to correct
        s1 (NumericValue): First expression to compare
        s2 (NumericValue): Second expression to compare
        atol (float, optional): Absolute tolerance for comparison. Defaults to 0.000001.

    Returns:
        Column: Corrected column
    """
    equal = float_equal(s1=s1, s2=s2, atol=atol)

    # Set values to null when s1 and s2 are approximately equal
    return equal.ifelse(ibis.null(), series)
