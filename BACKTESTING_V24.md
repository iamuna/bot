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

## Look-ahead protection

Signals are created only after a timeframe candle has fully closed. Orders are entered at the **next 1-minute candle open**, with configurable adverse slippage. Higher-timeframe analysis only sees candles that were closed at that historical moment.

If a 1-minute candle touches both a stop and a target, the simulator takes the conservative path and assumes the stop was hit first.

## Input format

Use a chronological or unsorted one-minute BTC OHLCV CSV. The loader accepts common column names such as:

`timestamp, open, high, low, close, volume`

Timestamps may be Unix seconds, Unix milliseconds, or ISO-8601 strings.

Example:

```csv
timestamp,open,high,low,close,volume
1700000000000,36500,36530,36480,36510,12.5
```

For meaningful 1m/3m research, use a large continuous dataset. Longer history also allows more of the higher-timeframe indicators to warm up.

## Run on Windows

Drag the CSV onto:

`RUN_BACKTEST_V24.bat`

or run:

```bat
RUN_BACKTEST_V24.bat C:\data\btc_1m.csv
```

Direct Python usage:

```bash
python backtest_v24.py btc_1m.csv --equity 1000 --fee-bps 5 --slippage-bps 1
```

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

The purpose is to compare strategy variants under identical historical conditions, not to promise future returns.

## Recommended research sequence

Run broad history first, then split the sample into development and untouched out-of-sample periods. Tune parameters only on the development set. After choosing a profile, validate it on the untouched period, then PAPER, then BloFin DEMO.
