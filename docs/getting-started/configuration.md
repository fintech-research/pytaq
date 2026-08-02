# Configuration

PyTAQ provides various configuration options for customizing behavior.

## Default Settings

PyTAQ includes sensible defaults from the Holden-Jacobsen (HJ) paper:

```python
from pytaq.hj_defaults import (
    HJ_MAX_SPREAD,  # Maximum allowed spread: $5.00
    HJ_START_TIME_QUOTES,  # Quote start time: 09:30:00
    HJ_END_TIME_QUOTES,  # Quote end time: 16:00:00
    HJ_START_TIME_TRADES,  # Trade start time: 09:30:00
    HJ_END_TIME_TRADES,  # Trade end time: 16:00:00
)
```

## Backend Configuration

### DuckDB

Default backend for local processing:

```python
import ibis

# In-memory database
con = ibis.connect("duckdb://:memory:")

# Persistent database
con = ibis.connect("duckdb://path/to/taq.db")

# With configuration options
con = ibis.connect(
    "duckdb://taq.db", read_only=False, config={"threads": 4, "memory_limit": "4GB"}
)
```

### PostgreSQL

For production deployments:

```python
import ibis

con = ibis.connect("postgresql://user:password@localhost:5432/taq_database")

# With connection pooling
con = ibis.connect(
    "postgresql://user:password@localhost:5432/taq_database", pool_size=10
)
```

### Polars

For in-memory processing:

```python
import ibis

con = ibis.connect("polars://")
```

## Data Cleaning Configuration

### Quote Cleaning

```python
from pytaq.cleaning import clean_quote_table
from decimal import Decimal

clean_quotes = clean_quote_table(
    quotes,
    # Quote condition filters
    keep_qu_cond=["A", "B", "H", "O", "R", "W"],
    # Remove cancelled quotes
    filter_cancelled=True,
    # Remove locked/crossed markets
    filter_crossed=True,
    # Maximum spread filter
    max_spread=Decimal("5.0"),
    # Keep only NBBO quotes
    nbbo_only=True,
)
```

### Trade Cleaning

```python
from pytaq.cleaning import clean_trades
from datetime import time

clean_trades_data = clean_trades(
    trades,
    # Exclude trade corrections
    exclude_corrections=True,
    # Filter for positive prices only
    price_positive_only=True,
    # Time range filters
    start_time=time(9, 30, 0),
    end_time=time(16, 0, 0),
)
```

## Metric Configuration

### Trade Signs

```python
from pytaq.metrics import sign_clnv

# Configure CLNV threshold
sign = sign_clnv(
    price=trades.price,
    best_bid=trades.best_bid,
    best_ask=trades.best_ask,
    tick_dir=trades.tick_direction,
    lock_cross=trades.locked,
    threshold=0.3,  # Default threshold
)
```

## Environment Variables

PyTAQ respects standard environment variables:

```bash
# Database connection
export DATABASE_URL="postgresql://user:pass@localhost/taq"

# Python path
export PYTHONPATH="${PYTHONPATH}:/path/to/pytaq"
```

## Performance Tuning

### Batch Processing

```python
# Process by date
for date in date_range:
    daily_data = quotes.filter(quotes.date == date)
    process_data(daily_data)

# Process by symbol
for symbol in symbols:
    symbol_data = quotes.filter(quotes.symbol == symbol)
    process_data(symbol_data)
```

### Memory Management

```python
# Use lazy evaluation
result = (
    table.filter(...)  # Applied on database
    .mutate(...)  # Applied on database
    .execute()  # Only now data is materialized
)

# For large results, iterate in chunks
for chunk in table.to_pandas(iterator=True, chunksize=10000):
    process_chunk(chunk)
```

## Logging

```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("pytaq")
logger.setLevel(logging.DEBUG)
```

## Next Steps

- See [Quick Start](quickstart.md) for examples
- Check [User Guide](../user-guide/extraction.md) for workflows
- Read [API Reference](../api/extract.md) for all options
