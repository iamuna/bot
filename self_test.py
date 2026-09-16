from __future__ import annotations
import random,time
from blofin_client import BloFinClient,bar_milliseconds,quantize_price,quantize_step
from bot import Terminal3BloFinBot
from config import BotConfig
from risk import size_for_risk
from strategy import TF_BARS,TF_ORDER,evaluate_all

def bars_cross(direction=1,n=350,start=90000.0,tf_ms=60000):
    rnd=random.Random(42 if direction>0 else 43);out=[];p=start;base=1700000000000
    for i in range(n):
        if i<n-2:drift=0;noise=rnd.uniform(-8,8)
        else:drift=direction*420;noise=direction*20
        o=p;c=max(1000,o+drift+noise);h=max(o,c)+8;l=min(o,c)-8
        out.append({'t':base+i*tf_ms,'o':o,'h':h,'l':l,'c':c,'v':100 if i<n-2 else 700,'qv':1 if i<n-2 else 7,'closed':True});p=c
    return out

def dataset(direction=1):return {tf:bars_cross(direction,350,90000,bar_milliseconds(bar)) for tf,bar in TF_BARS.items()}

def test_signing():
    c=BloFinClient('key','secret','pass',demo=True);h=c._headers('/api/v1/account/balance','GET','');assert h['ACCESS-KEY']=='key' and h['ACCESS-SIGN']

def test_all_timeframes():
    assert len(TF_ORDER)==15
    up=evaluate_all(dataset(1),'Aggressive',45,38,1.8);dn=evaluate_all(dataset(-1),'Aggressive',45,38,1.8)
    assert up.overall_score>20 and dn.overall_score<-20
    assert len(up.candidates)==15 and all(c.action=='BUY' for c in up.candidates)
    assert len(dn.candidates)==15 and all(c.action=='SELL' for c in dn.candidates)
    assert {'micro','intraday','swing','macro'}==set(up.horizons)

def test_risk():
    inst={'contractValue':'0.001','minSize':'0.1','lotSize':'0.1','maxMarketSize':'1000000'}
    p=size_for_risk(1000,100000,99500,inst,.35,3,45);assert float(p.contracts)>=.1 and p.risk_usd<=3.6;assert quantize_step(1.234,.1)=='1.2';assert quantize_price(100.26,.5)=='100.5'

def test_multiple_paper_positions():
    bot=Terminal3BloFinBot(BotConfig(environment='paper',signal_mode='Aggressive',paper_equity=1000));bot.instrument={'contractValue':'0.001','minSize':'0.1','lotSize':'0.1','maxMarketSize':'1000000','tickSize':'0.1'}
    ev=evaluate_all(dataset(1),'Aggressive',45,38,1.8);bot.last_eval=ev
    c1,c2=ev.candidates[0],ev.candidates[1]
    t1={'last':str(c1.entry_reference),'bidPrice':str(c1.entry_reference-.5),'askPrice':str(c1.entry_reference+.5)}
    t2={'last':str(c2.entry_reference),'bidPrice':str(c2.entry_reference-.5),'askPrice':str(c2.entry_reference+.5)}
    assert bot._execute(c1,t1,1000);assert bot._execute(c2,t2,1000);assert len(bot.paper_positions)==2
    assert bot.paper_positions[0]['timeframe']!=bot.paper_positions[1]['timeframe']

def main():
    test_signing();test_all_timeframes();test_risk();test_multiple_paper_positions();print('SELF TEST OK: signing, 15 timeframes, multi-horizon TA, multiple paper positions, sizing')
if __name__=='__main__':main()
