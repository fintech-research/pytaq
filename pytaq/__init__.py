"""PyTAQ: process NYSE TAQ trade and quote data with Ibis.

There are three ways to get at the data, and they differ only in how the raw
tables are opened. Everything downstream is shared.

1. On the WRDS cloud, or locally against the WRDS postgres server, via
   :mod:`pytaq.wrds` (needs the ``postgres`` extra).
2. Against local copies of the TAQ files, via :mod:`pytaq.local` (needs the
   ``duckdb`` extra).

A typical session::

    import datetime
    from pytaq import clean_trades, local

    con = local.connect()
    raw = local.get_trades(con, "data/", datetime.date(2020, 1, 2))
    trades = clean_trades(raw)

Use the DuckDB backend for local work. Ibis 12's polars backend implements no
window functions, and much of PyTAQ depends on them.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("pytaq")
except PackageNotFoundError:  # pragma: no cover - only when running from source
    __version__ = "0.0.0+unknown"

from . import cleaning, hj_defaults, local, metrics, tables, utils, wrds
from .cleaning import (
    clean_nbbo,
    clean_official_complete_nbbo,
    clean_quote_table,
    clean_trades,
    merge_quotes_nbbo,
    merge_trades_official_nbbo,
)
from .metrics import (
    compute_effective_spreads,
    compute_quote_inforce,
    compute_rs_and_pi,
    compute_spreads,
    compute_weighted_averages,
    sign_trades,
)
from .tables import (
    get_nbbo_table_name,
    get_official_complete_nbbo_table_name,
    get_quotes_table_name,
    get_trades_table_name,
)

__all__ = [
    "__version__",
    "clean_nbbo",
    "clean_official_complete_nbbo",
    "clean_quote_table",
    "clean_trades",
    "cleaning",
    "compute_effective_spreads",
    "compute_quote_inforce",
    "compute_rs_and_pi",
    "compute_spreads",
    "compute_weighted_averages",
    "get_nbbo_table_name",
    "get_official_complete_nbbo_table_name",
    "get_quotes_table_name",
    "get_trades_table_name",
    "hj_defaults",
    "local",
    "merge_quotes_nbbo",
    "merge_trades_official_nbbo",
    "metrics",
    "sign_trades",
    "tables",
    "utils",
    "wrds",
]
