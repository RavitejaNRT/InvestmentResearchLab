# FundamentalAlphaForge

## Quantitative Equity Research Engine

**FundamentalAlphaForge** is a Python-based quantitative equity research engine designed to analyze the **Nifty 500 universe** using a combination of:

* Market momentum
* Trend strength
* Risk characteristics
* Fundamental quality
* Fundamental growth
* Fundamental valuation
* Fundamental data completeness
* Fundamental confidence
* Combined market + fundamental research scoring

The project currently focuses on building a **robust research and ranking layer** using current market data and current fundamental information.

> **Current Stage:** Market Data + Fundamental Research Layer

---

## 1. What FundamentalAlphaForge Does

The engine executes an end-to-end equity research pipeline:

```text
Nifty 500 Universe
        ↓
Market Data Download
        ↓
Market Metrics
        ↓
Momentum Score
        ↓
Trend Score
        ↓
Risk Score
        ↓
Market Research Score
        ↓
Yahoo Finance Fundamentals
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
Combined Research Score
        ↓
Research Rankings
        ↓
Excel Research Workbook
        ↓
Excel Dashboard
```

The objective is to create a systematic framework for identifying stocks that demonstrate a combination of:

* Strong market characteristics
* Healthy business quality
* Attractive growth characteristics
* Relative valuation attractiveness
* Sufficient fundamental data coverage

The system is intended for **research and analysis**, not as an automated trading or investment-advice system.

---

# 2. Key Features

## Market Research

The engine downloads approximately **2 years of daily historical OHLCV data** and calculates:

* 3-month return
* 6-month return
* 12-month return
* 50-day moving average
* 200-day moving average
* Price vs 50 DMA
* Price vs 200 DMA
* 50 DMA vs 200 DMA
* 52-week high
* 52-week low
* Distance from 52-week high
* Distance from 52-week low
* Annualized volatility
* Maximum drawdown
* Average volume
* Current volume
* Current volume / average volume ratio

---

# 3. Market Scoring Model

The market research model consists of three components.

## Momentum Score

Momentum uses percentile-based scoring across:

| Factor                 |   Weight |
| ---------------------- | -------: |
| 3M Return              |      20% |
| 6M Return              |      20% |
| 12M Return             |      20% |
| Price vs 50 DMA        |      10% |
| Price vs 200 DMA       |      10% |
| 50 DMA vs 200 DMA      |      10% |
| 52-Week High Proximity |      10% |
| **Total**              | **100%** |

Each factor is converted into a percentile score from 0–100.

Higher values represent stronger relative momentum.

---

## Trend Score

Trend is based on three conditions:

1. Price > 50 DMA
2. Price > 200 DMA
3. 50 DMA > 200 DMA

The Trend Score represents the percentage of available trend conditions that are satisfied.

Possible scores are effectively:

```text
0
33.33
66.67
100
```

---

## Risk Score

Risk combines:

* Annualized volatility
* Maximum drawdown

Both components are percentile-ranked with lower risk receiving a higher score.

| Risk Component   | Weight |
| ---------------- | -----: |
| Volatility       |    50% |
| Maximum Drawdown |    50% |

---

## Market Research Score

The final Market Research Score is:

| Component      |   Weight |
| -------------- | -------: |
| Momentum Score |      50% |
| Trend Score    |      30% |
| Risk Score     |      20% |
| **Total**      | **100%** |

---

# 4. Fundamental Research Model

Fundamental data is obtained from **Yahoo Finance through `yfinance`**.

The model contains **18 fundamental factors** divided into three groups:

```text
Quality      → 9 factors
Growth       → 3 factors
Valuation    → 6 factors
```

Missing fundamental values remain `NaN`.

They are **not converted to zero**.

This is important because zero could incorrectly imply an actual financial value rather than missing information.

---

# 5. Quality Factors

The Quality model contains:

| Factor           |   Weight |
| ---------------- | -------: |
| ROE              |      20% |
| ROA              |      10% |
| Debt / Equity    |      15% |
| Profit Margin    |      10% |
| Operating Margin |      10% |
| Gross Margin     |       5% |
| Current Ratio    |       5% |
| Quick Ratio      |       5% |
| Free Cash Flow   |      20% |
| **Total**        | **100%** |

Higher values are generally preferred.

Debt/Equity is treated differently because lower leverage receives a higher percentile score.

---

# 6. Growth Factors

The Growth model contains:

| Factor                   |   Weight |
| ------------------------ | -------: |
| Revenue Growth           |      40% |
| Earnings Growth          |      40% |
| Quarterly Revenue Growth |      20% |
| **Total**                | **100%** |

All three growth factors are scored with higher values receiving higher scores.

### Important methodology decision

