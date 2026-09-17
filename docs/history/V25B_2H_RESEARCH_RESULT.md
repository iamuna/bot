# v2.5B 2h-entry research result

Candidate B changed only the minimum entry timeframe from 1h+ to **2h+** while keeping the v2.4.2 cost/risk stack unchanged.

Research corpus: the same 14 already-inspected 180-day BTC windows used for architecture research. This was **not** a blind validation run.

Completed result:

- Positive windows: 11 / 14
- Negative windows: 3 / 14
- Sum of independent net PnL: +$155.42
- Mean 180-day return: +1.110%
- Median 180-day return: +1.235%
- Best window: +9.61%
- Worst window: -9.19%
- Worst window max drawdown: 10.50%
- Median window max drawdown: 5.435%
- Pooled trades: 2,696
- Pooled win rate: 47.218%
- Pooled profit factor: 1.0660
- Pooled average R: +0.0269
- Total modeled fees: $194.22
- Gross PnL after modeled slippage but before fees: about +$349.63
- Full recorded runtime: 1,364.709 seconds (22m 45s)
- CSV load time: 15.094 seconds
- Replay stage: 1,343.620 seconds

Compared with candidate A, candidate B reduced trades from 8,273 to 2,696, fees from $388.69 to $194.22, improved pooled PF from 1.0023 to 1.0660, improved independent net PnL from +$8.63 to +$155.42, and reduced the worst window from -12.54% to -9.19%. Positive-window count stayed 11/14.

The result is not dependent on the single best window: removing the +9.61% best window still leaves about +$59.33 independent net PnL and pooled PF about 1.028. That is better than breakeven, but still a thin margin.

Approximate cost sensitivity, holding the completed fills fixed: one additional basis point of two-sided execution cost per side would reduce net PnL to about +$123.04; +2 bps leaves +$90.67; +3 bps leaves +$58.30; +4 bps leaves +$25.93; +5 bps turns the sample slightly negative at about -$6.44. This is only a friction stress test, not a full re-simulation.

Timeframe diagnosis from the realized v2.5B trades:

- 2h: 1,100 trades, +$125.44 net
- 3h: 599 trades, +$56.94 net
- 4h: 321 trades, -$65.35 net
- 6h: 206 trades, -$11.10 net
- 8h: 166 trades, approximately flat
- 12h: 127 trades, -$22.05 net
- 16h: 94 trades, +$3.60 net
- 1d: 36 trades, +$32.98 net
- 2d: 18 trades, +$23.67 net
- 3d: 13 trades, +$13.99 net

These per-timeframe numbers are diagnostics only. Selectively deleting losing timeframes after seeing the sample would be curve fitting because portfolio slots, equity, throttling and later entries would all change.

## Warm-up / holdout correction

The original plan described the 180 days immediately before the oldest research evaluation window as an untouched future holdout. That description was too strong. The oldest research window used a 60-day no-trade warm-up, so the final 60 days of that earlier 180-day interval were already loaded into the indicator state. They were not traded or scored for PnL, but they still influenced research-window indicators and therefore cannot be called completely blind data anymore.

The original 14-window/60-day research run first loaded early BTC history at approximately **2018-03-22 11:02 UTC**. Data earlier than that boundary remains the cleanest untouched segment in the current CSV.

The TA engine requires 200 bars before EMA200 is included. Sixty days fully initializes the 2h-6h entry horizons that dominate this candidate, but supplies only 180 8h bars. A 90-day warm-up would improve initialization, but applying it to all 14 windows would read new early data and shrink the untouched segment.

Therefore the next methodology check uses **13 already-seen windows with a 90-day warm-up** and intentionally omits the oldest research window. This keeps the stability check inside history that was already consumed by research. No strategy parameter changes are permitted during that check. The fully untouched final validation segment will be defined only after warm-up methodology is frozen.
