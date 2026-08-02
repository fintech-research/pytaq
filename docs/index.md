# PyTAQ Documentation

Welcome to the PyTAQ documentation! PyTAQ is a Python module for processing NYSE TAQ (Trade and Quote) data using the Ibis framework for cross-platform data manipulation.

## Overview

PyTAQ provides a comprehensive toolkit for:

- **Extracting** TAQ data from various sources (PostgreSQL, DuckDB, CSV files)
- **Cleaning** and standardizing trade and quote data
- **Computing** financial metrics such as spreads, liquidity measures, and trade classifications
- **Cross-platform processing** using Ibis for compatibility with multiple database backends

## Key Features

- ✨ **Ibis-based**: Leverages Ibis for portable, database-agnostic data operations
- 🧹 **Data Cleaning**: Built-in filters for withdrawn quotes, locked/crossed markets, and abnormal spreads
- 📊 **Rich Metrics**: Compute effective spreads, realized spreads, price impact, and more
- 🏷️ **Trade Classification**: Multiple algorithms including Lee-Ready, EMO, CLNV, and BJZ
- 🧪 **Well-Tested**: 75%+ code coverage with comprehensive test suite
- 🚀 **Performance**: Optimized for large-scale TAQ data processing

## Quick Example

```python
import ibis
from pytaq.cleaning import clean_quote_table, clean_trades
from pytaq.metrics import compute_effective_spreads

# Connect to your data source
con = ibis.connect("duckdb://taq.db")

# Load and clean quotes
quotes = con.table("quotes")
clean_quotes = clean_quote_table(quotes)

# Load and clean trades
trades = con.table("trades")
clean_trades_data = clean_trades(trades)

# Compute effective spreads
spreads = compute_effective_spreads(
    clean_trades_data, timestamp_col="timestamp", price_col="price"
)

# Execute and get results
results = spreads.execute()
```

## Project Status

PyTAQ is currently undergoing a refactoring from pandas to Ibis (branch: `ibis`) to improve:

- Cross-platform compatibility
- Performance with large datasets
- Integration with modern data warehouses

## Getting Started

Ready to dive in? Check out the [Installation Guide](getting-started/installation.md) to get started, or jump right into the [Quick Start](getting-started/quickstart.md) tutorial.

## Support

- 📖 Browse the [API Reference](api/cleaning.md) for detailed function documentation
- 💡 Check the [User Guide](user-guide/extraction.md) for common workflows
- 🐛 Report issues on [GitHub](https://github.com/vincentgregoire/pytaq/issues)
- 🤝 See [Contributing](contributing/development.md) to help improve PyTAQ

## License

PyTAQ is released under the MIT License. See the [License](about/license.md) page for details.
