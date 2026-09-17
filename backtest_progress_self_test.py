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
    assert 'max_drawdown_pct' in r
    print('PROGRESS SELF TEST OK: shared dataset, progress runner, ETA formatting')


if __name__ == '__main__':
    main()
