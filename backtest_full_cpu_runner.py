from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
import os
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, as_completed, wait
from pathlib import Path

import backtest_v24 as core
import backtest_progress_runner as progress
from backtest_v24_guarded import GuardedBacktester
import portfolio_cap

# Aggressive research mode: use every logical CPU for work that is genuinely
# independent. Time-ordered portfolio state is never split across candles,
# because doing that would change the backtest. Independent BASE/GUARDED
# replays are run concurrently instead.
portfolio_cap.install()

_RESAMPLE_BASE = None


def _fmt_seconds(seconds: float | None) -> str:
    return progress._fmt_seconds(seconds)


def all_cpu_workers(requested: int = 0) -> int:
    logical = max(1, int(os.cpu_count() or 1))
    if requested and requested > 0:
        return max(1, min(int(requested), logical))
    return logical


def _norm(v: str) -> str:
    return ''.join(ch for ch in str(v).lower() if ch.isalnum())


def _index(header: list[str], *names: str):
    m = {_norm(v): i for i, v in enumerate(header)}
    for name in names:
        k = _norm(name)
        if k in m:
            return m[k]
    return None


def _csv_layout(path: Path):
    """Read CSV metadata and first/last timestamps without scanning every row."""
    with path.open('rb') as f:
        header_raw = f.readline()
        data_start = f.tell()
        first_raw = b''
        while not first_raw:
            first_raw = f.readline().strip()
            if not first_raw and f.tell() >= path.stat().st_size:
                break
        size = f.seek(0, 2)
        tail_n = min(size, 256 * 1024)
        f.seek(size - tail_n)
        tail = f.read(tail_n)

    if not header_raw or not first_raw:
        raise ValueError(f'CSV has no usable data rows: {path}')

    header = next(csv.reader([header_raw.decode('utf-8-sig').rstrip('\r\n')]))
    indexes = {
        't': _index(header, 'timestamp', 'time', 'date', 'datetime', 'open_time', 'Open time'),
        'o': _index(header, 'open', 'o'),
        'h': _index(header, 'high', 'h'),
        'l': _index(header, 'low', 'l'),
        'c': _index(header, 'close', 'c'),
        'v': _index(header, 'volume', 'v'),
        'q': _index(header, 'quote_volume', 'quote asset volume', 'qv', 'quotevol'),
        'trades': _index(header, 'number of trades', 'trades'),
        'tb': _index(header, 'taker buy base asset volume', 'tb'),
        'tbq': _index(header, 'taker buy quote asset volume', 'tbq'),
    }
    required = ('t', 'o', 'h', 'l', 'c')
    missing = [k for k in required if indexes[k] is None]
    if missing:
        raise ValueError(f'Missing required CSV columns: {missing}')

    first_row = next(csv.reader([first_raw.decode('utf-8')]))
    first_t = core.parse_ts(first_row[indexes['t']])

    last_raw = None
    for candidate in reversed(tail.splitlines()):
        if candidate.strip():
            last_raw = candidate
            break
    if last_raw is None:
        raise ValueError('Could not find the last CSV row')
    last_row = next(csv.reader([last_raw.decode('utf-8')]))
    last_t = core.parse_ts(last_row[indexes['t']])
    return indexes, data_start, size, first_t, last_t


def resolve_time_range_fast(path: Path, start: str | None, end: str | None, last_days: float | None):
    path = Path(path)
    if path.suffix.lower() != '.csv':
        start_ms, end_ms = core.resolve_time_range(path, start, end, last_days)
        return start_ms, end_ms, None

    layout = _csv_layout(path)
    _, _, _, _first_t, last_t = layout
    start_ms = core.parse_ts(start) if start else None
    end_ms = core.parse_ts(end) if end else None
    if last_days is not None:
        end_ms = last_t if end_ms is None else min(end_ms, last_t)
        start_ms = end_ms - int(float(last_days) * 86_400_000)
    return start_ms, end_ms, layout


def _cell(row: list[str], i, default=''):
    if i is None or i < 0 or i >= len(row):
        return default
    return row[i]