`earningsQuarterlyGrowth` from Yahoo Finance is **not** treated as EPS Growth.

The model instead uses the available `earningsGrowth` field.

This avoids incorrectly labeling a Yahoo metric as a different financial concept.

---

# 7. Valuation Factors

The Valuation model contains:

| Factor      |   Weight |
| ----------- | -------: |
| P/E         |      20% |
| Forward P/E |      15% |
| P/B         |      10% |
| PEG         |      10% |
| Price/Sales |      20% |
| EV/EBITDA   |      25% |
| **Total**   | **100%** |

Lower positive valuation multiples receive higher percentile scores.

Zero and negative valuation values are excluded from valuation scoring because they are not treated as usable positive valuation multiples by the model.

---

# 8. Fundamental Score

The three fundamental groups are combined using:

| Component       |   Weight |
| --------------- | -------: |
| Quality Score   |      35% |
| Growth Score    |      35% |
| Valuation Score |      30% |
| **Total**       | **100%** |

The resulting value is the:

**Fundamental Score**

---

# 9. Missing Data Methodology

FundamentalAlphaForge does not assume that missing data means zero.

Instead:

```text
Available factor → included in scoring
Missing factor   → excluded from scoring
Missing factor   → tracked in completeness
```

When calculating weighted scores, the weights of available factors are effectively **renormalized**.

For example, if a stock has data for only some factors, the available factors can still contribute to the score without artificially assigning zero to missing factors.

At the same time, the system reports how complete the underlying fundamental dataset is.

This separates:

> **How good the stock appears to be**

from:

> **How much supporting fundamental information is actually available**

---

# 10. Fundamental Data Completeness

There are 18 fundamental factors in the model.

The engine calculates:

* Number of available fundamental factors
* Simple completeness
* Quality completeness
* Growth completeness
* Valuation completeness
* Weighted Quality completeness
* Weighted Growth completeness
* Weighted Valuation completeness
* Overall weighted fundamental completeness

The overall completeness uses the same group weights as the Fundamental Score:

```text
Quality     35%
Growth      35%
Valuation   30%
```

---

# 11. Fundamental Confidence

Fundamental completeness is translated into a confidence classification.

| Completeness      | Confidence |
| ----------------- | ---------- |
| >= 80%            | High       |
| >= 60% and < 80%  | Medium     |
| < 60%             | Low        |
| No available data | No Data    |

Stocks with **High** or **Medium** confidence are considered fundamental-ranking eligible.

Low-confidence stocks remain in the research dataset but are excluded from the headline Fundamental and Combined rankings.

---

# 12. Combined Research Score

The final research model combines market and fundamental research.

| Component             |   Weight |
| --------------------- | -------: |
| Market Research Score |      50% |
| Fundamental Score     |      50% |
| **Total**             | **100%** |

A stock must have:

* Fundamental ranking eligibility
* Market Research Score
* Fundamental Score

to receive a Combined Research Score.

Stocks without a valid combined score are not assigned a final rank.

---

# 13. Research Candidate Filter

The system also identifies a more selective group of research candidates.

A candidate must satisfy:

```text
Combined Research Score exists
AND
Fundamental ranking eligible
AND
Market Research Score >= 60
AND
Fundamental Score >= 60
AND
Trend Score >= 66.67
AND
Fundamental Completeness >= 60%
```

The resulting candidates are ranked by:

1. Combined Research Score
2. Market Research Score
3. Fundamental Score

The top 10 candidates are displayed.

---

# 14. Universe

The engine dynamically refreshes the current Nifty 500 universe.

The resulting symbols are stored in:

```text
universe.py
```

The loader:

* Dynamically imports the universe file
* Normalizes symbols to uppercase
* Removes duplicates
* Sorts symbols
* Validates that the universe contains at least 400 symbols

The system therefore does not silently proceed with a severely incomplete universe.

---

# 15. Market Data

Historical market data is obtained through the project's market-data layer using Yahoo Finance.

Default historical period:

```python
HISTORICAL_PERIOD = "2y"
```

The minimum requirements for a stock to enter the market research dataset include:

```text
At least 200 trading data points
Price >= ₹100
Valid 50 DMA
Valid 200 DMA
```

Stocks failing the data-quality requirements are removed before market scoring.

---

# 16. Excel Research Output

The engine creates:

```text
results/fundamental_alpha_forge_results.xlsx
```

The workbook contains four sheets:

### 1. Dashboard

A visual research dashboard containing:

* Run information
* Start timestamp
* End timestamp
* Runtime seconds
* Human-readable runtime
* Universe count
* Market researched count
* Combined eligible count
* Strong uptrend count
* High-confidence count
* Medium-confidence count
* Average completeness
* Median completeness
* Top 10 combined research stocks
* Top 10 market stocks
* Fundamental confidence breakdown
* Market score component chart
* Fundamental component chart
* Fundamental factor coverage chart
* Risk/return statistics
* Top 10 quality stocks
* Top 10 growth stocks
* Top 10 valuation stocks
* Research candidate summary

