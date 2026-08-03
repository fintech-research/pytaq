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

- [ ] Whether `time_m_nano` matters. Sub-microsecond ordering is currently
      dropped entirely. It may affect sequencing of quotes at the same
      microsecond, which `merge_quotes_nbbo` resolves with `qu_seqnum` instead.

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
      the default now that TAQ carries nanoseconds. See #40.
