# v2.5B final untouched early-data validation result

Date recorded: 2026-09-17

Status: **completed and consumed**. This interval is no longer blind validation data for v2.5B.

## Protocol

Candidate B remained frozen at the settings selected before this run:

- minimum entry timeframe: 2h
- fee: 6 bps per side
- slippage: 1 bp per side
- leverage setting: 30x
- aggregate gross-notional cap: 3.15x
- portfolio margin budget: 45%
- maximum modeled round-trip friction: 0.16R
- warm-up: 90 days

The validation runner used the earliest available BTC data as a 90-day no-trade warm-up, then evaluated only candles strictly earlier than the first timestamp ever loaded by the original v2.5 research process.

- dataset / warm-up start: 2017-08-17 04:00 UTC
- evaluation start: 2017-11-15 04:00 UTC
- evaluation end: 2018-03-22 11:01 UTC
- original v2.5 research-history floor: 2018-03-22 11:02 UTC
- overlap with prior v2.5 research history: **false**

The run therefore stopped exactly one minute before the original research-history boundary.

## Result

- starting equity: $1,000.00
- ending equity: $1,059.46
- return: **+5.95%**
- net PnL: **+$59.46**
- trades: 134
- wins: 72
- losses: 62
- win rate: 53.73%
- profit factor: **1.387**
- max drawdown: **5.62%**
- average R: **+0.177**
- modeled fees paid: $7.17
- peak equity: $1,107.59
- liquidation modeled: false
- warm-up entry blocks: 31,521
- CSV load time: 7.177 seconds
- replay time: 794.082 seconds
- total elapsed time: 801.264 seconds

The result is a positive independent holdout result. No numeric pass/fail threshold was pre-registered for this gate, so it should be preserved descriptively rather than retroactively assigning a new threshold.

## Timeframe breakdown

| Timeframe | Trades | Wins | Win rate | Net PnL | Sum R |
|---|---:|---:|---:|---:|---:|
| 2h | 56 | 27 | 48.2% | -$16.45 | +2.57 |
| 3h | 27 | 15 | 55.6% | +$6.56 | +2.50 |
| 4h | 19 | 12 | 63.2% | +$9.90 | +4.74 |
| 6h | 8 | 7 | 87.5% | +$34.42 | +8.86 |
| 8h | 4 | 2 | 50.0% | +$7.85 | +1.85 |
| 12h | 10 | 5 | 50.0% | +$15.21 | +0.67 |
| 16h | 3 | 0 | 0.0% | -$1.58 | -0.54 |
| 1d | 3 | 2 | 66.7% | +$6.23 | +1.66 |
| 2d | 3 | 2 | 66.7% | +$3.13 | +2.44 |
| 3d | 1 | 0 | 0.0% | -$5.80 | -1.01 |

The timeframe breakdown is diagnostic only. In particular, the negative 2h bucket must **not** be used to remove 2h entries and then relabel this same interval as blind validation; doing so would tune on the holdout.

## Interpretation and integrity rule

This run supports the existence of a positive historical edge under the frozen research assumptions, but it is only one relatively short early-BTC holdout with 134 trades. It does not establish live profitability and it does not model all perpetual-specific realities.

From this point onward:

1. This early interval is permanently treated as consumed.
2. Do not retune v2.5B against it and later describe the result as independent validation.
3. The next historical audit is a **single continuous chronological replay over the full available dataset** to check reset/warm-up artifacts and behavior through changing market regimes.
4. After that, add perpetual-specific funding, maintenance margin/liquidation, execution realism and gap handling.
5. Obtain genuinely fresh data or exchange-specific perpetual history for the next independent out-of-sample test.
6. Demo/PAPER validation comes only after those modeling layers are in place; real money remains out of scope.

Source run files supplied from `backtest_results_v25b_final_validation.zip`:

- `v25b_final_validation_summary_20260917_090347.json`
- `v24_backtest_20260917_090347.json`
- `v24_backtest_trades_20260917_090347.csv`
