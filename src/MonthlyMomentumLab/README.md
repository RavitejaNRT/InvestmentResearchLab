# MonthlyMomentumLab

## Production Monthly Momentum + Breakout Research Engine

`MonthlyMomentumLab` is a production-oriented quantitative equity research engine designed to generate **monthly momentum and breakout signals across the Nifty 500 universe**.

The project converts daily market data into completed monthly bars, calculates momentum, breakout and volume-confirmation features, ranks eligible stocks, selects the top portfolio candidates and generates monthly rebalance instructions.

The production engine uses a previously researched and locked strategy configuration.

---

## Locked Strategy

```text
COMB_M9S0_B6_V1.5_T0_R0_N10_RB1
```

### Strategy interpretation

| Component | Meaning                                          |
| --------- | ------------------------------------------------ |
| `COMB`    | Momentum + breakout                              |
| `M9`      | 9-month momentum                                 |
| `S0`      | No skip month                                    |
| `B6`      | 6-month breakout                                 |
| `V1.5`    | Current monthly volume >= 1.50x reference volume |
| `T0`      | No trend filter                                  |
| `R0`      | No market regime filter                          |
| `N10`     | Top 10 portfolio                                 |
| `RB1`     | Monthly rebalance                                |

The production implementation intentionally does **not** run the complete strategy parameter grid.

The research/backtest engine and the production signal engine are separate components.

---

# Research Philosophy

The engine follows a simple principle:

> **Research broadly, lock the strategy, then execute the locked rules consistently.**

The production engine should not continuously optimize itself based on the latest market conditions.

Once a strategy has been selected through the research process, the production system applies that configuration consistently to new completed monthly data.

This separation helps reduce the risk of changing the strategy after seeing recent market outcomes.

---

# Production Workflow

```text
Nifty 500 Universe
        |
        v
Universe Refresh
        |
        v
Daily OHLCV Data
        |
        v
Completed Monthly Bars
        |
        v
Feature Calculation
        |
        +----------------------+
        |                      |
        v                      v
  9M Momentum            6M Breakout
        |                      |
        +----------+-----------+
                   |
                   v
          Volume Confirmation
                   |
                   v
             Eligibility
                   |
                   v
          Combined Ranking
                   |
          +--------+--------+
          |                 |
          v                 v
       Top 30            Top 10
     Research Set       Portfolio
                            |
                            v
                    Current Holdings
                            |
                            v
                    BUY / HOLD / SELL
```

---

# Production Process

The engine performs the following stages:

1. Refresh the current Nifty 500 universe.
2. Load `universe.py`.
3. Download five years of daily market data.
4. Convert daily OHLCV data into completed monthly bars.
5. Exclude the currently incomplete month.
6. Calculate 9-month momentum.
7. Calculate the 6-month breakout feature.
8. Calculate monthly volume confirmation.
9. Filter eligible stocks.
10. Rank stocks using the combined momentum + breakout score.
11. Display the top 30 research candidates.
12. Select the top 10 portfolio.
13. Load current holdings.
14. Generate BUY / HOLD / SELL instructions.
15. Save CSV reports.
16. Save an Excel research report.
17. Display the final production signal.

---

# Signal Timing

The engine uses **completed calendar-month data**.

The current incomplete month is deliberately excluded.

For example:

```text
August 2026 month-end
        |
        v
Signal calculated after August data is complete
        |
        v
Signal date = 2026-08-31
        |
        v
Execution = next trading session
```

This prevents the production engine from using a partially completed month.

---

# Strategy Features

## 9-Month Momentum

The momentum calculation is:

```text
Momentum_9M =
    Current Month Close
    -------------------
    Close 9 Months Ago
    - 1
```

In mathematical form:

```text
Momentum_9M = Close(t) / Close(t-9) - 1
```

Higher momentum indicates stronger price appreciation over the nine-month lookback period.

---

## 6-Month Breakout

The breakout calculation compares the current monthly close with the highest high of the previous six completed months.

```text
Prior 6-Month High =
    Highest High from months t-6 through t-1
```

Then:

```text
Breakout_6M =
    Current Close / Prior 6-Month High - 1
```

This makes the breakout feature explicitly dependent on previous completed months.

The current month is not included in the reference high.

---

## Monthly Volume Confirmation

The production implementation calculates:

```text
Reference Volume =
    Average volume of previous 3 completed months
```

Then:

```text
Volume_Ratio =
    Current Month Volume / Reference Volume
```

The locked production threshold is:

```text
Volume_Ratio >= 1.50
```

Therefore, the current monthly volume must be at least 1.5 times the reference volume.

---

# Combined Score

The ranking score is:

```text
Combined_Score =
    Momentum_9M
    +
    Breakout_6M
```

The production engine ranks stocks primarily by:

1. Combined Score
2. 9-month Momentum
3. 6-month Breakout
4. Volume Ratio

All are ranked in descending order.

---

# Eligibility

A stock must have valid values for:

* Close
* 9-month momentum
* 6-month breakout
* Volume ratio

It must also satisfy:

```text
Volume_Ratio >= 1.50
```

