from __future__ import annotations

from backtest_oos_v242 import DAY_MS, MINUTE_MS, plan_windows
from backtest_v25 import V25_CONFIG
from backtest_v25_final_validation import (
    FROZEN_EQUITY,
    FROZEN_FEE_BPS,
    FROZEN_GROSS_CAP_X,
    FROZEN_LEVERAGE,
    FROZEN_PORTFOLIO_MARGIN_PCT,
    FROZEN_SLIPPAGE_BPS,
    FROZEN_WARMUP_DAYS,
)


def main() -> int:
    assert V25_CONFIG.min_entry_timeframe_minutes == 120
    assert abs(V25_CONFIG.max_round_trip_cost_r - 0.16) < 1e-12

    # Historical reproduction of the consumed final holdout is hard-locked to
    # the exact settings used by the original one-time validation run.
    assert FROZEN_WARMUP_DAYS == 90
    assert FROZEN_EQUITY == 1000.0
    assert FROZEN_FEE_BPS == 6.0
    assert FROZEN_SLIPPAGE_BPS == 1.0
    assert FROZEN_LEVERAGE == 30.0
    assert FROZEN_GROSS_CAP_X == 3.15
    assert FROZEN_PORTFOLIO_MARGIN_PCT == 45.0

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

    # The original final validation interval was strictly before the research
    # floor. It has now been consumed and is retained only for reproduction.
    synthetic_first = research_floor - 220 * DAY_MS
    final_eval_start = synthetic_first + 90 * DAY_MS
    final_eval_end = research_floor - MINUTE_MS
    assert synthetic_first < final_eval_start < final_eval_end < research_floor
    assert final_eval_start - synthetic_first == 90 * DAY_MS

    # The 180d interval immediately before the oldest research evaluation was
    # not fully blind: the original 60d warmup lies inside that interval.
    prior_end = int(research[-1]['eval_start_ms']) - MINUTE_MS
    prior_start = prior_end - 180 * DAY_MS + MINUTE_MS
    assert prior_start < research_floor <= prior_end

    print('V2.5 SELF TEST OK: frozen 2h candidate + stability boundary + locked holdout reproduction')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
