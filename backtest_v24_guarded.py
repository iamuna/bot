from __future__ import annotations

import argparse,json
from dataclasses import dataclass,asdict
from pathlib import Path

from backtest_v24 import Backtester,Candidate,load_1m_csv,save_report


@dataclass(frozen=True)
class GuardConfig:
    # Require the planned target to retain useful reward after estimated
    # round-trip fees + slippage. This is deliberately configurable so it can
    # be swept rather than treated as a magic number.
    min_net_target_r: float = 0.75

    # Do not throttle ordinary noise around starting equity. Once the account
    # has made a meaningful peak gain, reduce new risk as more of that peak
    # profit is surrendered.
    profit_guard_activation_pct: float = 3.0
    giveback_tier_1_pct: float = 20.0
    giveback_tier_2_pct: float = 35.0
    giveback_tier_3_pct: float = 50.0
    giveback_tier_4_pct: float = 65.0
    giveback_mult_1: float = 1.00
    giveback_mult_2: float = 0.75
    giveback_mult_3: float = 0.50
    giveback_mult_4: float = 0.25
    giveback_mult_5: float = 0.10

    # A losing cluster is evidence that the current regime may no longer fit
    # the signal model. Scale new risk down rather than permanently disabling
    # the strategy after one bad sample.
    loss_streak_1: int = 3
    loss_streak_2: int = 5
    loss_streak_3: int = 7
    loss_mult_1: float = 1.00
    loss_mult_2: float = 0.75
    loss_mult_3: float = 0.50
    loss_mult_4: float = 0.25


class GuardedBacktester(Backtester):
    """v2.4 research engine with report-driven portfolio protection.

    This class intentionally sits on top of the base v2.4 engine so historical
    tests can compare the adaptive strategy with and without these guards.
    The thresholds are hypotheses to backtest, not claims of optimality.
    """

    def __init__(self,base,equity=1000.0,fee_bps=6.0,slippage_bps=1.0,guard:GuardConfig|None=None):
        super().__init__(base,equity=equity,fee_bps=fee_bps,slippage_bps=slippage_bps)
        self.guard=guard or GuardConfig()
        self.current_loss_streak=0
        self.max_loss_streak=0
        self.cost_rejections=0
        self.risk_throttled_entries=0
        self.guard_scale_samples=[]
        self._entry_guard_mult=1.0
        self._last_net_target_r=None

    def _estimated_net_target_r(self,c:Candidate)->float:
        risk=max(abs(c.entry_ref-c.stop_ref),1e-9)
        gross_reward=abs(c.target_ref-c.entry_ref)
        # Conservative research estimate: fees and slippage on both sides.
        round_trip_cost=c.entry_ref*(2*self.fee_bps+2*self.slippage_bps)/10000.0
        return (gross_reward-round_trip_cost)/risk

    def _profit_guard_multiplier(self,price:float)->tuple[float,float]:
        peak_profit=max(0.0,self.peak-self.start_equity)
        activation=self.start_equity*self.guard.profit_guard_activation_pct/100.0
        if peak_profit<activation or peak_profit<=0:
            return 1.0,0.0
        mtm=self._mark_to_market(price)
        giveback=max(0.0,(self.peak-mtm)/peak_profit*100.0)
        g=self.guard
        if giveback<=g.giveback_tier_1_pct:m=g.giveback_mult_1
        elif giveback<=g.giveback_tier_2_pct:m=g.giveback_mult_2
        elif giveback<=g.giveback_tier_3_pct:m=g.giveback_mult_3
        elif giveback<=g.giveback_tier_4_pct:m=g.giveback_mult_4
        else:m=g.giveback_mult_5
        return m,giveback

    def _loss_streak_multiplier(self)->float:
        n=self.current_loss_streak;g=self.guard
        if n<g.loss_streak_1:return g.loss_mult_1
        if n<g.loss_streak_2:return g.loss_mult_2
        if n<g.loss_streak_3:return g.loss_mult_3
        return g.loss_mult_4

    def _risk_pct(self,c:Candidate):
        return super()._risk_pct(c)*self._entry_guard_mult*self._loss_streak_multiplier()

    def _open_candidate(self,c:Candidate,bar):
        net_r=self._estimated_net_target_r(c);self._last_net_target_r=net_r
        if net_r<self.guard.min_net_target_r:
            self.cost_rejections+=1
            self.rejections.append({'t':bar['t'],'tf':c.tf,'side':c.side,'reason':f'cost-adjusted target {net_r:.2f}R < {self.guard.min_net_target_r:.2f}R'})
            return
        profit_mult,giveback=self._profit_guard_multiplier(float(bar['o']))
        streak_mult=self._loss_streak_multiplier();self._entry_guard_mult=profit_mult
        combined=profit_mult*streak_mult
        self.guard_scale_samples.append(combined)
        if combined<0.999:self.risk_throttled_entries+=1
        super()._open_candidate(c,bar)

    def _close(self,p,price,reason,t):
        before=len(self.closed)
        super()._close(p,price,reason,t)
        if len(self.closed)==before:return
        pnl=float(self.closed[-1]['pnl'])
        if pnl<0:self.current_loss_streak+=1
        elif pnl>0:self.current_loss_streak=0
        self.max_loss_streak=max(self.max_loss_streak,self.current_loss_streak)

    def report(self):
        r=super().report();peak_profit=max(0.0,self.peak-self.start_equity)
        giveback=0.0 if peak_profit<=0 else max(0.0,(self.peak-self.equity)/peak_profit*100.0)
        r.update({
            'engine':'Terminal 3 v2.4 guarded research backtester',
            'guard_config':asdict(self.guard),
            'peak_equity':round(self.peak,2),
            'profit_giveback_pct':round(giveback,2),
            'current_loss_streak':self.current_loss_streak,
            'max_loss_streak':self.max_loss_streak,
            'cost_rejections':self.cost_rejections,
            'risk_throttled_entries':self.risk_throttled_entries,
            'avg_entry_risk_multiplier':round(sum(self.guard_scale_samples)/len(self.guard_scale_samples),3) if self.guard_scale_samples else 1.0,
        })
        return r


def main():
    ap=argparse.ArgumentParser(description='Terminal 3 v2.4 guarded adaptive-strategy backtester')
    ap.add_argument('csv',help='1-minute BTC OHLCV CSV')
    ap.add_argument('--equity',type=float,default=1000)
    ap.add_argument('--fee-bps',type=float,default=6.0,help='per-side fee assumption; regular BloFin taker is currently 6 bps')
    ap.add_argument('--slippage-bps',type=float,default=1.0)
    ap.add_argument('--min-net-target-r',type=float,default=.75)
    ap.add_argument('--profit-guard-activation',type=float,default=3.0)
    ap.add_argument('--out',default='backtest_results')
    a=ap.parse_args()
    guard=GuardConfig(min_net_target_r=a.min_net_target_r,profit_guard_activation_pct=a.profit_guard_activation)
    base=load_1m_csv(Path(a.csv));r=GuardedBacktester(base,a.equity,a.fee_bps,a.slippage_bps,guard).run();j,c=save_report(r,Path(a.out))
    keys=['start_equity','end_equity','return_pct','peak_equity','profit_giveback_pct','trades','win_rate_pct','profit_factor','max_drawdown_pct','avg_r','fees_paid','cost_rejections','risk_throttled_entries','max_loss_streak']
    print(json.dumps({k:r.get(k) for k in keys},indent=2));print(f'Report: {j}');print(f'Trades: {c}')

if __name__=='__main__':main()
