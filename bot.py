from __future__ import annotations

import csv,json,threading,time
from collections import deque
from datetime import datetime,timezone
from pathlib import Path
from typing import Any

from blofin_client import BloFinClient,quantize_price
from config import BotConfig
from risk import size_for_risk
from strategy import TF_BARS,TF_ORDER,evaluate_all,Candidate

ROOT=Path(__file__).resolve().parent
LOG_DIR=ROOT/'logs';LOG_DIR.mkdir(exist_ok=True)
TRADE_LOG=LOG_DIR/'trades.csv';EVENT_LOG=LOG_DIR/'events.jsonl'
EXCHANGE_MAX_POSITIONS=10

def iso_now():return datetime.now(timezone.utc).isoformat()
def f(v,d=0.0):
    try:return float(v)
    except:return d

class Terminal3BloFinBot:
    def __init__(self,cfg:BotConfig):
        self.cfg=cfg.validated();self.client=BloFinClient(cfg.api_key,cfg.secret_key,cfg.passphrase,demo=cfg.environment=='demo')
        self.lock=threading.RLock();self.running=False;self.armed=False;self.thread=None
        self.last_error='';self.last_message='Bot initialized; not armed.';self.last_scan_at='';self.last_ticker=None
        self.instrument=None;self.margin_mode='isolated';self.position_mode={'positionMode':'net_mode','multiPosition':'false'}
        self.positions=[];self.bot_owned:dict[str,dict[str,Any]]={};self.paper_positions:list[dict[str,Any]]=[]
        self.paper_equity=float(cfg.paper_equity);self.cached_equity=self.paper_equity if cfg.environment=='paper' else None
        self.day_key='';self.day_start_equity=self.paper_equity;self.day_realized=0.;self.kill_reason=''
        self.cache:dict[str,list[dict[str,Any]]]={tf:[] for tf in TF_ORDER};self.last_closed_t:dict[str,int]={}
        self.last_processed:set[str]=set();self.recent=deque(maxlen=120);self.last_eval=None;self.last_candidates=[];self.last_rejected=[]
        self.runtime={
            'signal_mode':cfg.signal_mode,'risk_pct':cfg.risk_pct,'leverage':cfg.leverage,
            'max_margin_use_pct':cfg.max_margin_use_pct,'max_total_open_risk_pct':cfg.max_total_open_risk_pct,
            'min_quality':cfg.min_quality,'min_confluence':cfg.min_confluence,'tp_r_multiple':cfg.tp_r_multiple,
            'enabled_timeframes':set(TF_ORDER),
        }
        self._next_tf_refresh={tf:0.0 for tf in TF_ORDER};self._ensure_log()

    def _ensure_log(self):
        if not TRADE_LOG.exists():
            with TRADE_LOG.open('w',newline='',encoding='utf-8') as x:
                csv.writer(x).writerow(['time_utc','environment','event','position_id','timeframe','side','entry','exit','contracts','stop','target','pnl','quality','confluence','reason','order_id'])
    def _event(self,kind,**kw):
        row={'time':iso_now(),'kind':kind,**kw};self.recent.appendleft(row)
        with EVENT_LOG.open('a',encoding='utf-8') as x:x.write(json.dumps(row,separators=(',',':'))+'\n')
    def _trade(self,event,**kw):
        with TRADE_LOG.open('a',newline='',encoding='utf-8') as x:
            csv.writer(x).writerow([iso_now(),self.cfg.environment,event,kw.get('position_id',''),kw.get('timeframe',''),kw.get('side',''),kw.get('entry',''),kw.get('exit',''),kw.get('contracts',''),kw.get('stop',''),kw.get('target',''),kw.get('pnl',''),kw.get('quality',''),kw.get('confluence',''),kw.get('reason',''),kw.get('order_id','')])

    def start_thread(self):
        if self.running:return
        self.running=True;self.thread=threading.Thread(target=self._loop,daemon=True);self.thread.start()

    def _init_exchange(self):
        self.instrument=self.client.get_instrument(self.cfg.instrument)
        if self.cfg.environment=='paper':
            self.position_mode={'positionMode':'long_short_mode','multiPosition':'true'}
        else:
            self.margin_mode=self.client.get_margin_mode();self.position_mode=self.client.get_position_mode();self._refresh_private()
            multi=str(self.position_mode.get('multiPosition','false')).lower()=='true'
            hedge=str(self.position_mode.get('positionMode','')).lower()=='long_short_mode'
            if self.cfg.require_multi_position and not (multi and hedge):
                raise RuntimeError('Multiple independent positions require BloFin Hedge Mode + Multi-Position mode. Use the dashboard button while no positions/orders are open.')

    def enable_multi_position_mode(self):
        if self.cfg.environment=='paper':
            self.position_mode={'positionMode':'long_short_mode','multiPosition':'true'};return self.position_mode
        self._refresh_private()
        if any(abs(f(p.get('positions'))) > 0 for p in self.positions):
            raise RuntimeError('BloFin requires all positions/orders closed before changing position mode.')
        out=self.client.set_position_mode('long_short_mode',True);self.position_mode=self.client.get_position_mode();self._event('position_mode_changed',result=out)
        return self.position_mode

    def arm(self,confirmation=''):
        with self.lock:
            if self.cfg.environment=='live' and confirmation!='LIVE':raise ValueError('Type LIVE in the dashboard to arm real-money mode')
            self._init_exchange();self._bootstrap_market();self.armed=True;self.kill_reason='';self.last_message=f'ARMED in {self.cfg.environment.upper()} mode · all-timeframe engine active';self._event('armed')
    def disarm(self,reason='User stopped new entries'):
        self.armed=False;self.last_message=reason;self._event('disarmed',reason=reason)

    def close_bot_positions_and_disarm(self):
        self.armed=False;errors=[]
        try:
            if self.cfg.environment=='paper':
                for p in list(self.paper_positions):self._paper_close(p,'manual stop')
            else:
                self._refresh_private();live_by_id={str(p.get('positionId') or ''):p for p in self.positions}
                for pid,meta in list(self.bot_owned.items()):
                    p=live_by_id.get(pid)
                    if not p:continue
                    try:self.client.close_position(self.cfg.instrument,self.margin_mode,str(p.get('positionSide') or meta.get('positionSide') or 'long'),pid)
                    except Exception as e:errors.append(f'{pid}: {e}')
                self._refresh_private()
            self.last_message='Bot stopped; close requests sent for bot-owned positions.' if not errors else 'Bot stopped; some close requests failed.'
        except Exception as e:errors.append(str(e))
        if errors:self.last_error='; '.join(errors)

    def _refresh_private(self):
        self.positions=self.client.get_positions(self.cfg.instrument)
        bal=self.client.get_balance();details=bal.get('details') or [];eq=f(bal.get('totalEquity'))
        if not eq and details:eq=f(details[0].get('equity') or details[0].get('available'))
        if eq>0:self.cached_equity=eq
    def _equity(self):
        if self.cfg.environment=='paper':return self.paper_equity
        self._refresh_private();return float(self.cached_equity or 0)
    def _reset_day(self,equity):
        k=datetime.now(timezone.utc).date().isoformat()
        if k!=self.day_key:self.day_key=k;self.day_start_equity=equity;self.day_realized=0.
    def _guard(self,equity):
        self._reset_day(equity)
        if self.day_start_equity>0 and equity<=self.day_start_equity*(1-self.cfg.max_daily_loss_pct/100):return 'daily equity stop reached'
        return ''

    def _bootstrap_market(self):
        for tf,bar in TF_BARS.items():
            if self.cache.get(tf):continue
            try:
                self.cache[tf]=self.client.get_candles(self.cfg.instrument,bar,600)
                closed=[x for x in self.cache[tf] if x.get('closed')]
                if closed:self.last_closed_t[tf]=int(closed[-1]['t'])
            except Exception as e:self._event('market_bootstrap_error',timeframe=tf,error=str(e))
        self._evaluate_market()

    @staticmethod
    def _refresh_interval(tf):
        if tf in {'1m','3m','5m'}:return 5.0
        if tf in {'15m','30m','1h','2h','4h'}:return 15.0
        if tf in {'6h','8h','12h','1d','3d'}:return 30.0
        return 60.0
    def _merge(self,old,new,keep=700):
        m={int(x['t']):x for x in old}
        for x in new:m[int(x['t'])]=x
        return [m[k] for k in sorted(m)][-keep:]
    def _refresh_due_timeframes(self):
        now=time.time();changed=False;closed_changed=[]
        for tf,bar in TF_BARS.items():
            if now<self._next_tf_refresh.get(tf,0):continue
            self._next_tf_refresh[tf]=now+self._refresh_interval(tf)
            try:
                fresh=self.client.get_candles(self.cfg.instrument,bar,4)
                self.cache[tf]=self._merge(self.cache.get(tf,[]),fresh)
                closed=[x for x in self.cache[tf] if x.get('closed')]
                if closed:
                    ct=int(closed[-1]['t'])
                    if self.last_closed_t.get(tf)!=ct:
                        self.last_closed_t[tf]=ct;closed_changed.append(tf);changed=True
            except Exception as e:self._event('market_refresh_error',timeframe=tf,error=str(e))
        return changed,closed_changed

    def _evaluate_market(self):
        ev=evaluate_all(self.cache,self.runtime['signal_mode'],self.runtime['min_quality'],self.runtime['min_confluence'],self.runtime['tp_r_multiple'],set(self.runtime['enabled_timeframes']))
        self.last_eval=ev;self.last_candidates=[c.to_dict() for c in ev.candidates];self.last_rejected=ev.rejected;self.last_scan_at=iso_now();return ev

    def _open_risk_usd(self):
        if self.cfg.environment=='paper':return sum(f(p.get('risk_usd')) for p in self.paper_positions)
        return sum(f(meta.get('risk_usd')) for meta in self.bot_owned.values())
    def _position_count(self):
        if self.cfg.environment=='paper':return len(self.paper_positions)
        return len([p for p in self.positions if abs(f(p.get('positions'))) > 0])

    def _execute(self,c:Candidate,ticker,equity):
        live=f(ticker.get('last'));bid=f(ticker.get('bidPrice'));ask=f(ticker.get('askPrice'))
        if not live:return False
        if self._position_count()>=EXCHANGE_MAX_POSITIONS:
            self._event('entry_rejected',timeframe=c.timeframe,side=c.action,reason='BloFin 10-position instrument limit reached');return False
        if bid and ask:
            bps=(ask-bid)/((ask+bid)/2)*10000
            if bps>self.cfg.max_spread_bps:self._event('entry_rejected',timeframe=c.timeframe,side=c.action,reason=f'spread {bps:.1f} bps');return False
        a=(self.last_eval.analyses.get(c.timeframe) if self.last_eval else {}) or {};atr=f(a.get('atr'));ref=float(c.entry_reference)
        if atr and abs(live-ref)>self.cfg.max_entry_slippage_atr*atr:
            self._event('entry_rejected',timeframe=c.timeframe,side=c.action,reason='price moved too far from signal close');return False
        shift=live-ref;stop=float(c.stop)+shift;target=float(c.target)+shift;tick=f(self.instrument.get('tickSize'),.1)
        stop_s=quantize_price(stop,tick);target_s=quantize_price(target,tick)
        plan=size_for_risk(equity,live,float(stop_s),self.instrument,self.runtime['risk_pct'],self.runtime['leverage'],self.runtime['max_margin_use_pct'])
        cap_usd=equity*self.runtime['max_total_open_risk_pct']/100
        if self._open_risk_usd()+plan.risk_usd>cap_usd:
            self._event('entry_rejected',timeframe=c.timeframe,side=c.action,reason=f'portfolio risk cap {self.runtime["max_total_open_risk_pct"]:.1f}% reached');return False
        sigkey=f'{c.timeframe}:{c.signal_bar_t}:{c.action}'
        if sigkey in self.last_processed:return False
        if self.cfg.environment=='paper':
            pid=f'PAPER-{int(time.time()*1000)}-{c.timeframe}'
            p={'positionId':pid,'positionSide':'long' if c.action=='BUY' else 'short','positions':plan.contracts,'averagePrice':live,'markPrice':live,'stop':float(stop_s),'target':float(target_s),'contractValue':f(self.instrument.get('contractValue')),'timeframe':c.timeframe,'quality':c.quality,'confluence':c.confluence,'risk_usd':plan.risk_usd,'openTime':int(time.time()*1000)}
            self.paper_positions.append(p);self.positions=list(self.paper_positions);oid='PAPER';self.bot_owned[pid]=dict(p)
        else:
            ps='long' if c.action=='BUY' else 'short';before={str(p.get('positionId') or '') for p in self.positions if p.get('positionId')}
            self.client.set_leverage(self.cfg.instrument,self.runtime['leverage'],self.margin_mode,ps)
            o=self.client.place_market_order(self.cfg.instrument,self.margin_mode,ps,'buy' if c.action=='BUY' else 'sell',plan.contracts,sl_price=stop_s,tp_price=target_s)
            oid=str(o.get('orderId',''));pid=str(o.get('positionId') or '')
            time.sleep(.7);self._refresh_private()
            if not pid:
                fresh=[p for p in self.positions if str(p.get('positionId') or '') not in before and str(p.get('positionSide') or '')==ps]
                if fresh:pid=str(max(fresh,key=lambda p:f(p.get('createTime'))).get('positionId') or '')
            if pid:self.bot_owned[pid]={'timeframe':c.timeframe,'positionSide':ps,'entry':live,'stop':float(stop_s),'target':float(target_s),'risk_usd':plan.risk_usd,'quality':c.quality,'confluence':c.confluence,'order_id':oid}
            else:self._event('position_tracking_warning',order_id=oid,timeframe=c.timeframe,reason='order filled but positionId not resolved yet')
        self.last_processed.add(sigkey);self.last_message=f'{c.action} {c.timeframe} opened · {plan.contracts} contracts · risk ≈ ${plan.risk_usd:.2f}'
        self._trade('OPEN',position_id=pid,timeframe=c.timeframe,side=c.action,entry=round(live,2),contracts=plan.contracts,stop=stop_s,target=target_s,quality=c.quality,confluence=c.confluence,reason=c.reason,order_id=oid)
        self._event('position_opened',position_id=pid,timeframe=c.timeframe,side=c.action,quality=c.quality,confluence=c.confluence,risk_usd=plan.risk_usd)
        return True

    def _paper_mark(self,t):
        px=f(t.get('last'))
        for p in list(self.paper_positions):
            p['markPrice']=px;side=p['positionSide']
            if side=='long' and px<=p['stop']:self._paper_close(p,'stop',p['stop'])
            elif side=='long' and px>=p['target']:self._paper_close(p,'target',p['target'])
            elif side=='short' and px>=p['stop']:self._paper_close(p,'stop',p['stop'])
            elif side=='short' and px<=p['target']:self._paper_close(p,'target',p['target'])
        self.positions=list(self.paper_positions)
    def _paper_close(self,p,reason,exit_price=None):
        if p not in self.paper_positions:return
        x=float(exit_price if exit_price is not None else f((self.last_ticker or {}).get('last'),p['averagePrice']));entry=f(p['averagePrice']);contracts=f(p['positions']);cv=f(p['contractValue']);sg=1 if p['positionSide']=='long' else -1
        pnl=(x-entry)*cv*contracts*sg;self.paper_equity+=pnl;self.cached_equity=self.paper_equity;self.day_realized+=pnl
        self._trade('CLOSE',position_id=p['positionId'],timeframe=p.get('timeframe',''),side=p['positionSide'],entry=entry,exit=x,contracts=contracts,stop=p['stop'],target=p['target'],pnl=round(pnl,4),quality=p.get('quality',''),confluence=p.get('confluence',''),reason=reason)
        self._event('position_closed',position_id=p['positionId'],timeframe=p.get('timeframe',''),pnl=round(pnl,4),reason=reason)
        self.paper_positions.remove(p);self.bot_owned.pop(p['positionId'],None);self.positions=list(self.paper_positions);self.last_message=f'{p.get("timeframe","")} paper position closed ({reason}) · PnL ${pnl:+.2f}'

    def _scan(self):
        t=self.client.get_ticker(self.cfg.instrument);self.last_ticker=t
        if self.cfg.environment=='paper':self._paper_mark(t)
        else:self._refresh_private()
        changed,changed_tfs=self._refresh_due_timeframes()
        if not changed and self.last_eval is not None:return
        ev=self._evaluate_market()
        if not self.armed:return
        eq=self._equity();g=self._guard(eq)
        if g:self.armed=False;self.kill_reason=g;self.last_message='Risk guard stopped new entries: '+g;return
        opened=0
        for c in ev.candidates:
            key=f'{c.timeframe}:{c.signal_bar_t}:{c.action}'
            if key in self.last_processed:continue
            if c.timeframe not in changed_tfs:continue
            if self._execute(c,t,eq):opened+=1
            if self._position_count()>=EXCHANGE_MAX_POSITIONS:break
        if opened==0 and ev.candidates:self.last_message=f'{len(ev.candidates)} fresh/active candidate(s); no new entry passed execution/risk checks.'
        elif opened==0:self.last_message=f'Market {ev.overall_direction} {ev.overall_score:+.1f}; waiting for a fresh confirmed signal on any enabled timeframe.'

    def update_runtime(self,payload:dict[str,Any]):
        with self.lock:
            if 'signal_mode' in payload:
                v=str(payload['signal_mode'])
                if v not in {'Conservative','Balanced','Aggressive'}:raise ValueError('Invalid signal mode')
                self.runtime['signal_mode']=v
            bounds={'risk_pct':(.01,3.0),'leverage':(1.0,self.cfg.max_software_leverage),'max_margin_use_pct':(1.0,80.0),'max_total_open_risk_pct':(.5,20.0),'min_quality':(35.0,85.0),'min_confluence':(25.0,85.0),'tp_r_multiple':(.75,5.0)}
            for k,(lo,hi) in bounds.items():
                if k in payload:
                    v=float(payload[k])
                    if not lo<=v<=hi:raise ValueError(f'{k} must be between {lo} and {hi}')
                    self.runtime[k]=v
            if 'enabled_timeframes' in payload:
                vals={str(x) for x in payload['enabled_timeframes'] if str(x) in TF_ORDER}
                if not vals:raise ValueError('At least one timeframe must be enabled')
                self.runtime['enabled_timeframes']=vals
            self._event('runtime_settings_updated',settings=self.runtime_public());self._evaluate_market()
            return self.runtime_public()
    def runtime_public(self):
        r=dict(self.runtime);r['enabled_timeframes']=[tf for tf in TF_ORDER if tf in self.runtime['enabled_timeframes']];return r

    def chart_data(self,tf='1h',limit=160):
        if tf not in TF_ORDER:raise ValueError('Unsupported timeframe')
        xs=self.cache.get(tf) or []
        return {'timeframe':tf,'candles':xs[-max(30,min(300,int(limit))):],'analysis':(self.last_eval.analyses.get(tf) if self.last_eval else {})}

    def _loop(self):
        try:self.instrument=self.client.get_instrument(self.cfg.instrument);self._bootstrap_market()
        except Exception as e:self.last_error=str(e)
        while self.running:
            try:self._scan();self.last_error=''
            except Exception as e:self.last_error=str(e);self._event('error',error=str(e))
            time.sleep(max(.5,self.cfg.loop_seconds))

    def _position_view(self):
        out=[]
        src=self.paper_positions if self.cfg.environment=='paper' else self.positions
        for p in src:
            if abs(f(p.get('positions')))<=0:continue
            pid=str(p.get('positionId') or '');meta=self.bot_owned.get(pid,{})
            row=dict(p);row['botOwned']=bool(meta);row['timeframe']=meta.get('timeframe') or p.get('timeframe') or '';row['stop']=meta.get('stop') or p.get('stop');row['target']=meta.get('target') or p.get('target');row['risk_usd']=meta.get('risk_usd') or p.get('risk_usd');row['quality']=meta.get('quality') or p.get('quality');row['confluence']=meta.get('confluence') or p.get('confluence');out.append(row)
        return out

    def status(self):
        t=self.last_ticker or {};eq=self.paper_equity if self.cfg.environment=='paper' else self.cached_equity;ev=self.last_eval
        return {
            'time':iso_now(),'running':self.running,'armed':self.armed,'environment':self.cfg.environment,'instrument':self.cfg.instrument,
            'price':f(t.get('last')) or None,'bid':f(t.get('bidPrice')) or None,'ask':f(t.get('askPrice')) or None,'equity':eq,
            'day_start_equity':self.day_start_equity,'day_realized':round(self.day_realized,4),'margin_mode':self.margin_mode,'position_mode':self.position_mode,
            'positions':self._position_view(),'open_position_count':self._position_count(),'exchange_position_cap':EXCHANGE_MAX_POSITIONS,
            'last_scan_at':self.last_scan_at,'last_message':self.last_message,'last_error':self.last_error,'kill_reason':self.kill_reason,
            'runtime':self.runtime_public(),'overall':{'score':ev.overall_score,'direction':ev.overall_direction,'horizons':ev.horizons} if ev else None,
            'analyses':ev.analyses if ev else {},'candidates':self.last_candidates[:20],'rejected':self.last_rejected[-20:],
            'open_risk_usd':round(self._open_risk_usd(),4),'recent_events':list(self.recent)[:30],
            'risk':{'max_daily_loss_pct':self.cfg.max_daily_loss_pct,'max_spread_bps':self.cfg.max_spread_bps,'max_entry_slippage_atr':self.cfg.max_entry_slippage_atr}
        }
