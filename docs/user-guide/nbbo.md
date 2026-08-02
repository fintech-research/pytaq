# NBBO Workflows

This guide covers working with National Best Bid and Offer (NBBO) data for market quality analysis.

## Overview

NBBO represents the best available bid and ask prices across all exchanges. PyTAQ provides tools for:

- Extracting NBBO data
- Computing NBBO-based metrics
- Analyzing market quality
- Comparing official vs computed NBBO

## NBBO Basics

### What is NBBO?

The National Best Bid and Offer (NBBO) is:
- **Best Bid**: Highest bid price across all exchanges
- **Best Ask**: Lowest ask price across all exchanges
- **Required by Regulation NMS**: Brokers must execute at NBBO or better

### NBBO vs Quote Data

```python
# Regular quotes: Exchange-specific
quotes = extract_quotes(con, path, date(2023, 1, 15), ["AAPL"])
# Contains: bid, ask, exchange, timestamp

# NBBO: Best across all exchanges
nbbo = extract_nbbo(con, path, date(2023, 1, 15), ["AAPL"])
# Contains: best_bid, best_ask, timestamp
```

## Extracting NBBO Data

### Basic NBBO Extraction

```python
from pytaq.extract.nbbo import extract_nbbo
from datetime import date
import ibis

con = ibis.duckdb.connect()

# Extract NBBO for specific symbols
nbbo = extract_nbbo(
    con=con,
    source_path="/path/to/taq/data",
    date=date(2023, 1, 15),
    symbols=["AAPL", "MSFT", "GOOGL"],
)

# View the data
print(nbbo.head().execute())
```

### Official NBBO

The official NBBO from the regulatory feed:

```python
from pytaq.extract.official_nbbo import extract_official_nbbo

# Extract official NBBO
official_nbbo = extract_official_nbbo(
    con=con, source_path="/path/to/taq/data", date=date(2023, 1, 15), symbols=["AAPL"]
)

# Compare columns
print("Official NBBO schema:")
print(official_nbbo.schema())
```

## Cleaning NBBO Data

### Basic NBBO Cleaning

```python
from pytaq.cleaning.nbbo import clean_nbbo_table
from decimal import Decimal

# Clean NBBO data
clean_nbbo = clean_nbbo_table(table=nbbo, max_spread=Decimal("5.0"))

# Check results
raw_count = nbbo.count().execute()
clean_count = clean_nbbo.count().execute()
print(
    f"Removed {raw_count - clean_count} records ({100 * (1 - clean_count / raw_count):.1f}%)"
)
```

### Handling Market Anomalies

```python
from pytaq.metrics.locks_crosses import compute_locks_crosses

# Identify locked and crossed markets
nbbo_with_quality = compute_locks_crosses(nbbo)

# Filter out crossed markets
valid_nbbo = nbbo_with_quality.filter(nbbo_with_quality["is_crossed"] == False)

# Keep locked but not crossed
keep_locked = nbbo_with_quality.filter(
    (nbbo_with_quality["is_crossed"] == False)
    & (nbbo_with_quality["is_locked"] == True)
)
```

## NBBO-Based Metrics

### NBBO Spreads

```python
from pytaq.metrics.quoted_spreads import compute_spreads

# Compute NBBO spreads
nbbo_spreads = compute_spreads(clean_nbbo)

# Execute and analyze
result = nbbo_spreads.execute()
print(result[["symbol", "timestamp", "quoted_spread_dollar", "quoted_spread_bps"]])

# Daily average NBBO spread
daily_spread = nbbo_spreads.group_by(["symbol", "date"]).aggregate(
    avg_spread_dollar=nbbo_spreads["quoted_spread_dollar"].mean(),
    avg_spread_bps=nbbo_spreads["quoted_spread_bps"].mean(),
    min_spread=nbbo_spreads["quoted_spread_dollar"].min(),
    max_spread=nbbo_spreads["quoted_spread_dollar"].max(),
)

print(daily_spread.execute())
```

### Time-Weighted NBBO Spread

```python
from pytaq.metrics.averages import time_weighted_average

# Compute time-weighted average NBBO spread
twa_nbbo_spread = time_weighted_average(
    table=nbbo_spreads,
    value_col="quoted_spread_dollar",
    time_col="timestamp",
    group_cols=["symbol", "date"],
)

result = twa_nbbo_spread.execute()
print(result[["symbol", "date", "twa_quoted_spread_dollar"]])
```

### Market Quality Metrics

```python
# Calculate percentage of time in locked/crossed states
quality_summary = (
    nbbo_with_quality.group_by(["symbol", "date"])
    .aggregate(
        total_observations=nbbo_with_quality["symbol"].count(),
        locked_observations=(nbbo_with_quality["is_locked"] == True).sum(),
        crossed_observations=(nbbo_with_quality["is_crossed"] == True).sum(),
    )
    .mutate(
        pct_locked=100.0
        * nbbo_with_quality["locked_observations"]
        / nbbo_with_quality["total_observations"],
        pct_crossed=100.0
        * nbbo_with_quality["crossed_observations"]
        / nbbo_with_quality["total_observations"],
    )
)

print(quality_summary.execute())
```

