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
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


load_dotenv()


def _f(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


def _i(name: str, default: int) -> int:
    try:
        return int(float(os.getenv(name, str(default))))
    except Exception:
        return default


@dataclass(frozen=True)
class BotConfig:
    instrument: str = os.getenv("BLOFIN_INSTRUMENT", "BTC-USDT")
    environment: str = os.getenv("BOT_ENV", "paper").lower()  # paper | demo | live
    signal_mode: str = os.getenv("SIGNAL_MODE", "Balanced")
    risk_pct: float = _f("RISK_PCT", 0.25)
    leverage: float = _f("LEVERAGE", 2.0)
    max_software_leverage: float = _f("MAX_SOFTWARE_LEVERAGE", 5.0)
    max_margin_use_pct: float = _f("MAX_MARGIN_USE_PCT", 25.0)
    max_daily_loss_pct: float = _f("MAX_DAILY_LOSS_PCT", 2.0)
    max_trades_per_day: int = _i("MAX_TRADES_PER_DAY", 12)
    max_consecutive_losses: int = _i("MAX_CONSECUTIVE_LOSSES", 3)
    cooldown_bars: int = _i("COOLDOWN_BARS", 2)
    max_spread_bps: float = _f("MAX_SPREAD_BPS", 8.0)
    max_entry_slippage_atr: float = _f("MAX_ENTRY_SLIPPAGE_ATR", 0.35)
    paper_equity: float = _f("PAPER_EQUITY", 1000.0)
    loop_seconds: float = _f("BOT_LOOP_SECONDS", 2.0)
    min_context_score: float = _f("MIN_CONTEXT_SCORE", 6.0)
    min_context_agreement: float = _f("MIN_CONTEXT_AGREEMENT", 55.0)
    tp_r_multiple: float = _f("TP_R_MULTIPLE", 2.0)
    live_unlock: str = os.getenv("ALLOW_LIVE_TRADING", "")

    @property
    def api_key(self) -> str:
        return os.getenv("BLOFIN_API_KEY", "")

    @property
    def secret_key(self) -> str:
        return os.getenv("BLOFIN_SECRET_KEY", "")

    @property
    def passphrase(self) -> str:
        return os.getenv("BLOFIN_PASSPHRASE", "")

    def validated(self) -> "BotConfig":
        if self.environment not in {"paper", "demo", "live"}:
            raise ValueError("BOT_ENV must be paper, demo, or live")
        if self.signal_mode not in {"Conservative", "Balanced", "Aggressive"}:
            raise ValueError("SIGNAL_MODE must be Conservative, Balanced, or Aggressive")
        if not 0.01 <= self.risk_pct <= 2.0:
            raise ValueError("RISK_PCT must be between 0.01 and 2.0")
        if not 1.0 <= self.leverage <= self.max_software_leverage <= 10.0:
            raise ValueError("LEVERAGE must be >=1 and <= MAX_SOFTWARE_LEVERAGE (software cap <=10)")
        if not 1.0 <= self.max_margin_use_pct <= 60.0:
            raise ValueError("MAX_MARGIN_USE_PCT must be between 1 and 60")
        if not 0.25 <= self.max_daily_loss_pct <= 10.0:
            raise ValueError("MAX_DAILY_LOSS_PCT must be between 0.25 and 10")
        if self.environment in {"demo", "live"} and not (self.api_key and self.secret_key and self.passphrase):
            raise ValueError("BloFin API credentials are required for demo/live mode")
        if self.environment == "live" and self.live_unlock != "I_ACCEPT_LIVE_RISK":
            raise ValueError("Live trading is locked. Set ALLOW_LIVE_TRADING=I_ACCEPT_LIVE_RISK locally to unlock it.")
        return self
