from __future__ import annotations

import math
from typing import Any


def _clamp(x,a=-100.0,b=100.0):return max(a,min(b,x))
def _ema(v,n):
    if not v:return None
    a=2/(n+1);x=float(v[0])
    for y in v[1:]:x=a*float(y)+(1-a)*x
    return x
def _sma(v,n):return sum(v[-n:])/n if len(v)>=n else None
def _std(v,n):
    if len(v)<n:return None
    s=v[-n:];m=sum(s)/n;return math.sqrt(sum((x-m)**2 for x in s)/n)
def _rsi(v,n=14):
    if len(v)<n+1:return None
    gains=[];losses=[]
    for a,b in zip(v[-n-1:-1],v[-n:]):
        d=b-a;gains.append(max(d,0));losses.append(max(-d,0))
    ag=sum(gains)/n;al=sum(losses)/n
    if al==0:return 100.0
    return 100-100/(1+ag/al)
def _tr(b,i):
    h=float(b[i]['h']);l=float(b[i]['l']);pc=float(b[i-1]['c']);return max(h-l,abs(h-pc),abs(l-pc))
def _atr(b,n=14):
    if len(b)<n+1:return None
    return sum(_tr(b,i) for i in range(len(b)-n,len(b)))/n
def _macd(v):
    if len(v)<35:return (None,None,None)
    line=_ema(v[-100:],12)-_ema(v[-100:],26);series=[]
    start=max(26,len(v)-40)
    for i in range(start,len(v)+1):
        s=v[:i]
        if len(s)>=26:series.append(_ema(s[-100:],12)-_ema(s[-100:],26))
    sig=_ema(series,9) if series else None
    return line,sig,(line-sig if sig is not None else None)
def _stoch(b,n=14):
    if len(b)<n:return None
    x=b[-n:];hi=max(float(z['h']) for z in x);lo=min(float(z['l']) for z in x);c=float(b[-1]['c']);return 50.0 if hi==lo else 100*(c-lo)/(hi-lo)
def _adx(b,n=14):
    if len(b)<n+2:return None
    trs=[];plus=[];minus=[]
    for i in range(len(b)-n,len(b)):
        up=float(b[i]['h'])-float(b[i-1]['h']);dn=float(b[i-1]['l'])-float(b[i]['l'])
        trs.append(_tr(b,i));plus.append(up if up>dn and up>0 else 0);minus.append(dn if dn>up and dn>0 else 0)
    tr=sum(trs)
    if tr<=0:return {'adx':0.0,'plus_di':0.0,'minus_di':0.0}
    p=100*sum(plus)/tr;m=100*sum(minus)/tr;dx=100*abs(p-m)/max(p+m,1e-9)
    return {'adx':dx,'plus_di':p,'minus_di':m}
def _roc(v,n=12):return ((v[-1]/v[-1-n])-1)*100 if len(v)>n and v[-1-n] else None
def _vwap(b,n=50):
    x=b[-n:];num=den=0.0
    for z in x:
        vol=float(z.get('qv') or z.get('v') or 0);tp=(float(z['h'])+float(z['l'])+float(z['c']))/3;num+=tp*vol;den+=vol
    return num/den if den>0 else None
def _obv_pressure(b,n=30):
    if len(b)<n+1:return None
    vals=[];obv=0.0
    for i in range(len(b)-n,len(b)):
        v=float(b[i].get('qv') or b[i].get('v') or 0);d=float(b[i]['c'])-float(b[i-1]['c']);obv+=v if d>0 else (-v if d<0 else 0);vals.append(v)
    avg=sum(vals)/max(len(vals),1);return _clamp(obv/max(avg*n*.35,1e-9),-2,2)
def _cmf(b,n=20):
    if len(b)<n:return None
    mf=vol=0.0
    for z in b[-n:]:
        h=float(z['h']);l=float(z['l']);c=float(z['c']);v=float(z.get('qv') or z.get('v') or 0);m=0 if h==l else ((c-l)-(h-c))/(h-l);mf+=m*v;vol+=v
    return mf/vol if vol else None
def _chop(b,n=14):
    if len(b)<n+1:return None
    x=b[-n:];hi=max(float(z['h']) for z in x);lo=min(float(z['l']) for z in x);rng=hi-lo
    if rng<=0:return 100.0
    tr=sum(_tr(b,i) for i in range(len(b)-n,len(b)));return 100*math.log10(max(tr/rng,1e-9))/math.log10(n)
