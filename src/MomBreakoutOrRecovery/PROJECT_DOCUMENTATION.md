# Momentum Continuation — Project Documentation

## 1. Project Overview

### Project Name

**Momentum Continuation**

### Project Type

Nifty 500 short-term positional stock ranking and trade-setup research engine.

### Primary Objective

The system scans the current Nifty 500 universe and identifies stocks exhibiting a combination of:

* Established bullish trend
* Breakout or retracement-recovery behavior
* Volume confirmation
* Positive momentum
* Adequate liquidity
* Defined risk
* Minimum 2:1 risk/reward

The resulting stocks are assigned a weighted setup-quality score and ranked from strongest to weakest.

---

# 2. Core Strategy

The complete strategy is:

```text
MOMENTUM CONTINUATION
=
ESTABLISHED UPTREND
AND
(
    20-DAY BREAKOUT
    OR
    CONTROLLED RETRACEMENT RECOVERY
)
```

This is a **trend-continuation strategy**, not a value-investing strategy and not a mean-reversion strategy.

The fundamental assumption is that stocks already demonstrating a strong bullish structure may continue their existing trend after either:

1. Breaking through a recent price resistance level, or
2. Recovering from a controlled pullback.

That assumption must be validated through backtesting rather than accepted as fact.

---

# 3. Design Principles

The engine follows five major principles.

## 3.1 Trend First

A stock must already have an established bullish trend before a continuation setup can qualify.

This prevents the breakout/recovery logic from being applied indiscriminately to stocks in weak or sideways trends.

## 3.2 Confirmation Over Anticipation

The strategy waits for confirmation.

For example, the breakout condition requires:

```text
Close > Previous 20-Day High
```

rather than merely requiring the intraday high to exceed resistance.

## 3.3 Volume Confirmation

Price movement is accompanied by a relative-volume condition.

This attempts to distinguish stronger price movements from low-volume movements.

## 3.4 Defined Risk

Every qualifying candidate must have a mechanically calculated stop-loss and at least a 2:1 risk/reward ratio.

## 3.5 Relative Ranking

The engine does not attempt to forecast the future price.

It ranks currently qualifying setups according to predefined characteristics.

---

# 4. Universe

The system refreshes the current Nifty 500 universe before analysis.

The intended process is:

```text
Current Nifty 500 Constituents
            ↓
Download Market Data
            ↓
Analyze Each Valid Symbol
```

The system should not hard-code an old stock list when the objective is to analyze the current Nifty 500.

---

# 5. Market Data

The engine obtains daily OHLCV data using Yahoo Finance through `yfinance`.

Required fields:

```text
Open
High
Low
Close
Volume
```

The current implementation requests approximately one year of daily data.

However, the strategy calculates a 252-trading-day 52-week high.

Therefore, the data-history requirement deserves attention.

## Important Data-History Issue

The code currently defines:

```python
MIN_HISTORY_DAYS = 200
```

while also calculating:

```python
High52 = High.shift(1).rolling(252).max()
```

These requirements are inconsistent.

A stock can have at least 200 rows while still not having enough data to calculate a genuine previous 252-trading-day high.

Therefore, if the 52-week high is intended to be fully populated, the downloaded history should normally contain at least approximately 252 trading sessions, plus the shifted observation.

This should be corrected before relying heavily on `High52`.

---

# 6. Configuration

## General

```python
TOP_N = 20

MIN_PRICE = 100

MIN_HISTORY_DAYS = 200

MIN_AVG_TRADED_VALUE_CRORE = 20
```

### Meaning

| Parameter                  |  Value | Purpose                             |
| -------------------------- | -----: | ----------------------------------- |
| TOP_N                      |     20 | Maximum displayed candidates        |
| MIN_PRICE                  |   ₹100 | Minimum stock price                 |
| MIN_HISTORY_DAYS           |    200 | Minimum available observations      |
| MIN_AVG_TRADED_VALUE_CRORE | ₹20 Cr | Minimum 20-day average traded value |

---

# 7. Breakout Configuration

```python
BREAKOUT_LOOKBACK = 20

BREAKOUT_VOLUME_MULTIPLIER = 1.5

STRONG_VOLUME_MULTIPLIER = 2.0

MIN_BREAKOUT_BODY_PERCENT = 1.0

CLOSE_POSITION_THRESHOLD = 0.75
```

## Important Observation

