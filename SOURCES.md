# Sources used for v2

BloFin API documentation (current at the time of the v2 rework):

- API overview and futures market data: https://docs.blofin.com/index.html
- Change log / Multi-Position additions: https://docs.blofin.com/changelog.html

Relevant documented behavior used by the bot:

- Futures candles: `GET /api/v1/market/candles`
- Native candle intervals: 1m / 3m / 5m / 15m / 30m / 1H / 2H / 4H / 6H / 8H / 12H / 1D / 3D / 1W / 1M
- Maximum candle request size: 1440
- Position mode: `GET /api/v1/account/position-mode`
- Change position mode: `POST /api/v1/account/set-position-mode`
- Multi-Position mode requires Hedge mode (`long_short_mode`)
- Each new opening order can create an independent `positionId`
- Closing in Multi-Position mode requires `positionId`
- Multi-Position mode supports up to 10 positions per instrument
- Market orders can attach TP/SL trigger prices
- `GET /api/v1/account/positions` may return multiple entries for the same instrument/side in Multi-Position mode

The implementation intentionally follows the exchange's 10-position hard limit rather than inventing a higher simultaneous-position setting.
