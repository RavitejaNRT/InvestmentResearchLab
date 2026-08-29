# Momentum Continuation (MC)

## Nifty 500 Short-Term Positional Stock Ranking Engine

Momentum Continuation (MC) is a Python-based research and decision-support system designed to identify and rank **Nifty 500 stocks showing a strong bullish momentum continuation structure**.

The strategy is intentionally designed around **one setup**, not separate breakout and retracement strategies.

### Core Setup

A stock qualifies only when the following sequence occurs:

```text
Established Uptrend
        ↓
20-Day Breakout
        ↓
Controlled Retracement
        ↓
Bullish Recovery
```

In logical form:

```text
Established Uptrend
AND
20-Day Breakout
AND
Controlled Retracement Recovery
```

The breakout and retracement are therefore **sequential phases of the same Momentum Continuation setup**.

---

# Strategy Objective

The objective is to identify stocks that:

1. Are already in an established bullish trend.
2. Break above a meaningful 20-day resistance level.
3. Successfully retrace after the breakout.
4. Keep the retracement controlled rather than suffering a major trend breakdown.
5. Show renewed bullish strength during the recovery.
6. Have sufficient volume and liquidity.
7. Offer a minimum acceptable risk/reward profile.

The system ranks qualifying stocks using a **100-point setup-quality score**.

> The score is a relative ranking metric. It is not a probability of profit, expected return, or prediction of future performance.

---

# Setup Logic

## Phase 1 — Established Uptrend

The stock must already be in a bullish trend.

Required conditions:

```text
Close > EMA50
EMA20 > EMA50
EMA50 > EMA200
```

This establishes the basic trend structure:

```text
Price
  ↓
EMA20
  ↓
EMA50
  ↓
EMA200
```

The purpose is to avoid attempting to trade against the primary trend.

---

# Phase 2 — Fresh 20-Day Breakout

After the stock is already in an established uptrend, it must produce a fresh breakout.

Required conditions:

```text
Close > Previous 20-Day High
Close > EMA20
EMA20 > EMA50
Volume >= 1.5 × 20-Day Average Volume
```

The breakout must therefore have both:

* Price confirmation
* Volume confirmation

A breakout without sufficient volume does not qualify.

---

# Phase 3 — Controlled Retracement

The strategy does **not** buy the initial breakout immediately.

After a qualifying breakout, the stock must subsequently experience a controlled retracement.

The retracement should be:

```text
5% to 20%
```

from the relevant post-breakout swing high.

The purpose of this phase is to identify stocks that:

* Break out strongly
* Consolidate or pull back
* Avoid excessive damage
* Maintain their broader bullish structure

---

# Phase 4 — Bullish Recovery

The retracement must then be followed by a bullish recovery.

Required recovery conditions:

```text
Established Uptrend
AND
Retracement = 5%–20%
AND
Close > EMA50
AND
Close > Previous Day High
AND
Volume >= 1.2 × 20-Day Average Volume
```

This creates the complete sequence:

```text
             20-Day Breakout
                    ▲
                    │
                    │
             ┌──────┴──────┐
             │             │
      Established       Strong
        Uptrend         Volume
             │
             ▼
       Controlled
       Retracement
          5–20%
             │
             ▼
      Bullish Recovery
             │
             ▼
       QUALIFIED MC
          SETUP
```

---

# Important Strategy Change

Breakout and retracement are **not independent setups**.

The strategy does **not** use:

```text
Breakout OR Retracement
```

Instead, the required sequence is:

```text
Uptrend
AND
Breakout
AND
Retracement
AND
Recovery
```

This is deliberately more selective.

A stock that has only:

```text
Uptrend + Breakout
```

does **not** qualify.

A stock that has only:

```text
Uptrend + Retracement + Recovery
```

does **not** qualify.

The stock must demonstrate the complete momentum-continuation sequence.

---

# Ranking System

Every qualifying stock receives a maximum score of **100 points**.

| Component           | Maximum |
| ------------------- | ------: |
| Momentum Strength   |      20 |
| Volume Confirmation |      20 |
| Trend Strength      |      20 |
| Closing Strength    |      15 |
| Price Strength      |      10 |
| EMA50 Position      |       5 |
| Liquidity           |       5 |
| Recovery Quality    |       5 |
| **Total**           | **100** |

---

## 1. Momentum Strength — 20 Points

Measures:

* 20-trading-day return
* 60-trading-day return

Higher positive momentum receives more points.

