from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import backtest_v24 as core
from backtest_v24_guarded import GuardedBacktester
from ta_engine import analyze_latest
import portfolio_cap

# Install one shared account-level margin/notional budget for BOTH the base and
# guarded engines before either backtester is constructed.
portfolio_cap.install()


def _fmt_seconds(seconds: float | None) -> str:
    if seconds is None or seconds < 0 or seconds == float('inf'):
        return '--:--'
    seconds = int(seconds + 0.5)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f'{h:d}:{m:02d}:{s:02d}'
    return f'{m:02d}:{s:02d}'


def build_dataset_with_progress(base, show_progress: bool = True):
    data = {}
    total = len(core.TF_ORDER)
    started = time.perf_counter()
    if show_progress:
        print(f'Building {total}-timeframe dataset...', flush=True)
    for idx, tf in enumerate(core.TF_ORDER, 1):
        data[tf] = core.resample(base, tf)
        if show_progress:
            pct = 100.0 * idx / total
            elapsed = time.perf_counter() - started
            msg = f'  Timeframes: {idx:2d}/{total}  {pct:5.1f}%  current={tf:<3}  elapsed={_fmt_seconds(elapsed)}'
            print('\r' + msg.ljust(100), end='', flush=True)
    if show_progress:
        print()
    return data


def _construct_with_shared_data(cls, base, shared_data, equity, fee_bps, slippage_bps):
    original = core.build_dataset
    core.build_dataset = lambda _base: shared_data
    try:
        return cls(base, equity=equity, fee_bps=fee_bps, slippage_bps=slippage_bps)
    finally:
        core.build_dataset = original


def run_with_progress(bt, label: str, show_progress: bool = True, refresh_seconds: float = 1.0):
    total = len(bt.base)
    started = time.perf_counter()
    last_print = 0.0

    def emit(done: int, force: bool = False):
        nonlocal last_print
        if not show_progress:
            return
        now = time.perf_counter()
        if not force and (now - last_print) < refresh_seconds:
            return
        last_print = now
        elapsed = max(now - started, 1e-9)
        rate = done / elapsed
        remaining = (total - done) / rate if rate > 0 else None
        pct = 100.0 * done / total if total else 100.0
        if total:
            px = float(bt.base[max(0, min(done - 1, total - 1))]['c']) if done else float(bt.base[0]['o'])
            exposure = portfolio_cap.current_exposure(bt, px)
            gross_x = exposure['gross_notional_x_equity']
            margin_pct = exposure['margin_used_pct']
        else:
            gross_x = 0.0; margin_pct = 0.0
        msg = (
            f'[{label}] {pct:6.2f}%  {done:,}/{total:,} candles  '
            f'{rate:,.0f} candles/s  elapsed={_fmt_seconds(elapsed)}  ETA={_fmt_seconds(remaining)}  '
            f'trades={len(bt.closed):,}  open={len(bt.positions)}  equity=${bt.equity:,.2f}  '
            f'gross={gross_x:.2f}x  margin={margin_pct:.1f}%'
        )
        print('\r' + msg.ljust(190), end='', flush=True)

    if show_progress:
        print(f'Running {label} simulation...', flush=True)
        print(
            f'Portfolio cap: total margin <= {portfolio_cap.PORTFOLIO_MARGIN_USE_PCT:.0f}% of MTM equity; '
            f'gross notional <= {portfolio_cap.PORTFOLIO_GROSS_NOTIONAL_X:.2f}x MTM equity; '
            f'leverage={core.LEVERAGE:.0f}x.',
            flush=True,
        )
    emit(0, force=True)

    for n, bar in enumerate(bt.base, 1):
        bt._manage(bar)
        if bt.pending:
            for c in sorted(bt.pending, key=lambda x: x.priority, reverse=True):
                bt._open_candidate(c, bar)
            bt.pending = []

        current_ct = int(bar['ct'])
        fresh = []
        for tf in core.TF_ORDER:
            bars_all = bt.data[tf]
            i = bt.next_event_idx[tf]
            while i < len(bars_all) and int(bars_all[i]['ct']) < current_ct:
                i += 1
            bt.next_event_idx[tf] = i
            if i >= len(bars_all) or int(bars_all[i]['ct']) != current_ct:
                continue
            b = bars_all[i]
            bt.next_event_idx[tf] = i + 1
            if not b.get('closed'):
                continue
            bt.cur_indices[tf] = i
            start = max(0, i - core.ANALYSIS_WINDOW + 1)
            window = bars_all[start:i + 1]
            if len(window) >= 30:
                try:
                    bt.analyses[tf] = analyze_latest(window, 'Aggressive')['confirmed']
                except Exception:
                    pass
            c = bt._candidate(tf, i)
            if c:
                fresh.append(c)
            bt.prev_score[tf] = float((bt.analyses.get(tf) or {}).get('score', 0))
        bt.pending = fresh
        bt._update_dd(float(bar['c']))
        emit(n)

    last = bt.base[-1]
    for p in list(bt.positions):
        bt._close(p, float(last['c']), 'end_of_test', int(last['ct']))

    emit(total, force=True)
    if show_progress:
        print()
    return bt.report()