`STRONG_VOLUME_MULTIPLIER` is currently defined as:

```python
STRONG_VOLUME_MULTIPLIER = 2.0
```

but it is not actually used in the scoring or signal detection functions.

Therefore, changing this value currently has no effect on the output.

If the intention is to explicitly reward volume above 2× average, the scoring function should use this constant.

---

# 8. Retracement Configuration

```python
RETRACEMENT_LOOKBACK = 60

MIN_RETRACEMENT_PERCENT = 5.0

MAX_RETRACEMENT_PERCENT = 20.0

RETRACEMENT_VOLUME_MULTIPLIER = 1.2
```

The strategy considers a retracement from the recent 60-day high.

Valid retracement:

```text
5% <= Retracement <= 20%
```

A recovery signal then requires:

```text
Close > Previous Day High
```

and:

```text
Volume >= 1.2 × 20-Day Average Volume
```

---

# 9. Trend Configuration

```python
SHORT_EMA = 10
FAST_EMA = 20
MEDIUM_EMA = 50
LONG_EMA = 200
```

The primary trend structure uses EMA20, EMA50 and EMA200.

EMA10 is calculated for potential future use but is not currently used by the core signal.

---

# 10. Established Uptrend

The established trend function requires:

```text
Close > EMA50

EMA20 > EMA50

EMA50 > EMA200
```

This creates the structure:

```text
Price
  >
EMA20
  >
EMA50
  >
EMA200
```

## Why Close > EMA20 Is Not Required

The implementation intentionally allows price to fall below EMA20 while remaining above EMA50.

This is important for the retracement setup.

For example:

```text
EMA200
──────────────

EMA50
──────────────
       ↑
   recovery

EMA20
──────────────

Price
   ↓
pullback
```

A controlled pullback may temporarily weaken short-term momentum without invalidating the medium/long-term bullish structure.

For breakout setups, however, the price must additionally be above EMA20.

---

# 11. 20-Day Breakout

The breakout requires:

```text
Established Uptrend
AND
Close > Previous 20-Day High
AND
Close > EMA20
AND
Volume >= 1.5 × Average 20-Day Volume
```

## Previous 20-Day High

The calculation is:

```python
df["High20"] = (
    df["High"]
    .shift(1)
    .rolling(20)
    .max()
)
```

The `shift(1)` is important.

It excludes today's high from the resistance calculation.

Therefore:

```text
Previous 20 completed sessions
        ↓
Highest High
        ↓
Today's Close must exceed it
```

This avoids a look-ahead problem in the breakout signal itself.

---

# 12. Controlled Retracement Recovery

The retracement setup requires:

```text
Established Uptrend
AND
Retracement >= 5%
AND
Retracement <= 20%
AND
Close > EMA50
AND
Close > Previous Day High
AND
Volume >= 1.2 × Average 20-Day Volume
```

The recent swing high is calculated from the previous 60 trading sessions.

Retracement:

```text
Retracement %
=
(1 - Current Close / Recent Swing High) × 100
```

Example:

```text
Recent Swing High = ₹1,000
Current Close     = ₹900

Retracement
= (1 - 900/1000) × 100
= 10%
```

This qualifies within the 5–20% range.

---

# 13. Price Filter

The engine rejects stocks below:

```text
₹100
```

The filter is applied to the latest available close.

This is primarily a practical liquidity/price-quality filter.

It does not establish that higher-priced stocks are fundamentally better investments.

---

# 14. Liquidity Filter

The strategy requires:

```text
20-Day Average Traded Value >= ₹20 crore
```

Traded value is calculated as:

```text
Close × Volume / 10,000,000
```

This converts the approximate traded value into crore rupees.

The stock is rejected if its average 20-day traded value is below ₹20 crore.

---

# 15. Technical Indicators

## EMA

The engine calculates:

```text
EMA10
EMA20
EMA50
EMA200
```

using pandas exponential moving averages.

## Volume

```text
VolumeAvg20
VolumeAvg50
```

are calculated using rolling averages.

## ATR14

The Average True Range uses:

```text
High - Low
High - Previous Close
Low - Previous Close
```

and takes the maximum of the three values for each day.

ATR14 is then calculated using a 14-session rolling mean.

## Momentum

Two returns are calculated:

```text
Return20
Return60
```

Formula:

```text
Return20 =
(Current Close / Close 20 sessions ago - 1) × 100
```

and similarly for 60 sessions.

---