Stocks failing these conditions are excluded from the current monthly ranking.

---

# Portfolio Construction

The production portfolio contains up to:

```text
10 stocks
```

Capital is:

```text
Rs. 100,000
```

The target allocation is equal-weighted.

For 10 eligible portfolio stocks:

```text
Rs. 100,000 / 10
=
Rs. 10,000 per stock
```

If fewer than 10 eligible stocks exist, available candidates are allocated equally across the available portfolio positions.

---

# Top 30 vs Top 10

The engine intentionally separates research output from portfolio output.

### Top 30

The top 30 stocks are the:

```text
Research Universe
```

They are useful for:

* Research
* Monitoring
* Reviewing ranking stability
* Comparing near-miss candidates

### Top 10

The top 10 stocks are the:

```text
Production Portfolio
```

These are the stocks used for monthly portfolio instructions.

---

# Rebalancing

The strategy uses monthly rebalancing.

The engine compares:

```text
Current Holdings
        vs
New Top 10
```

### BUY

A stock is marked `BUY` when:

```text
Stock is in new Top 10
AND
Stock is not currently held
```

### HOLD

A stock is marked `HOLD` when:

```text
Stock is in new Top 10
AND
Stock is already held
```

### SELL

A stock is marked `SELL` when:

```text
Stock is currently held
AND
Stock is no longer in Top 10
```

---

# Current Holdings

The production engine reads:

```text
results/current_holdings.csv
```

Expected column:

```text
Symbol
```

Example:

```csv
Symbol
RELIANCE.NS
TCS.NS
INFY.NS
```

If the file does not exist, the engine treats the portfolio as empty and generates BUY instructions for the current Top 10.

The production engine does not automatically execute trades.

---

# Market Regime Monitor

The project contains an optional market regime monitor.

It is intentionally **not part of the locked strategy**.

The locked strategy is:

```text
R0 = No market regime filter
```

The monitor currently uses a cross-sectional median of stock closing prices as a broad market proxy.

It calculates a:

```text
10-month moving average
```

and classifies the environment as:

```text
GREEN
YELLOW
RED
```

This is diagnostic information only.

```text
ENABLE_BEAR_OVERLAY = False
```

The regime monitor therefore does not modify the Top 10 portfolio.

Any future regime filter must be independently researched and backtested before being enabled.

---

# Data Architecture

The production engine uses the project's existing market-data foundation.

Primary components:

```text
trade_data.py
universe.py
main.py
```

### `trade_data.py`

Responsible for:

* Nifty 500 universe refresh
* Historical market data retrieval
* Existing data infrastructure

The production engine does not create a second independent data downloader.

---

### `universe.py`

Contains the current Nifty 500 symbol universe.

The production engine dynamically loads the symbol list from this file.

---

### `main.py`

The production signal engine.

Responsibilities include:

* Data loading
* Monthly conversion
* Feature calculation
* Ranking
* Portfolio selection
* Rebalance instructions
* Reporting

---

# Directory Structure

Recommended module structure:

```text
MonthlyMomentumLab/
│
├── main.py
├── trade_data.py
├── README.md
├── PROJECT_DOCUMENTATION.md
│
├── cache/
│   └── monthly_market_cache_production_v1.pkl
│
└── results/
    ├── current_monthly_signal.csv
    ├── current_monthly_top30.csv
    ├── current_monthly_orders.csv
    ├── current_monthly_run_summary.csv
    ├── current_holdings.csv
    └── monthly_momentum_lab_live_signal.xlsx
```

---

# Output Files

## `current_monthly_signal.csv`

Contains the current Top 10 production signal.

Includes information such as:

* Symbol
* Close
* Momentum
* Breakout
* Volume ratio
* Combined score
* Target weight
* Target capital
* Signal month
* Strategy
* Execution
* Regime monitor

---

## `current_monthly_top30.csv`

Contains the current Top 30 ranked research candidates.

---

## `current_monthly_orders.csv`

Contains:

```text
BUY
HOLD
SELL
```

instructions based on current holdings versus the new Top 10.

---

## `current_monthly_run_summary.csv`

Contains production-run metadata including:

* Run timestamp
* Strategy
* Signal month
* Universe information
* Eligible stocks
* Portfolio size
* Capital
* Regime status
* Runtime

---

## `monthly_momentum_lab_live_signal.xlsx`

Excel version of the production research output.

Sheets include:

```text
LIVE_SIGNAL
TOP_30
ORDERS
RUN_SUMMARY
STRATEGY_RULES
```

---

# Runtime Design

The production engine is deliberately designed to be much faster than the full strategy research engine.

The production process does **not** perform:

* Strategy parameter grid search
* Thousands of backtests
* Walk-forward optimization
* Strategy selection

Instead, it performs only the locked strategy calculation.

Typical runtime is expected to be in the range of:

```text
Seconds to a few minutes
```

The largest runtime component is normally historical market-data download.

---

# Caching

The engine saves completed monthly data to:

```text
cache/monthly_market_cache_production_v1.pkl
```

The cache provides a reusable representation of the monthly dataset.

