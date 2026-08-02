# Working with the NBBO

The National Best Bid and Offer is the best bid and best ask across all venues at a moment in time. Almost every liquidity metric is measured against it, so getting it right matters more than any other part of the pipeline.

There are two ways to obtain it.

## Read WRDS's official complete NBBO

Simplest, and what most work should use.

```python
import datetime

from pytaq import clean_official_complete_nbbo, local

con = local.connect()
raw = local.get_official_complete_nbbo(con, "data/", datetime.date(2020, 1, 2))
nbbo = clean_official_complete_nbbo(raw)
```

Output columns: `timestamp`, `symbol`, `best_bid`, `best_bidsizeshares`, `best_ask`, `best_asksizeshares`.

## Build it from the NBBO and quote files

The official file only carries quotes from venues that reported an NBBO. Holden and Jacobsen reconstruct the complete picture by unioning the NBBO file with the eligible quotes.

```python
from pytaq import clean_nbbo, clean_quote_table, merge_quotes_nbbo

nbbo = clean_nbbo(raw_nbbo)
quotes = clean_quote_table(raw_quotes)
official = merge_quotes_nbbo(nbbo, quotes)
```

`merge_quotes_nbbo` unions the two and, by default, keeps one row per symbol and timestamp: the one with the highest `qu_seqnum`, which is the last quote at that microsecond.

```python
official = merge_quotes_nbbo(nbbo, quotes, keep_changes_only=False)
```

With default options on both inputs this should reproduce WRDS's own official complete NBBO. That claim has not yet been checked against real data; it is tracked in `TO_VERIFY.md`.

## What cleaning the NBBO does

`clean_nbbo` runs these in order, each switchable:

1. **Time window**, 09:00 to 16:00 by default. Earlier than the trade window so quotes are in force before the first trade.
2. **Quote conditions**, keeping `A`, `B`, `H`, `O`, `R`, `W`.
3. **Cancelled quotes**, dropping `qu_cancel = "B"`. A null flag means "not cancelled" and is kept.
4. **Empty quotes**, dropping rows with neither a usable bid nor a usable ask.
5. **Spreads and best quotes**, computing spread and midpoint, nulling a side whose price or size is non-positive, converting round lots to shares.
6. **Abnormal spreads**, nulling a side when the spread exceeds $5.00 and that side moved more than $2.50 against the previous midpoint.
7. **Changes only**, keeping quotes that actually moved the NBBO.

### On the changes-only filter

A quote is kept if any of the bid, ask, bid size or ask size differs from the previous quote for that symbol. The comparison is null-safe: null to null is unchanged, null to a value is a change.

That matters at the boundaries. The opening quote of each symbol has no predecessor, so a plain `!=` would evaluate to NULL and drop it, which loses exactly the quote needed to sign the day's first trades.

## Matching trades

```python
from pytaq import merge_trades_official_nbbo

matched = merge_trades_official_nbbo(trades, nbbo)
```

A backward-looking as-of join. Each trade takes the most recent quote for its symbol at or before its own timestamp, never one that arrived later. Trades preceding any quote are kept with null quote columns, so counts are preserved and you can see how many were unmatched:

```python
df = matched.execute()
print(f"unmatched: {df['best_bid'].isna().sum()} of {len(df)}")
```
