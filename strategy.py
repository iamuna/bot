from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any

from ta_engine import analyze_latest, signal_history

NATIVE_TF_BARS: dict[str, str] = {
    "1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1H", "2h": "2H", "4h": "4H", "6h": "6H", "8h": "8H",
    "12h": "12H", "1d": "1D", "3d": "3D", "1w": "1W", "1M": "1M",
}
DERIVED_TFS: dict[str, tuple[str, int]] = {
    "45m": ("15m", 3), "3h": ("1h", 3), "16h": ("8h", 2),
    "2d": ("1d", 2), "4d": ("1d", 4), "5d": ("1d", 5), "6d": ("3d", 2),
    "2w": ("1w", 2), "3w": ("1w", 3),
    "2M": ("1M", 2), "3M": ("1M", 3), "4M": ("1M", 4), "5M": ("1M", 5), "6M": ("1M", 6), "12M": ("1M", 12),
}
TF_BARS = NATIVE_TF_BARS
TF_ORDER = [
    "1m","3m","5m","15m","30m","45m",
    "1h","2h","3h","4h","6h","8h","12h","16h",
    "1d","2d","3d","4d","5d","6d",
    "1w","2w","3w",
    "1M","2M","3M","4M","5M","6M","12M",
]
HORIZONS: dict[str, list[str]] = {
    "minutes": ["1m","3m","5m","15m","30m","45m"],
    "hours": ["1h","2h","3h","4h","6h","8h","12h","16h"],
    "days": ["1d","2d","3d","4d","5d","6d"],
    "weeks": ["1w","2w","3w"],
    "months": ["1M","2M","3M","4M","5M","6M","12M"],
}
HORIZON_WEIGHTS = {"minutes": .14, "hours": .29, "days": .28, "weeks": .16, "months": .13}
TF_IMPORTANCE = {tf: 1.0 for tf in TF_ORDER}
TF_IMPORTANCE.update({"1m":.62,"3m":.68,"5m":.75,"15m":.84,"30m":.90,"45m":.94,"1h":1.0,"2h":1.04,"3h":1.06,"4h":1.10,"6h":1.08,"8h":1.06,"12h":1.06,"16h":1.04,"1d":1.10,"2d":1.06,"3d":1.05,"4d":1.02,"5d":1.0,"6d":.98,"1w":1.0,"2w":.95,"3w":.92,"1M":.94,"2M":.90,"3M":.87,"4M":.84,"5M":.82,"6M":.80,"12M":.70})

_MINUTE=60_000;_HOUR=3_600_000;_DAY=86_400_000;_WEEK=604_800_000;_MONDAY_1970=4*_DAY