---

### 2. Research Data

Contains the complete research dataframe with market and fundamental information.

This sheet is intended to provide the detailed underlying dataset behind the dashboard and rankings.

It includes conditional formatting for major score columns.

---

### 3. Factor Coverage

Provides factor-level fundamental data availability:

* Group
* Factor
* Available
* Missing
* Coverage %
* Status
* Weight

Coverage status is classified as:

```text
>= 80%   → Strong
>= 60%   → Moderate
< 60%    → Sparse
```

The sheet includes visual conditional formatting and data bars.

---

### 4. Score Statistics

Provides statistical summaries for the major scores.

It includes:

* Count
* Mean
* Standard deviation
* Minimum
* 25th percentile
* Median
* 75th percentile
* Maximum

It also generates a correlation matrix covering the available research scores.

---

# 17. Excel Visualizations

The dashboard uses `openpyxl` charts and formatting, including:

* Pie chart
* Bar charts
* Horizontal bar charts
* Conditional color scales
* Data bars
* KPI cards
* Research tables
* Score correlation matrix

The dashboard is designed to provide a quick visual overview while the Research Data sheet provides the detailed underlying data.

---

# 18. Runtime Monitoring

The program records:

```text
Program start timestamp
Program end timestamp
Elapsed seconds
Total runtime HH:MM:SS
```

Runtime information is also written into the Excel Dashboard.

The completed research runtime is captured before Excel generation so the dashboard reflects the research execution runtime.

---

# 19. Research Outputs

The console output provides several analytical views:

* Universe summary
* Market rankings
* Fundamental rankings
* Combined rankings
* Detailed top stocks
* Factor leaders
* Research candidates
* Score distributions
* Fundamental availability statistics
* Research methodology notes
* Final research summary
* Program runtime

The main ranking displays are currently configured for the top 30 stocks, with detailed analysis configured for the top 10.

---

# 20. Current Research Philosophy

FundamentalAlphaForge deliberately separates:

### Market characteristics

```text
Momentum
Trend
Risk
```

from:

### Fundamental characteristics

```text
Quality
Growth
Valuation
```

and separately measures:

```text
Data Completeness
Confidence
```

This provides a more transparent research process than relying on a single opaque score.

---

# 21. Important Limitation: Current Fundamentals Are Not Point-in-Time

The current implementation retrieves the **latest/current fundamental information** from Yahoo Finance.

It does not currently maintain a complete historical point-in-time fundamental database containing:

* Financial statement publication dates
* Reporting dates
* Availability dates
* Historical fundamental snapshots
* Historical TTM values
* Historical 3-year CAGR
* Historical 5-year CAGR

Therefore, the current system is appropriate for:

> **Current equity research and ranking**

but should **not yet be considered a valid historical fundamental backtesting engine**.

Using today's fundamental values against historical stock prices could introduce **look-ahead bias**.

---

# 22. Future Backtesting Architecture

The intended future research evolution is:

```text
Historical Financial Statements
             ↓
Point-in-Time Financial Data
             ↓
TTM Calculations
             ↓
3Y / 5Y Growth Metrics
             ↓
Historical Factor Scores
             ↓
Historical Portfolio Construction
             ↓
VectorBT Backtesting
             ↓
Walk-Forward Testing
             ↓
Out-of-Sample Validation
```

Point-in-time financial reporting and availability dates should be implemented before historical fundamental backtesting is treated as reliable.

---

# 23. Future Roadmap

Potential future development stages include:

### Phase 1 — Current

* Nifty 500 universe
* Market data
* Market factors
* Market scoring
* Current fundamentals
* Quality scoring
* Growth scoring
* Valuation scoring
* Data completeness
* Confidence
* Combined research score
* Excel reporting
* Excel dashboard

### Phase 2 — Historical Fundamentals

* Historical financial statements
* Reporting dates
* Availability dates
* TTM calculations
* Historical fundamental snapshots
* 3-year revenue CAGR
* 5-year revenue CAGR
* 3-year EPS CAGR
* 5-year EPS CAGR

### Phase 3 — Backtesting

* Historical factor calculation
* Portfolio construction
* Entry/exit methodology
* Transaction costs
* Slippage
* Benchmark comparison
* VectorBT integration

### Phase 4 — Robust Validation

* Walk-forward testing
* Out-of-sample testing
* Regime analysis
* Parameter sensitivity
* Drawdown analysis
* Turnover analysis
* Risk-adjusted performance
* Factor attribution

---

