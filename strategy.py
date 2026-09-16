from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Any

from ta_engine import analyze_latest, signal_history

# Every native BloFin futures candle interval documented by the exchange.
TF_BARS: dict[str, str] = {
    "1m": "1m", "3m": "3m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1H", "2h": "2H", "4h": "4H", "6h": "6H", "8h": "8H",
    "12h": "12H", "1d": "1D", "3d": "3D", "1w": "1W", "1M": "1M",
}
TF_ORDER = list(TF_BARS)
HORIZONS: dict[str, list[str]] = {
    "micro": ["1m", "3m", "5m"],
    "intraday": ["15m", "30m", "1h", "2h", "4h"],
    "swing": ["6h", "8h", "12h", "1d", "3d"],
    "macro": ["1w", "1M"],
}
HORIZON_WEIGHTS = {"micro": 0.22, "intraday": 0.36, "swing": 0.29, "macro": 0.13}
TF_IMPORTANCE = {
    "1m": .55, "3m": .62, "5m": .70, "15m": .82, "30m": .90,
    "1h": 1.00, "2h": 1.06, "4h": 1.12, "6h": 1.10, "8h": 1.08,
    "12h": 1.08, "1d": 1.12, "3d": 1.02, "1w": .95, "1M": .80,
}

@dataclass
class Candidate:
    action: str
    timeframe: str
    reason: str
    signal: dict[str, Any]
    entry_reference: float
    stop: float
    target: float
    signal_bar_t: int
    quality: float
    confluence: float
    context_score: float
    priority: float
    horizon: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass
class MarketEvaluation:
    analyses: dict[str, Any]
    horizons: dict[str, Any]
    overall_score: float
    overall_direction: str
    candidates: list[Candidate]
    rejected: list[dict[str, Any]]


