import datetime
from decimal import Decimal
from typing import Sequence

import ibis

from ..hj_defaults import (
    HJ_DELETE_ABNORMAL_SPREADS,
    HJ_DELETE_CANCELED_QUOTES,
    HJ_DELETE_EMPTY_QUOTES,
    HJ_END_TIME_QUOTES,
    HJ_KEEP_CHANGES_ONLY,
    HJ_KEEP_QU_COND,
    HJ_MAX_QUOTE_CHANGE,
    HJ_MAX_SPREAD,
    HJ_START_TIME_QUOTES,
)
from .common import filter_by_time, merge_datetime, merge_symbol

NBBO_COLS_CLEAN = [
    "timestamp",
    "symbol",
    "best_bid",
    "best_bidsizeshares",
    "best_ask",
    "best_asksizeshares",
]

NBBO_COLS_FLAGS = [
    "qu_cond",
    "qu_cancel",
]


def filter_empty_quotes(t: ibis.Table) -> ibis.Table:
    # TODO: double-check, it seems this steps is actually wrong, you
    # should keep empty quotes. (This step is from H&J).
    # Delete if both ask and bid (or their size) are 0 or None
    empty_sel = (
        ((t.best_ask <= 0) & (t.best_bid <= 0))
        | ((t.best_asksiz <= 0) & (t.best_bidsiz <= 0))
        | (t.best_ask.isnull() & t.best_bid.isnull())
        | (t.best_asksiz.isnull() & t.best_bidsiz.isnull())
    )
    return t.filter(~empty_sel)


def compute_spreads_best_quotes(t: ibis.Table) -> ibis.Table:
    """Compute spreads and best quotes.

    Args:
        t (ibis.Table): Input table

    Returns:
        ibis.Table: Table with spreads and best quotes computed
    """
    # Compute spread and midpoint
    t = t.mutate(spread=t.best_ask - t.best_bid, midpoint=(t.best_ask + t.best_bid) / 2)

    # If size or price = 0 or null, set price and size to null
    ask_sel = (
        (t.best_ask <= 0)
        | t.best_ask.isnull()
        | (t.best_asksiz <= 0)
        | t.best_asksiz.isnull()
    )
    t = t.mutate(
        best_ask=ask_sel.ifelse(ibis.null(), t.best_ask),
        best_asksiz=ask_sel.ifelse(ibis.null(), t.best_asksiz),
    )

    # If size or price = 0 or null, set price and size to null
    bid_sel = (
        (t.best_bid <= 0)
        | t.best_bid.isnull()
        | (t.best_bidsiz <= 0)
        | t.best_bidsiz.isnull()
    )
    t = t.mutate(
        best_bid=bid_sel.ifelse(ibis.null(), t.best_bid),
        best_bidsiz=bid_sel.ifelse(ibis.null(), t.best_bidsiz),
    )

    # Bid/ask size are in round lots
    t = t.mutate(
        best_bidsizeshares=t.best_bidsiz * 100, best_asksizeshares=t.best_asksiz * 100
    )

    # Drop original size columns
    t = t.drop("best_bidsiz", "best_asksiz")

    return t


def filter_abnormal_spreads(
    t: ibis.Table, max_spread: Decimal, max_quote_change: Decimal
) -> ibis.Table:
    """Filter rows if quoted spread or quote change too large.

    Args:
        t (ibis.Table): Input table
        max_spread (Decimal): Maximum quoted spread, in dollars
        max_quote_change (Decimal): Maximum quote change, in dollars

    Returns:
        ibis.Table: Table with abnormal spreads filtered
    """
    # Get previous midpoint
    # Note: H&J only sorts on sym_root, not sym_suffix.
    #       They also sort on date, not timestamps (this is weird)
    window = ibis.window(order_by=[t.symbol, t.timestamp], group_by=[t.symbol])
    t = t.mutate(lmid=t.midpoint.lag().over(window))

    # If quoted spread > $5 and bid (ask) has decreased (increased) by
    # $2.50 then remove that quote.
    # Note: not sure this is good in all cases, i.e. when looking at
    # large events.
    # Note that here behaviour is sligthly different than in SAS
    # Because of the way SAS handles comparison with missing value
    # (i.e. a missing value is always smaller than a number)
    # So if first row has spread greater than max spread, best_bid
    # will be set to missing by SAS but not best_ask. Python
    # won't set any to null.
    bid_sel = (t.spread > max_spread) & (t.best_bid < (t.lmid - max_quote_change))
    t = t.mutate(
        best_bid=bid_sel.ifelse(ibis.null(), t.best_bid),
        best_bidsizeshares=bid_sel.ifelse(ibis.null(), t.best_bidsizeshares),
    )

    ask_sel = (t.spread > max_spread) & (t.best_ask > (t.lmid + max_quote_change))
    t = t.mutate(
        best_ask=ask_sel.ifelse(ibis.null(), t.best_ask),
        best_asksizeshares=ask_sel.ifelse(ibis.null(), t.best_asksizeshares),
    )

    return t


