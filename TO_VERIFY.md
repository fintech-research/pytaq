# To verify against real data

Things that cannot be checked without access to real WRDS TAQ data. Remove an
entry once it has been confirmed.

## Null vs empty string in TAQ flag columns

Two filters were dropping rows because SQL three-valued logic treats
`NULL != 'B'` as NULL rather than true. Both are fixed (see #6), but the
question of what WRDS actually returns is still open, and it determines how
much data the old behaviour was losing.

- [ ] Does `qu_cancel` come back as NULL or as an empty string in `cqm_*` and
      `nbbom_*`? The test fixtures use `""`, which is why the bug went
      unnoticed.
- [ ] Same question for `tr_corr` in `ctm_*`.

## Allowlist filters and nulls

These filters keep only listed values, so a null is excluded. That is probably
correct, but it is a silent exclusion and worth confirming against real data.

- [ ] `cleaning/quotes.py` and `cleaning/nbbo.py`: `qu_cond.isin(HJ_KEEP_QU_COND)`
      drops rows with a null quote condition. Confirm `qu_cond` is always
      populated in TAQ.
- [ ] `cleaning/trades.py`: `tr_corr == "00"` drops rows with a null correction
      code. Confirm `tr_corr` is always populated.
- [ ] `cleaning/quotes.py`: the `nbbo_only` filter on `qu_source` and
      `natbbo_ind` drops rows where either is null.

## Reference results

- [ ] Confirm the cleaning output reproduces the SAS / Holden and Jacobsen
      reference results on a known sample date.
