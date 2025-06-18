import ibis


def merge_trades_official_nbbo(
    trades: ibis.Table,
    off_nbbo: ibis.Table,
) -> ibis.Table:
    """Merges the trades with the corresponding official NBBO at the time.

    Args:
        trades (ibis.Table): Trades
        off_nbbo (ibis.Table): Official NBBO

    Returns:
        ibis.Table: Trades with the corresponding NBBO
    """
    # Sort both tables
    trades = trades.order_by(["timestamp", "symbol"])
    off_nbbo = off_nbbo.order_by(["timestamp", "symbol"])

    # Perform asof join
    return trades.asof_join(
        off_nbbo,
        predicates=[trades.symbol == off_nbbo.symbol],
        by="timestamp",
        tolerance=None,
        suffixes=("", "_quote"),
    )
