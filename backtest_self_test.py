from __future__ import annotations

import csv
import math
import random
import tempfile
import zipfile
from pathlib import Path

from backtest_v24 import Backtester, resample, qmult, regime_mult, tf_group, TF_RISK, load_1m_csv


def synthetic(n=520):
    r = random.Random(24); p = 75_000.0; out = []; base = 1_700_000_000_000
    for i in range(n):
        drift = 2.0 + 3.0 * math.sin(i / 35); o = p; c = max(1000, o + drift + r.uniform(-18, 18))
        h = max(o, c) + r.uniform(2, 12); l = min(o, c) - r.uniform(2, 12); v = 100 + r.uniform(0, 50)
        out.append({'t': base + i * 60_000, 'o': o, 'h': h, 'l': l, 'c': c, 'v': v, 'qv': v, 'quote_v': v, 'trades': 0, 'tb': 0.0, 'tbq': 0.0, 'ct': base + (i + 1) * 60_000 - 1, 'closed': True, 'source': 'test'})
        p = c
    return out


def test_binance_zip_loader():
    with tempfile.TemporaryDirectory() as td:
        csv_path = Path(td) / 'BTCUSD_1m_Binance.csv'
        with csv_path.open('w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['Open time', 'Open', 'High', 'Low', 'Close', 'Volume', 'Close time', 'Quote asset volume', 'Number of trades', 'Taker buy base asset volume', 'Taker buy quote asset volume', 'Ignore'])
            for i in range(120):
                minute = i % 60; hour = i // 60
                ts = f'2025-01-01 {hour:02d}:{minute:02d}:00'
                w.writerow([ts, 100+i*.01, 101+i*.01, 99+i*.01, 100.5+i*.01, 5, '', 500, 10, 2, 200, 0])
        zip_path = Path(td) / 'BTCUSD_1m_Binance.zip'
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
            z.write(csv_path, csv_path.name)
        rows = load_1m_csv(zip_path)
        assert len(rows) == 120
        assert rows[0]['qv'] == 500 and rows[0]['trades'] == 10 and rows[0]['tb'] == 2 and rows[0]['tbq'] == 200


def main():
    test_binance_zip_loader()
    x = synthetic()
    assert len(resample(x, '1m')) == len(x)
    m3 = resample(x, '3m'); assert len(m3) > 150 and all(b['h'] >= b['l'] for b in m3)
    assert tf_group('1m') == 'scalp' and tf_group('1h') == 'intraday' and tf_group('4h') == 'swing' and tf_group('1d') == 'macro'
    assert TF_RISK['1m'] < TF_RISK['1h'] < TF_RISK['1d']
    assert qmult(40) < qmult(75) < qmult(90)
    assert regime_mult('BREAKOUT UP') > regime_mult('RANGE')
    r = Backtester(x, equity=1000, fee_bps=5, slippage_bps=1).run()
    assert r['engine'].startswith('Terminal 3 v2.4') and r['start_equity'] == 1000
    assert r['end_equity'] > 0 and r['max_drawdown_pct'] >= 0 and 'by_timeframe' in r
    print('BACKTEST SELF TEST OK: Binance ZIP loader, resampling, adaptive risk tiers, slot groups, fees/slippage path, reporting')


if __name__ == '__main__':
    main()