## Trade Execution Analysis

### Price Improvement Analysis

```python
from pytaq.extract.trades import extract_trades

# Extract trades and NBBO
trades = extract_trades(con, path, date(2023, 1, 15), ["AAPL"])
nbbo = extract_nbbo(con, path, date(2023, 1, 15), ["AAPL"])

# Merge trades with NBBO
trades_with_nbbo = trades.join(
    nbbo,
    predicates=[
        trades["symbol"] == nbbo["symbol"],
        trades["timestamp"] == nbbo["timestamp"],
    ],
    how="left",
)

# Compute price improvement
trades_analyzed = trades_with_nbbo.mutate(
    # For buy trades: NBBO ask - execution price
    # For sell trades: execution price - NBBO bid
    price_improvement=ibis.case()
    .when(
        trades_with_nbbo["trade_sign"] == 1,
        trades_with_nbbo["best_ask"] - trades_with_nbbo["price"],
    )
    .when(
        trades_with_nbbo["trade_sign"] == -1,
        trades_with_nbbo["price"] - trades_with_nbbo["best_bid"],
    )
    .else_(None)
    .end()
)

# Summary statistics
improvement_stats = trades_analyzed.aggregate(
    avg_improvement=trades_analyzed["price_improvement"].mean(),
    pct_improved=(trades_analyzed["price_improvement"] > 0).sum()
    / trades_analyzed["symbol"].count(),
    total_savings=trades_analyzed["price_improvement"].sum(),
)

print(improvement_stats.execute())
```

### Trade-Through Analysis

```python
# Identify potential trade-throughs
# Buy trade above NBBO ask or sell trade below NBBO bid
trade_throughs = trades_with_nbbo.mutate(
    is_trade_through=ibis.case()
    .when(
        (trades_with_nbbo["trade_sign"] == 1)
        & (trades_with_nbbo["price"] > trades_with_nbbo["best_ask"]),
        True,
    )
    .when(
        (trades_with_nbbo["trade_sign"] == -1)
        & (trades_with_nbbo["price"] < trades_with_nbbo["best_bid"]),
        True,
    )
    .else_(False)
    .end()
)

# Count trade-throughs
tt_summary = trade_throughs.aggregate(
    total_trades=trade_throughs["symbol"].count(),
    trade_throughs=(trade_throughs["is_trade_through"] == True).sum(),
).mutate(
    pct_trade_through=100.0
    * trade_throughs["trade_throughs"]
    / trade_throughs["total_trades"]
)

print(tt_summary.execute())
```

## Official vs Computed NBBO

### Comparing NBBO Sources

```python
# Extract both versions
computed_nbbo = extract_nbbo(con, path, date(2023, 1, 15), ["AAPL"])
official_nbbo = extract_official_nbbo(con, path, date(2023, 1, 15), ["AAPL"])

# Merge on symbol and timestamp
comparison = computed_nbbo.join(
    official_nbbo,
    predicates=[
        computed_nbbo["symbol"] == official_nbbo["symbol"],
        computed_nbbo["timestamp"] == official_nbbo["timestamp"],
    ],
    how="inner",
    suffixes=("_computed", "_official"),
)

# Check for differences
differences = comparison.mutate(
    bid_diff=comparison["best_bid_computed"] - comparison["best_bid_official"],
    ask_diff=comparison["best_ask_computed"] - comparison["best_ask_official"],
).filter((comparison["bid_diff"] != 0) | (comparison["ask_diff"] != 0))

print(f"Total comparisons: {comparison.count().execute()}")
print(f"Differences found: {differences.count().execute()}")
```

### Validation Metrics

```python
# Compute correlation and mean differences
validation = comparison.aggregate(
    bid_corr=comparison["best_bid_computed"].corr(comparison["best_bid_official"]),
    ask_corr=comparison["best_ask_computed"].corr(comparison["best_ask_official"]),
    mean_bid_diff=(
        comparison["best_bid_computed"] - comparison["best_bid_official"]
    ).mean(),
    mean_ask_diff=(
        comparison["best_ask_computed"] - comparison["best_ask_official"]
    ).mean(),
)

print(validation.execute())
```

## Intraday NBBO Analysis

### NBBO by Time of Day

```python
from datetime import time

# Add hour column
nbbo_hourly = nbbo_spreads.mutate(hour=nbbo_spreads["timestamp"].hour()).filter(
    (nbbo_spreads["timestamp"].hour() >= 9) & (nbbo_spreads["timestamp"].hour() <= 16)
)

# Aggregate by hour
hourly_patterns = nbbo_hourly.group_by(["symbol", "hour"]).aggregate(
    avg_spread=nbbo_hourly["quoted_spread_dollar"].mean(),
    avg_midpoint=((nbbo_hourly["best_bid"] + nbbo_hourly["best_ask"]) / 2).mean(),
    num_updates=nbbo_hourly["symbol"].count(),
)

result = hourly_patterns.order_by(["symbol", "hour"]).execute()
print(result)
```

