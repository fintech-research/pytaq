# Methodology and defaults

Every filter and every convention PyTAQ applies is a choice. The defaults reproduce [Holden and Jacobsen (2014)](https://doi.org/10.1111/jofi.12127), which is the de facto standard in empirical microstructure work, and every one is a keyword argument you can change.

This page collects the choices in one place. [The conformance table](../reference/holden-jacobsen.md) maps each of them to the paper.

## Time windows

| | Default | Why |
|---|---|---|
| Trades | 09:30 to 16:00 | Regular trading hours |
| Quotes | **09:00** to 16:00 | Half an hour earlier, so the first trades of the day have a quote to match against |

The asymmetry is deliberate. Narrowing the quote window to 09:30 loses the quotes that the opening trades need.

## Trade filters

Corrected trades (`tr_corr != "00"`) and non-positive prices are dropped. Both are row deletions, since a corrected trade is not a trade.

## Quote filters exclude a side, they do not delete the row

This is the subtlest thing PyTAQ does, and it matters.

Quote filters set the offending **side** to null and keep the row. Holden and Jacobsen are explicit about why:

> They are NOT deleted, because that would incorrectly allow the prior quote from the exchange to enter the NBBO.

The NBBO carries each venue's last quote forward. Deleting a withdrawn quote does not take the venue out of the book; it leaves the venue's *previous* quote standing as though still live, which is the stale-quote problem the paper is about.

The two sides are handled independently, so a genuine one-sided quote keeps its live side and still contributes to that side of the NBBO.

| Filter | Default | Effect |
|---|---|---|
| Quote condition | keep `A B H O R W` | Both sides nulled if the condition is abnormal |
| Cancelled | on | Both sides nulled when `qu_cancel = "B"` |
| Crossed within a venue | on | Both sides nulled |
| Spread wider than $5 | on | Both sides nulled |
| Withdrawn | on | The affected side nulled |
| `nbbo_only` | on | A genuine row filter: keeps quotes that are themselves the NBBO |

A null flag means "not set". `qu_cancel` is null on essentially every real quote, and `NULL != 'B'` is NULL in SQL rather than true, so the filters test for it explicitly. Getting that wrong discards the entire table.

## Matching trades to quotes

Each trade is matched to the NBBO in force **one millisecond earlier**, as H&J specify for DTAQ. Without the lag, a quote stamped in the same instant as the trade counts as prevailing, and that quote may be a consequence of the trade rather than the state the trader faced.

The comparison is at nanosecond precision. TAQ resolves events to the nanosecond via `time_m_nano`, and on a liquid symbol a few percent of trades share a microsecond with another.

```python
merge_trades_official_nbbo(trades, nbbo, lag=datetime.timedelta(0))  # contemporaneous
```

## Percent measures

The dollar measure divided by the reference midpoint, as H&J define it. Realized spread and price impact use the **future** midpoint, the one they are measured against.

The log-difference form is available through `percent_method="log"` on every measure. The two agree to first order and diverge as spreads widen.

## Trade signing

Lee-Ready, EMO and CLNV, each falling back to the tick test where the price carries no information, and each suppressed when the market is locked or crossed. CLNV uses a 30% threshold.

The tick test carries the last non-zero direction forward. Trades before any price change have no direction and are left null rather than guessed at.

BJZ retail classification is also available; it postdates the paper.

## Averaging

Simple, share-weighted and dollar-weighted for trade measures; time-weighted for quote measures, where a quote counts for as long as it stood.

One deliberate departure from the paper: both sums are restricted to rows where the measure **and** the weight are observed. Summing the full weight column while the numerator skips nulls biases the result toward zero. On complete data, which is what H&J had, the two agree exactly.

## Exclusions when computing measures

Locked and crossed markets are excluded from quoted spreads, from effective spreads at the trade, and from realized spreads and price impacts at the horizon. A midpoint is not meaningful when the bid meets or exceeds the ask.

## What PyTAQ does not implement

**Interpolated Time**, an MTAQ technique for second-resolution timestamps. PyTAQ targets DTAQ, where H&J's recommendation is the official complete NBBO with a one-millisecond lag.

**Duration Limited Control** and **excluding regional exchanges**: H&J test both and recommend against them.
