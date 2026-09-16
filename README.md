# Terminal 3.0 · BloFin 30-Timeframe Bot v2.1

A BTC-USDT perpetual trading bot built from the Terminal 3.0 TA engine. It evaluates **30 timeframes**, lets every enabled timeframe create its own closed-candle trade candidate, and supports multiple independent positions through BloFin Hedge + Multi-Position mode.

## Timeframe universe

BloFin supplies these 15 intervals natively:

`1m 3m 5m 15m 30m 1H 2H 4H 6H 8H 12H 1D 3D 1W 1M`

v2.1 constructs another 15 from those native OHLCV bars:

`45m 3h 16h 2d 4d 5d 6d 2w 3w 2M 3M 4M 5M 6M 12M`

The complete trading map is therefore:

- Minutes: `1m 3m 5m 15m 30m 45m`
- Hours: `1h 2h 3h 4h 6h 8h 12h 16h`
- Days: `1d 2d 3d 4d 5d 6d`
- Weeks: `1w 2w 3w`
- Months: `1M 2M 3M 4M 5M 6M 12M`

Constructed candles preserve open/high/low/close and aggregate volume fields. An incomplete constructed candle is marked forming and cannot create a permanent signal.

## Strategy architecture

There is no master 3-minute trigger anymore. Any enabled timeframe can independently generate a BUY or SELL candidate when its just-closed candle creates a fresh Terminal signal.

The engine scores each timeframe using:

- Trend: EMA20/50/200, regression structure, ADX/+DI/-DI
- Momentum: RSI, MACD, Stochastic, ROC
- Structure: breakouts/breakdowns, Bollinger location, range structure
- Flow: relative volume, VWAP, CMF and OBV pressure
- Regime: trend, range, squeeze, breakout, high-volatility and mixed conditions

To reduce fake confidence from correlated intervals, scores are summarized into **Minutes / Hours / Days / Weeks / Months** before being combined into the overall market context and each candidate's confluence score.

## Aggressive defaults

- Signal mode: `Aggressive`
- Risk per new position: `0.35%` of equity
- Leverage: `3x`
- Max margin allocation used by position sizing: `45%`
- Portfolio planned-risk cap: `5%` of equity
- Daily equity stop: `5%`
- Base take-profit reference: `1.8R`, scaled slightly by horizon
- No max-trades-per-day rule
- No cooldown
- Duplicate execution of the same `{timeframe, closed candle, side}` is prevented

Trade frequency is intentionally unrestricted by an arbitrary daily count, but exposure is still bounded by portfolio risk, daily equity loss, spread, stale-entry and exchange limits.

## Multiple positions

PAPER mode simulates independent positions locally.

DEMO/LIVE expects BloFin Hedge + Multi-Position mode. Each accepted new opening signal is submitted without a `positionId`, allowing BloFin to create a separate position. The bot then resolves the generated `positionId` through Order Detail / current positions and tracks the position independently until it disappears from the open-position set.

BloFin currently documents a hard maximum of **10 positions per instrument** in Multi-Position mode. The bot does not add a smaller position-count or daily trade-count limit.

## Dashboard

The local UI updates continuously and includes:

- live BTC price/spread and equity;
- overall 30-timeframe bias;
- selectable candlestick chart for every native or constructed timeframe;
- filters for Minutes / Hours / Days / Weeks / Months;
- per-timeframe AUTO toggles;
- score, quality, agreement, setup, regime, RSI, ADX and data coverage;
- live aggression controls for signal mode, risk, leverage, quality, confluence, portfolio risk and target R;
- fresh candidate feed;
- multiple-position list;
- activity/error stream;
- trade CSV export.

## Modes

### PAPER
Default. Uses BloFin public prices and simulates positions locally.

### DEMO
Uses BloFin demo trading and requires demo API credentials.

### LIVE
Requires all three gates:

1. `BOT_ENV=live`
2. `ALLOW_LIVE_TRADING=I_ACCEPT_LIVE_RISK`
3. Type `LIVE` in the dashboard before arming

## Windows start

Run:

`START_BLOFIN_BOT.bat`

Configure BloFin locally with:

`CONFIGURE_BLOFIN.bat`

Do not commit or share `.env`.

## Security

Use a dedicated BloFin API key with **READ + TRADE only**. Do not grant TRANSFER permission. `.env`, logs, caches and local state are ignored by git.

## Tests

Run:

`python self_test.py`

GitHub Actions also compiles the project and runs the offline self-test on pushes and pull requests.
