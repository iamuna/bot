# Terminal 3.0 · BloFin Multi-Timeframe Bot v2.0

A BTC-USDT perpetual trading bot that evaluates **every native BloFin futures timeframe** and can open multiple independent positions when BloFin Multi-Position mode is enabled.

## What changed from v1

- Removed the 3-minute-only entry architecture.
- Scans **1m, 3m, 5m, 15m, 30m, 1H, 2H, 4H, 6H, 8H, 12H, 1D, 3D, 1W and 1M**.
- Every timeframe can independently create an entry.
- Uses horizon groups (micro / intraday / swing / macro) so correlated timeframes do not simply outvote everything else.
- Default signal mode is **Aggressive**.
- No daily trade-count limit and no cooldown.
- Supports BloFin **Hedge + Multi-Position mode**, where each opening order is an independent position.
- BloFin itself currently caps Multi-Position mode at **10 positions per instrument**; the bot respects that exchange limit.
- Interactive dashboard: selectable timeframe chart, all-timeframe heatmap/table, runtime aggression controls, position list, candidate stream and activity log.
- Runtime timeframe switches let you disable specific timeframes without editing files.
- TA engine upgraded with EMA structure, RSI, MACD, stochastic, ROC, ADX/+DI/-DI, VWAP, Bollinger location, ATR, CMF, OBV pressure, Choppiness and breakout/structure logic.

## Default aggression / risk settings

- Signal mode: `Aggressive`
- Risk per new position: `0.35%` of equity
- Leverage: `3x`
- Max margin allocation per position sizing calculation: `45%`
- Portfolio planned-risk cap: `5%` of equity
- Daily equity stop: `5%`
- Base take-profit reference: `1.8R` (slightly scaled by horizon)
- No trade-count limit
- No cooldown
- Max simultaneous positions: BloFin's hard **10-position** per-instrument limit

The bot is intentionally more active than v1, but trade frequency is not the same as unlimited risk. Portfolio-risk, daily-loss, spread, stale-entry and stop-loss controls remain.

## Modes

### PAPER
Default. Uses BloFin public market data and simulates independent positions locally.

### DEMO
Uses BloFin demo trading. API credentials are required.

### LIVE
Uses the real BloFin account. Three gates remain:

1. `BOT_ENV=live`
2. `ALLOW_LIVE_TRADING=I_ACCEPT_LIVE_RISK`
3. Type `LIVE` in the dashboard before arming

## Multi-Position mode

BloFin Multi-Position mode is available only under Hedge mode (`long_short_mode`). Each opening order can create a separate position with its own `positionId`, leverage and TP/SL. BloFin currently documents a limit of 10 positions per instrument.

The dashboard has **ENABLE MULTI-POSITION MODE**. BloFin requires there to be no open positions/orders when changing this account setting.

## Start

On Windows, run:

`START_BLOFIN_BOT.bat`

The old `START_BLOFIN_3M_BOT.bat` can remain for compatibility, but v2 is no longer a 3-minute bot.

## Security

Use a dedicated BloFin API key with **READ + TRADE only**. Do not grant TRANSFER permission. `.env` is ignored by git.

## Tests

Run:

`python self_test.py`

The test suite checks signing, all 15 timeframes, multi-horizon analysis, position sizing and multiple simultaneous paper positions.
