# FundamentalAlphaForge — Project Documentation

## 1. Project Overview

FundamentalAlphaForge is a quantitative equity research engine designed to analyse the Nifty 500 universe through a systematic combination of market and fundamental factors.

The system currently operates as a **current-research engine** rather than a historical backtesting engine.

Its purpose is to establish a robust research foundation before introducing point-in-time historical fundamentals and portfolio backtesting.

The current architecture combines:

```text
Market Research
+
Fundamental Research
+
Data Quality
+
Confidence Measurement
+
Cross-Sectional Ranking
+
Excel Reporting
```

---

# 2. Current Research Objective

The current objective is to answer:

> Which Nifty 500 stocks currently exhibit a strong combination of market characteristics, fundamental characteristics and sufficiently complete fundamental data?

The system does not attempt to predict an exact future price.

Instead, it creates a structured ranking based on predefined factor models.

---

# 3. End-to-End Architecture

The current pipeline is:

```text
Nifty 500 Universe
        │
        ▼
Universe Refresh
        │
        ▼
Historical Market Data
        │
        ▼
Market Metrics
        │
        ▼
Market Data Quality Filter
        │
        ├───────────────┐
        ▼               │
Momentum Score         │
        │               │
        ▼               │
Trend Score            │
        │               │
        ▼               │
Risk Score             │
        │               │
        ▼               │
Market Research Score  │
        │               │
        └───────────────┘
                │
                ▼
        Fundamental Data
                │
                ▼
      Fundamental Data Quality
                │
        ┌───────┼────────┐
        ▼       ▼        ▼
     Quality  Growth  Valuation
        │       │        │
        └───────┼────────┘
                ▼
        Fundamental Score
                │
                ▼
        Confidence Classification
                │
                ▼
       Combined Research Score
                │
                ▼
        Rankings & Diagnostics
                │
                ▼
          Excel Dashboard
```

---

# 4. Main Execution Sequence

`main.py` currently executes the research process in 28 logical stages.

## Step 1 — Universe

```python
symbols = refresh_and_load_universe()
```

The current Nifty 500 universe is refreshed and loaded.

---

## Step 2 — Market Data

Historical market data is requested for the universe.

Current historical period:

```text
2 years
```

The engine reports:

* Requested symbols
* Valid symbols
* Invalid symbols

The market-data download output is suppressed during the underlying call so the main console remains readable.

---

## Step 3 — Market Metrics

The raw market dataset is transformed into the research dataframe.

The market dataframe contains the calculated price, return, moving-average, 52-week, volatility, drawdown and volume metrics.

---

## Step 4 — Data Quality

The engine removes stocks that fail required market-data conditions.

Current minimum price:

```text
₹100
```

The engine also requires valid:

```text
Price
Data Points
50 DMA
200 DMA
```

and positive moving averages.

---

## Step 5 — Momentum

The engine calculates the Momentum Score.

---

## Step 6 — Trend

The engine calculates the Trend Score.

---

## Step 7 — Risk

The engine calculates the Risk Score.

---

## Step 8 — Market Research Score

The three market components are combined:

```text
50% Momentum
30% Trend
20% Risk
```

---

## Step 9 — Fundamentals

The fundamental research layer retrieves currently available fundamental data.

Primary source:

```text
Dalal / BSE
```

Supplementary source:

```text
yfinance
```

---

## Step 10 — Merge

Market and fundamental datasets are merged using:

```text
symbol
```

as the joining key.

---

## Step 11 — Fundamental Data Quality

The engine calculates:

* Available factor count
* Simple completeness
* Quality completeness
* Growth completeness
* Valuation completeness
* Weighted completeness
* Fundamental confidence
* Ranking eligibility

---

## Step 12 — Availability

Fundamental coverage is displayed factor by factor.

---

## Step 13 — Quality

Quality Score is calculated.

---

## Step 14 — Growth

Growth Score is calculated.

---

## Step 15 — Valuation

Valuation Score is calculated.

---

## Step 16 — Fundamental Score

Quality, Growth and Valuation are combined.

---

## Step 17 — Combined Score

Eligible market and fundamental scores are combined.

---

## Step 18 — Universe Summary

The engine displays overall universe statistics.

---

## Step 19 — Market Rankings

Market Research Score rankings are displayed.

