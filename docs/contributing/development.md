# Development Setup

Thank you for considering contributing to PyTAQ! This guide will help you set up your development environment.

## Prerequisites

- Python 3.9 or higher
- `uv` package manager
- Git

## Setting Up Your Environment

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/pytaq.git
cd pytaq

# Add upstream remote
git remote add upstream https://github.com/vincentgregoire/pytaq.git
```

### 2. Install Dependencies

```bash
# Install all dependencies including dev tools
uv sync --group dev

# Activate the virtual environment
source .venv/bin/activate
```

### 3. Verify Installation

```bash
# Run tests to ensure everything works
pytest

# Check code formatting
ruff check

# Run type checking (if configured)
mypy pytaq
```

## Development Workflow

### Creating a Branch

```bash
# Fetch latest changes
git fetch upstream
git checkout ibis
git merge upstream/ibis

# Create a feature branch
git checkout -b feature/your-feature-name
```

### Making Changes

1. **Write your code** following the [Code Style](code-style.md) guidelines
2. **Add tests** for new functionality (see [Testing](testing.md))
3. **Update documentation** if you change APIs or add features
4. **Run tests** to ensure nothing broke

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=pytaq --cov-report=html

# Check specific modules
pytest pytaq/metrics/test_signs.py -v
```

### Code Quality Checks

Before committing, ensure your code passes all checks:

```bash
# Format code with ruff
ruff format

# Check for linting issues
ruff check

# Fix auto-fixable issues
ruff check --fix
```

## Project Structure

```
pytaq/
├── pytaq/                  # Main package
│   ├── extract/           # Data extraction
│   ├── cleaning/          # Data cleaning
│   ├── metrics/           # Metric computation
│   └── utils/             # Utilities
├── tests/                 # Test files (mirrors pytaq/)
├── docs/                  # Documentation
├── pyproject.toml         # Project configuration
└── mkdocs.yml            # Documentation configuration
```

## Key Technologies

- **Ibis**: Portable dataframe library for cross-platform data manipulation
- **DuckDB**: Default backend for testing and local processing
- **pytest**: Testing framework
- **ruff**: Fast Python linter and formatter
- **mkdocs**: Documentation generator

## Common Tasks

### Running Tests

```bash
# All tests
pytest

# Specific module
pytest pytaq/metrics/

# With coverage
pytest --cov=pytaq --cov-report=term-missing

# Verbose output
pytest -v

# Stop on first failure
pytest -x
```

### Building Documentation

```bash
# Serve documentation locally
mkdocs serve

# Build documentation
mkdocs build

# Open in browser
open http://127.0.0.1:8000
```

### Adding Dependencies

```bash
# Add a runtime dependency
uv add package-name

# Add a development dependency
uv add --dev package-name

# Update dependencies
uv sync
```

## Debugging Tips

### Using IPython

```python
# Add to your code for interactive debugging
import IPython

IPython.embed()
```

### Inspecting Ibis Expressions

```python
# View the generated SQL
print(table.compile())

# Execute and inspect results
result = table.execute()
print(result.head())
```

### Testing with Different Backends

```python
# DuckDB (default)
con = ibis.connect("duckdb://:memory:")

# PostgreSQL
con = ibis.connect("postgresql://user:pass@localhost/db")

# Polars
con = ibis.connect("polars://")
```

## Getting Help

- Check existing [issues](https://github.com/vincentgregoire/pytaq/issues)
- Read the [User Guide](../user-guide/extraction.md)
- Ask questions in [Discussions](https://github.com/vincentgregoire/pytaq/discussions)

## Next Steps

- Review the [Testing](testing.md) guide
- Familiarize yourself with the [Code Style](code-style.md)
- Look for [good first issues](https://github.com/vincentgregoire/pytaq/labels/good%20first%20issue)
