# CURRENT STATUS — Terminal 3 / v2.5 Research

Last updated: 2026-09-17

## Active branch

- Research branch: `v2.5-research-engine`
- Production baseline on `main`: v2.3
- Current research candidate: **v2.5B**
- Candidate status: **frozen for validation**
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
- final-validation warm-up: 90 days

No timeframe, threshold, risk, exit, fee, slippage, leverage, portfolio-cap, or warm-up tuning should be performed before the final untouched validation is recorded.

## Last completed research gate

**90-day warm-up stability gate: PASSED**

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

## Current gate / next exact action

### Before consuming the untouched validation interval

Harden `backtest_v25_final_validation.py` so the frozen validation assumptions cannot be changed while still producing a report labeled `candidate_frozen: true`.

The official final-validation values must be fixed to:

- fee: 6 bps per side
- slippage: 1 bp per side
- leverage: 30x
- aggregate gross cap: 3.15x
- portfolio margin budget: 45%
- warm-up: 90 days

The warm-up is already equality-locked. The remaining frozen values should be hard-locked as well.

### Then run exactly once

Run:

`RUN_V25_FINAL_VALIDATION.bat`

Input: BTC 1-minute CSV.

Protocol:

1. Use the earliest available BTC history for the locked 90-day no-trade warm-up.
2. Evaluate only candles strictly earlier than the first timestamp ever loaded by the original v2.5 research process.
3. Record the result whether favorable or unfavorable.
4. Do not retune the candidate against that interval and later describe it as blind validation.
5. After this run, no historical BTC period in the current CSV remains untouched for v2.5B.

Results are written to:

`backtest_results_v25b_final_validation/`

## What comes after final validation

Regardless of the final-validation result, preserve it as a historical record. The planned sequence after that is:

1. Run a continuous chronological replay over the full available history to audit reset/warm-up artifacts.
2. Add perpetual-specific funding modeling.
3. Add maintenance-margin and liquidation modeling.
4. Improve execution realism and gap handling.
5. Obtain genuinely fresh data or exchange-specific perpetual history for another independent out-of-sample test.
6. Move to demo/PAPER validation only after those layers are complete.
7. Real-money deployment remains out of scope until validation and execution modeling are complete.

## Known engineering issues / follow-up work

These are separate from the frozen strategy and should not be confused with strategy tuning:

- `backtest_v25_final_validation.py` currently exposes several supposedly frozen assumptions as CLI arguments; hard-lock them before the one-time untouched validation.
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
- `docs/history/V25B_90D_STABILITY_RESULT.md` — latest completed stability result
- `README.md` — repository overview and branch status
- Git commit history — chronological implementation record

## Continuation rule

When resuming this project in another chat or session, read `CURRENT_STATUS.md` first, then `docs/V25_RESEARCH_PLAN.md`, then inspect the latest commits/results. Do not assume the next step from memory if this file or the branch has changed.
