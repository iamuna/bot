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

Removing the single best window still leaves about +$59.33 and pooled PF about 1.028, so the result is not entirely dependent on one lucky period. It is nevertheless still a modest edge, not a wide safety margin. See `history/V25B_2H_RESEARCH_RESULT.md`.

## Holdout-boundary correction

The original v2.5 plan described the 180 days immediately before the oldest research evaluation window as a future blind holdout. That was too strong: the oldest research window used a 60-day no-trade warm-up, so the final 60 days of that earlier interval were already loaded into indicator state. They were not traded, but their prices influenced research-window indicators.

The original 14-window/60-day research run first loaded early BTC history at approximately **2018-03-22 11:02 UTC**. Data earlier than that boundary is the cleanest untouched segment remaining in this CSV. The final validation interval will therefore be defined inside that earlier segment after warm-up methodology is frozen; it will be shorter than the previously planned 180 days.

## Warm-up stability gate

The TA engine requires 200 bars before EMA200 is included. Sixty days fully initializes the dominant 2h-6h entry horizons, but supplies only 180 bars on 8h and fewer bars on longer horizons that still participate in cross-timeframe context.

A 90-day stability check is useful, but running 90-day warm-up on all 14 windows would load new early BTC history and contaminate the remaining untouched segment. The safe check therefore uses **13 already-seen research windows with a 90-day warm-up** and deliberately omits the oldest research window.

Run `RUN_V25_STABILITY_90D.bat`.

The runner itself enforces two allowed modes only: the original 14-window/60-day research run, or the safe 13-window/90-day stability check. It refuses requests that would load history earlier than the original research boundary.

Decision sequence:

1. Candidate B strategy settings stay frozen at the completed 2h configuration.
2. Re-run 13 already-seen windows with a 90-day warm-up only.
3. If the result changes materially or collapses toward breakeven, do not consume any untouched early history; audit initialization/context methodology first.
4. If candidate B remains materially positive with controlled drawdown, freeze both strategy and warm-up methodology.
5. Define the final validation interval strictly before the original research-history boundary and run it exactly once.
6. After that, no remaining historical BTC period in this CSV should be described as blind validation data for this candidate.
7. Only after successful independent validation move to perpetual-specific funding, maintenance margin/liquidation, execution realism, gap handling, and demo/PAPER validation.
