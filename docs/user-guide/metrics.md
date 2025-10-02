# Computing Metrics

This guide covers computing financial metrics from TAQ data, including spreads, price impact, trade signs, and market quality measures.

## Overview

The metrics module provides functions to calculate:

- **Spreads**: Quoted spreads, effective spreads, realized spreads
- **Price Impact**: Temporary and permanent price impact
- **Trade Signs**: Lee-Ready, EMO, CLNV, BJZ classification
- **Market Quality**: Locked and crossed markets
- **Averages**: Time-weighted, volume-weighted averages

## Spread Metrics

### Quoted Spreads

The quoted spread is the difference between ask and bid:

```python
from pytaq.metrics.quoted_spreads import compute_spreads
from pytaq.cleaning.quotes import clean_quote_table

# Clean quotes first
clean_quotes = clean_quote_table(quotes, keep_qu_cond=["A"])

# Compute quoted spreads
spreads = compute_spreads(clean_quotes)

# View results
result = spreads.execute()
print(result[["symbol", "timestamp", "quoted_spread_dollar", "quoted_spread_bps"]])
```

The function computes:
- `quoted_spread_dollar`: Ask - Bid (in dollars)
- `quoted_spread_bps`: Spread as basis points of midpoint

### Effective Spreads

The effective spread measures execution cost relative to midpoint:

```python
from pytaq.metrics.effective_spreads import compute_effective_spread

# Requires trades with midpoint quotes
trades_with_quotes = merge_trades_quotes(trades, quotes)

# Compute effective spreads
eff_spreads = compute_effective_spread(
    table=trades_with_quotes,
    price_col="price",
    midpoint_col="midpoint",
    sign_col="trade_sign"
)

# View results
result = eff_spreads.execute()
print(result[["symbol", "timestamp", "eff_spread_dollar", "eff_spread_bps"]])
```

Effective spread = 2 × |price - midpoint|

### Realized Spreads

The realized spread measures price reversion after trade:

```python
from pytaq.metrics.rs_and_pi import dollar_realized_spread, bps_realized_spread

# Requires trades with current and future midpoints
trades_with_midpoints = prepare_trades_with_midpoints(trades, quotes)

# Compute dollar realized spread
rs_dollar = dollar_realized_spread(
    table=trades_with_midpoints,
    price_col="price",
    midpoint_next_col="midpoint_5min",  # 5-minute ahead
    sign_col="trade_sign"
)

# Compute basis points realized spread
rs_bps = bps_realized_spread(
    table=trades_with_midpoints,
    price_col="price",
    midpoint_col="midpoint",
    midpoint_next_col="midpoint_5min",
    sign_col="trade_sign"
)
```

Realized spread = sign × (price - midpoint_future) × 2

## Price Impact

### Dollar Price Impact

```python
from pytaq.metrics.rs_and_pi import dollar_price_impact

# Compute price impact in dollars
pi_dollar = dollar_price_impact(
    table=trades_with_midpoints,
    midpoint_col="midpoint",
    midpoint_next_col="midpoint_5min",
    sign_col="trade_sign"
)

# View results
result = pi_dollar.execute()
print(result[["symbol", "timestamp", "pi_dollar"]])
```

Price impact = sign × (midpoint_future - midpoint) × 2

### Basis Points Price Impact

```python
from pytaq.metrics.rs_and_pi import bps_price_impact

# Compute price impact in basis points
pi_bps = bps_price_impact(
    table=trades_with_midpoints,
    midpoint_col="midpoint",
    midpoint_next_col="midpoint_5min",
    sign_col="trade_sign"
)
```

## Trade Classification

### Lee-Ready Algorithm

The Lee-Ready (LR) algorithm classifies trades as buys or sells:

```python
from pytaq.metrics.signs import sign_lr

# Requires trades with midpoint
trades_with_midpoint = merge_trades_quotes(trades, quotes)

# Classify trades
trades_signed = trades_with_midpoint.mutate(
    trade_sign=sign_lr(
        price=trades_with_midpoint["price"],
        midpoint=trades_with_midpoint["midpoint"]
    )
)

# View results
result = trades_signed.execute()
print(result[["symbol", "price", "midpoint", "trade_sign"]])
# trade_sign: 1 (buy), -1 (sell), NULL (at midpoint)
```

