from typing import TYPE_CHECKING

import ibis

if TYPE_CHECKING:
    from ibis.expr.types import Table


def merge_quotes_nbbo(
    nbbo: "Table", quote: "Table", keep_changes_only: bool = True
) -> "Table":
    """Build the complete NBBO from the NBBO and quote files.

    The NBBO file is not a complete history. When a quote is itself both the
    new best bid and the new best offer, the SIP emits no NBBO record for it,
    so that quote exists only in the quotes file. WRDS's own guidance says the
    two must be combined:

        you would have to combine quotes data with NBBO data to generate a true
        history of NBBO for a given date, if for no other reason than to find
        the quotes with NATBBO_IND=1 ... that in themselves constitute both new
        best bids and new best asks, but did not generate an NBBO "appendage".

    Both inputs must therefore share a schema. `clean_nbbo` and
    `clean_quote_table` are kept aligned for this reason.

    Args:
        nbbo (Table): Cleaned NBBO, from `clean_nbbo`
        quote (Table): Cleaned NBBO-eligible quotes, from `clean_quote_table`
        keep_changes_only (bool): Keep one row per symbol and timestamp, the
            one with the highest sequence number

    Returns:
        Table: The complete NBBO
    """
    t = nbbo.union(quote)

    if not keep_changes_only:
        return t.order_by(["symbol", "timestamp", "qu_seqnum"])

    # Several venues can update within the same microsecond. The last of them,
    # by sequence number, is the one in force.
    #
    # ibis.row_number() is ZERO-based, so the row to keep is 0, not 1. Filtering
    # on 1 kept the second-highest sequence number and dropped every timestamp
    # that had only one quote, which on one day of AAPL returned 18,651 rows
    # where 550,307 were correct.
    ranked = t.mutate(
        _rank=ibis.row_number().over(
            group_by=["symbol", "timestamp"], order_by=ibis.desc("qu_seqnum")
        )
    )
    return (
        ranked.filter(ranked._rank == 0)
        .drop("_rank")
        .order_by(["symbol", "timestamp", "qu_seqnum"])
    )
