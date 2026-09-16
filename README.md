# Terminal 3.0 · BloFin BTC 3m Bot v1.0

This package turns the **Terminal 3.0 TA engine** into an execution bot for the BloFin `BTC-USDT` linear perpetual contract.

## Default behavior

The bot starts in **PAPER mode**. It can read public BloFin market data but it cannot place a real order until you explicitly configure demo/live credentials locally.

Run:

1. Extract the ZIP.
2. Double-click `START_BLOFIN_3M_BOT.bat`.
3. The dashboard opens locally.
4. Validate PAPER mode first.
5. For BloFin demo/live, run `CONFIGURE_BLOFIN.bat` and enter your API credentials **locally**. Do not paste keys into ChatGPT.

## What creates an entry

The entry timeframe is always **3 minutes**. A trade is considered only when the just-closed 3m candle creates a new permanent Terminal 3.0 BUY/SELL marker. It then checks:

- 15m, 1h, 4h and 1d Terminal 3.0 scores;
- strong higher-timeframe opposition;
- 3m regime (range/squeeze entries require breakout confirmation);
- overextension from EMA20;
- live bid/ask spread;
- how far price moved after the signal close;
- existing BTC positions;
- daily loss/trade-count/loss-streak/cooldown guards.

It does **not** enter merely because a live 3m score briefly turns green/red.

## Position sizing

The bot uses account equity and the Terminal 3.0 ATR/structure stop to size the position:

`risk USD = equity × risk %`

For a linear BTC contract:

`contracts = risk USD / (stop distance × contract value)`

The result is rounded to BloFin's current `lotSize`, checked against `minSize`/`maxMarketSize`, then capped by `MAX_MARGIN_USE_PCT` and leverage.

Default limits:

- Risk/trade: **0.25%**
- Leverage: **2x**
- Software leverage cap: **5x**
- Max margin allocation: **25%**
- Daily equity stop: **2%**
- Max trades/day: **12**
- Consecutive-loss stop: **3**
- Cooldown after close: **2 × 3m candles**
- Take-profit reference: **2R**
- One BTC position at a time; no pyramiding

All are local config values in `.env`.

## BloFin modes

### PAPER
No API key. Local simulated fills based on BloFin ticker data.

### DEMO
Uses BloFin's demo-trading API and actually sends demo orders. Requires a BloFin demo API key/passphrase.

### LIVE
Uses BloFin's live API. Three gates must all be satisfied:

1. `BOT_ENV=live`
2. `ALLOW_LIVE_TRADING=I_ACCEPT_LIVE_RISK`
3. Type `LIVE` in the dashboard before pressing **ARM BOT**

The bot refuses to run live in BloFin **Multi-Position mode**. It supports One-way mode and normal Hedge mode. It reads your current margin mode rather than silently changing the account-level setting.

## API-key permissions

Create a dedicated BloFin key with **READ + TRADE**. The bot does not need TRANSFER permission. IP-whitelisting the key is strongly recommended when practical.

## Important behavior

- Entry decisions are made from **closed 3m candles only**.
- Market orders attach a mark-price stop-loss and take-profit on BloFin.
- If a BTC position already exists, no new position is opened.
- The `CLOSE BOT POSITION + STOP` button only attempts to close a position the current bot process believes it opened. It intentionally will not blindly close an unrelated BTC position after a restart.
- Logs are stored under `logs/`.

## Files

- `ta_engine.py` — Terminal 3.0 TA/signal engine
- `strategy.py` — 3m entry + higher-timeframe gate
- `risk.py` — contract-aware risk sizing
- `blofin_client.py` — BloFin REST/auth/trading client
- `bot.py` — bot state machine and risk controls
- `app.py` — local dashboard
- `STRATEGY.md` — exact decision logic
- `SOURCES.md` — API references used for the implementation
