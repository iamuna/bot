# Terminal 3.0

BTC-USDT perpetual trading bot plus an isolated research backtesting stack.

## Branch status

- `main`: canonical v2.3 bot baseline.
- `v2.5-research-engine`: current research branch. The production bot files are kept intact, but the active experiment is the frozen v2.5B backtester. Research code is **not** treated as live-ready.
- `VERSION` still refers to the production bot version, not the research candidate.

## Current research candidate

v2.5B keeps the v2.4.2 cost/risk protections and allows only **2h+** signals to open positions. Lower timeframes still participate in technical context.

Candidate A (1h+) remained essentially breakeven after costs. Candidate B (2h+) was materially stronger on the original 14 inspected windows: 11/14 positive, +$155.42 independent net PnL, PF 1.0660, 2,696 trades and $194.22 modeled fees.

The follow-up **90-day warm-up stability check** reran the same 13 safe, already-seen windows and improved to **10/13 positive, +$224.93 net, PF 1.1054, 2,502 trades, $174.00 fees, and -7.10% worst window**. All 13 windows kept the same positive/negative sign versus the 60-day warm-up comparison. See `docs/history/V25B_90D_STABILITY_RESULT.md`.

The strategy and 90-day warm-up methodology are now frozen. The next run is the final untouched early-data validation:

`RUN_V25_FINAL_VALIDATION.bat`

This runner automatically uses the earliest available BTC history for a 90-day no-trade warm-up, then evaluates only candles that end **strictly before the first timestamp ever loaded by the original v2.5 research run**. It refuses to overlap the known research-history boundary. Results are written to `backtest_results_v25b_final_validation/`.

The original research/stability runs remain reproducible with:

- `RUN_V25_RESEARCH.bat` — original 14-window/60-day candidate-B research battery
- `RUN_V25_STABILITY_90D.bat` — safe 13-window/90-day stability battery

Research assumptions currently used by the frozen candidate:

- 6 bps fee per side
- 1 bp slippage per side
- 30x leverage setting
- 3.15x aggregate gross-notional cap
- 45% portfolio margin budget
- 0.16R maximum modeled round-trip friction
- 2h minimum entry timeframe
- 90-day final-validation warm-up

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
- `backtest_v25.py` — frozen 2h+ candidate
- `backtest_v25_research.py` — locked research/stability battery
- `backtest_v25_final_validation.py` — untouched early-data validation runner
- `backtest_oos_v242.py` — shared window-planning/report helpers
- `backtest_full_cpu_runner.py`, `backtest_progress_runner.py` — reusable parallel data/analysis helpers
- `portfolio_cap.py` — shared exposure/margin-cap layer

Historical one-off launchers and obsolete v2.1/v2.4 instructions are intentionally removed from this branch. They remain available in git history.

## Validation notes

v2.4.2 and v2.5A were approximately breakeven after costs. v2.5B is the first candidate with a materially positive research margin and has now passed the warm-up stability gate. It still has not passed its final untouched early-data validation, and even a successful result will not make it live-ready.

Remaining work after historical validation includes perpetual-specific funding, maintenance margin/liquidation, execution realism, gap handling, continuous chronological replay, and demo/PAPER behavior.

The current gate is documented in `docs/V25_RESEARCH_PLAN.md`.

## Security

Use a dedicated exchange API key with only the permissions the bot actually needs. Never commit secrets. Real-money trading should remain disabled until the research candidate survives independent validation plus perpetual-specific execution and liquidation modeling.
