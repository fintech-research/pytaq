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

- [x] **Does the `nbbo_only` filter exclude rows it should keep?** Yes, for
      NYSE-listed symbols. CQS uses letter codes for `natbbo_ind` while the
      code checks for `"1"`, which never appears. All 200,763 quotes for a
      NYSE-listed name were dropped. Filed as #30.

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
      reference results on a known sample date. Blocked behind #29 and #33.

- [ ] Confirm that `merge_quotes_nbbo` on the cleaned NBBO and quote files
      reproduces WRDS's own `complete_nbbo_*` table.

- [ ] The post-2016 CQS `natbbo_ind` codes. The 2013 Daily TAQ specification
      documents CQS as numeric (`0`, `1`, `2`, `4`, `6`) and that matches the
      2016 data exactly, so PyTAQ's filter is correct for that era. By 2020 CQS
      serves letters (`A`, `U`, `G`, `O`) and the filter drops every NYSE-listed
      quote. Resolving this needs a current specification; the 2013 edition in
      `~/Dropbox/Projects/taq docs/` predates the change. See #30.

- [ ] Whether the one-millisecond trade-to-quote lag H&J specify should remain
      the default now that TAQ carries nanoseconds. See #40.
