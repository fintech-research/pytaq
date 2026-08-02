"""Read TAQ data from local files.

The local counterpart of :mod:`pytaq.wrds`. Where that module opens a postgres
connection to the WRDS server, this one opens a DuckDB backend over files on
disk, and both hand back tables the cleaning functions accept unchanged.

Expected layout: one file per date per data type, named after the WRDS table it
came from, all in a single directory.

    data/
        ctm_20200102.parquet            trades
        cqm_20200102.parquet            quotes
        nbbom_20200102.parquet          NBBO
        complete_nbbo_20200102.parquet  official complete NBBO

Column names may be upper or lower case; the cleaning functions normalise them
either way.

Note on backends: use DuckDB. Ibis 12's polars backend implements no window
functions at all, and much of PyTAQ depends on them, so the polars extra cannot
run the pipeline.
"""

import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import ibis

from .tables import (
    get_nbbo_table_name,
    get_official_complete_nbbo_table_name,
    get_quotes_table_name,
    get_trades_table_name,
)

if TYPE_CHECKING:
    from ibis.backends.duckdb import Backend as DuckDBBackend

__all__ = [
    "connect",
    "get_nbbo",
    "get_official_complete_nbbo",
    "get_quotes",
    "get_table",
    "get_trades",
]

SUPPORTED_EXTENSIONS = ("parquet", "csv", "csv.gz")


def connect(**kwargs) -> "DuckDBBackend":
    """Open an in-memory DuckDB backend for reading local TAQ files.

    Args:
        **kwargs (Any): Passed through to ``ibis.duckdb.connect``.

    Returns:
        DuckDBBackend: Backend to pass to the ``get_*`` functions.
    """
    try:
        import ibis.backends.duckdb
    except ImportError as e:
        raise ImportError(
            "Reading local TAQ files requires the duckdb backend. "
            "Install it with: pip install 'pytaq[duckdb]'"
        ) from e

    return ibis.duckdb.connect(**kwargs)


def _find_file(data_dir: Path, table_name: str) -> Path:
    """Locate the file backing a table, trying each supported extension."""
    for extension in SUPPORTED_EXTENSIONS:
        candidate = data_dir / f"{table_name}.{extension}"
        if candidate.exists():
            return candidate

    tried = ", ".join(f"{table_name}.{ext}" for ext in SUPPORTED_EXTENSIONS)
    raise FileNotFoundError(f"No file for table {table_name!r} in {data_dir}: {tried}")


def get_table(
    con: "DuckDBBackend",
    data_dir: str | Path,
    table_name: str,
    symbols: list[str] | None = None,
) -> ibis.Table:
    """Read one daily TAQ table from a local file.

    Args:
        con (DuckDBBackend): Backend from :func:`connect`
        data_dir (str | Path): Directory holding the TAQ files
        table_name (str): Table name, e.g. ``ctm_20200102``
        symbols (list[str] | None): Restrict to these root symbols, or None for
            all of them

    Returns:
        ibis.Table: The raw table, ready for the cleaning functions

    Raises:
        FileNotFoundError: If no file matches the table name
    """
    path = _find_file(Path(data_dir), table_name)

    t = con.read_parquet(path) if path.name.endswith(".parquet") else con.read_csv(path)

    if symbols is not None:
        # Match the postgres path, which filters on sym_root. Fall back to the
        # uppercase spelling if the file has not been normalised.
        column = "sym_root" if "sym_root" in t.columns else "SYM_ROOT"
        t = t.filter(t[column].isin(symbols))

    return t


def get_trades(
    con: "DuckDBBackend",
    data_dir: str | Path,
    date: datetime.date | datetime.datetime,
    symbols: list[str] | None = None,
) -> ibis.Table:
    """Read the trades table for a date."""
    return get_table(con, data_dir, get_trades_table_name(date), symbols)


def get_quotes(
    con: "DuckDBBackend",
    data_dir: str | Path,
    date: datetime.date | datetime.datetime,
    symbols: list[str] | None = None,
) -> ibis.Table:
    """Read the quotes table for a date."""
    return get_table(con, data_dir, get_quotes_table_name(date), symbols)


def get_nbbo(
    con: "DuckDBBackend",
    data_dir: str | Path,
    date: datetime.date | datetime.datetime,
    symbols: list[str] | None = None,
) -> ibis.Table:
    """Read the NBBO table for a date."""
    return get_table(con, data_dir, get_nbbo_table_name(date), symbols)


def get_official_complete_nbbo(
    con: "DuckDBBackend",
    data_dir: str | Path,
    date: datetime.date | datetime.datetime,
    symbols: list[str] | None = None,
) -> ibis.Table:
    """Read the official complete NBBO table for a date."""
    return get_table(
        con, data_dir, get_official_complete_nbbo_table_name(date), symbols
    )
