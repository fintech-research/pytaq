import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ibis.expr.types import Table

#: Holden and Jacobsen (2014), section II.B: "For DTAQ, we match trades and
#: quotes with a one millisecond lag (i.e., a given trade is matched to the
#: NBBO that was in-force one millisecond earlier)."
HJ_TRADE_QUOTE_LAG = datetime.timedelta(milliseconds=1)


def merge_trades_official_nbbo(
    trades: "Table",
    off_nbbo: "Table",
    lag: datetime.timedelta = HJ_TRADE_QUOTE_LAG,
) -> "Table":
    """Match each trade to the NBBO in force `lag` before it.

    The lag exists to stop a quote that was itself a consequence of the trade
    being treated as the state the trader faced. Without it, a quote stamped in
    the same instant as the trade counts as prevailing, which biases effective
    spreads downward.

    Holden and Jacobsen specify one millisecond for DTAQ, and their Table IA.II
    shows the choice matters: moving from a 1ms to a 100ms lag shifts percent
    effective spread from 0.377% to 0.420% and trades outside the NBBO from
    3.3% to 5.1%. They argue against a longer arbitrary lag on the grounds that
    it will not stay appropriate as trading speeds change.

    A trade that precedes any usable quote for its symbol keeps null quote
    columns rather than being dropped, so trade counts are preserved.

    Args:
        trades ("Table"): Cleaned trades
        off_nbbo ("Table"): Cleaned official NBBO
        lag (datetime.timedelta): How far before the trade the quote must have
            been in force. Defaults to one millisecond, following H&J. Pass
            `timedelta(0)` to match contemporaneous quotes instead

    Returns:
        "Table": Trades with the prevailing NBBO attached, quote columns
        suffixed `_quote` where names collide
    """
    # `on` carries the inequality that makes this an as-of join, and must be
    # backward-looking: a trade is matched to a quote that already existed.
    # `predicates` carries the equi-join keys. There is no `by` or `suffixes`
    # argument; overlapping column names are disambiguated with `rname`.
    trade_time = trades.timestamp - lag if lag else trades.timestamp

    return trades.asof_join(
        off_nbbo,
        on=trade_time >= off_nbbo.timestamp,
        predicates=[trades.symbol == off_nbbo.symbol],
        rname="{name}_quote",
    )
