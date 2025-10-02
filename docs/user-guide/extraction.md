# Data Extraction

This guide covers extracting TAQ (Trade and Quote) data from various sources into Ibis tables.

## Overview

The extraction module provides functions to load raw TAQ data from:

- Parquet files (local or cloud storage)
- PostgreSQL databases
- CSV files
- WRDS (Wharton Research Data Services)

All extraction functions return Ibis `Table` objects for cross-platform data manipulation.

## Basic Extraction

### Loading Quote Data

```python
import ibis
from pytaq.extract.quotes import extract_quotes
from datetime import date

# Connect to DuckDB backend
con = ibis.duckdb.connect()

# Extract quotes for a specific date
quotes = extract_quotes(
    con=con,
    source_path="/path/to/taq/data",
    date=date(2023, 1, 15),
    symbols=["AAPL", "MSFT"]
)

# View the data
print(quotes.head().execute())
```

### Loading Trade Data

```python
from pytaq.extract.trades import extract_trades

# Extract trades
trades = extract_trades(
    con=con,
    source_path="/path/to/taq/data",
    date=date(2023, 1, 15),
    symbols=["AAPL", "MSFT"]
)
```

### Loading NBBO Data

```python
from pytaq.extract.nbbo import extract_nbbo

# Extract National Best Bid and Offer
nbbo = extract_nbbo(
    con=con,
    source_path="/path/to/taq/data",
    date=date(2023, 1, 15),
    symbols=["AAPL", "MSFT"]
)
```

### Loading Official NBBO

```python
from pytaq.extract.official_nbbo import extract_official_nbbo

# Extract official NBBO from regulatory feed
official_nbbo = extract_official_nbbo(
    con=con,
    source_path="/path/to/taq/data",
    date=date(2023, 1, 15),
    symbols=["AAPL", "MSFT"]
)
```

## Symbol Handling

### Single Symbol

```python
# Extract data for a single symbol
aapl_quotes = extract_quotes(
    con=con,
    source_path="/path/to/data",
    date=date(2023, 1, 15),
    symbols="AAPL"  # Single symbol as string
)
```

### Multiple Symbols

```python
# Extract data for multiple symbols
quotes = extract_quotes(
    con=con,
    source_path="/path/to/data",
    date=date(2023, 1, 15),
    symbols=["AAPL", "MSFT", "GOOGL"]  # List of symbols
)
```

### Symbol Suffixes

TAQ data includes symbols with suffixes (e.g., BRK A for Berkshire Hathaway Class A):

```python
# Handle symbols with suffixes
quotes = extract_quotes(
    con=con,
    source_path="/path/to/data",
    date=date(2023, 1, 15),
    symbols=["BRK A", "BRK B"]  # Space-separated suffix
)
```

## Date Handling

### Single Date

```python
# Extract for a specific date
quotes = extract_quotes(
    con=con,
    source_path="/path/to/data",
    date=date(2023, 1, 15)
)
```

### Date Ranges

```python
from datetime import timedelta

# Extract for multiple dates
start_date = date(2023, 1, 15)
end_date = date(2023, 1, 20)

all_quotes = []
current_date = start_date

while current_date <= end_date:
    daily_quotes = extract_quotes(
        con=con,
        source_path="/path/to/data",
        date=current_date,
        symbols=["AAPL"]
    )
    all_quotes.append(daily_quotes)
    current_date += timedelta(days=1)

# Combine all dates
combined_quotes = ibis.union(*all_quotes)
```

## Data Sources

### Parquet Files

PyTAQ works efficiently with Parquet files:

```python
# Read from local Parquet files
quotes = extract_quotes(
    con=con,
    source_path="/data/taq/parquet",
    date=date(2023, 1, 15)
)

# Read from S3 or cloud storage
quotes = extract_quotes(
    con=con,
    source_path="s3://bucket/taq/data",
    date=date(2023, 1, 15)
)
```

### PostgreSQL Database

Extract data from PostgreSQL:

