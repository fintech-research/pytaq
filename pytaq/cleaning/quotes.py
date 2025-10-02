from decimal import Decimal
from typing import Sequence

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


def filter_withdrawned_quotes(t: ibis.Table) -> ibis.Table:
    """Filters withdrawned quotes from the quotes table

    NOTE: See H&J (2014) page 11 for details.

    Args:
        t (ibis.Table): Quotes table

    Returns:
        ibis.Table: Quotes table without withdrawned quotes
    """
    sel = (
        t.ask.isnull()
        | (t.ask <= 0)
        | t.asksiz.isnull()
        | (t.asksiz <= 0)
        | t.bid.isnull()
        | (t.bid <= 0)
        | t.bidsiz.isnull()
        | (t.bidsiz <= 0)
    )
    return t.filter(~sel)


def filter_quote_table(
    t: ibis.Table,
    keep_qu_cond: Sequence[str] | None = HJ_KEEP_QU_COND,
    delete_canceled_quotes: bool = True,
    delete_crossed_markets: bool = True,
    delete_withdrawned_quotes: bool = True,
    delete_abnormal_spreads: bool = True,
    max_spread: Decimal = HJ_MAX_SPREAD,
    nbbo_only: bool = True,
) -> ibis.Table:
    """Filters the quote table of the TAQ database based on specified criteria.

    Args:
        t (ibis.Table): The input quote table from the TAQ database.
        keep_qu_cond (Sequence[str] | None, default=HJ_KEEP_QU_COND): A list of quote conditions to keep.
        delete_canceled_quotes (bool, default=True): Whether to delete canceled quotes.
        delete_crossed_markets (bool, default=True): Whether to delete quotes with crossed markets.
        delete_withdrawned_quotes (bool, default=True): Whether to delete withdrawned quotes.
        delete_abnormal_spreads (bool, default=True): Whether to delete quotes with abnormal spreads.
        max_spread (Decimal, default=HJ_MAX_SPREAD): The maximum spread allowed for a quote.
        nbbo_only (bool, default=True): Whether to keep only NBBO quotes.

    Returns:
        ibis.Table: The filtered quote table.

    """
    if keep_qu_cond is not None and len(keep_qu_cond) > 0:
        # Quote condition must be normal
        t = t.filter(t.qu_cond.isin(keep_qu_cond))

    if delete_canceled_quotes:
        # Delete if canceled
        t = t.filter(t.qu_cancel != "B")

    if delete_crossed_markets:
        # Delete abnormal crossed markets
        t = t.filter(t.bid <= t.ask)

    if delete_abnormal_spreads:
        # Delete abnormal spreads
        t = t.mutate(spread=t.ask - t.bid)
        t = t.filter(t.spread <= max_spread)

    if delete_withdrawned_quotes:
        # Delete withdrawned quotes
        t = filter_withdrawned_quotes(t)

    # Keep only those to be merged with NBBO file
    if nbbo_only:
        t = t.filter(
            ((t.qu_source == "C") & (t.natbbo_ind == "1"))
            | ((t.qu_source == "N") & (t.natbbo_ind == "4"))
        )

    return t


def clean_quote_table(
    t: ibis.Table,
    keep_qu_cond: Sequence[str] | None = HJ_KEEP_QU_COND,
    delete_canceled_quotes: bool = True,
    delete_crossed_markets: bool = True,
    delete_withdrawned_quotes: bool = True,
    delete_abnormal_spreads: bool = True,
    max_spread: Decimal = HJ_MAX_SPREAD,
    nbbo_only: bool = True,
    output_flags: bool = False,
) -> ibis.Table:
    """Cleans a quote table retreived from TAQ in WRDS

    Args:
        t (ibis.Table): Original quote table from TAQ in WRDS
        keep_qu_cond (Sequence[str] | None, default=HJ_KEEP_QU_COND): A list of quote conditions to keep.
        delete_canceled_quotes (bool, default=True): Whether to delete canceled quotes.
        delete_crossed_markets (bool, default=True): Whether to delete quotes with crossed markets.
        delete_withdrawned_quotes (bool, default=True): Whether to delete withdrawned quotes.
        delete_abnormal_spreads (bool, default=True): Whether to delete quotes with abnormal spreads.
        max_spread (Decimal, default=HJ_MAX_SPREAD): The maximum spread allowed for a quote.
        nbbo_only (bool, default=True): Whether to keep only NBBO quotes.
        output_flags (bool, default=False): Whether to output flags.

    Returns:
        ibis.Table: Cleaned quote table

    """
    t = t.rename({col.lower(): col for col in t.columns})
    t = merge_symbol(merge_datetime(t))

    t = filter_quote_table(
        t=t,
        keep_qu_cond=keep_qu_cond,
        delete_canceled_quotes=delete_canceled_quotes,
        delete_crossed_markets=delete_crossed_markets,
        delete_withdrawned_quotes=delete_withdrawned_quotes,
        delete_abnormal_spreads=delete_abnormal_spreads,
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
    # Columns to output
    quotes_out_cols = (
        QUOTES_COLS_CLEAN + QUOTES_COLS_FLAGS if output_flags else QUOTES_COLS_CLEAN
    )
    return t[quotes_out_cols]
