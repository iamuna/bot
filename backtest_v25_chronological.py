from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import backtest_v24 as core
import portfolio_cap
from backtest_full_cpu_runner import all_cpu_workers, load_1m_parallel, resolve_time_range_fast
from backtest_oos_v242 import DAY_MS, iso_ms
from backtest_v25 import V25Backtester


WARMUP_DAYS = 90
START_EQUITY = 1000.0
FEE_BPS = 6.0
SLIPPAGE_BPS = 1.0
LEVERAGE = 30.0
GROSS_CAP_X = 3.15
PORTFOLIO_MARGIN_PCT = 45.0


class ReplayProgressRows:
    """Read-only sequence wrapper that reports replay progress without changing bars."""

    def __init__(self, rows, *, label: str = 'CHRONOLOGICAL REPLAY', interval_s: float = 5.0):
        self._rows = rows
        self._label = label
        self._interval_s = max(0.5, float(interval_s))

    def __len__(self):
        return len(self._rows)

    def __getitem__(self, item):
        return self._rows[item]

    @staticmethod
    def _fmt_seconds(seconds: float) -> str:
        seconds = max(0, int(round(seconds)))
        hours, rem = divmod(seconds, 3600)
        minutes, secs = divmod(rem, 60)
        if hours:
            return f'{hours:02d}:{minutes:02d}:{secs:02d}'
        return f'{minutes:02d}:{secs:02d}'

    def __iter__(self):
        total = len(self._rows)
        started = time.perf_counter()
        last_print = started
        print(f'[{self._label}]   0.00% rows=0/{total:,} elapsed=00:00 ETA=calculating', flush=True)

        for index, row in enumerate(self._rows, 1):
            yield row
            now = time.perf_counter()
            if index != total and now - last_print < self._interval_s:
                continue

            elapsed = max(now - started, 1e-9)
            rate = index / elapsed
            eta = (total - index) / rate if rate > 0 else 0.0
            pct = 100.0 * index / max(total, 1)
            candle = iso_ms(int(row['t'])) if isinstance(row, dict) and 't' in row else '?'
            print(
                f'[{self._label}] {pct:6.2f}% rows={index:,}/{total:,} '
                f'elapsed={self._fmt_seconds(elapsed)} ETA={self._fmt_seconds(eta)} '
                f'candle={candle}',
                flush=True,
            )
            last_print = now


class ChronologicalBacktester(V25Backtester):
    """Frozen v2.5B with one initial warm-up and no later state resets."""

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
            'audit_status': 'CONTINUOUS CHRONOLOGICAL HISTORICAL AUDIT - NOT BLIND VALIDATION',
            'candidate_frozen': True,
            'evaluation_start_ms': self.evaluation_start_ms,
            'evaluation_start': iso_ms(self.evaluation_start_ms),
            'warmup_entry_blocks': self.warmup_entry_blocks,
        })
        return r


def summarize_by_year(report: dict) -> dict:
    """Summarize realized trades by UTC exit year for regime concentration checks."""
    out: dict[str, dict] = {}
    for trade in report.get('trades_detail') or []:
        t = int(trade.get('exit_t') or 0)
        year = str(datetime.fromtimestamp(t / 1000, tz=timezone.utc).year)
        d = out.setdefault(year, {
            'trades': 0,
            'wins': 0,
            'losses': 0,
            'net_pnl': 0.0,
            'fees': 0.0,
            'gross_profit': 0.0,
            'gross_loss': 0.0,
            'sum_r': 0.0,
            'first_exit_t': None,
            'last_exit_t': None,
        })
        pnl = float(trade.get('pnl') or 0.0)
        fees = float(trade.get('fees') or 0.0)
        r = float(trade.get('r') or 0.0)
        d['trades'] += 1
        d['wins'] += int(pnl > 0)
        d['losses'] += int(pnl < 0)
        d['net_pnl'] += pnl
        d['fees'] += fees
        d['sum_r'] += r
        if pnl > 0:
            d['gross_profit'] += pnl
        elif pnl < 0:
            d['gross_loss'] += -pnl
        d['first_exit_t'] = t if d['first_exit_t'] is None else min(d['first_exit_t'], t)
        d['last_exit_t'] = t if d['last_exit_t'] is None else max(d['last_exit_t'], t)

    for d in out.values():
        trades = int(d['trades'])
        gross_loss = float(d.pop('gross_loss'))
        gross_profit = float(d.pop('gross_profit'))
        d['win_rate_pct'] = round(100.0 * d['wins'] / trades, 2) if trades else 0.0
        d['profit_factor'] = round(gross_profit / gross_loss, 3) if gross_loss else None
        d['net_pnl'] = round(float(d['net_pnl']), 2)
        d['fees'] = round(float(d['fees']), 2)
        d['avg_r'] = round(float(d.pop('sum_r')) / trades, 3) if trades else 0.0
        d['first_exit'] = iso_ms(int(d.pop('first_exit_t'))) if d['first_exit_t'] is not None else None
        d['last_exit'] = iso_ms(int(d.pop('last_exit_t'))) if d['last_exit_t'] is not None else None
    return dict(sorted(out.items()))


def save_year_csv(by_year: dict, path: Path) -> None:
    fields = [
        'year', 'trades', 'wins', 'losses', 'win_rate_pct', 'profit_factor',
        'net_pnl', 'fees', 'avg_r', 'first_exit', 'last_exit',
    ]
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for year, row in by_year.items():
            w.writerow({'year': year, **{k: row.get(k) for k in fields if k != 'year'}})


