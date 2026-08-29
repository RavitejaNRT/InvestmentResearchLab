# Momentum Edge

## Nifty 500 Short-Term Positional Stock Ranking Engine

**Momentum Edge** is a Python-based technical-analysis and stock-ranking engine designed to identify high-quality short-term positional trading setups from the current **Nifty 500 universe**.

Established Uptrend AND (20-Day Breakout OR Controlled Retracement Recovery) : Momentum Edge — Uptrend + (Breakout OR Recovery)

The system focuses on stocks that are already in an established bullish trend and identifies one of two continuation setups:

```text
ESTABLISHED UPTREND
        AND
(
    20-DAY BREAKOUT
        OR
    CONTROLLED RETRACEMENT RECOVERY
)
```

The program ranks qualifying stocks using a weighted **100-point setup-quality score** and calculates a proposed entry, stop-loss, target, risk/reward ratio, and maximum holding period.

> **Important:** This is a research and decision-support system. It does not predict future returns, guarantee profits, or represent investment advice.

---

## Strategy Overview

The strategy attempts to avoid stocks that are simply starting a new trend or trading randomly.

Instead, it looks for:

### 1. Established Bullish Trend

A stock must satisfy:

* Close > EMA50
* EMA20 > EMA50
* EMA50 > EMA200

This establishes the basic structure:

```text
Price
  >
EMA20
  >
EMA50
  >
EMA200
```

### 2. Continuation Setup

Once the established trend is confirmed, the stock must satisfy **either**:

#### A. 20-Day Breakout

* Close > previous 20-day high
* Close > EMA20
* Volume >= 1.5 × 20-day average volume

#### B. Controlled Retracement Recovery

* Retracement from recent 60-day high between 5% and 20%
* Close > EMA50
* Close > previous day's high
* Volume >= 1.2 × 20-day average volume

---

## Ranking System

Qualifying stocks receive a maximum score of **100 points**.

| Component           |  Weight |
| ------------------- | ------: |
| Breakout Strength   |      25 |
| Volume Confirmation |      20 |
| Trend Strength      |      15 |
| Closing Strength    |      10 |
| Momentum            |      10 |
| Retracement Quality |      10 |
| EMA50 Position      |       5 |
| Liquidity           |       5 |
| **Total**           | **100** |

### Score Grades

|  Score | Grade | Interpretation            |
| -----: | :---: | ------------------------- |
| 90–100 |   A+  | Exceptional setup quality |
|  80–89 |   A   | Very strong setup         |
|  70–79 |   B   | Good setup                |
|  60–69 |   C   | Moderate setup            |
|    <60 |   D   | Weak setup                |

The score is a **relative ranking metric**, not a probability of profit or expected return.

---

## Trade Plan

For every qualifying stock, the engine calculates:

### Entry

Latest available closing price.

### Stop Loss

```text
20-day swing low - 0.5 × ATR14
```

A minimum practical risk of 2% is enforced.

### Target

The target is calculated as:

```text
Maximum of:
    2R
    Previous 52-week high
```

The target is capped at **30% above entry**.

Only setups with a minimum **2:1 risk/reward ratio** are retained.

### Maximum Holding Period

**60 trading days**

---

## Liquidity and Price Filters

Before technical setup detection, stocks must satisfy:

```text
Close >= ₹100

20-day average traded value >= ₹20 crore
```

This helps eliminate very low-priced and relatively illiquid candidates.

---

## Data Source

Market data is obtained using:

**Yahoo Finance through `yfinance`**

The program uses daily:

* Open
* High
* Low
* Close
* Volume

The Nifty 500 universe is refreshed before each run.

---

## Processing Pipeline

Each execution follows this sequence:

```text
Refresh Nifty 500 Universe
          ↓
Download Latest Daily OHLCV Data
          ↓
Calculate Technical Indicators
          ↓
Apply Price & Liquidity Filters
          ↓
Establish Bullish Trend
          ↓
Detect 20-Day Breakout
          ↓
Detect Retracement Recovery
          ↓
Calculate Setup Score
          ↓
Calculate Trade Plan
          ↓
Apply Risk/Reward Filter
          ↓
Rank Candidates
          ↓
Display Final Ranking
```

