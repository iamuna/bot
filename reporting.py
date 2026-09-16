from __future__ import annotations

import csv,json,math
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
from typing import Any

REPORT_INTERVAL_SECONDS=3*60*60


def _parse_time(value:str):
    try:return datetime.fromisoformat(str(value).replace('Z','+00:00')).astimezone(timezone.utc)
    except Exception:return None


def _f(value,default=0.0):
    try:return float(value)
    except Exception:return default


def _read_trade_rows(path:Path,start:datetime,end:datetime):
    if not path.exists():return []
    out=[]
    try:
        with path.open('r',encoding='utf-8',newline='') as fh:
            for row in csv.DictReader(fh):
                ts=_parse_time(row.get('time_utc',''))
                if ts and start<=ts<=end:out.append(row)
    except Exception:return []
    return out


def _read_events(path:Path,start:datetime,end:datetime):
    if not path.exists():return []
    out=[]
    try:
        for raw in path.read_text(encoding='utf-8').splitlines():
            if not raw.strip():continue
            try:row=json.loads(raw);ts=_parse_time(row.get('time',''))
            except Exception:continue
            if ts and start<=ts<=end:out.append(row)
    except Exception:return []
    return out


def summarize_window(trades:list[dict[str,Any]],events:list[dict[str,Any]]):
    opens=[r for r in trades if str(r.get('event','')).upper()=='OPEN']
    closes=[r for r in trades if str(r.get('event','')).upper()=='CLOSE']
    pnls=[_f(r.get('pnl')) for r in closes]
    wins=[x for x in pnls if x>0];losses=[x for x in pnls if x<0];flats=[x for x in pnls if x==0]
    gross_profit=sum(wins);gross_loss=abs(sum(losses));profit_factor=(gross_profit/gross_loss if gross_loss>0 else (math.inf if gross_profit>0 else None))
    tf=defaultdict(lambda:{'opens':0,'closes':0,'pnl':0.0,'wins':0,'losses':0})
    for r in opens:tf[str(r.get('timeframe') or '?')]['opens']+=1
    for r in closes:
        k=str(r.get('timeframe') or '?');p=_f(r.get('pnl'));tf[k]['closes']+=1;tf[k]['pnl']+=p
        if p>0:tf[k]['wins']+=1
        elif p<0:tf[k]['losses']+=1
    by_tf={k:{**v,'pnl':round(v['pnl'],4)} for k,v in sorted(tf.items(),key=lambda kv:(-abs(kv[1]['pnl']),kv[0]))}
    reject_reasons=Counter(str(e.get('reason') or 'unspecified') for e in events if e.get('kind')=='entry_rejected')
    return {
        'opened':len(opens),'closed':len(closes),'wins':len(wins),'losses':len(losses),'flats':len(flats),
        'win_rate_pct':round(100*len(wins)/len(closes),1) if closes else None,
        'realized_pnl':round(sum(pnls),4),'avg_closed_trade_pnl':round(sum(pnls)/len(closes),4) if closes else None,
        'gross_profit':round(gross_profit,4),'gross_loss':round(gross_loss,4),
        'profit_factor':round(profit_factor,3) if profit_factor is not None and math.isfinite(profit_factor) else ('inf' if profit_factor==math.inf else None),
        'by_timeframe':by_tf,'execution_rejections':sum(reject_reasons.values()),'top_rejection_reasons':reject_reasons.most_common(8),
    }


