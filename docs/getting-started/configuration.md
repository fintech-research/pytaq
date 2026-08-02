# Configuration

## Holden and Jacobsen defaults

Every filter default lives in `pytaq.hj_defaults` and follows [Holden and Jacobsen (2014)](https://doi.org/10.1111/jofi.12127). Nothing is hidden: each one is a keyword argument on the relevant function, so you can override any of them per call.

```python
from pytaq.hj_defaults import HJ_KEEP_QU_COND, HJ_MAX_SPREAD, HJ_START_TIME_QUOTES
```

| Name | Default | Meaning |
|---|---|---|
| `HJ_START_TIME_QUOTES` | `09:00` | Quote window opens |
| `HJ_END_TIME_QUOTES` | `16:00` | Quote window closes |
| `HJ_START_TIME_TRADES` | `09:30` | Trade window opens |
| `HJ_END_TIME_TRADES` | `16:00` | Trade window closes |
| `HJ_KEEP_QU_COND` | `["A", "B", "H", "O", "R", "W"]` | Quote conditions kept |
| `HJ_MAX_SPREAD` | `$5.00` | Quotes with a wider spread are dropped |
| `HJ_MAX_QUOTE_CHANGE` | `$2.50` | Threshold for the abnormal-quote-change filter |
| `HJ_DELETE_CANCELED_QUOTES` | `True` | Drop quotes with `qu_cancel = "B"` |
| `HJ_DELETE_EMPTY_QUOTES` | `True` | Drop quotes with no bid and no ask |
| `HJ_DELETE_ABNORMAL_SPREADS` | `True` | Apply the spread and quote-change filters |
| `HJ_DELETE_WITHDRAWN_QUOTES` | `True` | Drop quotes with a missing or non-positive side |
| `HJ_DELETE_CROSSED_MARKETS` | `True` | Drop quotes where the bid exceeds the ask |
| `HJ_KEEP_CHANGES_ONLY` | `True` | Keep only quotes that changed the NBBO |

Note the quote window opens at 09:00, half an hour before the trade window. That is deliberate: quotes need to be in force before the first trade can be matched to one.

Overriding is per call:

```python
import datetime
from decimal import Decimal

from pytaq import clean_nbbo

nbbo = clean_nbbo(
    raw_nbbo,
    start_time=datetime.time(9, 30),
    max_spread=Decimal("10.0"),
    keep_changes_only=False,
)
```

`HJ_MAX_SPREAD` and `HJ_MAX_QUOTE_CHANGE` are `Decimal`, not `float`, so prices compare exactly.

## Backends

### DuckDB, for local files

```python
from pytaq import local

con = local.connect()
```

`local.connect()` passes any keyword arguments through to `ibis.duckdb.connect`, so you can point at a persistent database or tune the engine:

```python
con = local.connect(threads=4, memory_limit="8GB")
```

### Postgres, for WRDS

```python
from pytaq import wrds

con = wrds.connect(username="...", password="...")
```

Defaults target the WRDS server (`wrds-pgdata.wharton.upenn.edu`, port 9737, database `wrds`, `sslmode=require`). Extra keyword arguments go through to `ibis.postgres.connect`.

### Polars

Installable, but it cannot run the full pipeline: Ibis 12's polars backend implements no window functions. Trade signing, quote in-force times, NBBO change filtering and the quotes-to-NBBO merge all need them. Use DuckDB.
