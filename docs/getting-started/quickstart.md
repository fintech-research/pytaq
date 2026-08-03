# Quick start

## The short version

```python
import datetime

from pytaq import local, process_day

con = local.connect()
date = datetime.date(2020, 1, 2)

day = process_day(
    local.get_trades(con, "data/", date, symbols=["AAPL"]),
    local.get_official_complete_nbbo(con, "data/", date, symbols=["AAPL"]),
    date=date,
)

daily = day.execute()
```

`process_day` runs the standard Holden and Jacobsen pipeline end to end and returns one row per symbol. It exists because the stages have an order, and the order carries constraints that are easy to get subtly wrong: the quote window opens half an hour before the trade window so the first trades have something to match, trades are matched to the quote in force one millisecond earlier, and realized spreads need the NBBO a second time at a later horizon. Getting any of that wrong produces plausible numbers rather than an error.

Every intermediate is on the returned object, and every underlying option is a keyword argument:

```python
day.signed              # trades with all four sign columns
day.effective_spreads   # per-trade measures
day.quoted_spreads      # per-quote measures with time in force
day.realized_spreads    # per-trade, at the horizon

process_day(..., horizon=datetime.timedelta(minutes=1), horizon_suffix="1min")
process_day(..., percent_method="log", track_retail=True)
```

The rest of this page assembles the same pipeline by hand, which is worth reading once even if you only ever call `process_day`.

## The long version

Every workflow has the same three stages. Only the first differs between the three usage paths.

1. **Open** the raw daily tables
2. **Clean** them
3. **Compute** metrics

## Opening the data

### Local TAQ files

`pytaq.local` expects one file per date per data type, named after the WRDS table it came from, in a single directory:

```text
data/
    ctm_20200102.parquet            trades
    cqm_20200102.parquet            quotes
    nbbom_20200102.parquet          NBBO
    complete_nbbo_20200102.parquet  official complete NBBO
```

Parquet and CSV are both read; the extension decides. Column names may be upper or lower case.

```python
import datetime

from pytaq import local

con = local.connect()
date = datetime.date(2020, 1, 2)

raw_trades = local.get_trades(con, "data/", date, symbols=["AAPL"])
raw_nbbo = local.get_official_complete_nbbo(con, "data/", date, symbols=["AAPL"])
```

### The WRDS postgres server

Identical from here on; only the opening differs. This works both on the WRDS cloud and from your own machine.

```python
import datetime

from pytaq import wrds

con = wrds.connect(username="your_username", password="your_password")
date = datetime.date(2020, 1, 2)

raw_trades = wrds.get_table(
    con,
    symbols=["AAPL"],
    table_name=pytaq.get_trades_table_name(date),
    database="taqmsec",
)
```

Keep credentials out of your code. A `.env` file read with `python-dotenv` works well:

```python
import os

from dotenv import load_dotenv

load_dotenv()
con = wrds.connect(os.environ["WRDS_USERNAME"], os.environ["WRDS_PASSWORD"])
```

## Cleaning

```python
from pytaq import clean_official_complete_nbbo, clean_trades

trades = clean_trades(raw_trades)
nbbo = clean_official_complete_nbbo(raw_nbbo)
```

`clean_trades` merges date and time into `timestamp`, merges the symbol root and suffix into `symbol`, drops corrected trades and non-positive prices, restricts to trading hours, and adds `dollar` volume.

Every filter can be turned off. The defaults come from Holden and Jacobsen; see [Configuration](configuration.md).

```python
import datetime

trades = clean_trades(
    raw_trades,
    exclude_corrections=False,
    start_time=datetime.time(9, 45),
    end_time=datetime.time(15, 45),
)
```

## Matching trades to quotes

Each trade is matched to the most recent quote for the same symbol at or before its timestamp. A trade that precedes any quote keeps null quote columns rather than being dropped.

```python
from pytaq import merge_trades_official_nbbo

matched = merge_trades_official_nbbo(trades, nbbo)
```

## Computing metrics

```python
from pytaq import sign_trades
from pytaq.metrics import compute_effective_spreads

signed = sign_trades(matched)
spreads = compute_effective_spreads(signed)

result = spreads.execute()
```

Nothing above touches the data. Ibis builds an expression and the engine runs it when you call `.execute()`, so filters and column selections are pushed down rather than materialised one stage at a time.

## Next

- [Configuration](configuration.md), the Holden and Jacobsen defaults and how to override them
- [Cleaning](../user-guide/cleaning.md)
- [Metrics](../user-guide/metrics.md)
