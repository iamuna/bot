from __future__ import annotations

import math
import random
import time

from blofin_client import BloFinClient, quantize_price, quantize_step
from risk import size_for_risk
from ta_engine import analyze_latest, signal_history


def bars(direction=1, n=700, start=90000.0, tf_ms=180000):
    rnd = random.Random(42 if direction > 0 else 43)
    out=[]
    p=start
    now=int(time.time()*1000)
    base=now-n*tf_ms
    for i in range(n):
        drift=direction*(8.0 + i*0.015)
        noise=rnd.uniform(-18,18)
        o=p
        c=max(1000,o+drift+noise)
        h=max(o,c)+rnd.uniform(3,22)
        l=min(o,c)-rnd.uniform(3,22)
        out.append({"t":base+i*tf_ms,"o":o,"h":h,"l":l,"c":c,"v":100+rnd.random()*100,"qv":1+rnd.random(),"trades":0,"tb":0.0,"tbq":0.0,"ct":base+(i+1)*tf_ms-1,"closed":True})
        p=c
    return out


def test_signing():
    c=BloFinClient("key","secret","pass",demo=True)
    h=c._headers('/api/v1/account/balance','GET','')
    assert h['ACCESS-KEY']=='key' and h['ACCESS-SIGN']


def test_ta():
    up=bars(1); down=bars(-1)
    au=analyze_latest(up,'Balanced')['confirmed']
    ad=analyze_latest(down,'Balanced')['confirmed']
    assert au['score'] > 0, au['score']
    assert ad['score'] < 0, ad['score']
    hu=signal_history(up,'Aggressive','3m')
    hd=signal_history(down,'Aggressive','3m')
    assert hu['latest']['direction']
    assert hd['latest']['direction']


def test_risk():
    inst={"contractValue":"0.001","minSize":"0.1","lotSize":"0.1","maxMarketSize":"1000000"}
    p=size_for_risk(1000,100000,99500,inst,0.25,2,25)
    assert float(p.contracts) >= 0.1
    assert p.risk_usd <= 2.6
    assert p.margin_estimate <= 250.01
    assert quantize_step(1.234,0.1)=='1.2'
    assert quantize_price(100.26,0.5)=='100.5'


if __name__=='__main__':
    test_signing(); test_ta(); test_risk()
    print('SELF TEST OK: signing, Terminal 3.0 TA, signal history, sizing, quantization')