def _lin_slope(v,n=20):
    if len(v)<n:return 0.0
    y=v[-n:];xm=(n-1)/2;ym=sum(y)/n;num=sum((i-xm)*(yy-ym) for i,yy in enumerate(y));den=sum((i-xm)**2 for i in range(n));return num/den if den else 0.0

def analyze_latest(bars:list[dict[str,Any]],mode:str='Balanced')->dict[str,Any]:
    closed=[x for x in bars if x.get('closed',True)]
    if len(closed)<30:raise ValueError('At least 30 closed candles are required')
    c=[float(x['c']) for x in closed];price=c[-1];atr=_atr(closed);atrp=(atr/price*100) if atr and price else None
    e20=_ema(c[-260:],20);e50=_ema(c[-320:],50);e200=_ema(c[-600:],200) if len(c)>=200 else None
    rsi=_rsi(c);macd,macd_sig,hist=_macd(c);st=_stoch(closed);adxv=_adx(closed);roc=_roc(c);vwap=_vwap(closed);obv=_obv_pressure(closed);cmf=_cmf(closed);chop=_chop(closed)
    bbm=_sma(c,20);bbs=_std(c,20);bb_upper=bbm+2*bbs if bbm is not None and bbs is not None else None;bb_lower=bbm-2*bbs if bbm is not None and bbs is not None else None;bb_width=((bb_upper-bb_lower)/bbm*100) if bbm and bb_upper is not None else None
    slope=_lin_slope(c,20);slope_pct=(slope/price*100*20) if price else 0.0
    prev20=closed[-21:-1] if len(closed)>=21 else closed[:-1];hh=max((float(x['h']) for x in prev20),default=price);ll=min((float(x['l']) for x in prev20),default=price);break_up=price>hh;break_dn=price<ll

    trend=0.0
    trend+=18 if price>e20 else -18;trend+=14 if e20 and e50 and e20>e50 else -14
    if e200 is not None:trend+=18 if e50>e200 else -18
    trend+=_clamp(slope_pct*8,-20,20)
    if adxv:
        di=adxv['plus_di']-adxv['minus_di'];trend+=_clamp(di*.35,-12,12)

    momentum=0.0
    if rsi is not None:momentum+=_clamp((rsi-50)*.9,-24,24)
    if hist is not None:momentum+=16 if hist>0 else -16
    if st is not None:momentum+=_clamp((st-50)*.32,-12,12)
    if roc is not None:momentum+=_clamp(roc*7,-16,16)

    structure=0.0
    if break_up:structure+=32
    elif break_dn:structure-=32
    else:
        if hh>ll:structure+=_clamp(((price-ll)/(hh-ll)-.5)*36,-18,18)
    structure+=_clamp(slope_pct*7,-18,18)
    if bb_upper is not None and bb_lower is not None and bb_upper>bb_lower:
        structure+=_clamp(((price-bb_lower)/(bb_upper-bb_lower)-.5)*20,-10,10)

    flow=0.0;vols=[float(x.get('qv') or x.get('v') or 0) for x in closed]
    if len(vols)>=20 and sum(vols[-20:])>0:
        avg=sum(vols[-20:])/20;rv=vols[-1]/max(avg,1e-9);flow+=(10 if c[-1]>=c[-2] else -10)*min(rv,2.5)/2.5
    if vwap is not None:flow+=10 if price>vwap else -10
    if obv is not None:flow+=_clamp(obv*6,-10,10)
    if cmf is not None:flow+=_clamp(cmf*35,-12,12)

    families={'trend':_clamp(trend),'momentum':_clamp(momentum),'structure':_clamp(structure),'flow':_clamp(flow)}
    score=_clamp(families['trend']*.32+families['momentum']*.23+families['structure']*.27+families['flow']*.18)
    if mode=='Conservative':score*=.92
    elif mode=='Aggressive':score*=1.10
    score=_clamp(score)
    fam_signs=[1 if v>6 else (-1 if v<-6 else 0) for v in families.values()];direction=1 if score>=0 else -1;aligned=sum(1 for s in fam_signs if s==direction);opposed=sum(1 for s in fam_signs if s==-direction);agreement=_clamp(50+aligned*12-opposed*10,0,100)
    adx_num=(adxv or {}).get('adx',0.0);quality=_clamp(42+abs(score)*.62+max(0,adx_num-16)*.45+(agreement-50)*.18,0,100)

    regime='MIXED'
    if break_up and score>20:regime='BREAKOUT UP'
    elif break_dn and score<-20:regime='BREAKOUT DOWN'
    elif bb_width is not None and bb_width<1.5 and (chop or 0)>55:regime='SQUEEZE'
    elif atrp is not None and atrp>3.5:regime='HIGH VOLATILITY'
    elif adx_num>=22 and score>8:regime='TREND UP'
    elif adx_num>=22 and score<-8:regime='TREND DOWN'
    elif (chop is not None and chop>=58) or abs(score)<17:regime='RANGE'

    ext=(price-e20)/atr if atr and e20 else None;th={'Conservative':48,'Balanced':40,'Aggressive':30}.get(mode,40);setup='WAIT'
    if score>=th:setup='BUY READY'
    elif score<=-th:setup='SELL READY'
    elif score>=18:setup='WATCH BUY'
    elif score<=-18:setup='WATCH SELL'
    coverage=min(100.0,45+len(closed)/4)
    result={'score':round(score,1),'quality':round(quality,1),'agreement':round(agreement,1),'regime':regime,'setup':setup,'rsi':round(rsi,1) if rsi is not None else None,'atr':round(atr,4) if atr else None,'atr_pct':round(atrp,3) if atrp is not None else None,'adx':round(adx_num,1),'plus_di':round((adxv or {}).get('plus_di',0),1),'minus_di':round((adxv or {}).get('minus_di',0),1),'roc':round(roc,3) if roc is not None else None,'stoch':round(st,1) if st is not None else None,'macd_hist':round(hist,5) if hist is not None else None,'ema20':e20,'ema50':e50,'ema200':e200,'vwap':vwap,'cmf':round(cmf,3) if cmf is not None else None,'chop':round(chop,1) if chop is not None else None,'bb_upper':bb_upper,'bb_mid':bbm,'bb_lower':bb_lower,'bb_width':round(bb_width,3) if bb_width is not None else None,'extension_atr':round(ext,2) if ext is not None else None,'coverage':round(coverage,1),'price':price,'families':{k:round(v,1) for k,v in families.items()}}
    return {'confirmed':result,'live':result.copy()}