# 16. Candle Analysis

The engine calculates:

### Candle Range

```text
High - Low
```

### Candle Body

```text
abs(Close - Open)
```

### Candle Body %

```text
Candle Body / Close × 100
```

### Close Position

```text
(Close - Low) / (High - Low)
```

Interpretation:

```text
1.00 → Close at high
0.75 → Close in upper 25%
0.50 → Close around middle
0.00 → Close at low
```

---

# 17. Ranking Methodology

The maximum score is 100.

```text
Breakout Strength       25
Volume Confirmation     20
Trend Strength          15
Closing Strength        10
Momentum                10
Retracement Quality     10
EMA50 Position           5
Liquidity                 5
                       ----
                        100
```

---

# 18. Breakout Score

Maximum:

```text
25 points
```

The implementation currently assigns:

```text
Breakout distance > 0%   → +15
Breakout distance >= 2%  → +5
Breakout distance >= 5%  → +5
```

Maximum:

```text
25
```

## Important Interpretation

The breakout score is calculated for all qualifying setups.

That means a **retracement-recovery candidate can receive breakout points** if its price happens to be above the previous 20-day high.

Therefore, the score component does not exclusively represent the detected setup type.

If the intention is for the score to distinguish breakout setups from retracement setups, the scoring logic should be adjusted.

---

# 19. Volume Score

Maximum:

```text
20 points
```

Current scoring:

| Volume Ratio | Points |
| -----------: | -----: |
|      >= 3.0× |     20 |
|      >= 2.0× |     15 |
|      >= 1.5× |     10 |
|      >= 1.2× |      5 |
|        <1.2× |      0 |

The signal thresholds and score thresholds are deliberately different.

A breakout requires at least 1.5× volume, while a retracement recovery requires at least 1.2×.

---

# 20. Trend Score

Maximum:

```text
15 points
```

Points:

```text
Close > EMA200 → 5
EMA50 > EMA200 → 5
EMA20 > EMA50 → 5
```

Because the main candidate filter already requires:

```text
Close > EMA50
EMA20 > EMA50
EMA50 > EMA200
```

most qualifying candidates will already satisfy a substantial portion of this score.

---

# 21. Closing Strength Score

Maximum:

```text
10 points
```

Points:

```text
Candle body >= 1%
    → 5 points

Close position >= 0.75
    → 5 points
```

This attempts to reward strong daily candles closing near their highs.

---

# 22. Momentum Score

Maximum:

```text
10 points
```

Points:

```text
20-day return > 5%
    → 5

60-day return > 10%
    → 5
```

This rewards stocks showing positive recent momentum.

---

# 23. Retracement Quality Score

Maximum:

```text
10 points
```

Conditions:

```text
Retracement between 5% and 20%
```

Then:

```text
Retracement <= 15%
    → 5 points

Close > Previous Day High
    → 5 points
```

This favors relatively controlled pullbacks followed by a recovery signal.

---

# 24. EMA50 Score

Maximum:

```text
5 points
```

Condition:

```text
Close > EMA50
```

Because Close > EMA50 is already part of the established-uptrend filter, qualifying stocks normally receive these 5 points.

---

# 25. Liquidity Score

Maximum:

```text
5 points
```

Condition:

```text
20-day average traded value >= ₹20 crore
```

Again, this is also a hard filter.

Therefore, qualifying stocks normally receive the full 5 liquidity points.

---

# 26. Trade Plan

## Configuration

```python
MIN_RISK_REWARD = 2.0

MAX_HOLDING_DAYS = 60

STOP_ATR_MULTIPLIER = 0.5

MIN_RISK_PERCENT = 2.0

MAX_TARGET_PERCENT = 30.0
```

---

# 27. Entry

The current implementation uses:

```text
Entry = Latest Available Close
```

This is a research convention.

It does **not** mean an actual trade can necessarily be entered at that exact price.

If the scan is performed after the market closes and the trade is entered on the following session, actual execution can differ significantly.

---

# 28. Stop Loss

The stop is:

```text
Previous 20-Day Swing Low
-
0.5 × ATR14
```

Formula:

```python
stop_loss = swing_low - ATR14 × 0.5
```

This attempts to place the stop below recent price structure with an ATR-based buffer.

---

# 29. Minimum Risk Adjustment

The system calculates:

```text
Downside %
=
(Entry - StopLoss) / Entry × 100
```

