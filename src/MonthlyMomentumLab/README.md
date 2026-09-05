# MonthlyMomentumLab

## Production Monthly Momentum + Breakout Research Engine

**MonthlyMomentumLab** is a quantitative equity research and portfolio-signal engine designed for the Indian equity market using the **Nifty 500 universe**.

The system converts daily OHLCV market data into completed monthly bars, calculates momentum, breakout and volume-confirmation factors, applies hard eligibility filters, ranks qualified stocks and produces a **Top 30 research list and Top 10 portfolio signal**.

The project is designed for fast, repeatable monthly research and live decision support.

---

# Current Strategy

## Locked Research Strategy

```text
COMB_M9S0_B6_V1.5_T0_R0_N10_RB1
```

### Strategy components

| Component | Meaning                                              |
| --------- | ---------------------------------------------------- |
| COMB      | Momentum + Breakout                                  |
| M9        | 9-month momentum                                     |
| S0        | No skip month                                        |
| B6        | 6-month breakout                                     |
| V1.5      | Current monthly volume >= 1.5x prior 3-month average |
| T0        | No trend filter                                      |
| R0        | No market regime filter                              |
| N10       | Top 10 portfolio                                     |
| RB1       | Monthly rebalance                                    |

---

# Live Eligibility Rules

The current production engine applies three hard filters **before ranking**.

A stock is eligible only if:

```text
Momentum_9M >= 0
AND
Breakout_6M >= 0
AND
Volume_Ratio >= 1.50
```

Therefore:

```text
Negative 9M momentum
        ↓
      EXCLUDE

Negative 6M breakout
        ↓
      EXCLUDE

Volume below 1.50x
        ↓
      EXCLUDE
```

This means a stock with negative momentum or a negative breakout **cannot appear in the Top 30 or Top 10 output**.

---

# Important Research Note

The original locked strategy research produced historical results before the additional non-negative momentum and breakout filters were introduced.

Therefore:

> The historical performance of the original strategy must not be assumed to apply to this modified live-filter version.

The additional filters are currently treated as **research constraints**, not statistically validated improvements.

A separate backtest is required to determine whether:

```text
Momentum_9M >= 0
```

and

```text
Breakout_6M >= 0
```

improve or reduce out-of-sample performance.

---

# Strategy Workflow

The production engine follows this workflow:

```text
Nifty 500 Universe
        │
        ▼
5 Years Daily OHLCV
        │
        ▼
Completed Monthly Bars
        │
        ▼
Feature Calculation
        │
        ├── 9M Momentum
        ├── 6M Breakout
        └── Volume Ratio
        │
        ▼
Hard Eligibility Filters
        │
        ├── Momentum >= 0
        ├── Breakout >= 0
        └── Volume >= 1.50x
        │
        ▼
Rank Qualified Stocks
        │
        ▼
Top 30 Research Candidates
        │
        ▼
Top 10 Portfolio
        │
        ▼
BUY / HOLD / SELL
        │
        ▼
CSV + Excel Reports
```

---

# Signal Timing

The engine uses the **latest completed monthly candle**.

The current incomplete month is excluded from the signal calculation.

For example:

```text
September 2026
     │
     ├── September still running
     │
     └── Not used for monthly signal
```

After September closes:

```text
September month-end
        │
        ▼
Calculate signal
        │
        ▼
Execute on following trading session
```

This prevents the current incomplete month from influencing the monthly ranking.

---

# Portfolio Construction

The production portfolio contains up to:

```text
10 stocks
```

Capital:

```text
₹100,000
```

Equal-weight allocation:

```text
₹100,000 / 10
=
₹10,000 per position
```

Therefore:

| Position  |   Allocation |
| --------- | -----------: |
| Stock 1   |      ₹10,000 |
| Stock 2   |      ₹10,000 |
| Stock 3   |      ₹10,000 |
| Stock 4   |      ₹10,000 |
| Stock 5   |      ₹10,000 |
| Stock 6   |      ₹10,000 |
| Stock 7   |      ₹10,000 |
| Stock 8   |      ₹10,000 |
| Stock 9   |      ₹10,000 |
| Stock 10  |      ₹10,000 |
| **Total** | **₹100,000** |

If fewer than 10 stocks qualify:

```text
Qualified stocks × ₹10,000
```

is invested and the remaining capital stays as cash.

---

# Monthly Rebalance Logic

The engine compares the current portfolio with the newly generated Top 10.

## New Top 10 entrant

```text
BUY
```

## Existing holding still in Top 10

```text
HOLD
```

## Existing holding no longer in Top 10

```text
SELL
```

Conceptually:

```text
Current Holdings
       │
       ▼
Compare with New Top 10
       │
       ├── Still qualified → HOLD
       │
       ├── New entrant     → BUY
       │
       └── Removed         → SELL
```

---

# Ranking Method

Qualified stocks are ranked using:

1. `Combined_Score`
2. `Momentum_9M`
3. `Breakout_6M`
4. `Volume_Ratio`

