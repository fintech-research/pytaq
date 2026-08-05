from typing import TYPE_CHECKING

import ibis

from .common import TIMESTAMP_NS_COL

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
        keep_changes_only (bool): Keep one row per symbol and instant, the one
            with the highest sequence number

    Returns:
        Table: The complete NBBO
    """
    t = nbbo.union(quote)

    # The instant two quotes have to share before one supersedes the other.
    # H&J dedup on `time_m`, which in DTAQ resolves to the nanosecond, so the
    # nanosecond key is used wherever it is available. Deduping on the
    # microsecond `timestamp` instead discards quotes that are genuinely distinct
    # events: on AAPL for 2020-01-02, 2,655 NBBO rows share a microsecond with
    # another row and nanoseconds separate every one of them.
    instant = TIMESTAMP_NS_COL if TIMESTAMP_NS_COL in t.columns else "timestamp"
    order = ["symbol", instant, "qu_seqnum"]

    if not keep_changes_only:
        return t.order_by(order)

    # Several venues can still update within the same nanosecond. The last of
    # them, by sequence number, is the one in force.
    #
    # ibis.row_number() is ZERO-based, so the row to keep is 0, not 1. Filtering
    # on 1 kept the second-highest sequence number and dropped every timestamp
    # that had only one quote, which on one day of AAPL returned 18,651 rows
    # where 550,307 were correct.
    ranked = t.mutate(
        _rank=ibis.row_number().over(
            group_by=["symbol", instant], order_by=ibis.desc("qu_seqnum")
        )
    )
    return ranked.filter(ranked._rank == 0).drop("_rank").order_by(order)
