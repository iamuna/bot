from __future__ import annotations

import math,random
from backtest_v24 import Backtester,resample,qmult,regime_mult,tf_group,TF_RISK


def synthetic(n=520):
    r=random.Random(24);p=75_000.0;out=[];base=1_700_000_000_000
    for i in range(n):
        drift=2.0+3.0*math.sin(i/35);o=p;c=max(1000,o+drift+r.uniform(-18,18));h=max(o,c)+r.uniform(2,12);l=min(o,c)-r.uniform(2,12);v=100+r.uniform(0,50)
        out.append({'t':base+i*60_000,'o':o,'h':h,'l':l,'c':c,'v':v,'qv':v,'quote_v':v,'trades':0,'tb':0.0,'tbq':0.0,'ct':base+(i+1)*60_000-1,'closed':True,'source':'test'})
        p=c
    return out


def main():
    x=synthetic()
    assert len(resample(x,'1m'))==len(x)
    m3=resample(x,'3m');assert len(m3)>150 and all(b['h']>=b['l'] for b in m3)
    assert tf_group('1m')=='scalp' and tf_group('1h')=='intraday' and tf_group('4h')=='swing' and tf_group('1d')=='macro'
    assert TF_RISK['1m']<TF_RISK['1h']<TF_RISK['1d']
    assert qmult(40)<qmult(75)<qmult(90)
    assert regime_mult('BREAKOUT UP')>regime_mult('RANGE')
    r=Backtester(x,equity=1000,fee_bps=5,slippage_bps=1).run()
    assert r['engine'].startswith('Terminal 3 v2.4') and r['start_equity']==1000
    assert r['end_equity']>0 and r['max_drawdown_pct']>=0 and 'by_timeframe' in r
    print('BACKTEST SELF TEST OK: resampling, adaptive risk tiers, slot groups, fees/slippage path, reporting')

if __name__=='__main__':main()