---

## Step 20 — Fundamental Rankings

Eligible fundamental rankings are displayed.

---

## Step 21 — Combined Rankings

Final research rankings are displayed.

---

## Step 22 — Detailed Research

The highest-ranked stocks are displayed with detailed market and fundamental information.

---

## Step 23 — Factor Leaders

Individual factor leaders are displayed.

---

## Step 24 — Research Candidates

The stricter candidate filter is applied.

---

## Step 25 — Score Distribution

Score statistics are displayed.

---

## Step 26 — Runtime

The research runtime is captured.

---

## Step 27 — Excel Output

The Excel workbook is generated.

---

## Step 28 — Final Output

Research notes, final summary and runtime are printed.

---

# 5. Configuration Parameters

The current engine uses the following major market-data parameters.

| Parameter             |    Current Value |
| --------------------- | ---------------: |
| Historical Period     |               2y |
| Minimum Price         |             ₹100 |
| Minimum Trading Days  |              200 |
| Momentum 3M           |  63 trading days |
| Momentum 6M           | 126 trading days |
| Momentum 12M          | 252 trading days |
| Short Moving Average  |          50 days |
| Long Moving Average   |         200 days |
| Volatility Window     |          63 days |
| Average Volume Window |          20 days |

---

# 6. Fundamental Configuration

Current fundamental collection settings include:

| Parameter              |     Value |
| ---------------------- | --------: |
| Request sleep          |  0.10 sec |
| Progress interval      | 25 stocks |
| BSE lookup timeout     |    15 sec |
| Maximum BSE candidates |         8 |
| Retry count            |         3 |
| Retry sleep            |     1 sec |

These settings are intended to balance data collection reliability and runtime.

---

# 7. Fundamental Factor Model

The model contains 11 fundamental factors.

## Quality Factors

```text
ROE
Profit Margin
Operating Margin
```

## Growth Factors

```text
QoQ Revenue Growth
QoQ Net Profit Growth
QoQ EPS Growth
YoY Revenue Growth
YoY Net Profit Growth
YoY EPS Growth
```

## Valuation Factors

```text
P/E
P/B
```

---

# 8. Quality Model

Weights:

```text
ROE                  = 40%
Profit Margin        = 30%
Operating Margin     = 30%
```

Formula:

```text
Quality Score
=
0.40 × ROE Score
+
0.30 × Profit Margin Score
+
0.30 × Operating Margin Score
```

The underlying factor values are converted to cross-sectional percentile scores before weighting.

---

# 9. Growth Model

The growth model is intentionally divided into two time horizons.

## QoQ

```text
Revenue      = 40%
Net Profit   = 35%
EPS          = 25%
```

## YoY

```text
Revenue      = 40%
Net Profit   = 35%
EPS          = 25%
```

The subgroup weighting is:

```text
QoQ = 40%
YoY = 60%
```

Conceptually:

```text
Growth Score
=
0.40 × QoQ Growth Score
+
0.60 × YoY Growth Score
```

This structure gives more importance to sustained annual growth while retaining sensitivity to recent quarter-to-quarter changes.

---

# 10. Valuation Model

The valuation model uses:

```text
P/E
P/B
```

Weights:

```text
P/E = 60%
P/B = 40%
```

Because lower positive valuation multiples are preferred:

```python
higher_is_better=False
```

is used for valuation percentile scoring.

The engine converts non-positive values to unavailable values.

---

# 11. Fundamental Group Model

Fundamental group weights:

```text
Quality    = 35%
Growth     = 45%
Valuation  = 20%
```

Formula:

```text
Fundamental Score
=
0.35 × Quality Score
+
0.45 × Growth Score
+
0.20 × Valuation Score
```

Available weights are renormalized when factors are missing.

---

# 12. Market Model

The market model consists of:

```text
Momentum
Trend
Risk
```

Weights:

```text
Momentum = 50%
Trend    = 30%
Risk     = 20%
```

Formula:

```text
Market Research Score
=
0.50 × Momentum Score
+
0.30 × Trend Score
+
0.20 × Risk Score
```

---

# 13. Momentum Model Details

The Momentum Score consists of:

| Factor            | Weight |
| ----------------- | -----: |
| 3M Return         |    20% |
| 6M Return         |    20% |
| 12M Return        |    20% |
| Price vs MA50     |    10% |
| Price vs MA200    |    10% |
| MA50 vs MA200     |    10% |
| 52-week Proximity |    10% |

The model therefore combines:

```text
Short-term momentum
+
Medium-term momentum
+
Long-term momentum
+
Trend positioning
+
Breakout proximity
```

---

# 14. Risk Model Details

Risk scoring uses:

```text
Volatility
Maximum Drawdown
```

The volatility score uses:

```text
lower volatility = better
```

The maximum drawdown score uses:

```text
smaller drawdown = better
```

The final Risk Score therefore represents relative risk attractiveness.

---

# 15. Percentile Scoring

The engine uses cross-sectional percentile scoring.

Conceptually:

```text
Raw Factor
     ↓
Rank within Universe
     ↓
Percentile
     ↓
0–100 Score
```

For positively oriented factors:

```text
Higher raw value → Higher score
```

For negatively oriented factors such as valuation and risk:

```text
Lower raw value → Higher score
```

This allows different factor units to be combined into a common scoring framework.

---

# 16. Missing Factor Handling

Missing factor values remain:

```text
NaN
```

They are not converted to:

```text
0
```

This is important because a missing financial value does not necessarily indicate poor performance.

When calculating weighted scores, available factor weights are used rather than assigning a zero score to unavailable factors.

---

# 17. Fundamental Completeness

The engine calculates both simple and weighted completeness.

## Simple factor completeness

```text
Available Factors
------------------ × 100
Total Factors
```

With 11 total fundamental factors:

```text
Fundamental Simple Completeness
=
Available Factors / 11 × 100
```

---

# 18. Group Completeness

Separate completeness metrics are calculated for:

```text
Quality
Growth
Valuation
```

Both simple and weighted completeness information is available.

Weighted completeness uses the same factor weights that drive the corresponding score.

This means a missing high-weight factor has a larger impact on weighted completeness than a missing low-weight factor.

---

# 19. Overall Fundamental Completeness

The overall weighted completeness combines:

```text
Quality Completeness × 35%
+
Growth Completeness × 45%
+
Valuation Completeness × 20%
```

The result becomes:

```text
fundamental_data_completeness
```

---

# 20. Confidence Classification

The completeness value is mapped to confidence.

```text
>= 80%       → High
60%–79.99%   → Medium
< 60%        → Low
```

Ranking eligibility:

```text
High    → Eligible
Medium  → Eligible
Low     → Excluded
```

This prevents stocks with insufficient fundamental coverage from dominating headline rankings.

---

# 21. Fundamental Ranking Eligibility

The engine creates:

```text
fundamental_ranking_eligible
```

which is true only for:

```text
High
Medium
```

confidence stocks.

Low-confidence stocks are retained in the Research Data sheet but excluded from headline Fundamental and Combined rankings.

---

# 22. Combined Research Model

The final score is:

```text
Combined Research Score
=
50% Market Research Score
+
50% Fundamental Score
```

The score is only assigned where:

```text
Fundamental ranking eligible
AND
Market Research Score exists
AND
Fundamental Score exists
```

This is an important design decision.

A stock with poor data completeness is not automatically given a low fundamental score. Instead, it is excluded from the headline combined ranking because confidence is insufficient.

---

# 23. Final Ranking

Stocks are sorted by:

```text
Combined Research Score
Market Research Score
Fundamental Score
```

in descending order.

The engine then creates:

```text
final_rank
```

for stocks with a valid Combined Research Score.

---

# 24. Research Candidate Model

The research-candidate filter is deliberately more selective than the general ranking.

Conditions:

```text
Combined Research Score exists
Fundamental ranking eligible
Market Research Score >= 60
Fundamental Score >= 60
Trend Score >= 66.67
Fundamental completeness >= 60%
```

This creates a second-level research universe.

The distinction is:

```text
Ranking
```

answers:

> Which stocks score highest?

while:

```text
Research Candidate Filter
```

answers:

> Which stocks satisfy a minimum quality, market-strength and data-confidence standard?

---

# 25. Data Sources

## Market Data

Market data is obtained through the project's existing market-data implementation.

The current workflow uses Yahoo Finance data through the project's market-data layer.

## Fundamental Data

Primary source:

```text
Dalal / BSE
```

Supplementary source:

```text
yfinance
```

The source methodology is intentionally documented so users can understand where each type of information originates.

---

# 26. Fundamental Source Philosophy

The fundamental system follows three principles.

### Principle 1 — Use supported data directly

If Dalal provides a factor, it is used directly.

### Principle 2 — Supplement only where necessary

yfinance is used to supplement YoY growth information.

### Principle 3 — Never fabricate missing information

Unsupported or unavailable fields remain unavailable.

This improves transparency and makes data-quality measurement possible.

---

# 27. Raw Fundamental Data Retention

The research dataset retains raw fundamental period information where available.

Examples include:

```text
Current Revenue
Previous Quarter Revenue
Current Net Profit
Previous Quarter Net Profit
Current EPS
Previous Quarter EPS
Fundamental Period
Previous Fundamental Period
Financial-Year Period
```

YoY source information is also retained where available.

This allows the calculated growth factors to be inspected rather than treated as unexplained black-box values.

---

# 28. Output Dataset

The Research Data sheet is designed to contain:

## Identification

```text
symbol
BSE code
BSE company name
BSE security symbol
Dalal security ID
```

## Market metrics

```text
price
returns
moving averages
52-week metrics
volatility
drawdown
volume metrics
```

## Market scores

```text
momentum_score
trend_score
risk_score
market_research_score
```

## Fundamental metrics

```text
ROE
profit margin
operating margin
QoQ growth
YoY growth
P/E
P/B
```

## Fundamental scores

```text
quality_score
growth_score
valuation_score
fundamental_score
```

## Data quality

```text
fundamental_factors_available
fundamental_simple_completeness
quality_data_completeness
growth_data_completeness
valuation_data_completeness
quality_weighted_completeness
growth_weighted_completeness
valuation_weighted_completeness
fundamental_weighted_completeness
fundamental_data_completeness
fundamental_confidence
fundamental_ranking_eligible
```

## Final research

```text
combined_research_score
final_rank
```

---

# 29. Excel Architecture

The Excel workbook contains four major sheets.

```text
Dashboard
Research Data
Factor Coverage
Score Statistics
```

---

# 30. Dashboard Architecture

The Dashboard contains:

## Run Information

```text
Start Timestamp
End Timestamp
Runtime Seconds
Runtime
```

## KPI Cards

```text
Universe
Market Researched
Combined Eligible
Strong Uptrend
High Confidence
Medium Confidence
Average Completeness
Median Completeness
```

## Ranking Tables

```text
Top 10 Combined Research Stocks
Top 10 Market Stocks
```

## Analytical Sections

```text
Fundamental Confidence Breakdown
Average Market Score Components
Average Fundamental Components
Fundamental Factor Coverage
Risk / Return Statistics
Top 10 Quality Stocks
Top 10 Growth Stocks
Top 10 Valuation Stocks
Research Candidate Summary
```

---

# 31. Factor Coverage Sheet

The Factor Coverage sheet provides an audit-oriented view of the fundamental dataset.

Each factor contains:

```text
Group
Factor
Available
Missing
Coverage %
Status
Weight
```

Coverage status:

```text
Strong    >= 80%
Moderate  >= 60%
Sparse    < 60%
```

Conditional formatting makes weak and strong coverage visually identifiable.

---

# 32. Score Statistics Sheet

The Score Statistics sheet provides:

```text
Descriptive Statistics
```

for the available score columns.

The calculated statistics include:

```text
Count
Mean
Standard Deviation
Minimum
25th Percentile
Median
75th Percentile
Maximum
```

A correlation matrix is also generated for the available scores.

This is useful for identifying whether different components are measuring highly similar characteristics.

---

# 33. Excel Safety

The function:

```python
excel_safe_value()
```

converts NumPy values into Excel-compatible Python values.

It also converts:

```text
NaN
Infinity
```

into:

```text
None
```

This prevents invalid values from being written into the workbook.

---

# 34. Excel Formatting

The workbook applies:

* Header formatting
* Number formatting
* Column sizing
* Frozen panes
* Auto filters
* Conditional formatting
* Data bars
* Color scales
* Charts
* KPI cards
* Section headers

The goal is to make the workbook useful both as a research dataset and as a human-readable report.

---

