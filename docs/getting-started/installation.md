# Installation

This guide will help you install PyTAQ and its dependencies.

## Requirements

- Python 3.9 or higher
- `uv` package manager (recommended) or `pip`

## Using uv (Recommended)

PyTAQ uses [uv](https://github.com/astral-sh/uv) for fast, reliable dependency management.

### Install uv

```bash
# On macOS and Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# On Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Clone and Install PyTAQ

```bash
# Clone the repository
git clone https://github.com/vincentgregoire/pytaq.git
cd pytaq

# Install dependencies
uv sync

# Activate the virtual environment
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate  # On Windows
```

## Using pip

If you prefer using pip:

```bash
# Clone the repository
git clone https://github.com/vincentgregoire/pytaq.git
cd pytaq

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Unix/macOS

# Install the package in editable mode
pip install -e .
```

## Development Installation

For development work, install the development dependencies:

```bash
# With uv
uv sync --group dev

# With pip
pip install -e ".[dev]"
```

This includes:

- `pytest` and `pytest-cov` for testing
- `ruff` for linting and formatting
- `jupyter` for interactive analysis
- `mkdocs` and `mkdocs-material` for documentation

## Backend Support

PyTAQ uses Ibis for data manipulation. Install additional backends as needed:

### DuckDB (Default)

DuckDB support is included by default:

```bash
# Already included in base installation
```

### PostgreSQL

For PostgreSQL support:

```bash
uv add ibis-framework[postgres]
# or with pip
pip install ibis-framework[postgres]
```

### Polars

For in-memory processing with Polars:

```bash
uv add ibis-framework[polars]
# or with pip
pip install ibis-framework[polars]
```

## Verify Installation

Test your installation:

```python
import pytaq
import ibis

# Create a DuckDB connection
con = ibis.connect("duckdb://:memory:")

# Verify imports work
from pytaq.cleaning import clean_quote_table
from pytaq.metrics import compute_effective_spreads

print("PyTAQ installed successfully!")
```

## Next Steps

- Follow the [Quick Start](quickstart.md) guide to process your first TAQ dataset
- Learn about [Configuration](configuration.md) options
- Explore the [User Guide](../user-guide/extraction.md) for detailed workflows
