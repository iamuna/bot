# v2.1 release validation

Automated CI must pass before merge:

- Python compileall
- dashboard JavaScript syntax check
- API signing construction
- BloFin Order Detail route test
- 30-timeframe bullish/bearish evaluation
- constructed 45m candle OHLCV/closed-state test
- contract-aware risk sizing
- multiple simultaneous paper-position execution

Live authenticated BloFin execution is intentionally not exercised in CI because repository tests contain no exchange credentials.
