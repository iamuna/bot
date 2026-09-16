# Sources used

Implementation checked against BloFin's current public Futures API documentation (September 2026):

- General API, REST roots, demo-trading roots, API permissions and request signing: https://docs.blofin.com/index.html
- Futures instruments (`contractValue`, `minSize`, `lotSize`, `tickSize`, leverage): `GET /api/v1/market/instruments`
- Ticker/bid/ask: `GET /api/v1/market/tickers`
- Candles and 3m support: `GET /api/v1/market/candles`
- Futures balance: `GET /api/v1/account/balance`
- Positions: `GET /api/v1/account/positions`
- Margin mode / position mode / leverage: account endpoints in the Futures API
- Market order with attached TP/SL: `POST /api/v1/trade/order`
- Position close: `POST /api/v1/trade/close-position`
- Position history: `GET /api/v1/account/positions-history`

The BloFin API changelog was also checked because Multi-Position support and trailing-stop capabilities changed in 2026: https://docs.blofin.com/changelog.html

The source code intentionally rejects Multi-Position mode rather than guessing how to manage independently keyed positions.
