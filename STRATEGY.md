# Strategy status

## Production baseline

The runtime bot on this branch is still the v2.3 30-timeframe Terminal 3.0 system. `VERSION` therefore remains `2.3`. Research changes are isolated in the historical backtest classes and are not silently wired into LIVE trading.

## Current research candidate: v2.5B

v2.5B inherits the full v2.4.2 Efficient stack and changes one structural rule from candidate A:

**Only signals from 2h and higher may open positions.**

Lower timeframes still participate in technical analysis and cross-timeframe context; they simply cannot create new v2.5B entries.

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

## Candidate A result

The 1h+ candidate reduced trading activity and fees substantially but still finished essentially breakeven on the 14 inspected research windows: pooled PF 1.0023, +$8.63 independent net PnL, 8,273 trades, $388.69 modeled fees, and 11/14 positive windows.

Its realized 1h entries dominated activity and lost $226.43 net across 5,608 trades. That observation is only a diagnostic, not a valid filtered backtest. Candidate B therefore reruns the full simulator with the entry floor raised to 2h rather than deleting 1h trades after the fact.

## Validation status

The inspected historical windows are research data. The earliest reserved 180-day holdout remains untouched and must stay untouched until a candidate is frozen with a materially stronger after-cost margin than breakeven.

Even a successful historical holdout will not make the system live-ready. Remaining validation work includes perpetual-specific funding, maintenance margin/liquidation, execution realism, gap handling, and demo/PAPER behavior.

See `docs/V25_RESEARCH_PLAN.md`, `docs/history/V25A_1H_RESEARCH_RESULT.md`, and `docs/history/VALIDATION_V242_FINAL_HOLDOUT.md`.