# 35. Runtime Architecture

The program records:

```python
PROGRAM_START_TIME
PROGRAM_END_TIME
PROGRAM_ELAPSED_SECONDS
```

The performance timer uses:

```python
time.perf_counter()
```

for elapsed-time measurement.

The completed research runtime is captured before Excel generation so that the dashboard receives the completed research runtime rather than being affected by workbook-generation time.

---

# 36. Error Handling

The program entry point handles two major cases.

## KeyboardInterrupt

If the user stops the program:

```text
Research run interrupted by user.
```

is displayed.

Exit code:

```text
1
```

---

## General Exception

Unexpected failures produce:

```text
RESEARCH RUN FAILED
```

followed by the error message.

The program exits with status code:

```text
1
```

---

# 37. Current Limitations

The current engine has several intentional limitations.

## 37.1 Current fundamentals are not point-in-time

Fundamental data represents currently available information.

It is not yet a complete historical dataset with reporting-date alignment.

---

## 37.2 Historical fundamental backtesting is not yet valid

Using today's fundamental values to simulate historical decisions can introduce:

```text
Look-ahead bias
```

Therefore the current fundamental engine should not yet be considered a production-grade historical backtesting system.

---

## 37.3 No historical financial database

The current system does not yet maintain a complete historical database containing every financial statement version as it became publicly available.

---

## 37.4 No portfolio construction

The current engine ranks stocks.

It does not yet decide:

```text
Position size
Portfolio weights
Number of holdings
Entry timing
Exit timing
Stop loss
Transaction costs
Slippage
```

---

## 37.5 No backtesting engine yet

The current system does not yet implement the intended VectorBT-based historical portfolio backtest.

---

# 38. Why the Current Architecture Is Important

The project is intentionally being built in stages.

The current stage establishes:

```text
Reliable Universe
+
Reliable Market Data
+
Market Factors
+
Fundamental Factors
+
Transparent Scoring
+
Data Completeness
+
Confidence
+
Ranking
+
Reporting
```

before introducing historical backtesting.

This avoids building a sophisticated backtest on top of unreliable or incorrectly timestamped fundamental data.

---

# 39. Future Point-in-Time Architecture

The intended next-generation architecture is:

```text
Historical Financial Statements
        ↓
Publication / Reporting Dates
        ↓
Point-in-Time Database
        ↓
Historical Fundamental Factors
        ↓
Historical Market Factors
        ↓
Historical Scores
        ↓
Historical Rankings
        ↓
Portfolio Construction
        ↓
VectorBT
        ↓
Walk-Forward Testing
        ↓
Out-of-Sample Validation
```

---

# 40. Future Fundamental Dataset

The next fundamental-data phase should introduce:

## Historical statements

* Quarterly revenue
* Quarterly profit
* Quarterly EPS
* Balance sheet data
* Cash-flow data

## Derived metrics

* TTM revenue
* TTM earnings
* TTM EPS
* 3-year growth
* 5-year growth
* CAGR metrics
* Margin trends
* ROE trends
* ROIC
* Debt metrics
* Cash-flow quality

## Valuation history

* Historical P/E
* Historical P/B
* Historical EV/EBITDA where available
* Historical valuation percentiles

---

# 41. Point-in-Time Requirement

Every historical fundamental observation should ideally have:

```text
Financial Period
+
Reporting Date
+
Publication / Availability Date
+
Value
+
Source
```

The critical field for unbiased backtesting is the date on which the information became available to the market.

For example:

```text
Financial Quarter
        ↓
Company Reports Results
        ↓
Information Becomes Public
        ↓
Only then can a backtest use it
```

This prevents future information from leaking into historical decisions.

---

# 42. Future Backtesting Framework

Once point-in-time fundamentals are available, the intended framework is:

```text
Historical Data
      ↓
Factor Calculation
      ↓
Cross-sectional Ranking
      ↓
Portfolio Selection
      ↓
Entry
      ↓
Holding Period
      ↓
Rebalance
      ↓
Transaction Costs
      ↓
Portfolio Returns
      ↓
Performance Metrics
```

VectorBT is planned for the backtesting stage.

---

# 43. Walk-Forward Testing

Future validation should use walk-forward methodology.

Conceptually:

