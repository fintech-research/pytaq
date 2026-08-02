from typing import TYPE_CHECKING

from ..utils.float_approx import float_equal

if TYPE_CHECKING:
    from ibis.expr.types import BooleanValue, Column, Table


def locked_rows(asks: "Column", bids: "Column") -> "BooleanValue":
    """Identifies rows with a market lock (equal bid and ask)

    Args:
        asks (Column): Ask quotes
        bids (Column): Bid quotes

    Returns:
        BooleanValue: Boolean expression indicating the lock status
    """
    return float_equal(s1=asks, s2=bids)


def crossed_rows(asks: "Column", bids: "Column") -> "BooleanValue":
    """Identifies rows with a market cross (ask lower than bid)

    Args:
        asks (Column): Ask quotes
        bids (Column): Bid quotes

    Returns:
        BooleanValue: Boolean expression indicating the cross status
    """
    return asks < bids


def locked_crossed_rows(asks: "Column", bids: "Column") -> "BooleanValue":
    """Identifies rows with a market lock or cross (ask lower or equal to bid)

    Args:
        asks (Column): Ask quotes
        bids (Column): Bid quotes

    Returns:
        BooleanValue: Boolean expression indicating the lock/cross status
    """
    return locked_rows(asks, bids) | crossed_rows(asks, bids)


def filter_locks_crosses(table: "Table", asks: "Column", bids: "Column") -> "Table":
    """Filters locked and crossed rows from a table

    Args:
        table (Table): Table to filter
        asks (Column): Ask quotes
        bids (Column): Bid quotes

    Returns:
        Table: Filtered table
    """
    return table.filter(~locked_crossed_rows(asks, bids))
