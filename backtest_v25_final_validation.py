from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import backtest_v24 as core
import portfolio_cap
from backtest_full_cpu_runner import all_cpu_workers, load_1m_parallel, resolve_time_range_fast
from backtest_oos_v242 import DAY_MS, MINUTE_MS, iso_ms, plan_windows
from backtest_v25 import V25Backtester, V25_CONFIG


class FinalValidationBacktester(V25Backtester):
    """Frozen v2.5B with a no-trade warm-up before the validation interval."""

    def __init__(self, base, evaluation_start_ms: int, *args, **kwargs):
        self.evaluation_start_ms = int(evaluation_start_ms)
        self.warmup_entry_blocks = 0
        super().__init__(base, *args, **kwargs)

    def _open_candidate(self, c, bar):
        if int(bar['t']) < self.evaluation_start_ms:
            self.warmup_entry_blocks += 1
            return
        return super()._open_candidate(c, bar)

    def report(self):
        r = super().report()
        r.update({
            'validation_status': 'FINAL UNTOUCHED EARLY VALIDATION - NOT RESEARCH',
            'candidate_frozen': True,
            'evaluation_start_ms': self.evaluation_start_ms,
            'evaluation_start': iso_ms(self.evaluation_start_ms),
            'warmup_entry_blocks': self.warmup_entry_blocks,
        })
        return r


