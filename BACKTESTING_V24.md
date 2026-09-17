# Terminal 3.0 v2.4 Backtesting Engine

This branch adds a research backtester for the proposed v2.4 adaptive-position architecture while keeping `main` v2.3 untouched.

## What it tests

The engine reuses the Terminal 3 technical-analysis logic and builds the full 30-timeframe universe from one-minute BTC OHLCV data. It is designed to test the v2.4 ideas discussed during the v2.3 paper run:

- timeframe-weighted risk budgets;
- quality-adjusted sizing;
- regime-dependent sizing;
- same-direction exposure reduction;
- 10-position global cap;
- horizon slot caps so 1m/3m cannot consume every position;
- staged stop protection;
- breakeven at approximately +1R;
- ATR-based trailing stops;
- maximum holding times;
- MFE/MAE measurement;
- realistic entry/exit fees and configurable slippage;
- per-timeframe performance and rejection logging.

The final v2.3 paper baseline is recorded in `V23_PAPER_BASELINE_20260917.md`.

## Report-driven guarded variant

`backtest_v24_guarded.py` adds three experimental protections on top of the base v2.4 engine so they can be A/B tested instead of blindly merged into the live bot:

1. **Cost-adjusted target gate.** A trade can be rejected if its planned target does not retain a configurable minimum net R after estimated round-trip fees and slippage.
2. **Equity high-water profit guard.** Once equity has made a meaningful gain, new-position risk is progressively reduced as a larger share of the accumulated peak profit is surrendered. The current research tiers are 20% / 35% / 50% / 65% giveback with risk multipliers 1.00 / 0.75 / 0.50 / 0.25 / 0.10 beyond the final tier.
3. **Loss-cluster throttle.** New risk is reduced after 3, 5 and 7 consecutive losing closes instead of continuing at full size through a regime transition.

These thresholds are hypotheses created from the first v2.3 paper run. They are deliberately configurable and must be validated on broad history and untouched out-of-sample periods before any live use.

## Portfolio exposure and leverage

Leverage is now an explicit research parameter rather than a hard-coded strategy assumption. The Windows comparison launcher currently defaults to **30x** because we want to test whether higher leverage improves margin efficiency, but leverage is separated from market exposure.

The default portfolio envelope is:

- maximum gross BTC notional: **3.15x marked-to-market account equity** across all simultaneous positions combined;
- maximum initial-margin budget: **45% of marked-to-market account equity** across the portfolio;
- maximum planned open stop-risk: **11.5% of equity**;
- maximum positions: **10**.

The effective gross entry cap is the smaller of the explicit 3.15x gross cap and the notional that can be supported by the margin budget at the selected leverage. This means raising the leverage setting from 7x to 30x does **not** automatically raise allowed market exposure from 3.15x to 13.5x. At 30x, a fully used 3.15x gross envelope requires about 10.5% initial margin, leaving the rest of the account outside the initial-margin allocation.

This design lets the research isolate leverage as a margin-efficiency variable rather than confusing leverage with risk sizing. Position risk is still determined primarily by stop distance, timeframe budget, quality, regime, existing correlated risk and portfolio caps.

The comparison runner accepts:

```bash
python backtest_progress_runner.py btc_1m.zip --last-days 180 --leverage 30 --gross-cap-x 3.15 --portfolio-margin-pct 45
```

The runner currently restricts the research leverage setting to 1x-30x. That is a project research limit, not a claim about the exchange's maximum leverage.

**Important:** liquidation mechanics are not yet modeled. A leverage result must not be interpreted as live-safe until exchange-specific maintenance-margin tiers, margin mode and liquidation behavior are added and tested.

## Look-ahead protection

Signals are created only after a timeframe candle has fully closed. Orders are entered at the **next 1-minute candle open**, with configurable adverse slippage. Higher-timeframe analysis only sees candles that were closed at that historical moment.

If a 1-minute candle touches both a stop and a target, the simulator takes the conservative path and assumes the stop was hit first.

## Input format

Use a chronological or unsorted one-minute BTC OHLCV CSV. ZIP files containing one CSV are also accepted. The loader accepts common column names such as:

`timestamp, open, high, low, close, volume`

and Binance-style headers such as `Open time` and `Quote asset volume`.

Timestamps may be Unix seconds, Unix milliseconds, or ISO-8601 strings.

Example:

```csv
timestamp,open,high,low,close,volume
1700000000000,36500,36530,36480,36510,12.5
```

For meaningful 1m/3m research, use a large continuous dataset. Longer history also allows more of the higher-timeframe indicators to warm up.

## Run on Windows

For the current base-vs-guarded comparison with progress and ETA, run:

`RUN_COMPARE_V24.bat`

The launcher asks for the BTC CSV/ZIP. Optional command-line arguments are data path, number of days and leverage, for example:

```bat
RUN_COMPARE_V24.bat C:\data\BTCUSD_1m_Binance.zip 180 30
```

The default comparison assumptions are 180 days, 30x leverage setting, 3.15x gross portfolio cap, 45% portfolio margin budget, 6 bps fee per side and 1 bp slippage per side.

Direct base adaptive engine:

```bash
python backtest_v24.py btc_1m.csv --equity 1000 --fee-bps 6 --slippage-bps 1
```

Guarded report-driven variant:

```bash
python backtest_v24_guarded.py btc_1m.csv --equity 1000 --fee-bps 6 --slippage-bps 1 --min-net-target-r 0.75 --profit-guard-activation 3
```

For the portfolio-cap/leverage model, use `backtest_progress_runner.py` / `RUN_COMPARE_V24.bat`; the direct legacy entry points do not install the portfolio-cap research layer.

Results are written to `backtest_results/` as JSON plus a trade-level CSV.

## Current v2.4 research profile

Timeframe base-risk budgets start small on fast charts and increase with horizon. Examples:

- 1m: 0.30%
- 3m: 0.40%
- 5m: 0.50%
- 15m: 0.65%
- 1h: 0.85%
- 2h–4h: 1.00%
- 6h–12h: 1.10%
- 16h–1d: 1.20%
- 2d+: 1.25%

Quality and regime multipliers adjust this budget, while existing same-direction risk reduces the size of additional correlated BTC positions.

Position slots are initially divided as:

- scalp 1m/3m/5m: 4;
- intraday 15m–1h: 3;
- swing 2h–12h: 2;
- macro 16h+: 1.

These are research parameters, not claims that they are optimal.

## Important limitations

This backtester is deliberately conservative but still cannot reproduce exchange microstructure perfectly. It does not yet reconstruct historical funding payments, order-book depth, partial fills, liquidation mechanics, exchange outages, or queue priority. Its fee/slippage assumptions should therefore be stress-tested rather than treated as exact.

The Binance history used for the first comparison is useful for strategy A/B research, but eventual validation should use perpetual-market data and historical funding if available because the live target is a perpetual futures market.

The purpose is to compare strategy variants under identical historical conditions, not to promise future returns.

## Recommended research sequence

Run broad history first, then split the sample into development and untouched out-of-sample periods. Tune parameters only on the development set. After choosing a profile, validate it on the untouched period, then PAPER, then BloFin DEMO.
