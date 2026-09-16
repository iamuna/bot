# v2 strategy — all-timeframe multi-position engine

## 1. Timeframes

The bot uses all native BloFin futures candle intervals:

`1m 3m 5m 15m 30m 1H 2H 4H 6H 8H 12H 1D 3D 1W 1M`

Any enabled timeframe can create a trade. A timeframe is not merely a confirmation layer for another timeframe.

## 2. Technical score

Each timeframe gets a score from roughly -100 to +100 built from four families:

- Trend: EMA20/50/200 structure, regression slope, ADX directional pressure
- Momentum: RSI, MACD histogram, Stochastic, ROC
- Structure: 20-candle breakout/breakdown, range location, Bollinger location, regression structure
- Flow: relative volume, VWAP position, OBV pressure, CMF

The combined weights are:

- Trend 32%
- Momentum 23%
- Structure 27%
- Flow 18%

Aggressive mode lowers the score threshold and slightly increases score sensitivity.

## 3. Regime detection

The engine labels conditions including:

- BREAKOUT UP / BREAKOUT DOWN
- TREND UP / TREND DOWN
- RANGE
- SQUEEZE
- HIGH VOLATILITY
- MIXED

Range entries require better evidence unless setup quality is unusually high. Severe EMA20/ATR overextension is also penalized.

## 4. Horizon model

To avoid 15 highly correlated timeframes creating false confidence, timeframes are summarized first into:

- Micro: 1m / 3m / 5m
- Intraday: 15m / 30m / 1h / 2h / 4h
- Swing: 6h / 8h / 12h / 1d / 3d
- Macro: 1w / 1M

The horizon scores are then combined into an overall market score. A trade's confluence uses its own horizon plus broader/higher-timeframe context. Ordinary counter-trend trades are allowed; only very strong broad opposition blocks a moderate-quality setup.

## 5. Entry trigger

A permanent entry candidate appears only on a **closed candle** when that timeframe produces a fresh Terminal score cross / breakout / breakdown signal.

Duplicate execution of the same `{timeframe, candle, side}` is prevented. This is not a trade-frequency cap; it only prevents placing the same order repeatedly every poll cycle.

## 6. Multiple positions

In PAPER mode, each accepted signal creates an independent simulated position.

In DEMO/LIVE, v2 expects BloFin Hedge + Multi-Position mode. Opening orders omit `positionId`, causing BloFin to create a new independent position. Closing an individual position uses its `positionId`.

BloFin documents a hard maximum of 10 positions per instrument in Multi-Position mode. That is the only position-count ceiling used by the strategy.

## 7. Risk

There is no max-trades-per-day rule and no cooldown. Risk is controlled by:

- account-risk sizing per position;
- portfolio planned-risk cap;
- daily equity stop;
- spread filter;
- stale-entry / slippage-vs-ATR filter;
- server-side mark-price stop-loss and take-profit in BloFin;
- exchange 10-position limit.

A faster strategy is not allowed to become an unbounded-loss strategy.