def _load_csv_chunk(
    path_text: str,
    chunk_id: int,
    byte_start: int,
    byte_end: int,
    data_start: int,
    indexes: dict,
    start_ms: int | None,
    end_ms: int | None,
):
    rows_out = []
    scanned = 0
    with open(path_text, 'rb') as f:
        f.seek(byte_start)
        if byte_start > data_start:
            # The partition usually starts in the middle of a row. The previous
            # partition owns that row, so discard the remainder here.
            f.readline()
        while True:
            line_start = f.tell()
            if line_start >= byte_end:
                break
            raw = f.readline()
            if not raw:
                break
            if not raw.strip():
                continue
            scanned += 1
            try:
                row = next(csv.reader([raw.decode('utf-8')]))
                t = core.parse_ts(_cell(row, indexes['t']))
            except Exception:
                continue
            if start_ms is not None and t < start_ms:
                continue
            if end_ms is not None and t > end_ms:
                continue
            try:
                o = float(_cell(row, indexes['o']))
                h = float(_cell(row, indexes['h']))
                l = float(_cell(row, indexes['l']))
                c = float(_cell(row, indexes['c']))
                v = float(_cell(row, indexes['v'], 0) or 0)
                q = float(_cell(row, indexes['q'], v) or v)
                trades = int(float(_cell(row, indexes['trades'], 0) or 0))
                tb = float(_cell(row, indexes['tb'], 0) or 0)
                tbq = float(_cell(row, indexes['tbq'], 0) or 0)
            except Exception:
                continue
            rows_out.append({
                't': t, 'o': o, 'h': h, 'l': l, 'c': c,
                'v': v, 'qv': q, 'quote_v': q, 'trades': trades,
                'tb': tb, 'tbq': tbq, 'ct': t + 59_999,
                'closed': True, 'source': 'csv:1m',
            })
    return chunk_id, scanned, rows_out


def load_1m_parallel(path: Path, start_ms, end_ms, workers: int, layout=None, show_progress: bool = True):
    path = Path(path)
    if path.suffix.lower() != '.csv':
        return core.load_1m_csv(path, start_ms, end_ms)

    if layout is None:
        layout = _csv_layout(path)
    indexes, data_start, size, _first_t, _last_t = layout
    workers = all_cpu_workers(workers)
    usable = max(0, size - data_start)
    if usable <= 0:
        raise ValueError('CSV contains no data bytes')

    chunks = []
    for i in range(workers):
        a = data_start + usable * i // workers
        b = data_start + usable * (i + 1) // workers
        chunks.append((i, a, b))

    started = time.perf_counter()
    completed_bytes = 0
    scanned_rows = 0
    selected = {}
    ctx = mp.get_context('spawn')
    if show_progress:
        print(f'Loading selected 1-minute candles with {workers} CPU workers...', flush=True)

    with ProcessPoolExecutor(max_workers=workers, mp_context=ctx) as pool:
        future_map = {
            pool.submit(
                _load_csv_chunk,
                str(path), i, a, b, data_start, indexes, start_ms, end_ms,
            ): (i, a, b)
            for i, a, b in chunks
        }
        for fut in as_completed(future_map):
            i, a, b = future_map[fut]
            chunk_id, scanned, rows = fut.result()
            selected[chunk_id] = rows
            scanned_rows += scanned
            completed_bytes += b - a
            if show_progress:
                pct = 100.0 * completed_bytes / usable
                elapsed = max(time.perf_counter() - started, 1e-9)
                rate = completed_bytes / elapsed
                eta = (usable - completed_bytes) / rate if rate > 0 else None
                print(
                    '\r' + (
                        f'[CSV LOAD] {pct:6.2f}%  chunks={len(selected):2d}/{workers}  '
                        f'rows_scanned={scanned_rows:,}  selected={sum(len(x) for x in selected.values()):,}  '
                        f'elapsed={_fmt_seconds(elapsed)}  ETA={_fmt_seconds(eta)}  workers={workers}'
                    ).ljust(165),
                    end='', flush=True,
                )

    out = []
    for i in range(workers):
        out.extend(selected.get(i, ()))
    out.sort(key=lambda x: x['t'])
    if show_progress:
        print()
    if len(out) < 100:
        raise ValueError('Need at least 100 one-minute candles')
    return out