def main() -> int:
    overall_started = time.perf_counter()
    ap = argparse.ArgumentParser(description='Terminal 3 v2.5B final untouched early validation')
    ap.add_argument('csv')
    ap.add_argument('--warmup-days', type=int, default=90)
    ap.add_argument('--equity', type=float, default=1000.0)
    ap.add_argument('--fee-bps', type=float, default=6.0)
    ap.add_argument('--slippage-bps', type=float, default=1.0)
    ap.add_argument('--leverage', type=float, default=30.0)
    ap.add_argument('--gross-cap-x', type=float, default=3.15)
    ap.add_argument('--portfolio-margin-pct', type=float, default=45.0)
    ap.add_argument('--workers', type=int, default=0)
    ap.add_argument('--out', default='backtest_results_v25b_final_validation')
    a = ap.parse_args()

    # This protocol is intentionally locked. Changing warm-up length after
    # seeing the stability result would turn methodology into another tuning
    # parameter and invalidate the final validation boundary.
    if a.warmup_days != 90:
        ap.error('final validation is locked to the frozen 90-day warm-up')
    if not (1 <= a.leverage <= 30):
        ap.error('--leverage must be between 1x and 30x')

    path = Path(a.csv)
    _, last_open_ms, layout = resolve_time_range_fast(path, None, None, None)
    if layout is not None:
        first_open_ms = int(layout[3])
        last_open_ms = int(layout[4])
    else:
        first_open_ms, scanned_last = core.scan_time_bounds(path)
        if last_open_ms is None:
            last_open_ms = scanned_last

    if first_open_ms is None or last_open_ms is None:
        raise RuntimeError('Could not determine dataset boundaries')

    # Reconstruct the first timestamp ever consumed by the original v2.5B
    # 14-window/60-day research protocol. The final validation evaluation must
    # end strictly before this timestamp so none of its evaluation candles have
    # ever appeared in research, even as warm-up/context.
    research_specs = plan_windows(
        int(last_open_ms), windows=14, window_days=180,
        skip_recent_days=180, warmup_days=60,
    )
    research_floor_ms = min(int(s['warmup_start_ms']) for s in research_specs)

    eval_end_ms = research_floor_ms - MINUTE_MS
    eval_start_ms = int(first_open_ms) + a.warmup_days * DAY_MS
    warmup_start_ms = int(first_open_ms)

    if eval_start_ms >= eval_end_ms:
        raise RuntimeError(
            'Dataset does not contain enough untouched early history for the '
            'locked 90-day warm-up plus a validation interval.'
        )

    workers = all_cpu_workers(a.workers)
    print('=' * 76)
    print('Terminal 3 v2.5B FINAL UNTOUCHED EARLY VALIDATION')
    print('=' * 76)
    print('Strategy is frozen: 2h+ entries, unchanged costs/risk/exits/caps.')
    print('Warm-up methodology is frozen at 90 days.')
    print('No candle at or after the original v2.5 research-history boundary')
    print('is loaded by this validation run.')
    print(f'Dataset first candle:   {iso_ms(first_open_ms)}')
    print(f'Warm-up start:          {iso_ms(warmup_start_ms)}')
    print(f'Evaluation start:       {iso_ms(eval_start_ms)}')
    print(f'Evaluation end:         {iso_ms(eval_end_ms)}')
    print(f'Original research floor:{iso_ms(research_floor_ms)}')
    print(f'CPU workers: {workers}/{os.cpu_count() or 1}')
    print()

    load_started = time.perf_counter()
    rows = load_1m_parallel(
        path, warmup_start_ms, eval_end_ms, workers, layout,
        show_progress=True,
    )
    load_seconds = time.perf_counter() - load_started
    if len(rows) < 100:
        raise RuntimeError('Validation slice has insufficient data')
    if int(rows[0]['t']) < warmup_start_ms or int(rows[-1]['t']) > eval_end_ms:
        raise RuntimeError('Loaded rows escaped the locked validation boundary')
    if int(rows[-1]['t']) >= research_floor_ms:
        raise RuntimeError('Validation attempted to read research-era history')

    core.LEVERAGE = float(a.leverage)
    portfolio_cap.PORTFOLIO_GROSS_NOTIONAL_X = float(a.gross_cap_x)
    portfolio_cap.PORTFOLIO_MARGIN_USE_PCT = float(a.portfolio_margin_pct)
    portfolio_cap.install()

    replay_started = time.perf_counter()
    bt = FinalValidationBacktester(
        rows,
        evaluation_start_ms=eval_start_ms,
        equity=a.equity,
        fee_bps=a.fee_bps,
        slippage_bps=a.slippage_bps,
    )
    report = bt.run()
    replay_seconds = time.perf_counter() - replay_started

    report.update({
        'validation_status': 'FINAL UNTOUCHED EARLY VALIDATION - NOT RESEARCH',
        'candidate': 'Terminal 3 v2.5B 2h-entry candidate',
        'candidate_frozen': True,
        'warmup_days': a.warmup_days,
        'warmup_start_ms': warmup_start_ms,
        'warmup_start': iso_ms(warmup_start_ms),
        'evaluation_start_ms': eval_start_ms,
        'evaluation_start': iso_ms(eval_start_ms),
        'evaluation_end_ms': eval_end_ms,
        'evaluation_end': iso_ms(eval_end_ms),
        'original_research_floor_ms': research_floor_ms,
        'original_research_floor': iso_ms(research_floor_ms),
        'evaluation_overlap_with_research_history': False,
        'fee_bps_per_side': a.fee_bps,
        'slippage_bps_per_side': a.slippage_bps,
        'leverage': a.leverage,
        'gross_cap_x': a.gross_cap_x,
        'portfolio_margin_pct': a.portfolio_margin_pct,
        'load_seconds': round(load_seconds, 3),
        'replay_elapsed_seconds': round(replay_seconds, 3),
        'elapsed_seconds': round(time.perf_counter() - overall_started, 3),
    })

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    core.save_report(report, out)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    summary = {
        'candidate': report['candidate'],
        'validation_status': report['validation_status'],
        'candidate_frozen': True,
        'warmup_days': a.warmup_days,
        'warmup_start': report['warmup_start'],
        'evaluation_start': report['evaluation_start'],
        'evaluation_end': report['evaluation_end'],
        'original_research_floor': report['original_research_floor'],
        'evaluation_overlap_with_research_history': False,
        'start_equity': report.get('start_equity'),
        'end_equity': report.get('end_equity'),
        'return_pct': report.get('return_pct'),
        'net_pnl': report.get('net_pnl'),
        'trades': report.get('trades'),
        'wins': report.get('wins'),
        'losses': report.get('losses'),
        'win_rate_pct': report.get('win_rate_pct'),
        'profit_factor': report.get('profit_factor'),
        'max_drawdown_pct': report.get('max_drawdown_pct'),
        'avg_r': report.get('avg_r'),
        'fees_paid': report.get('fees_paid'),
        'peak_equity': report.get('peak_equity'),
        'liquidation_modeled': report.get('liquidation_modeled'),
        'load_seconds': report['load_seconds'],
        'replay_elapsed_seconds': report['replay_elapsed_seconds'],
        'elapsed_seconds': report['elapsed_seconds'],
    }
    (out / f'v25b_final_validation_summary_{stamp}.json').write_text(
        json.dumps(summary, indent=2), encoding='utf-8'
    )

    print('\n' + '=' * 76)
    print('V2.5B FINAL VALIDATION COMPLETE')
    print('=' * 76)
    print(json.dumps(summary, indent=2))
    print(f'\nResults folder: {out}')
    return 0


if __name__ == '__main__':
    mp.freeze_support()
    raise SystemExit(main())