def signal_history(bars:list[dict[str,Any]],mode:str='Balanced',timeframe:str='3m')->dict[str,Any]:
    closed=[x for x in bars if x.get('closed',True)];markers=[];th={'Conservative':48,'Balanced':40,'Aggressive':30}.get(mode,40);start=max(35,len(closed)-220);prev=0.0
    for i in range(start,len(closed)+1):
        sample=closed[:i]
        try:a=analyze_latest(sample,mode)['confirmed']
        except Exception:continue
        s=float(a['score']);side=None;trigger='score cross'
        if s>=th and prev<th:side='BUY'
        elif s<=-th and prev>-th:side='SELL'
        if len(sample)>=22:
            p=float(sample[-1]['c']);hh=max(float(x['h']) for x in sample[-21:-1]);ll=min(float(x['l']) for x in sample[-21:-1])
            if side is None and s>=th+5 and p>hh:side='BUY';trigger='breakout'
            elif side is None and s<=-th-5 and p<ll:side='SELL';trigger='breakdown'
        if side:
            entry=float(sample[-1]['c']);atr=float(a.get('atr') or entry*.004);sign=1 if side=='BUY' else -1
            recent=sample[-7:]
            structural=(min(float(x['l']) for x in recent)-.15*atr) if side=='BUY' else (max(float(x['h']) for x in recent)+.15*atr)
            raw_dist=(entry-structural) if side=='BUY' else (structural-entry);dist=max(.75*atr,min(2.5*atr,raw_dist if raw_dist>0 else 1.25*atr));stop=entry-sign*dist;target=entry+sign*2*dist
            markers.append({'t':int(sample[-1]['t']),'side':side,'price':entry,'score':round(s,1),'quality':a['quality'],'agreement':a['agreement'],'regime':a['regime'],'trigger':trigger,'plan':{'stop':stop,'target':target,'risk':dist}})
        prev=s
    latest=analyze_latest(closed,mode)['confirmed'];latest['direction']='UP' if latest['score']>8 else ('DOWN' if latest['score']<-8 else 'NEUTRAL');return {'markers':markers,'latest':latest,'timeframe':timeframe}
