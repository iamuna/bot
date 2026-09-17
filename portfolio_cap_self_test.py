from __future__ import annotations

import backtest_v24 as core
import portfolio_cap


def synthetic(n=180):
    out = []
    t0 = 1_750_000_000_000
    p = 75_000.0
    for i in range(n):
        o = p
        c = p + (2.0 if i % 2 == 0 else -1.0)
        h = max(o, c) + 5.0
        l = min(o, c) - 5.0
        out.append({
            't': t0 + i * 60_000,
            'o': o, 'h': h, 'l': l, 'c': c,
            'v': 100.0, 'qv': 100.0, 'quote_v': 100.0,
            'trades': 0, 'tb': 0.0, 'tbq': 0.0,
            'ct': t0 + (i + 1) * 60_000 - 1,
            'closed': True, 'source': 'test',
        })
        p = c
    return out


def main():
    portfolio_cap.install()
    old_lev = core.LEVERAGE
    old_gross = portfolio_cap.PORTFOLIO_GROSS_NOTIONAL_X
    old_margin = portfolio_cap.PORTFOLIO_MARGIN_USE_PCT
    try:
        core.LEVERAGE = 30.0
        portfolio_cap.PORTFOLIO_GROSS_NOTIONAL_X = 3.15
        portfolio_cap.PORTFOLIO_MARGIN_USE_PCT = 45.0

        bt = core.Backtester(synthetic(), equity=1000.0, fee_bps=6.0, slippage_bps=1.0)
        bar = bt.base[-1]
        entry_ref = float(bar['o'])
        c = core.Candidate(
            tf='1m', side='BUY', signal_t=int(bar['ct']), quality=100.0,
            confluence=100.0, priority=100.0, entry_ref=entry_ref,
            stop_ref=entry_ref - 0.01, target_ref=entry_ref + 0.02,
            regime='BREAKOUT UP', atr=1.0,
        )

        # Tight stop requests enormous quantity. At 30x leverage the explicit
        # account-wide 3.15x gross cap, not the old per-position 45% block,
        # must be the binding exposure constraint.
        bt._open_candidate(c, bar)
        assert len(bt.positions) == 1
        exp = portfolio_cap.current_exposure(bt, float(bar['o']))
        assert exp['gross_notional_x_equity'] <= 3.15 + 1e-9
        assert exp['margin_used_pct'] <= 45.0 + 1e-9
        assert exp['margin_used_pct'] <= 10.6  # 3.15x / 30x ~= 10.5%
        assert bt.portfolio_cap_scaled_entries >= 1

        # A second tight-stop position must not stack another full exposure
        # block merely because 30x leverage leaves unused initial margin.
        bt._open_candidate(c, bar)
        assert len(bt.positions) == 1
        assert bt.portfolio_cap_rejections >= 1

        # Lower leverage can reduce the effective gross cap because the shared
        # margin budget becomes binding; higher leverage cannot raise it above
        # the explicit gross cap.
        core.LEVERAGE = 5.0
        assert abs(portfolio_cap.effective_gross_cap_x() - 2.25) < 1e-12
        core.LEVERAGE = 30.0
        assert abs(portfolio_cap.effective_gross_cap_x() - 3.15) < 1e-12

        r = bt.report()
        assert r['portfolio_margin_cap_pct'] == 45.0
        assert r['portfolio_gross_notional_cap_x'] == 3.15
        assert r['leverage'] == 30.0
        assert r['liquidation_modeled'] is False
        assert r['max_gross_notional_x_equity'] <= 3.15 + 1e-9
        print('PORTFOLIO CAP SELF TEST OK: 30x leverage decoupled from 3.15x gross exposure, shared margin budget enforced')
    finally:
        core.LEVERAGE = old_lev
        portfolio_cap.PORTFOLIO_GROSS_NOTIONAL_X = old_gross
        portfolio_cap.PORTFOLIO_MARGIN_USE_PCT = old_margin


if __name__ == '__main__':
    main()
