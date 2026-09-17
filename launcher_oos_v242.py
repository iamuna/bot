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


def positive_integer(raw: str, name: str, allow_zero: bool = False) -> str:
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{name} must be a whole number, got: {raw!r}') from exc
    if value < 0 or (value == 0 and not allow_zero):
        raise ValueError(f'{name} must be {"zero or greater" if allow_zero else "greater than zero"}')
    return str(value)


def default_workers() -> int:
    return max(1, int(os.cpu_count() or 1))


def self_test() -> int:
    assert clean_path(r' "C:\Data\BTC.csv" ') == r'C:\Data\BTC.csv'
    assert positive_integer('8', 'windows') == '8'
    assert positive_integer('0', 'workers', allow_zero=True) == '0'
    assert default_workers() >= 1
    print('V2.4.2 OOS LAUNCHER SELF TEST OK')
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == '--self-test':
        return self_test()

    root = Path(__file__).resolve().parent
    log_path = root / 'oos_launcher.log'
    log_path.write_text(
        f'Terminal 3 v2.4.2 OOS launcher\nStarted: {datetime.now().isoformat()}\n',
        encoding='utf-8',
    )

    try:
        raw_path = argv[0] if argv else input('BTC 1-minute CSV/ZIP path: ')
        input_text = clean_path(raw_path)
        if not input_text:
            raise ValueError('No input file selected.')
        input_path = Path(input_text).expanduser()
        if not input_path.is_absolute():
            input_path = (root / input_path).resolve()
        if not input_path.is_file():
            raise FileNotFoundError(f'File not found: {input_path}')

        windows = positive_integer(argv[1] if len(argv) > 1 else '8', 'windows')
        workers = positive_integer(argv[2] if len(argv) > 2 else '0', 'workers', allow_zero=True)

        print('\n' + '=' * 64)
        print('Terminal 3 v2.4.2 FROZEN OOS BATTERY')
        print('=' * 64)
        print(f'Data file: {input_path}')
        print(f'OOS windows: {windows} x 180 days')
        print('Excluded tuned period: latest 180 days in the file')
        print('Warm-up: 60 days before every OOS window, trading disabled')
        print('Strategy: FROZEN v2.4.2 Efficient (no tuning / no sweep)')
        print('Costs: 6 bps fee + 1 bp slippage per side')
        print('Leverage setting: 30x; aggregate gross exposure cap: 3.15x equity')
        print(f'CPU: {default_workers()} logical processors detected')
        print('The independent windows run concurrently when resources allow.\n')

        cmd = [
            sys.executable, '-u', str(root / 'backtest_oos_v242.py'), str(input_path),
            '--windows', windows,
            '--window-days', '180',
            '--skip-recent-days', '180',
            '--warmup-days', '60',
            '--equity', '1000',
            '--fee-bps', '6',
            '--slippage-bps', '1',
            '--leverage', '30',
            '--gross-cap-x', '3.15',
            '--portfolio-margin-pct', '45',
            '--workers', workers,
            '--out', 'backtest_results_oos_v242',
        ]
        rc = subprocess.call(cmd, cwd=root)
        with log_path.open('a', encoding='utf-8') as f:
            f.write(f'Exit code: {rc}\n')

        if rc == 0:
            print('\nOOS BATTERY FINISHED SUCCESSFULLY')
            print('Results: backtest_results_oos_v242\\')
        else:
            print(f'\nOOS battery failed with exit code {rc}.')
            print(f'Log: {log_path}')
        return rc
    except KeyboardInterrupt:
        print('\nStopped by user.')
        return 130
    except Exception as exc:
        with log_path.open('a', encoding='utf-8') as f:
            f.write(f'ERROR: {type(exc).__name__}: {exc}\n')
        print(f'\nERROR: {exc}')
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
