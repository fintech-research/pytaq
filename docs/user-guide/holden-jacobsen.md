# Conformance with Holden and Jacobsen (2014)

[Holden and Jacobsen (2014)](https://doi.org/10.1111/jofi.12127) is not a specification, but their cleaning procedure is the de facto default in empirical microstructure research. PyTAQ aims to reproduce it exactly by default, while making each choice visible and overridable.

This page records where PyTAQ stands against their published SAS code and against the Daily TAQ Client Specification. It is maintained by hand; when you change a measure, change this table.

There are **two** published programs, and they do not agree with each other:

- the **MTAQ** code of September 2013, printed at the end of the Internet Appendix, which reconstructs the NBBO from the consolidated quote file and uses Interpolated Time
- the **DTAQ** code of 16 March 2018, distributed separately, which is the one to compare against here, since it targets the same data PyTAQ does

Where the two differ, the DTAQ code wins and PyTAQ's defaults follow it: percent measures are log differences and the trade-to-quote lag is one nanosecond. Both MTAQ conventions remain available, since a large body of published work rests on them.

Legend: **matches**, **differs** (tracked by an issue), **absent**.

## Data retrieval and filtering

| Step | Holden and Jacobsen | PyTAQ | Status |
|---|---|---|---|
| Quote window | 09:00 to 16:00 | `HJ_START_TIME_QUOTES` 09:00 | matches |
| Trade window | 09:30 to 16:00 | `HJ_START_TIME_TRADES` 09:30 | matches |
| Trade filter | `corr = '00'` and `price > 0` | same | matches |
| Abnormal quote conditions | neutralise the quote | neutralises both sides | matches |
| Crossed quotes on one exchange | neutralise | neutralises both sides | matches |
| One-sided quotes | keep, neutralise the absent side | same | matches |
| Spread wider than $5 | neutralise | neutralises both sides | matches |
| Withdrawn quotes | neutralise, **explicitly not deleted** | neutralises the affected side | matches |
| NBBO eligibility | not applicable to MTAQ | `qu_source` and `natbbo_ind`, both encodings | matches |

These filters set the offending side to null rather than dropping the row, which is what H&J require: deleting a withdrawn quote leaves that exchange's *previous* quote standing in the reconstructed NBBO, the stale-quote error the paper is about. PyTAQ uses null where H&J use the sentinel values 0 and 9999999, which are a SAS artefact.

`clean_nbbo` still deletes rows on the cancelled-quote flag. That operates on the NBBO file, whose rows are the SIP's own output rather than per-venue quotes carried forward, so the same argument does not obviously apply. Worth revisiting.

## Matching trades to quotes

| Step | Holden and Jacobsen | PyTAQ | Status |
|---|---|---|---|
| Quote timing, DTAQ | paper: one millisecond. 2018 code: **one nanosecond** (`time_m=time_m+.000000001`) | one nanosecond by default, `HJ_PAPER_TRADE_QUOTE_LAG_NS` for the paper's | matches the code |
| Match direction | most recent prior quote | as-of join, backward, nanosecond precision | matches |
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

Dollar measures agree throughout.

**Percent measures follow the DTAQ code, which uses log differences.** Their 2018 program computes every one that way:

```sas
wQuotedSpread_Percent   = (log(Best_Ask) - log(Best_Bid)) * inforce;
wEffectiveSpread_Percent = abs(log(price) - log(midpoint)) * 2;
wPercentRealizedSpread_LR = BuySellLR * (log(price) - log(midpoint5)) * 2;
wPercentPriceImpact_LR    = BuySellLR * (log(midpoint5) - log(midpoint)) * 2;
```

Their 2013 MTAQ program divided the dollar measure by the reference midpoint instead. **PyTAQ defaults to the log form**, matching the DTAQ code formula for formula, since DTAQ is what PyTAQ targets. `percent_method="ratio"` restores the MTAQ convention, which much of the published literature uses. The two agree to first order and diverge as spreads widen.

| Measure | Holden and Jacobsen | PyTAQ | Status |
|---|---|---|---|
| Dollar quoted spread | `ask - bid` | same | matches |
| Percent quoted spread | DTAQ: `log(ask) - log(bid)` | same by default | matches, `percent_method="ratio"` for the MTAQ form |
| Dollar effective spread | `2·abs(P - M)` | same | matches |
| Percent effective spread | DTAQ: `2·abs(log P - log M)` | same by default | matches |
| Dollar realized spread | `2·D·(P - M₅)` | same | matches |
| Percent realized spread | DTAQ: `2·D·(log P - log M₅)` | same by default | matches |
| Dollar price impact | DTAQ: `2·D·(M₅ - M)` | same | matches |
| Percent price impact | DTAQ: `2·D·(log M₅ - log M)` | same by default | matches |
| Realized spread horizon | 5 minutes | `delay` parameter, default 5 minutes | matches |
| Denominator for RS and PI | the **future** midpoint `M₅` | `M₅` in the dollar form | matches |

### On price impact

The 2018 DTAQ code computes `wDollarPriceImpact_LR = BuySellLR*(midpoint5-midpoint)*2`, which is PyTAQ's expression exactly. Nothing to reconcile.

Their 2013 MTAQ code did something else: `wDollarPriceImpact = wEffectiveSpread_Dollar - wDollarRealizedSpread`, with the effective spread unsigned. That is identical to `2·D·(M₅ - M)` only when `D` agrees with the side of the midpoint the trade fell on, which Lee-Ready guarantees and EMO and CLNV do not, since both fall back to the tick test away from the quotes. So the two published programs disagree with each other on EMO and CLNV price impact, and PyTAQ follows the later one.

## Exclusions when computing measures

| Step | Holden and Jacobsen | PyTAQ | Status |
|---|---|---|---|
| Quoted spread: drop locked and crossed | `if BestOfr <= BestBid then delete` | `filter_locks_crosses`, applied by `compute_weighted_spreads` | matches |
| Effective spread: drop locked and crossed trades | `if lock or cross then delete` | derived from the prevailing quote | matches |
| Realized spread: drop if the **T+5** quote is locked or crossed | yes | same | matches |

## Aggregation

| Step | Holden and Jacobsen | PyTAQ | Status |
|---|---|---|---|
| Time in force | `inforce = abs(dif(InterpolatedTime))`, a fractional-second duration | `compute_quote_inforce`, seconds as a real number | matches |
| Quoted spread, time-weighted | `sum(x·inforce) / sum(inforce)` | `compute_weighted_averages` | matches, denominator restricted to observed rows |
| Last quote in force until 16:00 | `inforce = max(end - t, 0)` | `end_timestamp` parameter, clamped at zero | matches |
| Effective spread, simple average | `mean(x)` | `compute_averages` | matches |
| Share-weighted | `sum(x·size) / sum(size)` | same | matches, denominator restricted to observed rows |
| Dollar-weighted | `sum(x·dollar) / sum(dollar)` | same | matches, denominator restricted to observed rows |
| Quoted-spread statistics window | quotes before 09:30 deleted **after** the NBBO is built | `quoted_spread_start_time`, defaulting to the start of the trade window | matches |
| Locked and crossed quotes, quote statistics | deleted after timing, before weighting | same order in `process_day` | matches |

On the weighted averages: H&J sum the full weight column. Their aggregation reads `sum(dollar) as sumdollar` over every retained trade and divides by it, so a trade their signing algorithm left unclassified still enters the denominator while contributing nothing to the numerator. PyTAQ restricts both sums to rows where the measure and the weight are observed. On complete data the two agree exactly; where the measure is missing, a literal transcription of the SAS is biased toward zero in proportion to the weight the missing rows carry. This is the one place PyTAQ deliberately does not follow the published code. See #32.

## Not implemented

| Item | Note |
|---|---|
| Interpolated Time | An MTAQ technique, for second-resolution timestamps. PyTAQ targets DTAQ, where H&J's recommendation is the official complete NBBO with a one-nanosecond lag. Only needed for pre-2015 monthly TAQ |
| NBBO reconstruction across exchanges | H&J rebuild the NBBO from per-exchange quotes. PyTAQ's `merge_quotes_nbbo` unions the NBBO and quote files instead, which is the DTAQ equivalent and what WRDS's own guidance recommends: the NBBO file omits quotes that are themselves both the new best bid and best offer, so they must come from the quotes file |
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
- Internet Appendix to the above, including the September 2013 MTAQ SAS implementation
- **Holden and Jacobsen Daily TAQ Code, 16 March 2018**, the DTAQ program, which is the primary reference for this table
- Daily TAQ Client Specification, 6 August 2013 edition


## Validation against WRDS

Reconstructing the complete NBBO from the NBBO and quote files, AAPL on 2016-12-07:

| | rows |
|---|---|
| reconstructed, `keep_changes_only=False` | 571,268 |
| WRDS `complete_nbbo`, all rows | 569,448 |
| reconstructed, `keep_changes_only=True` | 550,307 |
| WRDS `complete_nbbo`, distinct timestamps | 548,522 |

Both settings land within 0.33% of the matching WRDS figure, and **99.88% of rows present in both agree exactly on best bid and best ask**. The residual is recorded in `TO_VERIFY.md`.
