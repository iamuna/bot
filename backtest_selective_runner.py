from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path

import backtest_v24 as core
import backtest_progress_runner as progress
import portfolio_cap
from backtest_full_cpu_runner import (
    all_cpu_workers,
    build_dataset_parallel,
    load_1m_parallel,
    resolve_time_range_fast,
)
from backtest_v24_guarded import GuardedBacktester
from backtest_v24_selective import SelectiveBacktester

portfolio_cap.install()


def _fmt_seconds(seconds: float | None) -> str:
    return progress._fmt_seconds(seconds)


def _construct(kind: str, base, shared_data, equity, fee_bps, slippage_bps):
    cls = GuardedBacktester if kind == 'guarded' else SelectiveBacktester
    return progress._construct_with_shared_data(
        cls, base, shared_data, equity, fee_bps, slippage_bps
    )


def _replay_job(kind, base, shared_data, analysis_cache, equity, fee_bps,
                slippage_bps, leverage, gross_cap_x, portfolio_margin_pct):
    core.LEVERAGE = float(leverage)
    portfolio_cap.PORTFOLIO_GROSS_NOTIONAL_X = float(gross_cap_x)
    portfolio_cap.PORTFOLIO_MARGIN_USE_PCT = float(portfolio_margin_pct)
    portfolio_cap.install()
    bt = _construct(kind, base, shared_data, equity, fee_bps, slippage_bps)
    label = 'GUARDED v2.4 CONTROL' if kind == 'guarded' else 'SELECTIVE v2.4.1'
    report = progress.run_with_progress(
        bt, label, show_progress=False, analysis_cache=analysis_cache
    )
    return kind, report


def _summary(report: dict) -> dict:
    keys = [
        'engine', 'status', 'bankrupt', 'processed_pct', 'start_equity',
        'end_equity', 'return_pct', 'trades', 'win_rate_pct', 'profit_factor',
        'max_drawdown_pct', 'avg_r', 'fees_paid', 'rejections', 'peak_equity',
        'profit_giveback_pct', 'cost_rejections', 'risk_throttled_entries',
        'max_loss_streak', 'selective_cost_rejections',
        'drawdown_lock_rejections', 'edge_throttled_entries',
        'drawdown_throttled_entries', 'selective_opened_entries',
        'max_start_drawdown_pct_selective', 'max_peak_drawdown_pct_selective',
        'portfolio_cap_rejections', 'portfolio_cap_scaled_entries',
        'max_gross_notional_x_equity', 'max_margin_used_pct',
    ]
    return {k: report.get(k) for k in keys if k in report}


def _save(kind: str, report: dict, out: Path):
    folder = out / ('guarded_control' if kind == 'guarded' else 'selective')
    return core.save_report(report, folder)


def run_replays(base, shared_data, cache, args):
    kinds = ['guarded', 'selective'] if args.mode == 'compare' else [args.mode]
    ctx = mp.get_context('spawn')
    reports = {}
    started = time.perf_counter()
    print(
        f'Running {" + ".join(k.upper() for k in kinds)} concurrently '
        f'on {len(kinds)} chronological replay process(es).',
        flush=True,
    )
    with ProcessPoolExecutor(max_workers=len(kinds), mp_context=ctx) as pool:
        futures = {
            pool.submit(
                _replay_job, kind, base, shared_data, cache,
                args.equity, args.fee_bps, args.slippage_bps,
                args.leverage, args.gross_cap_x, args.portfolio_margin_pct,
            ): kind
            for kind in kinds
        }
        pending = set(futures)
        last = 0.0
        while pending:
            done, _ = wait(pending, timeout=.75, return_when=FIRST_COMPLETED)
            now = time.perf_counter()
            if not done and now - last >= .75:
                last = now
                active = ', '.join(futures[f].upper() for f in pending)
                print(
                    '\r' + f'[REPLAY] elapsed={_fmt_seconds(now-started)} active={active}'.ljust(120),
                    end='', flush=True,
                )
            for fut in done:
                pending.remove(fut)
                kind, report = fut.result()
                reports[kind] = report
                print(
                    '\r' + f'[REPLAY] {kind.upper()} finished at {_fmt_seconds(time.perf_counter()-started)}'.ljust(120),
                    flush=True,
                )
    return reports


