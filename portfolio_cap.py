from __future__ import annotations

"""Portfolio-wide exposure limits for the v2.4 research backtester.

The original v2.4 engine applied the 45% margin allowance independently to
one candidate at a time.  With several simultaneous BTC positions that could
allow gross exposure to stack far beyond the intended account-level envelope.

This module patches the research Backtester at runtime so BOTH base v2.4 and
guarded v2.4 share one account-wide exposure budget:

* total initial-margin budget: 45% of current marked-to-market equity
* total gross-notional budget: 3.15x current marked-to-market equity

3.15x is the original 7x * 45% envelope, now deliberately decoupled from the
leverage setting.  If leverage is later raised (for example to 30x), leverage
can improve margin efficiency but cannot automatically increase gross market
exposure beyond 3.15x equity.

The limit is enforced when NEW positions are opened.  Existing positions are
not forcibly liquidated merely because market movement later changes the
notional/equity ratio; instead, no additional exposure can be added while the
portfolio is above the entry cap.  Forced deleveraging is a separate strategy
choice and should be tested explicitly rather than hidden inside sizing.
"""

import backtest_v24 as core

PORTFOLIO_MARGIN_USE_PCT = 45.0
PORTFOLIO_GROSS_NOTIONAL_X = 3.15

_INSTALLED = False
_ORIGINAL_UPDATE_DD = core.Backtester._update_dd
_ORIGINAL_REPORT = core.Backtester.report


def effective_gross_cap_x() -> float:
    """Gross exposure allowed by both the margin and explicit notional caps."""
    by_margin = (PORTFOLIO_MARGIN_USE_PCT / 100.0) * float(core.LEVERAGE)
    return min(PORTFOLIO_GROSS_NOTIONAL_X, by_margin)


def gross_notional(bt, price: float) -> float:
    price = float(price)
    return sum(abs(price * float(p.qty)) for p in bt.positions)


def _ensure_stats(bt) -> None:
    if not hasattr(bt, 'portfolio_cap_rejections'):
        bt.portfolio_cap_rejections = 0
        bt.max_gross_notional = 0.0
        bt.max_gross_notional_x_equity = 0.0
        bt.max_margin_used_pct = 0.0


def record_exposure(bt, price: float) -> None:
    _ensure_stats(bt)
    price = float(price)
    equity = float(bt._mark_to_market(price))
    gross = gross_notional(bt, price)
    bt.max_gross_notional = max(float(bt.max_gross_notional), gross)
    if equity > 0:
        gross_x = gross / equity
        margin_pct = 100.0 * (gross / max(float(core.LEVERAGE), 1e-9)) / equity
        bt.max_gross_notional_x_equity = max(float(bt.max_gross_notional_x_equity), gross_x)
        bt.max_margin_used_pct = max(float(bt.max_margin_used_pct), margin_pct)


def current_exposure(bt, price: float) -> dict[str, float]:
    _ensure_stats(bt)
    price = float(price)
    equity = float(bt._mark_to_market(price))
    gross = gross_notional(bt, price)
    gross_x = gross / equity if equity > 0 else float('inf')
    margin_pct = 100.0 * (gross / max(float(core.LEVERAGE), 1e-9)) / equity if equity > 0 else float('inf')
    return {
        'equity_mtm': equity,
        'gross_notional': gross,
        'gross_notional_x_equity': gross_x,
        'margin_used_pct': margin_pct,
    }


def _patched_open_candidate(self, c, bar):
    """Open a candidate while sharing one exposure budget across all slots."""
    _ensure_stats(self)

    if len(self.positions) >= core.MAX_POSITIONS:
        self.rejections.append({'t': bar['t'], 'tf': c.tf, 'side': c.side, 'reason': 'position cap'})
        return

    g = core.tf_group(c.tf)
    if self._group_count(g) >= core.GROUPS[g]['cap']:
        self.rejections.append({'t': bar['t'], 'tf': c.tf, 'side': c.side, 'reason': f'{g} slot cap'})
        return

    mark = float(bar['o'])
    entry = self._slip(mark, c.side, True)
    shift = entry - c.entry_ref
    stop = c.stop_ref + shift
    target = c.target_ref + shift
    dist = abs(entry - stop)

    rp = self._risk_pct(c)
    risk_budget = self.equity * rp / 100.0
    risk_qty = risk_budget / max(dist, 1e-9)

    # Portfolio cap is based on CURRENT marked-to-market equity and GROSS
    # exposure, so opposite-side BTC positions cannot cancel each other out.
    equity_before = float(self._mark_to_market(mark))
    existing_gross = gross_notional(self, mark)
    cap_x = effective_gross_cap_x()

    if equity_before <= 0 or cap_x <= 0:
        self.portfolio_cap_rejections += 1
        self.rejections.append({'t': bar['t'], 'tf': c.tf, 'side': c.side, 'reason': 'portfolio exposure cap'})
        return

    # Account for the immediate entry fee AND adverse entry slippage when
    # solving the maximum new quantity.  This prevents the act of entering the
    # trade from pushing post-entry MTM equity below the exposure budget.
    fee_rate = self.fee_bps / 10000.0
    entry_cost_per_qty = entry * fee_rate + abs(entry - mark)
    numerator = cap_x * equity_before - existing_gross
    denominator = mark + cap_x * entry_cost_per_qty
    exposure_qty = max(0.0, numerator / max(denominator, 1e-12))

    qty = min(risk_qty, exposure_qty)
    if qty <= 1e-12:
        self.portfolio_cap_rejections += 1
        self.rejections.append({'t': bar['t'], 'tf': c.tf, 'side': c.side, 'reason': 'portfolio exposure cap'})
        return

    risk = qty * dist
    if self._open_risk() + risk > self.equity * core.MAX_OPEN_RISK_PCT / 100.0:
        self.rejections.append({'t': bar['t'], 'tf': c.tf, 'side': c.side, 'reason': 'portfolio risk cap'})
        return

    fee = self._fee(entry * qty)
    self.equity -= fee
    p = core.Position(
        self.next_id, c.tf, c.side, int(bar['t']), entry, stop, target, stop,
        dist, risk, qty, c.quality, c.confluence, c.regime, c.atr, entry, entry,
        fees=fee,
    )
    self.next_id += 1
    self.positions.append(p)
    record_exposure(self, mark)


def _patched_update_dd(self, price):
    _ORIGINAL_UPDATE_DD(self, price)
    record_exposure(self, float(price))


def _patched_report(self):
    _ensure_stats(self)
    r = _ORIGINAL_REPORT(self)
    r.update({
        'portfolio_margin_cap_pct': PORTFOLIO_MARGIN_USE_PCT,
        'portfolio_gross_notional_cap_x': PORTFOLIO_GROSS_NOTIONAL_X,
        'effective_gross_cap_x': round(effective_gross_cap_x(), 4),
        'leverage': float(core.LEVERAGE),
        'portfolio_cap_rejections': int(self.portfolio_cap_rejections),
        'max_gross_notional': round(float(self.max_gross_notional), 2),
        'max_gross_notional_x_equity': round(float(self.max_gross_notional_x_equity), 4),
        'max_margin_used_pct': round(float(self.max_margin_used_pct), 2),
    })
    return r


def install() -> None:
    """Install the portfolio cap once for this Python process."""
    global _INSTALLED
    if _INSTALLED:
        return
    core.Backtester._open_candidate = _patched_open_candidate
    core.Backtester._update_dd = _patched_update_dd
    core.Backtester.report = _patched_report
    _INSTALLED = True
