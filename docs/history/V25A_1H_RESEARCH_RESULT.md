# v2.5A 1h-entry research result

Candidate A changed only the entry floor from 15m+ to **1h+** while keeping the v2.4.2 cost/risk stack unchanged.

Research corpus: the same 14 already-inspected 180-day BTC windows used for architecture research. This was **not** a blind validation run. The reserved earliest holdout remained untouched.

Completed result:

- Positive windows: 11 / 14
- Negative windows: 3 / 14
- Sum of independent net PnL: +$8.63
- Mean 180-day return: +0.062%
- Median 180-day return: +2.125%
- Best window: +11.80%
- Worst window: -12.54%
- Worst window max drawdown: 15.13%
- Pooled trades: 8,273
- Pooled win rate: 46.198%
- Pooled profit factor: 1.0023
- Total modeled fees: $388.69
- Recorded replay-stage runtime: 1,355.353 seconds (22m 35s); the old runner did not include CSV loading in that field.

Compared with v2.4.2 across the same 14 inspected windows, candidate A reduced trades from 19,425 to 8,273 and fees from about $701.22 to $388.69, while net PnL stayed almost unchanged (+$8.79 vs +$8.63). Window consistency improved from 7/14 positive to 11/14 positive, but the pooled edge remained effectively breakeven and the remaining losing windows were still large.

Timeframe diagnosis from the realized v2.5A trades:

- 1h: 5,608 trades, -$226.43 net, $287.35 fees
- 2h: 1,084 trades, +$113.13 net
- 3h: 592 trades, +$23.43 net
- 4h: 319 trades, +$46.70 net
- 6h: 203 trades, -$22.94 net
- 8h: 164 trades, +$12.17 net
- 12h: 126 trades, -$22.29 net
- 16h: 94 trades, +$24.71 net
- 1d and above: small samples, collectively positive in this run

Filtering the completed trade list after the fact is **not** a valid counterfactual backtest because removing 1h positions changes slot availability and portfolio state. It is only a research diagnostic. The next candidate therefore makes one clean structural change and reruns the full simulator: raise the minimum entry timeframe from 1h to 2h.