If the downside is below 2%, it adjusts the stop so that the calculated risk is at least 2%.

This is important because an extremely tight stop can make the calculated 2R target unrealistically close.

---

# 30. Target

The minimum target is:

```text
Entry + Risk × 2
```

The system also looks at the previous 52-week high.

The target becomes the greater of:

```text
2R
Previous 52-week high
```

Then it applies:

```text
Maximum target = Entry × 1.30
```

Therefore:

```text
Target
=
min(
    max(2R, Previous 52W High),
    Entry × 1.30
)
```

---

# 31. Risk/Reward

The calculation is:

```text
Risk
=
Entry - StopLoss

Reward
=
Target - Entry

Risk/Reward
=
Reward / Risk
```

Candidates below:

```text
2.0 : 1
```

are rejected.

---

# 32. Maximum Holding Period

The intended maximum holding period is:

```text
60 trading days
```

This is a planning constraint.

The current code calculates and displays the value but does not itself manage an open position or automatically exit after 60 days.

---

# 33. Candidate Qualification Pipeline

For each stock:

```text
1. Extract OHLCV
        ↓
2. Remove missing OHLCV rows
        ↓
3. Check minimum history
        ↓
4. Calculate indicators
        ↓
5. Apply price filter
        ↓
6. Apply liquidity filter
        ↓
7. Check established uptrend
        ↓
8. Detect breakout
        ↓
9. Detect retracement recovery
        ↓
10. Require at least one setup
        ↓
11. Calculate score
        ↓
12. Calculate trade plan
        ↓
13. Require minimum 2R
        ↓
14. Return candidate
```

---

# 34. Ranking

After all stocks are analyzed, the results are sorted by:

```text
Score DESC
RiskReward DESC
VolumeRatio DESC
```

Therefore:

### First priority

Highest setup-quality score.

### Second priority

Highest risk/reward.

### Third priority

Highest relative volume.

---

# 35. Output

The program displays:

## Primary Information

```text
Rank
Symbol
Setup
Score
Grade
Close
Entry
Target
Upside%
StopLoss
Downside%
R:R
```

## Secondary Information

```text
MaxDays
VolRatio
Retrace%
52W Upside%
Momentum
Trend
Breakout
Volume
CloseStr
RetraceQ
EMA50Score
LiquidityScore
Return20
Return60
AvgValueCr
```

---

# 36. Terminal Display

The program dynamically checks the terminal width.

If the entire table cannot fit, it divides the output into horizontal sections.

For example:

```text
TABLE 1/3

Rank Symbol Setup Score Grade Close Entry Target ...

TABLE 2/3

Rank Symbol MaxDays VolRatio Retrace% ...

TABLE 3/3

Rank Symbol Momentum Trend Breakout Volume ...
```

The Rank and Symbol columns are retained across sections so the rows can be matched.

---

# 37. Error Handling

`analyze_stock()` currently catches all exceptions:

```python
except Exception:
    return None
```

This prevents one problematic stock from terminating the entire scan.

However, this approach has a major debugging disadvantage.

An unexpected programming error can be silently converted into:

```text
None
```

and the stock simply disappears from the results.

For development and testing, it would be better to log exceptions, for example:

```text
Symbol XYZ.NS
Error: ...
```

while still allowing the remaining stocks to be processed.

---

# 38. Important Implementation Observations

The current implementation is functional, but several areas should be reviewed before treating the strategy as production-ready.

## 38.1 One-Year Data vs 252-Day High

The strategy requests approximately one year of data but calculates a 252-session high.

This can result in insufficient data for the 52-week-high calculation.

### Recommended improvement

Request at least:

```text
2 years
```

of daily data, especially for robustness around holidays, missing observations, IPOs and data gaps.

---

## 38.2 Current Nifty 500 vs Historical Backtesting

The current universe is refreshed from today's Nifty 500 constituents.

If this same universe is used to backtest historical performance, the results can suffer from **survivorship bias**.

A proper historical backtest should reconstruct the Nifty 500 membership as it existed on each historical date.

---

## 38.3 Entry at Closing Price

The strategy describes:

```text
Entry = Latest Close
```

But a live implementation cannot know the final closing price before the session ends.

If the signal is generated after market close and the actual order is placed the next day, the execution price may differ.

A more realistic backtest should define:

```text
Signal generated at Day T close
Entry executed at Day T+1 open
```

or explicitly simulate another execution rule.

