# Momentum Continuation (MC)

## Nifty 500 Short-Term Positional Stock Ranking Engine

---

## 1. Project Overview

**Momentum Continuation (MC)** is a Python-based research and decision-support system designed to identify and rank Nifty 500 stocks exhibiting a strong bullish momentum-continuation structure.

The system is designed for **short-term positional trading**, with an intended maximum holding period of **60 trading days**.

The core philosophy is:

> **Strong trend → fresh breakout → controlled retracement → bullish recovery**

The system does not treat breakout and retracement as two independent strategies.

Instead, they form a **single sequential Momentum Continuation setup**.

### Core Setup

```text
Established Uptrend
        AND
20-Day Breakout
        followed by
Controlled Retracement
        followed by
Bullish Recovery
```

Only stocks satisfying the complete sequence qualify.

---

# 2. Objective

The objective of the project is to systematically answer:

> **Which Nifty 500 stocks currently have the strongest evidence of momentum continuation, and what is the corresponding entry, stop-loss and target?**

The program:

1. Refreshes the current Nifty 500 universe.
2. Downloads the latest daily OHLCV data.
3. Calculates technical indicators.
4. Identifies established bullish trends.
5. Detects a fresh 20-day breakout.
6. Detects a subsequent controlled retracement.
7. Detects bullish recovery from that retracement.
8. Calculates a weighted setup-quality score.
9. Calculates Entry, Stop Loss and Target.
10. Applies minimum Risk/Reward requirements.
11. Ranks qualifying stocks.
12. Displays the final candidates at the end of the program.

---

# 3. Important Strategy Definition

The Momentum Continuation strategy consists of **one setup**.

It is NOT:

```text
Uptrend AND
(
    Breakout
    OR
    Retracement
)
```

Instead, it is:

```text
Uptrend
AND
Breakout
AND
Retracement
AND
Recovery
```

The sequence is important.

### Required sequence

```text
          Established Uptrend
                  │
                  ▼
          20-Day Breakout
                  │
                  ▼
       Controlled Retracement
             5% – 20%
                  │
                  ▼
        Bullish Recovery
                  │
                  ▼
             Qualification
```

The purpose of this sequence is to avoid buying every breakout or every pullback.

The strategy attempts to identify stocks where:

* the long-term trend is already bullish,
* momentum produces a fresh breakout,
* the stock subsequently pauses or retraces in a controlled manner,
* and buyers return with a bullish recovery.

---

# 4. Data Source

Market data is obtained from:

**Yahoo Finance through `yfinance`.**

The system uses daily:

* Open
* High
* Low
* Close
* Volume

data.

The Nifty 500 universe is refreshed before each analysis run.

---

# 5. Project Structure

A typical project structure is:

```text
TradeLens/
│
├── main.py
├── momentum_continuation.py
├── trade_data.py
├── universe.py
├── README.md
├── PROJECT_DOCUMENTATION.md
├── .gitignore
│
└── docs/
    └── PROJECT_DOCUMENTATION.md
```

The exact filenames may differ depending on the implementation.

---

# 6. Strategy Configuration

## Universe

```python
TOP_N = 20
```

The system displays the top 20 qualifying stocks.

---

## Minimum Price

```python
MIN_PRICE = 100
```

Stocks below ₹100 are excluded.

This is primarily intended to reduce very low-priced stocks and improve practical tradability.

---

## Minimum History

```python
MIN_HISTORY_DAYS = 200
```

A stock must have at least 200 trading days of usable history.

This is required because the strategy uses the 200 EMA.

---

## Liquidity Filter

```python
MIN_AVG_TRADED_VALUE_CRORE = 20
```

The stock must have at least:

```text
₹20 crore
```

of 20-day average daily traded value.

Traded value is calculated as:

```text
Close × Volume
```

and converted to ₹ crore.

---

# 7. Technical Indicators

The strategy calculates the following indicators.

## Exponential Moving Averages

```text
EMA10
EMA20
EMA50
EMA200
```

These are used to determine trend alignment.

---

## Volume Averages

```text
20-day average volume
50-day average volume
```

The 20-day average is primarily used for breakout and recovery volume confirmation.

---