def _bucket_start(ts: int, target_tf: str) -> int:
    n=int(target_tf[:-1]);u=target_tf[-1]
    if u=='m':size=n*_MINUTE;return (ts//size)*size
    if u=='h':size=n*_HOUR;return (ts//size)*size
    if u=='d':size=n*_DAY;return (ts//size)*size
    if u=='w':size=n*_WEEK;return _MONDAY_1970+((ts-_MONDAY_1970)//size)*size
    if u=='M':
        dt=datetime.fromtimestamp(ts/1000,tz=timezone.utc);idx=dt.year*12+(dt.month-1);b=(idx//n)*n;year=b//12;month=b%12+1
        return int(datetime(year,month,1,tzinfo=timezone.utc).timestamp()*1000)
    raise ValueError(f'Unsupported timeframe: {target_tf}')

def aggregate_timeframe(source: list[dict[str,Any]], target_tf: str, multiplier: int) -> list[dict[str,Any]]:
    groups: dict[int,list[dict[str,Any]]] = {}
    for b in sorted(source,key=lambda x:int(x['t'])):groups.setdefault(_bucket_start(int(b['t']),target_tf),[]).append(b)
    out=[]
    for t,xs in sorted(groups.items()):
        if not xs:continue
        first,last=xs[0],xs[-1];complete=len(xs)>=multiplier and all(bool(z.get('closed',True)) for z in xs[:multiplier])
        out.append({
            't':t,'o':float(first['o']),'h':max(float(z['h']) for z in xs),'l':min(float(z['l']) for z in xs),'c':float(last['c']),
            'v':sum(float(z.get('v') or 0) for z in xs),'qv':sum(float(z.get('qv') or 0) for z in xs),'quote_v':sum(float(z.get('quote_v') or 0) for z in xs),
            'trades':sum(int(z.get('trades') or 0) for z in xs),'tb':sum(float(z.get('tb') or 0) for z in xs),'tbq':sum(float(z.get('tbq') or 0) for z in xs),
            'ct':int(last.get('ct') or last['t']),'closed':complete,'source':f'constructed:{target_tf}',
        })
    return out

@dataclass
class Candidate:
    action: str; timeframe: str; reason: str; signal: dict[str,Any]; entry_reference: float; stop: float; target: float; signal_bar_t: int; quality: float; confluence: float; context_score: float; priority: float; horizon: str
    def to_dict(self):return asdict(self)

@dataclass
class MarketEvaluation:
    analyses: dict[str,Any]; horizons: dict[str,Any]; overall_score: float; overall_direction: str; candidates: list[Candidate]; rejected: list[dict[str,Any]]

def _closed(bars):return [b for b in bars if bool(b.get('closed',True))]
def _last_closed_t(bars):
    x=_closed(bars);return int(x[-1]['t']) if x else None
def _horizon_for(tf):
    for h,tfs in HORIZONS.items():
        if tf in tfs:return h
    return 'hours'
def _direction(score):return 'UP' if score>=18 else ('DOWN' if score<=-18 else 'MIXED')
def _weighted_average(items):
    den=sum(w for _,w in items);return sum(v*w for v,w in items)/den if den else 0.0

def _summarize_horizons(analyses):
    out={};overall_parts=[]
    for h,tfs in HORIZONS.items():
        vals=[];same_up=same_down=0.0
        for tf in tfs:
            a=analyses.get(tf) or {}
            if 'score' not in a or float(a.get('coverage',0))<=0:continue
            cov=max(.20,min(1.0,float(a.get('coverage',100))/100));w=TF_IMPORTANCE.get(tf,1)*cov;s=float(a.get('score',0));vals.append((s,w))
            if s>8:same_up+=w
            elif s<-8:same_down+=w
        score=_weighted_average(vals);total=sum(w for _,w in vals) or 1;agreement=100*max(same_up,same_down)/total
        out[h]={'score':round(score,1),'direction':_direction(score),'agreement':round(agreement,1),'timeframes':len(vals)}
        if vals:overall_parts.append((score,HORIZON_WEIGHTS[h]))
    return out,_weighted_average(overall_parts)

def _confluence_for(side,tf,analyses,horizons,overall):
    sign=1 if side=='BUY' else -1;own_h=_horizon_for(tf);own=float((horizons.get(own_h) or {}).get('score',0));names=list(HORIZONS);idx=names.index(own_h);higher=[float((horizons.get(h) or {}).get('score',0)) for h in names[idx+1:] if (horizons.get(h) or {}).get('timeframes',0)>0];higher_score=sum(higher)/len(higher) if higher else overall
    context=.50*own+.30*overall+.20*higher_score;aligned=max(-100,min(100,context*sign));conf=max(0,min(100,50+aligned*.55));return round(conf,1),round(context,1)

def evaluate_all(dataset,mode='Aggressive',min_quality=50,min_confluence=46,tp_r_multiple=1.8,enabled_timeframes=None):
    enabled=set(enabled_timeframes or TF_ORDER);analyses={};rejected=[]
    for tf in TF_ORDER:
        bars=dataset.get(tf) or []
        if len(_closed(bars))<30:
            analyses[tf]={'score':0.0,'quality':0.0,'agreement':0.0,'regime':'LOW DATA','setup':'WAIT','coverage':0.0};continue
        try:analyses[tf]=analyze_latest(bars,mode)['confirmed']
        except Exception as e:analyses[tf]={'score':0.0,'quality':0.0,'agreement':0.0,'regime':'ERROR','setup':'WAIT','coverage':0.0,'error':str(e)}
    horizons,overall=_summarize_horizons(analyses);candidates=[]
    for tf in TF_ORDER:
        if tf not in enabled:continue
        bars=dataset.get(tf) or [];latest_t=_last_closed_t(bars)
        if latest_t is None or len(_closed(bars))<30:continue
        try:hist=signal_history(bars,mode,tf)
        except Exception as e:rejected.append({'timeframe':tf,'reason':f'signal engine error: {e}'});continue
        markers=hist.get('markers') or []
        if not markers:continue
        marker=markers[-1]
        if int(marker.get('t',-1))!=int(latest_t):continue
        side=str(marker.get('side',''))
        if side not in {'BUY','SELL'}:continue
        sign=1 if side=='BUY' else -1;quality=float(marker.get('quality',0));confluence,context=_confluence_for(side,tf,analyses,horizons,overall);a=analyses.get(tf) or {};trigger=str(marker.get('trigger',''));regime=str(a.get('regime',''));extension=a.get('extension_atr');reasons=[]
        if quality<min_quality:reasons.append(f'quality {quality:.0f} < {min_quality:.0f}')
        if confluence<min_confluence and quality<min_quality+18:reasons.append(f'confluence {confluence:.0f}% < {min_confluence:.0f}%')
        if regime=='RANGE' and trigger not in {'breakout','breakdown'} and quality<min_quality+15:reasons.append('range signal lacks breakout confirmation')
        if extension is not None and float(extension)*sign>4 and quality<80:reasons.append('entry is severely extended from EMA20')
        if context*sign<=-42 and quality<78:reasons.append('broad multi-timeframe context strongly opposes')
        if reasons:
            rejected.append({'timeframe':tf,'side':side,'quality':round(quality,1),'confluence':confluence,'reason':'; '.join(reasons),'signal_bar_t':latest_t});continue
        entry=float(marker.get('price'));plan=marker.get('plan') or {};stop=float(plan.get('stop') or entry*(.995 if side=='BUY' else 1.005));risk=abs(entry-stop);h=_horizon_for(tf);r_mult=tp_r_multiple*{'minutes':.90,'hours':1.0,'days':1.10,'weeks':1.18,'months':1.25}[h];target=entry+sign*r_mult*risk
        if risk<=0 or not all(math.isfinite(x) for x in (entry,stop,target)):
            rejected.append({'timeframe':tf,'side':side,'reason':'invalid risk plan','signal_bar_t':latest_t});continue
        priority=quality*.48+confluence*.34+min(100,abs(float(a.get('score',0))))*.18;reason=f'{tf} {side}: quality {quality:.0f}, confluence {confluence:.0f}%, {regime.lower()}'
        candidates.append(Candidate(side,tf,reason,marker,entry,stop,target,int(latest_t),round(quality,1),confluence,context,round(priority,1),h))
    candidates.sort(key=lambda x:x.priority,reverse=True)
    return MarketEvaluation(analyses,horizons,round(overall,1),_direction(overall),candidates,rejected[-60:])
