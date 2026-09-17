# v2.3 PAPER baseline — 2026-09-17

This note records the completed v2.3 PAPER run used to guide v2.4 research. It is a baseline observation, not evidence of future profitability.

## Run summary

The uploaded archive contained 57 opens and 55 closes. Two positions were still open when the archive was captured, so the figures below are **realized closed-trade results only** unless stated otherwise.

- Starting equity: $1,000.00
- Final realized equity represented by closed trades: $1,013.49
- Realized P&L: +$13.49 (+1.35%)
- Closed trades: 55
- Wins / losses: 25 / 30
- Win rate: 45.45%
- Gross profit: $219.19
- Gross loss: $205.70
- Gross profit factor: 1.066
- Average closed trade: +$0.25
- Average winner: +$8.77, about +1.80R
- Average loser: -$6.86, about -1.00R
- Median trade: about -1.00R
- Maximum consecutive losing closes: 10

## Profit giveback

Realized equity peaked at approximately **$1,144.83** at 03:30:56 UTC and later fell to $1,013.49 in the captured close history.

- Peak gain over starting equity: +$144.83 (+14.48%)
- Peak-to-final realized decline: -$131.34
- Peak-to-final drawdown: about 11.47%
- Fraction of peak accumulated profit surrendered: about **90.7%**

The first major reversal after the peak produced eight consecutive losing closes totaling about -$72.78 before the next winner. Later in the run, a ten-loss closing streak occurred.

This is the main motivation for v2.4 high-water profit protection and loss-cluster risk throttling.

## Timeframe contribution

| TF | Closed | Wins | Win rate | Gross P&L | Gross PF |
|---|---:|---:|---:|---:|---:|
| 1m | 36 | 18 | 50.0% | +$42.76 | 1.547 |
| 3m | 11 | 3 | 27.3% | -$42.73 | 0.446 |
| 5m | 7 | 4 | 57.1% | +$29.66 | 1.867 |
| 15m | 1 | 0 | 0.0% | -$16.20 | 0.000 |

The sample is far too small to permanently disable any timeframe, but it is enough to justify testing weighted sizing, slot reservation and rolling timeframe-health statistics.

## First report vs later deterioration

The automatic 3-hour report ended with 42 closed trades, 24 wins, 18 losses and +$73.86 realized P&L. After that report, the archive contains another 13 closes: **1 winner and 12 losers**, totaling about **-$60.37** gross.

This shows why a single favorable report window cannot be used as proof of an edge and why v2.4 must react to regime transition and profit giveback.

## Execution-cost stress test

The 55 closed trades represent roughly **$363,949** of two-sided notional turnover, using the logged BTC-USDT contract size relationship. v2.3 PAPER did not deduct exchange trading fees.

Illustrative fee-only stress tests on the same closed trades:

- 0.06% on both entry and exit notionals: about $218.37 fees; gross +$13.49 becomes about **-$204.88** before slippage/funding.
- 0.02% on both entry and exit notionals: about $72.79 fees; gross +$13.49 becomes about **-$59.30** before slippage/funding.
- 0.06% entry + 0.02% exit: about $145.56 fees; gross +$13.49 becomes about **-$132.07** before slippage/funding.

These are stress-test assumptions, not a reconstruction of actual exchange charges. The applicable fee depends on maker/taker execution and account tier.

The result makes **cost-adjusted expected reward** a first-class v2.4 filter, especially for short-timeframe trades whose planned price move may be small relative to round-trip costs.

## v2.4 hypotheses created from this baseline

1. Reduce base risk on 1m/3m and prevent fast charts from occupying the whole portfolio.
2. Reject trades whose target does not retain enough net R after estimated fees/slippage.
3. Use an equity high-water mark to progressively reduce new risk as accumulated profit is surrendered.
4. Reduce new risk during statistically abnormal losing clusters rather than continuing at full size.
5. Keep staged stop protection, breakeven and ATR trailing, but backtest the percentages instead of assuming tighter is always better.
6. Judge every change on net return, profit factor, expectancy, max drawdown, profit giveback, MFE/MAE, costs and out-of-sample stability.
