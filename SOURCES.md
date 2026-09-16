# Sources used for v2.1

Primary reference: BloFin's official API documentation.

- API guide: https://docs.blofin.com/index.html
- Change log / Multi-Position additions: https://docs.blofin.com/changelog.html

## Market data behavior used

`GET /api/v1/market/candles`

BloFin documents these native futures candle intervals:

`1m / 3m / 5m / 15m / 30m / 1H / 2H / 4H / 6H / 8H / 12H / 1D / 3D / 1W / 1M`

Maximum response size is 1440 candles. The response has a `confirm` field where `1` means completed and `0` means the candle is still forming.

v2.1 builds the additional Terminal intervals locally from those official native OHLCV bars; it does not pretend BloFin supplies unsupported native bars.

## Multi-Position behavior used

BloFin documents that Multi-Position mode:

- is available under Hedge mode (`long_short_mode`);
- creates independent positions identified by `positionId`;
- can return multiple positions for the same instrument and direction;
- requires `positionId` to close a specific position;
- supports at most 10 positions per instrument.

The bot respects that exchange limit. It has no smaller max-trades-per-day limit and no cooldown.

## New-opening order tracking

BloFin's Place Order response may return an empty `positionId` for a new opening order because the independent position is created when the order fills. The documentation says to retrieve the generated ID through Order Detail or WebSocket.

v2.1 therefore uses:

`GET /api/v1/trade/order-detail`

and falls back to current-position reconciliation. Until an accepted opening order is matched to its independent `positionId`, its planned risk remains reserved by the local portfolio-risk engine.

## Protection orders

The order endpoint supports take-profit and stop-loss trigger prices and supports `mark` as a trigger-price type. v2.1 attaches mark-price TP/SL values to accepted market entries.
