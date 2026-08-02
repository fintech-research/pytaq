# Conformance with Holden and Jacobsen (2014)

[Holden and Jacobsen (2014)](https://doi.org/10.1111/jofi.12127) is not a specification, but their cleaning procedure is the de facto default in empirical microstructure research. PyTAQ aims to reproduce it exactly by default, while making each choice visible and overridable.

This page records where PyTAQ stands against their published SAS code (Internet Appendix, September 2013 version) and against the Daily TAQ Client Specification. It is maintained by hand; when you change a measure, change this table.

Legend: **matches**, **differs** (tracked by an issue), **absent**.

## Data retrieval and filtering

| Step | Holden and Jacobsen | PyTAQ | Status |
|---|---|---|---|
| Quote window | 09:00 to 16:00 | `HJ_START_TIME_QUOTES` 09:00 | matches |
| Trade window | 09:30 to 16:00 | `HJ_START_TIME_TRADES` 09:30 | matches |
| Trade filter | `corr = '00'` and `price > 0` | same | matches |
| Abnormal quote conditions | neutralise the quote | drops the row | differs, #41 |
| Crossed quotes on one exchange | neutralise | drops the row | differs, #41 |
| One-sided quotes | keep, neutralise the absent side | drops the row | differs, #41 |
| Spread wider than $5 | neutralise | drops the row | differs, #41 |
| Withdrawn quotes | neutralise, **explicitly not deleted** | drops the row | differs, #41 |
| NBBO eligibility | not applicable to MTAQ | `qu_source` and `natbbo_ind` | matches the 2013 spec; breaks on post-2016 CQS, #30 |

The withdrawn-quote row is the one that matters most. Deleting a withdrawn quote leaves that exchange's *previous* quote standing in the reconstructed NBBO, which is the stale-quote error the paper is about.

## Matching trades to quotes

| Step | Holden and Jacobsen | PyTAQ | Status |
|---|---|---|---|
| Quote timing, DTAQ | one millisecond lag | contemporaneous (`>=`) | differs, #40 |
| Match direction | most recent prior quote | as-of join, backward | matches |
| Trades with no prior quote | not applicable | kept, null quote columns | extension |

## Trade signing

| Step | Holden and Jacobsen | PyTAQ | Status |
|---|---|---|---|
| Lee-Ready | price against midpoint, tick otherwise | `sign_lr` | matches |
| EMO (their EOH) | price at bid or ask, tick otherwise | `sign_emo` | matches |
| CLNV, 30% threshold | `ofr30 = ask - 0.3·spread` | `DEFAULT_CLNV_THRESHOLD = 0.3` | matches |
| Gated on locked and crossed | assign only when `lock = 0 and cross = 0` | same | matches |
| Tick test | up-tick buy, down-tick sell, carry forward | `sign_tick` | matches |
| BJZ retail | not in the paper | `sign_bjz` | extension |

## Liquidity measures

Dollar measures agree throughout. Percent measures do not: H&J divide the dollar measure by the midpoint, PyTAQ takes a log difference.

| Measure | Holden and Jacobsen | PyTAQ | Status |
|---|---|---|---|
| Dollar quoted spread | `ask - bid` | same | matches |
| Percent quoted spread | `(ask - bid) / midpoint` | `log(ask) - log(bid)` | differs, #39 |
| Dollar effective spread | `2·abs(P - M)` | same | matches |
| Percent effective spread | `2·abs(P - M) / M` | `2·abs(log P - log M)` | differs, #39 |
| Dollar realized spread | `2·D·(P - M₅)` | same | matches |
| Percent realized spread | `2·D·(P - M₅) / M₅` | `2·D·(log P - log M₅)` | differs, #39 |
| Dollar price impact | `ES$ - RS$` | `2·D·(M₅ - M)` | matches, algebraically identical |
| Percent price impact | `(ES$ - RS$) / M₅` | `2·D·(log M₅ - log M)` | differs, #39 |
| Realized spread horizon | 5 minutes | `delay` parameter, default 5 minutes | matches |
| Denominator for RS and PI | the **future** midpoint `M₅` | `M₅` in the dollar form | matches |

## Exclusions when computing measures

| Step | Holden and Jacobsen | PyTAQ | Status |
|---|---|---|---|
| Quoted spread: drop locked and crossed | `if BestOfr <= BestBid then delete` | `filter_locks_crosses` | available, not wired into `compute_spreads` |
| Effective spread: drop locked and crossed trades | `if lock or cross then delete` | expects `lock` and `cross` columns nothing creates | differs, #27 |
| Realized spread: drop if the **T+5** quote is locked or crossed | yes | intended, currently raises | differs, #26 |

## Aggregation

| Step | Holden and Jacobsen | PyTAQ | Status |
|---|---|---|---|
| Quoted spread, time-weighted | `sum(x·inforce) / sum(inforce)` | `compute_weighted_averages` | matches in form, null bias, #32 |
| Last quote in force until 16:00 | `inforce = max(end - t, 0)` | `end_timestamp` parameter | matches |
| Effective spread, simple average | `mean(x)` | `compute_averages` | matches |
| Share-weighted | `sum(x·size) / sum(size)` | same | matches in form, null bias, #32 |
| Dollar-weighted | `sum(x·dollar) / sum(dollar)` | same | matches in form, null bias, #32 |
| Quoted-spread statistics window | quotes before 09:30 deleted **after** the NBBO is built | uses one window throughout | differs, minor |

On #32: H&J's data has no missing measures at the point of aggregation, so the null-weighting question never arises for them. PyTAQ's fix is a deliberate improvement rather than a divergence, but it is a place where the two can differ on data containing nulls, and that is worth knowing when comparing output.

## Not implemented

| Item | Note |
|---|---|
| Interpolated Time | An MTAQ technique, for second-resolution timestamps. PyTAQ targets DTAQ, where H&J's recommendation is the official complete NBBO with a one-millisecond lag. Only needed for pre-2015 monthly TAQ |
| NBBO reconstruction across exchanges | H&J rebuild the NBBO from per-exchange quotes. PyTAQ's `merge_quotes_nbbo` unions the NBBO and quote files instead, which is the DTAQ equivalent |
| Maximum depth | H&J report both total depth across venues and the largest single-venue depth. PyTAQ computes only the total |
| Duration Limited Control | H&J test it and recommend against it. Deliberately absent |
| Excluding regional exchanges | H&J test it and prefer excluding locked and crossed instead. Deliberately absent |

## Where PyTAQ deliberately goes further

- **Two data sources.** WRDS postgres and local files, through one implementation
- **Every filter is a keyword argument.** H&J's procedure is the default, not the only option
- **BJZ retail classification**, which postdates the paper
- **Reproducibility.** Quote ordering is tie-broken on `qu_seqnum`, so repeated runs agree. See #33
- **Null-safe filters**, so a null flag does not silently discard a row. See #6

## Sources

- Holden, C. and S. Jacobsen (2014), "Liquidity Measurement Problems in Fast, Competitive Markets: Expensive and Cheap Solutions", *Journal of Finance* 69(4)
- Internet Appendix to the above, including the September 2013 SAS implementation
- Daily TAQ Client Specification, 6 August 2013 edition
