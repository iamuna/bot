from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from blofin_client import quantize_step


@dataclass
class SizePlan:
    contracts: str
    raw_contracts: float
    risk_usd: float
    stop_distance: float
    notional_usd: float
    margin_estimate: float
    capped_by_margin: bool


def size_for_risk(equity: float, entry: float, stop: float, instrument: dict[str, Any],
                  risk_pct: float, leverage: float, max_margin_use_pct: float) -> SizePlan:
    contract_value = float(instrument.get("contractValue") or 0)
    min_size = float(instrument.get("minSize") or 0)
    lot_size = float(instrument.get("lotSize") or min_size or 1)
    max_market = float(instrument.get("maxMarketSize") or 1e18)
    if contract_value <= 0 or lot_size <= 0:
        raise ValueError("Invalid BloFin contract specification")
    distance = abs(float(entry) - float(stop))
    if distance <= 0:
        raise ValueError("Stop distance must be positive")
    risk_usd = max(0.0, float(equity) * float(risk_pct) / 100.0)
    raw_contracts = risk_usd / (distance * contract_value)

    max_margin = max(0.0, equity * max_margin_use_pct / 100.0)
    max_notional = max_margin * leverage
    max_contracts_by_margin = max_notional / max(entry * contract_value, 1e-12)
    capped = raw_contracts > max_contracts_by_margin
    raw_contracts = min(raw_contracts, max_contracts_by_margin, max_market)
    contracts_s = quantize_step(raw_contracts, lot_size)
    contracts = float(contracts_s)
    if contracts < min_size or contracts <= 0:
        raise ValueError(f"Calculated size {contracts_s} is below BloFin minimum {min_size}")
    notional = contracts * contract_value * entry
    margin = notional / leverage
    actual_risk = contracts * contract_value * distance
    return SizePlan(contracts_s, contracts, round(actual_risk, 4), distance, round(notional, 2), round(margin, 2), capped)
