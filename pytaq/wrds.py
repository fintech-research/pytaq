import datetime
from sys import platform, version_info
from typing import TYPE_CHECKING

import ibis

if TYPE_CHECKING:
    from ibis.backends.postgres import Backend as PostgresBackend

# Define the application name, WRDS will probably use it to track usage
APPNAME = f"{platform} python {version_info.major}.{version_info.minor}.{version_info.micro}/pytaq-ibis"

# Define the WRDS connection parameters
WRDS_POSTGRES_HOST = "wrds-pgdata.wharton.upenn.edu"
WRDS_POSTGRES_PORT = 9737
WRDS_POSTGRES_DB = "wrds"
WRDS_CONNECT_ARGS = {"sslmode": "require", "application_name": APPNAME}

DEFAULT_DATABASE = "taqmsec"


def connect(
    username: str,
    password: str,
    host: str = WRDS_POSTGRES_HOST,
    port: int = WRDS_POSTGRES_PORT,
    database: str = WRDS_POSTGRES_DB,
    sslmode: str = "require",
    application_name: str = APPNAME,
    **kwargs,
) -> "PostgresBackend":
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
) -> ibis.Table:
    t = con.table(table_name, database=database)
    if symbols is not None:
        t = t.filter(t.sym_root.isin(symbols))
    return t


def get_trades_table_name(date: datetime.date | datetime.datetime) -> str:
    return "ctm_" + date.strftime("%Y%m%d")


def get_nbbo_table_name(date: datetime.date | datetime.datetime) -> str:
    return "nbbom_" + date.strftime("%Y%m%d")


def get_official_complete_nbbo_table_name(
    date: datetime.date | datetime.datetime,
) -> str:
    return "complete_nbbo_" + date.strftime("%Y%m%d")


def get_quotes_table_name(date: datetime.date | datetime.datetime) -> str:
    return "cqm_" + date.strftime("%Y%m%d")