def _closed(bars: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [b for b in bars if bool(b.get("closed", True))]


def _last_closed_t(bars: list[dict[str, Any]]) -> int | None:
    xs = _closed(bars)
    return int(xs[-1]["t"]) if xs else None


def _horizon_for(tf: str) -> str:
    for h, tfs in HORIZONS.items():
        if tf in tfs:
            return h
    return "intraday"


def _direction(score: float) -> str:
    if score >= 18:
        return "UP"
    if score <= -18:
        return "DOWN"
    return "MIXED"


def _weighted_average(items: list[tuple[float, float]]) -> float:
    den = sum(w for _, w in items)
    return sum(v*w for v, w in items) / den if den else 0.0


def _summarize_horizons(analyses: dict[str, Any]) -> tuple[dict[str, Any], float]:
    out: dict[str, Any] = {}
    overall_parts: list[tuple[float, float]] = []
    for h, tfs in HORIZONS.items():
        vals: list[tuple[float, float]] = []
        same_up = same_down = 0.0
        for tf in tfs:
            a = analyses.get(tf) or {}
            if "score" not in a:
                continue
            cov = max(.25, min(1.0, float(a.get("coverage", 100.0))/100.0))
            w = TF_IMPORTANCE.get(tf, 1.0) * cov
            s = float(a.get("score", 0.0))
            vals.append((s, w))
            if s > 8:
                same_up += w
            elif s < -8:
                same_down += w
        score = _weighted_average(vals)
        total = sum(w for _, w in vals) or 1.0
        agreement = 100.0 * max(same_up, same_down) / total
        out[h] = {
            "score": round(score, 1),
            "direction": _direction(score),
            "agreement": round(agreement, 1),
            "timeframes": len(vals),
        }
        if vals:
            overall_parts.append((score, HORIZON_WEIGHTS[h]))
    overall = _weighted_average(overall_parts)
    return out, overall


def _confluence_for(side: str, tf: str, analyses: dict[str, Any], horizons: dict[str, Any], overall: float) -> tuple[float, float]:
    sign = 1.0 if side == "BUY" else -1.0
    own_h = _horizon_for(tf)
    own = float((horizons.get(own_h) or {}).get("score", 0.0))
    horizon_names = list(HORIZONS)
    idx = horizon_names.index(own_h)
    higher = [float((horizons.get(h) or {}).get("score", 0.0)) for h in horizon_names[idx+1:]]
    higher_score = sum(higher)/len(higher) if higher else overall
    context = .50*own + .30*overall + .20*higher_score
    aligned = max(-100.0, min(100.0, context*sign))
    conf = max(0.0, min(100.0, 50.0 + aligned*.55))
    return round(conf, 1), round(context, 1)


def evaluate_all(
    dataset: dict[str, list[dict[str, Any]]],
    mode: str = "Aggressive",
    min_quality: float = 50.0,
    min_confluence: float = 46.0,
    tp_r_multiple: float = 1.8,
    enabled_timeframes: set[str] | None = None,
) -> MarketEvaluation:
    enabled = set(enabled_timeframes or TF_ORDER)
    analyses: dict[str, Any] = {}
    rejected: list[dict[str, Any]] = []

    for tf in TF_ORDER:
        bars = dataset.get(tf) or []
        if len(_closed(bars)) < 30:
            analyses[tf] = {"score": 0.0, "quality": 0.0, "agreement": 0.0, "regime": "NO DATA", "setup": "WAIT", "coverage": 0.0}
            continue
        try:
            analyses[tf] = analyze_latest(bars, mode)["confirmed"]
        except Exception as e:
            analyses[tf] = {"score": 0.0, "quality": 0.0, "agreement": 0.0, "regime": "ERROR", "setup": "WAIT", "coverage": 0.0, "error": str(e)}

    horizons, overall = _summarize_horizons(analyses)
    candidates: list[Candidate] = []

    for tf in TF_ORDER:
        if tf not in enabled:
            continue
        bars = dataset.get(tf) or []
        latest_t = _last_closed_t(bars)
        if latest_t is None or len(_closed(bars)) < 30:
            continue
        try:
            hist = signal_history(bars, mode, tf)
        except Exception as e:
            rejected.append({"timeframe": tf, "reason": f"signal engine error: {e}"})
            continue
        markers = hist.get("markers") or []
        if not markers:
            continue
        marker = markers[-1]
        if int(marker.get("t", -1)) != int(latest_t):
            continue

        side = str(marker.get("side", ""))
        if side not in {"BUY", "SELL"}:
            continue
        sign = 1.0 if side == "BUY" else -1.0
        quality = float(marker.get("quality", 0.0))
        confluence, context = _confluence_for(side, tf, analyses, horizons, overall)
        a = analyses.get(tf) or {}
        trigger = str(marker.get("trigger", ""))
        regime = str(a.get("regime", ""))
        extension = a.get("extension_atr")
        reasons: list[str] = []

        if quality < min_quality:
            reasons.append(f"quality {quality:.0f} < {min_quality:.0f}")
        if confluence < min_confluence and quality < min_quality + 18:
            reasons.append(f"confluence {confluence:.0f}% < {min_confluence:.0f}%")
        if regime == "RANGE" and trigger not in {"breakout", "breakdown"} and quality < min_quality + 15:
            reasons.append("range signal lacks breakout confirmation")
        if extension is not None and float(extension)*sign > 4.0 and quality < 80:
            reasons.append("entry is severely extended from EMA20")
        if context*sign <= -42 and quality < 78:
            reasons.append("broad multi-timeframe context strongly opposes")

        if reasons:
            rejected.append({"timeframe": tf, "side": side, "quality": round(quality, 1), "confluence": confluence, "reason": "; ".join(reasons), "signal_bar_t": latest_t})
            continue

        entry = float(marker.get("price"))
        plan = marker.get("plan") or {}
        stop = float(plan.get("stop") or (entry * (.995 if side == "BUY" else 1.005)))
        risk = abs(entry-stop)
        h = _horizon_for(tf)
        r_mult = tp_r_multiple * {"micro": .90, "intraday": 1.0, "swing": 1.10, "macro": 1.20}[h]
        target = entry + sign*r_mult*risk
        if risk <= 0 or not all(math.isfinite(x) for x in (entry, stop, target)):
            rejected.append({"timeframe": tf, "side": side, "reason": "invalid risk plan", "signal_bar_t": latest_t})
            continue

        priority = quality*.48 + confluence*.34 + min(100.0, abs(float(a.get("score", 0.0))))*.18
        reason = f"{tf} {side}: quality {quality:.0f}, confluence {confluence:.0f}%, {regime.lower()}"
        candidates.append(Candidate(
            side, tf, reason, marker, entry, stop, target, int(latest_t), round(quality, 1),
            confluence, context, round(priority, 1), h,
        ))

    candidates.sort(key=lambda x: x.priority, reverse=True)
    return MarketEvaluation(
        analyses=analyses,
        horizons=horizons,
        overall_score=round(overall, 1),
        overall_direction=_direction(overall),
        candidates=candidates,
        rejected=rejected[-40:],
    )