def _resample_init(base):
    global _RESAMPLE_BASE
    _RESAMPLE_BASE = base


def _resample_one(tf: str):
    if _RESAMPLE_BASE is None:
        raise RuntimeError('resample worker was not initialized')
    return tf, core.resample(_RESAMPLE_BASE, tf)


def build_dataset_parallel(base, workers: int, show_progress: bool = True):
    workers = max(1, min(all_cpu_workers(workers), len(core.TF_ORDER) - 1))
    data = {'1m': list(base)}
    tfs = [tf for tf in core.TF_ORDER if tf != '1m']
    started = time.perf_counter()
    ctx = mp.get_context('spawn')
    if show_progress:
        print(f'Building {len(core.TF_ORDER)}-timeframe dataset with up to {workers} CPU workers...', flush=True)
        print('\r  Timeframes:  1/30    3.3%  current=1m'.ljust(110), end='', flush=True)

    with ProcessPoolExecutor(
        max_workers=workers,
        mp_context=ctx,
        initializer=_resample_init,
        initargs=(base,),
    ) as pool:
        futures = {pool.submit(_resample_one, tf): tf for tf in tfs}
        done = 1
        for fut in as_completed(futures):
            tf, bars = fut.result()
            data[tf] = bars
            done += 1
            if show_progress:
                elapsed = time.perf_counter() - started
                pct = 100.0 * done / len(core.TF_ORDER)
                print(
                    '\r' + f'  Timeframes: {done:2d}/{len(core.TF_ORDER)}  {pct:5.1f}%  current={tf:<3}  elapsed={_fmt_seconds(elapsed)}  workers={workers}'.ljust(110),
                    end='', flush=True,
                )
    if show_progress:
        print()
    return {tf: data[tf] for tf in core.TF_ORDER}


def _replay_job(
    kind: str,
    base,
    shared_data,
    analysis_cache,
    equity: float,
    fee_bps: float,
    slippage_bps: float,
    leverage: float,
    gross_cap_x: float,
    portfolio_margin_pct: float,
):
    """Run one deterministic replay in its own process.

    BASE and GUARDED are independent once the shared historical TA cache exists,
    so running them simultaneously uses two CPU cores without changing either
    strategy's chronological state transitions.
    """
    core.LEVERAGE = float(leverage)
    portfolio_cap.PORTFOLIO_GROSS_NOTIONAL_X = float(gross_cap_x)
    portfolio_cap.PORTFOLIO_MARGIN_USE_PCT = float(portfolio_margin_pct)
    portfolio_cap.install()
    cls = core.Backtester if kind == 'base' else GuardedBacktester
    bt = progress._construct_with_shared_data(cls, base, shared_data, equity, fee_bps, slippage_bps)
    report = progress.run_with_progress(
        bt,
        'BASE v2.4' if kind == 'base' else 'GUARDED v2.4',
        show_progress=False,
        analysis_cache=analysis_cache,
    )
    return kind, report


def run_compare_replays_parallel(
    base,
    shared_data,
    analysis_cache,
    equity: float,
    fee_bps: float,
    slippage_bps: float,
    leverage: float,
    gross_cap_x: float,
    portfolio_margin_pct: float,
    show_progress: bool = True,
):
    """Run BASE and GUARDED concurrently and return both reports."""
    ctx = mp.get_context('spawn')
    started = time.perf_counter()
    reports = {}
    if show_progress:
        print(
            'Running BASE + GUARDED concurrently on 2 dedicated replay processes. '
            'Each replay remains strictly time-ordered.',
            flush=True,
        )

    with ProcessPoolExecutor(max_workers=2, mp_context=ctx) as pool:
        futures = {
            pool.submit(
                _replay_job,
                kind,
                base,
                shared_data,
                analysis_cache,
                equity,
                fee_bps,
                slippage_bps,
                leverage,
                gross_cap_x,
                portfolio_margin_pct,
            ): kind
            for kind in ('base', 'guarded')
        }
        pending = set(futures)
        last_print = 0.0
        while pending:
            done, _ = wait(pending, timeout=0.75, return_when=FIRST_COMPLETED)
            now = time.perf_counter()
            if show_progress and not done and now - last_print >= 0.75:
                last_print = now
                active = ', '.join(futures[f].upper() for f in pending)
                print(
                    '\r' + f'[PARALLEL REPLAY] elapsed={_fmt_seconds(now - started)}  active={active}'.ljust(120),
                    end='', flush=True,
                )
            for fut in done:
                pending.remove(fut)
                kind, report = fut.result()
                reports[kind] = report
                if show_progress:
                    print(
                        '\r' + f'[PARALLEL REPLAY] {kind.upper()} finished in {_fmt_seconds(time.perf_counter() - started)}'.ljust(120),
                        flush=True,
                    )

    return reports


