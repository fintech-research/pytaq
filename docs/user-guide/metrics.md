# Metrics

Metrics run on a table of trades already matched to quotes, as produced by [`merge_trades_official_nbbo`](cleaning.md#matching-trades-to-quotes).

## Trade signing

```python
from pytaq import sign_trades

signed = sign_trades(matched)
```

Adds one column per algorithm, prefixed `BuySell` by default:

| Column | Algorithm |
|---|---|
| `BuySellTick` | Tick test |
| `BuySellLR` | Lee-Ready |
| `BuySellEMO` | Ellis, Michaely and O'Hara |
| `BuySellCLNV` | Chakrabarty, Li, Nguyen and Van Ness |
| `BuySellBJZ` | Boehmer, Jones and Zhang, retail trades only |
| `BuySellLRnotBJZ` and friends | The base algorithm, restricted to trades BJZ did not classify |

`+1` is a buy, `-1` a sell, null unclassified.

```python
signed = sign_trades(
    matched,
    groupby_col="symbol",
    timestamp_col="timestamp",
    price_col="price",
    sign_col_prefix="BuySell",
    clnv_threshold=0.3,
)
```

### The tick test

A trade is a buy if the price rose against the previous trade for the same symbol, a sell if it fell. A zero return carries no information, so the direction is carried forward from the last non-zero move.

Trades before any price change have no direction at all and are left null rather than guessed at. `sign_tick` can be called on its own; it returns the table with the direction column added, because the forward fill needs an intermediate result that SQL will not let it nest.

### BJZ retail classification

BJZ identifies retail trades from sub-penny price improvement on off-exchange trades (`ex = "D"`). A price ending in `.XX01` to `.XX39` is a retail sell, `.XX60` to `.XX99` a retail buy. Anything else, and any on-exchange trade, is unclassified.

The `notBJZ` columns apply a base algorithm only to trades BJZ left unclassified, which is how you separate retail from the rest.

## Spreads

```python
from pytaq.metrics import compute_effective_spreads, compute_spreads

quoted = compute_spreads(nbbo)
effective = compute_effective_spreads(signed)
```

`compute_spreads` adds `quoted_spread_dollar` and `quoted_spread_percent` to a quote table, along with depth in dollars and shares on each side.

### Percent conventions

Every percent measure follows Holden and Jacobsen by default: the dollar measure divided by the reference midpoint. The log-difference form is available on each function:

```python
compute_spreads(nbbo, percent_method="log")
compute_effective_spreads(signed, percent_method="log")
compute_rs_and_pi(signed, nbbo, percent_method="log")
```

The two agree to first order and diverge as spreads widen, so the choice matters least where spreads are tightest. Dollar measures are unaffected. Note that realized spread and price impact are divided by the **future** midpoint, as H&J specify, not the contemporaneous one.

`compute_effective_spreads` adds `DollarEffectiveSpread` and `PercentEffectiveSpread`, twice the absolute distance between the trade price and the prevailing midpoint.

Trades struck while the market was locked or crossed are excluded, as Holden and Jacobsen require, since the midpoint is not meaningful then. The indicators are derived from the prevailing bid and ask, so nothing needs preparing:

```python
effective = compute_effective_spreads(signed)
effective = compute_effective_spreads(signed, exclude_locked_crossed=False)  # keep them
```

## Realized spreads and price impacts

Both need the midpoint at some horizon after the trade, so they take the NBBO table as well:

```python
import datetime

from pytaq.metrics import compute_rs_and_pi

result = compute_rs_and_pi(
    signed,
    off_nbbo_table=nbbo,
    delay=datetime.timedelta(minutes=5),
    suffix="5min",
    track_retail=False,
)
```

The horizon is a `timedelta` and `suffix` names the output columns, so several horizons can sit side by side. `track_retail=True` adds the BJZ-based variants.

## Averaging

Two functions, for two different weightings.

Time-weighted, for quote-level measures. A quote counts for as long as it stood, so you need `inforce` first:

```python
import datetime

from pytaq.metrics import compute_quote_inforce, compute_weighted_averages

close = datetime.datetime(2020, 1, 2, 16, 0)
with_inforce = compute_quote_inforce(nbbo, end_timestamp=close)

daily = compute_weighted_averages(
    with_inforce,
    measures=["quoted_spread_dollar", "quoted_spread_percent"],
    groupby_col="symbol",
    inforce_col="inforce",
)
```

`compute_quote_inforce` gives each quote the seconds until the next quote for the same symbol. The last quote of the day runs to `end_timestamp`.

Simple and share- or dollar-weighted, for trade-level measures:

```python
from pytaq.metrics import compute_averages

daily = compute_averages(
    signed,
    cols=["DollarEffectiveSpread", "PercentEffectiveSpread"],
    group="symbol",
    weights=[(None, ""), ("size", "_sw"), ("dollar", "_dw")],
)
```

Each `(weight_column, suffix)` pair produces one set of output columns: `(None, "")` for the simple average, `("size", "_sw")` share-weighted, `("dollar", "_dw")` dollar-weighted.

## Locks and crosses

```python
from pytaq.metrics import (
    crossed_rows,
    filter_locks_crosses,
    locked_crossed_rows,
    locked_rows,
)

clean = filter_locks_crosses(nbbo, asks=nbbo.best_ask, bids=nbbo.best_bid)
```

A locked market has bid equal to ask, a crossed market has bid above ask. Comparisons go through an absolute tolerance rather than exact equality, since prices that should be equal often are not to the last bit.
