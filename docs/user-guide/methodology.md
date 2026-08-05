# Methodology and defaults

Every filter and every convention PyTAQ applies is a choice. The defaults reproduce [Holden and Jacobsen (2014)](https://doi.org/10.1111/jofi.12127), which is the de facto standard in empirical microstructure work, and every one is a keyword argument you can change.

This page collects the choices in one place. [The conformance table](holden-jacobsen.md) maps each of them to the paper.

## Time windows

| | Default | Why |
|---|---|---|
| Trades | 09:30 to 16:00 | Regular trading hours |
| Quotes | **09:00** to 16:00 | Half an hour earlier, so the first trades of the day have a quote to match against |
| Quoted-spread statistics | 09:30 to 16:00 | A spread quoted before anyone could trade against it should not enter the day's average |

The asymmetry is deliberate. Narrowing the quote window to 09:30 loses the quotes that the opening trades need, so the window stays open early for matching and the pre-open quotes are dropped afterwards, when the quoted spread is time-weighted. That is H&J's own sequence, and `quoted_spread_start_time` controls it.

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

Each trade is matched to the NBBO in force **one nanosecond earlier**, as H&J's 2018 DTAQ code does. Without the lag, a quote stamped in the same instant as the trade counts as prevailing, and that quote may be a consequence of the trade rather than the state the trader faced. Their 2014 paper specifies one millisecond, which was TAQ's resolution then; pass `HJ_PAPER_TRADE_QUOTE_LAG_NS` to reproduce it.

The comparison is at nanosecond precision. TAQ resolves events to the nanosecond via `time_m_nano`, and on a liquid symbol a few percent of trades share a microsecond with another.

```python
merge_trades_official_nbbo(trades, nbbo, lag=0)  # contemporaneous
```

The lag is an integer count of nanoseconds. A `datetime.timedelta` is still accepted, but it cannot express one nanosecond: its finest unit is the microsecond.

## Percent measures

Twice the log difference, as H&J's 2018 DTAQ code computes every one of them. Realized spread and price impact take the log difference against the **future** midpoint, the one they are measured against.

The ratio form, the dollar measure divided by the reference midpoint, is available through `percent_method="ratio"` on every measure. That is what their 2013 monthly TAQ code did and what much of the published literature reports. The two agree to first order and diverge as spreads widen.

## Trade signing

Lee-Ready, EMO and CLNV, each falling back to the tick test where the price carries no information, and each suppressed when the market is locked or crossed. CLNV uses a 30% threshold.

The tick test carries the last non-zero direction forward. Trades before any price change have no direction and are left null rather than guessed at.

BJZ retail classification is also available; it postdates the paper.

## Averaging

Simple, share-weighted and dollar-weighted for trade measures; time-weighted for quote measures, where a quote counts for as long as it stood, measured as a real number of seconds rather than in whole seconds.

One deliberate departure from the paper: both sums are restricted to rows where the measure **and** the weight are observed. H&J sum the full weight column, so a trade their signing algorithm could not classify still enters the denominator of a share- or dollar-weighted realized spread while contributing nothing to the numerator, which biases the result toward zero in proportion to the weight those trades carry. On complete data the two agree exactly.

## Exclusions when computing measures

Locked and crossed markets are excluded from quoted spreads, from effective spreads at the trade, and from realized spreads and price impacts at the horizon. A midpoint is not meaningful when the bid meets or exceeds the ask.

For quoted spreads the order matters, and it follows H&J: the window is applied first, then each quote is timed, then the locked and crossed ones are dropped. A dropped quote's duration is not handed to its predecessor, it simply does not count, and every surviving quote keeps the duration it actually stood for.

## What PyTAQ does not implement

**Interpolated Time**, an MTAQ technique for second-resolution timestamps. PyTAQ targets DTAQ, where H&J's recommendation is the official complete NBBO with a one-millisecond lag.

**Duration Limited Control** and **excluding regional exchanges**: H&J test both and recommend against them.