def main() -> int:
    overall_started = time.perf_counter()
    ap = argparse.ArgumentParser(
        description='Terminal 3 v2.5B full-history continuous chronological audit'
    )
    ap.add_argument('csv', help='BTC 1-minute CSV')
    ap.add_argument('--workers', type=int, default=0, help='CSV load workers; 0=all logical CPUs')
    ap.add_argument('--out', default='backtest_results_v25b_chronological')
    a = ap.parse_args()
    if a.workers < 0:
        ap.error('--workers must be 0 (auto) or a positive integer')

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

    evaluation_start_ms = int(first_open_ms) + WARMUP_DAYS * DAY_MS
    if evaluation_start_ms >= int(last_open_ms):
        raise RuntimeError('Dataset is too short for the frozen 90-day warm-up')

    workers = all_cpu_workers(a.workers)
    print('=' * 80)
    print('Terminal 3 v2.5B CONTINUOUS CHRONOLOGICAL HISTORICAL AUDIT')
    print('=' * 80)
    print('This is NOT a blind validation run. The historical dataset is already consumed.')
    print('Strategy remains frozen; this audit checks continuous state without window resets.')
    print(f'Dataset first candle: {iso_ms(first_open_ms)}')
    print(f'Warm-up start:        {iso_ms(first_open_ms)}')
    print(f'Evaluation start:     {iso_ms(evaluation_start_ms)}')
    print(f'Dataset last candle:  {iso_ms(last_open_ms)}')
    print(f'Frozen settings: fee={FEE_BPS:g}bps/side slippage={SLIPPAGE_BPS:g}bps/side '
          f'leverage={LEVERAGE:g}x gross_cap={GROSS_CAP_X:g}x margin_budget={PORTFOLIO_MARGIN_PCT:g}%')
    print(f'CPU workers for CSV load: {workers}/{os.cpu_count() or 1}')
    print('Replay itself remains chronological/stateful and is not split across candles.')
    print()

    load_started = time.perf_counter()
    rows = load_1m_parallel(
        path, int(first_open_ms), int(last_open_ms), workers, layout,
        show_progress=True,
    )
    load_seconds = time.perf_counter() - load_started
    if int(rows[0]['t']) != int(first_open_ms):
        raise RuntimeError('Loaded history does not begin at the dataset boundary')
    if int(rows[-1]['t']) > int(last_open_ms):
        raise RuntimeError('Loaded history escaped the dataset boundary')

    core.LEVERAGE = LEVERAGE
    portfolio_cap.PORTFOLIO_GROSS_NOTIONAL_X = GROSS_CAP_X
    portfolio_cap.PORTFOLIO_MARGIN_USE_PCT = PORTFOLIO_MARGIN_PCT
    portfolio_cap.install()

    replay_started = time.perf_counter()
    bt = ChronologicalBacktester(
        rows,
        evaluation_start_ms=evaluation_start_ms,
        equity=START_EQUITY,
        fee_bps=FEE_BPS,
        slippage_bps=SLIPPAGE_BPS,
    )
    # Wrap only after initialization. This changes console output only; the
    # strategy receives the same rows in the same order and keeps one stateful
    # portfolio/TA sequence for the entire replay.
    bt.base = ReplayProgressRows(bt.base, label='CHRONOLOGICAL REPLAY', interval_s=5.0)
    report = bt.run()
    replay_seconds = time.perf_counter() - replay_started

    by_year = summarize_by_year(report)
    report.update({
        'audit_status': 'CONTINUOUS CHRONOLOGICAL HISTORICAL AUDIT - NOT BLIND VALIDATION',
        'candidate': 'Terminal 3 v2.5B 2h-entry candidate',
        'candidate_frozen': True,
        'historical_data_already_consumed': True,
        'warmup_days': WARMUP_DAYS,
        'warmup_start_ms': int(first_open_ms),
        'warmup_start': iso_ms(int(first_open_ms)),
        'evaluation_start_ms': evaluation_start_ms,
        'evaluation_start': iso_ms(evaluation_start_ms),
        'evaluation_end_ms': int(last_open_ms),
        'evaluation_end': iso_ms(int(last_open_ms)),
        'fee_bps_per_side': FEE_BPS,
        'slippage_bps_per_side': SLIPPAGE_BPS,
        'leverage': LEVERAGE,
        'gross_cap_x': GROSS_CAP_X,
        'portfolio_margin_pct': PORTFOLIO_MARGIN_PCT,
        'chronological_state_resets': 0,
        'by_year': by_year,
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
        'audit_status': report['audit_status'],
        'candidate_frozen': True,
        'historical_data_already_consumed': True,
        'warmup_days': WARMUP_DAYS,
        'warmup_start': report['warmup_start'],
        'evaluation_start': report['evaluation_start'],
        'evaluation_end': report['evaluation_end'],
        'chronological_state_resets': 0,
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
        'warmup_entry_blocks': report.get('warmup_entry_blocks'),
        'by_year': by_year,
        'load_seconds': report['load_seconds'],
        'replay_elapsed_seconds': report['replay_elapsed_seconds'],
        'elapsed_seconds': report['elapsed_seconds'],
    }
    summary_path = out / f'v25b_chronological_summary_{stamp}.json'
    year_path = out / f'v25b_chronological_by_year_{stamp}.csv'
    summary_path.write_text(json.dumps(summary, indent=2), encoding='utf-8')
    save_year_csv(by_year, year_path)

    print('\n' + '=' * 80)
    print('V2.5B CONTINUOUS CHRONOLOGICAL AUDIT COMPLETE')
    print('=' * 80)
    print(json.dumps({k: v for k, v in summary.items() if k != 'by_year'}, indent=2))
    print('\nCalendar-year realized-trade breakdown:')
    print(json.dumps(by_year, indent=2))
    print(f'\nResults folder: {out}')
    print(f'Summary: {summary_path.name}')
    print(f'By year: {year_path.name}')
    return 0


if __name__ == '__main__':
    mp.freeze_support()
    raise SystemExit(main())
