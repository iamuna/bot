# Terminal 3 v2.4.2 final holdout result

Frozen strategy: v2.4.2 Efficient. No strategy parameters were changed for this holdout.

Final blind holdout battery: 6 independent 180-day windows, 2018-05-21 through 2021-05-05, $1,000 reset per window, 6 bps fee + 1 bp slippage per side.

Summary from the completed run:

- Positive windows: 3 / 6
- Negative windows: 3 / 6
- Sum of independent net PnL: -$25.34
- Mean 180-day return: -0.423%
- Median 180-day return: +0.970%
- Best window: +7.39%
- Worst window: -12.77%
- Worst window max drawdown: 15.22%
- Pooled trades: 8,287
- Pooled win rate: 44.672%
- Pooled profit factor: 0.9889
- Total modeled fees: $297.77

Interpretation: the frozen candidate did not clear the final holdout robustness gate. It remained close to breakeven, but the edge is too thin to treat as validated. The earlier 8-window OOS battery had pooled PF 1.0127 and +$34.13 independent PnL; combining those 14 independent windows gives roughly +$8.79 net across 19,425 trades, about $701 in modeled fees, and pooled PF about 1.0018. This is effectively breakeven and execution-sensitive.

Research diagnostic only (not a valid counterfactual backtest): across the first OOS battery and final holdout, 15m and 30m entries were repeatedly loss-making, while several 1h-4h groups were positive. Because the holdout has now been inspected, it must not be reused as a blind validation set for a redesigned strategy.

Validation caveat discovered after the run: the independent-window harness uses only a 60-day no-trade warm-up. This is enough for lower timeframes but not for stable long-horizon context across all 30 reconstructed timeframes. Future validation work should audit warm-up sensitivity and include a continuous chronological portfolio run with no 180-day resets before any live-readiness conclusion.
