# MonthlyMomentumLab

## Project Documentation

### Production Monthly Momentum + Breakout Research Engine

---

# 1. Project Overview

`MonthlyMomentumLab` is a quantitative equity research and production signal engine designed for systematic monthly stock selection within the Nifty 500 universe.

The system uses a monthly momentum + breakout methodology.

Daily market data is converted into completed monthly bars. The engine then calculates:

* 9-month momentum
* 6-month breakout strength
* Monthly volume confirmation
* Combined ranking score

The highest-ranked eligible stocks form the monthly research and portfolio candidates.

The production portfolio contains up to 10 stocks with equal capital allocation.

---

# 2. Strategy Identity

The locked production strategy is:

```text
COMB_M9S0_B6_V1.5_T0_R0_N10_RB1
```

The identifier is intentionally compact and describes the primary strategy parameters.

| Code | Parameter           | Value               |
| ---- | ------------------- | ------------------- |
| COMB | Strategy family     | Momentum + Breakout |
| M9   | Momentum            | 9 months            |
| S0   | Skip month          | 0 months            |
| B6   | Breakout            | 6 months            |
| V1.5 | Volume confirmation | >= 1.50x            |
| T0   | Trend filter        | None                |
| R0   | Regime filter       | None                |
| N10  | Portfolio size      | Top 10              |
| RB1  | Rebalance           | Monthly             |

---

# 3. Design Objective

The objective is to create a production engine that:

1. Uses a defined universe.
2. Uses reproducible market data.
3. Converts daily data into completed monthly observations.
4. Calculates predefined strategy features.
5. Produces a deterministic ranking.
6. Selects the highest-ranked stocks.
7. Compares the new portfolio against current holdings.
8. Generates rebalance instructions.
9. Produces auditable reports.
10. Runs quickly enough for practical monthly operation.

The production system intentionally avoids unnecessary computational work.

---

# 4. Research and Production Separation

The architecture separates strategy discovery from signal generation.

```text
                  RESEARCH
                     |
                     v
          Strategy discovery
                     |
                     v
             Backtesting
                     |
                     v
          Out-of-sample testing
                     |
                     v
            Strategy selection
                     |
                     v
              LOCK STRATEGY
                     |
                     v
                  PRODUCTION
                     |
                     v
          Current market signal
```

This separation is important.

The production engine is not intended to continuously search for a better strategy.

Instead, it applies the selected configuration consistently.

---

# 5. Production Architecture

The main production components are:

```text
InvestmentResearchLab
│
├── universe.py
│
└── src
    │
    └── MonthlyMomentumLab
        │
        ├── main.py
        ├── trade_data.py
        ├── README.md
        ├── PROJECT_DOCUMENTATION.md
        │
        ├── cache/
        │
        └── results/
```

---

# 6. Module Responsibilities

## 6.1 `main.py`

`main.py` is the production signal engine.

It is responsible for:

* Universe refresh orchestration
* Universe loading
* Historical data loading
* Data normalization
* Monthly conversion
* Feature calculation
* Signal generation
* Regime monitoring
* Holdings loading
* Order generation
* CSV reporting
* Excel reporting
* Runtime measurement
* Error handling

---

## 6.2 `trade_data.py`

`trade_data.py` is the existing market-data foundation.

The production engine discovers and uses the existing historical-data function rather than implementing a separate downloader.

The currently expected function is:

```python
get_historical_market_data_for_symbols
```

The function returns:

```python
data, valid_symbols
```

The production engine explicitly handles this tuple structure.

---

## 6.3 `universe.py`

The root-level `universe.py` contains the Nifty 500 symbol list.

The production engine dynamically searches for supported variable names such as:

```text
NIFTY_500_SYMBOLS
NIFTY500_SYMBOLS
SYMBOLS
symbols
NIFTY_500
NIFTY500
```

The symbols are normalized into `.NS` format.

Example:

```text
RELIANCE
```

becomes:

```text
RELIANCE.NS
```

---

# 7. Universe Refresh