## Previous 20-Day High

The current day's high is excluded.

```text
Previous 20-Day High =
maximum high of the previous 20 completed trading days
```

This prevents look-ahead bias.

---

## Previous 52-Week High

The current trading day is excluded.

```text
Previous 52-Week High =
maximum high of previous 252 trading days
```

This is used for price-strength scoring and target calculation.

---

## ATR14

Average True Range over 14 trading days.

ATR is used to provide additional room below the swing low when calculating the stop-loss.

---

## Momentum

The system calculates:

```text
20-day return
60-day return
```

These contribute to the Momentum Strength score.

---

## Candle Strength

The system calculates:

* Candle range
* Candle body
* Candle body percentage
* Close position within the daily range

A close near the daily high is considered stronger bullish closing behavior.

---

# 8. Established Uptrend

A stock must first satisfy the established bullish trend requirement.

### Conditions

```text
Close > EMA50
AND
EMA20 > EMA50
AND
EMA50 > EMA200
```

In simplified form:

```text
Price
  >
EMA20
  >
EMA50
  >
EMA200
```

The actual qualification requires Close > EMA50, while EMA20 > EMA50 > EMA200 establishes the moving-average structure.

---

# 9. Stage 1 — 20-Day Breakout

After establishing the bullish trend, the stock must demonstrate a fresh 20-day breakout.

### Conditions

```text
Close > Previous 20-Day High
AND
Close > EMA20
AND
EMA20 > EMA50
AND
Volume >= 1.5 × 20-Day Average Volume
```

The breakout therefore requires both:

### Price confirmation

```text
Close > Previous 20-Day High
```

and:

### Volume confirmation

```text
Today's Volume >= 1.5 × Average 20-Day Volume
```

This attempts to identify a breakout supported by meaningful participation rather than a price move occurring on weak volume.

---

# 10. Stage 2 — Controlled Retracement

After the breakout, the stock must experience a controlled retracement.

The intended retracement range is:

```text
5% – 20%
```

The retracement is measured from the recent swing high.

### Retracement Formula

```text
Retracement % =
(1 - Current Close / Recent Swing High) × 100
```

The recent swing high is calculated using the previous 60 trading days.

The current trading day is excluded.

---

# 11. Stage 3 — Bullish Recovery

The retracement alone is not sufficient.

The stock must subsequently demonstrate bullish recovery.

### Recovery Conditions

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
Volume >= 1.2 × 20-Day Average Volume
```

The recovery therefore requires:

* controlled retracement,
* price remaining above the 50 EMA,
* bullish price confirmation,
* and above-average volume.

---

# 12. Complete Momentum Continuation Setup

The final setup is:

```text
Established Uptrend
        AND
20-Day Breakout
        AND
Controlled 5%-20% Retracement
        AND
Bullish Recovery
```

Conceptually:

```text
             BULLISH TREND
                   │
                   ▼
          ┌─────────────────┐
          │ 20-Day Breakout │
          └────────┬────────┘
                   │
                   ▼
             Price advances
                   │
                   ▼
          ┌─────────────────┐
          │   Retracement   │
          │     5%-20%      │
          └────────┬────────┘
                   │
                   ▼
          ┌─────────────────┐
          │ Bullish Recovery│
          │ Close > PrevHigh│
          │ Volume confirms │
          └────────┬────────┘
                   │
                   ▼
          MOMENTUM CONTINUATION
```

---

# 13. Why Breakout and Retracement Are Sequential

The strategy deliberately avoids this structure:

```text
Breakout OR Retracement
```

because that would allow a stock to qualify from either condition independently.

Instead, the strategy asks for evidence that momentum has gone through a complete cycle:

```text
Breakout
   ↓
Profit-taking / controlled pullback
   ↓
Demand returns
   ↓
