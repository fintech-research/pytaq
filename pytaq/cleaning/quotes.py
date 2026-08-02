from collections.abc import Sequence
from decimal import Decimal

import ibis

from ..hj_defaults import (
    HJ_KEEP_QU_COND,
    HJ_MAX_SPREAD,
)
from .common import merge_datetime, merge_symbol

QUOTES_COLS_CLEAN = [
    "timestamp",
    "symbol",
    "best_bid",
    "best_bidsizeshares",
    "best_bidex",
    "best_ask",
    "best_asksizeshares",
    "best_askex",
    "qu_seqnum",
]

QUOTES_COLS_FLAGS = ["qu_cond", "natbbo_ind", "qu_source", "qu_cancel"]


def _neutralize(t: ibis.Table, condition, sides: str = "both") -> ibis.Table:
    """Null out one or both sides of a quote where `condition` holds.

    Holden and Jacobsen never delete a quote row. Each of their filters sets the
    offending side to an extreme value (`BID=0`, `OFR=9999999`) so it cannot win
    the NBBO, while the row itself survives. Their Quote Filter 5 says why:

        They are NOT deleted, because that would incorrectly allow the prior
        quote from the exchange to enter the NBBO.

    The NBBO carries each venue's last quote forward. Deleting a withdrawn quote
    does not take the venue out of the book, it leaves the venue's *previous*
    quote standing as though still live, which is the stale-quote error the
    paper is about.

    Null is used rather than their magic numbers, which are a SAS artefact.
    """
    updates = {}
    if sides in ("both", "ask"):
        updates["ask"] = condition.ifelse(ibis.null(), t.ask)
        updates["asksiz"] = condition.ifelse(ibis.null(), t.asksiz)
    if sides in ("both", "bid"):
        updates["bid"] = condition.ifelse(ibis.null(), t.bid)
        updates["bidsiz"] = condition.ifelse(ibis.null(), t.bidsiz)
    return t.mutate(**updates)


def neutralize_withdrawn_quotes(t: ibis.Table) -> ibis.Table:
    """Null out any side a venue has withdrawn.

    A side is withdrawn when its price or its size is missing or non-positive.
    The two sides are treated independently, so a genuine one-sided quote keeps
    its live side and still contributes to the NBBO. Holden and Jacobsen's
    Quote Filter 3 requires this.

    Args:
        t (ibis.Table): Quotes table

    Returns:
        ibis.Table: Quotes table with withdrawn sides nulled
    """
    ask_withdrawn = t.ask.isnull() | (t.ask <= 0) | t.asksiz.isnull() | (t.asksiz <= 0)
    bid_withdrawn = t.bid.isnull() | (t.bid <= 0) | t.bidsiz.isnull() | (t.bidsiz <= 0)
    t = _neutralize(t, ask_withdrawn, sides="ask")
    return _neutralize(t, bid_withdrawn, sides="bid")


def neutralize_crossed_quotes(t: ibis.Table) -> ibis.Table:
    """Null out both sides of a quote crossed within a single venue.

    A venue quoting a bid above its own ask is reporting something impossible,
    so neither side is trustworthy.
    """
    crossed = (t.bid > t.ask) & (t.bid > 0) & (t.ask > 0)
    return _neutralize(t, crossed)


def neutralize_abnormal_spreads(t: ibis.Table, max_spread: Decimal) -> ibis.Table:
    """Null out both sides of a quote whose spread is implausibly wide."""
    abnormal = ((t.ask - t.bid) > max_spread) & (t.bid > 0) & (t.ask > 0)
    return _neutralize(t, abnormal)


