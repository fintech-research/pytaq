from typing import TYPE_CHECKING

import ibis

if TYPE_CHECKING:
    from ibis.expr.types import Table


def merge_quotes_nbbo(
    nbbo: "Table", quote: "Table", keep_changes_only: bool = True
) -> "Table":
    """Merges the NBBO and Quote tables to create the official complete NBBO.

    With default options used to clean the input tables, this function should
    yield the same results as the official complete NBBO table in WRDS.

    Args:
        nbbo ("Table"): NBBO quotes
        quote ("Table"): Quotes
        keep_changes_only (bool, optional): Only keep the last observation for each timestamp. Defaults to True.

    Returns:
        "Table": Official complete NBBO
    """
    # Union the tables
    t = nbbo.union(quote)

    # Sort by symbol, timestamp, sequence number
    t = t.order_by(["symbol", "timestamp", "qu_seqnum"])

    # Remove duplicate quotes at same microsecond (keep last one based on sequence number)
    if keep_changes_only:
        t = (
            t.group_by(["symbol", "timestamp"])
            .mutate(
                row_num=ibis.row_number().over(
                    order_by=[ibis.desc("qu_seqnum")], group_by=["symbol", "timestamp"]
                )
            )
            .filter(ibis._.row_num == 1)
            .drop("row_num")
        )

    return t
