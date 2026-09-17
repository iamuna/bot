from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import os
import time
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path

import backtest_v24 as core
from backtest_v24_guarded import GuardedBacktester
from ta_engine import analyze_latest
import portfolio_cap

# Install one shared account-level margin/notional budget for BOTH the base and
# guarded engines before either backtester is constructed.
portfolio_cap.install()

# Only these TA fields are consumed by the historical strategy loop. Keeping a
# compact tuple cache avoids retaining hundreds of thousands of large analysis
# dictionaries while allowing the expensive TA calculations to be shared by
# BASE and GUARDED.
_ANALYSIS_FIELDS = ('score', 'coverage', 'quality', 'regime', 'extension_atr', 'atr')


def _fmt_seconds(seconds: float | None) -> str:
    if seconds is None or seconds < 0 or seconds == float('inf'):
        return '--:--'
    seconds = int(seconds + 0.5)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f'{h:d}:{m:02d}:{s:02d}'
    return f'{m:02d}:{s:02d}'


def _auto_workers(requested: int = 0) -> int:
    """Choose CPU workers conservatively for a desktop backtest.

    CPython's TA loop is CPU-bound, so processes are used rather than threads.
    Half the reported logical CPUs is a good default for SMT machines: on the
    user's 8-core / 16-thread PC this selects 8 worker processes and targets the
    physical cores without intentionally oversubscribing them.
    """
    logical = max(1, int(os.cpu_count() or 1))
    if requested and requested > 0:
        return max(1, min(int(requested), logical))
    return max(1, min(8, logical // 2 if logical >= 4 else logical))


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


def _pack_analysis(a: dict):
    return tuple(a.get(k) for k in _ANALYSIS_FIELDS)


def _unpack_analysis(values):
    return dict(zip(_ANALYSIS_FIELDS, values))


def _analysis_chunk(tf: str, start_i: int, end_i: int, slice_start: int, bars_slice):
    """CPU worker: precompute one contiguous TA chunk exactly as live replay does."""
    results = []
    for global_i in range(start_i, end_i):
        local_i = global_i - slice_start
        if local_i < 0 or local_i >= len(bars_slice):
            continue
        b = bars_slice[local_i]
        if not b.get('closed'):
            continue
        window_start_global = max(0, global_i - core.ANALYSIS_WINDOW + 1)
        local_start = window_start_global - slice_start
        window = bars_slice[local_start:local_i + 1]
        if len(window) < 30:
            continue
        try:
            confirmed = analyze_latest(window, 'Aggressive')['confirmed']
        except Exception:
            continue
        results.append((global_i, _pack_analysis(confirmed)))
    return tf, start_i, end_i, results


def build_analysis_cache_parallel(data, workers: int = 0, show_progress: bool = True):
    """Precompute expensive TA once using multiple CPU processes.

    BASE and GUARDED use identical historical TA inputs, so recomputing every
    indicator twice in the sequential replay wastes most of the CPU time. This
    stage splits each timeframe into bounded overlapping chunks, computes them
    across worker processes, and stores only the six fields the strategy uses.
    The later portfolio simulations therefore stay deterministic while becoming
    much lighter.
    """
    workers = _auto_workers(workers)
    cache = {tf: [None] * len(data[tf]) for tf in core.TF_ORDER}
    total_points = sum(max(0, len(data[tf]) - 29) for tf in core.TF_ORDER)
    if total_points <= 0:
        return cache

    # Aim for several tasks per worker so the 1m timeframe cannot monopolize a
    # single process, while keeping IPC/pickling overhead bounded on Windows.
    chunk_size = max(2000, min(12000, int(math.ceil(total_points / max(workers * 8, 1)))))
    descriptors = deque()
    for tf in core.TF_ORDER:
        n = len(data[tf])
        start = 29
        while start < n:
            end = min(n, start + chunk_size)
            descriptors.append((tf, start, end))
            start = end

    started = time.perf_counter()
    done_points = 0
    successful = 0
    last_print = 0.0

    if show_progress:
        logical = int(os.cpu_count() or 1)
        print(
            f'Precomputing technical analysis with {workers} CPU workers '
            f'({logical} logical CPUs detected; chunk={chunk_size:,})...',
            flush=True,
        )

    def emit(force: bool = False):
        nonlocal last_print
        if not show_progress:
            return
        now = time.perf_counter()
        if not force and now - last_print < 0.75:
            return
        last_print = now
        elapsed = max(now - started, 1e-9)
        rate = done_points / elapsed
        eta = (total_points - done_points) / rate if rate > 0 else None
        pct = 100.0 * done_points / total_points
        msg = (
            f'[TA PRECOMPUTE] {pct:6.2f}%  {done_points:,}/{total_points:,} points  '
            f'{rate:,.0f}/s  elapsed={_fmt_seconds(elapsed)}  ETA={_fmt_seconds(eta)}  '
            f'workers={workers}  cached={successful:,}'
        )
        print('\r' + msg.ljust(170), end='', flush=True)

    # Spawn is explicit so CI and Windows exercise the same process semantics.
    ctx = mp.get_context('spawn')
    max_in_flight = max(workers * 2, 1)
    pending = {}

    def submit_one(pool):
        if not descriptors:
            return False
        tf, start_i, end_i = descriptors.popleft()
        slice_start = max(0, start_i - core.ANALYSIS_WINDOW + 1)
        # Only send the bars needed by this chunk plus its warm-up overlap.
        bars_slice = data[tf][slice_start:end_i]
        fut = pool.submit(_analysis_chunk, tf, start_i, end_i, slice_start, bars_slice)
        pending[fut] = (tf, start_i, end_i)
        return True

    emit(force=True)
    with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as pool:
        while len(pending) < max_in_flight and submit_one(pool):
            pass

        while pending:
            completed, _ = wait(tuple(pending), return_when=FIRST_COMPLETED)
            for fut in completed:
                _tf, _start, _end = pending.pop(fut)
                tf, start_i, end_i, rows = fut.result()
                for i, packed in rows:
                    cache[tf][i] = packed
                successful += len(rows)
                done_points += end_i - start_i
                emit()
                submit_one(pool)

    emit(force=True)
    if show_progress:
        print()
        print(
            f'TA cache ready: {successful:,} historical analyses computed once and shared by BASE + GUARDED.',
            flush=True,
        )
    return cache


def _construct_with_shared_data(cls, base, shared_data, equity, fee_bps, slippage_bps):
    original = core.build_dataset
    core.build_dataset = lambda _base: shared_data
    try:
        return cls(base, equity=equity, fee_bps=fee_bps, slippage_bps=slippage_bps)
    finally:
        core.build_dataset = original


def _bankruptcy_snapshot(bt, price: float, t: int, processed: int, total: int) -> dict:
    """Create an explicit account-failure record when MTM equity is exhausted.

    Liquidation mechanics are not yet modeled, so zero MTM equity is treated as
    an economic stop rather than allowing impossible negative-capital trading.
    """
    mtm = float(bt._mark_to_market(float(price)))
    return {
        'bankrupt': True,
        'status': 'BANKRUPT',
        'bankruptcy_t': int(t),
        'bankruptcy_mtm_equity': round(mtm, 6),
        'realized_equity_at_bankruptcy': round(float(bt.equity), 6),
        'open_positions_at_bankruptcy': len(bt.positions),
        'processed_candles': int(processed),
        'processed_pct': round(100.0 * processed / total, 4) if total else 100.0,
        'economic_end_equity': 0.0,
    }


def _finalize_report(bt, bankruptcy: dict | None, processed: int, total: int) -> dict:
    r = bt.report()
    if bankruptcy is None:
        r.update({
            'bankrupt': False,
            'status': 'COMPLETE',
            'processed_candles': int(processed),
            'processed_pct': round(100.0 * processed / total, 4) if total else 100.0,
            'economic_end_equity': round(float(r.get('end_equity', bt.equity)), 2),
        })
        return r

    # Once MTM equity is exhausted, the economically meaningful account value
    # is zero. Do not continue sizing trades from negative/invalid capital.
    r.update(bankruptcy)
    r['end_equity'] = 0.0
    r['return_pct'] = -100.0
    r['net_pnl'] = round(-float(bt.start_equity), 2)
    r['max_drawdown_pct'] = max(100.0, float(r.get('max_drawdown_pct') or 0.0))
    return r


def run_with_progress(
    bt,
    label: str,
    show_progress: bool = True,
    refresh_seconds: float = 1.0,
    analysis_cache=None,
):
    total = len(bt.base)
    started = time.perf_counter()
    last_print = 0.0
    bankruptcy = None
    processed = 0

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
            f'leverage setting={core.LEVERAGE:.0f}x; '
            f'effective gross cap={portfolio_cap.effective_gross_cap_x():.2f}x.',
            flush=True,
        )
        if analysis_cache is not None:
            print('Using shared precomputed TA cache; indicator calculations are not repeated in this replay.', flush=True)
        print('Liquidation mechanics are not modeled; MTM equity <= $0 stops the simulation as BANKRUPT.', flush=True)
    emit(0, force=True)

    for n, bar in enumerate(bt.base, 1):
        # If the previous candle already exhausted capital, do not process
        # another candle or permit any new position sizing.
        opening_mtm = float(bt._mark_to_market(float(bar['o'])))
        if opening_mtm <= 0:
            bankruptcy = _bankruptcy_snapshot(bt, float(bar['o']), int(bar['t']), n - 1, total)
            processed = n - 1
            emit(processed, force=True)
            break

        bt._manage(bar)
        processed = n

        # Existing positions can exhaust the account during this candle.
        after_manage_mtm = float(bt._mark_to_market(float(bar['c'])))
        if after_manage_mtm <= 0:
            bankruptcy = _bankruptcy_snapshot(bt, float(bar['c']), int(bar['ct']), n, total)
            bt._update_dd(float(bar['c']))
            emit(n, force=True)
            break

        if bt.pending:
            for c in sorted(bt.pending, key=lambda x: x.priority, reverse=True):
                bt._open_candidate(c, bar)
                # Entry fees/slippage can also consume the remaining capital.
                entry_mtm = float(bt._mark_to_market(float(bar['o'])))
                if entry_mtm <= 0:
                    bankruptcy = _bankruptcy_snapshot(bt, float(bar['o']), int(bar['t']), n, total)
                    break
            bt.pending = []
            if bankruptcy is not None:
                bt._update_dd(float(bar['o']))
                emit(n, force=True)
                break

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

            if analysis_cache is not None:
                packed = analysis_cache[tf][i] if i < len(analysis_cache[tf]) else None
                if packed is not None:
                    bt.analyses[tf] = _unpack_analysis(packed)
            else:
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

        closing_mtm = float(bt._mark_to_market(float(bar['c'])))
        if closing_mtm <= 0:
            bankruptcy = _bankruptcy_snapshot(bt, float(bar['c']), int(bar['ct']), n, total)
            emit(n, force=True)
            break

        emit(n)

    if bankruptcy is None:
        last = bt.base[-1]
        for p in list(bt.positions):
            bt._close(p, float(last['c']), 'end_of_test', int(last['ct']))
        processed = total
        emit(total, force=True)
    else:
        if show_progress:
            print(
                f'\n*** {label} BANKRUPT at {bankruptcy["processed_pct"]:.2f}% of the test '
                f'(MTM equity={bankruptcy["bankruptcy_mtm_equity"]:.2f}). '
                f'Remaining candles skipped. ***',
                flush=True,
            )

    if show_progress:
        print()
    return _finalize_report(bt, bankruptcy, processed, total)


def _summary(report):
    keys = [
        'status', 'bankrupt', 'bankruptcy_t', 'bankruptcy_mtm_equity',
        'processed_pct', 'start_equity', 'end_equity', 'return_pct', 'trades',
        'win_rate_pct', 'profit_factor', 'max_drawdown_pct', 'avg_r',
        'fees_paid', 'rejections', 'leverage', 'portfolio_margin_cap_pct',
        'portfolio_gross_notional_cap_x', 'effective_gross_cap_x',
        'max_gross_notional_x_equity', 'max_margin_used_pct',
        'portfolio_cap_rejections', 'portfolio_cap_scaled_entries',
        'liquidation_modeled', 'peak_equity', 'profit_giveback_pct',
        'cost_rejections', 'risk_throttled_entries', 'max_loss_streak',
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
    ap.add_argument('--leverage', type=float, default=30.0, help='research leverage setting; capped at 30x by this runner')
    ap.add_argument('--gross-cap-x', type=float, default=3.15, help='account-wide gross notional cap as multiple of MTM equity')
    ap.add_argument('--portfolio-margin-pct', type=float, default=45.0, help='account-wide initial-margin budget as percent of MTM equity')
    ap.add_argument('--workers', type=int, default=0, help='TA worker processes; 0=auto (8 on a 16-thread CPU)')
    a = ap.parse_args()

    if not (1.0 <= a.leverage <= 30.0):
        ap.error('--leverage must be between 1x and 30x for this research runner')
    if not (0.1 <= a.gross_cap_x <= 10.0):
        ap.error('--gross-cap-x must be between 0.1x and 10x')
    if not (1.0 <= a.portfolio_margin_pct <= 100.0):
        ap.error('--portfolio-margin-pct must be between 1 and 100')
    if a.workers < 0:
        ap.error('--workers must be 0 (auto) or a positive integer')

    # Leverage is now an explicit test parameter instead of a hard-coded 7x
    # assumption. Gross exposure stays separately capped, so moving to 30x
    # cannot silently turn a 3.15x exposure envelope into 13.5x exposure.
    core.LEVERAGE = float(a.leverage)
    portfolio_cap.PORTFOLIO_GROSS_NOTIONAL_X = float(a.gross_cap_x)
    portfolio_cap.PORTFOLIO_MARGIN_USE_PCT = float(a.portfolio_margin_pct)
    workers = _auto_workers(a.workers)

    path = Path(a.csv)
    print('Scanning data range...', flush=True)
    range_started = time.perf_counter()
    start_ms, end_ms = core.resolve_time_range(path, a.start, a.end, a.last_days)
    print(f'Data range resolved in {_fmt_seconds(time.perf_counter() - range_started)}.', flush=True)

    print('Loading selected 1-minute candles...', flush=True)
    load_started = time.perf_counter()
    base = core.load_1m_csv(path, start_ms, end_ms)
    print(f'Loaded {len(base):,} candles in {_fmt_seconds(time.perf_counter() - load_started)}.', flush=True)

    print(
        f'Risk envelope: leverage={core.LEVERAGE:.0f}x, '
        f'gross cap={portfolio_cap.PORTFOLIO_GROSS_NOTIONAL_X:.2f}x equity, '
        f'margin budget={portfolio_cap.PORTFOLIO_MARGIN_USE_PCT:.0f}%, '
        f'effective cap={portfolio_cap.effective_gross_cap_x():.2f}x equity.',
        flush=True,
    )
    print(f'CPU mode: {workers} TA worker processes.', flush=True)

    shared_data = build_dataset_with_progress(base, show_progress=True)
    analysis_cache = build_analysis_cache_parallel(shared_data, workers=workers, show_progress=True)
    out = Path(a.out)

    if a.mode in {'base', 'compare'}:
        base_bt = _construct_with_shared_data(core.Backtester, base, shared_data, a.equity, a.fee_bps, a.slippage_bps)
        base_report = run_with_progress(base_bt, 'BASE v2.4', analysis_cache=analysis_cache)
        j, c = core.save_report(base_report, out / 'base')
        print('BASE result:')
        print(json.dumps(_summary(base_report), indent=2))
        print(f'Report: {j}\nTrades: {c}\n', flush=True)

    if a.mode in {'guarded', 'compare'}:
        guard_bt = _construct_with_shared_data(GuardedBacktester, base, shared_data, a.equity, a.fee_bps, a.slippage_bps)
        guard_report = run_with_progress(guard_bt, 'GUARDED v2.4', analysis_cache=analysis_cache)
        j, c = core.save_report(guard_report, out / 'guarded')
        print('GUARDED result:')
        print(json.dumps(_summary(guard_report), indent=2))
        print(f'Report: {j}\nTrades: {c}', flush=True)


if __name__ == '__main__':
    mp.freeze_support()
    main()