The production workflow currently refreshes daily market data so that the signal is generated from current market information.

---

# Error Handling

The engine includes defensive handling for:

* Missing `trade_data.py`
* Missing `universe.py`
* Missing market-data loader
* Empty market data
* Unsupported market-data formats
* Invalid symbols
* Insufficient monthly history
* Missing holdings file
* Excel generation failures
* Keyboard interruption

The program prints a structured failure message and traceback if execution fails.

---

# Data Leakage Controls

A major design objective is avoiding look-ahead bias.

The production engine follows several safeguards.

### Completed months only

The incomplete current month is excluded.

### Momentum

Uses historical data through the completed signal month.

### Breakout

Uses only the previous six completed months for the breakout reference.

### Volume

Uses previous completed months for the reference volume calculation.

### Execution

Signals are intended for the next trading session rather than assuming execution at a future unknown price.

---

# Research vs Production

The project deliberately separates two responsibilities.

## Research Engine

Used for:

* Strategy discovery
* Parameter testing
* Backtesting
* Walk-forward analysis
* Out-of-sample testing
* Strategy selection

## Production Engine

Used for:

* Applying the locked strategy
* Generating the current signal
* Ranking stocks
* Generating portfolio instructions
* Producing reports

The production engine should not silently change the researched strategy.

---

# Important Strategy Governance Rule

The following parameters should be treated as locked unless a new research cycle is performed:

```text
Momentum = 9 months
Skip = 0 months
Breakout = 6 months
Volume = 1.50x
Trend Filter = None
Regime Filter = None
Portfolio = Top 10
Rebalance = Monthly
```

Changing these values creates a different strategy.

For example:

```text
B6 -> B3
```

is not a minor implementation change.

It creates a different strategy that should be separately researched and validated.

---

# Operational Workflow

Recommended monthly operating procedure:

```text
1. Wait for month-end.

2. Ensure the market month is complete.

3. Run main.py.

4. Review:
       current_monthly_top30.csv
       current_monthly_signal.csv
       current_monthly_orders.csv

5. Confirm the strategy configuration has not changed.

6. Review BUY / HOLD / SELL instructions.

7. Execute the intended orders independently.

8. Update current_holdings.csv after actual holdings
   have been confirmed.

9. Preserve the generated reports for audit/history.
```

The software generates research signals and instructions. It does not directly place market orders.

---

# Example Execution

Suppose the current Top 10 is:

```text
STOCK_A
STOCK_B
STOCK_C
STOCK_D
STOCK_E
STOCK_F
STOCK_G
STOCK_H
STOCK_I
STOCK_J
```

and the current portfolio contains:

```text
STOCK_A
STOCK_B
STOCK_C
STOCK_X
STOCK_Y
```

The engine produces:

```text
STOCK_X    SELL
STOCK_Y    SELL

STOCK_A    HOLD
STOCK_B    HOLD
STOCK_C    HOLD

STOCK_D    BUY
STOCK_E    BUY
STOCK_F    BUY
STOCK_G    BUY
STOCK_H    BUY
STOCK_I    BUY
STOCK_J    BUY
```

The resulting portfolio is aligned to the new Top 10.

---

# Installation

From the project environment:

```powershell
cd C:\Users\natte\Documents\Project\InvestmentResearchLab
```

Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Run the production engine:

```powershell
cd src\MonthlyMomentumLab
python main.py
```

---

# Dependencies

The engine requires the project's Python environment and primarily uses:

```text
Python
NumPy
Pandas
OpenPyXL
```

The market-data dependency is provided through the project's existing `trade_data.py` infrastructure.

---

# Production Safety

Before using a generated signal for real capital, verify:

* The universe refresh completed successfully.
* All expected market data was downloaded.
* The signal month is complete.
* The strategy name is correct.
* Top 10 candidates are populated.
* The BUY / HOLD / SELL report is consistent with actual holdings.
* `ENABLE_BEAR_OVERLAY` remains `False` unless separately validated.
* The production feature calculations remain aligned with the research/backtest implementation.

The production engine is a research and decision-support system, not an autonomous trading system.

---

# Strategy Identifier

For reproducibility, the production strategy is identified by:

```text
COMB_M9S0_B6_V1.5_T0_R0_N10_RB1
```

This identifier should be preserved in:

* Source code
* CSV reports
* Excel reports
* Research documentation
* Git history

---

# Project Status

```text
STATUS: Production Signal Engine
```

Current capabilities:

* [x] Nifty 500 universe refresh
* [x] Historical market-data download
* [x] Completed monthly-bar conversion
* [x] 9-month momentum
* [x] 6-month breakout
* [x] Monthly volume confirmation
* [x] Cross-sectional ranking
* [x] Top 30 research output
* [x] Top 10 portfolio selection
* [x] Current holdings comparison
* [x] BUY / HOLD / SELL generation
* [x] CSV reporting
* [x] Excel reporting
* [x] Runtime measurement
* [x] Diagnostic regime monitor
* [x] Bear overlay disabled by default

Future enhancements should be researched and validated separately before becoming part of the locked production strategy.