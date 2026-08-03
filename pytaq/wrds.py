from sys import platform, version_info
from typing import TYPE_CHECKING, Any

import ibis

from .tables import DEFAULT_DATABASE

if TYPE_CHECKING:
    from ibis.backends.postgres import Backend as PostgresBackend
    from ibis.expr.types import Table

__all__ = ["DEFAULT_DATABASE", "connect", "get_table"]

# Define the application name, WRDS will probably use it to track usage
APPNAME = f"{platform} python {version_info.major}.{version_info.minor}.{version_info.micro}/pytaq-ibis"

# Define the WRDS connection parameters
WRDS_POSTGRES_HOST = "wrds-pgdata.wharton.upenn.edu"
WRDS_POSTGRES_PORT = 9737
WRDS_POSTGRES_DB = "wrds"
WRDS_CONNECT_ARGS = {"sslmode": "require", "application_name": APPNAME}


def connect(
    username: str,
    password: str,
    host: str = WRDS_POSTGRES_HOST,
    port: int = WRDS_POSTGRES_PORT,
    database: str = WRDS_POSTGRES_DB,
    sslmode: str = "require",
    application_name: str = APPNAME,
    **kwargs: Any,
) -> "PostgresBackend":
    """Open a connection to the WRDS postgres server.

    Args:
        username (str): WRDS username
        password (str): WRDS password
        host (str): Server hostname
        port (int): Server port
        database (str): Database name
        sslmode (str): TLS mode; WRDS requires at least "require"
        application_name (str): Reported to WRDS for usage tracking
        **kwargs (Any): Passed through to `ibis.postgres.connect`

    Returns:
        PostgresBackend: An open connection

    Raises:
        ImportError: If the postgres extra is not installed
        ConnectionError: If the server rejects the connection
    """
    # Imported lazily so that pytaq.wrds stays importable without the postgres
    # extra installed; only connecting actually needs the driver.
    try:
        from ibis.backends.postgres import Backend as _PostgresBackend
        from psycopg import OperationalError
    except ImportError as e:
        raise ImportError(
            "Connecting to WRDS requires the postgres backend. "
            "Install it with: pip install 'pytaq[postgres]'"
        ) from e

    try:
        con = ibis.postgres.connect(
            user=username,
            password=password,
            host=host,
            port=port,
            database=database,
            **({"sslmode": sslmode, "application_name": application_name} | kwargs),
        )
    except OperationalError as e:
        raise ConnectionError(f"Failed to connect to WRDS: {e}") from e

    if isinstance(con, _PostgresBackend):
        return con
    else:
        raise ConnectionError("Failed to connect to WRDS (unknown error)")


def get_table(
    con: "PostgresBackend",
    symbols: list[str] | None,
    table_name: str,
    database: str,
) -> "Table":
    """Read one daily TAQ table from the WRDS server.

    Args:
        con (PostgresBackend): Connection from :func:`connect`
        symbols (list[str] | None): Restrict to these root symbols, or None for
            all of them
        table_name (str): Table name, e.g. "ctm_20200102"
        database (str): Schema holding the table, usually "taqmsec"

    Returns:
        Table: The raw table, ready for the cleaning functions
    """
    t = con.table(table_name, database=database)
    if symbols is not None:
        t = t.filter(t.sym_root.isin(symbols))
    return t