At the beginning of every production run, the engine attempts to refresh the Nifty 500 universe through the existing `trade_data.py` implementation.

Supported function names include:

```text
refresh_nifty500_universe
refresh_nifty_500_universe
update_nifty500_universe
update_nifty_500_universe
```

If an available refresh function is found, it is executed before loading `universe.py`.

This keeps the production universe aligned with the project's existing universe infrastructure.

---

# 8. Historical Market Data

The production configuration uses:

```python
HISTORICAL_PERIOD = "5y"
```

The requested universe is the current Nifty 500.

The historical data contains daily OHLCV observations.

Expected fields include:

```text
Open
High
Low
Close
Adj Close
Volume
```

The normalization layer supports common DataFrame structures produced by market-data libraries.

---

# 9. Data Normalization

Market-data structures can differ depending on the downloader.

The engine normalizes them into a consistent representation:

```text
Field        Symbol
-------------------------
Open         RELIANCE.NS
High         RELIANCE.NS
Low          RELIANCE.NS
Close        RELIANCE.NS
Volume       RELIANCE.NS
...
```

This allows the feature engine to operate independently of the exact original DataFrame column arrangement.

---

# 10. Daily-to-Monthly Conversion

The production strategy operates on monthly observations.

Daily data is aggregated into calendar-month bars.

For each stock:

### Monthly Open

The production engine currently does not use monthly open for strategy calculations.

### Monthly High

```text
Maximum daily high within the month
```

### Monthly Low

```text
Minimum daily low within the month
```

### Monthly Close

```text
Last available daily close within the month
```

### Monthly Volume

```text
Sum of daily volume within the month
```

---

# 11. Incomplete Month Protection

One of the most important production controls is exclusion of the current incomplete month.

The engine determines the beginning of the current calendar month.

All monthly observations occurring within the current month are excluded.

Therefore:

```text
Current incomplete month
        |
        X
```

and:

```text
Last completed month
        |
        YES
```

is used as the signal month.

This prevents a partially formed month from influencing the production ranking.

---

# 12. Minimum Historical Requirement

The production engine uses:

```python
MIN_MONTHS_REQUIRED = 15
```

A stock needs sufficient monthly history to support the production calculations.

The engine reports the number of symbols with at least the required monthly history.

---

# 13. Feature Engine

The feature engine calculates three principal features.

---

## 13.1 Momentum

Configuration:

```python
MOMENTUM_MONTHS = 9
```

Formula:

```text
Momentum_9M(t)
=
Close(t) / Close(t-9) - 1
```

Example:

If:

```text
Current Close = 150
9-month-ago Close = 100
```

then:

```text
Momentum = 150 / 100 - 1
         = 0.50
         = 50%
```

---

# 14. Breakout Feature

Configuration:

```python
BREAKOUT_MONTHS = 6
```

For each stock:

```text
Prior High =
highest monthly high among the previous six completed months
```

The current month is excluded from the reference window.

Formula:

```text
Breakout_6M(t)
=
Close(t) / Prior_6M_High - 1
```

A positive result indicates the current close is above the previous six-month high.

---

# 15. Volume Confirmation

Configuration:

```python
VOLUME_MULTIPLIER = 1.50
```

The reference volume is:

```text
Average volume of the previous three completed months
```

Formula:

```text
Volume_Ratio(t)
=
Current Month Volume
/
Average Previous 3-Month Volume
```

Eligibility condition:

```text
Volume_Ratio >= 1.50
```

Therefore:

```text
Current volume >= 150% of reference volume
```

is required.

---

# 16. Combined Score

The production ranking score is:

```text
Combined_Score
=
Momentum_9M
+
Breakout_6M
```

No additional weighting is applied.

For example:

```text
Momentum = 40%
Breakout = 10%

Combined Score = 50%
```

The combined score is used as the primary ranking variable.

---

# 17. Ranking Hierarchy

Stocks are sorted by:

```text
1. Combined_Score
2. Momentum_9M
3. Breakout_6M
4. Volume_Ratio
```

All four fields are sorted descending.

A numerical research rank is then assigned:

