from __future__ import annotations

from backtest_oos_v242 import DAY_MS, MINUTE_MS, plan_windows
from backtest_v25 import V25_CONFIG


def main() -> int:
    assert V25_CONFIG.min_entry_timeframe_minutes == 120
    assert abs(V25_CONFIG.max_round_trip_cost_r - 0.16) < 1e-12

    last_open = 2_000_000_000_000

    # Original completed research protocol: 14 evaluation windows, 60d warmup.
    research = plan_windows(
        last_open, windows=14, window_days=180,
        skip_recent_days=180, warmup_days=60,
    )
    assert len(research) == 14
    for a, b in zip(research, research[1:]):
        assert int(b['eval_end_ms']) == int(a['eval_start_ms']) - MINUTE_MS

    research_floor = min(int(s['warmup_start_ms']) for s in research)

    # Safe stability protocol: omit the oldest evaluation window and extend
    # warmup to 90d. Its earliest read must remain later than (or equal to)
    # the earliest BTC timestamp already consumed by the original research.
    stability = plan_windows(
        last_open, windows=13, window_days=180,
        skip_recent_days=180, warmup_days=90,
    )
    assert len(stability) == 13
    stability_floor = min(int(s['warmup_start_ms']) for s in stability)
    assert stability_floor >= research_floor

    # The 180d interval immediately before the oldest research evaluation is
    # not fully blind: the original 60d warmup lies inside that interval.
    prior_end = int(research[-1]['eval_start_ms']) - MINUTE_MS
    prior_start = prior_end - 180 * DAY_MS + MINUTE_MS
    assert prior_start < research_floor <= prior_end

    print('V2.5 SELF TEST OK: 2h entry floor + safe 13-window/90d stability boundary')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
