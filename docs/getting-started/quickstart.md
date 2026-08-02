# Quick Start

This guide will walk you through a basic workflow for processing TAQ data with PyTAQ.

## Basic Workflow

The typical PyTAQ workflow consists of three main steps:

1. **Extract**: Load data from your source
2. **Clean**: Filter and standardize the data
3. **Compute**: Calculate metrics and statistics

## Example: Processing Quote Data

### Step 1: Connect to Data

```python
import ibis
from datetime import datetime, time

# Connect to your database
con = ibis.connect("duckdb://path/to/taq.db")

# Or use an in-memory database for testing
con = ibis.connect("duckdb://:memory:")
```

### Step 2: Load Raw Data

```python
# Load quotes table
quotes = con.table("quotes")

# Preview the data
print(quotes.head().execute())
```

### Step 3: Clean the Data

```python
from pytaq.cleaning import clean_quote_table

# Clean quotes with default filters
clean_quotes = clean_quote_table(
    quotes,
    keep_qu_cond=["A", "B", "H", "O", "R", "W"],  # Valid quote conditions
    filter_cancelled=True,  # Remove cancelled quotes
    filter_crossed=True,  # Remove crossed markets
    max_spread=5.0,  # Remove quotes with spread > $5
    nbbo_only=True,  # Keep only NBBO quotes
)

# Execute and view results
result = clean_quotes.execute()
print(f"Original rows: {quotes.count().execute()}")
print(f"After cleaning: {result.shape[0]}")
```

### Step 4: Compute Metrics

```python
from pytaq.metrics import compute_effective_spreads

# Compute effective spreads
spreads = compute_effective_spreads(
    clean_quotes,
    timestamp_col="timestamp",
    price_col="price",
    best_ask_col="best_ask",
    best_bid_col="best_bid",
    filter_locks_crosses=True,
)

# View results
results = spreads.execute()
print(results[["symbol", "eff_spread_dollar", "eff_spread_percent"]].head())
```

## Example: Trade Classification

PyTAQ supports multiple trade classification algorithms:

```python
from pytaq.metrics import sign_bjz, sign_lr, sign_emo, sign_clnv

# Load your trades
trades = con.table("trades")

# BJZ retail classification (for off-exchange trades)
trades = trades.mutate(bjz_sign=sign_bjz(trades.price, trades.ex))

# Lee-Ready classification
trades = trades.mutate(
    midpoint=(trades.best_bid + trades.best_ask) / 2,
    lock_cross=(trades.best_ask <= trades.best_bid),
)

trades = trades.mutate(
    lr_sign=sign_lr(
        trades.price, trades.midpoint, trades.tick_direction, trades.lock_cross
    )
)

# Execute and view
results = trades.execute()
print(results[["symbol", "price", "bjz_sign", "lr_sign"]].head())
```

## Example: Computing Realized Spreads

```python
from pytaq.metrics import dollar_realized_spread, percent_realized_spread

# Assuming you have trades with next midpoint
trades = trades.mutate(
    rs_dollar=dollar_realized_spread(
        trades.trade_sign, trades.price, trades.midpoint_next
    ),
    rs_percent=percent_realized_spread(
        trades.trade_sign, trades.price, trades.midpoint_next
    ),
)

results = trades.execute()
print(results[["symbol", "price", "rs_dollar", "rs_percent"]].head())
```

## Working with Time Filters

```python
from datetime import time
from pytaq.extract.common import filter_by_time

# Filter to regular trading hours (9:30 AM - 4:00 PM)
filtered = filter_by_time(quotes, start_time=time(9, 30, 0), end_time=time(16, 0, 0))

results = filtered.execute()
```

## Merging Symbol Information

```python
from pytaq.extract.common import merge_symbol

# Merge symbol root and suffix
quotes = merge_symbol(quotes)

# Now you have a 'symbol' column (e.g., "BRK A")
print(quotes.select("symbol").head().execute())
```

## Tips for Large Datasets

1. **Use lazy evaluation**: Ibis expressions are lazy - they don't execute until you call `.execute()`
2. **Filter early**: Apply filters before expensive operations
3. **Use appropriate backends**: DuckDB for local files, PostgreSQL for database storage
4. **Batch processing**: Process data in chunks by date or symbol

```python
# Good: Filter first, then compute
filtered = quotes.filter(quotes.symbol == "AAPL")
result = clean_quote_table(filtered).execute()

# Less efficient: Compute on everything, then filter
result = clean_quote_table(quotes).execute()
result = result[result["symbol"] == "AAPL"]
```

## Next Steps

- Explore the [User Guide](../user-guide/extraction.md) for detailed workflows
- Check the [API Reference](../api/cleaning.md) for complete function documentation
- Learn about [Data Cleaning](../user-guide/cleaning.md) options
- See [Computing Metrics](../user-guide/metrics.md) for all available calculations
