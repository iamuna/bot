from __future__ import annotations

import os,socket,threading,time,webbrowser
from datetime import datetime,timezone
from pathlib import Path
from flask import Flask,Response,jsonify,render_template,request

from automation import ensure_multi_position
from bot import Terminal3BloFinBot,TRADE_LOG,EVENT_LOG
from config import BotConfig
from reporting import REPORT_INTERVAL_SECONDS,build_report,report_markdown,save_report

APP_VERSION="2.3"
APP_TITLE="Terminal 3.0 · BloFin 30-Timeframe Bot"
cfg=BotConfig().validated();bot=Terminal3BloFinBot(cfg);bot.start_thread();app=Flask(__name__)

REPORT_DIR=Path(__file__).resolve().parent/'logs'/'reports'
report_lock=threading.RLock()
latest_report=None
report_window_start=None
report_start_equity=None
next_report_at=None
last_armed=False


def _report_meta():
    with report_lock:
        return {
            'interval_hours':3,
            'latest':latest_report,
            'window_start':report_window_start.isoformat() if report_window_start else None,
            'next_report_at':datetime.fromtimestamp(next_report_at,timezone.utc).isoformat() if next_report_at else None,
        }


def _generate_report(now=None):
    global latest_report,report_window_start,report_start_equity,next_report_at
    now=now or datetime.now(timezone.utc)
    with report_lock:
        start=report_window_start or now
        state=bot.status();state['report_start_equity']=report_start_equity
        report=build_report(TRADE_LOG,EVENT_LOG,state,start,now)
        save_report(REPORT_DIR,report)
        latest_report=report
        report_window_start=now
        report_start_equity=state.get('equity')
        next_report_at=time.time()+REPORT_INTERVAL_SECONDS
        try:bot._event('three_hour_report',realized_pnl=report['performance']['realized_pnl'],opened=report['performance']['opened'],closed=report['performance']['closed'])
        except Exception:pass
        return report


def _report_loop():
    global report_window_start,report_start_equity,next_report_at,last_armed
    while True:
        try:
            state=bot.status();armed=bool(state.get('armed'));now=time.time()
            with report_lock:
                if armed and not last_armed:
                    report_window_start=datetime.now(timezone.utc);report_start_equity=state.get('equity');next_report_at=now+REPORT_INTERVAL_SECONDS
                elif not armed:
                    report_window_start=None;report_start_equity=None;next_report_at=None
                due=armed and next_report_at is not None and now>=next_report_at
                last_armed=armed
            if due:_generate_report(datetime.now(timezone.utc))
        except Exception:
            pass
        time.sleep(10)

threading.Thread(target=_report_loop,daemon=True,name='three-hour-report').start()

@app.route('/')
def index():return render_template('index.html',version=APP_VERSION,environment=cfg.environment)
@app.route('/api/status')
def status():
    s=bot.status();s['reporting']=_report_meta();return jsonify(s)
@app.route('/api/chart')
def chart():
    try:return jsonify({'ok':True,**bot.chart_data(request.args.get('tf','1h'),int(request.args.get('limit','160')))})
    except Exception as e:return jsonify({'ok':False,'error':str(e)}),400
@app.route('/api/settings',methods=['POST'])
def settings():
    try:
        p=request.get_json(silent=True) or {}
        unknown=set(p)-{'enabled_timeframes'}
        if unknown:raise ValueError('The trading profile is fixed in v2.3; only timeframe AUTO switches can be changed.')
        return jsonify({'ok':True,'settings':bot.update_runtime(p)})
    except Exception as e:return jsonify({'ok':False,'error':str(e)}),400
@app.route('/api/arm',methods=['POST'])
def arm():
    try:
        p=request.get_json(silent=True) or {}
        ensure_multi_position(bot)
        bot.arm(str(p.get('confirmation','')))
        return jsonify({'ok':True,'status':bot.status()})
    except Exception as e:return jsonify({'ok':False,'error':str(e)}),400
@app.route('/api/stop',methods=['POST'])
def stop():bot.disarm();return jsonify({'ok':True,'status':bot.status()})
@app.route('/api/kill',methods=['POST'])
def kill():bot.close_bot_positions_and_disarm();return jsonify({'ok':True,'status':bot.status()})
@app.route('/api/trades.csv')
def trades_csv():
    if not TRADE_LOG.exists():return Response('',mimetype='text/csv')
    return Response(TRADE_LOG.read_text(encoding='utf-8'),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=terminal3_blofin_30tf_trades.csv'})
@app.route('/api/report/latest')
def report_latest():
    with report_lock:
        if latest_report is None:return jsonify({'ok':False,'error':'No 3-hour report has been generated yet.'}),404
        return jsonify({'ok':True,'report':latest_report})
@app.route('/api/report/latest.md')
def report_latest_md():
    with report_lock:
        if latest_report is None:return Response('No 3-hour report has been generated yet.\n',status=404,mimetype='text/plain')
        return Response(report_markdown(latest_report),mimetype='text/markdown',headers={'Content-Disposition':'attachment; filename=terminal3_latest_3h_report.md'})
@app.route('/health')
def health():
    s=bot.status();return jsonify({'ok':True,'armed':s['armed'],'environment':s['environment'],'price':s['price'],'positions':s['open_position_count'],'unresolved_orders':s['unresolved_order_count'],'reporting':_report_meta()})

def find_port(preferred=8803):
    for port in range(preferred,preferred+30):
        with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
            try:s.bind(('127.0.0.1',port));return port
            except OSError:pass
    raise RuntimeError('No free local port found')

def main():
    port=find_port();url=f'http://127.0.0.1:{port}'
    print(f'{APP_TITLE} v{APP_VERSION}');print(f'Mode: {cfg.environment.upper()} · 30 timeframes (15 BloFin native + 15 constructed) · Instrument: {cfg.instrument}');print(f'Profile: {cfg.profile_name} · multi-position is automatic when armed');print('Automatic performance report: every 3 hours while armed');print(f'Dashboard: {url}')
    if cfg.environment=='live':print('LIVE mode enabled locally. Dashboard still requires typing LIVE before arming.')
    else:print('Real-money trading is not enabled.')
    if os.environ.get('AUTO_OPEN_BROWSER','1')=='1':threading.Timer(1.0,lambda:webbrowser.open(url)).start()
    app.run(host='127.0.0.1',port=port,debug=False,threaded=True,use_reloader=False)

if __name__=='__main__':main()
