from __future__ import annotations

import os
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path


def clean_path(raw: str) -> str:
    s = str(raw or '').strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in {'"', "'"}:
        s = s[1:-1].strip()
    return s


def positive_number(raw: str, name: str) -> str:
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{name} must be a number, got: {raw!r}') from exc
    if value <= 0:
        raise ValueError(f'{name} must be greater than zero, got: {raw!r}')
    return str(int(value)) if value.is_integer() else str(value)


def positive_integer(raw: str, name: str) -> str:
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{name} must be a whole number, got: {raw!r}') from exc
    if value <= 0:
        raise ValueError(f'{name} must be greater than zero, got: {raw!r}')
    return str(value)


def default_workers() -> int:
    return max(1, int(os.cpu_count() or 1))


def append_log(log_path: Path, text: str) -> None:
    with log_path.open('a', encoding='utf-8') as f:
        f.write(text.rstrip() + '\n')


def self_test() -> int:
    assert clean_path(r'  "C:\Users\ib\Desktop\sfc\BTCUSD_1m_Binance.zip"  ') == r'C:\Users\ib\Desktop\sfc\BTCUSD_1m_Binance.zip'
    assert clean_path(r'C:\Data\BTC.zip') == r'C:\Data\BTC.zip'
    assert positive_number('180', 'days') == '180'
    assert positive_number('30', 'leverage') == '30'
    assert positive_number('7.5', 'leverage') == '7.5'
    assert positive_integer('16', 'workers') == '16'
    assert default_workers() == max(1, int(os.cpu_count() or 1))
    try:
        positive_number('0', 'days')
    except ValueError:
        pass
    else:
        raise AssertionError('zero must be rejected')
    print('V2.4 LAUNCHER SELF TEST OK: selective comparison + maximum-use CPU selection')
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == '--self-test':
        return self_test()

    root = Path(__file__).resolve().parent
    log_path = root / 'backtest_launcher.log'
    log_path.write_text(
        f'Terminal 3.0 v2.4.1 launcher log\nStarted: {datetime.now().isoformat()}\n',
        encoding='utf-8',
    )

    try:
        if argv:
            raw_path = argv[0]
        else:
            print('No data file was passed to the launcher.')
            print('Paste the full path below, or drag the CSV/ZIP into this window.')
            raw_path = input('BTC 1-minute CSV/ZIP path: ')

        input_text = clean_path(raw_path)
        if not input_text:
            raise ValueError('No input file selected.')

        input_path = Path(input_text).expanduser()
        if not input_path.is_absolute():
            input_path = (root / input_path).resolve()
        if not input_path.is_file():
            raise FileNotFoundError(f'File not found: {input_path}')

        days = positive_number(argv[1] if len(argv) >= 2 and argv[1] else '180', 'days')
        leverage = positive_number(argv[2] if len(argv) >= 3 and argv[2] else '30', 'leverage')
        workers = positive_integer(argv[3] if len(argv) >= 4 and argv[3] else str(default_workers()), 'workers')

        append_log(log_path, f'Input: {input_path}')
        append_log(log_path, f'Days: {days}')
        append_log(log_path, f'Leverage: {leverage}x')
        append_log(log_path, f'Maximum-use workers: {workers}')

        print('\n================================================')
        print('Terminal 3.0 v2.4.1 Selective Repair Test')
        print('Guarded control vs Selective - MAXIMUM USE MODE')
        print('================================================')
        print(f'Data file: {input_path}')
        print(f'Research window: most recent {days} days')
        print(f'Leverage setting: {leverage}x')
        print(f'CPU workers available to parallel stages: {workers}')
        print('Final replay: GUARDED CONTROL + SELECTIVE run concurrently')
        print('Gross exposure cap: 3.15x account equity')
        print('Portfolio margin budget: 45% of account equity')
        print('Fee assumption: 6 bps per side')
        print('Slippage assumption: 1 bp per side')
        print('Selective anti-churn: max round-trip cost 0.20R')
        print('Selective target hurdle: at least 1.50R net after modeled costs')
        print('Selective risk: rolling past-trade edge sizing + 15% new-risk drawdown lock')
        print('NOTE: this is a research candidate; liquidation mechanics are not modeled.')
        print('\nStarting comparison. The runner will use as much useful compute as each stage can safely consume.\n', flush=True)

        cmd = [
            sys.executable,
            '-u',
            str(root / 'backtest_selective_runner.py'),
            str(input_path),
            '--last-days', days,
            '--fee-bps', '6',
            '--slippage-bps', '1',
            '--leverage', leverage,
            '--gross-cap-x', '3.15',
            '--portfolio-margin-pct', '45',
            '--workers', workers,
            '--out', 'backtest_results_selective',
            '--mode', 'compare',
        ]
        rc = subprocess.call(cmd, cwd=root)
        append_log(log_path, f'Backtest exit code: {rc}')

        if rc == 0:
            print('\n========================================')
            print('REPAIR COMPARISON COMPLETE')
            print('Control results:   backtest_results_selective\\guarded_control\\')
            print('Selective results: backtest_results_selective\\selective\\')
            print('Summary:           backtest_results_selective\\v241_selective_comparison_*.json')
            print('========================================')
            append_log(log_path, 'SUCCESS: repair comparison completed')
        else:
            print(f'\nERROR: v2.4.1 repair comparison failed with exit code {rc}.')
            print(f'Launcher log: {log_path}')
        return rc

    except KeyboardInterrupt:
        append_log(log_path, 'Stopped by user (KeyboardInterrupt)')
        print('\nStopped by user.')
        return 130
    except Exception as exc:
        append_log(log_path, f'ERROR: {type(exc).__name__}: {exc}')
        print(f'\nERROR: {exc}')
        print(f'Launcher log: {log_path}')
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