### Opening and Closing Spreads

```python
# Opening spreads (9:30-10:00 AM)
opening = (
    nbbo_spreads.filter(
        (nbbo_spreads["timestamp"].hour() == 9)
        & (nbbo_spreads["timestamp"].minute() >= 30)
        | (nbbo_spreads["timestamp"].hour() == 10)
        & (nbbo_spreads["timestamp"].minute() < 0)
    )
    .group_by("symbol")
    .aggregate(avg_opening_spread=nbbo_spreads["quoted_spread_dollar"].mean())
)

# Closing spreads (3:30-4:00 PM)
closing = (
    nbbo_spreads.filter(
        (nbbo_spreads["timestamp"].hour() == 15)
        & (nbbo_spreads["timestamp"].minute() >= 30)
        | (nbbo_spreads["timestamp"].hour() == 16)
        & (nbbo_spreads["timestamp"].minute() == 0)
    )
    .group_by("symbol")
    .aggregate(avg_closing_spread=nbbo_spreads["quoted_spread_dollar"].mean())
)

# Combine
open_close = opening.join(closing, "symbol")
print(open_close.execute())
```

## NBBO Update Frequency

### Analyzing Quote Updates

```python
# Compute time between NBBO updates
nbbo_updates = nbbo.mutate(
    prev_timestamp=nbbo["timestamp"]
    .lag()
    .over(ibis.window(group_by="symbol", order_by="timestamp"))
).mutate(time_delta=(nbbo["timestamp"] - nbbo["prev_timestamp"]).total_seconds())

# Summary statistics
update_stats = nbbo_updates.group_by("symbol").aggregate(
    avg_time_between_updates=nbbo_updates["time_delta"].mean(),
    median_time=nbbo_updates["time_delta"].approx_median(),
    updates_per_second=1.0 / nbbo_updates["time_delta"].mean(),
)

print(update_stats.execute())
```

## Best Execution Analysis

### Complete Best Execution Report

```python
from pytaq.metrics.effective_spreads import compute_effective_spread
from pytaq.metrics.signs import sign_lr

# 1. Get NBBO spreads
nbbo_spreads = compute_spreads(clean_nbbo)

# 2. Get trades with NBBO
trades_nbbo = trades.join(nbbo_spreads, ["symbol", "timestamp"], how="left")

# 3. Classify trades
signed_trades = trades_nbbo.mutate(
    trade_sign=sign_lr(trades_nbbo["price"], trades_nbbo["midpoint"])
)

# 4. Compute effective spreads
effective = compute_effective_spread(
    table=signed_trades,
    price_col="price",
    midpoint_col="midpoint",
    sign_col="trade_sign",
)

# 5. Best execution metrics
execution_report = effective.group_by("symbol").aggregate(
    # Spread metrics
    avg_nbbo_spread=effective["quoted_spread_dollar"].mean(),
    avg_eff_spread=effective["eff_spread_dollar"].mean(),
    # Execution quality
    pct_at_nbbo=(
        (effective["price"] == effective["best_bid"])
        | (effective["price"] == effective["best_ask"])
    ).sum()
    / effective["symbol"].count(),
    pct_inside_nbbo=(
        (effective["price"] > effective["best_bid"])
        & (effective["price"] < effective["best_ask"])
    ).sum()
    / effective["symbol"].count(),
    # Volume metrics
    total_volume=effective["volume"].sum(),
    num_trades=effective["symbol"].count(),
)

print(execution_report.execute())
```

## Common Workflows

### Daily NBBO Summary

```python
def daily_nbbo_summary(con, path, date_val, symbols):
    """Generate comprehensive daily NBBO summary."""
    # Extract and clean
    nbbo = extract_nbbo(con, path, date_val, symbols)
    clean = clean_nbbo_table(nbbo, max_spread=Decimal("10.0"))

    # Compute spreads and quality
    spreads = compute_spreads(clean)
    quality = compute_locks_crosses(clean)

    # Daily aggregates
    summary = (
        spreads.join(quality, ["symbol", "timestamp"])
        .group_by("symbol")
        .aggregate(
            # Spread metrics
            avg_spread_dollar=spreads["quoted_spread_dollar"].mean(),
            avg_spread_bps=spreads["quoted_spread_bps"].mean(),
            min_spread=spreads["quoted_spread_dollar"].min(),
            max_spread=spreads["quoted_spread_dollar"].max(),
            # Quality metrics
            pct_locked=(quality["is_locked"] == True).sum() / quality["symbol"].count(),
            pct_crossed=(quality["is_crossed"] == True).sum()
            / quality["symbol"].count(),
            # Update metrics
            num_updates=spreads["symbol"].count(),
        )
    )

    return summary.execute()


# Use it
summary = daily_nbbo_summary(con, "/path/to/data", date(2023, 1, 15), ["AAPL", "MSFT"])
print(summary)
```

## Next Steps

- Review [extraction guide](extraction.md) for loading NBBO data
- Learn about [metrics computation](metrics.md) for advanced analysis
- Explore [API documentation](../api/extract.md) for NBBO-specific functions