The purpose is to distinguish strong momentum stocks from stocks that technically qualify but have weak price movement.

---

## 2. Volume Confirmation — 20 Points

Measures current volume relative to the 20-day average.

| Volume Ratio | Points |
| -----------: | -----: |
|       ≥ 3.0× |     20 |
|       ≥ 2.5× |     17 |
|       ≥ 2.0× |     15 |
|       ≥ 1.5× |     10 |
|       ≥ 1.2× |      5 |
|       < 1.2× |      0 |

Volume is one of the most heavily weighted factors because momentum without participation can be less convincing.

---

## 3. Trend Strength — 20 Points

The trend score evaluates EMA alignment.

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

---

## 4. Closing Strength — 15 Points

Measures the quality of the latest daily candle.

Two characteristics are considered:

### Candle Body

The candle should have a meaningful body.

Minimum body:

```text
1%
```

### Close Position

The closing price should be in the upper 25% of the day's range.

```text
ClosePosition >= 0.75
```

Maximum:

```text
15 points
```

---

# 5. Price Strength — 10 Points

Measures proximity to the previous 52-week high.

Stocks trading close to or above their previous 52-week high receive more points.

| Distance from Previous 52W High | Points |
| ------------------------------: | -----: |
|                   At/above high |     10 |
|                            ≤ 5% |      9 |
|                           ≤ 10% |      7 |
|                           ≤ 15% |      5 |
|                           ≤ 20% |      3 |
|                           > 20% |      0 |

---

# 6. EMA50 Position — 5 Points

A stock receives:

```text
5 points
```

when:

```text
Close > EMA50
```

This reinforces the requirement that the stock remains above an important intermediate trend level.

---

# 7. Liquidity — 5 Points

The system requires sufficient trading liquidity.

Minimum:

```text
20-day average traded value >= ₹20 crore
```

Traded value is calculated as:

```text
Close × Volume
```

and converted into ₹ crore.

---

# 8. Recovery Quality — 5 Points

The recovery component evaluates the controlled retracement.

|   Retracement | Points |
| ------------: | -----: |
|        5%–10% |      5 |
|      >10%–15% |      4 |
|      >15%–20% |      2 |
| Outside range |      0 |

A moderate retracement receives the highest score.

---

# Score Grades

|  Score | Grade | Interpretation            |
| -----: | :---: | ------------------------- |
| 90–100 |   A+  | Exceptional setup quality |
|  80–89 |   A   | Very strong setup         |
|  70–79 |   B   | Good setup                |
|  60–69 |   C   | Moderate setup            |
|    <60 |   D   | Weak setup                |

The grade is for **ranking convenience only**.

It should not be interpreted as a probability of success.

---

# Trade Plan

For every qualifying stock, the system calculates:

* Entry
* Stop Loss
* Target
* Upside %
* Downside %
* Risk/Reward
* Maximum holding period

---

## Entry

The proposed entry is:

```text
Latest available closing price
```

The system is intended for positional research rather than guaranteed execution at the exact closing price.

---

# Stop Loss

The initial stop is based on the previous 20-day swing low and ATR14.

Formula:

```text
Stop Loss =
Previous 20-Day Swing Low
-
0.5 × ATR14
```

A minimum practical risk threshold of:

```text
2%
```

is also applied.

---

# Target

The initial target is calculated using:

```text
Minimum Target = Entry + (Risk × 2)
```

The system then considers the previous 52-week high as a potential resistance/target level.

The target is constrained by:

```text
Maximum Target = Entry × 1.30
```

Therefore the maximum target distance is:

```text
30%
```

---

# Minimum Risk/Reward

Only setups satisfying:

```text
Risk/Reward >= 2:1
```

are retained.

This means the potential reward must be at least twice the calculated risk.

---

# Maximum Holding Period

Maximum intended holding period:

```text
60 trading days
```

If the setup does not reach the target or trigger the stop within the intended holding period, the position should be reviewed according to the strategy's exit rules.

---

# Universe

The system uses the:

```text
Current Nifty 500 constituents
```

The universe is refreshed every time the program runs.

This is important because index constituents change over time.

---

# Data Source

Market data is obtained through:

```text
Yahoo Finance
```

using:

```text
yfinance
```

The system uses daily:

* Open
* High
* Low
* Close
* Volume

data.

---

# Minimum Data Requirements

The system requires at least:

```text
200 trading days
```

of historical data for a stock to be analyzed.

The strategy also uses longer lookback calculations such as:

