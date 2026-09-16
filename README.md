# Terminal 3.0 · BloFin 30-Timeframe Bot v2.3

A BTC-USDT perpetual trading bot built from the Terminal 3.0 TA engine. It evaluates **30 timeframes**, lets every enabled timeframe create its own closed-candle trade candidate, and supports multiple independent positions through BloFin Hedge + Multi-Position mode.

## What changed in v2.3

The bot now generates an **automatic performance report every 3 hours while armed**. The reporting window starts when you arm the bot. After each report, a new 3-hour window begins automatically.

Reports are saved locally under:

`logs/reports/`

Each cycle creates both JSON and Markdown versions, plus continuously updated `latest.json` and `latest.md` files.

Every report includes:

- trades opened and closed in the 3-hour window;
- wins, losses and win rate;
- realized P&L and average closed-trade P&L;
- gross profit, gross loss and profit factor;
- performance broken down by timeframe;
- execution rejection count and the most common rejection reasons;
- current equity and the equity change across the report window;
- current open positions and planned open risk;
- current all-timeframe direction, score and Minutes/Hours/Days/Weeks/Months horizon readings;
- current signal-candidate and strategy-rejection counts.

The dashboard shows a countdown to the next report, a compact summary of the most recent report, and a button to download the latest Markdown report.

## Fixed trading profile

The bot uses one predetermined built-in profile rather than manual aggression controls:

- Signal mode: `Aggressive`
- Risk per new position: `1.45%` of equity
- Leverage: `7x`
- Max margin allocation used by position sizing: `45%`
- Portfolio planned-risk cap: `11.5%` of equity
- Minimum setup quality: `35%`
- Minimum multi-timeframe confluence: `25%`
- Base take-profit reference: `2.0R`, scaled slightly by horizon
- No max-trades-per-day rule
- No cooldown
- Duplicate execution of the same `{timeframe, closed candle, side}` is prevented

Independent safety checks remain active: daily equity stop, spread filter, stale-entry/ATR slippage filter, stop-losses, portfolio-risk cap, exchange position limit and unresolved-order risk reservation.

## Timeframe universe

BloFin supplies these 15 intervals natively:

`1m 3m 5m 15m 30m 1H 2H 4H 6H 8H 12H 1D 3D 1W 1M`

The bot constructs another 15 from native OHLCV bars:

`45m 3h 16h 2d 4d 5d 6d 2w 3w 2M 3M 4M 5M 6M 12M`

The complete trading map is therefore:

- Minutes: `1m 3m 5m 15m 30m 45m`
- Hours: `1h 2h 3h 4h 6h 8h 12h 16h`
- Days: `1d 2d 3d 4d 5d 6d`
- Weeks: `1w 2w 3w`
- Months: `1M 2M 3M 4M 5M 6M 12M`

Constructed candles preserve open/high/low/close and aggregate volume fields. An incomplete constructed candle is marked forming and cannot create a permanent signal.

## Strategy architecture

There is no master 3-minute trigger. Any enabled timeframe can independently generate a BUY or SELL candidate when its just-closed candle creates a fresh Terminal signal.

The engine scores each timeframe using:

- Trend: EMA20/50/200, regression structure, ADX/+DI/-DI
- Momentum: RSI, MACD, Stochastic, ROC
- Structure: breakouts/breakdowns, Bollinger location, range structure
- Flow: relative volume, VWAP, CMF and OBV pressure
- Regime: trend, range, squeeze, breakout, high-volatility and mixed conditions

To reduce fake confidence from correlated intervals, scores are summarized into **Minutes / Hours / Days / Weeks / Months** before being combined into the overall market context and each candidate's confluence score.

## Multiple positions

PAPER mode simulates independent positions locally and starts in multi-position behavior automatically.

For DEMO/LIVE, arming the bot automatically checks BloFin account mode. If Hedge + Multi-Position is not already active, the bot requests it before trading. New opening orders omit `positionId`, allowing BloFin to create a separate position. The bot then resolves the generated `positionId` through Order Detail/current positions and tracks that position independently.

BloFin currently documents a hard maximum of **10 positions per instrument** in Multi-Position mode. The bot does not add a smaller position-count or daily trade-count limit.

## Dashboard

The local UI includes live BTC price/spread and equity, overall 30-timeframe bias, one large selectable candlestick chart, Minutes / Hours / Days / Weeks / Months filters, per-timeframe AUTO switches, score/quality/agreement/setup/regime/RSI/ADX/data coverage, fixed-profile status, automatic Multi-Position status, 3-hour report countdown and summary, fresh candidate feed, multiple-position list, activity/error stream and trade/report exports.

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

Use a dedicated BloFin API key with **READ + TRADE only**. Do not grant TRANSFER permission. `.env`, logs, caches, reports and local state are ignored by git.

## Tests

Run:

`python self_test.py`

GitHub Actions compiles the project, validates the dashboard JavaScript and runs the offline self-test on pushes and pull requests.