def _summary(report):
    keys = [
        'start_equity', 'end_equity', 'return_pct', 'trades', 'win_rate_pct',
        'profit_factor', 'max_drawdown_pct', 'avg_r', 'fees_paid', 'rejections',
        'leverage', 'portfolio_margin_cap_pct', 'portfolio_gross_notional_cap_x',
        'effective_gross_cap_x', 'max_gross_notional_x_equity',
        'max_margin_used_pct', 'portfolio_cap_rejections',
        'peak_equity', 'profit_giveback_pct', 'cost_rejections',
        'risk_throttled_entries', 'max_loss_streak',
    ]
    return {k: report.get(k) for k in keys if k in report}


def main():
    ap = argparse.ArgumentParser(description='Terminal 3 v2.4 comparison runner with live progress and ETA')
    ap.add_argument('csv', help='1-minute BTC OHLCV CSV or ZIP containing one CSV')
    ap.add_argument('--equity', type=float, default=1000)
    ap.add_argument('--fee-bps', type=float, default=6.0)
    ap.add_argument('--slippage-bps', type=float, default=1.0)
    ap.add_argument('--start', default=None)
    ap.add_argument('--end', default=None)
    ap.add_argument('--last-days', type=float, default=180.0)
    ap.add_argument('--out', default='backtest_results')
    ap.add_argument('--mode', choices=['base', 'guarded', 'compare'], default='compare')
    a = ap.parse_args()

    path = Path(a.csv)
    print('Scanning data range...', flush=True)
    range_started = time.perf_counter()
    start_ms, end_ms = core.resolve_time_range(path, a.start, a.end, a.last_days)
    print(f'Data range resolved in {_fmt_seconds(time.perf_counter() - range_started)}.', flush=True)

    print('Loading selected 1-minute candles...', flush=True)
    load_started = time.perf_counter()
    base = core.load_1m_csv(path, start_ms, end_ms)
    print(f'Loaded {len(base):,} candles in {_fmt_seconds(time.perf_counter() - load_started)}.', flush=True)

    shared_data = build_dataset_with_progress(base, show_progress=True)
    out = Path(a.out)

    if a.mode in {'base', 'compare'}:
        base_bt = _construct_with_shared_data(core.Backtester, base, shared_data, a.equity, a.fee_bps, a.slippage_bps)
        base_report = run_with_progress(base_bt, 'BASE v2.4')
        j, c = core.save_report(base_report, out / 'base')
        print('BASE result:')
        print(json.dumps(_summary(base_report), indent=2))
        print(f'Report: {j}\nTrades: {c}\n', flush=True)

    if a.mode in {'guarded', 'compare'}:
        guard_bt = _construct_with_shared_data(GuardedBacktester, base, shared_data, a.equity, a.fee_bps, a.slippage_bps)
        guard_report = run_with_progress(guard_bt, 'GUARDED v2.4')
        j, c = core.save_report(guard_report, out / 'guarded')
        print('GUARDED result:')
        print(json.dumps(_summary(guard_report), indent=2))
        print(f'Report: {j}\nTrades: {c}', flush=True)


if __name__ == '__main__':
    main()