```python
from pytaq.extract.postgresql import load_from_postgres
import ibis

# Connect to PostgreSQL
con = ibis.postgres.connect(
    host="localhost",
    database="taq",
    user="username",
    password="password"
)

# Load quotes from database
quotes = load_from_postgres(
    con=con,
    table_name="quotes",
    date=date(2023, 1, 15),
    symbols=["AAPL", "MSFT"]
)
```

## Time Filtering

### Merging Date and Time

TAQ data often stores dates and times separately. PyTAQ provides utilities to merge them:

```python
from pytaq.extract.common import merge_date_time

# Merge separate date and time columns
quotes_with_timestamp = merge_date_time(
    table=quotes,
    date_col="date",
    time_col="time_m",
    timestamp_col="timestamp"  # New column name
)
```

### Filtering by Time Range

```python
from datetime import time
from pytaq.metrics.timestamps import filter_timestamp

# Filter to regular trading hours (9:30 AM - 4:00 PM)
regular_hours = filter_timestamp(
    table=quotes,
    timestamp="timestamp",
    start_time=time(9, 30),
    end_time=time(16, 0)
)
```

## Working with Ibis Tables

All extraction functions return Ibis `Table` objects:

```python
# View table schema
print(quotes.schema())

# Select specific columns
selected = quotes.select(["symbol", "timestamp", "bid", "ask"])

# Filter rows
filtered = quotes.filter(quotes["bid"] > 100)

# Execute and convert to pandas
df = quotes.execute()

# Execute and convert to polars
pl_df = quotes.to_polars()

# Execute and convert to PyArrow
arrow_table = quotes.to_pyarrow()
```

## Performance Tips

### 1. Use Appropriate Backend

```python
# DuckDB for analytics and large datasets
con = ibis.duckdb.connect()

# Polars for in-memory processing
con = ibis.polars.connect()

# PostgreSQL for persistent storage
con = ibis.postgres.connect(...)
```

### 2. Filter Early

```python
# Filter at extraction time
quotes = extract_quotes(
    con=con,
    source_path="/path/to/data",
    date=date(2023, 1, 15),
    symbols=["AAPL"]  # Only load needed symbols
)

# Apply additional filters before execution
filtered = quotes.filter(
    (quotes["bid"] > 0) & (quotes["ask"] > 0)
)
```

### 3. Select Only Needed Columns

```python
# Select minimal columns
minimal = quotes.select([
    "symbol",
    "timestamp",
    "bid",
    "ask"
])
```

### 4. Use Lazy Evaluation

```python
# Build the query pipeline without executing
quotes = extract_quotes(con, "/path/to/data", date(2023, 1, 15))
filtered = quotes.filter(quotes["bid"] > 100)
selected = filtered.select(["symbol", "bid", "ask"])

# Execute only when needed
result = selected.execute()
```

## Common Patterns

### Extract and Clean Pipeline

```python
from pytaq.extract.quotes import extract_quotes
from pytaq.cleaning.quotes import clean_quote_table

# Extract raw quotes
raw_quotes = extract_quotes(
    con=con,
    source_path="/path/to/data",
    date=date(2023, 1, 15),
    symbols=["AAPL"]
)

# Clean the quotes
clean_quotes = clean_quote_table(
    table=raw_quotes,
    keep_qu_cond=["A", "B"],  # Keep only valid conditions
    max_spread=5.0
)
```

### Combining Trades and Quotes

```python
from pytaq.extract.trades import extract_trades
from pytaq.extract.quotes import extract_quotes

# Extract both
trades = extract_trades(con, "/path/to/data", date(2023, 1, 15))
quotes = extract_quotes(con, "/path/to/data", date(2023, 1, 15))

# Join on symbol and timestamp
merged = trades.join(
    quotes,
    predicates=[
        trades["symbol"] == quotes["symbol"],
        trades["timestamp"] == quotes["timestamp"]
    ],
    how="left"
)
```

## Next Steps

- Learn about [data cleaning](cleaning.md) to prepare extracted data
- Explore [computing metrics](metrics.md) from clean data
- Understand [NBBO workflows](nbbo.md) for market quality analysis
