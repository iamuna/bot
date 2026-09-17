# Terminal 3.0

BTC-USDT perpetual trading bot plus an isolated research backtesting stack.

## Branch status

- `main`: canonical v2.3 bot baseline.
- `v2.5-research-engine`: current research branch. The production bot files are kept intact, but the active experiment is the v2.5 backtester. Research code is **not** treated as live-ready.
- `VERSION` still refers to the production bot version, not the research candidate.

## Current research candidate

v2.5 keeps the v2.4.2 cost/risk protections and makes one structural change: only **1h+** signals may open positions. Lower timeframes still participate in technical context.

Run the research battery on Windows with:

`RUN_V25_RESEARCH.bat`

The runner expects a BTC 1-minute CSV and writes results to `backtest_results_v25_research/`.

Research assumptions currently used by the candidate:

- 6 bps fee per side
- 1 bp slippage per side
- 30x leverage setting
- 3.15x aggregate gross-notional cap
- 45% portfolio margin budget
- 0.16R maximum modeled round-trip friction
- 1h minimum entry timeframe

The inspected 2018-2025 windows are research data. They are not blind validation data anymore. One older holdout remains reserved.

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
- `backtest_v25.py` — current 1h+ candidate
- `backtest_v25_research.py` — 14-window research battery
- `backtest_oos_v242.py` — shared window-planning/report helpers
- `backtest_full_cpu_runner.py`, `backtest_progress_runner.py` — reusable parallel data/analysis helpers
- `portfolio_cap.py` — shared exposure/margin-cap layer

Historical one-off launchers and obsolete v2.1/v2.4 instructions are intentionally removed from this branch. They remain available in git history.

## Validation notes

The v2.4.2 frozen candidate finished effectively around breakeven across the inspected OOS + holdout windows after modeled costs, so it was not considered robust enough for real money. See `docs/history/VALIDATION_V242_FINAL_HOLDOUT.md`.

The next research gate is documented in `docs/V25_RESEARCH_PLAN.md`.

## Security

Use a dedicated exchange API key with only the permissions the bot actually needs. Never commit secrets. Real-money trading should remain disabled until the research candidate survives independent validation plus perpetual-specific funding, maintenance-margin, liquidation and execution modeling.
