# To verify against real data

Things that need access to real WRDS TAQ data. Remove an entry once confirmed.

Live checks below were run against `taqmsec` on the WRDS postgres server for
trading day 2020-01-02, using AAPL (Nasdaq-listed) and A (NYSE-listed).

## Answered

- [x] **Does `qu_cancel` come back as NULL or as an empty string?** NULL, on
      every row. Across 1,925,187 AAPL quotes: 1,925,187 null, 0 empty string,
      0 equal to `"B"`.

      This makes the bug fixed in #6 a total-data-loss bug rather than an edge
      case. The old `qu_cancel != "B"` is NULL for a null flag, so quote
      cleaning would have discarded **every quote in the table**.

- [x] **Same question for `tr_corr`.** Populated, as `"00"`. The trades
      allowlist filter is safe.

- [x] **Does the `nbbo_only` filter exclude rows it should keep?** It did, for
      every NYSE-listed symbol on data from 30 October 2017 onward. CTA
      renumbered the National BBO Indicator from digits to letters on that date
      (Daily TAQ Client Specification 3.0b): `A` was `0`, `G` was `1`, `O` was
      `2`, `T` was `6`, `U` was `4`. UTP never changed. PyTAQ now accepts both
      spellings. Fixed in #30.

- [x] **What type is `time_m`?** A SQL `time`, not numeric seconds since
      midnight as every fixture assumes. No cleaning function runs against real
      WRDS data. Filed as #29.

- [x] **What type are prices?** `decimal`, not float. Arithmetic, `log()` and
      the `float_approx` helpers all work correctly on postgres, and spreads
      come out exact (0.03 rather than 0.029999...). They arrive in pandas as
      `object` dtype, which callers doing numpy work need to know.

- [x] **Do the daily tables exist under `taqmsec`?** Yes, all four. Year
      schemas (`taqm_2003` through `taqm_2026`) also carry them, so
      `DEFAULT_DATABASE = "taqmsec"` remains valid.

## Still open

- [ ] `cleaning/quotes.py` and `cleaning/nbbo.py`: `qu_cond.isin(HJ_KEEP_QU_COND)`
      drops rows with a null quote condition. Every sampled row had `"R"`, so
      this looks safe, but it has not been checked over a full day or across
      listing venues.

- [x] **Does `time_m_nano` matter?** Yes. On AAPL for 2020-01-02, microsecond
      timestamps leave 7,427 trades (2.62%) and 2,655 NBBO rows (0.67%) sharing
      an instant with another row. Nanoseconds resolve every one: distinct
      counts at nanosecond precision equal the row counts exactly. It is now
      carried as `timestamp_ns` and used for ordering and matching. See #52.

- [ ] Confirm the cleaning output reproduces the SAS / Holden and Jacobsen
      reference results on a known sample date. No longer blocked: the pipeline
      runs end to end on both sources. Needs a published reference figure to
      compare against, since H&J report 2008 averages over 100 stocks rather
      than per-symbol numbers.

- [x] **Does `merge_quotes_nbbo` reproduce WRDS's own `complete_nbbo_*`?**
      Substantially, yes. AAPL, 2016-12-07:

      | | rows |
      |---|---|
      | reconstructed, `keep_changes_only=False` | 571,268 |
      | WRDS `complete_nbbo`, all rows | 569,448 |
      | reconstructed, `keep_changes_only=True` | 550,307 |
      | WRDS `complete_nbbo`, distinct timestamps | 548,522 |

      Both settings land within 0.33% of the matching WRDS figure, and the
      count difference between them is explained: WRDS keeps 20,926 rows
      sharing a timestamp with another, which `keep_changes_only` collapses.

      On rows present in both, **99.88% agree exactly on best bid and best
      ask** (568,772 of 569,448). Still open: the systematic excess of roughly
      1,800 quotes we include and WRDS does not, and the 676 value
      disagreements, which are single-tick differences on one side.

- [ ] Explain the ~1,800 excess quotes and the 676 single-tick value
      disagreements in the reconstruction above.

- [ ] Whether the one-millisecond trade-to-quote lag H&J specify should remain
      the default now that TAQ carries nanoseconds. See #40. **Evidence found:**
      their own Daily TAQ program of 16 March 2018 uses **one nanosecond**
      (`time_m=time_m+.000000001`), not the millisecond the 2014 paper specifies.
      So the authors moved with the data. This is now a decision to make, not a
      question to answer: matching the paper and matching their current code are
      no longer the same thing.

- [ ] **Whether `percent_method` should default to `log`.** Their 2018 DTAQ code
      computes every percent measure as a log difference; their 2013 MTAQ code
      divided the dollar measure by the reference midpoint, which is PyTAQ's
      default. `percent_method="log"` reproduces the DTAQ code exactly, formula
      for formula. Changing the default would match the authors' current
      practice, at the cost of diverging from a large body of published work
      using the ratio form. Needs a judgement call, and a note in the docs
      either way.

- [ ] **The rewritten `compute_quote_inforce` on postgres.** It now derives a
      duration from the integer `timestamp_ns` key, which needs no date
      arithmetic and should be identical on both backends. The fallback branch,
      taken only when a caller passes a table without `timestamp_ns`, uses
      `delta(unit="microsecond")`, and no test has ever run a metrics function
      against the WRDS server: the integration tests cover the cleaning
      functions only. Run the quoted-spread path against `taqmsec` once and
      confirm the numbers match a DuckDB run on the same materialised data.

- [ ] **How much the three 0.4.0 corrections move the numbers on real data.**
      All three are verified on fixtures, and the direction is understood, but
      the size on a real symbol-day is not measured. Time-weighted quoted
      spreads change for every symbol-day; effective and realized spreads change
      only on trades near a quote update. Worth one before-and-after run on AAPL
      for 2020-01-02 before anything is published from this.
