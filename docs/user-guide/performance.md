# Performance and choosing a data source

The three usage paths are not equally fast, and the difference is large enough to change how you work rather than just how long you wait.

## The short version

**The direct WRDS connection suits small queries: a handful of symbols, or part of a day. For anything larger, pull the data down and work from local files.**

Everything PyTAQ does is an Ibis expression, so the work happens wherever the data is. Against a local DuckDB reading Parquet, a full day of one symbol through the entire pipeline takes well under a second. Against the WRDS postgres server, the same expression runs on their machine, over their network, in a shared environment.

## Why the WRDS path is slow

Nothing here is a defect in WRDS or in PyTAQ. It is what the pipeline asks for:

- **As-of joins.** Matching trades to quotes, and again to the NBBO at a later horizon, are as-of joins over a full trading day. For one liquid symbol that is a few hundred thousand trades against a few hundred thousand quotes
- **Window functions.** The tick test, the NBBO change filter and the quote in-force calculation all order and lag over the whole day
- **It is a shared server.** You are competing with everyone else on it

Composed into a single expression and executed remotely, that can take many minutes for one symbol-day. The same work locally is sub-second.

## What to do instead

### Small queries: query WRDS directly

Fine for exploration, checking a schema, or a few symbols on one day.

```python
from pytaq import wrds

con = wrds.connect(username, password)
trades = wrds.get_table(con, ["AAPL"], "ctm_20200102", "taqmsec")
print(trades.count().execute())
```

### Anything larger: materialise first, then process

Pull the raw tables down once, then run the pipeline locally. Filter on the server, so only what you need crosses the network.

```python
import datetime

import ibis

from pytaq import process_day, wrds

date = datetime.date(2020, 1, 2)
symbols = ["AAPL", "MSFT", "IBM"]

remote = wrds.connect(username, password)
local_con = ibis.duckdb.connect("taq.ddb")

for name in ["ctm_20200102", "complete_nbbo_20200102"]:
    remote_table = wrds.get_table(remote, symbols, name, "taqmsec")
    local_con.create_table(name, remote_table.to_pyarrow(), overwrite=True)

day = process_day(
    local_con.table("ctm_20200102"),
    local_con.table("complete_nbbo_20200102"),
    date=date,
)
daily = day.execute()
```

The download is one scan per table. Everything after it runs at local speed, and you can iterate without paying the network cost again.

### Bulk work: keep local copies

If you are running many dates, export the daily tables once and use [`pytaq.local`](../getting-started/quickstart.md). That is what the local path exists for.

Store them as Parquet. If your copies came off WRDS as `sas7bdat`, convert them first, since DuckDB does not read that format: [Daflip](https://www.vincentgregoire.com/daflip/) converts a file in one command.

```bash
uvx daflip ctm_20200102.sas7bdat data/ctm_20200102.parquet
```

## Backends

Use **DuckDB** for local work.

Ibis 12's polars backend implements no window functions at all, not even `row_number()`. Trade signing, quote in-force times, the NBBO change filter and the quotes-to-NBBO merge all need them, so polars cannot run the pipeline. The extra remains installable for anyone who wants the non-windowed pieces, but it is not the supported local backend.

## Memory

Nothing is loaded until `.execute()`. A full day of quotes for the whole market is hundreds of millions of rows, so filter to the symbols you want before executing, and prefer aggregating on the engine over pulling rows into pandas:

```python
day.daily.execute()        # one row per symbol
day.signed.execute()       # every trade, which may be very large
```
