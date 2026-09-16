# v2.2 strategy — fixed-profile 30-timeframe multi-position engine

## 1. Timeframes

The strategy evaluates 30 intervals.

Native BloFin candles:

`1m 3m 5m 15m 30m 1h 2h 4h 6h 8h 12h 1d 3d 1w 1M`

Constructed locally from native OHLCV candles:

`45m 3h 16h 2d 4d 5d 6d 2w 3w 2M 3M 4M 5M 6M 12M`

Any enabled timeframe can create a trade. There is no master entry timeframe. A constructed interval cannot generate a permanent entry until enough closed source candles exist to complete that constructed bar.

## 2. Predetermined trading profile

v2.2 deliberately removes dashboard aggression controls. The strategy uses one fixed profile:

- Signal mode: Aggressive
- Risk/trade: 1.45% of equity
- Leverage: 7x
- Max margin use in sizing: 45%
- Portfolio planned-risk cap: 11.5%
- Minimum quality: 35%
- Minimum confluence: 25%
- Base target: 2.0R, adjusted slightly by horizon

These are code-level strategy constants rather than runtime UI or `.env` controls.

## 3. Technical score

Each timeframe receives a roughly -100 to +100 score built from four independent families:

- **Trend — 32%:** EMA20/50/200 structure, regression slope and ADX directional pressure.
- **Momentum — 23%:** RSI, MACD histogram, Stochastic and ROC.
- **Structure — 27%:** breakout/breakdown behavior, range position, Bollinger location and regression structure.
- **Flow — 18%:** relative volume, VWAP position, OBV pressure and CMF.

The Aggressive signal model reduces the score threshold and slightly increases score sensitivity, while execution/risk guards remain independent.

## 4. Regime detection

The engine distinguishes conditions such as BREAKOUT UP / BREAKOUT DOWN, TREND UP / TREND DOWN, RANGE, SQUEEZE, HIGH VOLATILITY and MIXED. Range signals generally need breakout confirmation unless quality is unusually high. Severe EMA20/ATR overextension is also penalized.

## 5. Hierarchical multi-timeframe model

Thirty correlated intervals are not treated as 30 independent votes. They are summarized first into five horizons:

- **Minutes:** 1m / 3m / 5m / 15m / 30m / 45m
- **Hours:** 1h / 2h / 3h / 4h / 6h / 8h / 12h / 16h
- **Days:** 1d / 2d / 3d / 4d / 5d / 6d
- **Weeks:** 1w / 2w / 3w
- **Months:** 1M / 2M / 3M / 4M / 5M / 6M / 12M

The current horizon weights are Minutes 14%, Hours 29%, Days 28%, Weeks 16% and Months 13%. Coverage and per-timeframe importance modify effective contribution. A candidate's confluence combines its own horizon, whole-market score and higher-horizon context.

## 6. Entry trigger

A candidate exists only when a **closed candle** on an enabled timeframe creates a fresh Terminal score-cross, breakout or breakdown marker. The key `{timeframe, candle timestamp, side}` is stored after execution so polling cannot repeatedly place the same trade. That is duplicate protection, not a frequency limit.

## 7. Automatic multiple positions

PAPER mode always uses independent simulated positions.

For DEMO/LIVE there is no manual Multi-Position button. When the user arms the bot, it automatically checks BloFin account mode. If Hedge + Multi-Position is not active, the bot requests it before entering trades. If BloFin rejects the mode change because positions/orders are open, arming fails visibly instead of silently switching to single-position behavior.

New opening orders omit `positionId`, so each accepted setup can create its own independent position. The bot resolves the generated `positionId` through BloFin Order Detail/current positions, records it, and uses that ID when an individual bot-owned position must be closed.

Pending position-ID resolution reserves the trade's planned risk so a temporarily unresolved fill cannot let the next trade bypass the portfolio-risk cap. BloFin's exchange-level Multi-Position limit remains 10 positions per instrument.

## 8. Risk and execution

There is no max-trades-per-day rule and no cooldown. New signals may trade whenever they pass the model and execution checks.

Risk remains controlled by account-risk sizing, the fixed 11.5% portfolio planned-risk cap, daily equity stop, spread filter, stale-entry / ATR slippage filter, server-side mark-price stop-loss and take-profit, exchange position limit, duplicate-signal prevention and unresolved-order risk reservation.
