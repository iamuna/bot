from __future__ import annotations

from backtest_progress_runner import _fmt_seconds, build_dataset_with_progress, run_with_progress, _construct_with_shared_data
import backtest_v24 as core
from backtest_self_test import synthetic


def main():
    x = synthetic(220)
    assert _fmt_seconds(65) == '01:05'
    data = build_dataset_with_progress(x, show_progress=False)
    assert set(data) == set(core.TF_ORDER)

    bt = _construct_with_shared_data(core.Backtester, x, data, 1000, 6, 1)
    r = run_with_progress(bt, 'TEST', show_progress=False)
    assert r['start_equity'] == 1000
    assert r['end_equity'] > 0
    assert r['status'] == 'COMPLETE' and r['bankrupt'] is False
    assert 'max_drawdown_pct' in r

    # Account failure must terminate immediately instead of allowing impossible
    # negative-capital trading through the rest of the historical dataset.
    bt2 = _construct_with_shared_data(core.Backtester, x, data, 1000, 6, 1)
    bt2.equity = -1.0
    r2 = run_with_progress(bt2, 'BANKRUPTCY TEST', show_progress=False)
    assert r2['status'] == 'BANKRUPT' and r2['bankrupt'] is True
    assert r2['end_equity'] == 0.0 and r2['return_pct'] == -100.0
    assert r2['processed_candles'] == 0

    print('PROGRESS SELF TEST OK: shared dataset, ETA formatting, and hard bankruptcy stop')


if __name__ == '__main__':
    main()