def _save_and_print(kind: str, report: dict, out: Path):
    folder = 'base' if kind == 'base' else 'guarded'
    label = 'BASE' if kind == 'base' else 'GUARDED'
    j, c = core.save_report(report, out / folder)
    print(f'{label} result:')
    print(json.dumps(progress._summary(report), indent=2))
    print(f'Report: {j}\nTrades: {c}\n', flush=True)


def self_test() -> int:
    from tempfile import TemporaryDirectory
    from backtest_self_test import synthetic

    logical = max(1, int(os.cpu_count() or 1))
    assert all_cpu_workers(0) == logical
    assert all_cpu_workers(logical + 99) == logical

    with TemporaryDirectory() as td:
        p = Path(td) / 'tiny.csv'
        rows = synthetic(220)
        with p.open('w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['Open time', 'Open', 'High', 'Low', 'Close', 'Volume'])
            for b in rows:
                w.writerow([b['t'], b['o'], b['h'], b['l'], b['c'], b.get('v', 0)])
        start_ms, end_ms, layout = resolve_time_range_fast(p, None, None, 1)
        a = load_1m_parallel(p, start_ms, end_ms, min(2, logical), layout, show_progress=False)
        b = core.load_1m_csv(p, start_ms, end_ms)
        assert len(a) == len(b)
        assert [x['t'] for x in a] == [x['t'] for x in b]
        ds_parallel = build_dataset_parallel(a, min(2, logical), show_progress=False)
        ds_serial = core.build_dataset(a)
        assert {tf: len(ds_parallel[tf]) for tf in core.TF_ORDER} == {tf: len(ds_serial[tf]) for tf in core.TF_ORDER}

        # Exercise the same spawn-based concurrent replay path used on Windows.
        cache = progress.build_analysis_cache_parallel(ds_parallel, workers=min(2, logical), show_progress=False)
        reports = run_compare_replays_parallel(
            a, ds_parallel, cache, 1000.0, 6.0, 1.0, 30.0, 3.15, 45.0,
            show_progress=False,
        )
        assert set(reports) == {'base', 'guarded'}
        assert reports['base']['start_equity'] == 1000.0
        assert reports['guarded']['start_equity'] == 1000.0

    print(
        f'FULL CPU SELF TEST OK: parallel CSV load + resample + TA + concurrent replays, '
        f'logical CPUs={logical}'
    )
    return 0


def main():
    ap = argparse.ArgumentParser(description='Terminal 3 v2.4 maximum-use CPU comparison runner')
    ap.add_argument('csv', nargs='?', help='1-minute BTC OHLCV CSV or ZIP containing one CSV')
    ap.add_argument('--equity', type=float, default=1000)
    ap.add_argument('--fee-bps', type=float, default=6.0)
    ap.add_argument('--slippage-bps', type=float, default=1.0)
    ap.add_argument('--start', default=None)
    ap.add_argument('--end', default=None)
    ap.add_argument('--last-days', type=float, default=180.0)
    ap.add_argument('--out', default='backtest_results')
    ap.add_argument('--mode', choices=['base', 'guarded', 'compare'], default='compare')
    ap.add_argument('--leverage', type=float, default=30.0)
    ap.add_argument('--gross-cap-x', type=float, default=3.15)
    ap.add_argument('--portfolio-margin-pct', type=float, default=45.0)
    ap.add_argument('--workers', type=int, default=0, help='0=all logical CPUs')
    ap.add_argument('--serial-replays', action='store_true', help='debug option: do not run BASE/GUARDED concurrently')
    ap.add_argument('--self-test', action='store_true')
    a = ap.parse_args()

    if a.self_test:
        raise SystemExit(self_test())
    if not a.csv:
        ap.error('csv path is required')
    if not (1.0 <= a.leverage <= 30.0):
        ap.error('--leverage must be between 1x and 30x')
    if not (0.1 <= a.gross_cap_x <= 10.0):
        ap.error('--gross-cap-x must be between 0.1x and 10x')
    if not (1.0 <= a.portfolio_margin_pct <= 100.0):
        ap.error('--portfolio-margin-pct must be between 1 and 100')
    if a.workers < 0:
        ap.error('--workers must be 0 or a positive integer')

    workers = all_cpu_workers(a.workers)
    core.LEVERAGE = float(a.leverage)
    portfolio_cap.PORTFOLIO_GROSS_NOTIONAL_X = float(a.gross_cap_x)
    portfolio_cap.PORTFOLIO_MARGIN_USE_PCT = float(a.portfolio_margin_pct)

    path = Path(a.csv)
    print(
        f'MAXIMUM USE MODE: {workers} worker processes / {os.cpu_count() or 1} logical CPUs available. '
        'All safely parallelizable work will use them.',
        flush=True,
    )

    range_started = time.perf_counter()
    if path.suffix.lower() == '.csv':
        print('Reading CSV first/last timestamps directly (no full-file scan)...', flush=True)
    else:
        print('Scanning compressed data range (ZIP decompression itself is serial)...', flush=True)
    start_ms, end_ms, layout = resolve_time_range_fast(path, a.start, a.end, a.last_days)
    print(f'Data range resolved in {_fmt_seconds(time.perf_counter() - range_started)}.', flush=True)

    load_started = time.perf_counter()
    base = load_1m_parallel(path, start_ms, end_ms, workers, layout, show_progress=True)
    print(f'Loaded {len(base):,} selected candles in {_fmt_seconds(time.perf_counter() - load_started)}.', flush=True)

    print(
        f'Risk envelope: leverage={core.LEVERAGE:.0f}x, '
        f'gross cap={portfolio_cap.PORTFOLIO_GROSS_NOTIONAL_X:.2f}x equity, '
        f'margin budget={portfolio_cap.PORTFOLIO_MARGIN_USE_PCT:.0f}%, '
        f'effective cap={portfolio_cap.effective_gross_cap_x():.2f}x equity.',
        flush=True,
    )

    shared_data = build_dataset_parallel(base, workers, show_progress=True)
    analysis_cache = progress.build_analysis_cache_parallel(shared_data, workers=workers, show_progress=True)
    out = Path(a.out)

    if a.mode == 'compare' and not a.serial_replays:
        reports = run_compare_replays_parallel(
            base,
            shared_data,
            analysis_cache,
            a.equity,
            a.fee_bps,
            a.slippage_bps,
            core.LEVERAGE,
            portfolio_cap.PORTFOLIO_GROSS_NOTIONAL_X,
            portfolio_cap.PORTFOLIO_MARGIN_USE_PCT,
            show_progress=True,
        )
        _save_and_print('base', reports['base'], out)
        _save_and_print('guarded', reports['guarded'], out)
        return

    if a.mode in {'base', 'compare'}:
        base_bt = progress._construct_with_shared_data(core.Backtester, base, shared_data, a.equity, a.fee_bps, a.slippage_bps)
        base_report = progress.run_with_progress(base_bt, 'BASE v2.4', analysis_cache=analysis_cache)
        _save_and_print('base', base_report, out)

    if a.mode in {'guarded', 'compare'}:
        guard_bt = progress._construct_with_shared_data(GuardedBacktester, base, shared_data, a.equity, a.fee_bps, a.slippage_bps)
        guard_report = progress.run_with_progress(guard_bt, 'GUARDED v2.4', analysis_cache=analysis_cache)
        _save_and_print('guarded', guard_report, out)


if __name__ == '__main__':
    mp.freeze_support()
    main()