All are ranked from highest to lowest.

The primary ranking score is:

```text
Combined_Score =
    Momentum_9M
    +
    Breakout_6M
```

---

# Feature Definitions

## 9-Month Momentum

```text
Momentum_9M =
    Current Close
    ----------------
    Close 9 months ago
    - 1
```

Python implementation:

```python
Momentum_9M = Close / Close_9M_ago - 1
```

Example:

```text
Current Close = ₹1,000
9 months ago  = ₹800

Momentum =
1,000 / 800 - 1
=
25%
```

---

# 6-Month Breakout

The breakout compares the current monthly closing price against the highest high of the **previous six completed monthly bars**.

The current month is excluded from the reference window.

Conceptually:

```text
Breakout_6M =
    Current Close
    -------------------------------
    Highest previous 6-month High
    - 1
```

The use of the previous six months prevents the current month's high from contaminating the breakout reference.

---

# Volume Confirmation

The current month's volume is compared against the average volume of the previous three completed months.

```text
Prior 3M Average Volume =
    Volume(t-1)
    Volume(t-2)
    Volume(t-3)
    -------------------
            3
```

Then:

```text
Volume_Ratio =
    Current Month Volume
    --------------------
    Prior 3M Average Volume
```

Eligibility requires:

```text
Volume_Ratio >= 1.50
```

Meaning current monthly volume must be at least **150% of the previous three-month average**.

---

# Example Eligibility

Consider a stock:

```text
Momentum_9M  = +32%
Breakout_6M  = +8%
Volume_Ratio = 2.10x
```

Result:

```text
QUALIFIED
```

Another stock:

```text
Momentum_9M  = -5%
Breakout_6M  = +12%
Volume_Ratio = 2.00x
```

Result:

```text
EXCLUDED
```

because:

```text
Momentum_9M < 0
```

Another:

```text
Momentum_9M  = +25%
Breakout_6M  = -3%
Volume_Ratio = 2.00x
```

Result:

```text
EXCLUDED
```

because:

```text
Breakout_6M < 0
```

Another:

```text
Momentum_9M  = +25%
Breakout_6M  = +5%
Volume_Ratio = 1.20x
```

Result:

```text
EXCLUDED
```

because:

```text
Volume_Ratio < 1.50
```

---

# Top 30 vs Top 10

The engine deliberately produces two levels of output.

## Top 30

The Top 30 is the **research candidate list**.

It allows inspection of:

* strongest qualified stocks
* momentum
* breakout strength
* volume confirmation
* combined ranking

The Top 30 is not necessarily the actual portfolio.

## Top 10

The Top 10 is the **portfolio selection**.

These stocks receive:

```text
Target_Weight = 10%
Target_Capital = ₹10,000
```

when all ten positions are available.

---

# Market Regime Monitor

The engine includes a diagnostic market regime monitor.

It calculates a cross-sectional market proxy using the median monthly closing price across the available universe.

It then compares the proxy with its 10-month moving average.

Possible states:

```text
GREEN
YELLOW
RED
UNKNOWN
```

## GREEN

```text
Market Proxy > 10M MA
AND
10M MA is rising
```

## RED

```text
Market Proxy < 10M MA
AND
10M MA is falling
```

## YELLOW

Any intermediate or transitional condition.

---

# Regime Overlay Status

The strategy currently uses:

```text
R0
```

which means:

```text
No market regime filter
```

Therefore:

```python
ENABLE_BEAR_OVERLAY = False
```

The regime monitor is currently **diagnostic only**.

It does not change the Top 10 selection.

This is intentional because introducing a regime filter would create another strategy variation that needs independent backtesting.

---

# Data

The project uses:

```text
Nifty 500
```

with:

```text
5 years of daily OHLCV data
```

The daily market data is obtained through:

```text
trade_data.py
```

The engine supports the existing project market-data architecture and handles the expected:

```python
(data, valid_symbols)
```

return structure.

---

# Monthly Data Construction

Daily OHLCV data is converted to completed monthly bars.

For each stock:

### Monthly Open

Not currently required by the strategy.

### Monthly High

```text
Maximum daily High during the month
```

### Monthly Low

```text
Minimum daily Low during the month
```

### Monthly Close

```text
Last available daily Close
```

### Monthly Volume

```text
Sum of daily Volume during the month
```

---

# Project Structure

```text
InvestmentResearchLab/
│
├── universe.py
│
├── src/
│   │
│   └── MonthlyMomentumLab/
│       │
│       ├── __init__.py
│       ├── main.py
│       ├── trade_data.py
│       ├── README.md
│       ├── PROJECT_DOCUMENTATION.md
│       │
│       ├── cache/
│       │
│       └── results/
│
├── tests/
│
├── notebooks/
│
├── docs/
│
├── data/
│
├── .gitignore
├── README.md
└── pyproject.toml
```

Generated files are intentionally excluded from Git where configured in `.gitignore`.

---

