from __future__ import annotations

import random

from blofin_client import BloFinClient,quantize_price,quantize_step
from bot import Terminal3BloFinBot
from config import BotConfig
from risk import size_for_risk
from strategy import NATIVE_TF_BARS,DERIVED_TFS,TF_ORDER,HORIZONS,aggregate_timeframe,evaluate_all


def tf_ms(tf:str)->int:
    n=int(tf[:-1]);u=tf[-1]
    return n*{'m':60_000,'h':3_600_000,'d':86_400_000,'w':604_800_000,'M':30*86_400_000}[u]


def bars_cross(direction=1,n=350,start=90_000.0,interval_ms=60_000):
    rnd=random.Random(42 if direction>0 else 43);out=[];p=start;base=1_700_000_000_000
    for i in range(n):
        final=i==n-1
        drift=direction*1200 if final else 0
        noise=direction*35 if final else rnd.uniform(-7,7)
        o=p;c=max(1000,o+drift+noise);h=max(o,c)+(25 if final else 8);l=min(o,c)-(25 if final else 8)
        out.append({'t':base+i*interval_ms,'o':o,'h':h,'l':l,'c':c,'v':900 if final else 100,'qv':9 if final else 1,'quote_v':900_000 if final else 100_000,'trades':0,'tb':0.0,'tbq':0.0,'ct':base+(i+1)*interval_ms-1,'closed':True})
        p=c
    return out


def dataset(direction=1):
    return {tf:bars_cross(direction,350,90_000,tf_ms(tf)) for tf in TF_ORDER}


def test_signing_and_order_detail_route():
    c=BloFinClient('key','secret','pass',demo=True);h=c._headers('/api/v1/account/balance','GET','');assert h['ACCESS-KEY']=='key' and h['ACCESS-SIGN']
    class Capture(BloFinClient):
        def _request(self,method,path,params=None,body=None,private=False):
            self.seen=(method,path,params,private);return {'positionId':'P-123'}
    x=Capture('key','secret','pass');d=x.get_order_detail('BTC-USDT',order_id='O-1')
    assert d['positionId']=='P-123';assert x.seen[0]=='GET' and x.seen[1]=='/api/v1/trade/order-detail';assert x.seen[2]['orderId']=='O-1' and x.seen[3] is True


def test_constructed_candles():
    src=[]
    for i in range(6):
        o=100+i;c=o+1
        src.append({'t':i*15*60_000,'o':o,'h':c+1,'l':o-1,'c':c,'v':10+i,'qv':1+i,'quote_v':100+i,'trades':i+1,'tb':.1*i,'tbq':.2*i,'ct':(i+1)*15*60_000-1,'closed':True})
    x=aggregate_timeframe(src,'45m',3)
    assert len(x)==2 and all(b['closed'] for b in x)
    assert x[0]['o']==100 and x[0]['c']==103 and x[0]['h']==104 and x[0]['l']==99
    assert x[0]['v']==sum(10+i for i in range(3)) and x[0]['source']=='constructed:45m'
    partial=aggregate_timeframe(src[:2],'45m',3);assert len(partial)==1 and partial[0]['closed'] is False


def test_all_timeframes():
    assert len(NATIVE_TF_BARS)==15 and len(DERIVED_TFS)==15 and len(TF_ORDER)==30
    assert set(HORIZONS)=={'minutes','hours','days','weeks','months'}
    up=evaluate_all(dataset(1),'Aggressive',45,38,1.8);dn=evaluate_all(dataset(-1),'Aggressive',45,38,1.8)
    assert up.overall_score>20,up.overall_score
    assert dn.overall_score<-20,dn.overall_score
    assert len(up.candidates)>=25,len(up.candidates)
    assert len(dn.candidates)>=25,len(dn.candidates)
    assert all(c.action=='BUY' for c in up.candidates)
    assert all(c.action=='SELL' for c in dn.candidates)
    assert set(up.horizons)=={'minutes','hours','days','weeks','months'}


def test_risk():
    inst={'contractValue':'0.001','minSize':'0.1','lotSize':'0.1','maxMarketSize':'1000000'}
    p=size_for_risk(1000,100000,99500,inst,.35,3,45)
    assert float(p.contracts)>=.1 and p.risk_usd<=3.6
    assert quantize_step(1.234,.1)=='1.2';assert quantize_price(100.26,.5)=='100.5'


def test_multiple_paper_positions():
    bot=Terminal3BloFinBot(BotConfig(environment='paper',signal_mode='Aggressive',paper_equity=1000))
    bot.instrument={'contractValue':'0.001','minSize':'0.1','lotSize':'0.1','maxMarketSize':'1000000','tickSize':'0.1'}
    ev=evaluate_all(dataset(1),'Aggressive',45,38,1.8);bot.last_eval=ev
    c1,c2=ev.candidates[0],ev.candidates[1]
    for c in (c1,c2):
        t={'last':str(c.entry_reference),'bidPrice':str(c.entry_reference-.5),'askPrice':str(c.entry_reference+.5)}
        assert bot._execute(c,t,1000)
    assert len(bot.paper_positions)==2
    assert bot.paper_positions[0]['timeframe']!=bot.paper_positions[1]['timeframe']
    assert bot._open_risk_usd()>0


def main():
    test_signing_and_order_detail_route();test_constructed_candles();test_all_timeframes();test_risk();test_multiple_paper_positions()
    print('SELF TEST OK: signing, order-detail tracking, 30 timeframes, aggregation, multi-horizon TA, multi-position paper execution, sizing')

if __name__=='__main__':main()
