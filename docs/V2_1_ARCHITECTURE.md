# v2.1 architecture

Data path:

1. Fetch BloFin's 15 native BTC-USDT futures candle intervals.
2. Construct the other 15 Terminal intervals from native OHLCV bars.
3. Analyze each completed timeframe independently with the Terminal TA engine.
4. Summarize correlated timeframes into Minutes / Hours / Days / Weeks / Months.
5. Build fresh closed-candle candidates and rank by quality, confluence and local score.
6. Apply execution guards: spread, stale-entry distance, portfolio planned risk, daily equity stop, duplicate key and exchange position capacity.
7. Submit a new independent BloFin opening order in Hedge + Multi-Position mode.
8. Resolve the generated positionId through Order Detail/current positions and maintain risk ownership until that exchange position closes.

The one-second application loop updates live status; trading decisions remain closed-candle events rather than one-second signal noise.
