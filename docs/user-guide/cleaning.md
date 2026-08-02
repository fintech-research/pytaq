# Data Cleaning

This guide covers cleaning and standardizing TAQ data to prepare it for analysis.

## Overview

The cleaning module provides functions to:

- Remove invalid or erroneous records
- Filter by quote conditions and trade conditions
- Apply spread constraints
- Standardize data formats
- Handle symbol suffixes

All cleaning functions accept and return Ibis `Table` objects.

## Quote Cleaning

### Basic Quote Cleaning

```python
from pytaq.cleaning.quotes import clean_quote_table
from pytaq.extract.quotes import extract_quotes
from decimal import Decimal

# Extract raw quotes
raw_quotes = extract_quotes(con, "/path/to/data", date(2023, 1, 15), ["AAPL"])

# Clean the quotes
clean_quotes = clean_quote_table(
    table=raw_quotes,
    keep_qu_cond=["A", "B"],  # Valid quote conditions
    max_spread=Decimal("5.0"),  # Maximum allowed spread
)

# Execute to view results
print(clean_quotes.execute())
```

### Quote Condition Filtering

TAQ quote condition codes indicate quote quality:

```python
# Keep only regular quotes (condition A)
regular_quotes = clean_quote_table(table=raw_quotes, keep_qu_cond=["A"])

# Keep multiple valid conditions
valid_quotes = clean_quote_table(
    table=raw_quotes,
    keep_qu_cond=["A", "B", "H"],  # Regular, auto-exec, fast trading
)

# Keep all quotes (no filtering)
all_quotes = clean_quote_table(table=raw_quotes, keep_qu_cond=None)
```

Common quote conditions:
- `A`: Regular quote
- `B`: Auto-execution
- `H`: Fast trading
- `R`: Regular two-sided quote
- `T`: Slow quote on offer side

### Spread Filtering

Filter out quotes with unreasonable spreads:

```python
from decimal import Decimal

# Tight constraint for liquid stocks
tight_filter = clean_quote_table(
    table=raw_quotes,
    max_spread=Decimal("1.0"),  # $1 maximum spread
)

# Relaxed constraint for less liquid stocks
relaxed_filter = clean_quote_table(table=raw_quotes, max_spread=Decimal("10.0"))

# Special handling for high-priced stocks (e.g., BRK A)
high_price = clean_quote_table(table=raw_quotes, max_spread=Decimal("200.0"))

# No spread filtering
no_filter = clean_quote_table(table=raw_quotes, max_spread=None)
```

### Symbol Suffix Handling

Clean quotes while preserving symbol suffixes:

```python
# Data with suffixes (e.g., "BRK A")
quotes_with_suffix = extract_quotes(
    con, "/path/to/data", date(2023, 1, 15), ["BRK A", "BRK B"]
)

# Clean while keeping suffix information
clean_with_suffix = clean_quote_table(
    table=quotes_with_suffix,
    keep_qu_cond=["A"],
    max_spread=Decimal("200.0"),  # Higher threshold for BRK A
)
```

## Trade Cleaning

### Basic Trade Cleaning

```python
from pytaq.cleaning.trades import clean_trade_table
from pytaq.extract.trades import extract_trades

# Extract raw trades
raw_trades = extract_trades(con, "/path/to/data", date(2023, 1, 15), ["AAPL"])

# Clean the trades
clean_trades = clean_trade_table(
    table=raw_trades,
    keep_tr_scond=["@", "F"],  # Valid sale conditions
    remove_abnormal_sales=True,
)
```

### Trade Sale Condition Filtering

Filter trades by sale condition codes:

```python
# Keep only regular trades
regular_trades = clean_trade_table(
    table=raw_trades,
    keep_tr_scond=["@"],  # Regular sale
)

# Keep multiple valid conditions
valid_trades = clean_trade_table(
    table=raw_trades,
    keep_tr_scond=["@", "F", "*"],  # Regular, intermarket sweep, odd lot
)

# Keep all trades
all_trades = clean_trade_table(table=raw_trades, keep_tr_scond=None)
```

Common sale conditions:
- `@`: Regular sale
- `F`: Intermarket sweep order
- `*`: Odd lot trade
- `B`: Average price trade
- `W`: Weighted average price

### Removing Abnormal Sales

Filter out special trade types:

```python
# Remove abnormal sales (default: True)
normal_trades = clean_trade_table(table=raw_trades, remove_abnormal_sales=True)

# Keep all sales including abnormal
all_sales = clean_trade_table(table=raw_trades, remove_abnormal_sales=False)
```

Abnormal sales include:
- Opening prints
- Closing prints
- Bunched trades
- Prior reference price trades

### Price Filtering

Remove trades with invalid prices:

```python
# Remove zero and negative prices (automatic in cleaning)
valid_prices = clean_trade_table(table=raw_trades)

# Manual price filtering with Ibis
filtered_trades = raw_trades.filter(
    (raw_trades["price"] > 0) & (raw_trades["price"] < 1000000)
)
```

## NBBO Cleaning

### Basic NBBO Cleaning

```python
from pytaq.cleaning.nbbo import clean_nbbo_table
from pytaq.extract.nbbo import extract_nbbo

# Extract raw NBBO
raw_nbbo = extract_nbbo(con, "/path/to/data", date(2023, 1, 15), ["AAPL"])

# Clean the NBBO
clean_nbbo = clean_nbbo_table(table=raw_nbbo, max_spread=Decimal("5.0"))
```

### Locked and Crossed Markets

NBBO cleaning handles locked markets (bid = ask) and crossed markets (bid > ask):

