# v2.5B 90-day warm-up stability result

Candidate B stayed frozen at **2h+ entries** with the same v2.4.2 cost/risk/exit stack. Only the no-trade warm-up changed from 60 days to 90 days.

To avoid loading any BTC history earlier than the original research-history boundary, this stability check reran only the **13 already-seen newest research windows**. The oldest 14th research window was deliberately omitted.

Completed result:

- Positive windows: 10 / 13
- Negative windows: 3 / 13
- Sum of independent net PnL: +$224.93
- Mean 180-day return: +1.730%
- Median 180-day return: +1.330%
- Best window: +7.80%
- Worst window: -7.10%
- Worst window max drawdown: 9.80%
- Median window max drawdown: 5.45%
- Pooled trades: 2,502
- Pooled wins / losses: 1,183 / 1,319
- Pooled win rate: 47.282%
- Pooled profit factor: 1.1054
- Pooled average R: +0.0246
- Total modeled fees: $174.00
- Gross PnL after modeled slippage but before fees: about +$398.90
- Full runtime: 1,517.072 seconds (25m 17s)
- CSV load time: 15.686 seconds
- Replay stage: 1,495.797 seconds

For an apples-to-apples comparison, the same 13 windows under the original 60-day warm-up produced approximately:

- 10 / 13 positive windows
- +$133.36 net PnL
- pooled PF 1.0590
- 2,530 trades
- $186.36 fees
- mean return +1.026%
- median return +1.210%
- worst window -9.19%
- worst window max drawdown 10.50%

All 13 windows kept the same positive/negative sign when warm-up changed from 60 to 90 days. Window-return correlation was about 0.859. The mean absolute change in 180-day return was about 1.65 percentage points, so the strategy is directionally stable but return magnitude is still sensitive to initialization/context history.

The aggregate improved rather than collapsing: PF 1.0590 -> 1.1054 and net PnL +$133.36 -> +$224.93 on the same windows. Removing the single best 90-day window still leaves about +$146.89 and pooled PF about 1.076. Removing the two best windows still leaves about +$69.64 and pooled PF about 1.042.

A completed-fill friction stress approximation implies roughly $289,976 of two-sided turnover. Each additional 1 bp per side would cost about $29.00 on these fills; approximately +7.8 bps per side beyond the modeled fee/slippage assumptions would erase the observed aggregate net profit. This is not a full re-simulation.

Timeframe diagnostics remain research-only. In the 90-day run, 2h and 3h were positive, 4h was negative, and several higher horizons had small samples. No further timeframe selection is permitted before final validation.

Conclusion: candidate B passes the warm-up stability gate sufficiently to freeze the 90-day methodology and proceed to the final untouched early-data validation. The final validation interval must end strictly before the first timestamp ever loaded by the original v2.5 research run.
