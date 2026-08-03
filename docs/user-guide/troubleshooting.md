# Troubleshooting

## A filter returns zero rows

Almost always a flag column whose encoding does not match what the filter expects.

**`nbbo_only` drops everything.** CTA renumbered the National BBO Indicator from digits to letters on 30 October 2017: `G` was `1`, `A` was `0`, `O` was `2`, `T` was `6`, `U` was `4`. PyTAQ accepts both spellings, so this should not happen, but if you are working with an unusual vintage:

```python
clean_quote_table(raw, cta_nbbo_codes=("1", "G"), utp_nbbo_codes=("4",))
```

Check what your data actually contains before assuming:

```python
raw.group_by(["qu_source", "natbbo_ind"]).aggregate(n=raw.count()).execute()
```

**A quote-condition filter drops everything.** `keep_qu_cond` is an allowlist, and a null condition is not in it. Pass `keep_qu_cond=None` to disable.

## `TypeError: time_m must be a time or a numeric...`

`time_m` arrives two ways: a SQL `time` from the WRDS postgres server, a `double` of seconds since midnight from most local exports. PyTAQ handles both. Anything else, a string most likely, means the source has been converted somewhere along the way. Check with `raw.schema()`.

## Everything is null after cleaning

Quote filters null out a **side** rather than dropping the row, by design. Rows with both sides null are quotes from a venue that has stepped away. That is information, not an error.

If more is null than you expect, run the filters one at a time with `output_flags=True` to see which one is responsible.

## The pipeline is very slow

You are probably running against the WRDS server. See [Performance](performance.md): the direct connection suits small queries, and anything larger should be materialised locally first.

## `OperationNotDefinedError: No translation rule for ... WindowFunction`

You are on the polars backend. Ibis 12's polars compiler implements no window functions, so it cannot run trade signing, quote in-force times, the NBBO change filter or the quotes-to-NBBO merge. Use DuckDB.

## `ImportError: ... requires the postgres backend`

Install the extra for the path you are using:

```bash
pip install 'pytaq[postgres]'   # WRDS
pip install 'pytaq[duckdb]'     # local files
```

Importing `pytaq` never requires either; only connecting does.

## Results change between runs

They should not. If they do, the ordering is underdetermined somewhere: timestamps are not unique, and a window ordered only on them lets `lag()` pick arbitrarily among ties. PyTAQ orders on `timestamp_ns` and breaks remaining ties on `qu_seqnum`. If you have passed `sequence_col=None`, or your data lacks both, that is the cause.

## Numbers disagree with a published paper

Check [the conformance table](holden-jacobsen.md) first. The defaults follow Holden and Jacobsen, but two things differ deliberately, and other papers make different choices again, particularly on the percent convention and the trade-quote lag. Both are arguments:

```python
process_day(..., percent_method="log", lag=datetime.timedelta(0))
```