```python
# Remove locked and crossed markets
valid_nbbo = clean_nbbo_table(
    table=raw_nbbo,
    max_spread=Decimal("5.0"),
    remove_crossed=True,  # Default
)

# Keep locked markets, remove crossed
keep_locked = clean_nbbo_table(table=raw_nbbo, remove_locked=False, remove_crossed=True)
```

## Combined Cleaning Pipeline

### Extract, Clean, and Merge

```python
from pytaq.extract.quotes import extract_quotes
from pytaq.extract.trades import extract_trades
from pytaq.cleaning.quotes import clean_quote_table
from pytaq.cleaning.trades import clean_trade_table
from decimal import Decimal
from datetime import date

# Extract data
date_val = date(2023, 1, 15)
symbols = ["AAPL", "MSFT"]

raw_quotes = extract_quotes(con, "/path/to/data", date_val, symbols)
raw_trades = extract_trades(con, "/path/to/data", date_val, symbols)

# Clean data
clean_quotes = clean_quote_table(
    table=raw_quotes, keep_qu_cond=["A", "B"], max_spread=Decimal("5.0")
)

clean_trades = clean_trade_table(
    table=raw_trades, keep_tr_scond=["@", "F"], remove_abnormal_sales=True
)

# Execute and view
print(f"Clean quotes: {clean_quotes.count().execute()} records")
print(f"Clean trades: {clean_trades.count().execute()} records")
```

### Time-of-Day Filtering

Combine cleaning with time filtering:

```python
from datetime import time

# Clean and filter to regular trading hours
clean_quotes = clean_quote_table(raw_quotes, keep_qu_cond=["A"])

# Filter to 9:30 AM - 4:00 PM ET
regular_hours = clean_quotes.filter(
    (clean_quotes["time_m"] >= time(9, 30)) & (clean_quotes["time_m"] <= time(16, 0))
)
```

## Quality Checks

### Pre-Cleaning Statistics

```python
# Count records before cleaning
raw_count = raw_quotes.count().execute()
print(f"Raw quotes: {raw_count}")

# Check spread distribution
spreads = raw_quotes.mutate(spread=raw_quotes["ask"] - raw_quotes["bid"])
spread_stats = spreads.select("spread").execute().describe()
print(spread_stats)

# Check quote conditions
conditions = raw_quotes.group_by("qu_cond").count().execute()
print(conditions)
```

### Post-Cleaning Validation

```python
# Count records after cleaning
clean_count = clean_quotes.count().execute()
print(f"Clean quotes: {clean_count}")
print(
    f"Removed: {raw_count - clean_count} ({100 * (1 - clean_count / raw_count):.1f}%)"
)

# Verify no invalid spreads
max_spread_check = (
    clean_quotes.mutate(spread=clean_quotes["ask"] - clean_quotes["bid"])
    .select("spread")
    .execute()["spread"]
    .max()
)
print(f"Maximum spread: ${max_spread_check:.2f}")

# Verify only valid conditions
valid_conditions = clean_quotes.select("qu_cond").distinct().execute()
print(f"Remaining conditions: {list(valid_conditions['qu_cond'])}")
```

## Symbol-Specific Cleaning

Different symbols may need different parameters:

```python
from decimal import Decimal


def clean_by_symbol(raw_quotes, symbol):
    """Apply symbol-specific cleaning rules."""
    # Filter to specific symbol
    symbol_quotes = raw_quotes.filter(raw_quotes["symbol"] == symbol)

    # Symbol-specific parameters
    if symbol == "BRK A":
        # High-priced stock needs higher spread threshold
        max_spread = Decimal("200.0")
    elif symbol in ["AAPL", "MSFT", "GOOGL"]:
        # Liquid stocks with tight spreads
        max_spread = Decimal("1.0")
    else:
        # Default threshold
        max_spread = Decimal("5.0")

    return clean_quote_table(
        table=symbol_quotes, keep_qu_cond=["A"], max_spread=max_spread
    )


# Apply to multiple symbols
symbols = ["AAPL", "BRK A", "XYZ"]
cleaned_tables = [clean_by_symbol(raw_quotes, sym) for sym in symbols]

# Combine results
all_clean = ibis.union(*cleaned_tables)
```

## Common Issues

### Issue 1: Too Aggressive Filtering

```python
# Problem: Removed too many records
clean_quotes = clean_quote_table(
    table=raw_quotes,
    keep_qu_cond=["A"],  # Too restrictive
    max_spread=Decimal("0.50"),  # Too tight
)
# Result: Very few records remain

# Solution: Relax constraints
clean_quotes = clean_quote_table(
    table=raw_quotes,
    keep_qu_cond=["A", "B", "H"],  # More conditions
    max_spread=Decimal("5.0"),  # Wider spread
)
```

### Issue 2: Symbol Suffix Mismatch

```python
# Problem: Symbol with suffix not found
raw_quotes = extract_quotes(con, "/path/to/data", date(2023, 1, 15), ["BRK A"])
# If data uses "BRK" and "A" in separate columns

# Solution: Check schema and handle suffixes
print(raw_quotes.schema())  # Check column names
# Use symbol + suffix columns appropriately
```

### Issue 3: Decimal Precision

```python
from decimal import Decimal

# Problem: Float precision issues
clean_quotes = clean_quote_table(
    table=raw_quotes,
    max_spread=5.0,  # Float
)

# Solution: Use Decimal for exact precision
clean_quotes = clean_quote_table(
    table=raw_quotes,
    max_spread=Decimal("5.0"),  # Exact decimal
)
```

## Next Steps

- Learn about [computing metrics](metrics.md) from cleaned data
- Explore [NBBO workflows](nbbo.md) for market quality analysis
- Review [API documentation](../api/cleaning.md) for detailed function references
