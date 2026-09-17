from __future__ import annotations

import argparse
import csv
import json
import math
import multiprocessing as mp
import os
import statistics
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path

import backtest_v24 as core
import portfolio_cap
from backtest_full_cpu_runner import all_cpu_workers, load_1m_parallel, resolve_time_range_fast
from backtest_v24_efficient import EfficientBacktester, EfficientConfig

DAY_MS = 86_400_000
MINUTE_MS = 60_000

# This battery intentionally freezes the strategy that survived the tuned
# Apr-Oct 2025 research window. No parameter sweep is performed here.
FROZEN_STRATEGY = {
    'name': 'Terminal 3 v2.4.2 Efficient',
    'min_entry_timeframe_minutes': 15,
    'max_round_trip_cost_r': 0.16,
    'min_net_target_r': 1.50,
    'fee_bps_per_side': 6.0,
    'slippage_bps_per_side': 1.0,
    'leverage': 30.0,
    'gross_cap_x': 3.15,
    'portfolio_margin_pct': 45.0,
}


def _fmt_seconds(seconds: float | None) -> str:
    if seconds is None or seconds < 0 or not math.isfinite(seconds):
        return '--:--'
    seconds = int(seconds + 0.5)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f'{h:d}:{m:02d}:{s:02d}' if h else f'{m:02d}:{s:02d}'


def iso_ms(t: int) -> str:
    return datetime.fromtimestamp(t / 1000, tz=timezone.utc).isoformat()


def plan_windows(
    last_open_ms: int,
    windows: int = 8,
    window_days: int = 180,
    skip_recent_days: int = 180,
    warmup_days: int = 60,
) -> list[dict]:
    """Plan contiguous, non-overlapping OOS windows before the tuned period.

    The latest `skip_recent_days` are excluded completely because v2.4.2 was
    developed using that period. Every OOS window resets to the same starting
    equity. Warm-up candles are processed with trading disabled so indicators
    can initialize without leaking PnL into the evaluation interval.
    """
    if windows < 1 or window_days < 1 or skip_recent_days < 0 or warmup_days < 0:
        raise ValueError('invalid OOS window parameters')

    tuned_start = int(last_open_ms) - int(skip_recent_days * DAY_MS)
    out = []
    next_end = tuned_start - MINUTE_MS
    for i in range(windows):
        eval_end = next_end
        eval_start = eval_end - int(window_days * DAY_MS) + MINUTE_MS
        warmup_start = eval_start - int(warmup_days * DAY_MS)
        out.append({
            'window_id': i + 1,
            'eval_start_ms': eval_start,
            'eval_end_ms': eval_end,
            'warmup_start_ms': warmup_start,
            'eval_start': iso_ms(eval_start),
            'eval_end': iso_ms(eval_end),
            'warmup_start': iso_ms(warmup_start),
        })
        next_end = eval_start - MINUTE_MS
    return out


class OOSEfficientBacktester(EfficientBacktester):
    """Frozen v2.4.2 with a no-trade indicator warm-up interval."""

    def __init__(self, base, evaluation_start_ms: int, *args, **kwargs):
        self.evaluation_start_ms = int(evaluation_start_ms)
        super().__init__(*args, base=base, **kwargs)
        self.warmup_entry_blocks = 0

    def _open_candidate(self, c, bar):
        if int(bar['t']) < self.evaluation_start_ms:
            self.warmup_entry_blocks += 1
            return
        return super()._open_candidate(c, bar)

    def report(self):
        r = super().report()
        r['oos_evaluation_start_ms'] = self.evaluation_start_ms
        r['oos_evaluation_start'] = iso_ms(self.evaluation_start_ms)
        r['warmup_entry_blocks'] = self.warmup_entry_blocks
        return r


def _window_job(
    spec: dict,
    base_slice: list[dict],
    equity: float,
    fee_bps: float,
    slippage_bps: float,
    leverage: float,
    gross_cap_x: float,
    portfolio_margin_pct: float,
) -> tuple[int, dict]:
    # Each OOS window is an independent experiment. Strategy and execution
    # assumptions are identical for every worker.
    core.LEVERAGE = float(leverage)
    portfolio_cap.PORTFOLIO_GROSS_NOTIONAL_X = float(gross_cap_x)
    portfolio_cap.PORTFOLIO_MARGIN_USE_PCT = float(portfolio_margin_pct)
    portfolio_cap.install()

    bt = OOSEfficientBacktester(
        base_slice,
        evaluation_start_ms=int(spec['eval_start_ms']),
        equity=equity,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        efficient=EfficientConfig(
            min_entry_timeframe_minutes=15,
            max_round_trip_cost_r=0.16,
        ),
    )
    report = bt.run()
    report.update({
        'oos_window_id': int(spec['window_id']),
        'oos_eval_start_ms': int(spec['eval_start_ms']),
        'oos_eval_end_ms': int(spec['eval_end_ms']),
        'oos_eval_start': spec['eval_start'],
        'oos_eval_end': spec['eval_end'],
        'oos_warmup_start': spec['warmup_start'],
        'oos_frozen_strategy': FROZEN_STRATEGY,
    })
    return int(spec['window_id']), report


