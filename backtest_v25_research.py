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
import portfolio_cap
from backtest_full_cpu_runner import all_cpu_workers, load_1m_parallel, resolve_time_range_fast
from backtest_oos_v242 import _fmt_seconds, iso_ms, plan_windows, summarize_reports
from backtest_v25 import V25Backtester, V25_CONFIG


class ResearchV25Backtester(V25Backtester):
    """v2.5 candidate with a no-trade warm-up before each research window."""

    def __init__(self, base, evaluation_start_ms: int, *args, **kwargs):
        self.evaluation_start_ms = int(evaluation_start_ms)
        super().__init__(base, *args, **kwargs)
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


def _slice_rows(rows: list[dict], start_ms: int, end_ms: int) -> list[dict]:
    return [b for b in rows if start_ms <= int(b['t']) <= end_ms]


def _window_job(spec, base_slice, equity, fee_bps, slippage_bps,
                leverage, gross_cap_x, portfolio_margin_pct):
    core.LEVERAGE = float(leverage)
    portfolio_cap.PORTFOLIO_GROSS_NOTIONAL_X = float(gross_cap_x)
    portfolio_cap.PORTFOLIO_MARGIN_USE_PCT = float(portfolio_margin_pct)
    portfolio_cap.install()

    bt = ResearchV25Backtester(
        base_slice,
        evaluation_start_ms=int(spec['eval_start_ms']),
        equity=equity,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
    )
    r = bt.run()
    r.update({
        'oos_window_id': int(spec['window_id']),
        'oos_eval_start_ms': int(spec['eval_start_ms']),
        'oos_eval_end_ms': int(spec['eval_end_ms']),
        'oos_eval_start': spec['eval_start'],
        'oos_eval_end': spec['eval_end'],
        'oos_warmup_start': spec['warmup_start'],
        'v25_research_config': {
            'candidate': 'v2.5B',
            'min_entry_timeframe_minutes': V25_CONFIG.min_entry_timeframe_minutes,
            'max_round_trip_cost_r': V25_CONFIG.max_round_trip_cost_r,
            'min_net_target_r': 1.50,
            'fee_bps_per_side': fee_bps,
            'slippage_bps_per_side': slippage_bps,
            'leverage': leverage,
            'gross_cap_x': gross_cap_x,
            'portfolio_margin_pct': portfolio_margin_pct,
        },
        'research_status': 'INSPECTED RESEARCH WINDOWS - NOT BLIND HOLDOUT',
    })
    return int(spec['window_id']), r