def filter_changes_only(t: ibis.Table) -> ibis.Table:
    """Keep only changes, i.e. consecutive entries with different quotes.

    Args:
        t (ibis.Table): Input table

    Returns:
        ibis.Table: Table with only changed quotes
    """
    # Keep only changes
    # There is a slight difference here with the SAS code because
    # in Python np.nan == np.nan is False. Should not affect end
    # results, but this means consecutive entries with all null symbols
    # won't be removed. We add a second condition to remove those.
    window = ibis.window(order_by=[t.symbol, t.timestamp], group_by=[t.symbol])

    sel = (
        (t.best_ask != t.best_ask.lag().over(window))
        | (t.best_bid != t.best_bid.lag().over(window))
        | (t.best_bidsizeshares != t.best_bidsizeshares.lag().over(window))
        | (t.best_asksizeshares != t.best_asksizeshares.lag().over(window))
    )

    sel_all_null = (
        t.best_ask.isnull()
        & t.best_bid.isnull()
        & t.best_bidsizeshares.isnull()
        & t.best_asksizeshares.isnull()
        & t.best_ask.lag().over(window).isnull()
        & t.best_bid.lag().over(window).isnull()
        & t.best_bidsizeshares.lag().over(window).isnull()
        & t.best_asksizeshares.lag().over(window).isnull()
    )

    return t.filter(sel | sel_all_null)


def clean_nbbo(
    t: ibis.Table,
    start_time: datetime.time | None = HJ_START_TIME_QUOTES,
    end_time: datetime.time | None = HJ_END_TIME_QUOTES,
    keep_qu_cond: Sequence[str] = HJ_KEEP_QU_COND,
    delete_canceled_quotes: bool = HJ_DELETE_CANCELED_QUOTES,
    delete_empty_quotes: bool = HJ_DELETE_EMPTY_QUOTES,
    delete_abnormal_spreads: bool = HJ_DELETE_ABNORMAL_SPREADS,
    keep_changes_only: bool = HJ_KEEP_CHANGES_ONLY,
    max_spread: Decimal = HJ_MAX_SPREAD,
    max_quote_change: Decimal = HJ_MAX_QUOTE_CHANGE,
    output_flags: bool = False,
) -> ibis.Table:
    t = merge_datetime(merge_symbol(t))
    t = filter_by_time(t, start_time, end_time)

    if keep_qu_cond is not None:
        # Quote condition must be normal
        t = t.filter(t.qu_cond.isin(keep_qu_cond))
    if delete_canceled_quotes:
        # Delete if canceled
        t = t.filter(t.qu_cancel != "B")
    if delete_empty_quotes:
        t = filter_empty_quotes(t)
    t = compute_spreads_best_quotes(t)
    if delete_abnormal_spreads:
        t = filter_abnormal_spreads(
            t, max_spread=max_spread, max_quote_change=max_quote_change
        )
    if keep_changes_only:
        t = filter_changes_only(t)

    # Keep only relevant columns
    # Columns to output
    nbbo_out_cols = (
        NBBO_COLS_CLEAN + NBBO_COLS_FLAGS if output_flags else NBBO_COLS_CLEAN
    )
    return t[nbbo_out_cols]
