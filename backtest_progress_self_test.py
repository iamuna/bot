from __future__ import annotations

from backtest_progress_runner import (
    _fmt_seconds,
    _construct_with_shared_data,
    build_analysis_cache_parallel,
    build_dataset_with_progress,
    run_with_progress,
)
import backtest_v24 as core
from backtest_self_test import synthetic


def main():
    x = synthetic(260)
    assert _fmt_seconds(65) == '01:05'
    data = build_dataset_with_progress(x, show_progress=False)
    assert set(data) == set(core.TF_ORDER)

    # Parallel precomputation must preserve the exact historical replay result.
    cache = build_analysis_cache_parallel(data, workers=2, show_progress=False)
    assert set(cache) == set(core.TF_ORDER)
    assert any(v is not None for v in cache['1m'][29:])

    direct_bt = _construct_with_shared_data(core.Backtester, x, data, 1000, 6, 1)
    direct = run_with_progress(direct_bt, 'DIRECT TEST', show_progress=False)

    cached_bt = _construct_with_shared_data(core.Backtester, x, data, 1000, 6, 1)
    cached = run_with_progress(cached_bt, 'CACHED TEST', show_progress=False, analysis_cache=cache)

    for key in ('end_equity', 'return_pct', 'trades', 'wins', 'losses', 'profit_factor', 'max_drawdown_pct', 'avg_r'):
        assert cached.get(key) == direct.get(key), (key, direct.get(key), cached.get(key))
    assert cached['trades_detail'] == direct['trades_detail']
    assert cached['status'] == 'COMPLETE' and cached['bankrupt'] is False

    # Account failure must terminate immediately instead of allowing impossible
    # negative-capital trading through the rest of the historical dataset.
    bt2 = _construct_with_shared_data(core.Backtester, x, data, 1000, 6, 1)
    bt2.equity = -1.0
    r2 = run_with_progress(bt2, 'BANKRUPTCY TEST', show_progress=False, analysis_cache=cache)
    assert r2['status'] == 'BANKRUPT' and r2['bankrupt'] is True
    assert r2['end_equity'] == 0.0 and r2['return_pct'] == -100.0
    assert r2['processed_candles'] == 0

    print('PROGRESS SELF TEST OK: parallel TA cache matches sequential replay and bankruptcy stop works')


if __name__ == '__main__':
    main()