### EMO Algorithm

The Ellis, Michaely, and O'Hara (EMO) algorithm:

```python
from pytaq.metrics.signs import sign_emo

# Classify with EMO
trades_signed = trades.mutate(
    trade_sign=sign_emo(
        price=trades["price"],
        midpoint=trades["midpoint"],
        buy_sell=trades["buy_sell_indicator"]  # Exchange-provided indicator
    )
)
```

### CLNV Algorithm

The Chakrabarty, Li, Nguyen, and Van Ness (CLNV) algorithm:

```python
from pytaq.metrics.signs import sign_clnv

# Classify with CLNV
trades_signed = trades.mutate(
    trade_sign=sign_clnv(
        price=trades["price"],
        midpoint=trades["midpoint"],
        buy_sell=trades["buy_sell_indicator"]
    )
)
```

### BJZ Algorithm

The Boehmer, Jones, and Zhang (BJZ) algorithm for retail trades:

```python
from pytaq.metrics.signs import sign_bjz

# Classify off-exchange trades
trades_signed = trades.mutate(
    trade_sign=sign_bjz(
        price=trades["price"],
        ex=trades["exchange"]  # 'D' for off-exchange
    )
)

# View off-exchange classifications
result = trades_signed.filter(
    trades_signed["exchange"] == "D"
).execute()
print(result[["symbol", "price", "exchange", "trade_sign"]])
```

BJZ uses sub-penny pricing patterns:
- Sells: 3rd-4th decimals in [0.01, 0.40)
- Buys: 3rd-4th decimals in [0.60, 0.99)
- Only for off-exchange trades (exchange='D')

## Market Quality Metrics

### Locked and Crossed Markets

```python
from pytaq.metrics.locks_crosses import compute_locks_crosses

# Compute lock and cross indicators
quality_metrics = compute_locks_crosses(nbbo)

# View results
result = quality_metrics.execute()
print(result[["symbol", "timestamp", "is_locked", "is_crossed"]])

# Summary statistics
locks = result["is_locked"].sum()
crosses = result["is_crossed"].sum()
print(f"Locked markets: {locks}")
print(f"Crossed markets: {crosses}")
```

Definitions:
- Locked market: bid = ask
- Crossed market: bid > ask

## Time-Weighted Averages

### Simple Time-Weighted Average

```python
from pytaq.metrics.averages import time_weighted_average

# Compute time-weighted average spread
twa_spread = time_weighted_average(
    table=quotes,
    value_col="quoted_spread",
    time_col="timestamp",
    group_cols=["symbol", "date"]
)

# View results
result = twa_spread.execute()
print(result[["symbol", "date", "twa_quoted_spread"]])
```

### Volume-Weighted Average Price (VWAP)

```python
from pytaq.metrics.averages import volume_weighted_average

# Compute VWAP
vwap = volume_weighted_average(
    table=trades,
    value_col="price",
    weight_col="volume",
    group_cols=["symbol", "date"]
)

# View results
result = vwap.execute()
print(result[["symbol", "date", "vwap"]])
```

## Complete Workflow Example

### End-to-End Metrics Calculation