```text
Training Period
      ↓
Model / Rule Definition
      ↓
Validation Period
      ↓
Out-of-Sample Period
      ↓
Advance Window
      ↓
Repeat
```

This helps determine whether a factor model continues to work outside the period in which it was developed.

---

# 44. Robustness Testing

Future research should test sensitivity to:

* Ranking thresholds
* Factor weights
* Holding periods
* Rebalancing frequency
* Universe definitions
* Transaction costs
* Slippage
* Market regimes
* Sector concentration
* Liquidity constraints

The objective is to determine whether results are robust or dependent on a narrow set of assumptions.

---

# 45. Research Interpretation

The system should be interpreted as a ranking framework.

For example:

```text
High Combined Score
```

means the stock has a relatively strong combination of the factors included in the model.

It does **not** mean:

```text
Guaranteed future return
```

Similarly:

```text
Low Score
```

does not necessarily mean a company is fundamentally poor.

It means the stock ranks relatively lower according to the current model and available data.

---

# 46. Confidence vs Score

A particularly important distinction in the architecture is:

```text
Score ≠ Confidence
```

A stock can have a high score but incomplete data.

Therefore the engine separately measures:

```text
Fundamental Score
```

and:

```text
Fundamental Data Completeness
```

and then uses:

```text
Fundamental Confidence
```

to determine ranking eligibility.

This is designed to reduce false precision.

---

# 47. Research Transparency

The system deliberately exposes:

```text
Raw Factors
+
Factor Scores
+
Group Scores
+
Completeness
+
Confidence
+
Final Score
```

rather than only presenting a final ranking.

This allows a researcher to investigate:

> Why did this stock rank highly?

rather than treating the system as a black box.

---

# 48. Reproducibility

A research run should preserve enough information to understand:

```text
What universe was analysed?
What market data was available?
What fundamental data was available?
Which factors were missing?
How were scores calculated?
What confidence level was assigned?
Why was a stock eligible or excluded?
```

Future versions should expand this further by storing:

* Run date
* Data timestamps
* Source timestamps
* Model version
* Configuration version
* Universe version
* Fundamental dataset version

---

# 49. Development Philosophy

FundamentalAlphaForge follows a staged development philosophy:

### Stage 1

```text
Market Data Foundation
```

### Stage 2

```text
Current Fundamental Research
```

### Stage 3

```text
Historical Fundamental Dataset
```

### Stage 4

```text
Point-in-Time Research
```

### Stage 5

```text
Backtesting
```

### Stage 6

```text
Walk-Forward Validation
```

### Stage 7

```text
Out-of-Sample Validation
```

### Stage 8

```text
Portfolio Research
```

The intention is to validate each layer before adding complexity.

---

# 50. Testing Strategy

The project should maintain tests for critical components including:

```text
Configuration
Universe handling
Market-data transformations
Return calculations
Moving averages
Percentile scoring
Weighted scoring
Completeness calculations
Confidence classification
Fundamental calculations
Ranking logic
Excel output
```

As the project grows, unit tests and integration tests should be expanded before introducing historical backtesting.

---

# 51. Important Implementation Principles

The following principles should remain stable as the project evolves.

### Principle 1

**Do not convert missing financial information into zero.**

### Principle 2

**Do not fabricate unsupported fundamental values.**

### Principle 3

**Keep raw data available for inspection.**

### Principle 4

**Separate data completeness from factor score.**

### Principle 5

**Do not mix current fundamentals with historical backtesting without point-in-time controls.**

### Principle 6

**Prefer transparent factor models over unexplained black-box outputs.**

### Principle 7

**Validate future strategy changes through out-of-sample testing.**

---

# 52. Current Research Formula Summary

## Market

```text
Market Research
=
50% Momentum
+
30% Trend
+
20% Risk
```

## Fundamental

```text
Fundamental
=
35% Quality
+
45% Growth
+
20% Valuation
```

## Combined

```text
Combined Research
=
50% Market Research
+
50% Fundamental
```

## Quality

```text
40% ROE
+
30% Net Profit Margin
+
30% Operating Margin
```

## Growth

```text
40% QoQ
+
60% YoY
```

Within both QoQ and YoY:

```text
40% Revenue
+
35% Net Profit
+
25% EPS
```

## Valuation

```text
60% P/E
+
40% P/B
```

---