Recovery
```

This is intended to identify continuation rather than simply identify stocks that are already extended.

---

# 14. Ranking Methodology

Every qualifying stock receives a maximum score of:

```text
100 points
```

The score is a **relative setup-quality score**.

It is not:

* probability of profit,
* expected return,
* prediction of future price,
* or guarantee of success.

---

# 15. Score Components

| Component           | Maximum Points |
| ------------------- | -------------: |
| Momentum Strength   |             20 |
| Volume Confirmation |             20 |
| Trend Strength      |             20 |
| Closing Strength    |             15 |
| Price Strength      |             10 |
| EMA50 Position      |              5 |
| Liquidity           |              5 |
| Recovery Quality    |              5 |
| **Total**           |        **100** |

---

# 16. Momentum Strength — 20 Points

Momentum is measured using:

```text
20-day return
60-day return
```

### 20-Day Momentum

| Return | Points |
| ------ | -----: |
| ≥ 15%  |     10 |
| ≥ 10%  |      8 |
| ≥ 5%   |      5 |
| > 0%   |      2 |
| ≤ 0%   |      0 |

### 60-Day Momentum

| Return | Points |
| ------ | -----: |
| ≥ 30%  |     10 |
| ≥ 20%  |      8 |
| ≥ 10%  |      5 |
| > 0%   |      2 |
| ≤ 0%   |      0 |

Maximum:

```text
20 points
```

---

# 17. Volume Confirmation — 20 Points

Current volume is compared with the 20-day average volume.

```text
Volume Ratio =
Today's Volume / 20-Day Average Volume
```

| Volume Ratio | Points |
| ------------ | -----: |
| ≥ 3.0×       |     20 |
| ≥ 2.5×       |     17 |
| ≥ 2.0×       |     15 |
| ≥ 1.5×       |     10 |
| ≥ 1.2×       |      5 |
| < 1.2×       |      0 |

Maximum:

```text
20 points
```

---

# 18. Trend Strength — 20 Points

The trend score consists of four conditions.

| Condition      | Points |
| -------------- | -----: |
| Close > EMA200 |      5 |
| EMA50 > EMA200 |      5 |
| EMA20 > EMA50  |      5 |
| EMA10 > EMA20  |      5 |

Maximum:

```text
20 points
```

This rewards stronger moving-average alignment.

---

# 19. Closing Strength — 15 Points

Closing strength contains two components.

### Candle Body

If:

```text
Candle Body >= 1%
```

the stock receives:

```text
7 points
```

### Close Position

The close must be in the upper 25% of the daily range.

```text
Close Position >= 0.75
```

This contributes:

```text
8 points
```

Maximum:

```text
15 points
```

---

# 20. Price Strength — 10 Points

Price strength measures proximity to the previous 52-week high.

| Distance from 52W High | Points |
| ---------------------- | -----: |
| At/above high          |     10 |
| ≤ 5%                   |      9 |
| ≤ 10%                  |      7 |
| ≤ 15%                  |      5 |
| ≤ 20%                  |      3 |
| > 20%                  |      0 |

The intention is to reward stocks trading near significant highs.

---

# 21. EMA50 Position — 5 Points

If:

```text
Close > EMA50
```

the stock receives:

```text
5 points
```

This is a simple additional confirmation of bullish positioning.

---

# 22. Liquidity — 5 Points

If 20-day average traded value is at least:

```text
₹20 crore
```

the stock receives:

```text
5 points
```

The liquidity filter is also applied before the stock can qualify.

---

# 23. Recovery Quality — 5 Points

Recovery quality rewards controlled retracement depth.

| Retracement   | Points |
| ------------- | -----: |
| 5%–10%        |      5 |
| >10%–15%      |      4 |
| >15%–20%      |      2 |
| Outside range |      0 |

This factor does not create a separate strategy.

It only improves ranking within the Momentum Continuation strategy.

---

# 24. Score Grades

| Score  | Grade | Interpretation            |
| ------ | ----- | ------------------------- |
| 90–100 | A+    | Exceptional setup quality |
| 80–89  | A     | Very strong setup         |
| 70–79  | B     | Good setup                |
| 60–69  | C     | Moderate setup            |
| <60    | D     | Weak setup                |

The grade is a ranking aid and should not be interpreted as a probability of success.

---

# 25. Trade Plan

For each qualifying stock the system calculates:

```text
Entry
Stop Loss
Target
Upside %
Downside %
Risk/Reward
Maximum Holding Days
```

---

# 26. Entry

The proposed entry is:

```text
Latest available closing price
```

Therefore:

```text
Entry = Latest Close
```

This is a research convention.

It does not imply that the next day's market will open at the same price.

---

# 27. Stop Loss

The stop-loss is based on the previous 20-day swing low.

### Formula

```text
Stop Loss =
Previous 20-Day Swing Low
-
0.5 × ATR14
```

The ATR component provides additional room below the swing low.

---

# 28. Minimum Risk

The system uses:

```text
MIN_RISK_PERCENT = 2%
```

If calculated downside risk is below 2%, the stop is adjusted so that the planned risk is at least 2%.

This avoids unrealistically tight stops.

---

# 29. Target

The initial minimum target is:

```text
Entry + 2 × Risk
```

Therefore:

```text
Minimum Target = Entry + 2R
```

If a valid previous 52-week high exists above the entry, it can become the resistance-based target.

The final target is:

```text
max(2R target, previous 52-week high)
```

subject to the maximum target cap.

---

# 30. Maximum Target

The maximum target is:

```text
30% above Entry
```

Therefore:

```text
Maximum Target =
Entry × 1.30
```

The final target cannot exceed this cap.

---

# 31. Risk / Reward

The system requires:

```text
Minimum Risk/Reward = 2:1
```

Formula:

```text
Risk/Reward =
(Target - Entry) /
(Entry - Stop Loss)
```

Any stock producing less than 2:1 is rejected.

---

# 32. Maximum Holding Period

The intended maximum holding period is:

```text
60 trading days
```

This is a positional strategy rather than an intraday strategy.

If the trade has not reached its objective or stop-loss within the intended period, the position should be reviewed according to the trading plan.

---

# 33. Ranking Priority

After all qualifying stocks are identified, they are sorted using:

### Priority 1

```text
Higher Momentum Continuation Score
```

### Priority 2

```text
Higher Risk/Reward
```

### Priority 3

```text
Higher Volume Ratio
```

Therefore:

```text
Score
   ↓
