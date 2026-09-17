# Terminal 3.0

BTC-USDT perpetual trading bot plus an isolated research backtesting stack.

## Branch status

- `main`: canonical v2.3 bot baseline.
- `v2.5-research-engine`: current research branch. The production bot files are kept intact, but the active experiment is the v2.5B backtester. Research code is **not** treated as live-ready.
- `VERSION` still refers to the production bot version, not the research candidate.

## Current research candidate

v2.5B keeps the v2.4.2 cost/risk protections and makes one structural change from v2.5A: only **2h+** signals may open positions. Lower timeframes still participate in technical context.

Candidate A used a 1h floor and remained essentially breakeven after costs on the 14 inspected research windows: pooled PF 1.0023, +$8.63 net, 11/14 positive windows and 8,273 trades.

Candidate B was materially stronger on the same 14 inspected windows: **11/14 positive, +$155.42 independent net PnL, PF 1.0660, 2,696 trades, $194.22 modeled fees, and a -9.19% worst window**. The detailed result is stored in `docs/history/V25B_2H_RESEARCH_RESULT.md`.

The strategy is now frozen while warm-up methodology is checked. Run:

`RUN_V25_STABILITY_90D.bat`

That repeats the same 14 known research windows with a 90-day no-trade warm-up and does **not** touch the final reserved historical holdout. Results are written to `backtest_results_v25b_stability_90d/`.

The original 60-day candidate-B run remains reproducible with:

`RUN_V25_RESEARCH.bat`

Research assumptions currently used by the candidate:

- 6 bps fee per side
- 1 bp slippage per side
- 30x leverage setting
- 3.15x aggregate gross-notional cap
- 45% portfolio margin budget
- 0.16R maximum modeled round-trip friction
- 2h minimum entry timeframe

The inspected 2018-2025 windows are research data. They are not blind validation data anymore. One older 180-day holdout remains reserved.

## Production bot

The production/PAPER bot still supports the 30-timeframe Terminal 3.0 signal engine and BloFin integration.

Windows helpers:

- `START_BLOFIN_BOT.bat` — start the bot/dashboard
- `CONFIGURE_BLOFIN.bat` — configure BloFin credentials locally
- `RUN_SELF_TEST.bat` — run the current offline regression suite

Do not commit `.env` or API credentials.

## Repository layout

Core runtime:

- `bot.py`, `app.py`, `automation.py`
- `blofin_client.py`, `config.py`, `risk.py`, `reporting.py`
- `strategy.py`, `ta_engine.py`
- `static/`, `templates/`

Research/backtesting:

- `backtest_v24.py` — base historical engine
- `backtest_v24_guarded.py` — cost/profit/loss protection layer
- `backtest_v24_selective.py` — anti-churn/rolling-edge layer
- `backtest_v24_efficient.py` — 15m+ efficient baseline used by v2.5
- `backtest_v25.py` — current frozen 2h+ candidate
- `backtest_v25_research.py` — 14-window research/stability battery
- `backtest_oos_v242.py` — shared window-planning/report helpers
- `backtest_full_cpu_runner.py`, `backtest_progress_runner.py` — reusable parallel data/analysis helpers
- `portfolio_cap.py` — shared exposure/margin-cap layer

Historical one-off launchers and obsolete v2.1/v2.4 instructions are intentionally removed from this branch. They remain available in git history.

## Validation notes

The v2.4.2 frozen candidate finished effectively around breakeven across the inspected OOS + holdout windows after modeled costs. Candidate v2.5A also remained effectively breakeven. v2.5B is the first candidate with a meaningfully positive research margin, but it is still execution-sensitive and has not yet consumed its final blind holdout.

The current research gate is documented in `docs/V25_RESEARCH_PLAN.md`.

## Security

Use a dedicated exchange API key with only the permissions the bot actually needs. Never commit secrets. Real-money trading should remain disabled until the research candidate survives independent validation plus perpetual-specific funding, maintenance-margin, liquidation and execution modeling.
