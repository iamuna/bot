from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, asdict

from backtest_v24 import Candidate, tf_group
from backtest_v24_guarded import GuardConfig, GuardedBacktester


@dataclass(frozen=True)
class SelectiveConfig:
    """Research-only anti-churn and capital-preservation layer.

    These are deliberately broad, structural constraints rather than a fit to
    one exact timeframe. The goal is to reject trades whose transaction costs
    consume too much of the planned stop, reduce risk while an edge is
    unproven/negative, and stop adding risk during a material account drawdown.
    """

    # Round-trip fees + modeled slippage may consume at most 0.20R of the
    # planned initial stop. This dynamically filters very tight-stop scalps.
    max_round_trip_cost_r: float = 0.20

    # Parent guarded engine also requires the planned target to retain at least
    # this much reward after estimated round-trip costs.
    min_net_target_r: float = 1.50

    # Online edge learner. It only uses trades that have already CLOSED, so no
    # future information is introduced. Buckets are timeframe-group + side.
    edge_window: int = 40
    edge_warmup_trades: int = 12
    edge_probe_mult: float = 0.35

    # Capital-preservation drawdown tiers. These scale NEW risk only. Existing
    # positions still exit through their normal stop/target/time logic.
    drawdown_tier_1_pct: float = 3.0
    drawdown_tier_2_pct: float = 5.0
    drawdown_tier_3_pct: float = 7.0
    drawdown_tier_4_pct: float = 10.0
    drawdown_lock_pct: float = 15.0
    drawdown_mult_1: float = 1.00
    drawdown_mult_2: float = 0.75
    drawdown_mult_3: float = 0.55
    drawdown_mult_4: float = 0.35
    drawdown_mult_5: float = 0.20


