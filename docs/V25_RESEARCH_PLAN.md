# v2.5 research gate

v2.4.2 is now frozen as the baseline. Its final blind holdout produced pooled PF 0.9889 over 8,287 trades and therefore did not clear the robustness gate.

For v2.5, the already-inspected 2018-2025 windows are now research data, not blind validation data. One older 180-day BTC window remains reserved and must not be inspected until a v2.5 candidate is frozen.

Initial structural hypothesis for v2.5: keep the same signal engine, cost model, risk protections, portfolio cap, and leverage envelope, but require entry timeframe >= 1h. This is based on a repeated cross-period diagnostic: 15m and 30m were loss-making in both the first OOS battery and the final holdout, while several 1h-4h groups were positive. This is a broad architecture change rather than per-timeframe cherry-picking.

Research sequence:

1. Build v2.5 1h+ candidate without changing the TA weights or exit logic.
2. Re-run the 14 already-inspected 180-day windows as a research battery.
3. Require a materially better margin than breakeven before touching the reserved earliest holdout; target robustness is not a fixed optimization objective, but PF should be comfortably above 1 after costs and results should not depend on one window.
4. If the research battery is weak, reject the candidate instead of tuning the reserved holdout.
5. If the candidate is frozen, run the final reserved 180-day blind window once.
6. Only after that move to perpetual-specific funding, maintenance margin, liquidation, and execution realism.
