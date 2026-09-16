from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from ta_engine import analyze_latest, signal_history


TF_BARS = {"3m": "3m", "15m": "15m", "1h": "1H", "4h": "4H", "1d": "1D"}
CONTEXT_WEIGHTS = {"15m": 0.34, "1h": 0.34, "4h": 0.22, "1d": 0.10}


@dataclass
class Decision:
    action: str  # BUY | SELL | WAIT
    reason: str
    signal: dict[str, Any] | None
    entry_reference: float | None
    stop: float | None
    target: float | None
    context_score: float
    context_agreement: float
    analyses: dict[str, Any]
    signal_bar_t: int | None = None


def _closed(bars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [b for b in bars if bool(b.get("closed", True))]


def _last_closed_t(bars: list[dict[str, Any]]) -> int | None:
    xs = _closed(bars)
    return int(xs[-1]["t"]) if xs else None


def evaluate(dataset: dict[str, list[dict[str, Any]]], mode: str = "Balanced",
             min_context_score: float = 6.0, min_context_agreement: float = 55.0,
             tp_r_multiple: float = 2.0) -> Decision:
    analyses: dict[str, Any] = {}
    for tf in ("3m", "15m", "1h", "4h", "1d"):
        bars = dataset.get(tf) or []
        if len(bars) < 30:
            return Decision("WAIT", f"Not enough {tf} history", None, None, None, None, 0, 0, analyses)
        analyses[tf] = analyze_latest(bars, mode)["confirmed"]

    bars3 = dataset["3m"]
    hist = signal_history(bars3, mode, "3m")
    markers = hist.get("markers") or []
    if not markers:
        return Decision("WAIT", "No confirmed Terminal 3.0 signal on 3m", None, None, None, None, 0, 0, analyses)

    latest_marker = markers[-1]
    latest_closed_t = _last_closed_t(bars3)
    if latest_closed_t is None or int(latest_marker.get("t", -1)) != int(latest_closed_t):
        return Decision("WAIT", "Latest 3m candle did not create a new confirmed signal", latest_marker, None, None, None, 0, 0, analyses)

    side = str(latest_marker["side"])
    sign = 1.0 if side == "BUY" else -1.0
    weighted = 0.0
    same = 0.0
    weight_total = 0.0
    hard_blocks: list[str] = []
    for tf, w in CONTEXT_WEIGHTS.items():
        a = analyses[tf]
        s = float(a.get("score", 0.0))
        cov = max(0.0, min(1.0, float(a.get("coverage", 100.0)) / 100.0))
        ew = w * (0.45 + 0.55 * cov)
        weighted += s * ew
        weight_total += ew
        if s * sign > 8:
            same += ew
        elif s * sign < -8:
            same -= ew * 0.65

    context_score = weighted / max(weight_total, 1e-9)
    context_agreement = max(0.0, min(100.0, 50.0 + 50.0 * same / max(weight_total, 1e-9)))

    # Strong higher-timeframe opposition vetoes a 3m entry rather than averaging it away.
    if float(analyses["1h"].get("score", 0.0)) * sign <= -45:
        hard_blocks.append("1h strongly opposes")
    if float(analyses["4h"].get("score", 0.0)) * sign <= -55:
        hard_blocks.append("4h strongly opposes")
    if float(analyses["1d"].get("score", 0.0)) * sign <= -65:
        hard_blocks.append("1d strongly opposes")

    a3 = analyses["3m"]
    regime = str(a3.get("regime", ""))
    trigger = str(latest_marker.get("trigger", ""))
    if regime in {"RANGE", "SQUEEZE"} and trigger not in {"breakout", "breakdown"}:
        hard_blocks.append(f"3m regime is {regime.lower()} without breakout confirmation")
    extension = a3.get("extension_atr")
    if extension is not None and float(extension) * sign > 3.0:
        hard_blocks.append("3m entry is overextended versus EMA20")
    if float(latest_marker.get("quality", 0.0)) < 56:
        hard_blocks.append("setup quality below 56")

    if hard_blocks:
        return Decision("WAIT", "; ".join(hard_blocks), latest_marker, None, None, None,
                        round(context_score, 1), round(context_agreement, 1), analyses, latest_closed_t)
    if context_score * sign < min_context_score:
        return Decision("WAIT", f"Higher-timeframe context too weak ({context_score:+.1f})", latest_marker, None, None, None,
                        round(context_score, 1), round(context_agreement, 1), analyses, latest_closed_t)
    if context_agreement < min_context_agreement:
        return Decision("WAIT", f"Higher-timeframe agreement only {context_agreement:.0f}%", latest_marker, None, None, None,
                        round(context_score, 1), round(context_agreement, 1), analyses, latest_closed_t)

    entry = float(latest_marker.get("price"))
    plan = latest_marker.get("plan") or {}
    stop = float(plan.get("stop") or (entry * (0.995 if side == "BUY" else 1.005)))
    risk = abs(entry - stop)
    target = entry + sign * tp_r_multiple * risk
    if risk <= 0 or not all(math.isfinite(x) for x in (entry, stop, target)):
        return Decision("WAIT", "Invalid risk plan", latest_marker, None, None, None,
                        round(context_score, 1), round(context_agreement, 1), analyses, latest_closed_t)

    return Decision(side, f"New 3m {side} signal confirmed by higher timeframes", latest_marker,
                    entry, stop, target, round(context_score, 1), round(context_agreement, 1), analyses, latest_closed_t)
