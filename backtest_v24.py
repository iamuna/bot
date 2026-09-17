from __future__ import annotations

import argparse,csv,json,math,statistics
from dataclasses import dataclass,asdict
from datetime import datetime,timezone
from pathlib import Path
from typing import Any

from strategy import TF_ORDER,HORIZONS,HORIZON_WEIGHTS,TF_IMPORTANCE,_bucket_start,_bucket_end
from ta_engine import analyze_latest

MIN_QUALITY=35.0
MIN_CONFLUENCE=25.0
MAX_OPEN_RISK_PCT=11.5
MAX_POSITIONS=10
LEVERAGE=7.0
MAX_MARGIN_USE_PCT=45.0
BASE_TP_R=2.0

TF_RISK={
    '1m':.30,'3m':.40,'5m':.50,'15m':.65,'30m':.75,'45m':.85,'1h':.85,
    '2h':1.00,'3h':1.00,'4h':1.00,'6h':1.10,'8h':1.10,'12h':1.10,
    '16h':1.20,'1d':1.20,'2d':1.25,'3d':1.25,'4d':1.25,'5d':1.25,'6d':1.25,
    '1w':1.25,'2w':1.25,'3w':1.25,'1M':1.25,'2M':1.25,'3M':1.25,'4M':1.25,'5M':1.25,'6M':1.25,'12M':1.25,
}
QUALITY_MULT=((45,.70),(55,.85),(70,1.00),(85,1.15),(101,1.25))
GROUPS={
    'scalp':{'tfs':{'1m','3m','5m'},'cap':4},
    'intraday':{'tfs':{'15m','30m','45m','1h'},'cap':3},
    'swing':{'tfs':{'2h','3h','4h','6h','8h','12h'},'cap':2},
    'macro':{'tfs':set(TF_ORDER)-{'1m','3m','5m','15m','30m','45m','1h','2h','3h','4h','6h','8h','12h'},'cap':1},
}
TRAIL_ATR={'scalp':.6,'intraday':.9,'swing':1.2,'macro':1.5}
MAX_HOLD_MIN={'1m':60,'3m':120,'5m':240,'15m':720,'30m':1440,'45m':1440,'1h':2880,'2h':4320,'3h':5760,'4h':7200,'6h':10080,'8h':14400,'12h':20160,'16h':28800,'1d':43200}


def tf_group(tf:str)->str:
    for name,g in GROUPS.items():
        if tf in g['tfs']:return name
    return 'macro'

def horizon_for(tf:str)->str:
    for h,tfs in HORIZONS.items():
        if tf in tfs:return h
    return 'hours'

def qmult(q:float)->float:
    for ceiling,m in QUALITY_MULT:
        if q<ceiling:return m
    return 1.25

def regime_mult(regime:str)->float:
    r=regime.upper()
    if 'BREAKOUT' in r:return 1.10
    if 'RANGE' in r:return .72
    if 'SQUEEZE' in r:return .82
    if 'HIGH VOL' in r:return .80
    return 1.0

def tf_minutes(tf:str)->int:
    n=int(tf[:-1]);u=tf[-1]
    return n*{'m':1,'h':60,'d':1440,'w':10080,'M':43200}[u]

def weighted_average(items):
    den=sum(w for _,w in items);return sum(v*w for v,w in items)/den if den else 0.0

def summarize_horizons(analyses):
    out={};overall=[]
    for h,tfs in HORIZONS.items():
        vals=[];up=down=0.0
        for tf in tfs:
            a=analyses.get(tf) or {}
            if 'score' not in a or float(a.get('coverage',0))<=0:continue
            cov=max(.2,min(1,float(a.get('coverage',100))/100));w=TF_IMPORTANCE.get(tf,1)*cov;s=float(a.get('score',0));vals.append((s,w))
            if s>8:up+=w
            elif s<-8:down+=w
        score=weighted_average(vals);total=sum(w for _,w in vals) or 1
        out[h]={'score':score,'agreement':100*max(up,down)/total,'timeframes':len(vals)}
        if vals:overall.append((score,HORIZON_WEIGHTS[h]))
    return out,weighted_average(overall)
