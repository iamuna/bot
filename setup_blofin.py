from __future__ import annotations

import getpass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PATH = ROOT / ".env"

print("Terminal 3.0 · BloFin 3m Bot configuration")
print("Credentials stay in this local .env file. Do not paste them into ChatGPT.")
print("Use a BloFin API key with READ + TRADE only. TRANSFER permission is not needed.")
print()
mode = input("Mode [paper/demo/live] (default paper): ").strip().lower() or "paper"
if mode not in {"paper", "demo", "live"}:
    raise SystemExit("Invalid mode")
values = {"BOT_ENV": mode}
if mode in {"demo", "live"}:
    values["BLOFIN_API_KEY"] = getpass.getpass("BloFin API key: ").strip()
    values["BLOFIN_SECRET_KEY"] = getpass.getpass("BloFin secret key: ").strip()
    values["BLOFIN_PASSPHRASE"] = getpass.getpass("BloFin API passphrase: ").strip()
if mode == "live":
    print("Live mode remains locked until the exact line ALLOW_LIVE_TRADING=I_ACCEPT_LIVE_RISK is present.")
    unlock = input("Enable the live-mode software lock now? Type ENABLE to do so: ").strip()
    if unlock == "ENABLE":
        values["ALLOW_LIVE_TRADING"] = "I_ACCEPT_LIVE_RISK"

risk = input("Risk per trade % (default 0.25): ").strip() or "0.25"
lev = input("Leverage (default 2): ").strip() or "2"
values["RISK_PCT"] = risk
values["LEVERAGE"] = lev
values["SIGNAL_MODE"] = input("Signal mode [Conservative/Balanced/Aggressive] (default Balanced): ").strip() or "Balanced"
values.setdefault("MAX_SOFTWARE_LEVERAGE", "5")
values.setdefault("MAX_MARGIN_USE_PCT", "25")
values.setdefault("MAX_DAILY_LOSS_PCT", "2")
values.setdefault("MAX_TRADES_PER_DAY", "12")
values.setdefault("MAX_CONSECUTIVE_LOSSES", "3")
values.setdefault("COOLDOWN_BARS", "2")
values.setdefault("MAX_SPREAD_BPS", "8")
values.setdefault("TP_R_MULTIPLE", "2")

PATH.write_text("\n".join(f"{k}={v}" for k,v in values.items())+"\n", encoding="utf-8")
print(f"\nSaved {PATH}")
print("Restart the bot after changing configuration.")
