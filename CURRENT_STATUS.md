# CURRENT STATUS — Terminal 3 / v2.5 Research

Last updated: 2026-09-17

## Active branch

- Research branch: `v2.5-research-engine`
- Production baseline on `main`: v2.3
- Current research candidate: **v2.5B**
- Candidate status: **frozen; historical validation completed**
- Research code is not considered live-ready.

## Current candidate

v2.5B preserves the v2.4.2 cost/risk protections and only allows **2h+** signals to open positions. Lower timeframes remain available to the TA/context engine.

Frozen research assumptions:

- minimum entry timeframe: 2h
- fee: 6 bps per side
- slippage: 1 bp per side
- leverage setting: 30x
- aggregate gross-notional cap: 3.15x
- portfolio margin budget: 45%
- maximum modeled round-trip friction: 0.16R
- warm-up methodology: 90 days

Do not tune timeframe, threshold, risk, exit, fee, slippage, leverage, portfolio-cap, or warm-up settings against the consumed validation interval.

## Completed research gates

### 90-day warm-up stability gate — PASSED

Result on the 13 already-seen safe research windows:

- 10 / 13 positive windows
- +$224.93 sum of independent net PnL
- pooled profit factor: 1.1054
- 2,502 trades
- $174.00 modeled fees
- mean 180-day return: +1.730%
- median 180-day return: +1.330%
- best window: +7.80%
- worst window: -7.10%
- worst-window max drawdown: 9.80%

The strategy and 90-day warm-up methodology were frozen after this gate.

### Final untouched early-data validation — COMPLETED

The one-time early holdout was run with the frozen candidate and produced a positive independent result:

- evaluation: 2017-11-15 04:00 UTC through 2018-03-22 11:01 UTC
- original research-history floor: 2018-03-22 11:02 UTC
- overlap with previous v2.5 research history: false
- start equity: $1,000.00
- end equity: $1,059.46
- return: **+5.95%**
- net PnL: **+$59.46**
- trades: 134
- win rate: 53.73%
- profit factor: **1.387**
- max drawdown: **5.62%**
- average R: **+0.177**
- modeled fees: $7.17

No numeric pass/fail threshold had been pre-registered for this gate, so preserve the result descriptively. The interval is now **consumed** and must never again be described as blind validation data for v2.5B.

Full record:

- `docs/history/V25B_FINAL_UNTOUCHED_VALIDATION_RESULT.md`
- `docs/history/V25B_FINAL_UNTOUCHED_VALIDATION_SUMMARY.json`

The old `RUN_V25_FINAL_VALIDATION.bat` path is now retained only as a **hard-locked historical reproduction** utility. It labels reruns as reproductions and rejects changes to the frozen equity, fee, slippage, leverage, portfolio-cap and warm-up settings.

## Current gate / next exact action

### Continuous chronological replay over the full available BTC history

Implementation is ready:

`RUN_V25_CHRONOLOGICAL.bat`

Input: the same BTC 1-minute CSV.

The runner hard-locks the frozen v2.5B research settings, uses one 90-day no-trade warm-up, then replays the rest of the dataset continuously with **zero periodic state resets**. It shows live progress/ETA and writes full aggregate results plus a calendar-year realized-trade breakdown to `backtest_results_v25b_chronological/`.

Purpose: audit whether the candidate's behavior is materially affected by the reset/warm-up structure used by the independent research windows and verify performance through changing market regimes in one uninterrupted stateful replay.

Requirements:

1. Keep v2.5B strategy parameters frozen.
2. Use the same 90-day initial no-trade warm-up.
3. After warm-up, replay the remaining dataset continuously with no periodic state resets.
4. Preserve all normal fees, slippage, risk controls, exits, leverage and portfolio caps.
5. Report full-history aggregate performance plus chronological period breakdowns so regime concentration is visible.
6. Show visible replay progress and ETA; progress instrumentation must not alter trading calculations.
7. Treat this as a historical audit, **not** a new blind validation test, because the dataset has already been inspected.

Do not use the chronological replay to silently optimize the current frozen candidate. Any future strategy revision must become a new named candidate and require genuinely fresh independent data for its next out-of-sample test.

## After chronological replay

Planned sequence:

1. Add perpetual-specific funding modeling.
2. Add maintenance-margin and liquidation modeling.
3. Improve execution realism and gap handling.
4. Obtain genuinely fresh BTC history or exchange-specific perpetual history for another independent out-of-sample test.
5. Align demo/PAPER execution with the research assumptions and validate behavior prospectively.
6. Real-money deployment remains out of scope until validation and execution modeling are complete.

## Known engineering issues / follow-up work

These are separate from strategy tuning:

- The production/PAPER bot on `main` is still the v2.3 runtime, not the v2.5B research candidate.
- PAPER execution is not yet a faithful validation of the research cost model; fees/slippage/funding and execution behavior need alignment before PAPER results are compared directly with backtests.
- Live bot ownership/order state is primarily runtime memory and needs stronger restart recovery/persistence before real-money use.
- Exchange order submission should be idempotent/recoverable across ambiguous timeout/network-failure cases before real-money use.
- Dashboard control endpoints should receive an additional local-session/CSRF hardening pass before real-money use.

## Key project memory files

Use these to reconstruct project state in a future chat/session:

- `CURRENT_STATUS.md` — first file to read; current gate and next action
- `docs/V25_RESEARCH_PLAN.md` — research methodology, decisions, and validation sequence
- `docs/history/V25A_1H_RESEARCH_RESULT.md` — candidate A result
- `docs/history/V25B_2H_RESEARCH_RESULT.md` — original candidate B result
- `docs/history/V25B_90D_STABILITY_RESULT.md` — warm-up stability result
- `docs/history/V25B_FINAL_UNTOUCHED_VALIDATION_RESULT.md` — consumed independent validation result
- `backtest_v25_chronological.py` — current full-history audit runner
- `README.md` — repository overview and branch status
- Git commit history — chronological implementation record

## Continuation rule

When resuming this project in another chat or session, read `CURRENT_STATUS.md` first, then `docs/V25_RESEARCH_PLAN.md`, then inspect the latest commits/results. Do not assume the next step from memory if this file or the branch has changed.