def confluence(side,tf,analyses,horizons,overall):
    sign=1 if side=='BUY' else -1;own_h=horizon_for(tf);own=float((horizons.get(own_h) or {}).get('score',0));names=list(HORIZONS);i=names.index(own_h)
    higher=[float((horizons.get(h) or {}).get('score',0)) for h in names[i+1:] if (horizons.get(h) or {}).get('timeframes',0)>0]
    higher_score=sum(higher)/len(higher) if higher else overall;ctx=.50*own+.30*overall+.20*higher_score;aligned=max(-100,min(100,ctx*sign));return max(0,min(100,50+aligned*.55)),ctx


def _pick(row,*names,default=''):
    lower={str(k).lower():v for k,v in row.items()}
    for n in names:
        if n.lower() in lower:return lower[n.lower()]
    return default

def parse_ts(v:str)->int:
    s=str(v).strip()
    if s.replace('.','',1).isdigit():
        x=float(s)
        if x<1e11:x*=1000
        return int(x)
    dt=datetime.fromisoformat(s.replace('Z','+00:00'))
    if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp()*1000)
def load_1m_csv(path:Path)->list[dict[str,Any]]:
    out=[]
    with path.open(newline='',encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            t=parse_ts(_pick(r,'timestamp','time','date','datetime','open_time'))
            o=float(_pick(r,'open','o'));h=float(_pick(r,'high','h'));l=float(_pick(r,'low','l'));c=float(_pick(r,'close','c'))
            v=float(_pick(r,'volume','v',default=0) or 0);q=float(_pick(r,'quote_volume','qv','quotevol',default=v) or v)
            out.append({'t':t,'o':o,'h':h,'l':l,'c':c,'v':v,'qv':q,'quote_v':q,'trades':0,'tb':0.0,'tbq':0.0,'ct':t+59_999,'closed':True,'source':'csv:1m'})
    out.sort(key=lambda x:x['t'])
    if len(out)<100:raise ValueError('Need at least 100 one-minute candles')
    return out

def resample(base:list[dict[str,Any]],tf:str)->list[dict[str,Any]]:
    if tf=='1m':return list(base)
    groups={}
    for b in base:groups.setdefault(_bucket_start(int(b['t']),tf),[]).append(b)
    out=[]
    need=tf_minutes(tf)
    for t,xs in sorted(groups.items()):
        span=((int(xs[-1]['t'])-int(xs[0]['t']))//60_000)+1
        closed=span>=need
        out.append({'t':t,'o':float(xs[0]['o']),'h':max(float(x['h']) for x in xs),'l':min(float(x['l']) for x in xs),'c':float(xs[-1]['c']),'v':sum(float(x.get('v') or 0) for x in xs),'qv':sum(float(x.get('qv') or 0) for x in xs),'quote_v':sum(float(x.get('quote_v') or 0) for x in xs),'trades':0,'tb':0.0,'tbq':0.0,'ct':_bucket_end(t,tf),'closed':closed,'source':'resampled:1m'})
    return out

def build_dataset(base):return {tf:resample(base,tf) for tf in TF_ORDER}

@dataclass
class Candidate:
    tf:str;side:str;signal_t:int;quality:float;confluence:float;priority:float;entry_ref:float;stop_ref:float;target_ref:float;regime:str;atr:float
@dataclass
class Position:
    id:int;tf:str;side:str;entry_t:int;entry:float;stop:float;target:float;initial_stop:float;risk_per_unit:float;risk_usd:float;qty:float;quality:float;confluence:float;regime:str;atr:float;highest:float;lowest:float;mfe_r:float=0.0;mae_r:float=0.0;stage:str='initial';fees:float=0.0

class Backtester:
    def __init__(self,base:list[dict[str,Any]],equity=1000.0,fee_bps=5.0,slippage_bps=1.0):
        self.base=base;self.data=build_dataset(base);self.equity=float(equity);self.start_equity=float(equity);self.peak=self.equity;self.max_dd=0.0;self.fee_bps=float(fee_bps);self.slippage_bps=float(slippage_bps)
        self.analyses={};self.prev_score={};self.positions=[];self.closed=[];self.rejections=[];self.pending=[];self.next_id=1;self.cur_indices={tf:-1 for tf in TF_ORDER};self.equity_curve=[]
        self.close_events={}
        for tf,bars in self.data.items():
            for i,b in enumerate(bars):
                if b.get('closed'):self.close_events.setdefault(int(b['ct']),[]).append((tf,i))
        self.base_index={int(b['t']):i for i,b in enumerate(base)}
    def _mark_to_market(self,price):
        u=0.0
        for p in self.positions:u+=(price-p.entry)*p.qty*(1 if p.side=='BUY' else -1)
        return self.equity+u
    def _update_dd(self,price):
        mtm=self._mark_to_market(price);self.peak=max(self.peak,mtm);dd=(self.peak-mtm)/self.peak*100 if self.peak else 0;self.max_dd=max(self.max_dd,dd);self.equity_curve.append(mtm)
    def _fee(self,notional):return abs(notional)*self.fee_bps/10000
    def _slip(self,price,side,is_entry):
        s=self.slippage_bps/10000
        if is_entry:return price*(1+s if side=='BUY' else 1-s)
        return price*(1-s if side=='BUY' else 1+s)
    def _group_count(self,g):return sum(1 for p in self.positions if tf_group(p.tf)==g)
    def _open_risk(self):return sum(p.risk_usd for p in self.positions)
    def _same_side_risk(self,side):return sum(p.risk_usd for p in self.positions if p.side==side)
    def _candidate(self,tf,i):
        bars=self.data[tf][:i+1]
        if len(bars)<30:return None
        a=self.analyses.get(tf) or {};score=float(a.get('score',0));prev=float(self.prev_score.get(tf,0));th=30;side=None;trigger='score cross'
        if score>=th and prev<th:side='BUY'
        elif score<=-th and prev>-th:side='SELL'
        if len(bars)>=22:
            p=float(bars[-1]['c']);hh=max(float(x['h']) for x in bars[-21:-1]);ll=min(float(x['l']) for x in bars[-21:-1])
            if side is None and score>=th+5 and p>hh:side='BUY';trigger='breakout'
            elif side is None and score<=-th-5 and p<ll:side='SELL';trigger='breakdown'
        if not side:return None
        horizons,overall=summarize_horizons(self.analyses);conf,ctx=confluence(side,tf,self.analyses,horizons,overall);quality=float(a.get('quality',0));regime=str(a.get('regime',''));sign=1 if side=='BUY' else -1;reasons=[]
        if quality<MIN_QUALITY:reasons.append('quality')
        if conf<MIN_CONFLUENCE and quality<MIN_QUALITY+18:reasons.append('confluence')
        if regime=='RANGE' and trigger not in {'breakout','breakdown'} and quality<MIN_QUALITY+15:reasons.append('range')
        ext=a.get('extension_atr')
        if ext is not None and float(ext)*sign>4 and quality<80:reasons.append('extended')
        if ctx*sign<=-42 and quality<78:reasons.append('context')
        if reasons:
            self.rejections.append({'t':int(bars[-1]['ct']),'tf':tf,'side':side,'reason':'+'.join(reasons)});return None
        entry=float(bars[-1]['c']);atr=float(a.get('atr') or entry*.004);recent=bars[-7:];structural=(min(float(x['l']) for x in recent)-.15*atr) if side=='BUY' else (max(float(x['h']) for x in recent)+.15*atr);raw=(entry-structural) if side=='BUY' else (structural-entry);dist=max(.75*atr,min(2.5*atr,raw if raw>0 else 1.25*atr));stop=entry-sign*dist;rm=BASE_TP_R*{'minutes':.90,'hours':1.0,'days':1.10,'weeks':1.18,'months':1.25}[horizon_for(tf)];target=entry+sign*rm*dist;priority=quality*.48+conf*.34+min(100,abs(score))*.18
        return Candidate(tf,side,int(bars[-1]['ct']),quality,conf,priority,entry,stop,target,regime,atr)
    def _risk_pct(self,c:Candidate):
        base=TF_RISK[c.tf];m=qmult(c.quality)*regime_mult(c.regime);same=self._same_side_risk(c.side);cap=self.equity*MAX_OPEN_RISK_PCT/100;exposure=1.0 if cap<=0 else max(.45,1-.55*min(1,same/cap));return min(1.5,base*m*exposure)
    def _open_candidate(self,c:Candidate,bar):
        if len(self.positions)>=MAX_POSITIONS:self.rejections.append({'t':bar['t'],'tf':c.tf,'side':c.side,'reason':'position cap'});return
        g=tf_group(c.tf)
        if self._group_count(g)>=GROUPS[g]['cap']:self.rejections.append({'t':bar['t'],'tf':c.tf,'side':c.side,'reason':f'{g} slot cap'});return
        sign=1 if c.side=='BUY' else -1;entry=self._slip(float(bar['o']),c.side,True);shift=entry-c.entry_ref;stop=c.stop_ref+shift;target=c.target_ref+shift;dist=abs(entry-stop)
        rp=self._risk_pct(c);risk_budget=self.equity*rp/100;qty=risk_budget/max(dist,1e-9);max_notional=self.equity*(MAX_MARGIN_USE_PCT/100)*LEVERAGE;qty=min(qty,max_notional/max(entry,1e-9));risk=qty*dist
        if self._open_risk()+risk>self.equity*MAX_OPEN_RISK_PCT/100:self.rejections.append({'t':bar['t'],'tf':c.tf,'side':c.side,'reason':'portfolio risk cap'});return
        fee=self._fee(entry*qty);self.equity-=fee
        p=Position(self.next_id,c.tf,c.side,int(bar['t']),entry,stop,target,stop,dist,risk,qty,c.quality,c.confluence,c.regime,c.atr,entry,entry,fees=fee);self.next_id+=1;self.positions.append(p)
    def _close(self,p:Position,price,reason,t):
        exitp=self._slip(price,p.side,False);sg=1 if p.side=='BUY' else -1;gross=(exitp-p.entry)*p.qty*sg;fee=self._fee(exitp*p.qty);net=gross-fee;self.equity+=net;self.positions.remove(p);self.closed.append({'id':p.id,'tf':p.tf,'side':p.side,'entry_t':p.entry_t,'exit_t':t,'entry':p.entry,'exit':exitp,'pnl':net,'gross':gross,'fees':p.fees+fee,'r':net/max(p.risk_usd,1e-9),'reason':reason,'quality':p.quality,'confluence':p.confluence,'regime':p.regime,'mfe_r':p.mfe_r,'mae_r':p.mae_r})
    def _manage(self,bar):
        for p in list(self.positions):
            hi=float(bar['h']);lo=float(bar['l']);sg=1 if p.side=='BUY' else -1;p.highest=max(p.highest,hi);p.lowest=min(p.lowest,lo)
            fav=(p.highest-p.entry)*sg if sg>0 else (p.entry-p.lowest);adv=(p.entry-p.lowest) if sg>0 else (p.highest-p.entry);p.mfe_r=max(p.mfe_r,fav/max(p.risk_per_unit,1e-9));p.mae_r=max(p.mae_r,adv/max(p.risk_per_unit,1e-9))
            r_now=((float(bar['c'])-p.entry)*sg)/max(p.risk_per_unit,1e-9)
            if r_now>=.75 and p.stage=='initial':
                p.stop=max(p.stop,p.entry-.25*p.risk_per_unit) if sg>0 else min(p.stop,p.entry+.25*p.risk_per_unit);p.stage='protect'
            if r_now>=1.0:
                p.stop=max(p.stop,p.entry) if sg>0 else min(p.stop,p.entry);p.stage='trailing';atr=float((self.analyses.get(p.tf) or {}).get('atr') or p.atr);trail=TRAIL_ATR[tf_group(p.tf)]*atr
                p.stop=max(p.stop,p.highest-trail) if sg>0 else min(p.stop,p.lowest+trail)
            stop_hit=lo<=p.stop if sg>0 else hi>=p.stop;target_hit=hi>=p.target if sg>0 else lo<=p.target
            if stop_hit:self._close(p,p.stop,'stop/trailing',int(bar['ct']));continue
            if target_hit:self._close(p,p.target,'target',int(bar['ct']));continue
            hold=(int(bar['ct'])-p.entry_t)/60_000;limit=MAX_HOLD_MIN.get(p.tf,tf_minutes(p.tf)*30)
            if hold>=limit:self._close(p,float(bar['c']),'time',int(bar['ct']))
    def run(self):
        events_by_min={}
        for ct,events in self.close_events.items():events_by_min.setdefault(ct//60_000,[]).extend(events)
        for bi,bar in enumerate(self.base):
            self._manage(bar)
            if self.pending:
                for c in sorted(self.pending,key=lambda x:x.priority,reverse=True):self._open_candidate(c,bar)
                self.pending=[]
            events=events_by_min.get(int(bar['ct'])//60_000,[])
            fresh=[]
            for tf,i in events:
                self.cur_indices[tf]=i;bars=self.data[tf][:i+1]
                if len(bars)>=30:
                    try:self.analyses[tf]=analyze_latest(bars,'Aggressive')['confirmed']
                    except Exception:pass
                c=self._candidate(tf,i)
                if c:fresh.append(c)
                self.prev_score[tf]=float((self.analyses.get(tf) or {}).get('score',0))
            self.pending=fresh
            self._update_dd(float(bar['c']))
        last=self.base[-1]
        for p in list(self.positions):self._close(p,float(last['c']),'end_of_test',int(last['ct']))
        return self.report()
    def report(self):
        wins=[x for x in self.closed if x['pnl']>0];losses=[x for x in self.closed if x['pnl']<0];gp=sum(x['pnl'] for x in wins);gl=-sum(x['pnl'] for x in losses);by_tf={}
        for x in self.closed:
            d=by_tf.setdefault(x['tf'],{'trades':0,'wins':0,'pnl':0.0,'r':0.0});d['trades']+=1;d['wins']+=x['pnl']>0;d['pnl']+=x['pnl'];d['r']+=x['r']
        return {'engine':'Terminal 3 v2.4 research backtester','start_equity':self.start_equity,'end_equity':round(self.equity,2),'return_pct':round((self.equity/self.start_equity-1)*100,2),'trades':len(self.closed),'wins':len(wins),'losses':len(losses),'win_rate_pct':round(100*len(wins)/len(self.closed),2) if self.closed else 0,'profit_factor':round(gp/gl,3) if gl else None,'net_pnl':round(self.equity-self.start_equity,2),'max_drawdown_pct':round(self.max_dd,2),'avg_r':round(statistics.mean([x['r'] for x in self.closed]),3) if self.closed else 0,'avg_mfe_r':round(statistics.mean([x['mfe_r'] for x in self.closed]),3) if self.closed else 0,'avg_mae_r':round(statistics.mean([x['mae_r'] for x in self.closed]),3) if self.closed else 0,'fees_paid':round(sum(x['fees'] for x in self.closed),2),'rejections':len(self.rejections),'by_timeframe':{k:{**v,'pnl':round(v['pnl'],2),'r':round(v['r'],2),'win_rate_pct':round(100*v['wins']/v['trades'],1)} for k,v in sorted(by_tf.items(),key=lambda kv:TF_ORDER.index(kv[0]))},'trades_detail':self.closed,'rejections_detail':self.rejections}


def save_report(report:dict,outdir:Path):
    outdir.mkdir(parents=True,exist_ok=True);stamp=datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S');j=outdir/f'v24_backtest_{stamp}.json';c=outdir/f'v24_backtest_trades_{stamp}.csv';j.write_text(json.dumps(report,indent=2),encoding='utf-8')
    fields=['id','tf','side','entry_t','exit_t','entry','exit','pnl','gross','fees','r','reason','quality','confluence','regime','mfe_r','mae_r']
    with c.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows([{k:x.get(k) for k in fields} for x in report['trades_detail']])
    return j,c

def main():
    ap=argparse.ArgumentParser(description='Terminal 3 v2.4 adaptive-strategy backtester')
    ap.add_argument('csv',help='1-minute BTC OHLCV CSV');ap.add_argument('--equity',type=float,default=1000);ap.add_argument('--fee-bps',type=float,default=5.0);ap.add_argument('--slippage-bps',type=float,default=1.0);ap.add_argument('--out',default='backtest_results');a=ap.parse_args()
    base=load_1m_csv(Path(a.csv));r=Backtester(base,a.equity,a.fee_bps,a.slippage_bps).run();j,c=save_report(r,Path(a.out));print(json.dumps({k:r[k] for k in ['start_equity','end_equity','return_pct','trades','win_rate_pct','profit_factor','max_drawdown_pct','avg_r','fees_paid','rejections']},indent=2));print(f'Report: {j}');print(f'Trades: {c}')
if __name__=='__main__':main()