* 20 trading days
* 60 trading days
* 200 EMA
* 252 trading days for 52-week calculations

---

# Program Workflow

Every execution follows this process:

```text
START
  │
  ▼
Refresh Nifty 500 Universe
  │
  ▼
Download Latest Daily OHLCV Data
  │
  ▼
Calculate Technical Indicators
  │
  ▼
Check Minimum Price
  │
  ▼
Check Liquidity
  │
  ▼
Check Established Uptrend
  │
  ▼
Check 20-Day Breakout
  │
  ▼
Wait for / Identify Controlled Retracement
  │
  ▼
Check Bullish Recovery
  │
  ▼
Calculate 100-Point Score
  │
  ▼
Calculate Entry / Stop / Target
  │
  ▼
Check Minimum 2:1 Risk/Reward
  │
  ▼
Rank Qualifying Stocks
  │
  ▼
Display Top Candidates
  │
  ▼
Display Ranking Methodology
  │
  ▼
END
```

---

# Ranking Priority

When multiple stocks qualify, they are ranked using:

### 1. Momentum Continuation Score

Higher score ranks first.

### 2. Risk/Reward

If scores are equal, higher R:R ranks first.

### 3. Volume Ratio

If both score and R:R are equal, higher volume confirmation ranks first.

In simplified form:

```text
Score ↓
   ↓
R:R ↓
   ↓
Volume Ratio ↓
```

---

# Output

The program displays the highest-ranked qualifying Nifty 500 stocks.

Default:

```text
TOP 20
```

The primary output includes:

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

Additional information includes:

* Volume ratio
* Retracement %
* 52-week upside
* Momentum score
* Trend score
* Volume score
* Closing strength
* Price strength
* Recovery quality
* EMA50 score
* Liquidity score
* 20-day return
* 60-day return
* Average traded value

---

# Output Layout

The program automatically detects the terminal width.

If the terminal is wide enough, the output is displayed in a single table.

If the terminal is narrow, the columns are split into multiple horizontal tables.

For example:

```text
TABLE 1/2
Rank Symbol Score Grade Close Entry Target Upside% StopLoss Downside% R:R

TABLE 2/2
Rank Symbol MaxDays VolRatio Retrace% 52W Upside% Momentum Trend ...
```

Rank and Symbol are repeated so that each section can be interpreted independently.

---

# Configuration

Important parameters are centralized near the top of the Python program.

Example:

```python
TOP_N = 20

MIN_PRICE = 100

MIN_HISTORY_DAYS = 200

MIN_AVG_TRADED_VALUE_CRORE = 20

BREAKOUT_LOOKBACK = 20

BREAKOUT_VOLUME_MULTIPLIER = 1.5

RETRACEMENT_LOOKBACK = 60

MIN_RETRACEMENT_PERCENT = 5.0

MAX_RETRACEMENT_PERCENT = 20.0

RETRACEMENT_VOLUME_MULTIPLIER = 1.2

SHORT_EMA = 10

FAST_EMA = 20

MEDIUM_EMA = 50

LONG_EMA = 200

MIN_RISK_REWARD = 2.0

MAX_HOLDING_DAYS = 60

STOP_ATR_MULTIPLIER = 0.5

MIN_RISK_PERCENT = 2.0

MAX_TARGET_PERCENT = 30.0
```

These values can be changed for research and backtesting.

---

# Installation

Create and activate a virtual environment:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install pandas numpy yfinance
```

---

# Running the Program

Run:

```bash
python momentum_continuation.py
```

Replace `momentum_continuation.py` with the actual filename used in the project.

---

# Example Interpretation

Suppose a stock has:

```text
Established Uptrend       YES
20-Day Breakout           YES
Breakout Volume           1.8×
Controlled Retracement    8%
Recovery                   YES
Recovery Volume            1.4×
Score                      87
R:R                        2.6
```

The stock qualifies because the complete sequence has occurred:

```text
Uptrend
   ↓
Breakout
   ↓
8% Controlled Retracement
   ↓
Bullish Recovery
   ↓
Momentum Continuation
```

A different stock with:

```text
Established Uptrend       YES
20-Day Breakout           YES
Controlled Retracement    NO
```

does **not** qualify.

Likewise:

```text
Established Uptrend       YES
Controlled Retracement    YES
Recovery                   YES
20-Day Breakout            NO
```

does **not** qualify.

This is intentional.

---

# Why the Strategy Uses a Sequence

The central hypothesis is that a strong continuation candidate may be more interesting when it demonstrates the following progression:

```text
Trend
  ↓