# Running the Engine

Open PowerShell in:

```text
InvestmentResearchLab\src\MonthlyMomentumLab
```

Activate the virtual environment if required:

```powershell
..\..\..\.venv\Scripts\Activate.ps1
```

Then run:

```powershell
python main.py
```

---

# Expected Runtime

The engine is designed to complete in:

```text
seconds to a few minutes
```

The major runtime component is downloading the five-year daily market data.

Feature calculation and signal generation are designed to be very fast.

A representative production run completed in approximately:

```text
~1 minute
```

with:

```text
500 requested stocks
500 valid daily symbols
60 completed monthly periods
```

Runtime varies depending on network speed and market-data source performance.

---

# Output Files

The engine generates the following reports inside:

```text
src/MonthlyMomentumLab/results/
```

## 1. Current Monthly Signal

```text
current_monthly_signal.csv
```

Contains the complete ranked list of eligible stocks.

---

## 2. Top 30

```text
current_monthly_top30.csv
```

Contains the Top 30 qualified research candidates.

---

## 3. Orders

```text
current_monthly_orders.csv
```

Contains:

```text
BUY
HOLD
SELL
```

instructions based on current holdings.

---

## 4. Run Summary

```text
current_monthly_run_summary.csv
```

Contains:

* run timestamp
* signal month
* strategy
* universe size
* valid symbols
* usable monthly symbols
* completed months
* eligible stocks
* Top 30 count
* Top 10 count
* capital allocated
* cash remaining
* active filters
* regime
* runtime

---

## 5. Excel Report

```text
monthly_momentum_lab_live_signal.xlsx
```

The Excel workbook contains:

```text
Top 30
Top 10
Orders
Eligible Universe
Run Summary
Regime Monitor
```

---

# Cache

The monthly dataset is also saved as:

```text
cache/monthly_market_cache_production_v1.pkl
```

The cache provides a reusable monthly-data artifact for research and diagnostics.

The current production workflow still refreshes market data through `trade_data.py` so that the live signal is based on fresh market information.

---

# Safety Checks

The production engine contains explicit safety checks.

The Top 30 and Top 10 cannot contain:

```text
Momentum_9M < 0
```

or:

```text
Breakout_6M < 0
```

If this condition occurs, the program raises an error rather than silently producing an invalid signal.

---

# Investment Interpretation

The strategy is designed to identify stocks showing a combination of:

```text
Longer-term positive momentum
        +
Recent breakout strength
        +
Strong current volume confirmation
```

The hard filters prevent stocks with:

```text
negative 9M momentum
```

or:

```text
negative 6M breakout
```

from entering the ranking.

The system is therefore intentionally selective.

It is acceptable for the engine to return fewer than 30 qualified stocks.

It is also acceptable for it to return fewer than 10 portfolio stocks.

The engine does **not** force weak stocks into the portfolio merely to fill the Top 10.

---

# What This Project Is Not

MonthlyMomentumLab is not:

* a guaranteed-return system
* an automated broker
* a financial-advice service
* a prediction engine
* a high-frequency trading system
* a replacement for independent investment judgment

The output is a quantitative research and decision-support signal.

---

# Research Discipline

The project follows these principles:

1. Use completed monthly data.
2. Avoid current-month leakage.
3. Keep strategy rules explicit.
4. Separate research from production.
5. Preserve the locked strategy definition.
6. Backtest strategy modifications independently.
7. Do not assume historical performance applies to modified rules.
8. Maintain reproducible reports.
9. Record runtime and signal dates.
10. Avoid unnecessary strategy complexity.

---

# Current Status

```text
PROJECT STATUS
==============

Universe                  : Nifty 500
Historical Data           : 5 years daily
Signal Timeframe          : Monthly
Momentum                  : 9 months
Breakout                  : 6 months
Volume Confirmation       : 1.50x
Momentum >= 0 Filter      : ENABLED
Breakout >= 0 Filter      : ENABLED
Trend Filter              : OFF
Regime Filter             : OFF
Portfolio Size            : Top 10
Research List              : Top 30
Rebalance                  : Monthly
Position Weight            : Equal Weight
Capital                    : ₹100,000
Bear Overlay               : OFF
```

---

# Next Research Step

The most important next research task is to backtest the modified eligibility rules:

```text
Momentum_9M >= 0
AND
Breakout_6M >= 0
AND
Volume_Ratio >= 1.50
```

The comparison should be made against the original locked strategy using:

* development period
* out-of-sample period
* untouched holdout period
* CAGR
* Sharpe ratio
* maximum drawdown
* turnover
* number of trades
* percentage of months with fewer than 10 qualified stocks

Only after this comparison should the modified rules be considered statistically validated.

---

# Disclaimer

This project is for quantitative research and educational purposes.

Historical backtest performance does not guarantee future results.

The live signal is not a guarantee of profitability.

Any investment decision should consider liquidity, transaction costs, taxes, slippage, corporate actions, market conditions and individual risk tolerance.