import ibis


def merge_quotes_nbbo(
    nbbo: ibis.Table, quote: ibis.Table, keep_changes_only: bool = True
) -> ibis.Table:
    """Merges the NBBO and Quote tables to create the official complete NBBO.

    With default options used to clean the input tables, this function should
    yield the same results as the official complete NBBO table in WRDS.

    Args:
        nbbo (ibis.Table): NBBO quotes
        quote (ibis.Table): Quotes
        keep_changes_only (bool, optional): Only keep the last observation for each timestamp. Defaults to True.

    Returns:
        ibis.Table: Official complete NBBO
    """
    # Union the tables
    t = nbbo.union(quote)

    # Sort by symbol, timestamp, sequence number
    t = t.order_by(["symbol", "timestamp", "qu_seqnum"])

    # Remove duplicate quotes at same microsecond (keep last one based on sequence number)
    if keep_changes_only:
        t = (
            t.group_by(["symbol", "timestamp"])
            .mutate(
                row_num=ibis.row_number().over(
                    order_by=[ibis.desc("qu_seqnum")], group_by=["symbol", "timestamp"]
                )
            )
            .filter(lambda x: x.row_num == 1)
            .drop("row_num")
        )

    return t
