# Risk model

The bot intentionally has no max-trades-per-day rule and no cooldown. Signal frequency and account exposure are separate controls.

Default new-position risk is 0.35% of equity. A proposed position is sized from the distance between entry and its protective stop, then constrained by the configured leverage/margin limit.

Portfolio planned risk is the sum of the stop-defined risk for bot-owned open positions plus accepted opening orders whose BloFin positionId is still being resolved. New entries stop when the configured portfolio-risk ceiling would be exceeded.

A separate daily equity drawdown circuit breaker pauses new entries when account equity falls by the configured percentage from that UTC day's starting equity.

These controls do not guarantee a maximum realized loss: gaps, slippage, liquidation mechanics, exchange/API outages and execution failures can produce losses beyond modeled stop risk.
