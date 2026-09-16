from __future__ import annotations

import base64, hashlib, hmac, json, time, uuid
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

LIVE_URL = "https://openapi.blofin.com"
DEMO_URL = "https://demo-trading-openapi.blofin.com"

class BloFinError(RuntimeError): pass

class BloFinClient:
    def __init__(self, api_key: str = "", secret_key: str = "", passphrase: str = "", demo: bool = True):
        self.api_key=api_key; self.secret_key=secret_key; self.passphrase=passphrase
        self.base_url=DEMO_URL if demo else LIVE_URL
        self.session=requests.Session()
        retry=Retry(total=4,connect=4,read=4,status=4,backoff_factor=.4,status_forcelist=(418,429,500,502,503,504),allowed_methods=frozenset({"GET"}),respect_retry_after_header=True)
        self.session.mount("https://",HTTPAdapter(max_retries=retry,pool_connections=20,pool_maxsize=20))
        self.session.headers.update({"User-Agent":"Terminal3-BloFin-MTF-Bot/2.0"})

    @staticmethod
    def _compact_json(body): return "" if body is None else json.dumps(body,separators=(",",":"),ensure_ascii=False)
    @staticmethod
    def _query(params):
        if not params:return ""
        return urlencode([(k,str(v)) for k,v in params.items() if v is not None and v!=""])
    def _headers(self,pathq,method,body_str):
        if not (self.api_key and self.secret_key and self.passphrase):raise BloFinError("Private endpoint requested without API credentials")
        ts=str(int(time.time()*1000));nonce=str(uuid.uuid4());prehash=f"{pathq}{method.upper()}{ts}{nonce}{body_str}"
        hex_sig=hmac.new(self.secret_key.encode(),prehash.encode(),hashlib.sha256).hexdigest().encode();sig=base64.b64encode(hex_sig).decode()
        return {"ACCESS-KEY":self.api_key,"ACCESS-SIGN":sig,"ACCESS-TIMESTAMP":ts,"ACCESS-NONCE":nonce,"ACCESS-PASSPHRASE":self.passphrase,"Content-Type":"application/json"}
    def _request(self,method,path,params=None,body=None,private=False):
        q=self._query(params);pathq=path+("?"+q if q else "");bs=self._compact_json(body);headers=self._headers(pathq,method,bs) if private else {"Content-Type":"application/json"}
        try:r=self.session.request(method.upper(),self.base_url+pathq,headers=headers,data=bs if body is not None else None,timeout=12)
        except requests.RequestException as e:raise BloFinError(f"Network error: {e}") from e
        try:p=r.json()
        except Exception as e:raise BloFinError(f"Non-JSON response ({r.status_code}): {r.text[:300]}") from e
        if r.status_code>=400:raise BloFinError(f"HTTP {r.status_code}: {p}")
        code=str(p.get("code","0")) if isinstance(p,dict) else "0"
        if code!="0":raise BloFinError(f"BloFin error {code}: {p.get('msg','')}")
        return p.get("data") if isinstance(p,dict) else p

    def get_instrument(self,inst_id="BTC-USDT"):
        d=self._request("GET","/api/v1/market/instruments",{"instId":inst_id})
        if not d:raise BloFinError(f"Instrument not found: {inst_id}")
        return d[0]
    def get_ticker(self,inst_id="BTC-USDT"):
        d=self._request("GET","/api/v1/market/tickers",{"instId":inst_id})
        if not d:raise BloFinError(f"Ticker not found: {inst_id}")
        return d[0]
    def get_candles(self,inst_id="BTC-USDT",bar="3m",limit=500):
        limit=max(2,min(1440,int(limit)));d=self._request("GET","/api/v1/market/candles",{"instId":inst_id,"bar":bar,"limit":limit});out=[]
        for row in d or []:
            if len(row)<9:continue
            t=int(row[0]);out.append({"t":t,"o":float(row[1]),"h":float(row[2]),"l":float(row[3]),"c":float(row[4]),"v":float(row[5]),"qv":float(row[6]),"quote_v":float(row[7]),"trades":0,"tb":0.0,"tbq":0.0,"ct":t+bar_milliseconds(bar)-1,"closed":str(row[8])=="1","source":"blofin"})
        out.sort(key=lambda x:x["t"]);return out
    def get_funding_rate(self,inst_id="BTC-USDT"):
        d=self._request("GET","/api/v1/market/funding-rate",{"instId":inst_id});return d[0] if isinstance(d,list) and d else (d if isinstance(d,dict) else None)
    def get_balance(self):return self._request("GET","/api/v1/account/balance",private=True) or {}
    def get_positions(self,inst_id="BTC-USDT",position_id=""):
        return list(self._request("GET","/api/v1/account/positions",{"instId":inst_id,"positionId":position_id},private=True) or [])
    def get_margin_mode(self):return str((self._request("GET","/api/v1/account/margin-mode",private=True) or {}).get("marginMode","cross"))
    def get_position_mode(self):return dict(self._request("GET","/api/v1/account/position-mode",private=True) or {})
    def set_position_mode(self,position_mode="long_short_mode",multi_position=True):
        body={"positionMode":position_mode,"multiPosition":"true" if multi_position else "false"}
        return dict(self._request("POST","/api/v1/account/set-position-mode",body=body,private=True) or {})
    def set_leverage(self,inst_id,leverage,margin_mode,position_side="net",position_id=""):
        body={"instId":inst_id,"leverage":str(int(leverage) if float(leverage).is_integer() else leverage),"marginMode":margin_mode}
        if position_side in {"long","short"}:body["positionSide"]=position_side
        if position_id:body["positionId"]=position_id
        return dict(self._request("POST","/api/v1/account/set-leverage",body=body,private=True) or {})
    def place_market_order(self,inst_id,margin_mode,position_side,side,size,sl_price=None,tp_price=None,client_order_id=None,position_id=""):
        body={"instId":inst_id,"marginMode":margin_mode,"positionSide":position_side,"side":side,"orderType":"market","size":size,"clientOrderId":client_order_id or f"mtf{int(time.time()*1000)}"[-32:]}
        if position_id:body["positionId"]=position_id
        if tp_price:body.update({"tpTriggerPrice":tp_price,"tpOrderPrice":"-1","tpTriggerPriceType":"mark"})
        if sl_price:body.update({"slTriggerPrice":sl_price,"slOrderPrice":"-1","slTriggerPriceType":"mark"})
        d=self._request("POST","/api/v1/trade/order",body=body,private=True)
        if isinstance(d,list) and d:
            x=d[0]
            if str(x.get("code","0"))!="0":raise BloFinError(f"Order rejected: {x}")
            return x
        return dict(d or {})
    def close_position(self,inst_id,margin_mode,position_side,position_id=""):
        body={"instId":inst_id,"marginMode":margin_mode,"positionSide":position_side}
        if position_id:body["positionId"]=position_id
        return dict(self._request("POST","/api/v1/trade/close-position",body=body,private=True) or {})

def bar_milliseconds(bar:str)->int:
    n=int(bar[:-1]);u=bar[-1]
    if u=="m":return n*60_000
    if u=="H":return n*3_600_000
    if u=="D":return n*86_400_000
    if u=="W":return n*604_800_000
    if u=="M":return n*30*86_400_000
    raise ValueError(f"Unsupported bar: {bar}")

def quantize_step(value:float,step:float,rounding=ROUND_DOWN)->str:
    d=Decimal(str(value));s=Decimal(str(step))
    if s<=0:return format(d,"f")
    q=(d/s).to_integral_value(rounding=rounding)*s;dec=max(0,-s.as_tuple().exponent);return f"{q:.{dec}f}"
def quantize_price(value:float,tick:float)->str:return quantize_step(value,tick,ROUND_HALF_UP)
