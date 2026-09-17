from __future__ import annotations

from datetime import datetime, timezone

from backtest_v25_chronological import (
    FEE_BPS,
    GROSS_CAP_X,
    LEVERAGE,
    PORTFOLIO_MARGIN_PCT,
    SLIPPAGE_BPS,
    WARMUP_DAYS,
    summarize_by_year,
)


def ms(year, month, day):
    return int(datetime(year, month, day, tzinfo=timezone.utc).timestamp() * 1000)


def main():
    assert WARMUP_DAYS == 90
    assert FEE_BPS == 6.0
    assert SLIPPAGE_BPS == 1.0
    assert LEVERAGE == 30.0
    assert GROSS_CAP_X == 3.15
    assert PORTFOLIO_MARGIN_PCT == 45.0

    report = {
        'trades_detail': [
            {'exit_t': ms(2020, 1, 2), 'pnl': 10.0, 'fees': 1.0, 'r': 1.0},
            {'exit_t': ms(2020, 2, 2), 'pnl': -5.0, 'fees': 0.5, 'r': -0.5},
            {'exit_t': ms(2021, 1, 2), 'pnl': 3.0, 'fees': 0.4, 'r': 0.3},
        ]
    }
    by_year = summarize_by_year(report)
    assert list(by_year) == ['2020', '2021']
    assert by_year['2020']['trades'] == 2
    assert by_year['2020']['wins'] == 1
    assert by_year['2020']['losses'] == 1
    assert by_year['2020']['net_pnl'] == 5.0
    assert by_year['2020']['profit_factor'] == 2.0
    assert by_year['2020']['avg_r'] == 0.25
    assert by_year['2021']['net_pnl'] == 3.0
    print('v2.5 chronological audit helper self-test passed')


if __name__ == '__main__':
    main()
