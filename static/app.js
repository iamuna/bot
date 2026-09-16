(() => {
  const $=id=>document.getElementById(id);
  const money=x=>x==null||!Number.isFinite(Number(x))?'—':'$'+Number(x).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
  const signed=(x,d=1)=>x==null||!Number.isFinite(Number(x))?'—':(Number(x)>0?'+':'')+Number(x).toFixed(d);
  const cls=x=>Number(x)>12?'bull':Number(x)<-12?'bear':'neutral';
  const esc=x=>String(x??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  function metric(k,v){return `<div class="metric"><div class="k">${esc(k)}</div><div class="mv">${esc(v)}</div></div>`}
  function render(s){
    $('price').textContent=money(s.price);
    if(s.bid&&s.ask){const mid=(Number(s.bid)+Number(s.ask))/2;const bps=(Number(s.ask)-Number(s.bid))/mid*10000;$('spread').textContent=`Bid ${money(s.bid)} · Ask ${money(s.ask)} · ${bps.toFixed(1)} bps`}
    $('armed').textContent=s.armed?'ARMED':'STOPPED';$('armed').className='v '+(s.armed?'bull':'bear');
    $('message').textContent=s.last_message||'—';
    const d=s.decision||{};$('decision').textContent=d.action||'—';$('decision').className='v '+(d.action==='BUY'?'bull':d.action==='SELL'?'bear':'neutral');
    $('decisionReason').textContent=d.reason||'No scan yet';
    $('equity').textContent=money(s.equity);$('daily').textContent=`Start ${money(s.day_start_equity)} · Bot realized ${money(s.day_realized)} · ${s.trades_today} trades`;
    $('scanTime').textContent=s.last_scan_at?new Date(s.last_scan_at).toLocaleTimeString():'—';
    const a=(d.analyses||{})['3m']||{};$('score').textContent=signed(a.score);$('score').className='score '+cls(a.score);$('quality').textContent=a.quality==null?'—':Number(a.quality).toFixed(0)+'%';$('regime').textContent=a.regime||'—';
    const sig=d.signal||{};$('signalMetrics').innerHTML=[metric('Setup',a.setup||'—'),metric('Trigger',sig.trigger||'—'),metric('Agreement',a.agreement==null?'—':Number(a.agreement).toFixed(0)+'%'),metric('RSI',a.rsi==null?'—':Number(a.rsi).toFixed(1)),metric('ATR',a.atr==null?'—':money(a.atr)),metric('Coverage',a.coverage==null?'—':Number(a.coverage).toFixed(0)+'%')].join('');
    $('contextScore').textContent=signed(d.context_score);$('contextScore').className=cls(d.context_score);$('contextAgreement').textContent=d.context_agreement==null?'—':`agreement ${Number(d.context_agreement).toFixed(0)}%`;
    const rows=['15m','1h','4h','1d'].map(tf=>{const x=(d.analyses||{})[tf]||{};return `<tr><td>${tf}</td><td class="${cls(x.score)}">${signed(x.score)}</td><td>${esc(x.setup||'—')}</td><td>${esc(x.regime||'—')}</td></tr>`}).join('');$('contextRows').innerHTML=rows||'<tr><td colspan="4">Waiting…</td></tr>';
    const r=s.risk||{};$('riskGrid').innerHTML=[metric('Risk / trade',(r.risk_pct??'—')+'%'),metric('Leverage',(r.leverage??'—')+'×'),metric('Max margin use',(r.max_margin_use_pct??'—')+'%'),metric('Daily stop',(r.max_daily_loss_pct??'—')+'%'),metric('Max trades',r.max_trades_per_day??'—'),metric('Loss streak stop',r.max_consecutive_losses??'—'),metric('Cooldown',(r.cooldown_bars??'—')+' bars'),metric('Take profit',(r.tp_r_multiple??'—')+'R'),metric('Margin mode',s.margin_mode||'—')].join('');
    const p=s.position;$('owner').textContent=p?(s.bot_owned_position?'bot-owned':'existing/account position'):'—';
    if(!p){$('position').className='position-empty';$('position').textContent='No BTC position detected.'}else{$('position').className='position-grid';$('position').innerHTML=[metric('Side',p.positionSide||'—'),metric('Contracts',p.positions||'—'),metric('Entry',money(p.averagePrice)),metric('Mark',money(p.markPrice)),metric('Unrealized',money(p.unrealizedPnl)),metric('Leverage',(p.leverage||r.leverage||'—')+'×')].join('')}
    if(s.last_error){$('error').style.display='block';$('error').textContent=s.last_error}else{$('error').style.display='none';}
    if(s.environment==='live'){$('warning').textContent='REAL-MONEY MODE. Confirm the API key has READ + TRADE only, keep TRANSFER disabled, and type LIVE before arming.'}
  }
  async function req(url,opt){const r=await fetch(url,opt);const j=await r.json();if(!r.ok||j.ok===false)throw new Error(j.error||'Request failed');return j}
  async function poll(){try{render(await req('/api/status'))}catch(e){$('error').style.display='block';$('error').textContent=e.message}}
  $('arm').addEventListener('click',async()=>{try{await req('/api/arm',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirmation:$('confirm').value.trim()})});$('confirm').value='';poll()}catch(e){alert(e.message)}});
  $('stop').addEventListener('click',async()=>{await req('/api/stop',{method:'POST'});poll()});
  $('kill').addEventListener('click',async()=>{if(confirm('Close the bot-owned BTC position (if any) and stop the bot?')){await req('/api/kill',{method:'POST'});poll()}});
  $('export').addEventListener('click',()=>location.href='/api/trades.csv');
  poll();setInterval(poll,1000);
})();