Risk/Reward
   ↓
Volume Ratio
```

determines the final ranking.

---

# 34. Output

The program displays the final results only after the complete analysis has finished.

The output includes:

* Rank
* Symbol
* Score
* Grade
* Close
* Entry
* Target
* Upside %
* Stop Loss
* Downside %
* Risk/Reward
* Maximum holding days
* Volume ratio
* Retracement %
* 52-week upside
* Individual score components
* 20-day return
* 60-day return
* Average traded value

The terminal output is dynamically divided into horizontal table sections depending on terminal width.

The tables are displayed **at the end of the analysis**, after all Nifty 500 stocks have been processed.

---

# 35. Example Output Structure

```text
============================================================
MOMENTUM CONTINUATION (MC)
TOP NIFTY 500 CANDIDATES
============================================================

Terminal width detected: 160 columns
Showing top 20 candidates.
Ranking score maximum: 100/100


TABLE 1/2

Rank Symbol Score Grade Close Entry Target Upside% StopLoss Downside% R:R
---- ------ ----- ----- ----- ----- ------ ------- -------- -------- ----
1    ABC    92    A+    ...
2    XYZ    89    A     ...
3    PQR    86    A     ...


TABLE 2/2

Rank Symbol MaxDays VolRatio Retrace% 52W Upside% Momentum Trend ...
---- ------ ------- -------- --------- ----------- -------- -----
1    ABC    60      ...
2    XYZ    60      ...
3    PQR    60      ...
```

---

# 36. Important Implementation Consideration

The strategy is intended to identify a **sequence**, not merely the current state.

Therefore, future versions should preserve historical event information such as:

```text
Breakout Date
Breakout Price
Breakout Volume Ratio
Post-Breakout High
Retracement Low
Retracement %
Recovery Date
Recovery Volume Ratio
```

This allows the system to verify that the retracement occurred **after the breakout**, rather than simply observing that a stock happens to be 5%–20% below a recent high.

This distinction is important for correctly implementing the sequential strategy.

---

# 37. Look-Ahead Bias

The implementation deliberately excludes the current trading day when calculating historical reference levels.

Examples:

```text
Previous 20-Day High
Previous 52-Week High
Previous 20-Day Low
Previous 10-Day Low
Recent Swing High
```

This prevents today's price from being used to calculate the reference level against which today's price is subsequently compared.

However, backtesting must still ensure that:

* only information available at the decision time is used,
* no future prices influence the entry,
* corporate actions are handled appropriately,
* delisted stocks are considered where possible,
* and transaction costs/slippage are accounted for.

---

# 38. Data Limitations

Yahoo Finance data is useful for research but should not automatically be treated as institutional-grade trading data.

Potential issues include:

* delayed/inconsistent intraday updates,
* historical data adjustments,
* missing observations,
* corporate-action effects,
* occasional download failures,
* ticker changes,
* delisted securities,
* and differences between data vendors.

The system should therefore be considered a **research and decision-support tool**.

---

# 39. Exception Handling

Individual stock analysis is protected so that one problematic symbol does not terminate the entire Nifty 500 analysis.

If an exception occurs during analysis of a stock:

```text
None
```

is returned and the stock is skipped.

This allows the remaining universe to continue processing.

For production-quality research, however, silently ignoring exceptions should eventually be replaced with structured logging so that data problems can be investigated.

---

# 40. Strategy Strengths

The methodology attempts to combine several forms of evidence:

### Trend

```text
EMA20 > EMA50 > EMA200
```

### Breakout

```text
Close > Previous 20-Day High
```

### Participation

```text
Volume confirmation
```

### Controlled Pullback

```text
5%–20% retracement
```

### Recovery

```text
Close > Previous Day High
```

### Price Strength

```text
Near 52-week high
```

### Risk Management

```text
Minimum 2:1 Risk/Reward
```

This makes the methodology more selective than a simple breakout screen.

---

# 41. Potential Weaknesses

The strategy should not be assumed to work simply because it combines many bullish indicators.

Potential weaknesses include:

### 1. Indicator overlap

EMA alignment, momentum, price strength and breakout behavior are partially related.

Therefore, the 100-point score may effectively give multiple points to the same underlying market characteristic.

---

### 2. Volume can be event-driven

A high volume day can result from:

* news,
* block deals,
* corporate announcements,
* index changes,
* earnings,
* or other temporary events.

High volume does not automatically mean sustained institutional accumulation.

---

### 3. Retracement measurement is path-dependent

A stock can move significantly during the 60-day lookback period and still satisfy the current retracement formula.

Therefore, historical event tracking is preferable to using only the current snapshot.

---

### 4. Target construction may be restrictive

Using the greater of 2R and the previous 52-week high, followed by a 30% cap, can produce targets that do not necessarily correspond to actual resistance or realistic price behavior.

This should be validated through backtesting.

---

### 5. Stop-loss sensitivity

A stop based on the previous 20-day low can sometimes be:

* too wide,
* too tight,
* or distorted by a single abnormal candle.

ATR helps but does not eliminate this problem.

---

# 42. Research and Backtesting Requirements

Before using the strategy with real capital, the following should be tested.

## Entry performance

Measure:

* win rate,
* average return,
* median return,
* maximum favorable excursion,
* maximum adverse excursion.

---

## Risk-adjusted performance

Measure:

* Sharpe ratio,
* Sortino ratio,
* maximum drawdown,
* Calmar ratio,
* profit factor.

---

## Trade distribution

Measure:

* number of trades,
* average holding period,
* winners versus losers,
* consecutive losses,
* largest loss,
* largest winner.

---

## Market-regime analysis

The strategy should be evaluated separately during:

```text
Bull markets
Sideways markets
Bear markets
High-volatility periods
Low-volatility periods
```

A strategy that performs well only in strong bull markets should not be assumed to be universally robust.

---

# 43. Transaction Costs

Backtests should include realistic costs such as:

* brokerage,
* STT,
* exchange charges,
* GST,
* SEBI charges,
* stamp duty,
* slippage.

Ignoring transaction costs can materially overstate returns.

---

# 44. Survivorship Bias

Using today's Nifty 500 constituents to backtest historical periods can introduce survivorship bias.

For example:

```text
Current Nifty 500
        ↓