---

## 38.4 Look-Ahead Bias

The current breakout calculation correctly uses:

```python
shift(1)
```

before calculating the previous 20-day high.

This is good because today's high is excluded from the breakout reference.

The same principle should be maintained throughout any future backtesting implementation.

---

## 38.5 Target Based on Previous 52-Week High

Using the previous 52-week high as a target is mechanically simple but conceptually important.

If the previous high represents major resistance, assuming that price will reach it may not be justified.

The code correctly treats it as a calculated target rather than an expected return.

---

## 38.6 Score Redundancy

Some scoring components overlap with hard filters.

For example:

```text
Close > EMA50
```

is both:

* a hard trend requirement
* a 5-point EMA50 score

Likewise liquidity is both:

* a hard filter
* a 5-point score

This means these dimensions do not provide much differentiation among qualifying stocks.

The score is therefore not a completely independent measure of setup quality.

---

# 39. Recommended Research Enhancements

Before relying on the ranking for real trading, the next development stage should be a proper backtesting engine.

It should measure:

```text
Number of trades
Win rate
Average win
Average loss
Profit factor
Expectancy
Maximum drawdown
CAGR
Sharpe ratio
Sortino ratio
Average holding period
Median holding period
Maximum consecutive losses
```

It should also compare:

```text
Momentum Continuation
vs
Nifty 500
vs
Nifty 500 TRI
vs
Simple buy-and-hold
```

---

# 40. Backtesting Requirements

A valid historical test should avoid:

### Look-ahead bias

No future information may influence a historical signal.

### Survivorship bias

Historical constituents should be used rather than today's constituents.

### Execution bias

Entry and exit prices should reflect realistic execution.

### Corporate-action problems

Splits, bonuses and other corporate actions must be handled appropriately.

### Transaction costs

The test should account for:

* Brokerage
* STT
* Exchange charges
* GST
* Stamp duty
* Slippage
* Taxes where applicable

---

# 41. Suggested Backtest Model

A practical initial model:

```text
Day T:
    Calculate signal after market close

Day T+1:
    Enter at realistic executable price

During holding period:
    Monitor stop loss
    Monitor target

Exit when:
    Stop loss hit
    OR target hit
    OR maximum holding period reached
```

If both target and stop appear to be hit on the same daily candle, the backtest must use a conservative assumption or intraday data.

Using only daily OHLC data makes the exact order of intraday events unknowable.

---

# 42. Portfolio-Level Considerations

Ranking individual stocks is not the same as constructing a portfolio.

A future portfolio layer should define:

```text
Maximum number of simultaneous positions
Maximum capital per position
Maximum portfolio risk
Maximum sector exposure
Maximum correlation
Position sizing
Cash allocation
Re-entry rules
```

For example, selecting the top five stocks does not automatically mean all five should receive equal capital.

---

# 43. Position Sizing

A future version could calculate position size based on risk.

Example:

```text
Capital available = ₹100,000

Maximum trade risk = 1%

Maximum monetary risk = ₹1,000
```

If:

```text
Entry = ₹500
Stop = ₹475

Risk/share = ₹25
```

Then:

```text
Position size
=
₹1,000 / ₹25
=
40 shares
```

This produces a risk-based position rather than simply investing an arbitrary amount.

---

# 44. Strategy Strengths

The current design has several strengths:

* Clear mathematical rules
* No subjective chart interpretation
* Explicit trend definition
* Explicit breakout definition
* Volume confirmation
* Liquidity filter
* Defined stop
* Defined target
* Minimum risk/reward
* Reproducible ranking
* Nifty 500 universe
* No fundamental-data dependency
* Explicit research disclaimer

---

# 45. Strategy Weaknesses

Potential weaknesses include:

* Momentum signals can fail during market-wide corrections.
* Breakouts can become false breakouts.
* High volume does not necessarily mean buying pressure.
* A 5–20% retracement range is arbitrary until empirically validated.
* EMA relationships are backward-looking.
* The scoring weights are manually selected.
* Several score components overlap with hard filters.
* Daily OHLC data cannot always determine intraday stop/target order.
* The current trade plan does not model transaction costs.
* Today's Nifty 500 universe is unsuitable for unbiased historical backtesting.
* A 60-day maximum holding period has not been demonstrated to be optimal.

These are research questions rather than assumptions that should be treated as proven.

---

# 46. Recommended Development Roadmap

