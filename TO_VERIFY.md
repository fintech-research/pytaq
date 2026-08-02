# To verify against real data

Things that need access to real WRDS TAQ data. Remove an entry once confirmed.

## Answered on 2026-08-02

Checked against `taqmsec` on the live WRDS server, trading day 2020-01-02.

- [x] **Does `qu_cancel` come back as NULL or as an empty string?** NULL, on
      every row. Across 1,925,187 AAPL quotes: 1,925,187 null, 0 empty string,
      0 equal to `"B"`.

      This makes the bug fixed in #6 a total-data-loss bug rather than an edge
      case. The old `qu_cancel != "B"` evaluates to NULL for a null flag, so
      the quote-cleaning path would have discarded **every quote in the table**.

- [x] **Same question for `tr_corr`.** Populated, as `"00"`. The trades
      allowlist filter is safe.

- [x] **Does the `nbbo_only` filter on `qu_source` and `natbbo_ind` exclude
      rows it should keep?** Yes, for NYSE-listed symbols. CQS uses letter
      codes for `natbbo_ind` and the code checks for `"1"`, which never
      appears, so all 200,763 quotes for a NYSE-listed name were dropped.
      Filed as #30.

## Still open

- [ ] `cleaning/quotes.py` and `cleaning/nbbo.py`: `qu_cond.isin(HJ_KEEP_QU_COND)`
      drops rows with a null quote condition. Observed values were `"R"` on
      every sampled row, so this looks safe, but it has not been checked over a
      full day or across listing venues.

- [ ] Confirm the cleaning output reproduces the SAS / Holden and Jacobsen
      reference results on a known sample date. Blocked behind #29, since the
      pipeline cannot currently run against real WRDS data at all.

- [ ] Confirm that `merge_quotes_nbbo` on the cleaned NBBO and quote files
      reproduces WRDS's own `complete_nbbo_*` table.