# 24. Project Structure

A typical project structure is:

```text
FundamentalAlphaForge/
│
├── src/
│   └── FundamentalAlphaForge/
│       ├── main.py
│       └── trade_data.py
│
├── universe.py
│
├── results/
│   └── fundamental_alpha_forge_results.xlsx
│
├── docs/
│   └── PROJECT_DOCUMENTATION.md
│
├── README.md
│
└── ...
```

The exact repository structure may evolve as the project moves into additional research and backtesting stages.

---

# 25. Configuration

The primary research parameters are defined in the main research module.

Important defaults include:

```python
HISTORICAL_PERIOD = "2y"

MIN_PRICE = 100.0
MIN_TRADING_DAYS = 200

MOMENTUM_3M_DAYS = 63
MOMENTUM_6M_DAYS = 126
MOMENTUM_12M_DAYS = 252

SHORT_MA = 50
LONG_MA = 200

VOLATILITY_DAYS = 63
AVERAGE_VOLUME_DAYS = 20
```

Display configuration includes:

```python
TOP_STOCKS_TO_DISPLAY = 30
TOP_STOCKS_DETAILED = 10
TOP_FACTOR_LEADERS = 5
TOP_RESEARCH_CANDIDATES = 10
```

Confidence thresholds:

```python
HIGH_CONFIDENCE_COMPLETENESS = 80.0
MEDIUM_CONFIDENCE_COMPLETENESS = 60.0
```

---

# 26. Dependencies

The current implementation uses Python packages including:

```text
numpy
pandas
yfinance
openpyxl
```

It also uses Python standard-library modules such as:

```text
datetime
time
pathlib
sys
io
importlib
contextlib
typing
```

A project environment should be created before installing dependencies.

Example:

```bash
python -m venv .venv
```

Activate the environment and install the required packages:

```bash
pip install numpy pandas yfinance openpyxl
```

---

# 27. Running the Engine

From the project environment, execute the main research program.

For example:

```bash
python main.py
```

The program will:

1. Refresh the Nifty 500 universe
2. Load `universe.py`
3. Download historical market data
4. Calculate market metrics
5. Apply data-quality filtering
6. Calculate market scores
7. Retrieve fundamental data
8. Calculate fundamental completeness
9. Calculate Quality Score
10. Calculate Growth Score
11. Calculate Valuation Score
12. Calculate Fundamental Score
13. Calculate Combined Research Score
14. Generate rankings and diagnostics
15. Create the Excel workbook
16. Display the final runtime

---

# 28. Error Handling

The program explicitly handles several failure conditions.

Examples include:

* Missing `universe.py`
* Invalid universe structure
* Insufficient universe size
* No market data returned
* No valid Yahoo Finance symbols
* All stocks failing market data-quality filtering
* User interruption through `Ctrl+C`
* Unexpected runtime exceptions

The program exits with an error status when the research run cannot be completed successfully.

---

# 29. Data Integrity Principles

The current implementation follows several important principles:

### Missing is not zero

Missing financial data remains missing.

### Score what is available

Available factors can contribute to a score.

### Measure completeness separately

Completeness tells the user how much supporting information exists.

### Confidence affects headline rankings

Low-confidence stocks are retained in the dataset but excluded from headline fundamental/combined rankings.

### Avoid false EPS terminology

Yahoo's quarterly earnings-growth field is not mislabeled as EPS Growth.

### Avoid premature backtesting

Current fundamentals are not treated as historical point-in-time fundamentals.

---

# 30. Disclaimer

FundamentalAlphaForge is a **research and quantitative analysis tool**.

Its rankings and scores are analytical outputs and are **not investment advice, buy/sell recommendations, or guarantees of future performance**.

Historical or current rankings should not be interpreted as guarantees of future returns.

Before using any output for investment decisions, the underlying data, methodology, assumptions, valuation, liquidity, corporate actions, and other relevant information should be independently validated.

---

# 31. Project Vision

The long-term objective of FundamentalAlphaForge is to evolve from a current-data equity research engine into a complete quantitative research platform:

```text
             FUNDAMENTALALPHAFORGE
                       │
          ┌────────────┴────────────┐
          │                         │
     Market Research         Fundamental Research
          │                         │
     Momentum                     Quality
     Trend                        Growth
     Risk                         Valuation
          │                         │
          └────────────┬────────────┘
                       │
                Research Score
                       │
              Candidate Selection
                       │
             Historical Database
                       │
                 Backtesting
                       │
              Walk-Forward Testing
                       │
              Out-of-Sample Testing
                       │
                Research Platform
```

The guiding principle is to build the research system **methodically**, with transparent factors, explicit data-quality measurements, and progressively stronger historical validation rather than jumping directly from current rankings to backtested conclusions.
