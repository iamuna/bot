from __future__ import annotations

from backtest_self_test import synthetic
from backtest_v24 import Candidate
from backtest_v24_selective import SelectiveBacktester


def candidate(entry=100.0, stop=99.0, target=102.0, tf='1h', side='BUY'):
    return Candidate(
        tf=tf, side=side, signal_t=1, quality=80.0, confluence=70.0,
        priority=80.0, entry_ref=entry, stop_ref=stop,
        target_ref=target, regime='TREND UP', atr=1.0,
    )


def main():
    x = synthetic(260)
    bt = SelectiveBacktester(x, equity=1000, fee_bps=6, slippage_bps=1)

    # A 1-cent stop on a $100 instrument has a huge modeled cost in R and must
    # be rejected before any position can be opened.
    tight = candidate(entry=100, stop=99.99, target=100.03, tf='1m')
    bt._open_candidate(tight, x[100])
    assert bt.selective_cost_rejections == 1
    assert len(bt.positions) == 0

    # Material account drawdown must lock new risk instead of allowing the
    # strategy to grind asymptotically toward zero.
    bt.equity = 840.0
    normal = candidate(entry=100, stop=99, target=102, tf='1h')
    bt._open_candidate(normal, x[101])
    assert bt.drawdown_lock_rejections == 1
    assert len(bt.positions) == 0

    # Report surface must expose the new research controls.
    r = bt.report()
    assert r['engine'].startswith('Terminal 3 v2.4.1 selective')
    assert r['selective_config']['max_round_trip_cost_r'] == 0.20
    assert 'rolling_edge' in r
    assert 'max_start_drawdown_pct_selective' in r

    print('SELECTIVE SELF TEST OK: cost-R gate, drawdown lock, rolling-edge reporting')


if __name__ == '__main__':
    main()
