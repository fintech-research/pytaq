from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ibis.expr.types import Table


def compute_averages(
    table: "Table",
    cols: Iterable[str],
    group: str = "symbol",
    weights: Iterable[tuple[str | None, str]] = [
        (None, ""),
    ],
) -> "Table":
    """Computes simple and weighted averages of table columns.

    Averages are computed for every column of `table` in `cols`, grouped by `group`.
    Weighting to apply are provided as tuples in `weights`, where the first element
    if the weighting column (or None for a simple average) and the second element is
    the suffix to append to the resulting column.

    Args:
        table (Table): Table to operate on
        cols (Iterable[str]): Columns to compute the average
        group (str): Columns to group by
        weights (Iterable[Tuple(Union[str, None], str)]): Weights to apply. Defaults to [ (None, ""), ].

    Returns:
        Table: Table of the averages
    """
    # Start with grouping
    grouped = table.group_by(group)

    # Build aggregation expressions
    aggregations = {}

    for col in cols:
        for weight_col, suffix in weights:
            col_name = f"{col}{suffix}"

            if weight_col is None:
                # Simple average, which already ignores nulls.
                aggregations[col_name] = table[col].mean()
            else:
                # Weighted average. Both sums must run over the same rows: the
                # numerator drops rows where the measure is null, so summing
                # the full weight column in the denominator biases the result
                # toward zero in proportion to the weight carried by the
                # missing observations. On three observations with the middle
                # one missing and holding 98% of the weight, that turned a
                # correct 1.5 into 0.03.
                observed = table[col].notnull() & table[weight_col].notnull()
                weighted_sum = (table[col] * table[weight_col]).sum(where=observed)
                weight_sum = table[weight_col].sum(where=observed)
                aggregations[col_name] = weighted_sum / weight_sum

    return grouped.agg(**aggregations)


def compute_averages_ave_sw_dw(
    table: "Table",
    measures: Iterable[str],
    simple: bool = True,
    dollar_weighted: bool = True,
    share_weighted: bool = True,
) -> "Table":
    """Computes simple and weighted averages by symbol for multiple measures.

    Args:
        table (Table): Table to operate on
        measures (Iterable[str]): Measures to compute averages for
        simple (bool, optional): Whether to compute simple averages. Defaults to True.
        dollar_weighted (bool, optional): Whether to compute dollar-weighted averages. Defaults to True.
        share_weighted (bool, optional): Whether to compute share-weighted averages. Defaults to True.

    Returns:
        Table: Table of the averages
    """

    weights: list[tuple[str | None, str]] = []
    if simple:
        weights.append((None, "_average"))
    if dollar_weighted:
        weights.append(("dollar", "_dollar_weighted"))
    if share_weighted:
        weights.append(("size", "_share_weighted"))

    return compute_averages(table=table, cols=measures, group="symbol", weights=weights)
