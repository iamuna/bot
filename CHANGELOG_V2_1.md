# v2.1 — full Terminal timeframe release

- Expanded the strategy from 15 native BloFin intervals to the full 30-timeframe Terminal 3.0 universe.
- Added locally constructed 45m, 3h, 16h, 2d, 4d, 5d, 6d, 2w, 3w, 2M, 3M, 4M, 5M, 6M and 12M OHLCV bars.
- Replaced four horizon buckets with Minutes / Hours / Days / Weeks / Months hierarchical confluence.
- Kept every enabled timeframe eligible to create an independent closed-candle trade.
- Retained no daily trade-count limit and no cooldown.
- Hardened BloFin Multi-Position tracking by resolving new opening orders through Order Detail and reserving planned risk while a new positionId is unresolved.
- Reconciles stale bot-owned positions when they disappear from the exchange open-position set.
- Upgraded the dashboard to show all 30 timeframes, native/constructed source, timeframe group filters, clickable signal candidates and forming-candle close timing.
- Removed the obsolete 3-minute launcher.
- Expanded CI/self-test coverage to 30 timeframes, constructed-candle integrity, order-detail routing, JavaScript syntax and multiple paper positions.
