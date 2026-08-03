"""One call from raw TAQ tables to daily liquidity measures.

The stages have an order, and the order carries constraints that are not
obvious from the individual function signatures: quotes must be cleaned before
the NBBO can be built, the NBBO before trades can be matched to it, matching
before signing, signing before effective spreads, and realized spreads need the
NBBO again at a later horizon. The quote window also opens half an hour before
the trade window, so that the first trades of the day have a quote to match.

Getting any of that wrong produces plausible numbers rather than an error,
which is the worst failure mode for research code. :func:`process_day` encodes
the ordering once.

Everything stays lazy. The returned object holds Ibis expressions, so you can
inspect an intermediate, add your own step, or execute only what you need.

A note on the postgres path: composing every stage into one expression and
executing it against the WRDS server is slow, because the as-of joins and
window functions run remotely over a full trading day. Against local files it
takes under a second. If you are working off WRDS directly, consider
materialising the cleaned tables first rather than executing the whole chain in
a single query.
"""

import datetime
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .cleaning.merge_trades_official_nbbo import (
    HJ_TRADE_QUOTE_LAG,
    merge_trades_official_nbbo,
)
from .cleaning.official_nbbo import clean_official_complete_nbbo
from .cleaning.trades import clean_trades
from .hj_defaults import (
    HJ_END_TIME_QUOTES,
    HJ_END_TIME_TRADES,
    HJ_START_TIME_QUOTES,
    HJ_START_TIME_TRADES,
)
from .metrics.averages import compute_averages
from .metrics.conventions import (
    DEFAULT_PERCENT_METHOD,
    PercentMethod,
    check_percent_method,
)
from .metrics.effective_spreads import compute_effective_spreads
from .metrics.locks_crosses import filter_locks_crosses
from .metrics.quoted_spreads import (
    compute_quote_inforce,
    compute_spreads,
    compute_weighted_averages,
)
from .metrics.rs_and_pi import compute_rs_and_pi
from .metrics.signs import BASE_SIGNS, RETAIL_SIGNS, sign_trades
from .metrics.timestamps import filter_timestamp

if TYPE_CHECKING:
    from ibis.expr.types import Table

#: Measures averaged per symbol-day from the trade side.
TRADE_MEASURES = ("effective_spread_dollar", "effective_spread_percent")

#: Measures averaged per symbol-day from the quote side, time-weighted.
QUOTE_MEASURES = ("quoted_spread_dollar", "quoted_spread_percent")

#: Simple, share-weighted and dollar-weighted, as Holden and Jacobsen report.
TRADE_WEIGHTS: tuple[tuple[str | None, str], ...] = (
    (None, ""),
    ("size", "_share_weighted"),
    ("dollar", "_dollar_weighted"),
)


@dataclass(frozen=True)
class DayResult:
    """The stages of one symbol-day, all lazy.

    `daily` is what most callers want. The intermediates are exposed because
    checking them is often the only way to understand a surprising number, and
    because someone will always need a step PyTAQ does not provide.
    """

    trades: "Table"
    nbbo: "Table"
    matched: "Table"
    signed: "Table"
    effective_spreads: "Table"
    quoted_spreads: "Table"
    realized_spreads: "Table | None"
    daily: "Table"

    def execute(self):
        """Execute the daily result. Shorthand for `result.daily.execute()`."""
        return self.daily.execute()