## Phase 1 — Current Scanner

```text
Nifty 500
   ↓
Technical Indicators
   ↓
Setup Detection
   ↓
Ranking
   ↓
Trade Plan
```

## Phase 2 — Historical Backtesting

Add:

```text
Historical Universe
Historical Signals
Entry Simulation
Stop Simulation
Target Simulation
Transaction Costs
Performance Metrics
```

## Phase 3 — Portfolio Simulation

Add:

```text
Position Sizing
Capital Management
Concurrent Positions
Sector Exposure
Portfolio Drawdown
```

## Phase 4 — Paper Trading

Run the strategy without real capital and record:

```text
Signal Date
Entry
Actual Execution
Stop
Target
Exit
Return
Holding Period
Reason for Exit
```

## Phase 5 — Live Decision Support

Only after adequate validation:

```text
Daily Data
    ↓
Scanner
    ↓
Rank
    ↓
Manual Review
    ↓
Trade Decision
```

The system should remain decision-support software rather than blindly executing trades.

---

# 47. Configuration Reference

| Parameter                     | Default | Purpose                     |
| ----------------------------- | ------: | --------------------------- |
| TOP_N                         |      20 | Number of displayed stocks  |
| MIN_PRICE                     |    ₹100 | Minimum price               |
| MIN_AVG_TRADED_VALUE_CRORE    |  ₹20 Cr | Minimum liquidity           |
| BREAKOUT_LOOKBACK             |      20 | Breakout period             |
| BREAKOUT_VOLUME_MULTIPLIER    |    1.5× | Breakout volume requirement |
| STRONG_VOLUME_MULTIPLIER      |    2.0× | Currently unused            |
| MIN_BREAKOUT_BODY_PERCENT     |      1% | Strong candle threshold     |
| CLOSE_POSITION_THRESHOLD      |    0.75 | Close near high             |
| RETRACEMENT_LOOKBACK          |      60 | Swing-high period           |
| MIN_RETRACEMENT_PERCENT       |      5% | Minimum pullback            |
| MAX_RETRACEMENT_PERCENT       |     20% | Maximum pullback            |
| RETRACEMENT_VOLUME_MULTIPLIER |    1.2× | Recovery volume             |
| SHORT_EMA                     |      10 | EMA10                       |
| FAST_EMA                      |      20 | EMA20                       |
| MEDIUM_EMA                    |      50 | EMA50                       |
| LONG_EMA                      |     200 | EMA200                      |
| MIN_RISK_REWARD               |     2.0 | Minimum R:R                 |
| MAX_HOLDING_DAYS              |      60 | Maximum intended holding    |
| STOP_ATR_MULTIPLIER           |     0.5 | ATR stop buffer             |
| MIN_RISK_PERCENT              |      2% | Minimum calculated risk     |
| MAX_TARGET_PERCENT            |     30% | Target cap                  |

---

# 48. Final Strategy Definition

The complete current strategy can be summarized as:

```text
UNIVERSE
Current Nifty 500
        ↓
PRICE
Close >= ₹100
        ↓
LIQUIDITY
20D Avg Traded Value >= ₹20 Cr
        ↓
TREND
Close > EMA50
EMA20 > EMA50
EMA50 > EMA200
        ↓
CONTINUATION
        ┌─────────────────────────┐
        │                         │
        ▼                         ▼
20-Day Breakout          Retracement Recovery
        │                         │
Close > 20D High          5%–20% retracement
Close > EMA20             Close > EMA50
Volume >= 1.5x            Close > Previous Day High
                          Volume >= 1.2x
        │                         │
        └───────────┬─────────────┘
                    ↓
               SCORE / 100
                    ↓
              TRADE PLAN
                    ↓
                R:R >= 2
                    ↓
                 RANKING
                    ↓
              TOP 20 STOCKS
```

---

# 49. Final Research Principle

The most important distinction in this project is:

```text
SIGNAL QUALITY
        ≠
PROBABILITY OF PROFIT
```

The 100-point score answers:

> "How strongly does this stock satisfy the predefined Momentum Continuation characteristics compared with other qualifying stocks?"

It does **not** answer:

> "What is the probability that this trade will make money?"

That second question can only be investigated through properly designed historical and forward testing.

The next logical stage for the project is therefore **not adding more indicators**. It is validating whether the existing rules and weights actually produce positive risk-adjusted expectancy after realistic execution costs and drawdowns.
