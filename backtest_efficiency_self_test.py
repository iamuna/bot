from __future__ import annotations

from backtest_self_test import synthetic
from backtest_v24 import Candidate
from backtest_v24_efficient import EfficientBacktester


def candidate(tf='5m'):
    return Candidate(
        tf=tf, side='BUY', signal_t=1, quality=90.0, confluence=80.0,
        priority=90.0, entry_ref=100.0, stop_ref=99.0, target_ref=102.0,
        regime='TREND UP', atr=1.0,
    )


def main():
    x = synthetic(220)
    bt = EfficientBacktester(x, equity=1000, fee_bps=6, slippage_bps=1)
    bar = x[100]

    # Low timeframes remain available as analysis context but cannot consume
    # capital in the efficient candidate.
    bt._open_candidate(candidate('5m'), bar)
    assert len(bt.positions) == 0
    assert bt.low_tf_rejections == 1

    # Structural configuration is explicit and reportable.
    assert bt.efficient.min_entry_timeframe_minutes == 15
    assert abs(bt.selective.max_round_trip_cost_r - 0.16) < 1e-12

    r = bt.report()
    assert r['engine'].startswith('Terminal 3 v2.4.2 efficient')
    assert r['efficient_config']['min_entry_timeframe_minutes'] == 15
    assert r['low_tf_rejections'] == 1
    print('EFFICIENCY SELF TEST OK: >=15m entry floor + 0.16R friction cap')


if __name__ == '__main__':
    main()