def main() -> int:
    overall_started = time.perf_counter()
    ap = argparse.ArgumentParser(description='Terminal 3 v2.5B 14-window research battery')
    ap.add_argument('csv')
    ap.add_argument('--windows', type=int, default=14)
    ap.add_argument('--window-days', type=int, default=180)
    ap.add_argument('--skip-recent-days', type=int, default=180)
    ap.add_argument('--warmup-days', type=int, default=60)
    ap.add_argument('--equity', type=float, default=1000.0)
    ap.add_argument('--fee-bps', type=float, default=6.0)
    ap.add_argument('--slippage-bps', type=float, default=1.0)
    ap.add_argument('--leverage', type=float, default=30.0)
    ap.add_argument('--gross-cap-x', type=float, default=3.15)
    ap.add_argument('--portfolio-margin-pct', type=float, default=45.0)
    ap.add_argument('--workers', type=int, default=0)
    ap.add_argument('--out', default='backtest_results_v25_research_2h')
    a = ap.parse_args()

    if a.windows != 14:
        ap.error('v2.5 research battery is locked to exactly 14 inspected windows')
    if not (1 <= a.leverage <= 30):
        ap.error('--leverage must be between 1x and 30x')

    path = Path(a.csv)
    _, last_open_ms, layout = resolve_time_range_fast(path, None, None, None)
    if last_open_ms is None:
        if layout is not None:
            last_open_ms = int(layout[4])
        else:
            _, last_open_ms = core.scan_time_bounds(path)

    specs = plan_windows(
        int(last_open_ms), windows=14, window_days=180,
        skip_recent_days=180, warmup_days=a.warmup_days,
    )
    # The next older 180-day interval is deliberately not planned or loaded.
    # It remains reserved for one final blind check if a candidate becomes
    # materially stronger than breakeven on the inspected research corpus.
    earliest = min(int(s['warmup_start_ms']) for s in specs)
    latest = max(int(s['eval_end_ms']) for s in specs)
    workers = all_cpu_workers(a.workers)

    print('=' * 72)
    print('Terminal 3 v2.5B RESEARCH BATTERY')
    print('=' * 72)
    print('Single strategy change vs candidate A: entries must be 2h or higher.')
    print('Everything else remains v2.4.2 Efficient.')
    print('Research corpus: 14 already-inspected 180-day windows.')
    print('The older reserved holdout is NOT loaded by this runner.')
    print(f'CPU workers available: {workers}/{os.cpu_count() or 1}')
    print()

    load_started = time.perf_counter()
    rows = load_1m_parallel(path, earliest, latest, workers, layout, show_progress=True)
    load_seconds = time.perf_counter() - load_started
    print(f'Loaded {len(rows):,} shared 1m candles in {_fmt_seconds(load_seconds)}.')

    jobs = []
    for spec in specs:
        base_slice = _slice_rows(rows, int(spec['warmup_start_ms']), int(spec['eval_end_ms']))
        if len(base_slice) < 100:
            raise RuntimeError(f'window {spec["window_id"]} has insufficient data')
        jobs.append((spec, base_slice))
        print(f'Window {spec["window_id"]:02d}: {spec["eval_start"][:10]} -> {spec["eval_end"][:10]}')

    replay_workers = min(len(jobs), workers)
    reports = []
    replay_started = time.perf_counter()
    ctx = mp.get_context('spawn')
    print(f'\nRunning {len(jobs)} v2.5B windows with up to {replay_workers} concurrent processes...')
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
                print('\r' + f'[V25B] elapsed={_fmt_seconds(now-replay_started)} active={active}'.ljust(120), end='', flush=True)
            for fut in done:
                pending.remove(fut)
                wid, report = fut.result()
                reports.append(report)
                print('\r' + (
                    f'[V25B] W{wid:02d} return={report.get("return_pct",0):+.2f}% '
                    f'PF={report.get("profit_factor")} DD={report.get("max_drawdown_pct")}% '
                    f'trades={report.get("trades")} elapsed={_fmt_seconds(time.perf_counter()-replay_started)}'
                ).ljust(140), flush=True)

    replay_seconds = time.perf_counter() - replay_started
    summary = summarize_reports(reports)
    # summarize_reports is shared with v2.4.2 and carries its baseline label;
    # overwrite it so the saved summary cannot misidentify this candidate.
    summary['strategy'] = {
        'name': 'Terminal 3 v2.5B 2h-entry research candidate',
        'min_entry_timeframe_minutes': V25_CONFIG.min_entry_timeframe_minutes,
        'max_round_trip_cost_r': V25_CONFIG.max_round_trip_cost_r,
        'min_net_target_r': 1.50,
        'fee_bps_per_side': a.fee_bps,
        'slippage_bps_per_side': a.slippage_bps,
        'leverage': a.leverage,
        'gross_cap_x': a.gross_cap_x,
        'portfolio_margin_pct': a.portfolio_margin_pct,
    }
    summary['candidate'] = 'Terminal 3 v2.5B 2h-entry research candidate'
    summary['research_status'] = 'NOT BLIND VALIDATION'
    summary['reserved_holdout_consumed'] = False
    summary['load_seconds'] = round(load_seconds, 3)
    summary['replay_elapsed_seconds'] = round(replay_seconds, 3)
    summary['elapsed_seconds'] = round(time.perf_counter() - overall_started, 3)

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for r in sorted(reports, key=lambda x: int(x['oos_window_id'])):
        core.save_report(r, out / f'window_{int(r["oos_window_id"]):02d}')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    (out / f'v25b_research_summary_{stamp}.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')

    print('\n' + '=' * 72)
    print('V2.5B RESEARCH BATTERY COMPLETE')
    print('=' * 72)
    print(json.dumps({k: v for k, v in summary.items() if k != 'windows'}, indent=2))
    print(f'\nResults folder: {out}')
    return 0


if __name__ == '__main__':
    mp.freeze_support()
    raise SystemExit(main())
