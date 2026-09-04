# FundamentalAlphaForge

## Quantitative Equity Research Engine

**FundamentalAlphaForge** is a Python-based quantitative equity research engine designed to systematically analyse the **Nifty 500** universe using a combination of:

* Market momentum
* Trend strength
* Risk characteristics
* Fundamental quality
* Earnings and revenue growth
* Valuation
* Fundamental data completeness
* Data confidence
* Combined market + fundamental scoring

The project is intended to evolve from a current-research screening engine into a **point-in-time quantitative research and backtesting framework**.

> **Important:** FundamentalAlphaForge is a research and ranking system. It does not generate investment advice or guaranteed BUY/SELL recommendations.

---

# Current Project Stage

## Market Data + Fundamental Research Layer

The current implementation performs a complete research run from universe construction through Excel reporting.

The pipeline is:

```text
Nifty 500 Universe
        ↓
Market Data
        ↓
Market Metrics
        ↓
Data Quality Filter
        ↓
Momentum Score
        ↓
Trend Score
        ↓
Risk Score
        ↓
Market Research Score
        ↓
Dalal / BSE Fundamentals
        ↓
Supplementary yfinance Growth Data
        ↓
Fundamental Data Quality
        ↓
Quality Score
        ↓
Growth Score
        ↓
Valuation Score
        ↓
Fundamental Score
        ↓
Confidence Classification
        ↓
Combined Research Score
        ↓
Rankings & Diagnostics
        ↓
Excel Dashboard
```

---

# Key Features

## 1. Dynamic Nifty 500 Universe

The engine refreshes the current Nifty 500 universe before each research run.

The universe is loaded into:

```text
universe.py
```

This prevents the research engine from depending on a permanently hard-coded stock list.

---

# 2. Historical Market Data

The current market-data layer downloads:

```text
2 years of daily OHLCV data
```

for the Nifty 500 universe.

Market data is supplied through the project's market-data layer and processed by `main.py`.

The engine validates returned symbols and excludes securities that do not provide sufficient usable market history.

---

# 3. Market Metrics

For each valid stock, the engine calculates:

### Momentum

* 3-month return
* 6-month return
* 12-month return

### Moving averages

* 50-day moving average
* 200-day moving average
* Price vs 50 DMA
* Price vs 200 DMA
* 50 DMA vs 200 DMA

### 52-week statistics

* 52-week high
* 52-week low
* Distance from 52-week high
* 52-week high proximity

### Risk

* Volatility
* Maximum drawdown

### Volume

* Volume-related market metrics

---

# 4. Market Scoring Model

The market layer produces three primary component scores:

```text
Momentum Score
Trend Score
Risk Score
```

These are combined into the:

```text
Market Research Score
```

using:

| Component | Weight |
| --------- | -----: |
| Momentum  |    50% |
| Trend     |    30% |
| Risk      |    20% |

Therefore:

```text
Market Research Score
=
50% Momentum
+
30% Trend
+
20% Risk
```

---

# 5. Momentum Model

Momentum is composed of:

| Factor                 | Weight |
| ---------------------- | -----: |
| 3M Return              |    20% |
| 6M Return              |    20% |
| 12M Return             |    20% |
| Price vs 50 DMA        |    10% |
| Price vs 200 DMA       |    10% |
| 50 DMA vs 200 DMA      |    10% |
| 52-week High Proximity |    10% |

The scoring system uses cross-sectional percentile scoring rather than relying on fixed absolute thresholds for every factor.

---

# 6. Trend Model

The trend model evaluates whether the stock is positioned within a positive technical structure.

Important trend conditions include:

```text
Price > 50 DMA
Price > 200 DMA
50 DMA > 200 DMA
```

The engine also identifies stocks satisfying the project's strong-uptrend definition.

---

# 7. Risk Model

The risk score considers:

* Volatility
* Maximum drawdown

Lower volatility is preferred.

Smaller drawdowns are preferred.

The risk score is therefore designed so that a higher score represents a more attractive risk profile.

---

# 8. Fundamental Research

The fundamental layer combines data from:

### Primary fundamental source

**Dalal / BSE**

Used for currently available fundamental information including:

* ROE
* Net Profit Margin
* Operating Profit Margin
* Current-quarter revenue
* Previous-quarter revenue
* Current-quarter net profit
* Previous-quarter net profit
* Current-quarter EPS
* Previous-quarter EPS
* P/E
* P/B

### Supplementary source

**yfinance**

yfinance is used only where required to supplement YoY growth information.

The project deliberately avoids fabricating unsupported fundamental fields.

If a value is unavailable:

```text
NaN
```

is retained.

Missing data is **not converted to zero**.

---

# 9. Fundamental Factors

The current fundamental model contains 11 raw factors.

## Quality

1. ROE
2. Net Profit Margin
3. Operating Profit Margin

## Growth

4. QoQ Revenue Growth
5. QoQ Net Profit Growth
6. QoQ EPS Growth
7. YoY Revenue Growth
8. YoY Net Profit Growth
9. YoY EPS Growth

## Valuation

10. P/E
11. P/B

---

# 10. Quality Score

Quality consists of:

| Factor                  | Weight |
| ----------------------- | -----: |
| ROE                     |    40% |
| Net Profit Margin       |    30% |
| Operating Profit Margin |    30% |

Higher values are preferred.

```text
Quality Score
=
40% ROE
+
30% Net Profit Margin
+
30% Operating Profit Margin
```

---

# 11. Growth Score

Growth combines both sequential and annual growth.

## QoQ subgroup

| Factor            | Weight |
| ----------------- | -----: |
| Revenue Growth    |    40% |
| Net Profit Growth |    35% |
| EPS Growth        |    25% |

## YoY subgroup

| Factor            | Weight |
| ----------------- | -----: |
| Revenue Growth    |    40% |
| Net Profit Growth |    35% |
| EPS Growth        |    25% |

The two subgroups are then weighted:

| Growth Component | Weight |
| ---------------- | -----: |
| QoQ Growth       |    40% |
| YoY Growth       |    60% |

Therefore:

```text
Growth Score
=
40% QoQ Growth
+
60% YoY Growth
```

This places greater emphasis on annual growth while still capturing recent sequential momentum.

---

# 12. Valuation Score

The valuation model uses:

* P/E
* P/B

Weights:

| Factor | Weight |
| ------ | -----: |
| P/E    |    60% |
| P/B    |    40% |

Lower positive valuation multiples receive higher scores.

Zero or negative valuation multiples are treated as unavailable.

```text
Valuation Score
=
60% P/E
+
40% P/B
```

---

# 13. Fundamental Score

The three fundamental groups are combined as:

| Group     | Weight |
| --------- | -----: |
| Quality   |    35% |
| Growth    |    45% |
| Valuation |    20% |

Therefore:

```text
Fundamental Score
=
35% Quality
+
45% Growth
+
20% Valuation
```

The scoring system uses available-factor weighting, meaning missing factors do not automatically become zero.

---

# 14. Missing Data Philosophy

One of the core design principles of FundamentalAlphaForge is:

> **Missing data must remain missing.**

The engine does not assume:

```text
Missing = 0
```

Instead:

```text
Missing = NaN
```

Available factors are scored using their available weights.

This prevents unavailable financial information from being incorrectly interpreted as poor financial performance.

---

# 15. Fundamental Data Completeness

The engine measures fundamental data availability at multiple levels.

### Factor level

For every fundamental factor:

```text
Available
Missing
Coverage %
```

is calculated.

### Group level

Completeness is calculated separately for:

* Quality
* Growth
* Valuation

### Overall level

An overall weighted completeness score is calculated using the same fundamental weighting structure used by the scoring model.

---

# 16. Fundamental Confidence

Fundamental data completeness is converted into a confidence classification.

| Completeness     | Confidence |
| ---------------- | ---------- |
| >= 80%           | High       |
| >= 60% and < 80% | Medium     |
| < 60%            | Low        |

Only:

```text
High
Medium
```

confidence stocks are eligible for headline fundamental rankings.

Low-confidence stocks remain available in the full Research Data output.

This separates:

```text
Score
```

from:

```text
Confidence in the underlying data
```

---

# 17. Combined Research Score

The final research model combines market and fundamental research equally.

| Component             | Weight |
| --------------------- | -----: |
| Market Research Score |    50% |
| Fundamental Score     |    50% |

Therefore:

```text
Combined Research Score
=
50% Market Research
+
50% Fundamental
```

A stock must have:

* Fundamental ranking eligibility
* Valid Market Research Score
* Valid Fundamental Score

to receive a Combined Research Score.

The resulting stocks are ranked using:

```text
Combined Research Score
↓
Market Research Score
↓
Fundamental Score
```

---

# 18. Research Candidate Filter

The engine additionally identifies a more selective group of research candidates.

A candidate must satisfy:

```text
Combined Research Score available
AND
Fundamental ranking eligible
AND
Market Research Score >= 60
AND
Fundamental Score >= 60
AND
Trend Score >= 66.67
AND
Fundamental completeness >= 60%
```

These conditions are intended to identify stocks that have a reasonable combination of:

* Market strength
* Trend strength
* Fundamental strength
* Data confidence

---

# 19. Excel Reporting

The engine produces:

```text
fundamental_alpha_forge_results.xlsx
```

The workbook currently contains four sheets.

## 1. Dashboard

Provides a visual research summary including:

* Run information
* Universe size
* Market-researched count
* Combined eligible count
* Strong-uptrend count
* High-confidence count
* Medium-confidence count
* Average completeness
* Median completeness
* Top combined research stocks
* Top market stocks
* Fundamental confidence breakdown
* Market score components
* Fundamental score components
* Fundamental factor coverage
* Risk/return statistics
* Top Quality stocks
* Top Growth stocks
* Top Valuation stocks
* Research candidate summary
* Charts

---

## 2. Research Data

Contains the detailed stock-level research dataset.

This sheet is intended to preserve the underlying research information rather than only the top-ranked stocks.

It includes market metrics, fundamental metrics, factor scores, completeness measures, confidence classifications and research rankings.

---

## 3. Factor Coverage

Provides factor-level fundamental data coverage.

For each factor the workbook reports:

* Group
* Factor
* Available
* Missing
* Coverage %
* Status
* Weight

Coverage status is classified as:

```text
>= 80%  → Strong
>= 60%  → Moderate
< 60%   → Sparse
```

---

## 4. Score Statistics

Provides descriptive statistics for the calculated scores, including:

* Minimum
* 25th percentile
* Median
* 75th percentile
* Maximum

It also provides a correlation matrix for the available score metrics.

---

# 20. Excel Visualization

The workbook uses `openpyxl` to create:

* KPI cards
* Formatted tables
* Conditional formatting
* Data bars
* Color scales
* Pie charts
* Bar charts
* Frozen panes
* Auto filters
* Automatic column sizing

The factor coverage DataBar explicitly specifies its color to avoid the OpenPyXL `DataBar.color = None` formatting issue.

---

# 21. Research Diagnostics

The console output provides several research views:

### Universe Summary

Shows:

* Stocks analysed
* Stocks above minimum price
* Stocks above 50 DMA
* Stocks above 200 DMA
* Stocks with 50 DMA above 200 DMA
* Strong uptrend stocks
* Fundamental score coverage
* Confidence distribution
* Fundamental ranking eligibility
* Combined ranking eligibility

### Market Rankings

Displays the top market-research stocks.

### Fundamental Rankings

Displays the top High/Medium-confidence fundamental stocks.

### Combined Rankings

Displays the highest Combined Research Score stocks.

### Detailed Research

Displays detailed market + fundamental information for the top candidates.

### Factor Leaders

Shows leaders across individual market and fundamental factors.

### Research Candidates

Shows stocks satisfying the stricter research-candidate criteria.

### Score Distribution

Displays descriptive statistics for the calculated scores and completeness measures.

---

# 22. Data Quality Controls

Before scoring, market data passes through a quality filter.

The current requirements include:

```text
Valid symbol
Valid price
Sufficient data points
Valid 50 DMA
Valid 200 DMA
Price >= ₹100
50 DMA > 0
200 DMA > 0
```

Stocks failing these requirements are removed from the market research dataset.

---

# 23. Runtime Tracking

The engine records:

* Start timestamp
* End timestamp
* Elapsed seconds
* Total runtime

Runtime information is also passed into the Excel dashboard.

---

# 24. Error Handling

The program handles:

### Keyboard interruption

A user interruption results in a controlled exit.

### Runtime errors

Unexpected errors are reported as:

```text
RESEARCH RUN FAILED
```

The error message is displayed and the process exits with status code `1`.

---

# 25. Project Structure

The project is organized around a separation between data acquisition, research logic and output.

A typical structure is:

```text
FundamentalAlphaForge/
│
├── data/
│
├── docs/
│
├── notebooks/
│
├── src/
│   └── FundamentalAlphaForge/
│       ├── main.py
│       ├── trade_data.py
│       └── results/
│           └── fundamental_alpha_forge_results.xlsx
│
├── tests/
│
├── universe.py
│
├── README.md
│
├── PROJECT_DOCUMENTATION.md
│
└── pyproject.toml
```

The exact repository structure may evolve as the project grows.

---

# 26. Technology Stack

FundamentalAlphaForge currently uses Python and a number of open-source libraries.

Core technologies include:

* Python
* pandas
* NumPy
* yfinance
* requests
* Dalal
* openpyxl
* pytest

The project also uses Yahoo Finance market data through the existing market-data implementation.

---

# 27. Running the Project

From the project environment, execute:

```bash
python src/FundamentalAlphaForge/main.py
```

The engine will:

1. Refresh the Nifty 500 universe.
2. Load the universe.
3. Download historical market data.
4. Calculate market metrics.
5. Apply market-data quality filters.
6. Calculate Momentum, Trend and Risk scores.
7. Calculate the Market Research Score.
8. Download fundamental data.
9. Calculate fundamental completeness.
10. Calculate Quality, Growth and Valuation scores.
11. Calculate Fundamental Score.
12. Apply fundamental confidence rules.
13. Calculate Combined Research Score.
14. Display rankings and diagnostics.
15. Generate the Excel dashboard.
16. Print the final research summary and runtime.

---

# 28. Important Research Limitation

The current fundamental dataset represents **currently available fundamental information**.

It is not yet a complete historical point-in-time financial database.

Therefore, the current system is suitable for:

```text
Current equity research
Current screening
Factor exploration
Research ranking
Data-quality analysis
```

but should **not yet be treated as an unbiased historical fundamental backtesting system**.

The primary reason is look-ahead bias.

For example, a currently available financial value may not have been publicly available on the historical date being tested.

---

# 29. Future Research Roadmap

The next major development stages are:

```text
Historical Financial Statements
        ↓
Reporting Dates
        ↓
Point-in-Time Fundamental Dataset
        ↓
TTM Metrics
        ↓
3-Year Growth
        ↓
5-Year Growth
        ↓
Historical Factor Scores
        ↓
VectorBT Backtesting
        ↓
Walk-Forward Testing
        ↓
Out-of-Sample Validation
        ↓
Robustness Testing
```

Future research areas may include:

* Historical quarterly financial statements
* Reporting-date alignment
* TTM fundamentals
* 3-year CAGR
* 5-year CAGR
* Historical valuation
* Historical factor rankings
* Sector-relative scoring
* Industry normalization
* Factor neutralization
* Transaction costs
* Slippage
* Portfolio construction
* Position sizing
* Rebalancing rules
* Walk-forward validation
* Out-of-sample testing
* Benchmark comparison

---

# 30. Backtesting Philosophy

The project intentionally separates:

```text
Current Research
```

from:

```text
Historical Backtesting
```

The current engine should first establish a reliable research and data-quality foundation.

Historical backtesting should only be introduced after the fundamental dataset contains appropriate point-in-time information.

The intended future workflow is:

```text
Point-in-Time Data
        ↓
Historical Factor Calculation
        ↓
Historical Ranking
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

# 31. Disclaimer

FundamentalAlphaForge is an experimental quantitative research project.

The rankings and scores are analytical outputs generated from available data and predefined mathematical rules.

They are not investment advice.

Past performance does not guarantee future results.

Data availability, accuracy, delays, corporate actions, survivorship bias, look-ahead bias, transaction costs and other implementation effects can materially affect research results.

Any future trading strategy should be independently validated using appropriate historical and out-of-sample testing before being considered for real-world use.

---

# FundamentalAlphaForge

### From market data to systematic fundamental equity research.

**Current Stage:** Market Data + Fundamental Research Layer

**Next Major Stage:** Point-in-Time Historical Fundamental Research + Backtesting