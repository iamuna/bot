(() => {
  const $=id=>document.getElementById(id);
  const TF_ORDER=['1m','3m','5m','15m','30m','1h','2h','4h','6h','8h','12h','1d','3d','1w','1M'];
  const money=x=>x==null||!Number.isFinite(Number(x))?'—':'$'+Number(x).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
  const signed=(x,d=1)=>x==null||!Number.isFinite(Number(x))?'—':(Number(x)>0?'+':'')+Number(x).toFixed(d);
  const cls=x=>Number(x)>12?'bull':Number(x)<-12?'bear':'neutral';
  const esc=x=>String(x??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  let state=null, selectedTF='1h', chartLimit=120, chartPayload=null, settingsSeeded=false;

  async function req(url,opt){const r=await fetch(url,opt);const j=await r.json();if(!r.ok||j.ok===false)throw new Error(j.error||'Request failed');return j}
  function setRange(id,val,suffix=''){const el=$(id); if(document.activeElement!==el)el.value=val; const out=$(id+'Out'); if(out)out.textContent=Number(val).toFixed(id==='targetR'?1:(id==='riskPct'?2:1))+suffix}
  function renderSettings(r){
    if(!r)return;
    if(!settingsSeeded){$('signalMode').value=r.signal_mode||'Aggressive';settingsSeeded=true}
    setRange('riskPct',r.risk_pct,'%');setRange('leverage',r.leverage,'×');setRange('minQuality',r.min_quality,'%');setRange('minConfluence',r.min_confluence,'%');setRange('portfolioRisk',r.max_total_open_risk_pct,'%');setRange('targetR',r.tp_r_multiple,'R');
  }
  function render(s){
    state=s;$('price').textContent=money(s.price);
    if(s.bid&&s.ask){const mid=(+s.bid + +s.ask)/2;const bps=(+s.ask-+s.bid)/mid*10000;$('spread').textContent=`Bid ${money(s.bid)} · Ask ${money(s.ask)} · ${bps.toFixed(1)} bps`}
    $('armed').textContent=s.armed?'ARMED':'STOPPED';$('armed').className='v '+(s.armed?'bull':'bear');$('message').textContent=s.last_message||'—';
    const o=s.overall||{};$('bias').textContent=`${o.direction||'—'} ${signed(o.score)}`;$('bias').className='v '+cls(o.score);
    const h=o.horizons||{};$('horizonLine').textContent=['micro','intraday','swing','macro'].map(k=>`${k} ${signed((h[k]||{}).score)}`).join(' · ');
    $('posCount').textContent=s.open_position_count??0;$('posCap').textContent=s.exchange_position_cap??10;$('equity').textContent=money(s.equity);$('openRisk').textContent=money(s.open_risk_usd);
    renderSettings(s.runtime||{});renderMatrix(s);renderCandidates(s);renderPositions(s);renderEvents(s);
    if(s.environment==='live')$('warning').textContent='REAL-MONEY MODE. No daily trade-count limit or cooldown. BloFin hard-caps Multi-Position mode at 10 positions per instrument.';
    if(s.last_error){$('error').style.display='block';$('error').textContent=s.last_error}else $('error').style.display='none';
  }
  function renderMatrix(s){
    const enabled=new Set((s.runtime||{}).enabled_timeframes||[]),a=s.analyses||{};
    $('tfRows').innerHTML=TF_ORDER.map(tf=>{const x=a[tf]||{};return `<tr data-tf="${tf}" class="${tf===selectedTF?'selected':''}"><td><input class="tf-toggle" data-toggle="${tf}" type="checkbox" ${enabled.has(tf)?'checked':''}></td><td><b>${tf}</b></td><td class="${cls(x.score)}">${signed(x.score)}</td><td>${x.quality==null?'—':Number(x.quality).toFixed(0)+'%'}</td><td>${x.agreement==null?'—':Number(x.agreement).toFixed(0)+'%'}</td><td>${esc(x.setup||'—')}</td><td>${esc(x.regime||'—')}</td><td>${x.rsi==null?'—':Number(x.rsi).toFixed(1)}</td><td>${x.adx==null?'—':Number(x.adx).toFixed(1)}</td><td>${x.coverage==null?'—':Number(x.coverage).toFixed(0)+'%'}</td></tr>`}).join('');
    document.querySelectorAll('#tfRows tr').forEach(tr=>tr.addEventListener('click',e=>{if(e.target.matches('input'))return;selectedTF=tr.dataset.tf;$('chartLabel').textContent=`${selectedTF} · live cached candles`;loadChart();renderMatrix(state)}));
    document.querySelectorAll('.tf-toggle').forEach(cb=>cb.addEventListener('change',e=>{e.stopPropagation();applyTimeframes()}));
  }
  async function applyTimeframes(){const enabled=[...document.querySelectorAll('.tf-toggle:checked')].map(x=>x.dataset.toggle);try{await req('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled_timeframes:enabled})});poll()}catch(e){alert(e.message)}}
  function renderCandidates(s){
    const xs=s.candidates||[];$('candidateCount').textContent=xs.length;
    $('candidates').className='stack'+(xs.length?'':' empty');$('candidates').innerHTML=xs.length?xs.map(c=>`<div class="item"><div class="item-top"><div class="item-main ${c.action==='BUY'?'bull':'bear'}">${esc(c.timeframe)} ${esc(c.action)}</div><span class="badge">priority ${Number(c.priority||0).toFixed(0)}</span></div><div class="item-sub">quality ${Number(c.quality||0).toFixed(0)}% · confluence ${Number(c.confluence||0).toFixed(0)}% · ${esc(c.horizon)} · ${esc(c.reason)}</div></div>`).join(''):'No fresh candidates.';
  }
  function renderPositions(s){
    const xs=s.positions||[];$('positions').className='stack'+(xs.length?'':' empty');
    $('positions').innerHTML=xs.length?xs.map(p=>{const side=String(p.positionSide||'').toLowerCase();const entry=Number(p.averagePrice||p.entry||0),mark=Number(p.markPrice||s.price||0),cv=Number(p.contractValue||0),qty=Number(p.positions||0);let pnl=p.unrealizedPnl;if((pnl==null||pnl==='')&&entry&&mark&&cv&&qty)pnl=(mark-entry)*cv*qty*(side==='short'?-1:1);return `<div class="item"><div class="item-top"><div class="item-main ${side==='long'?'bull':'bear'}">${esc(p.timeframe||'?')} ${esc(side.toUpperCase())}</div><span class="badge">${p.botOwned?'BOT':'ACCOUNT'} · ${esc(p.positionId||'paper')}</span></div><div class="item-sub">${esc(p.positions||'—')} contracts · entry ${money(entry)} · mark ${money(mark)} · PnL ${money(pnl)}<br>stop ${money(p.stop)} · target ${money(p.target)} · planned risk ${money(p.risk_usd)}</div></div>`}).join(''):'No positions.';
  }
  function renderEvents(s){const xs=s.recent_events||[];$('events').innerHTML=xs.length?xs.map(e=>`<div class="event"><b>${new Date(e.time).toLocaleTimeString()} · ${esc(e.kind)}</b><br>${esc(e.reason||e.error||e.timeframe||'')}</div>`).join(''):'No events yet.'}

  async function loadChart(){try{chartPayload=await req(`/api/chart?tf=${encodeURIComponent(selectedTF)}&limit=${chartLimit}`);$('chartLabel').textContent=`${selectedTF} · ${chartPayload.candles.length} candles · score ${signed((chartPayload.analysis||{}).score)}`;$('zoomLabel').textContent=`${chartLimit} candles`;drawChart()}catch(e){$('chartReadout').textContent=e.message}}
  function drawChart(){
    const c=$('chart'),ctx=c.getContext('2d'),rect=c.getBoundingClientRect(),dpr=window.devicePixelRatio||1;c.width=Math.max(300,Math.floor(rect.width*dpr));c.height=Math.max(240,Math.floor(rect.height*dpr));ctx.scale(dpr,dpr);const W=rect.width,H=rect.height;ctx.clearRect(0,0,W,H);ctx.fillStyle='#090e14';ctx.fillRect(0,0,W,H);
    const xs=(chartPayload||{}).candles||[];if(!xs.length){ctx.fillStyle='#8492a3';ctx.fillText('No candles',20,30);return}
    const pad={l:52,r:12,t:12,b:24},pw=W-pad.l-pad.r,ph=H-pad.t-pad.b;let lo=Math.min(...xs.map(x=>+x.l)),hi=Math.max(...xs.map(x=>+x.h));const extra=(hi-lo)*.06||1;lo-=extra;hi+=extra;const y=v=>pad.t+(hi-v)/(hi-lo)*ph,x=i=>pad.l+(i+.5)*pw/xs.length,bw=Math.max(1,pw/xs.length*.58);
    ctx.strokeStyle='#17212b';ctx.lineWidth=1;ctx.fillStyle='#8492a3';ctx.font='10px Segoe UI';for(let i=0;i<5;i++){const yy=pad.t+ph*i/4;ctx.beginPath();ctx.moveTo(pad.l,yy);ctx.lineTo(W-pad.r,yy);ctx.stroke();const price=hi-(hi-lo)*i/4;ctx.fillText('$'+price.toLocaleString(undefined,{maximumFractionDigits:0}),4,yy+3)}
    xs.forEach((b,i)=>{const up=+b.c>=+b.o;ctx.strokeStyle=up?'#2bd79d':'#ff6272';ctx.fillStyle=ctx.strokeStyle;ctx.beginPath();ctx.moveTo(x(i),y(+b.h));ctx.lineTo(x(i),y(+b.l));ctx.stroke();const yy=Math.min(y(+b.o),y(+b.c)),hh=Math.max(1,Math.abs(y(+b.o)-y(+b.c)));ctx.fillRect(x(i)-bw/2,yy,bw,hh)});
    c.onmousemove=ev=>{const r=c.getBoundingClientRect(),mx=ev.clientX-r.left;const i=Math.max(0,Math.min(xs.length-1,Math.floor((mx-pad.l)/pw*xs.length)));const b=xs[i];$('chartReadout').textContent=`${new Date(+b.t).toLocaleString()} · O ${money(b.o)} H ${money(b.h)} L ${money(b.l)} C ${money(b.c)} · ${b.closed?'closed':'live'}`};
  }
  window.addEventListener('resize',()=>{if(chartPayload)drawChart()});

  async function applySettings(){const p={signal_mode:$('signalMode').value,risk_pct:+$('riskPct').value,leverage:+$('leverage').value,min_quality:+$('minQuality').value,min_confluence:+$('minConfluence').value,max_total_open_risk_pct:+$('portfolioRisk').value,tp_r_multiple:+$('targetR').value};try{await req('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});poll()}catch(e){alert(e.message)}}
  ['riskPct','leverage','minQuality','minConfluence','portfolioRisk','targetR'].forEach(id=>$(id).addEventListener('input',()=>setRange(id,$(id).value,id==='riskPct'||id==='minQuality'||id==='minConfluence'||id==='portfolioRisk'?'%':id==='leverage'?'×':'R')));
  $('applySettings').addEventListener('click',applySettings);
  $('arm').addEventListener('click',async()=>{try{await req('/api/arm',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirmation:$('confirm').value.trim()})});$('confirm').value='';poll()}catch(e){alert(e.message)}});
  $('stop').addEventListener('click',async()=>{await req('/api/stop',{method:'POST'});poll()});
  $('kill').addEventListener('click',async()=>{if(confirm('Close every bot-owned position from this process and stop new entries?')){await req('/api/kill',{method:'POST'});poll()}});
  $('multi').addEventListener('click',async()=>{if(confirm('Enable BloFin Hedge + Multi-Position mode? BloFin requires no open positions/orders.')){try{await req('/api/enable-multiposition',{method:'POST'});alert('Multi-Position mode enabled.');poll()}catch(e){alert(e.message)}}});
  $('export').addEventListener('click',()=>location.href='/api/trades.csv');
  $('zoomOut').addEventListener('click',()=>{chartLimit=Math.min(300,chartLimit+30);loadChart()});$('zoomIn').addEventListener('click',()=>{chartLimit=Math.max(30,chartLimit-30);loadChart()});
  async function poll(){try{render(await req('/api/status'))}catch(e){$('error').style.display='block';$('error').textContent=e.message}}
  poll();loadChart();setInterval(poll,1000);setInterval(loadChart,5000);
})();