---

## Technical Indicators

The engine calculates:

* EMA10
* EMA20
* EMA50
* EMA200
* 20-day average volume
* 50-day average volume
* 20-day average traded value
* Previous 20-day high
* Previous 60-day high
* Previous 20-day low
* Previous 10-day low
* Previous 52-week high
* ATR14
* 20-day return
* 60-day return
* Candle range
* Candle body
* Candle body percentage
* Closing position within candle
* Recent swing high
* Retracement percentage
* Previous day high

---

## Ranking Priority

Stocks are sorted using:

```text
1. Higher Score
2. Higher Risk/Reward
3. Higher Volume Ratio
```

The default output displays the top **20 candidates**.

---

## Project Structure

A suggested project structure is:

```text
MomentumContinuation/
│
├── momentum_continuation.py
├── trade_data.py
├── universe.py
├── requirements.txt
├── README.md
├── PROJECT_DOCUMENTATION.md
│
├── data/
│
├── output/
│
└── .venv/
```

The exact filenames may differ depending on the implementation.

---

## Requirements

Recommended environment:

* Python 3.10+
* pandas
* numpy
* yfinance

Install dependencies:

```bash
pip install pandas numpy yfinance
```

Or, if a requirements file exists:

```bash
pip install -r requirements.txt
```

---

## Running the Program

Run:

```bash
python momentum_continuation.py
```

The program will:

1. Refresh the Nifty 500 universe.
2. Download market data.
3. Analyze the available stocks.
4. Identify qualifying setups.
5. Rank them.
6. Display the methodology and rules.
7. Display the final ranking tables.

---

## Example Output

The final ranking contains information such as:

```text
Rank  Symbol  Setup                  Score  Grade  Close  Entry  Target  Upside%  StopLoss  Downside%  R:R
1     XYZ     20-DAY BREAKOUT        92     A+     ...
2     ABC     RETRACEMENT RECOVERY   87     A      ...
3     DEF     20-DAY BREAKOUT        82     A      ...
```

Additional columns include:

* Volume ratio
* Retracement %
* 52-week upside
* Momentum score
* Trend score
* Breakout score
* Volume score
* Closing-strength score
* Retracement-quality score
* EMA50 score
* Liquidity score
* 20-day return
* 60-day return
* Average traded value

---

## Important Limitations

The strategy has several important limitations.

### No prediction

A high score does not mean the stock will rise.

### No guaranteed stop execution

The calculated stop-loss is an intended exit level. Overnight gaps and slippage can produce a larger loss.

### Historical indicators are backward-looking

EMA, volume, ATR, breakout and momentum calculations are based on historical market data.

### Data quality matters

Yahoo Finance data may occasionally contain missing, delayed, revised, or otherwise imperfect information.

### Survivorship bias

If historical testing uses only today's Nifty 500 constituents, stocks that were removed from the index in the past may be excluded. This can make historical results look better than they would have been in real time.

### Transaction costs

Brokerage, STT, exchange charges, GST, stamp duty, slippage and taxes are not automatically reflected in the technical ranking.

### Target methodology

The target is a mechanically calculated price level. It should not be interpreted as an analyst price target or expected return.

---

## Research Philosophy

The objective is not to find the stock that is guaranteed to produce the highest return.

The objective is to create a **consistent and reproducible selection process**:

```text
Trend
  +
Continuation Signal
  +
Volume
  +
Momentum
  +
Liquidity
  +
Defined Risk
  =
Ranked Trading Opportunity
```

The system should therefore be evaluated using historical backtesting and forward paper trading rather than by looking at individual successful signals.

---

## Disclaimer

This software is provided for educational and research purposes.

It does not constitute financial, investment, trading, tax, or legal advice.

Past performance does not guarantee future results.

The user is responsible for independently evaluating any trading decision and its associated risks.