def _slice_rows(rows: list[dict], start_ms: int, end_ms: int) -> list[dict]:
    return [b for b in rows if start_ms <= int(b['t']) <= end_ms]


def summarize_reports(reports: list[dict]) -> dict:
    ordered = sorted(reports, key=lambda r: int(r['oos_window_id']))
    all_trades = [t for r in ordered for t in r.get('trades_detail', [])]
    wins = [t for t in all_trades if float(t.get('pnl') or 0) > 0]
    losses = [t for t in all_trades if float(t.get('pnl') or 0) < 0]
    gp = sum(float(t['pnl']) for t in wins)
    gl = -sum(float(t['pnl']) for t in losses)
    returns = [float(r.get('return_pct') or 0) for r in ordered]
    dds = [float(r.get('max_drawdown_pct') or 0) for r in ordered]
    pnls = [float(r.get('net_pnl') or 0) for r in ordered]
    rs = [float(t.get('r') or 0) for t in all_trades]

    return {
        'strategy': FROZEN_STRATEGY,
        'window_count': len(ordered),
        'positive_windows': sum(x > 0 for x in returns),
        'negative_windows': sum(x < 0 for x in returns),
        'flat_windows': sum(x == 0 for x in returns),
        'sum_independent_net_pnl': round(sum(pnls), 2),
        'mean_return_pct': round(statistics.mean(returns), 3) if returns else 0.0,
        'median_return_pct': round(statistics.median(returns), 3) if returns else 0.0,
        'best_window_return_pct': round(max(returns), 3) if returns else 0.0,
        'worst_window_return_pct': round(min(returns), 3) if returns else 0.0,
        'max_window_drawdown_pct': round(max(dds), 3) if dds else 0.0,
        'median_window_drawdown_pct': round(statistics.median(dds), 3) if dds else 0.0,
        'pooled_trades': len(all_trades),
        'pooled_wins': len(wins),
        'pooled_losses': len(losses),
        'pooled_win_rate_pct': round(100 * len(wins) / len(all_trades), 3) if all_trades else 0.0,
        'pooled_profit_factor': round(gp / gl, 4) if gl > 0 else None,
        'pooled_avg_r': round(statistics.mean(rs), 4) if rs else 0.0,
        'total_fees_paid': round(sum(float(r.get('fees_paid') or 0) for r in ordered), 2),
        'windows': [
            {
                'window_id': int(r['oos_window_id']),
                'eval_start': r['oos_eval_start'],
                'eval_end': r['oos_eval_end'],
                'end_equity': r.get('end_equity'),
                'return_pct': r.get('return_pct'),
                'trades': r.get('trades'),
                'win_rate_pct': r.get('win_rate_pct'),
                'profit_factor': r.get('profit_factor'),
                'max_drawdown_pct': r.get('max_drawdown_pct'),
                'avg_r': r.get('avg_r'),
                'fees_paid': r.get('fees_paid'),
                'peak_equity': r.get('peak_equity'),
            }
            for r in ordered
        ],
    }


