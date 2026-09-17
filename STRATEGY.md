# Strategy status

## Production baseline

The runtime bot on this branch is still the v2.3 30-timeframe Terminal 3.0 system. `VERSION` therefore remains `2.3`. Research changes are isolated in the historical backtest classes and are not silently wired into LIVE trading.

## Current research candidate: v2.5

v2.5 inherits the full v2.4.2 Efficient stack and changes one structural rule:

**Only signals from 1h and higher may open positions.**

The 1m/3m/5m/15m/30m data still participate in technical analysis and cross-timeframe context; they simply cannot create new v2.5 entries.

Inherited controls include:

- modeled fees and slippage in trade economics;
- maximum round-trip friction of 0.16R;
- minimum net-target hurdle inherited from the selective layer;
- rolling closed-trade edge throttling;
- drawdown-based new-risk reduction and lockout;
- portfolio planned-risk limits;
- aggregate gross-notional and margin-use caps;
- staged stop protection, breakeven/trailing and time exits.

The current research runner uses 6 bps fee + 1 bp slippage per side, a 30x leverage setting, 3.15x aggregate gross exposure cap and 45% margin budget. Under that gross cap, 30x changes margin efficiency rather than allowing 30x account notional.

## Validation status

v2.4.2 did not clear its final robustness gate. Across the inspected independent windows it was approximately breakeven after costs, which is too execution-sensitive to treat as a reliable edge.

Those inspected windows are now research data for v2.5. The v2.5 candidate must be frozen before the final reserved historical holdout is touched.

Even a successful historical holdout will not make the system live-ready. Remaining validation work includes perpetual-specific funding, maintenance margin/liquidation, execution realism, gap handling, and demo/PAPER behavior.

See `docs/V25_RESEARCH_PLAN.md` and `docs/history/VALIDATION_V242_FINAL_HOLDOUT.md` for the current research gate and prior result.
