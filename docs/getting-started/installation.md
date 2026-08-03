# Installation

PyTAQ requires Python 3.13 or later.

## Pick your extra

The Ibis backends are optional, because which one you need depends on where your data lives. Installing plain `pytaq` gives you the cleaning and metrics code but no way to open data.

```bash
# Local TAQ files
pip install 'pytaq[duckdb]'

# WRDS postgres server, on the WRDS cloud or from your own machine
pip install 'pytaq[postgres]'

# Everything
pip install 'pytaq[all]'
```

With `uv`:

```bash
uv add 'pytaq[duckdb]'
```

Importing `pytaq` always works, whichever extra you chose. Only connecting needs a backend, and if the right one is missing the error says which extra to install.

## Why `polars` is not the local default

There is a `polars` extra, but do not reach for it first. Ibis 12's polars backend implements no window functions, so it cannot run the parts of PyTAQ that need them: trade signing, quote in-force times, NBBO change filtering, or the quotes-to-NBBO merge. Use `duckdb` for local work.

## Development install

```bash
git clone https://github.com/fintech-research/pytaq.git
cd pytaq
uv sync
uv run pre-commit install
```

`uv sync` installs every backend plus the development tools. See [Development setup](../contributing/development.md).
