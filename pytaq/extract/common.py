from typing import TYPE_CHECKING

import ibis

if TYPE_CHECKING:
    from ibis.expr.types import Table


def merge_datetime(table: "Table") -> "Table":
    """Merges date and time columns into a timestamp column.

    Args:
        table (Table): Original Ibis table with 'date' and 'time_m' columns

    Returns:
        Table: Table with merged timestamp column
    """
    # Merge date and time using Ibis expressions
    return table.mutate(timestamp=ibis.func.datetime.combine(table.date, table.time_m))


def merge_symbol(table: "Table") -> "Table":
    """Merges symbol and sym_root columns.

    Args:
        table (Table): Original Ibis table with 'sym_root' and 'sym_suffix' columns

    Returns:
        Table: Table with merged symbol column
    """
    # Merge symbol using conditional logic
    return table.mutate(
        symbol=table.sym_suffix.isnull().ifelse(
            table.sym_root, table.sym_root + " " + table.sym_suffix
        )
    )