def main():
    ap = argparse.ArgumentParser(
        description='Terminal 3 guarded-control vs selective v2.4.1 full-CPU research runner'
    )
    ap.add_argument('csv')
    ap.add_argument('--equity', type=float, default=1000.0)
    ap.add_argument('--fee-bps', type=float, default=6.0)
    ap.add_argument('--slippage-bps', type=float, default=1.0)
    ap.add_argument('--start', default=None)
    ap.add_argument('--end', default=None)
    ap.add_argument('--last-days', type=float, default=180.0)
    ap.add_argument('--out', default='backtest_results_selective')
    ap.add_argument('--mode', choices=['guarded', 'selective', 'compare'], default='compare')
    ap.add_argument('--leverage', type=float, default=30.0)
    ap.add_argument('--gross-cap-x', type=float, default=3.15)
    ap.add_argument('--portfolio-margin-pct', type=float, default=45.0)
    ap.add_argument('--workers', type=int, default=0, help='0=all logical CPUs')
    a = ap.parse_args()

    if not (1 <= a.leverage <= 30):
        ap.error('--leverage must be between 1x and 30x')
    if a.workers < 0:
        ap.error('--workers must be 0 or positive')

    workers = all_cpu_workers(a.workers)
    core.LEVERAGE = float(a.leverage)
    portfolio_cap.PORTFOLIO_GROSS_NOTIONAL_X = float(a.gross_cap_x)
    portfolio_cap.PORTFOLIO_MARGIN_USE_PCT = float(a.portfolio_margin_pct)

    path = Path(a.csv)
    print('=' * 64)
    print('Terminal 3 v2.4.1 Selective Repair Test')
    print('GUARDED CONTROL vs SELECTIVE candidate')
    print('=' * 64)
    print(f'Full CPU workers: {workers}/{os.cpu_count() or 1}')
    print(f'Window: most recent {a.last_days:g} days in the data file')
    print(f'Costs: {a.fee_bps:g} bps fee + {a.slippage_bps:g} bp slippage per side')
    print(f'Leverage: {a.leverage:g}x; aggregate gross cap: {a.gross_cap_x:g}x equity')
    print('Selective: max modeled round-trip cost=0.20R, min net target=1.50R,')
    print('           rolling past-trade edge sizing, 15% new-risk drawdown lock.')
    print('This is a research candidate, not a profitability claim.')
    print()

    t0 = time.perf_counter()
    start_ms, end_ms, layout = resolve_time_range_fast(
        path, a.start, a.end, a.last_days
    )
    print(f'Range resolved in {_fmt_seconds(time.perf_counter()-t0)}.')

    t0 = time.perf_counter()
    base = load_1m_parallel(
        path, start_ms, end_ms, workers, layout, show_progress=True
    )
    print(f'Loaded {len(base):,} candles in {_fmt_seconds(time.perf_counter()-t0)}.')

    shared_data = build_dataset_parallel(base, workers, show_progress=True)
    cache = progress.build_analysis_cache_parallel(
        shared_data, workers=workers, show_progress=True
    )

    reports = run_replays(base, shared_data, cache, a)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    comparison = {}
    for kind in ('guarded', 'selective'):
        if kind not in reports:
            continue
        report = reports[kind]
        j, c = _save(kind, report, out)
        comparison[kind] = _summary(report)
        print(f'\n{kind.upper()} RESULT')
        print(json.dumps(comparison[kind], indent=2))
        print(f'Report: {j}')
        print(f'Trades: {c}')

    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    compare_path = out / f'v241_selective_comparison_{stamp}.json'
    compare_path.write_text(json.dumps(comparison, indent=2), encoding='utf-8')
    print(f'\nComparison summary: {compare_path}')


if __name__ == '__main__':
    mp.freeze_support()
    main()
