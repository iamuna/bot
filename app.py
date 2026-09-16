from __future__ import annotations

import os,socket,threading,webbrowser
from flask import Flask,Response,jsonify,render_template,request

from bot import Terminal3BloFinBot,TRADE_LOG
from config import BotConfig

APP_VERSION="2.1"
APP_TITLE="Terminal 3.0 · BloFin 30-Timeframe Bot"
cfg=BotConfig().validated();bot=Terminal3BloFinBot(cfg);bot.start_thread();app=Flask(__name__)

@app.route('/')
def index():return render_template('index.html',version=APP_VERSION,environment=cfg.environment)
@app.route('/api/status')
def status():return jsonify(bot.status())
@app.route('/api/chart')
def chart():
    try:return jsonify({'ok':True,**bot.chart_data(request.args.get('tf','1h'),int(request.args.get('limit','160')))})
    except Exception as e:return jsonify({'ok':False,'error':str(e)}),400
@app.route('/api/settings',methods=['POST'])
def settings():
    try:return jsonify({'ok':True,'settings':bot.update_runtime(request.get_json(silent=True) or {})})
    except Exception as e:return jsonify({'ok':False,'error':str(e)}),400
@app.route('/api/arm',methods=['POST'])
def arm():
    try:
        p=request.get_json(silent=True) or {};bot.arm(str(p.get('confirmation','')));return jsonify({'ok':True,'status':bot.status()})
    except Exception as e:return jsonify({'ok':False,'error':str(e)}),400
@app.route('/api/stop',methods=['POST'])
def stop():bot.disarm();return jsonify({'ok':True,'status':bot.status()})
@app.route('/api/kill',methods=['POST'])
def kill():bot.close_bot_positions_and_disarm();return jsonify({'ok':True,'status':bot.status()})
@app.route('/api/enable-multiposition',methods=['POST'])
def multi():
    try:return jsonify({'ok':True,'position_mode':bot.enable_multi_position_mode()})
    except Exception as e:return jsonify({'ok':False,'error':str(e)}),400
@app.route('/api/trades.csv')
def trades_csv():
    if not TRADE_LOG.exists():return Response('',mimetype='text/csv')
    return Response(TRADE_LOG.read_text(encoding='utf-8'),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=terminal3_blofin_30tf_trades.csv'})
@app.route('/health')
def health():
    s=bot.status();return jsonify({'ok':True,'armed':s['armed'],'environment':s['environment'],'price':s['price'],'positions':s['open_position_count'],'unresolved_orders':s['unresolved_order_count']})

def find_port(preferred=8803):
    for port in range(preferred,preferred+30):
        with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
            try:s.bind(('127.0.0.1',port));return port
            except OSError:pass
    raise RuntimeError('No free local port found')

def main():
    port=find_port();url=f'http://127.0.0.1:{port}'
    print(f'{APP_TITLE} v{APP_VERSION}');print(f'Mode: {cfg.environment.upper()} · 30 timeframes (15 BloFin native + 15 constructed) · Instrument: {cfg.instrument}');print(f'Dashboard: {url}')
    if cfg.environment=='live':print('LIVE mode enabled locally. Dashboard still requires typing LIVE before arming.')
    else:print('Real-money trading is not enabled.')
    if os.environ.get('AUTO_OPEN_BROWSER','1')=='1':threading.Timer(1.0,lambda:webbrowser.open(url)).start()
    app.run(host='127.0.0.1',port=port,debug=False,threaded=True,use_reloader=False)

if __name__=='__main__':main()
