# v2.1 strategy — 30-timeframe multi-position engine

## 1. Timeframes

The strategy evaluates 30 intervals.

Native BloFin candles:

`1m 3m 5m 15m 30m 1h 2h 4h 6h 8h 12h 1d 3d 1w 1M`

Constructed locally from native OHLCV candles:

`45m 3h 16h 2d 4d 5d 6d 2w 3w 2M 3M 4M 5M 6M 12M`

Any enabled timeframe can create a trade. There is no master entry timeframe.

A constructed interval cannot generate a permanent entry until enough closed source candles exist to complete that constructed bar.

## 2. Technical score

Each timeframe receives a roughly -100 to +100 score built from four independent families:

- **Trend — 32%:** EMA20/50/200 structure, regression slope and ADX directional pressure.
- **Momentum — 23%:** RSI, MACD histogram, Stochastic and ROC.
- **Structure — 27%:** breakout/breakdown behavior, range position, Bollinger location and regression structure.
- **Flow — 18%:** relative volume, VWAP position, OBV pressure and CMF.

Aggressive mode reduces the score threshold and slightly increases score sensitivity. It does not disable the execution/risk guards.

## 3. Regime detection

The engine distinguishes conditions such as:

- BREAKOUT UP / BREAKOUT DOWN
- TREND UP / TREND DOWN
- RANGE
- SQUEEZE
- HIGH VOLATILITY
- MIXED

Range signals generally need breakout confirmation unless quality is unusually high. Severe EMA20/ATR overextension is also penalized.

## 4. Hierarchical multi-timeframe model

Thirty correlated intervals are not treated as 30 independent votes. They are summarized first into five horizons:

- **Minutes:** 1m / 3m / 5m / 15m / 30m / 45m
- **Hours:** 1h / 2h / 3h / 4h / 6h / 8h / 12h / 16h
- **Days:** 1d / 2d / 3d / 4d / 5d / 6d
- **Weeks:** 1w / 2w / 3w
- **Months:** 1M / 2M / 3M / 4M / 5M / 6M / 12M

The current horizon weights are:

- Minutes 14%
- Hours 29%
- Days 28%
- Weeks 16%
- Months 13%

Coverage and per-timeframe importance modify the effective contribution. Very short intervals and extremely long intervals are intentionally downweighted relative to the central 1h–1d structure.

A candidate's confluence combines its own horizon, the whole-market score and higher-horizon context. Counter-trend signals can still trade when their quality is high enough; very strong broad opposition blocks ordinary-quality signals.

## 5. Entry trigger

A candidate exists only when a **closed candle** on an enabled timeframe creates a fresh Terminal score-cross, breakout or breakdown marker.

The key `{timeframe, candle timestamp, side}` is stored after execution so polling cannot repeatedly place the same trade. That is duplicate protection, not a frequency limit.

## 6. Multiple independent positions

PAPER mode creates a separate simulated position for every accepted setup.

DEMO/LIVE expects BloFin Hedge + Multi-Position mode. New opening orders omit `positionId`, so each accepted setup can create its own independent position. The bot resolves the generated `positionId` through BloFin Order Detail/current positions, records it, and uses that ID when an individual bot-owned position must be closed.

Pending position-ID resolution reserves the trade's planned risk so a temporarily unresolved fill cannot let the next trade bypass the portfolio-risk cap.

When an exchange position disappears from the open-position list, stale bot ownership/risk tracking is removed automatically.

BloFin's exchange-level Multi-Position limit remains 10 positions per instrument.

## 7. Risk and execution

There is no max-trades-per-day rule and no cooldown. New signals may trade whenever they pass the model and execution checks.

Risk remains controlled by:

- account-risk sizing per position;
- portfolio planned-risk cap;
- daily equity stop;
- spread filter;
- stale-entry / ATR slippage filter;
- server-side mark-price stop-loss and take-profit;
- exchange 10-position limit;
- duplicate-signal prevention;
- unresolved-order risk reservation.

The goal is higher activity, not unbounded account exposure.
