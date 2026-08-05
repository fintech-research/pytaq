import datetime
from typing import TYPE_CHECKING

from .common import TIMESTAMP_NS_COL

if TYPE_CHECKING:
    from ibis.expr.types import Table

#: Holden and Jacobsen's Daily TAQ code of 16 March 2018 lags by one nanosecond:
#: it shifts every quote forward with ``time_m=time_m+.000000001`` before
#: interleaving. This is the default, since it is their current practice on the
#: data PyTAQ targets.
HJ_TRADE_QUOTE_LAG_NS: int = 1

#: Holden and Jacobsen (2014), section II.B: "For DTAQ, we match trades and
#: quotes with a one millisecond lag (i.e., a given trade is matched to the
#: NBBO that was in-force one millisecond earlier)." The paper predates
#: nanosecond TAQ; their own code moved on. Pass this to reproduce the paper.
HJ_PAPER_TRADE_QUOTE_LAG_NS: int = 1_000_000


def lag_nanoseconds(lag: "datetime.timedelta | int") -> int:
    """Normalise a lag to an integer count of nanoseconds.

    A `datetime.timedelta` cannot hold a nanosecond: its finest unit is the
    microsecond, so `timedelta(microseconds=0.001)` is zero. The lag is therefore
    an `int` of nanoseconds, with a timedelta still accepted for convenience.

    Args:
        lag (datetime.timedelta | int): Nanoseconds, or a timedelta

    Returns:
        int: The lag in nanoseconds
    """
    if isinstance(lag, datetime.timedelta):
        return round(lag.total_seconds() * 1_000_000_000)
    return int(lag)


def merge_trades_official_nbbo(
    trades: "Table",
    off_nbbo: "Table",
    lag: "datetime.timedelta | int" = HJ_TRADE_QUOTE_LAG_NS,
) -> "Table":
    """Match each trade to the NBBO in force `lag` nanoseconds before it.

    The lag exists to stop a quote that was itself a consequence of the trade
    being treated as the state the trader faced. Without it, a quote stamped in
    the same instant as the trade counts as prevailing, which biases effective
    spreads downward.

    One nanosecond by default, which is what H&J's 2018 DTAQ code applies. Their
    2014 paper specifies one millisecond, and Table IA.II shows the choice
    matters: moving from a 1ms to a 100ms lag shifts percent effective spread
    from 0.377% to 0.420% and trades outside the NBBO from 3.3% to 5.1%. They
    argue against a longer arbitrary lag on the grounds that it will not stay
    appropriate as trading speeds change, and by 2018, with TAQ resolving to
    nanoseconds, they had shortened it to the smallest unit available. Pass
    `HJ_PAPER_TRADE_QUOTE_LAG_NS` for the paper's millisecond.

    Matching is done on `timestamp_ns` when both sides carry it, which is what
    the cleaners produce. Against microsecond-resolution `timestamp` alone, a
    sub-microsecond lag cannot be expressed and degrades to a contemporaneous
    match, the closest approximation at that resolution.

    A trade that precedes any usable quote for its symbol keeps null quote
    columns rather than being dropped, so trade counts are preserved.

    Args:
        trades ("Table"): Cleaned trades
        off_nbbo ("Table"): Cleaned official NBBO
        lag (datetime.timedelta | int): Nanoseconds before the trade at which the
            quote must have been in force, or a timedelta. Defaults to one
            nanosecond, following H&J's DTAQ code. Pass `0` to match
            contemporaneous quotes instead

    Returns:
        "Table": Trades with the prevailing NBBO attached, quote columns
        suffixed `_quote` where names collide
    """
    lag_ns = lag_nanoseconds(lag)

    # `on` carries the inequality that makes this an as-of join, and must be
    # backward-looking: a trade is matched to a quote that already existed.
    # `predicates` carries the equi-join keys. There is no `by` or `suffixes`
    # argument; overlapping column names are disambiguated with `rname`.
    if TIMESTAMP_NS_COL in trades.columns and TIMESTAMP_NS_COL in off_nbbo.columns:
        trade_time = trades[TIMESTAMP_NS_COL] - lag_ns
        quote_time = off_nbbo[TIMESTAMP_NS_COL]
    else:
        # Whole microseconds only. A 1ns lag floors to zero here, which is not a
        # silent loss: at microsecond resolution a quote in the same microsecond
        # as the trade is indistinguishable from one a nanosecond earlier.
        lag_us = lag_ns // 1000
        trade_time = (
            trades.timestamp - datetime.timedelta(microseconds=lag_us)
            if lag_us
            else trades.timestamp
        )
        quote_time = off_nbbo.timestamp

    return trades.asof_join(
        off_nbbo,
        on=trade_time >= quote_time,
        predicates=[trades.symbol == off_nbbo.symbol],
        rname="{name}_quote",
    )
