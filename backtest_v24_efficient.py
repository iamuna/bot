from __future__ import annotations

from dataclasses import dataclass, asdict

from backtest_v24 import Candidate, tf_minutes
from backtest_v24_selective import SelectiveBacktester, SelectiveConfig


@dataclass(frozen=True)
class EfficientConfig:
    """Structural follow-up to the v2.4.1 selective run.

    The first selective test proved that anti-churn protection can keep the
    account alive, but the remaining trades still paid too much friction. This
    candidate makes two broad changes only:

    1. 1m/3m/5m may still contribute to analysis/context, but they cannot open
       positions. The prior control and selective runs both showed that the
       scalp bucket was the dominant source of cost-adjusted loss.
    2. Surviving trades must keep round-trip fee+slippage below 0.16R rather
       than 0.20R. This is an economics constraint, not a timeframe-specific
       profit target.

    It is a research candidate, not a profitability claim.
    """

    min_entry_timeframe_minutes: int = 15
    max_round_trip_cost_r: float = 0.16


class EfficientBacktester(SelectiveBacktester):
    """v2.4.2 research candidate focused on net expectancy after costs."""

    def __init__(
        self,
        base,
        equity=1000.0,
        fee_bps=6.0,
        slippage_bps=1.0,
        efficient: EfficientConfig | None = None,
    ):
        self.efficient = efficient or EfficientConfig()
        selective = SelectiveConfig(
            max_round_trip_cost_r=self.efficient.max_round_trip_cost_r,
            min_net_target_r=1.50,
            edge_window=40,
            edge_warmup_trades=12,
            edge_probe_mult=0.35,
            drawdown_tier_1_pct=3.0,
            drawdown_tier_2_pct=5.0,
            drawdown_tier_3_pct=7.0,
            drawdown_tier_4_pct=10.0,
            drawdown_lock_pct=15.0,
            drawdown_mult_1=1.00,
            drawdown_mult_2=0.75,
            drawdown_mult_3=0.55,
            drawdown_mult_4=0.35,
            drawdown_mult_5=0.20,
        )
        super().__init__(
            base,
            equity=equity,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
            selective=selective,
        )
        self.low_tf_rejections = 0

    def _open_candidate(self, c: Candidate, bar):
        if tf_minutes(c.tf) < self.efficient.min_entry_timeframe_minutes:
            self.low_tf_rejections += 1
            self.rejections.append({
                't': bar['t'],
                'tf': c.tf,
                'side': c.side,
                'reason': (
                    f'entry timeframe {c.tf} below '
                    f'{self.efficient.min_entry_timeframe_minutes}m efficiency floor'
                ),
            })
            return
        super()._open_candidate(c, bar)

    def report(self):
        r = super().report()
        r.update({
            'engine': 'Terminal 3 v2.4.2 efficient research backtester',
            'efficient_config': asdict(self.efficient),
            'low_tf_rejections': self.low_tf_rejections,
        })
        return r
