# Cleaning

Cleaning turns a raw daily TAQ table into a standardised one. Every cleaning function takes an Ibis table and returns an Ibis table, so nothing executes until you ask for results.

All four share two steps: the separate `date` and `time_m` columns are merged into a `timestamp`, and `sym_root` and `sym_suffix` are merged into a `symbol`. Source columns may be upper or lower case.

## Trades

```python
from pytaq import clean_trades

trades = clean_trades(raw_trades)
```

Drops corrected trades (`tr_corr != "00"`) and non-positive prices, restricts to the trade window, and adds `dollar` (price times size). Output columns: `timestamp`, `symbol`, `ex`, `size`, `price`, `dollar`, `tr_seqnum`, `tr_scond`.

```python
import datetime

trades = clean_trades(
    raw_trades,
    exclude_corrections=True,
    price_positive_only=True,
    start_time=datetime.time(9, 30),
    end_time=datetime.time(16, 0),
)
```

## Quotes

```python
from pytaq import clean_quote_table

quotes = clean_quote_table(raw_quotes)
```

Applies, in order: quote-condition allowlist, cancelled quotes, crossed markets, abnormal spreads, withdrawn quotes, and NBBO eligibility. Sizes are converted from round lots to shares.

"Exclude" means the offending side is set to null, not that the row is dropped. Holden and Jacobsen are explicit that a withdrawn quote must not be deleted, because the NBBO carries each venue's last quote forward and deleting the withdrawal leaves the venue's *previous* quote standing as though still live. Only `nbbo_only` is a genuine row filter.

One consequence: a one-sided quote keeps its live side and still contributes to that side of the NBBO, rather than being discarded.

Each step has its own switch:

```python
quotes = clean_quote_table(
    raw_quotes,
    keep_qu_cond=["A", "R"],
    exclude_canceled_quotes=True,
    exclude_crossed_markets=True,
    exclude_withdrawn_quotes=True,
    exclude_abnormal_spreads=True,
    nbbo_only=True,
    output_flags=False,
)
```

`output_flags=True` keeps `qu_cond`, `natbbo_ind`, `qu_source` and `qu_cancel` in the output, which is useful when checking why a row survived.

A null `qu_cancel` means "not cancelled" and the quote is kept. This is worth stating because the obvious spelling, `qu_cancel != "B"`, is NULL in SQL for a null flag and silently drops the row.

## NBBO

```python
from pytaq import clean_nbbo

nbbo = clean_nbbo(raw_nbbo)
```

Adds the empty-quote filter, sets a side to null when its price or size is non-positive, applies the abnormal-spread and abnormal-quote-change filters, and by default keeps only quotes that changed the NBBO.

The change filter compares each quote against the previous one for the same symbol using null-safe comparison, so the opening quote of each symbol is kept, and consecutive all-null quotes collapse.

## Official complete NBBO

Either read WRDS's version and clean it:

```python
from pytaq import clean_official_complete_nbbo

nbbo = clean_official_complete_nbbo(raw_official_nbbo)
```

or build it yourself from the NBBO and quote files:

```python
from pytaq import clean_nbbo, clean_quote_table, merge_quotes_nbbo

official = merge_quotes_nbbo(clean_nbbo(raw_nbbo), clean_quote_table(raw_quotes))
```

With the default options on the inputs, the constructed table should match WRDS's own. Confirming that against real data is still outstanding; see `TO_VERIFY.md`.

## Matching trades to quotes

```python
from pytaq import merge_trades_official_nbbo

matched = merge_trades_official_nbbo(trades, nbbo)
```

An as-of join: each trade takes the most recent quote for its symbol at or before its timestamp, never a later one. A trade before any quote keeps null quote columns rather than being dropped, so trade counts are preserved. Quote columns that collide with trade columns are suffixed `_quote`.