```python
from datetime import date, time
from decimal import Decimal
from pytaq.extract.quotes import extract_quotes
from pytaq.extract.trades import extract_trades
from pytaq.cleaning.quotes import clean_quote_table
from pytaq.cleaning.trades import clean_trade_table
from pytaq.metrics.quoted_spreads import compute_spreads
from pytaq.metrics.signs import sign_lr
from pytaq.metrics.rs_and_pi import dollar_realized_spread
import ibis

# 1. Extract data
date_val = date(2023, 1, 15)
symbols = ["AAPL", "MSFT"]

quotes = extract_quotes(con, "/path/to/data", date_val, symbols)
trades = extract_trades(con, "/path/to/data", date_val, symbols)

# 2. Clean data
clean_quotes = clean_quote_table(
    quotes, keep_qu_cond=["A"], max_spread=Decimal("5.0")
)
clean_trades = clean_trade_table(
    trades, keep_tr_scond=["@"], remove_abnormal_sales=True
)

# 3. Compute quoted spreads
spreads = compute_spreads(clean_quotes)

# 4. Merge trades with quotes for midpoint
merged = clean_trades.join(
    spreads,
    predicates=[
        clean_trades["symbol"] == spreads["symbol"],
        clean_trades["timestamp"] == spreads["timestamp"]
    ],
    how="left"
)

# 5. Classify trades
signed_trades = merged.mutate(
    trade_sign=sign_lr(
        price=merged["price"],
        midpoint=merged["midpoint"]
    )
)

# 6. Compute realized spreads (requires future midpoints)
# ... add logic to compute future midpoints ...
rs = dollar_realized_spread(
    table=signed_trades,
    price_col="price",
    midpoint_next_col="midpoint_5min",
    sign_col="trade_sign"
)

# 7. Execute and analyze
result = rs.execute()
print(result[["symbol", "timestamp", "price", "trade_sign", "rs_dollar"]])

# 8. Aggregate by symbol
daily_metrics = result.groupby("symbol").agg({
    "rs_dollar": "mean",
    "price": "count"
}).rename(columns={"price": "num_trades"})
print(daily_metrics)
```

## Advanced Metrics

### Intraday Patterns

```python
from datetime import time

# Compute spreads by hour
hourly_spreads = spreads.mutate(
    hour=spreads["timestamp"].hour()
).group_by(["symbol", "hour"]).aggregate(
    avg_spread=spreads["quoted_spread_dollar"].mean(),
    min_spread=spreads["quoted_spread_dollar"].min(),
    max_spread=spreads["quoted_spread_dollar"].max()
)

result = hourly_spreads.order_by("hour").execute()
print(result)
```

### Cross-Symbol Analysis

```python
# Compare metrics across symbols
symbol_metrics = signed_trades.group_by("symbol").aggregate(
    avg_price=signed_trades["price"].mean(),
    avg_spread=signed_trades["quoted_spread_dollar"].mean(),
    num_trades=signed_trades["symbol"].count(),
    pct_buys=(signed_trades["trade_sign"] == 1).sum() / signed_trades["symbol"].count()
)

result = symbol_metrics.order_by(ibis.desc("num_trades")).execute()
print(result)
```

### Rolling Windows

```python
# Compute 5-minute rolling average spread
rolling_spread = quotes.mutate(
    rolling_avg_spread=quotes["quoted_spread_dollar"].mean().over(
        ibis.window(
            preceding=300,  # 5 minutes in seconds
            following=0,
            order_by="timestamp"
        )
    )
)
```

## Performance Optimization

### 1. Filter Early

```python
# Filter to regular hours before metrics
regular_hours = clean_trades.filter(
    (clean_trades["time_m"] >= time(9, 30)) &
    (clean_trades["time_m"] <= time(16, 0))
)

# Then compute metrics on filtered data
signed_trades = regular_hours.mutate(
    trade_sign=sign_lr(regular_hours["price"], regular_hours["midpoint"])
)
```

### 2. Compute Only Needed Metrics

```python
# Don't compute all metrics if only need quoted spreads
spreads_only = compute_spreads(clean_quotes).select([
    "symbol",
    "timestamp",
    "quoted_spread_dollar"
])
```

### 3. Use Appropriate Aggregation

```python
# Daily aggregates instead of tick-by-tick
daily_spreads = spreads.group_by(["symbol", "date"]).aggregate(
    mean_spread=spreads["quoted_spread_dollar"].mean(),
    median_spread=spreads["quoted_spread_dollar"].approx_median()
)
```

## Next Steps

- Learn about [NBBO-specific workflows](nbbo.md)
- Review [API documentation](../api/metrics.md) for detailed function references
- Explore [extraction](extraction.md) and [cleaning](cleaning.md) pipelines