Historical backtest
```

may exclude companies that were previously constituents but later left the index.

A more rigorous historical test should reconstruct the Nifty 500 membership as it existed at each historical date.

---

# 45. Position Sizing

The current ranking engine identifies opportunities but does not necessarily determine optimal position size.

A future risk-management layer could calculate position size using:

```text
Maximum portfolio risk per trade
÷
Risk per share
```

For example:

```text
Position Size =
Maximum Rupee Risk /
(Entry - Stop Loss)
```

This is generally more robust than allocating the same rupee amount to every stock when stop distances vary significantly.

---

# 46. Strategy Philosophy

The project follows a simple principle:

> **Do not try to predict which stock will rise. Instead, rank stocks based on observable evidence of bullish momentum continuation.**

The system therefore focuses on:

```text
Trend
+
Breakout
+
Retracement
+
Recovery
+
Volume
+
Price Strength
+
Risk/Reward
```

rather than attempting to forecast future prices directly.

---

# 47. Safety and Interpretation

The system is a research and decision-support tool.

It does not:

* guarantee profits,
* predict future returns,
* guarantee execution prices,
* guarantee that stop-losses will execute at the intended level,
* or eliminate market risk.

A stop-loss is an intended exit level.

During gaps or extreme volatility, execution can occur materially below the intended stop.

---

# 48. Current Strategy Summary

The complete strategy can be summarized as:

```text
NIFTY 500
    │
    ▼