def process_day(
    raw_trades: "Table",
    raw_official_nbbo: "Table",
    date: datetime.date,
    *,
    lag: datetime.timedelta = HJ_TRADE_QUOTE_LAG,
    horizon: datetime.timedelta | None = datetime.timedelta(minutes=5),
    horizon_suffix: str = "5min",
    percent_method: PercentMethod = DEFAULT_PERCENT_METHOD,
    track_retail: bool = False,
    trade_start_time: datetime.time | None = HJ_START_TIME_TRADES,
    trade_end_time: datetime.time | None = HJ_END_TIME_TRADES,
    quote_start_time: datetime.time | None = HJ_START_TIME_QUOTES,
    quote_end_time: datetime.time | None = HJ_END_TIME_QUOTES,
    quoted_spread_start_time: datetime.time | None = HJ_START_TIME_TRADES,
    exclude_locked_crossed: bool = True,
    groupby_col: str = "symbol",
) -> DayResult:
    """Run the standard Holden and Jacobsen pipeline for one date.

    Takes the raw trade and official NBBO tables for a single date, from either
    :mod:`pytaq.wrds` or :mod:`pytaq.local`, and returns every stage plus the
    per-symbol daily aggregates.

    Nothing executes until you ask for it.

    Args:
        raw_trades (Table): Raw trades for the date
        raw_official_nbbo (Table): Raw official complete NBBO for the date
        date (datetime.date): The trading date, used to place the closing
            timestamp for the last quote's time in force
        lag (datetime.timedelta): How far before each trade the matched quote
            must have been in force. One millisecond, following H&J
        horizon (datetime.timedelta | None): Horizon for realized spread and
            price impact, or None to skip them
        horizon_suffix (str): Names the horizon in the output columns
        percent_method (PercentMethod): `"ratio"` for the H&J definition or
            `"log"` for log differences
        track_retail (bool): Also compute the BJZ retail-trade variants
        trade_start_time (datetime.time | None): Start of the trade window
        trade_end_time (datetime.time | None): End of the trade window
        quote_start_time (datetime.time | None): Start of the quote window.
            Earlier than the trade window so the first trades have a quote
        quote_end_time (datetime.time | None): End of the quote window
        quoted_spread_start_time (datetime.time | None): Start of the window for
            quoted-spread statistics only, applied after the NBBO is in hand.
            H&J open the quote window early so that early trades have a quote to
            match, then drop the pre-open quotes before time-weighting, since a
            spread quoted before the open is not a spread anyone traded against.
            Defaults to the start of the trade window. Pass None to weight the
            whole quote window
        exclude_locked_crossed (bool): Drop trades and quotes struck while the
            market was locked or crossed
        groupby_col (str): Column to aggregate by

    Returns:
        DayResult: Every stage, lazily

    Raises:
        ValueError: If `percent_method` is not recognised
    """
    check_percent_method(percent_method)

    trades = clean_trades(
        raw_trades, start_time=trade_start_time, end_time=trade_end_time
    )
    nbbo = clean_official_complete_nbbo(
        raw_official_nbbo, start_time=quote_start_time, end_time=quote_end_time
    )
    nbbo = nbbo.mutate(midpoint=(nbbo.best_bid + nbbo.best_ask) / 2)

    matched = merge_trades_official_nbbo(trades, nbbo, lag=lag)
    signed = sign_trades(matched, groupby_col=groupby_col)

    effective_spreads = compute_effective_spreads(
        signed,
        percent_method=percent_method,
        exclude_locked_crossed=exclude_locked_crossed,
    )

    # Quoted-spread statistics, in H&J's order: restrict the window, then time
    # each quote, then drop the locked and crossed ones. The order matters. A
    # dropped quote's duration is not handed to its predecessor, it simply does
    # not count, and a quote that survives keeps the duration it actually stood
    # for.
    quote_panel = nbbo
    if quoted_spread_start_time is not None:
        quote_panel = filter_timestamp(
            quote_panel,
            timestamp=quote_panel.timestamp,
            start_time=quoted_spread_start_time,
        )

    # The last quote of the day stands until the close.
    close = datetime.datetime.combine(date, quote_end_time or datetime.time(16, 0))
    quote_panel = compute_quote_inforce(
        quote_panel, end_timestamp=close, groupby_col=groupby_col
    )

    if exclude_locked_crossed:
        quote_panel = filter_locks_crosses(
            quote_panel, asks=quote_panel.best_ask, bids=quote_panel.best_bid
        )

    quoted_spreads = compute_spreads(quote_panel, percent_method=percent_method)

    realized_spreads = None
    if horizon is not None:
        realized_spreads = compute_rs_and_pi(
            signed,
            off_nbbo_table=nbbo,
            delay=horizon,
            suffix=horizon_suffix,
            track_retail=track_retail,
            percent_method=percent_method,
        )

    daily = _daily_aggregates(
        effective_spreads,
        quoted_spreads,
        realized_spreads,
        horizon_suffix=horizon_suffix,
        track_retail=track_retail,
        groupby_col=groupby_col,
    )

    return DayResult(
        trades=trades,
        nbbo=nbbo,
        matched=matched,
        signed=signed,
        effective_spreads=effective_spreads,
        quoted_spreads=quoted_spreads,
        realized_spreads=realized_spreads,
        daily=daily,
    )


def _daily_aggregates(
    effective_spreads: "Table",
    quoted_spreads: "Table",
    realized_spreads: "Table | None",
    *,
    horizon_suffix: str,
    track_retail: bool,
    groupby_col: str,
) -> "Table":
    """One row per symbol: trade-weighted and time-weighted measures joined."""
    trade_side = compute_averages(
        effective_spreads,
        cols=TRADE_MEASURES,
        group=groupby_col,
        weights=list(TRADE_WEIGHTS),
    )

    quote_side = compute_weighted_averages(
        quoted_spreads,
        measures=list(QUOTE_MEASURES),
        groupby_col=groupby_col,
    )

    # `outer` keeps a symbol that has quotes but no trades, or the reverse.
    # rname avoids a collision on the join key itself, which ibis rejects.
    daily = trade_side.join(
        quote_side, groupby_col, how="outer", rname="{name}_quotes"
    ).drop(f"{groupby_col}_quotes")

    if realized_spreads is not None:
        signs = BASE_SIGNS + RETAIL_SIGNS if track_retail else BASE_SIGNS
        measures = [
            f"{prefix}{sign}_{horizon_suffix}"
            for sign in signs
            for prefix in (
                "realized_spread_dollar_",
                "realized_spread_percent_",
                "price_impact_dollar_",
                "price_impact_percent_",
            )
        ]
        rs_side = compute_averages(
            realized_spreads,
            cols=measures,
            group=groupby_col,
            weights=list(TRADE_WEIGHTS),
        )
        daily = daily.join(rs_side, groupby_col, how="outer", rname="{name}_rs").drop(
            f"{groupby_col}_rs"
        )

    return daily
