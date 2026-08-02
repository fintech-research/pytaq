import ibis


def merge_trades_official_nbbo(
    trades: ibis.Table,
    off_nbbo: ibis.Table,
) -> ibis.Table:
    """Merges the trades with the corresponding official NBBO at the time.

    Each trade is matched to the most recent quote for the same symbol at or
    before the trade's timestamp. A trade that precedes any quote for its
    symbol keeps null quote columns rather than being dropped.

    Args:
        trades (ibis.Table): Trades
        off_nbbo (ibis.Table): Official NBBO

    Returns:
        ibis.Table: Trades with the corresponding NBBO
    """
    # `on` carries the inequality that makes this an as-of join, and must be
    # backward-looking: a trade is matched to a quote that already existed.
    # `predicates` carries the equi-join keys. There is no `by` or `suffixes`
    # argument; overlapping column names are disambiguated with `rname`.
    return trades.asof_join(
        off_nbbo,
        on=trades.timestamp >= off_nbbo.timestamp,
        predicates=[trades.symbol == off_nbbo.symbol],
        rname="{name}_quote",
    )