# 53. Research Candidate Formula

A stock becomes a Research Candidate when:

```text
Combined Score exists
AND
Fundamental Confidence is High or Medium
AND
Market Research Score >= 60
AND
Fundamental Score >= 60
AND
Trend Score >= 66.67
AND
Fundamental Completeness >= 60%
```

This is a screening rule, not a trading signal.

---

# 54. Final Research Output

At the end of a successful run, the console reports:

```text
Universe
Valid market symbols
Market-researched stocks
Fundamental scores
Fundamental eligible stocks
Combined ranking stocks
Average fundamental completeness
Median fundamental completeness
Top research stock
Market score
Fundamental score
Quality score
Growth score
Valuation score
Data completeness
Confidence
```

The Excel workbook provides the persistent research output.

---

# 55. Final Research Stock

The top stock displayed by the final summary is simply the stock with the highest valid:

```text
Combined Research Score
```

among the eligible stocks.

It should be interpreted as:

```text
Top-ranked research stock according to the current model
```

and not:

```text
Guaranteed best investment
```

---

# 56. Current Status

## Implemented

* Nifty 500 universe refresh
* Universe loading
* 2-year market-data retrieval
* Market factor calculation
* Momentum scoring
* Trend scoring
* Risk scoring
* Market Research Score
* Dalal/BSE fundamental retrieval
* yfinance supplementary YoY growth
* Quality scoring
* Growth scoring
* Valuation scoring
* Fundamental Score
* Fundamental completeness
* Confidence classification
* Ranking eligibility
* Combined Research Score
* Market rankings
* Fundamental rankings
* Combined rankings
* Factor leaders
* Research candidates
* Score distributions
* Research diagnostics
* Excel Research Data
* Excel Dashboard
* Factor Coverage sheet
* Score Statistics sheet
* Excel charts
* Conditional formatting
* Runtime reporting
* Error handling

---

# 57. Next Major Milestone

The next major milestone should be:

```text
POINT-IN-TIME HISTORICAL FUNDAMENTAL DATA
```

rather than immediately building a backtest.

The recommended progression is:

```text
Historical Financial Data
        ↓
Reporting Dates
        ↓
Publication Dates
        ↓
Historical Fundamental Database
        ↓
Historical Factor Engine
        ↓
Historical Ranking Engine
        ↓
VectorBT
        ↓
Walk-Forward Testing
        ↓
Out-of-Sample Validation
```

---

# 58. Long-Term Vision

The long-term objective of FundamentalAlphaForge is to become a research platform capable of answering questions such as:

```text
Which factors historically worked?

Under which market regimes?

For which sectors?

With what holding period?

At what rebalance frequency?

With what transaction costs?

How stable are the results?

Do the results survive out-of-sample testing?

Does the factor combination produce economically meaningful
and statistically robust results?
```

The final objective is therefore not simply to produce a stock list.

It is to build a **reproducible quantitative research framework**.

---

# 59. Disclaimer

FundamentalAlphaForge is a software and quantitative research project.

Its outputs are model-generated research results based on available data and predefined rules.

They should not be interpreted as personalized investment advice.

Historical results, where eventually produced, may contain data-quality limitations and cannot guarantee future performance.

Any strategy developed from this system should undergo appropriate:

```text
Historical Testing
+
Walk-Forward Testing
+
Out-of-Sample Validation
+
Transaction-Cost Analysis
+
Robustness Testing
```

before being considered for real-world deployment.

---

# 60. Conclusion

FundamentalAlphaForge currently provides a structured framework for combining:

```text
Market Momentum
+
Trend
+
Risk
+
Fundamental Quality
+
Growth
+
Valuation
+
Data Completeness
+
Confidence
```

into a transparent equity research ranking.

The current implementation establishes the foundation.

The most important next step is to introduce **historical point-in-time fundamental data**, after which the project can progress toward rigorous backtesting, walk-forward validation and out-of-sample quantitative research.

---

**FundamentalAlphaForge**

```text
Market Data
    ↓
Market Factors
    ↓
Fundamental Factors
    ↓
Data Quality
    ↓
Confidence
    ↓
Research Score
    ↓
Ranking
    ↓
Dashboard
    ↓
Point-in-Time Research
    ↓
Backtesting
    ↓
Validation
```