```text
1
2
3
...
N
```

---

# 18. Eligibility Pipeline

The signal engine first selects the latest completed month.

Then stocks must satisfy:

```text
Close is valid
AND
Momentum_9M is valid
AND
Breakout_6M is valid
AND
Volume_Ratio is valid
AND
Volume_Ratio >= 1.50
```

Only these stocks participate in the ranking.

---

# 19. Top 30 Research Universe

The engine retains:

```python
TOP_RESEARCH_STOCKS = 30
```

The Top 30 is primarily a research and monitoring output.

It provides visibility into:

* strongest candidates
* ranking dispersion
* near-term momentum
* breakout strength
* volume confirmation

The Top 30 is not equivalent to the actual portfolio.

---

# 20. Top 10 Portfolio

The production portfolio uses:

```python
TOP_PORTFOLIO_STOCKS = 10
```

The highest-ranked 10 eligible stocks become the target portfolio.

The capital allocation is:

```python
TOTAL_CAPITAL = 100_000.0
```

Equal allocation:

```text
100,000 / 10
=
10,000 per stock
```

Target weight:

```text
10% per stock
```

---

# 21. Reduced Portfolio Scenario

If fewer than 10 stocks pass the eligibility criteria, the engine does not manufacture additional candidates.

Instead, it allocates equally among the available eligible stocks.

For example:

```text
7 eligible stocks
```

results in:

```text
7 positions
```

with approximately:

```text
14.2857% each
```

of the modeled capital.

This avoids weakening the strategy simply to reach an arbitrary number of holdings.

---

# 22. Holdings Management

The production engine reads:

```text
results/current_holdings.csv
```

Expected field:

```text
Symbol
```

The holdings file represents the portfolio currently believed to be held.

The engine does not infer holdings from previous signals.

This distinction is important because:

```text
Previous signal
!=
Actual current portfolio
```

The holdings file should therefore be updated after actual trades have been confirmed.

---

# 23. Rebalance Logic

The target portfolio is compared with current holdings.

The comparison produces three actions.

---

## BUY

```text
Target Top 10
+
Not currently held
=
BUY
```

---

## HOLD

```text
Target Top 10
+
Already held
=
HOLD
```

---

## SELL

```text
Currently held
+
Not in target Top 10
=
SELL
```

---

# 24. Order Processing Sequence

Orders are displayed in this priority:

```text
SELL
BUY
HOLD
```

This makes exits visible before new entries.

The engine does not submit orders to a broker.

---

# 25. Execution Model

The production signal is calculated after the completion of the signal month.

The intended model is:

```text
Month-end data
       |
       v
Signal calculation
       |
       v
Next trading session
       |
       v
Execution
```

The engine does not claim execution at a price that is not yet known.

---

# 26. Market Regime Monitor

The production engine includes a diagnostic regime monitor.

This is deliberately separate from the locked strategy.

The locked strategy specifies:

```text
R0
```

which means:

```text
No market regime filter
```

---

# 27. Regime Monitor Methodology

The available stock-level monthly data is converted into a cross-sectional matrix:

```text
Month x Stock
```

The median stock close for each month is used as a broad market proxy.

Then:

```text
10-month moving average
```

is calculated.

The monitor compares:

```text
Current Market Proxy
vs
Current 10M MA
```

and:

```text
Current 10M MA
vs
Previous 10M MA
```

---

# 28. Regime States

### GREEN

```text
Market Proxy > 10M MA
AND
10M MA > Previous 10M MA
```

Interpretation:

```text
Positive trend environment
```

---

### RED

```text
Market Proxy < 10M MA
AND
10M MA < Previous 10M MA
```

Interpretation:

```text
Weakening trend environment
```

---

### YELLOW

Anything that does not satisfy the strict GREEN or RED conditions.

Interpretation:

```text
Mixed / transitional environment
```

---

# 29. Important Regime Limitation

The regime monitor is not the Nifty 500 index itself.

It uses a cross-sectional stock-price proxy.

Therefore it should be interpreted as:

```text
Diagnostic market breadth-style proxy
```

rather than:

```text
Official Nifty 500 index signal
```

It should not be used as a portfolio filter unless separately validated.

---

# 30. Bear Overlay

The code contains:

```python
ENABLE_BEAR_OVERLAY = False
```

This must remain disabled while the locked strategy remains:

```text
R0
```

Activating a regime-based portfolio reduction would create a different strategy.

For example:

```text
R0
```

and:

```text
R1
```

should be treated as separate research configurations.

Any future overlay should undergo:

* Full-history backtesting
* Development-period testing
* Out-of-sample testing
* Drawdown analysis
* Turnover analysis
* Comparison against the locked R0 strategy

before production use.

---

# 31. Data Leakage Controls

The production design attempts to prevent look-ahead bias.

### Control 1 — Completed months only

The current incomplete month is excluded.

### Control 2 — Momentum lookback

Momentum uses historical prices only.

### Control 3 — Breakout lookback

The breakout reference uses:

```text
previous six completed months
```

rather than the current month.

### Control 4 — Volume reference

The volume reference uses:

```text
previous three completed months
```

rather than the current month.

### Control 5 — Execution

The signal is intended for the next trading session.

---

# 32. Production Reports

The engine generates five principal report outputs.

```text
current_monthly_signal.csv
current_monthly_top30.csv
current_monthly_orders.csv
current_monthly_run_summary.csv
monthly_momentum_lab_live_signal.xlsx
```

---

# 33. Signal Report

File:

```text
current_monthly_signal.csv
```

Purpose:

```text
Current production portfolio
```

Contains the Top 10 and associated strategy metrics.

Important fields include:

```text
Symbol
Close
Momentum_9M
Breakout_6M
Volume_Ratio
Combined_Score
Target_Weight
Target_Capital
Signal_Month
Strategy
Execution
Regime_Monitor
Bear_Overlay_Enabled
```

---

# 34. Top 30 Report

File:

```text
current_monthly_top30.csv
```

Purpose:

```text
Research and monitoring
```

This file provides the complete current Top 30 ranked candidate set.

---

# 35. Orders Report

File:

```text
current_monthly_orders.csv
```

Purpose:

```text
Portfolio rebalance instructions
```

Possible actions:

```text
SELL
BUY
HOLD
```

---

# 36. Run Summary

File:

```text
current_monthly_run_summary.csv
```

Purpose:

```text
Audit and operational monitoring
```

Contains:

* Run timestamp
* Strategy identifier
* Signal month
* Universe information
* Eligible stock count
* Portfolio size
* Total capital
* Capital per position
* Regime monitor
* Bear overlay status
* Runtime

---

# 37. Excel Report

File:

```text
monthly_momentum_lab_live_signal.xlsx
```

The workbook contains:

```text
LIVE_SIGNAL
TOP_30
ORDERS
RUN_SUMMARY
STRATEGY_RULES
```

This provides a single human-readable production report.

---

# 38. Strategy Rules Sheet

The Excel `STRATEGY_RULES` sheet records the production configuration.

This is useful for auditability.

The production report should always clearly identify:

```text
COMB_M9S0_B6_V1.5_T0_R0_N10_RB1
```

rather than relying on undocumented configuration values.

---

# 39. Runtime Architecture

The production engine measures runtime using:

```python
time.perf_counter()
```

Timing is recorded for major stages:

```text
Universe refresh
Universe loading
Daily market data
Monthly conversion
Feature engine
Signal generation
Regime calculation
Holdings loading
Order generation
Report generation
Total runtime
```

This makes performance regressions easier to identify.

---

# 40. Performance Philosophy

The production engine should remain lightweight.

The full research engine may evaluate thousands of strategy combinations.

The production engine does not.

Production should perform:

```text
Download
    ->
Transform
    ->
Calculate
    ->
Rank
    ->
Report
```

rather than:

```text
Download
    ->
Thousands of backtests
    ->
Optimization
    ->
Strategy selection
    ->
Signal
```

---

# 41. Cache

The production monthly cache is:

```text
cache/monthly_market_cache_production_v1.pkl
```

It contains the standardized monthly dataset.

The cache is intended to reduce repeated monthly transformation work and provide a reusable local representation.

The current production workflow still refreshes daily market data to obtain current information.

---

# 42. Error Handling

The program handles several common failure scenarios.

Examples include:

```text
Missing trade_data.py
Missing universe.py
Missing market-data function
Invalid market-data structure
Empty market data
Insufficient history
Missing holdings file
Excel/report failure
Keyboard interruption
```

The entry point catches unexpected exceptions and prints the traceback.

---

# 43. Operational Validation

Before treating a production run as valid, check:

### Universe

```text
Expected universe loaded
```

### Market data

```text
Valid symbols > 0
Daily end date is current enough
```

### Monthly data

```text
Completed months >= minimum requirement
```

### Signal

```text
Signal month is the latest completed month
```

### Strategy

```text
Strategy identifier is unchanged
```

### Portfolio

```text
Top 10 is populated
```

### Orders

```text
BUY / HOLD / SELL matches current holdings
```

### Overlay

```text
Bear overlay = OFF
```

unless a separately validated strategy is intentionally being tested.

---

# 44. Recommended Production Checklist

Before each monthly signal run:

```text
[ ] Month has completed
[ ] Universe refresh completed
[ ] Nifty 500 universe loaded
[ ] Historical data downloaded successfully
[ ] Latest daily date is correct
[ ] Current incomplete month excluded
[ ] Sufficient monthly history exists
[ ] Strategy identifier is unchanged
[ ] Bear overlay remains OFF
[ ] Top 30 generated
[ ] Top 10 generated
[ ] Current holdings file is correct
[ ] BUY / HOLD / SELL reviewed
[ ] Reports generated successfully
```

---

# 45. Manual Execution

From PowerShell:

```powershell
cd C:\Users\natte\Documents\Project\InvestmentResearchLab
.\.venv\Scripts\Activate.ps1
cd src\MonthlyMomentumLab
python main.py
```

---

# 46. Expected Production Sequence

A successful run should look conceptually like:

```text
MONTHLYMOMENTUMLAB

STAGE 1 — REFRESH NIFTY 500 UNIVERSE

STAGE 2 — LOAD UNIVERSE

STAGE 3 — DOWNLOAD DAILY MARKET DATA

STAGE 4 — CONVERT TO COMPLETED MONTHLY BARS

STAGE 5 — CALCULATE MOMENTUM + BREAKOUT FEATURES

STAGE 6 — GENERATE CURRENT MONTHLY SIGNAL

STAGE 7 — CALCULATE REGIME MONITOR

STAGE 8 — LOAD CURRENT HOLDINGS

STAGE 9 — GENERATE REBALANCE ORDERS

STAGE 10 — SAVE REPORTS

RUN COMPLETE
```

---

# 47. Current Production Philosophy

The engine follows four important principles.

## Principle 1 — No Look-Ahead

Only information available at the signal date should influence the signal.

## Principle 2 — Strategy Lock

Production parameters should not be changed casually.

## Principle 3 — Research/Production Separation

Backtesting and production signal generation are different responsibilities.

## Principle 4 — Auditability

Every production run should leave behind enough information to understand:

```text
When was the signal generated?
Which strategy was used?
Which stocks qualified?
What were the rankings?
What were the intended actions?
How long did the run take?
```

---

# 48. What This Engine Does Not Do

The production engine does not:

* Place broker orders
* Manage broker authentication
* Guarantee execution prices
* Guarantee investment returns
* Predict future stock prices
* Run the full strategy grid
* Automatically optimize parameters
* Automatically activate the bear overlay
* Replace independent investment due diligence

It is a systematic research and signal-generation tool.

---

# 49. Strategy Change Governance

Any change to one of the following should trigger a new research/validation cycle:

```text
Momentum lookback
Breakout lookback
Volume threshold
Volume reference period
Skip-month logic
Trend filter
Regime filter
Portfolio size
Rebalance frequency
Ranking formula
Eligibility rules
Execution assumptions
```