def save_battery(reports: list[dict], summary: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for r in sorted(reports, key=lambda x: int(x['oos_window_id'])):
        wid = int(r['oos_window_id'])
        core.save_report(r, out / f'window_{wid:02d}')

    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    (out / f'v242_oos_summary_{stamp}.json').write_text(
        json.dumps(summary, indent=2), encoding='utf-8'
    )
    csv_path = out / f'v242_oos_windows_{stamp}.csv'
    fields = [
        'window_id', 'eval_start', 'eval_end', 'end_equity', 'return_pct',
        'trades', 'win_rate_pct', 'profit_factor', 'max_drawdown_pct',
        'avg_r', 'fees_paid', 'peak_equity',
    ]
    with csv_path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(summary['windows'])


def main() -> int:
    ap = argparse.ArgumentParser(description='Frozen Terminal 3 v2.4.2 multi-window OOS battery')
    ap.add_argument('csv', help='BTC 1-minute CSV or ZIP containing one CSV')
    ap.add_argument('--windows', type=int, default=8)
    ap.add_argument('--window-days', type=int, default=180)
    ap.add_argument('--skip-recent-days', type=int, default=180,
                    help='exclude the tuned recent period from OOS evaluation')
    ap.add_argument('--warmup-days', type=int, default=60)
    ap.add_argument('--equity', type=float, default=1000.0)
    ap.add_argument('--fee-bps', type=float, default=6.0)
    ap.add_argument('--slippage-bps', type=float, default=1.0)
    ap.add_argument('--leverage', type=float, default=30.0)
    ap.add_argument('--gross-cap-x', type=float, default=3.15)
    ap.add_argument('--portfolio-margin-pct', type=float, default=45.0)
    ap.add_argument('--workers', type=int, default=0, help='0=auto; one replay worker per OOS window up to CPU count')
    ap.add_argument('--out', default='backtest_results_oos_v242')
    a = ap.parse_args()

    if a.windows < 1 or a.window_days < 1 or a.warmup_days < 0 or a.skip_recent_days < 0:
        ap.error('invalid window settings')
    if not (1 <= a.leverage <= 30):
        ap.error('--leverage must be between 1x and 30x')

    path = Path(a.csv)
    # Direct CSV range lookup is near-instant. ZIP uses the existing scan fallback.
    _, last_open_ms, layout = resolve_time_range_fast(path, None, None, None)
    if last_open_ms is None:
        # resolve_time_range_fast returns (None, None, layout) without an end
        # when no explicit range is requested, so use layout metadata for CSV.
        if layout is not None:
            last_open_ms = int(layout[4])
        else:
            _, last_open_ms = core.scan_time_bounds(path)

    specs = plan_windows(
        int(last_open_ms),
        windows=a.windows,
        window_days=a.window_days,
        skip_recent_days=a.skip_recent_days,
        warmup_days=a.warmup_days,
    )

    earliest = min(int(s['warmup_start_ms']) for s in specs)
    latest = max(int(s['eval_end_ms']) for s in specs)
    loader_workers = all_cpu_workers(a.workers)

    print('=' * 72)
    print('Terminal 3 v2.4.2 FROZEN OUT-OF-SAMPLE BATTERY')
    print('=' * 72)
    print(f'OOS windows: {a.windows} x {a.window_days} days')
    print(f'Excluded tuned period: latest {a.skip_recent_days} days')
    print(f'Indicator warm-up before each window: {a.warmup_days} days (no trading)')
    print(f'Execution costs: {a.fee_bps:g} bps fee + {a.slippage_bps:g} bp slippage per side')
    print('Strategy is frozen: >=15m entries, max round-trip cost 0.16R, no parameter sweep.')
    print(f'Loading shared historical span: {iso_ms(earliest)} -> {iso_ms(latest)}')
    print()

    t0 = time.perf_counter()
    rows = load_1m_parallel(path, earliest, latest, loader_workers, layout, show_progress=True)
    print(f'Loaded {len(rows):,} shared 1m candles in {_fmt_seconds(time.perf_counter() - t0)}.')

    jobs = []
    for spec in specs:
        base_slice = _slice_rows(rows, int(spec['warmup_start_ms']), int(spec['eval_end_ms']))
        if len(base_slice) < 100:
            raise RuntimeError(f'window {spec["window_id"]} has insufficient data')
        jobs.append((spec, base_slice))
        print(
            f'Window {spec["window_id"]:02d}: {spec["eval_start"][:10]} -> {spec["eval_end"][:10]} '
            f'({len(base_slice):,} candles incl. warm-up)'
        )

    replay_workers = min(len(jobs), max(1, all_cpu_workers(a.workers)))
    print(f'\nRunning {len(jobs)} independent OOS windows with up to {replay_workers} concurrent replay processes...')
    started = time.perf_counter()
    reports = []
    ctx = mp.get_context('spawn')
    with ProcessPoolExecutor(max_workers=replay_workers, mp_context=ctx) as pool:
        futures = {
            pool.submit(
                _window_job, spec, base_slice,
                a.equity, a.fee_bps, a.slippage_bps,
                a.leverage, a.gross_cap_x, a.portfolio_margin_pct,
            ): int(spec['window_id'])
            for spec, base_slice in jobs
        }
        pending = set(futures)
        last_print = 0.0
        while pending:
            done, _ = wait(pending, timeout=1.0, return_when=FIRST_COMPLETED)
            now = time.perf_counter()
            if not done and now - last_print >= 1.0:
                last_print = now
                active = ','.join(f'{futures[f]:02d}' for f in sorted(pending, key=lambda x: futures[x]))
                print(
                    '\r' + f'[OOS] elapsed={_fmt_seconds(now-started)} active windows={active}'.ljust(120),
                    end='', flush=True,
                )
            for fut in done:
                pending.remove(fut)
                wid, report = fut.result()
                reports.append(report)
                print(
                    '\r' + (
                        f'[OOS] window {wid:02d} complete: return={report.get("return_pct", 0):+.2f}% '
                        f'PF={report.get("profit_factor")} DD={report.get("max_drawdown_pct")}% '
                        f'trades={report.get("trades")} elapsed={_fmt_seconds(time.perf_counter()-started)}'
                    ).ljust(140),
                    flush=True,
                )

    summary = summarize_reports(reports)
    out = Path(a.out)
    save_battery(reports, summary, out)

    print('\n' + '=' * 72)
    print('OOS BATTERY COMPLETE')
    print('=' * 72)
    print(json.dumps({k: v for k, v in summary.items() if k != 'windows'}, indent=2))
    print('\nPer-window results:')
    for w in summary['windows']:
        print(
            f'  W{w["window_id"]:02d} {w["eval_start"][:10]}..{w["eval_end"][:10]}  '
            f'return={w["return_pct"]:+.2f}%  PF={w["profit_factor"]}  '
            f'DD={w["max_drawdown_pct"]:.2f}%  trades={w["trades"]}'
        )
    print(f'\nResults folder: {out}')
    return 0


if __name__ == '__main__':
    mp.freeze_support()
    raise SystemExit(main())
