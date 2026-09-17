# v2.5 research gate

v2.4.2 is frozen as the baseline. Its final blind holdout produced pooled PF 0.9889 over 8,287 trades and did not clear the robustness gate.

For v2.5, the already-inspected 2018-2025 windows are research data, not blind validation data. One older 180-day BTC window remains reserved and must not be inspected until a v2.5 candidate is frozen.

## Candidate A — 1h+ entries

Candidate A kept the same signal engine, cost model, risk protections, portfolio cap, and leverage envelope, but required entry timeframe >= 1h.

Its 14-window research result was still effectively breakeven: pooled PF 1.0023, +$8.63 independent net PnL, 8,273 trades, $388.69 modeled fees, and 11/14 positive windows. It improved trade/fee efficiency and window consistency versus v2.4.2, but did not create a sufficiently wide edge. The reserved holdout was therefore not consumed.

The realized trade diagnostic showed 1h entries dominating the candidate: 5,608 trades, -$226.43 net and $287.35 in fees. Several 2h+ groups were positive. This diagnostic is not itself a valid backtest because removing 1h positions changes portfolio state.

See `history/V25A_1H_RESEARCH_RESULT.md` for the full result.

## Candidate B — 2h+ entries

Candidate B makes exactly one additional structural change: raise the minimum entry timeframe from 1h to **2h**. Lower timeframes remain available to TA/context. All other cost, risk, exit, leverage and portfolio-cap logic remains unchanged.

Research sequence:

1. Re-run the same 14 inspected 180-day windows with the 2h+ candidate.
2. Require a materially better margin than breakeven before touching the reserved holdout. PF should be comfortably above 1 after modeled costs, drawdowns should remain controlled, and the result should not depend on one window.
3. If candidate B remains weak, reject it and continue architecture research only on the inspected research corpus.
4. If candidate B is strong enough, freeze it before consuming the reserved earliest 180-day holdout exactly once.
5. Only after successful independent validation move to perpetual-specific funding, maintenance margin/liquidation, execution realism, gap handling, and demo/PAPER validation.