def build_report(trade_log:Path,event_log:Path,state:dict[str,Any],start:datetime,end:datetime):
    trades=_read_trade_rows(trade_log,start,end);events=_read_events(event_log,start,end);perf=summarize_window(trades,events)
    overall=state.get('overall') or {};price=state.get('price');equity=state.get('equity')
    report={
        'kind':'3-hour bot report','generated_at':end.isoformat(),'window_start':start.isoformat(),'window_end':end.isoformat(),
        'environment':state.get('environment'),'instrument':state.get('instrument'),'armed':state.get('armed'),
        'price':price,'equity':equity,'open_positions':state.get('open_position_count',0),'open_planned_risk_usd':state.get('open_risk_usd',0),
        'market':{'direction':overall.get('direction'),'score':overall.get('score'),'horizons':overall.get('horizons') or {}},
        'signals':{'active_candidates':len(state.get('candidates') or []),'recent_strategy_rejections':len(state.get('rejected') or [])},
        'performance':perf,
    }
    start_equity=_f(state.get('report_start_equity'),0)
    if start_equity>0 and equity is not None:
        report['equity_change_since_report_start']=round(_f(equity)-start_equity,4)
        report['equity_change_since_report_start_pct']=round(100*(_f(equity)-start_equity)/start_equity,3)
    return report


def report_markdown(report:dict[str,Any]):
    p=report['performance'];m=report['market'];eq=report.get('equity');change=report.get('equity_change_since_report_start');change_pct=report.get('equity_change_since_report_start_pct')
    pf=p.get('profit_factor');wr=p.get('win_rate_pct')
    lines=[
        '# BTC Bot — 3 Hour Report','',
        f"**Window:** {report['window_start']} → {report['window_end']}",
        f"**Mode:** {str(report.get('environment','')).upper()} · **BTC:** ${_f(report.get('price')):,.2f}",
        f"**Market bias:** {m.get('direction','—')} {m.get('score','—')}",
        f"**Equity:** ${_f(eq):,.2f}"+(f" · window change ${change:+.2f} ({change_pct:+.2f}%)" if change is not None else ''),
        f"**Open positions:** {report.get('open_positions',0)} · planned risk ${_f(report.get('open_planned_risk_usd')):,.2f}",'',
        '## Trading performance','',
        f"- Opened: {p['opened']} · Closed: {p['closed']}",
        f"- Wins: {p['wins']} · Losses: {p['losses']} · Win rate: {wr if wr is not None else 'n/a'}%",
        f"- Realized P&L: ${p['realized_pnl']:+.2f} · Avg closed trade: {('$'+format(p['avg_closed_trade_pnl'],'+.2f')) if p['avg_closed_trade_pnl'] is not None else 'n/a'}",
        f"- Profit factor: {pf if pf is not None else 'n/a'}",
        f"- Execution rejections: {p['execution_rejections']}",'',
        '## Timeframes','',
    ]
    if p['by_timeframe']:
        for tf,x in p['by_timeframe'].items():lines.append(f"- **{tf}** — opens {x['opens']}, closes {x['closes']}, wins {x['wins']}, losses {x['losses']}, P&L ${x['pnl']:+.2f}")
    else:lines.append('- No trades in this window.')
    if p['top_rejection_reasons']:
        lines+=['','## Top execution rejection reasons','']+[f"- {n}× {reason}" for reason,n in p['top_rejection_reasons']]
    lines+=['','## Current horizon scores','']
    for name,x in (m.get('horizons') or {}).items():lines.append(f"- **{name}**: {x.get('direction','—')} {x.get('score','—')} · agreement {x.get('agreement','—')}%")
    return '\n'.join(lines)+'\n'


def save_report(report_dir:Path,report:dict[str,Any]):
    report_dir.mkdir(parents=True,exist_ok=True)
    stamp=datetime.fromisoformat(report['generated_at']).strftime('%Y%m%d_%H%M%S_UTC')
    json_path=report_dir/f'report_{stamp}.json';md_path=report_dir/f'report_{stamp}.md'
    json_path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    md=report_markdown(report);md_path.write_text(md,encoding='utf-8')
    (report_dir/'latest.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    (report_dir/'latest.md').write_text(md,encoding='utf-8')
    return {'json':str(json_path),'markdown':str(md_path),'latest_json':str(report_dir/'latest.json'),'latest_markdown':str(report_dir/'latest.md')}
