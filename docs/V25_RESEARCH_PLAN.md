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

The original 14-window/60-day research run first loaded early BTC history at approximately **2018-03-22 11:02 UTC**. Data earlier than that timestamp is the clean untouched segment remaining in this CSV.

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

Candidate B strategy parameters and the 90-day warm-up methodology are now frozen. No more timeframe, threshold, risk, exit, fee, slippage, leverage or warm-up tuning is permitted before final validation.

## Final untouched early-data validation

Run:

`RUN_V25_FINAL_VALIDATION.bat`

The final runner derives its boundary from the original research protocol rather than from a hard-coded date:

1. Reconstruct the earliest timestamp ever loaded by the original 14-window/60-day v2.5 research run.
2. End evaluation exactly one minute before that research-history boundary.
3. Use the earliest available BTC candles as a 90-day no-trade warm-up.
4. Begin evaluation immediately after that 90-day warm-up.
5. Refuse any run that overlaps the original research-history boundary.

With the current Binance CSV, this produces a shorter-than-180-day early validation interval because the dataset itself starts in August 2017. That is intentional; preserving untouched data is more important than forcing an arbitrary 180-day length.

Decision sequence:

1. Run the frozen final early-data validation exactly once.
2. Record the result regardless of whether it is favorable.
3. Do not retune against that interval afterward and relabel it as validation.
4. After this run, no historical period in the current CSV remains untouched for v2.5B.
5. Next, run a continuous chronological replay over the full available history to audit reset/warm-up artifacts.
6. Then add perpetual-specific funding, maintenance margin/liquidation, execution realism and gap handling.
7. Obtain genuinely fresh data (newer BTC history or exchange-specific perpetual history) for the next independent out-of-sample check.
8. Only after those stages move to demo/PAPER validation. Real money remains out of scope until all validation layers are complete.
