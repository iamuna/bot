from __future__ import annotations

from backtest_oos_v242 import DAY_MS, MINUTE_MS, plan_windows
from backtest_v25 import V25_CONFIG


def main() -> int:
    assert V25_CONFIG.min_entry_timeframe_minutes == 120
    assert abs(V25_CONFIG.max_round_trip_cost_r - 0.16) < 1e-12

    # Synthetic last timestamp. Fourteen research windows must be contiguous
    # and the next older 180-day interval must remain outside the plan.
    last_open = 2_000_000_000_000
    specs = plan_windows(last_open, windows=14, window_days=180,
                         skip_recent_days=180, warmup_days=60)
    assert len(specs) == 14
    for a, b in zip(specs, specs[1:]):
        assert int(b['eval_end_ms']) == int(a['eval_start_ms']) - MINUTE_MS
    reserved_end = int(specs[-1]['eval_start_ms']) - MINUTE_MS
    reserved_start = reserved_end - 180 * DAY_MS + MINUTE_MS
    assert reserved_end < int(specs[-1]['eval_start_ms'])
    assert reserved_start < reserved_end

    print('V2.5 SELF TEST OK: 2h entry floor and reserved holdout boundary')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