class SelectiveBacktester(GuardedBacktester):
    """v2.4.1 research candidate focused on cost discipline and survival.

    This is NOT assumed profitable. It is a controlled candidate that directly
    addresses the failure mode found in the 180-day v2.4 run: extreme low-TF
    turnover, costs consuming large fractions of 1R, and continued full-risk
    trading while the account was demonstrably losing.
    """

    def __init__(self, base, equity=1000.0, fee_bps=6.0, slippage_bps=1.0,
                 guard: GuardConfig | None = None,
                 selective: SelectiveConfig | None = None):
        self.selective = selective or SelectiveConfig()
        if guard is None:
            guard = GuardConfig(min_net_target_r=self.selective.min_net_target_r)
        super().__init__(base, equity=equity, fee_bps=fee_bps,
                         slippage_bps=slippage_bps, guard=guard)

        self.edge_r = defaultdict(lambda: deque(maxlen=self.selective.edge_window))
        self._selective_risk_mult = 1.0
        self.selective_cost_rejections = 0
        self.drawdown_lock_rejections = 0
        self.edge_throttled_entries = 0
        self.drawdown_throttled_entries = 0
        self.selective_opened_entries = 0
        self.max_observed_cost_r = 0.0
        self.max_start_drawdown_pct = 0.0
        self.max_peak_drawdown_pct = 0.0

    def _cost_r(self, c: Candidate) -> float:
        risk_per_unit = max(abs(c.entry_ref - c.stop_ref), 1e-9)
        round_trip_cost = c.entry_ref * (2 * self.fee_bps + 2 * self.slippage_bps) / 10000.0
        return round_trip_cost / risk_per_unit

    @staticmethod
    def _edge_key_from_trade(tf: str, side: str):
        return f'{tf_group(tf)}:{side}'

    def _edge_stats(self, key: str) -> tuple[int, float, float]:
        xs = list(self.edge_r.get(key, ()))
        if not xs:
            return 0, 0.0, 1.0
        avg_r = sum(xs) / len(xs)
        gp = sum(x for x in xs if x > 0)
        gl = -sum(x for x in xs if x < 0)
        pf = gp / gl if gl > 1e-12 else (9.99 if gp > 0 else 1.0)
        return len(xs), avg_r, pf

    def _edge_multiplier(self, c: Candidate) -> float:
        key = self._edge_key_from_trade(c.tf, c.side)
        n, avg_r, pf = self._edge_stats(key)
        g = self.selective
        if n < g.edge_warmup_trades:
            return g.edge_probe_mult
        # Continuous throttling instead of binary curve-fitting. A clearly
        # negative recent bucket gets tiny probe risk; a merely weak bucket is
        # reduced; only evidence of positive net expectancy earns full risk.
        if avg_r <= -0.25 or pf < 0.65:
            return 0.10
        if avg_r <= -0.10 or pf < 0.85:
            return 0.20
        if avg_r <= 0.00 or pf < 1.00:
            return 0.40
        if avg_r < 0.10 or pf < 1.15:
            return 0.70
        return 1.00

    def _drawdown_multiplier(self, price: float) -> float:
        mtm = float(self._mark_to_market(price))
        start_dd = max(0.0, (self.start_equity - mtm) / max(self.start_equity, 1e-9) * 100.0)
        peak_dd = max(0.0, (self.peak - mtm) / max(self.peak, 1e-9) * 100.0)
        self.max_start_drawdown_pct = max(self.max_start_drawdown_pct, start_dd)
        self.max_peak_drawdown_pct = max(self.max_peak_drawdown_pct, peak_dd)
        dd = max(start_dd, peak_dd)
        g = self.selective
        if dd >= g.drawdown_lock_pct:
            return 0.0
        if dd >= g.drawdown_tier_4_pct:
            return g.drawdown_mult_5
        if dd >= g.drawdown_tier_3_pct:
            return g.drawdown_mult_4
        if dd >= g.drawdown_tier_2_pct:
            return g.drawdown_mult_3
        if dd >= g.drawdown_tier_1_pct:
            return g.drawdown_mult_2
        return g.drawdown_mult_1

    def _risk_pct(self, c: Candidate):
        return super()._risk_pct(c) * self._selective_risk_mult

    def _open_candidate(self, c: Candidate, bar):
        cost_r = self._cost_r(c)
        self.max_observed_cost_r = max(self.max_observed_cost_r, cost_r)
        if cost_r > self.selective.max_round_trip_cost_r:
            self.selective_cost_rejections += 1
            self.rejections.append({
                't': bar['t'], 'tf': c.tf, 'side': c.side,
                'reason': f'round-trip cost {cost_r:.2f}R > {self.selective.max_round_trip_cost_r:.2f}R',
            })
            return

        dd_mult = self._drawdown_multiplier(float(bar['o']))
        if dd_mult <= 0:
            self.drawdown_lock_rejections += 1
            self.rejections.append({
                't': bar['t'], 'tf': c.tf, 'side': c.side,
                'reason': f'account drawdown lock >= {self.selective.drawdown_lock_pct:.1f}%',
            })
            return

        edge_mult = self._edge_multiplier(c)
        self._selective_risk_mult = dd_mult * edge_mult
        if edge_mult < 0.999:
            self.edge_throttled_entries += 1
        if dd_mult < 0.999:
            self.drawdown_throttled_entries += 1

        before = len(self.positions)
        super()._open_candidate(c, bar)
        if len(self.positions) > before:
            self.selective_opened_entries += 1

    def _close(self, p, price, reason, t):
        before = len(self.closed)
        tf = p.tf
        side = p.side
        super()._close(p, price, reason, t)
        if len(self.closed) == before:
            return
        r = float(self.closed[-1].get('r') or 0.0)
        self.edge_r[self._edge_key_from_trade(tf, side)].append(r)

    def report(self):
        r = super().report()
        edge_report = {}
        for key in sorted(self.edge_r):
            n, avg_r, pf = self._edge_stats(key)
            edge_report[key] = {
                'trades_in_window': n,
                'avg_net_r': round(avg_r, 4),
                'profit_factor_r': round(pf, 3),
            }
        r.update({
            'engine': 'Terminal 3 v2.4.1 selective research backtester',
            'selective_config': asdict(self.selective),
            'selective_cost_rejections': self.selective_cost_rejections,
            'drawdown_lock_rejections': self.drawdown_lock_rejections,
            'edge_throttled_entries': self.edge_throttled_entries,
            'drawdown_throttled_entries': self.drawdown_throttled_entries,
            'selective_opened_entries': self.selective_opened_entries,
            'max_observed_cost_r': round(self.max_observed_cost_r, 4),
            'max_start_drawdown_pct_selective': round(self.max_start_drawdown_pct, 3),
            'max_peak_drawdown_pct_selective': round(self.max_peak_drawdown_pct, 3),
            'rolling_edge': edge_report,
        })
        return r