Price >= ₹100
    │
    ▼
20-Day Average Traded Value >= ₹20 Cr
    │
    ▼
Established Uptrend
    │
    ├── Close > EMA50
    ├── EMA20 > EMA50
    └── EMA50 > EMA200
    │
    ▼
20-Day Breakout
    │
    ├── Close > Previous 20-Day High
    ├── Close > EMA20
    ├── EMA20 > EMA50
    └── Volume >= 1.5× Avg Volume
    │
    ▼
Controlled Retracement
    │
    └── 5%–20%
    │
    ▼
Bullish Recovery
    │
    ├── Close > EMA50
    ├── Close > Previous Day High
    └── Volume >= 1.2× Avg Volume
    │
    ▼
100-Point Ranking
    │
    ▼
Trade Plan
    │
    ├── Entry
    ├── Stop Loss
    ├── Target
    └── Risk/Reward >= 2:1
    │
    ▼
Rank Candidates
    │
    ▼
Display Top 20
```

---

# 49. Configuration Reference

| Parameter              |           Value |
| ---------------------- | --------------: |
| Top candidates         |              20 |
| Minimum price          |            ₹100 |
| Minimum history        |        200 days |
| Minimum traded value   |          ₹20 Cr |
| Breakout lookback      |         20 days |
| Breakout volume        |            1.5× |
| Retracement lookback   |         60 days |
| Minimum retracement    |              5% |
| Maximum retracement    |             20% |
| Recovery volume        |            1.2× |
| Short EMA              |              10 |
| Fast EMA               |              20 |
| Medium EMA             |              50 |
| Long EMA               |             200 |
| ATR                    |              14 |
| Stop ATR multiplier    |             0.5 |
| Minimum risk           |              2% |
| Minimum R:R            |             2:1 |
| Maximum target         |             30% |
| Maximum holding period | 60 trading days |

---

# 50. Final Definition

The official Momentum Continuation setup is:

```text
ESTABLISHED UPTREND

AND

20-DAY BREAKOUT

FOLLOWED BY

CONTROLLED 5%-20% RETRACEMENT

FOLLOWED BY

BULLISH RECOVERY
```

In one line:

```text
Established Uptrend
AND
(20-Day Breakout
     followed by
 Controlled Retracement Recovery)
```

This is the core definition that should remain consistent across:

* the Python implementation,
* documentation,
* backtesting,
* ranking,
* and future versions of TradeLens.

---

## Disclaimer

Momentum Continuation (MC) is a quantitative research and decision-support methodology.

The output is not investment advice and should not be interpreted as a prediction or guarantee of future returns.

Actual trading outcomes may differ because of market volatility, gaps, slippage, liquidity, transaction costs, corporate actions and data-quality limitations.

Any strategy should be independently backtested and validated before being used with real capital.
