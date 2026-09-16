from __future__ import annotations

from typing import Any


def _ema(v,n):
    if not v:return None
    a=2/(n+1);x=v[0]
    for y in v[1:]:x=a*y+(1-a)*x
    return x

def _rsi(v,n=14):
    if len(v)<n+1:return None
    g=[];l=[]
    for a,b in zip(v[-n-1:-1],v[-n:]):
        d=b-a;g.append(max(d,0));l.append(max(-d,0))
    ag=sum(g)/n;al=sum(l)/n
    if al==0:return 100.0
    return 100-100/(1+ag/al)

def _atr(b,n=14):
    if len(b)<n+1:return None
    tr=[]
    for i in range(len(b)-n,len(b)):
        h=float(b[i]['h']);lo=float(b[i]['l']);pc=float(b[i-1]['c'])
        tr.append(max(h-lo,abs(h-pc),abs(lo-pc)))
    return sum(tr)/n

def _macd(v):
    if len(v)<35:return (None,None)
    line=_ema(v[-80:],12)-_ema(v[-80:],26);hist=[]
    for i in range(max(26,len(v)-25),len(v)+1):
        s=v[:i]
        if len(s)>=26:hist.append(_ema(s[-80:],12)-_ema(s[-80:],26))
    signal=_ema(hist,9) if hist else None
    return line,(line-signal if signal is not None else None)

def _stoch(b,n=14):
    if len(b)<n:return None
    x=b[-n:];hi=max(float(z['h']) for z in x);lo=min(float(z['l']) for z in x);c=float(b[-1]['c'])
    return 50 if hi==lo else 100*(c-lo)/(hi-lo)

def _adx_proxy(b,n=14):
    if len(b)<n+2:return None
    a=_atr(b,n)
    if not a:return 0.0
    move=abs(float(b[-1]['c'])-float(b[-n]['c']))
    return max(0,min(60,100*move/(n*a)))

def _clamp(x,a=-100,b=100):return max(a,min(b,x))

def analyze_latest(bars:list[dict[str,Any]],mode:str='Balanced')->dict[str,Any]:
    closed=[x for x in bars if x.get('closed',True)]
    if len(closed)<30:raise ValueError('At least 30 closed candles are required')
    c=[float(x['c']) for x in closed];price=c[-1]
    e20=_ema(c[-250:],20);e50=_ema(c[-300:],50);e200=_ema(c[-500:],200) if len(c)>=200 else None
    rsi=_rsi(c);atr=_atr(closed);_,hist=_macd(c);st=_stoch(closed);adx=_adx_proxy(closed)
    trend=0.0
    trend+=18 if price>e20 else -18;trend+=14 if e20>e50 else -14
    if e200 is not None:trend+=18 if e50>e200 else -18
    slope=(c[-1]-c[-21])/max(abs(c[-21]),1e-9)*100 if len(c)>=21 else 0
    trend+=_clamp(slope*12,-20,20)
    momentum=0.0
    if rsi is not None:momentum+=_clamp((rsi-50)*.9,-25,25)
    if hist is not None:momentum+=16 if hist>0 else -16
    if st is not None:momentum+=_clamp((st-50)*.35,-12,12)
    structure=0.0;look=closed[-21:-1]
    if look:
        hh=max(float(x['h']) for x in look);ll=min(float(x['l']) for x in look)
        structure+=25 if price>hh else (-25 if price<ll else 0)
    structure+=_clamp(slope*10,-20,20)
    flow=0.0;vols=[float(x.get('v',0) or 0) for x in closed]
    if len(vols)>=20 and sum(vols[-20:])>0:
        rv=vols[-1]/max(sum(vols[-20:])/20,1e-9);flow+=(10 if c[-1]>=c[-2] else -10)*min(rv,2)/2
    score=_clamp(trend*.32+momentum*.23+structure*.27+flow*.18)
    if mode=='Conservative':score*=.9
    elif mode=='Aggressive':score*=1.08
    score=_clamp(score);quality=_clamp(52+abs(score)*.55+(max(0,(adx or 0)-18))*.35,0,100);agreement=_clamp(50+abs(score)*.6,0,100)
    regime='MIXED'
    if adx is not None and adx>=22:regime='TREND UP' if score>8 else ('TREND DOWN' if score<-8 else 'MIXED')
    elif abs(score)<18:regime='RANGE'
    ext=(price-e20)/atr if atr and e20 else None;th={'Conservative':48,'Balanced':40,'Aggressive':32}.get(mode,40);setup='WAIT'
    if score>=th:setup='BUY READY'
    elif score<=-th:setup='SELL READY'
    elif score>=22:setup='WATCH BUY'
    elif score<=-22:setup='WATCH SELL'
    coverage=min(100.0,50+len(closed)/5)
    result={'score':round(score,1),'quality':round(quality,1),'agreement':round(agreement,1),'regime':regime,'setup':setup,'rsi':round(rsi,1) if rsi is not None else None,'atr':round(atr,4) if atr else None,'adx':round(adx,1) if adx is not None else None,'ema20':e20,'ema50':e50,'ema200':e200,'extension_atr':round(ext,2) if ext is not None else None,'coverage':round(coverage,1),'price':price}
    return {'confirmed':result,'live':result.copy()}

def signal_history(bars:list[dict[str,Any]],mode:str='Balanced',timeframe:str='3m')->dict[str,Any]:
    closed=[x for x in bars if x.get('closed',True)];markers=[];th={'Conservative':48,'Balanced':40,'Aggressive':32}.get(mode,40);start=max(30,len(closed)-160);prev=0.0
    for i in range(start,len(closed)+1):
        sample=closed[:i]
        try:a=analyze_latest(sample,mode)['confirmed']
        except Exception:continue
        s=float(a['score']);side=None;trigger='score cross'
        if s>=th and prev<th:side='BUY'
        elif s<=-th and prev>-th:side='SELL'
        if len(sample)>=22:
            p=float(sample[-1]['c']);hh=max(float(x['h']) for x in sample[-21:-1]);ll=min(float(x['l']) for x in sample[-21:-1])
            if side is None and s>=th+6 and p>hh:side='BUY';trigger='breakout'
            if side is None and s<=-th-6 and p<ll:side='SELL';trigger='breakdown'
        if side:
            entry=float(sample[-1]['c']);atr=float(a.get('atr') or entry*.005);sign=1 if side=='BUY' else -1;stop=entry-sign*max(atr*1.35,entry*.0025);target=entry+sign*2*abs(entry-stop)
            markers.append({'t':int(sample[-1]['t']),'side':side,'price':entry,'score':round(s,1),'quality':a['quality'],'trigger':trigger,'plan':{'stop':stop,'target':target}})
        prev=s
    latest=analyze_latest(closed,mode)['confirmed'];latest['direction']='UP' if latest['score']>8 else ('DOWN' if latest['score']<-8 else 'NEUTRAL')
    return {'markers':markers,'latest':latest,'timeframe':timeframe}