A code change that alters any of these is potentially a strategy change rather than merely a software improvement.

---

# 50. Backtest Consistency Requirement

The production implementation must remain mathematically aligned with the research/backtest implementation.

Particular attention should be paid to:

```text
Momentum definition
Breakout definition
Volume reference definition
Ranking formula
Eligibility rules
Portfolio construction
Rebalance timing
Execution timing
```

If any of these differ between the research engine and production engine, the historical backtest results cannot automatically be assumed to represent the production implementation.

This is a critical validation requirement.

---

# 51. Reproducibility

The following should be preserved for each production signal:

```text
Strategy identifier
Signal month
Run timestamp
Universe size
Valid market-data symbols
Usable monthly symbols
Eligible stock count
Top 30
Top 10
Orders
Runtime
```

The generated CSV and Excel reports provide the primary operational record.

---

# 52. Future Enhancements

Potential future improvements include:

### Signal History

Store every monthly Top 30 and Top 10 rather than overwriting the current files.

### Portfolio History

Maintain historical holdings and rebalance records.

### Turnover Analytics

Measure:

```text
Monthly turnover
Annual turnover
Number of entries
Number of exits
```

### Transaction Cost Modeling

Add brokerage, taxes, slippage and market-impact assumptions to research.

### Research/Production Validation

Create an automated test that compares production feature calculations against the backtest implementation.

### Market Index Regime

If a regime overlay is researched, use an explicit index series rather than the current stock-level proxy.

### Automated Data Quality Checks

Validate:

* duplicate symbols
* missing months
* abnormal prices
* zero volume
* stale data
* unexpected date gaps

### Historical Signal Archive

Create:

```text
results/history/
```

with one immutable folder per signal month.

---

# 53. Recommended Future History Structure

A future production archive could use:

```text
results/
│
├── current/
│
└── history/
    │
    ├── 2026-06/
    │   ├── signal.csv
    │   ├── top30.csv
    │   ├── orders.csv
    │   └── run_summary.csv
    │
    ├── 2026-07/
    │   ├── signal.csv
    │   ├── top30.csv
    │   ├── orders.csv
    │   └── run_summary.csv
    │
    └── 2026-08/
        ├── signal.csv
        ├── top30.csv
        ├── orders.csv
        └── run_summary.csv
```

This would create a permanent monthly research audit trail.

---

# 54. Project Status

```text
PROJECT: MonthlyMomentumLab

STATUS:
Production Signal Engine

STRATEGY:
COMB_M9S0_B6_V1.5_T0_R0_N10_RB1

TIMEFRAME:
Monthly

UNIVERSE:
Nifty 500

PORTFOLIO:
Top 10

CAPITAL MODEL:
Rs. 100,000

REBALANCE:
Monthly

REGIME FILTER:
Disabled

BEAR OVERLAY:
Disabled
```

---

# 55. Final Design Summary

The production architecture is intentionally simple:

```text
Current Nifty 500
        |
        v
5 Years Daily Data
        |
        v
Completed Monthly Bars
        |
        v
9M Momentum
        +
6M Breakout
        +
1.5x Volume Confirmation
        |
        v
Combined Ranking
        |
        v
Top 30 Research Candidates
        |
        v
Top 10 Portfolio
        |
        v
Current Holdings Comparison
        |
        v
BUY / HOLD / SELL
        |
        v
CSV + Excel Reports
```

The core philosophy is:

> **Do the complex work during research. Keep production deterministic, transparent and fast.**

The production engine should apply the locked strategy consistently rather than continuously changing the rules based on recent market behavior.

---

# 56. Important Research Governance Note

The existence of a strong historical backtest does not guarantee future performance.

The production system should therefore be treated as an ongoing research process.

Performance should be monitored using:

```text
Realized returns
Drawdown
Turnover
Transaction costs
Slippage
Signal stability
Universe changes
Out-of-sample behavior
```

Any substantial strategy modification should return to the research engine before being promoted to production.

---

## End of Documentation