Expansion
  ↓
Profit-taking / Pullback
  ↓
Demand returns
  ↓
Continuation
```

The breakout demonstrates expansion.

The retracement tests whether the stock can absorb profit-taking without destroying the trend.

The recovery demonstrates renewed buying interest.

However, this is a **research hypothesis**, not an established guarantee of superior returns.

---

# Important Research Considerations

## 1. Avoid Look-Ahead Bias

The strategy must only use information that was available at the time of the signal.

For example:

```python
shift(1)
```

is used where appropriate to exclude today's candle from previous-high calculations.

This prevents today's price from being accidentally used to define its own breakout level.

---

## 2. Yahoo Finance Data Limitations

Yahoo Finance is useful for research, but it should not automatically be treated as institutional-grade market data.

Potential issues include:

* Data corrections
* Delays
* Corporate-action adjustments
* Missing observations
* Temporary download failures
* Changes in historical data

For serious backtesting, data quality should be independently validated.

---

# Backtesting Recommendation

Before using the strategy with real capital, test:

### 1. Historical performance

Measure:

* CAGR
* Win rate
* Average return
* Median return
* Maximum drawdown
* Profit factor
* Expectancy
* Sharpe ratio
* Average holding period

### 2. Signal frequency

Determine:

```text
How many qualifying setups occur per year?
```

A strategy that produces very few signals may not have enough observations to establish confidence.

### 3. Market-regime performance

Test separately during:

* Bull markets
* Bear markets
* Sideways markets
* High-volatility periods
* Low-volatility periods

### 4. Transaction costs

Include:

* Brokerage
* STT
* Exchange charges
* GST
* SEBI charges
* Stamp duty
* Slippage

A backtest that ignores these costs can overstate actual returns.

---

# Survivorship Bias

Because the system refreshes the **current Nifty 500 universe**, historical backtests must be careful about survivorship bias.

Using today's Nifty 500 constituents to test historical periods can incorrectly exclude companies that were previously in the index but later left it.

For rigorous historical testing, the universe should ideally use the constituents that actually existed on each historical date.

---

# Overfitting Warning

The strategy contains several configurable thresholds:

```text
20-day breakout
1.5× volume
5–20% retracement
1.2× recovery volume
EMA10
EMA20
EMA50
EMA200
2R minimum
30% target cap
60-day holding period
```

Changing these parameters repeatedly until historical returns look excellent can create **overfitting**.

A strong backtest does not automatically mean a strong live strategy.

The preferred approach is:

```text
Define rules
    ↓
Backtest
    ↓
Out-of-sample test
    ↓
Walk-forward validation
    ↓
Paper trade
    ↓
Live deployment
```

---

# Risk Disclaimer

Momentum Continuation is a research and decision-support system.

It does not:

* Predict future stock prices.
* Guarantee profits.
* Guarantee a 2:1 realized reward/risk outcome.
* Guarantee execution at the calculated entry.
* Guarantee execution at the calculated stop loss.

A stop loss is an **intended exit level**, not a guaranteed maximum loss.

Overnight gaps, illiquidity and slippage can cause actual execution to occur significantly away from the intended stop.

---

# Project Philosophy

The system is designed around five principles:

```text
Simple
   +
Objective
   +
Rule-Based
   +
Risk-Aware
   +
Testable
```

The goal is not to predict which stock will rise tomorrow.

The goal is to systematically identify stocks that currently exhibit a predefined combination of:

```text
Bullish Trend
      +
Breakout
      +
Controlled Retracement
      +
Bullish Recovery
      +
Volume
      +
Liquidity
      +
Acceptable Risk/Reward
```

and rank them consistently.

---

# Final Strategy Definition

The complete Momentum Continuation strategy can be summarized as:

```text
QUALIFY STOCK

IF

    Established Uptrend

AND

    Fresh 20-Day Breakout

AND

    Controlled 5%–20% Retracement

AND

    Bullish Recovery

AND

    Sufficient Volume

AND

    Sufficient Liquidity

AND

    Risk/Reward >= 2:1

THEN

    Calculate 100-Point Score
    Calculate Entry
    Calculate Stop Loss
    Calculate Target
    Rank Candidate

ELSE

    Reject
```

### Core Formula

```text
Momentum Continuation
=
Established Uptrend
AND
20-Day Breakout
AND
Controlled Retracement Recovery
```

This is the **single setup** implemented by the system.
