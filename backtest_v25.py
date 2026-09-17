from __future__ import annotations

from dataclasses import asdict

from backtest_v24_efficient import EfficientBacktester, EfficientConfig


V25_CONFIG = EfficientConfig(
    min_entry_timeframe_minutes=60,
    max_round_trip_cost_r=0.16,
)


class V25Backtester(EfficientBacktester):
    """v2.5 research candidate: preserve v2.4.2, raise entry floor to 1h.

    This is intentionally a single structural change. Lower timeframes remain
    available to the shared TA/context engine, but only 1h+ signals may open a
    position. Cost filters, rolling edge sizing, drawdown protection, exits,
    leverage envelope, and portfolio caps remain unchanged from v2.4.2.

    The already-inspected 2018-2025 BTC windows are research data for this
    candidate. They are not blind validation data anymore.
    """

    def __init__(self, base, equity=1000.0, fee_bps=6.0, slippage_bps=1.0):
        super().__init__(
            base,
            equity=equity,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
            efficient=V25_CONFIG,
        )

    def report(self):
        r = super().report()
        r.update({
            'engine': 'Terminal 3 v2.5 hourly-entry research backtester',
            'v25_config': asdict(V25_CONFIG),
            'research_status': 'NOT BLIND VALIDATION',
        })
        return r
