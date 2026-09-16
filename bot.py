from __future__ import annotations

import csv,json,threading,time
from datetime import datetime,timezone
from pathlib import Path
from typing import Any

from blofin_client import BloFinClient,quantize_price
from config import BotConfig
from risk import size_for_risk
from strategy import evaluate

ROOT=Path(__file__).resolve().parent
LOG_DIR=ROOT/'logs';LOG_DIR.mkdir(exist_ok=True)
TRADE_LOG=LOG_DIR/'trades.csv';EVENT_LOG=LOG_DIR/'events.jsonl'

def iso_now():return datetime.now(timezone.utc).isoformat()
def f(v,d=0.0):
    try:return float(v)
    except:return d

class Terminal3BloFinBot:
    def __init__(self,cfg:BotConfig):
        self.cfg=cfg.validated();self.client=BloFinClient(cfg.api_key,cfg.secret_key,cfg.passphrase,demo=cfg.environment=='demo')
        self.lock=threading.RLock();self.running=False;self.armed=False;self.thread=None;self.last_error='';self.last_message='Bot initialized; not armed.'
        self.last_decision=None;self.last_scan_at='';self.last_ticker=None;self.last_closed_3m_t=None;self.last_processed_signal_t=None
        self.instrument=None;self.margin_mode='isolated';self.position_mode={'positionMode':'net_mode','multiPosition':'false'};self.position=None;self.bot_owned_position=False
        self.paper_position=None;self.paper_equity=float(cfg.paper_equity);self.cached_equity=self.paper_equity if cfg.environment=='paper' else None
        self.day_key='';self.day_start_equity=self.paper_equity;self.day_realized=0.;self.trades_today=0;self.consecutive_losses=0;self.cooldown_until_ms=0;self.kill_reason=''
        self._ensure_log()
    def _ensure_log(self):
        if not TRADE_LOG.exists():
            with TRADE_LOG.open('w',newline='',encoding='utf-8') as x:csv.writer(x).writerow(['time_utc','environment','event','side','entry','exit','contracts','stop','target','pnl','reason','order_id'])
    def _event(self,kind,**kw):
        with EVENT_LOG.open('a',encoding='utf-8') as x:x.write(json.dumps({'time':iso_now(),'kind':kind,**kw},separators=(',',':'))+'\n')
    def _trade(self,event,**kw):
        with TRADE_LOG.open('a',newline='',encoding='utf-8') as x:csv.writer(x).writerow([iso_now(),self.cfg.environment,event,kw.get('side',''),kw.get('entry',''),kw.get('exit',''),kw.get('contracts',''),kw.get('stop',''),kw.get('target',''),kw.get('pnl',''),kw.get('reason',''),kw.get('order_id','')])
    def start_thread(self):
        if self.running:return
        self.running=True;self.thread=threading.Thread(target=self._loop,daemon=True);self.thread.start()
    def _init_exchange(self):
        self.instrument=self.client.get_instrument(self.cfg.instrument)
        if self.cfg.environment!='paper':
            self.margin_mode=self.client.get_margin_mode();self.position_mode=self.client.get_position_mode()
            if str(self.position_mode.get('multiPosition','false')).lower()=='true':raise RuntimeError('Multi-Position mode is not supported by this bot')
            self._refresh_private()
    def arm(self,confirmation=''):
        with self.lock:
            if self.cfg.environment=='live' and confirmation!='LIVE':raise ValueError('Type LIVE in the dashboard to arm real-money mode')
            self._init_exchange();self.armed=True;self.kill_reason='';self.last_message=f'ARMED in {self.cfg.environment.upper()} mode';self._event('armed')
    def disarm(self,reason='User stopped bot'):
        self.armed=False;self.last_message=reason;self._event('disarmed',reason=reason)
    def close_bot_position_and_disarm(self):
        self.armed=False
        try:
            if self.cfg.environment=='paper' and self.paper_position:self._paper_close('manual stop')
            elif self.bot_owned_position and self.position:
                ps=str(self.position.get('positionSide') or 'net');pid=str(self.position.get('positionId') or '')
                self.client.close_position(self.cfg.instrument,self.margin_mode,ps,pid);self.last_message='Bot-owned position close requested; bot stopped.'
            else:self.last_message='Bot stopped. No bot-owned position to close.'
        except Exception as e:self.last_error=str(e)
    def _refresh_private(self):
        pos=self.client.get_positions(self.cfg.instrument);self.position=next((p for p in pos if abs(f(p.get('positions'))) > 0),None)
        bal=self.client.get_balance();details=bal.get('details') or []
        eq=f(bal.get('totalEquity'))
        if not eq and details: eq=f(details[0].get('equity') or details[0].get('available'))
        if eq>0:self.cached_equity=eq
    def _equity(self):
        if self.cfg.environment=='paper':return self.paper_equity
        self._refresh_private();return float(self.cached_equity or 0)
    def _reset_day(self,equity):
        k=datetime.now(timezone.utc).date().isoformat()
        if k!=self.day_key:self.day_key=k;self.day_start_equity=equity;self.day_realized=0.;self.trades_today=0;self.consecutive_losses=0
    def _guard(self,equity):
        self._reset_day(equity)
        if self.day_start_equity>0 and equity<=self.day_start_equity*(1-self.cfg.max_daily_loss_pct/100):return 'daily equity stop reached'
        if self.trades_today>=self.cfg.max_trades_per_day:return 'max trades/day reached'
        if self.consecutive_losses>=self.cfg.max_consecutive_losses:return 'loss-streak stop reached'
        if int(time.time()*1000)<self.cooldown_until_ms:return 'cooldown active'
        return ''
    def _dataset(self):
        limits={'3m':1000,'15m':900,'1h':700,'4h':500,'1d':350};return {tf:self.client.get_candles(self.cfg.instrument,bar,limits[tf]) for tf,bar in {'3m':'3m','15m':'15m','1h':'1H','4h':'4H','1d':'1D'}.items()}
    def _position_side(self,side):
        mode=str(self.position_mode.get('positionMode','net_mode')).lower();return ('long' if side=='BUY' else 'short') if 'long_short' in mode or 'hedge' in mode else 'net'
    def _execute(self,d,ticker,equity):
        live=f(ticker.get('last'));bid=f(ticker.get('bidPrice'));ask=f(ticker.get('askPrice'))
        if not live:return
        if bid and ask:
            bps=(ask-bid)/((ask+bid)/2)*10000
            if bps>self.cfg.max_spread_bps:self.last_message=f'Signal rejected: spread {bps:.1f} bps';return
        atr=f((d.analyses.get('3m') or {}).get('atr'));ref=float(d.entry_reference);sign=1 if d.action=='BUY' else -1
        if atr and abs(live-ref)>self.cfg.max_entry_slippage_atr*atr:self.last_message='Signal rejected: entry moved too far from signal close';return
        shift=live-ref;stop=float(d.stop)+shift;target=float(d.target)+shift
        tick=f(self.instrument.get('tickSize'),.1);stop_s=quantize_price(stop,tick);target_s=quantize_price(target,tick)
        plan=size_for_risk(equity,live,float(stop_s),self.instrument,self.cfg.risk_pct,self.cfg.leverage,self.cfg.max_margin_use_pct)
        if self.cfg.environment=='paper':
            self.paper_position={'positionSide':'long' if d.action=='BUY' else 'short','positions':plan.contracts,'averagePrice':live,'stop':float(stop_s),'target':float(target_s),'contractValue':f(self.instrument.get('contractValue'))};self.position=self.paper_position;oid='PAPER'
        else:
            ps=self._position_side(d.action);self.client.set_leverage(self.cfg.instrument,self.cfg.leverage,self.margin_mode,ps)
            o=self.client.place_market_order(self.cfg.instrument,self.margin_mode,ps,'buy' if d.action=='BUY' else 'sell',plan.contracts,sl_price=stop_s,tp_price=target_s);oid=str(o.get('orderId',''));time.sleep(.5);self._refresh_private()
        self.bot_owned_position=True;self.trades_today+=1;self.last_processed_signal_t=d.signal_bar_t;self.last_message=f'{d.action} opened: {plan.contracts} contracts · risk ≈ ${plan.risk_usd:.2f}'
        self._trade('OPEN',side=d.action,entry=round(live,2),contracts=plan.contracts,stop=stop_s,target=target_s,reason=d.reason,order_id=oid)
    def _paper_mark(self,t):
        p=self.paper_position
        if not p:return
        px=f(t.get('last'));side=p['positionSide']
        if side=='long' and px<=p['stop']:self._paper_close('stop',p['stop'])
        elif side=='long' and px>=p['target']:self._paper_close('target',p['target'])
        elif side=='short' and px>=p['stop']:self._paper_close('stop',p['stop'])
        elif side=='short' and px<=p['target']:self._paper_close('target',p['target'])
    def _paper_close(self,reason,exit_price=None):
        p=self.paper_position
        if not p:return
        x=float(exit_price if exit_price is not None else f((self.last_ticker or {}).get('last'),p['averagePrice']));entry=f(p['averagePrice']);contracts=f(p['positions']);cv=f(p['contractValue']);sg=1 if p['positionSide']=='long' else -1
        pnl=(x-entry)*cv*contracts*sg;self.paper_equity+=pnl;self.cached_equity=self.paper_equity;self.day_realized+=pnl;self.consecutive_losses=self.consecutive_losses+1 if pnl<0 else 0
        self._trade('CLOSE',side=p['positionSide'],entry=entry,exit=x,contracts=contracts,stop=p['stop'],target=p['target'],pnl=round(pnl,4),reason=reason)
        self.paper_position=None;self.position=None;self.bot_owned_position=False;self.cooldown_until_ms=int(time.time()*1000)+self.cfg.cooldown_bars*180000;self.last_message=f'Paper position closed ({reason}) · PnL ${pnl:+.2f}'
    def _scan(self):
        t=self.client.get_ticker(self.cfg.instrument);self.last_ticker=t
        if self.cfg.environment=='paper':self._paper_mark(t)
        else:self._refresh_private()
        probe=self.client.get_candles(self.cfg.instrument,'3m',35);closed=[b for b in probe if b.get('closed')]
        if not closed:return
        ct=int(closed[-1]['t'])
        if self.last_closed_3m_t==ct:return
        self.last_closed_3m_t=ct;self.last_scan_at=iso_now();d=evaluate(self._dataset(),self.cfg.signal_mode,self.cfg.min_context_score,self.cfg.min_context_agreement,self.cfg.tp_r_multiple)
        self.last_decision={'action':d.action,'reason':d.reason,'entry_reference':d.entry_reference,'stop':d.stop,'target':d.target,'context_score':d.context_score,'context_agreement':d.context_agreement,'signal_bar_t':d.signal_bar_t,'signal':d.signal,'analyses':d.analyses}
        if not self.armed or d.action=='WAIT':self.last_message=d.reason;return
        if d.signal_bar_t==self.last_processed_signal_t:self.last_message='Signal already processed; duplicate prevented.';return
        if self.position or self.paper_position:self.last_message='Signal ignored: BTC position already open.';return
        eq=self._equity();g=self._guard(eq)
        if g:self.armed=False;self.kill_reason=g;self.last_message='Risk guard stopped bot: '+g;return
        self._execute(d,t,eq)
    def _loop(self):
        try:self.instrument=self.client.get_instrument(self.cfg.instrument)
        except Exception as e:self.last_error=str(e)
        while self.running:
            try:self._scan();self.last_error=''
            except Exception as e:self.last_error=str(e);self._event('error',error=str(e))
            time.sleep(max(1.,self.cfg.loop_seconds))
    def status(self):
        t=self.last_ticker or {};eq=self.paper_equity if self.cfg.environment=='paper' else self.cached_equity
        return {'time':iso_now(),'running':self.running,'armed':self.armed,'environment':self.cfg.environment,'instrument':self.cfg.instrument,'signal_mode':self.cfg.signal_mode,'price':f(t.get('last')) or None,'bid':f(t.get('bidPrice')) or None,'ask':f(t.get('askPrice')) or None,'equity':eq,'day_start_equity':self.day_start_equity,'day_realized':round(self.day_realized,4),'trades_today':self.trades_today,'consecutive_losses':self.consecutive_losses,'cooldown_until_ms':self.cooldown_until_ms,'margin_mode':self.margin_mode,'position_mode':self.position_mode,'position':self.position,'bot_owned_position':self.bot_owned_position,'last_closed_3m_t':self.last_closed_3m_t,'last_scan_at':self.last_scan_at,'last_message':self.last_message,'last_error':self.last_error,'kill_reason':self.kill_reason,'decision':self.last_decision,'risk':{'risk_pct':self.cfg.risk_pct,'leverage':self.cfg.leverage,'max_margin_use_pct':self.cfg.max_margin_use_pct,'max_daily_loss_pct':self.cfg.max_daily_loss_pct,'max_trades_per_day':self.cfg.max_trades_per_day,'max_consecutive_losses':self.cfg.max_consecutive_losses,'cooldown_bars':self.cfg.cooldown_bars,'tp_r_multiple':self.cfg.tp_r_multiple}}
