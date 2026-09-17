# v2.5 research gate

v2.4.2 is frozen as the baseline. Its final blind holdout produced pooled PF 0.9889 over 8,287 trades and did not clear the robustness gate.

For v2.5, the already-inspected 2018-2025 windows are research data, not blind validation data.

## Candidate A — 1h+ entries

Candidate A kept the same signal engine, cost model, risk protections, portfolio cap, and leverage envelope, but required entry timeframe >= 1h.

Its 14-window research result was still effectively breakeven: pooled PF 1.0023, +$8.63 independent net PnL, 8,273 trades, $388.69 modeled fees, and 11/14 positive windows. It improved trade/fee efficiency and window consistency versus v2.4.2, but did not create a sufficiently wide edge.

The realized trade diagnostic showed 1h entries dominating the candidate: 5,608 trades, -$226.43 net and $287.35 in fees. Several 2h+ groups were positive. This diagnostic is not itself a valid backtest because removing 1h positions changes portfolio state.

See `history/V25A_1H_RESEARCH_RESULT.md` for the full result.

## Candidate B — 2h+ entries

Candidate B makes exactly one additional structural change: raise the minimum entry timeframe from 1h to **2h**. Lower timeframes remain available to TA/context. All other cost, risk, exit, leverage and portfolio-cap logic remains unchanged.

The first 14-window candidate-B run was materially stronger than candidate A:

- 11 / 14 positive windows
- +$155.42 sum of independent net PnL
- pooled PF 1.0660
- 2,696 trades
- $194.22 modeled fees
- mean 180-day return +1.110%
- median 180-day return +1.235%
- best window +9.61%
- worst window -9.19%
- worst window max drawdown 10.50%

See `history/V25B_2H_RESEARCH_RESULT.md`.

## Holdout-boundary correction

The original v2.5 plan described the 180 days immediately before the oldest research evaluation window as a future blind holdout. That was too strong: the oldest research window used a 60-day no-trade warm-up, so the final 60 days of that earlier interval were already loaded into indicator state. They were not traded, but their prices influenced research-window indicators.

The original 14-window/60-day research run first loaded early BTC history at approximately **2018-03-22 11:02 UTC**. Data earlier than that timestamp was the clean untouched segment remaining in this CSV before the final validation run.

## Warm-up stability gate — PASSED

The safe stability test reran only the 13 already-seen newest research windows with a **90-day warm-up**, leaving the untouched early segment unconsumed.

Result:

- 10 / 13 positive windows
- +$224.93 sum of independent net PnL
- pooled PF 1.1054
- 2,502 trades
- $174.00 modeled fees
- mean 180-day return +1.730%
- median 180-day return +1.330%
- best window +7.80%
- worst window -7.10%
- worst window max drawdown 9.80%

For the same 13 windows, the original 60-day warm-up produced about +$133.36 and PF 1.0590. All 13 windows preserved their positive/negative sign when warm-up changed, with return correlation about 0.859. Magnitudes moved materially, so initialization still matters, but the candidate did not collapse or reverse. See `history/V25B_90D_STABILITY_RESULT.md`.

Candidate B strategy parameters and the 90-day warm-up methodology were frozen after this gate.

## Final untouched early-data validation — COMPLETED

The frozen candidate was run exactly once on the remaining untouched early interval.

Protocol:

1. Reconstructed the earliest timestamp ever loaded by the original 14-window/60-day v2.5 research run.
2. Ended evaluation exactly one minute before that research-history boundary.
3. Used the earliest available BTC candles as a 90-day no-trade warm-up.
4. Began evaluation immediately after that warm-up.
5. Loaded no candle at or after the original research-history floor.

Observed interval:

- warm-up start: 2017-08-17 04:00 UTC
- evaluation start: 2017-11-15 04:00 UTC
- evaluation end: 2018-03-22 11:01 UTC
- original research floor: 2018-03-22 11:02 UTC
- overlap with prior v2.5 research history: false

Result:

- start equity: $1,000.00
- end equity: $1,059.46
- return: **+5.95%**
- net PnL: **+$59.46**
- 134 trades
- 53.73% win rate
- profit factor: **1.387**
- max drawdown: **5.62%**
- average R: **+0.177**
- $7.17 modeled fees

No numeric pass/fail threshold had been pre-registered for this gate, so the correct record is that the independent holdout produced a positive result under the frozen assumptions. See `history/V25B_FINAL_UNTOUCHED_VALIDATION_RESULT.md`.

The early interval is now permanently consumed. No historical BTC period in the current CSV remains untouched for v2.5B.

## Current gate — continuous chronological replay

The next task is a single continuous stateful replay over the full available BTC history.

Purpose:

- audit whether the rolling independent-window methodology created reset/warm-up artifacts;
- observe the candidate across changing market regimes without periodic state resets;
- measure aggregate and chronological performance under the exact frozen v2.5B strategy settings.

Protocol requirements:

1. Keep all v2.5B strategy settings frozen.
2. Use one 90-day no-trade warm-up at the beginning of the dataset.
3. Replay all remaining candles continuously after warm-up.
4. Do not reset TA, rolling-edge, drawdown or portfolio state between arbitrary windows.
5. Preserve the same fee, slippage, risk, exit, leverage and portfolio-cap assumptions.
6. Produce full-history aggregate metrics plus chronological period breakdowns.
7. Treat this as a historical audit, **not** a blind validation run.
8. Do not silently optimize v2.5B from this replay. A materially changed strategy becomes a new named candidate and requires genuinely fresh independent data.

## After chronological replay

1. Add perpetual-specific funding modeling.
2. Add maintenance-margin and liquidation modeling.
3. Improve execution realism and gap handling.
4. Obtain genuinely fresh BTC history or exchange-specific perpetual history for the next independent out-of-sample check.
5. Align demo/PAPER execution with the research assumptions and validate prospectively.
6. Real-money deployment remains out of scope until all validation and execution layers are complete.
