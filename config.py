from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"


def load_dotenv(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip(); v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v

load_dotenv()


def _f(name: str, default: float) -> float:
    try: return float(os.getenv(name, str(default)))
    except Exception: return default


def _b(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None: return default
    return v.strip().lower() in {"1","true","yes","on"}


@dataclass(frozen=True)
class BotConfig:
    instrument: str = os.getenv("BLOFIN_INSTRUMENT", "BTC-USDT")
    environment: str = os.getenv("BOT_ENV", "paper").lower()
    signal_mode: str = os.getenv("SIGNAL_MODE", "Aggressive")
    risk_pct: float = _f("RISK_PCT", 0.35)
    leverage: float = _f("LEVERAGE", 3.0)
    max_software_leverage: float = _f("MAX_SOFTWARE_LEVERAGE", 8.0)
    max_margin_use_pct: float = _f("MAX_MARGIN_USE_PCT", 45.0)
    max_total_open_risk_pct: float = _f("MAX_TOTAL_OPEN_RISK_PCT", 5.0)
    max_daily_loss_pct: float = _f("MAX_DAILY_LOSS_PCT", 5.0)
    max_spread_bps: float = _f("MAX_SPREAD_BPS", 10.0)
    max_entry_slippage_atr: float = _f("MAX_ENTRY_SLIPPAGE_ATR", 0.55)
    paper_equity: float = _f("PAPER_EQUITY", 1000.0)
    loop_seconds: float = _f("BOT_LOOP_SECONDS", 1.0)
    min_quality: float = _f("MIN_QUALITY", 50.0)
    min_confluence: float = _f("MIN_CONFLUENCE", 46.0)
    tp_r_multiple: float = _f("TP_R_MULTIPLE", 1.8)
    require_multi_position: bool = _b("REQUIRE_MULTI_POSITION", True)
    live_unlock: str = os.getenv("ALLOW_LIVE_TRADING", "")

    @property
    def api_key(self) -> str: return os.getenv("BLOFIN_API_KEY", "")
    @property
    def secret_key(self) -> str: return os.getenv("BLOFIN_SECRET_KEY", "")
    @property
    def passphrase(self) -> str: return os.getenv("BLOFIN_PASSPHRASE", "")

    def validated(self) -> "BotConfig":
        if self.environment not in {"paper", "demo", "live"}:
            raise ValueError("BOT_ENV must be paper, demo, or live")
        if self.signal_mode not in {"Conservative", "Balanced", "Aggressive"}:
            raise ValueError("SIGNAL_MODE must be Conservative, Balanced, or Aggressive")
        if not 0.01 <= self.risk_pct <= 3.0:
            raise ValueError("RISK_PCT must be between 0.01 and 3.0")
        if not 1.0 <= self.leverage <= self.max_software_leverage <= 20.0:
            raise ValueError("LEVERAGE must be >=1 and <= MAX_SOFTWARE_LEVERAGE (software cap <=20)")
        if not 1.0 <= self.max_margin_use_pct <= 80.0:
            raise ValueError("MAX_MARGIN_USE_PCT must be between 1 and 80")
        if not 0.25 <= self.max_daily_loss_pct <= 20.0:
            raise ValueError("MAX_DAILY_LOSS_PCT must be between 0.25 and 20")
        if not 0.5 <= self.max_total_open_risk_pct <= 20.0:
            raise ValueError("MAX_TOTAL_OPEN_RISK_PCT must be between 0.5 and 20")
        if self.environment in {"demo", "live"} and not (self.api_key and self.secret_key and self.passphrase):
            raise ValueError("BloFin API credentials are required for demo/live mode")
        if self.environment == "live" and self.live_unlock != "I_ACCEPT_LIVE_RISK":
            raise ValueError("Live trading is locked. Set ALLOW_LIVE_TRADING=I_ACCEPT_LIVE_RISK locally to unlock it.")
        return self