def filter_quote_table(
    t: ibis.Table,
    keep_qu_cond: Sequence[str] | None = HJ_KEEP_QU_COND,
    exclude_canceled_quotes: bool = True,
    exclude_crossed_markets: bool = True,
    exclude_withdrawn_quotes: bool = True,
    exclude_abnormal_spreads: bool = True,
    max_spread: Decimal = HJ_MAX_SPREAD,
    nbbo_only: bool = True,
) -> ibis.Table:
    """Exclude unusable quotes from the NBBO, following Holden and Jacobsen.

    "Exclude" means the offending side is set to null, not that the row is
    dropped. See :func:`_neutralize` for why that distinction matters.

    The one genuine row filter is `nbbo_only`, which selects the quotes that are
    themselves the NBBO and so belong in the union with the NBBO file. That is a
    choice about which rows are relevant, not a data-quality repair.

    Args:
        t (ibis.Table): The input quote table from the TAQ database
        keep_qu_cond (Sequence[str] | None): Quote conditions considered normal;
            quotes with any other condition are excluded
        exclude_canceled_quotes (bool): Exclude quotes flagged as cancelled
        exclude_crossed_markets (bool): Exclude quotes crossed within one venue
        exclude_withdrawn_quotes (bool): Exclude withdrawn sides
        exclude_abnormal_spreads (bool): Exclude quotes with a spread wider than
            `max_spread`
        max_spread (Decimal): Maximum plausible spread, in dollars
        nbbo_only (bool): Keep only rows that are themselves the NBBO

    Returns:
        ibis.Table: The quote table with unusable sides nulled
    """
    if keep_qu_cond is not None and len(keep_qu_cond) > 0:
        # Abnormal quote condition: the quote is not usable, but the venue is
        # still in the book, so neutralise rather than drop.
        t = _neutralize(t, ~t.qu_cond.isin(keep_qu_cond))

    if exclude_canceled_quotes:
        # A null cancel flag means "not cancelled". In SQL `NULL != 'B'` is
        # NULL rather than true, so it has to be spelled out.
        t = _neutralize(t, (t.qu_cancel == "B").fill_null(False))

    if exclude_crossed_markets:
        t = neutralize_crossed_quotes(t)

    if exclude_abnormal_spreads:
        t = neutralize_abnormal_spreads(t, max_spread)

    if exclude_withdrawn_quotes:
        # Must come after the others: they can themselves null out a side, and
        # this step is what records that the venue now has nothing there.
        t = neutralize_withdrawn_quotes(t)

    # Keep only those to be merged with NBBO file. This one is a real filter.
    if nbbo_only:
        t = t.filter(
            ((t.qu_source == "C") & (t.natbbo_ind == "1"))
            | ((t.qu_source == "N") & (t.natbbo_ind == "4"))
        )

    return t


def clean_quote_table(
    t: ibis.Table,
    keep_qu_cond: Sequence[str] | None = HJ_KEEP_QU_COND,
    exclude_canceled_quotes: bool = True,
    exclude_crossed_markets: bool = True,
    exclude_withdrawn_quotes: bool = True,
    exclude_abnormal_spreads: bool = True,
    max_spread: Decimal = HJ_MAX_SPREAD,
    nbbo_only: bool = True,
    output_flags: bool = False,
) -> ibis.Table:
    """Clean a raw quote table from TAQ.

    Args:
        t (ibis.Table): Original quote table from TAQ
        keep_qu_cond (Sequence[str] | None): Quote conditions considered normal
        exclude_canceled_quotes (bool): Exclude quotes flagged as cancelled
        exclude_crossed_markets (bool): Exclude quotes crossed within one venue
        exclude_withdrawn_quotes (bool): Exclude withdrawn sides
        exclude_abnormal_spreads (bool): Exclude implausibly wide spreads
        max_spread (Decimal): Maximum plausible spread, in dollars
        nbbo_only (bool): Keep only rows that are themselves the NBBO
        output_flags (bool): Keep the quote condition and source flags

    Returns:
        ibis.Table: Cleaned quote table
    """
    t = t.rename({col.lower(): col for col in t.columns})
    t = merge_symbol(merge_datetime(t))

    t = filter_quote_table(
        t=t,
        keep_qu_cond=keep_qu_cond,
        exclude_canceled_quotes=exclude_canceled_quotes,
        exclude_crossed_markets=exclude_crossed_markets,
        exclude_withdrawn_quotes=exclude_withdrawn_quotes,
        exclude_abnormal_spreads=exclude_abnormal_spreads,
        max_spread=max_spread,
        nbbo_only=nbbo_only,
    )

    # Rename columns (Ibis rename uses {new_name: old_name} mapping)
    t = t.rename(best_ask="ask", best_bid="bid", best_bidex="ex")
    t = t.mutate(best_askex=t.best_bidex)

    # Bid/ask size are in round lots
    t = t.mutate(
        best_bidsizeshares=t.bidsiz * 100,
        best_asksizeshares=t.asksiz * 100,
    )

    # Keep only relevant columns
    quotes_out_cols = (
        QUOTES_COLS_CLEAN + QUOTES_COLS_FLAGS if output_flags else QUOTES_COLS_CLEAN
    )
    return t[quotes_out_cols]
