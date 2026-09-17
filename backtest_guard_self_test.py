from __future__ import annotations

import math,random
from backtest_v24 import Candidate
from backtest_v24_guarded import GuardConfig,GuardedBacktester


def synthetic(n=260):
    r=random.Random(240);p=75_000.0;out=[];base=1_700_000_000_000
    for i in range(n):
        o=p;c=max(1000,o+2+2*math.sin(i/25)+r.uniform(-15,15));h=max(o,c)+8;l=min(o,c)-8;v=100+r.uniform(0,40)
        out.append({'t':base+i*60_000,'o':o,'h':h,'l':l,'c':c,'v':v,'qv':v,'quote_v':v,'trades':0,'tb':0.0,'tbq':0.0,'ct':base+(i+1)*60_000-1,'closed':True,'source':'test'})
        p=c
    return out


def main():
    x=synthetic();g=GuardConfig();b=GuardedBacktester(x,equity=1000,fee_bps=6,slippage_bps=1,guard=g)
    tight=Candidate('1m','BUY',0,90,50,80,100.0,99.9,100.18,'TREND UP',.1)
    roomy=Candidate('5m','BUY',0,90,50,80,100.0,99.5,100.90,'TREND UP',.5)
    assert b._estimated_net_target_r(tight)<g.min_net_target_r
    assert b._estimated_net_target_r(roomy)>g.min_net_target_r

    b.peak=1150.0;b.equity=1100.0
    mult,giveback=b._profit_guard_multiplier(float(x[-1]['c']))
    assert 33<giveback<34 and mult==.75
    b.equity=1050.0
    mult,giveback=b._profit_guard_multiplier(float(x[-1]['c']))
    assert 66<giveback<67 and mult==.10

    b.current_loss_streak=0;assert b._loss_streak_multiplier()==1.0
    b.current_loss_streak=3;assert b._loss_streak_multiplier()==.75
    b.current_loss_streak=5;assert b._loss_streak_multiplier()==.50
    b.current_loss_streak=7;assert b._loss_streak_multiplier()==.25

    r=GuardedBacktester(x,equity=1000,fee_bps=6,slippage_bps=1).run()
    assert r['engine'].startswith('Terminal 3 v2.4 guarded')
    assert 'profit_giveback_pct' in r and 'cost_rejections' in r and 'max_loss_streak' in r
    print('GUARDED BACKTEST SELF TEST OK: cost gate, high-water profit guard, loss-streak throttle, reporting')

if __name__=='__main__':main()
