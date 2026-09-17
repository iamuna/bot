from __future__ import annotations

from backtest_oos_v242 import MINUTE_MS, DAY_MS, plan_windows, summarize_reports


def main():
    last = 1_800_000_000_000
    ws = plan_windows(last, windows=3, window_days=180, skip_recent_days=180, warmup_days=60)
    assert len(ws) == 3
    assert ws[0]['eval_end_ms'] == last - 180 * DAY_MS - MINUTE_MS
    assert ws[1]['eval_end_ms'] == ws[0]['eval_start_ms'] - MINUTE_MS
    assert ws[0]['warmup_start_ms'] == ws[0]['eval_start_ms'] - 60 * DAY_MS
    assert ws[0]['eval_start_ms'] > ws[1]['eval_start_ms'] > ws[2]['eval_start_ms']

    reports = [
        {
            'oos_window_id': 1, 'oos_eval_start': 'A', 'oos_eval_end': 'B',
            'end_equity': 1010.0, 'return_pct': 1.0, 'net_pnl': 10.0,
            'trades': 2, 'win_rate_pct': 50.0, 'profit_factor': 2.0,
            'max_drawdown_pct': 3.0, 'avg_r': .1, 'fees_paid': 2.0,
            'peak_equity': 1020.0,
            'trades_detail': [
                {'pnl': 8.0, 'r': .8}, {'pnl': -4.0, 'r': -.4},
            ],
        },
        {
            'oos_window_id': 2, 'oos_eval_start': 'C', 'oos_eval_end': 'D',
            'end_equity': 995.0, 'return_pct': -.5, 'net_pnl': -5.0,
            'trades': 1, 'win_rate_pct': 0.0, 'profit_factor': 0.0,
            'max_drawdown_pct': 4.0, 'avg_r': -.2, 'fees_paid': 1.0,
            'peak_equity': 1000.0,
            'trades_detail': [{'pnl': -2.0, 'r': -.2}],
        },
    ]
    s = summarize_reports(reports)
    assert s['window_count'] == 2
    assert s['positive_windows'] == 1 and s['negative_windows'] == 1
    assert s['sum_independent_net_pnl'] == 5.0
    assert s['pooled_trades'] == 3
    assert s['pooled_profit_factor'] == round(8.0 / 6.0, 4)
    assert s['total_fees_paid'] == 3.0
    print('V2.4.2 OOS SELF TEST OK: disjoint holdouts, warm-up boundaries, pooled aggregation')


if __name__ == '__main__':
    main()
