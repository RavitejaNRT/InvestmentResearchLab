# MomentumPortfolioLab — Project Documentation

## 1. Executive Summary

The historical test from 2011-03 to 2026-09 produced:

| Metric                 |      Result | Meaning                               |
| ---------------------- | ----------: | ------------------------------------- |
| CAGR                   |  **38.98%** | Historical annualized growth          |
| Max drawdown           | **-26.54%** | Worst peak-to-trough decline          |
| Volatility             |  **24.57%** | Annualized return variability         |
| Sharpe                 |    **1.47** | Return relative to volatility         |
| Positive months        |  **69.52%** | Months with positive portfolio return |
| Final multiple         | **164.39×** | ₹10L → ~₹16.44Cr historically         |
| 3Y rolling CAGR median |  **44.08%** | Typical 3-year annualized result      |
| 5Y rolling CAGR median |  **44.91%** | Typical 5-year annualized result      |

Your OOS period is:

2021-03-31 → 2026-09-30

It produced:

CAGR       34.32%
Max DD    -26.54%
Sharpe      1.30

This is useful because you're not looking only at the entire 2011–2026 period.

The strategy still produced a strong historical result in the later period.

But it is not truly independent of survivorship bias, as your own limitation #5 correctly states.

MomentumPortfolioLab is a rules-based quantitative equity portfolio system designed around **monthly cross-sectional momentum selection within the current Nifty 500 universe**.

The project has two distinct roles:

```text
main.py
= Production Monthly Portfolio Decision Engine

backtest.py
= Historical Research, Robustness and OOS Validation Engine
```

The production strategy is deliberately simple:

```text
Current Nifty 500
        ↓
OHLCV
        ↓
12–1 Momentum
        +
6-Month Momentum
        ↓
Volatility Adjustment
        ↓
Cross-Sectional Z-Scores
        ↓
50/50 Composite
        ↓
Top 20
        ↓
Equal Weight
        ↓
Monthly Rebalance
```

The central operating principle is:

> **The portfolio is monthly, even though `main.py` may be run weekly for monitoring.**

---

# 2. Primary System: `main.py`

## 2.1 Purpose

`main.py` is the production-facing component.

Its purpose is to determine the **current official portfolio** according to the tested monthly momentum methodology.

The program:

1. Refreshes the Nifty 500 universe.
2. Downloads current/recent market data.
3. Calculates the strategy score.
4. Determines the latest completed month-end.
5. Selects the Top 20.
6. Adds metadata.
7. Calculates market breadth.
8. Loads the previous model portfolio.
9. Generates portfolio actions.
10. Saves the new official portfolio state.

The source code explicitly describes `main.py` as a monthly momentum portfolio decision engine and states that it calculates the same methodology used in the backtest.

---

# 3. Strategy Parameters

| Parameter                 |      Production setting |
| ------------------------- | ----------------------: |
| Universe                  |       Current Nifty 500 |
| Data                      |                   OHLCV |
| 12–1 momentum weight      |                     50% |
| 6M momentum weight        |                     50% |
| Volatility adjustment     |                     Yes |
| Ranking                   | Cross-sectional z-score |
| Portfolio size            |                  Top 20 |
| Weighting                 |            Equal weight |
| Rebalance                 |                 Monthly |
| Fundamentals              |                      No |
| Market regime filter      |                      No |
| Research transaction cost |                  10 bps |
| Research slippage         |                   5 bps |
| Research total cost       |                  15 bps |

The backtest defines the same baseline strategy characteristics: current Nifty 500, OHLCV-only data, 12–1 plus 6-month momentum, volatility adjustment, cross-sectional ranking, Top 20, equal weighting and monthly rebalancing.

---

# 4. Data Architecture

## 4.1 Universe

The universe is generated through the existing:

```text
trade_data.py
```

The production/backtest engines dynamically load this file and call:

```python
refresh_nifty500_universe()
```

The project intentionally does not modify the existing `trade_data.py`.

The generated universe is:

```text
universe.py
```

The architecture is therefore:

```text
trade_data.py
       ↓
refresh_nifty500_universe()
       ↓
universe.py
       ↓
main.py / backtest.py
```

---

# 5. Market Data

Market prices are obtained through yfinance.

The production engine uses recent daily OHLCV data sufficient to calculate:

* monthly prices
* momentum
* volatility
* EMA breadth
* current prices

The backtest downloads a longer historical series beginning in 2010 to support the research period beginning in 2011.

---

# 6. Signal Timing

This is a critical anti-look-ahead design feature.

The strategy does not use the current incomplete month to determine the official portfolio.

The signal is based on the latest **completed month-end**.

Conceptually:

```text
Month T
    ↓
Wait for completion
    ↓
Month-end becomes official
    ↓
Calculate next portfolio
```

The momentum calculations use information through the previous completed month.

The backtest explicitly defines:

```text
Signal at month T
    ↓
Information only through T-1
```

and calculates:

```text
12–1:
P[t-1] / P[t-13] - 1

6M:
P[t-1] / P[t-7] - 1
```

This prevents the current signal month from being used prematurely.

---

# 7. Detailed Score Construction

## 7.1 Step 1 — Monthly Price Series

Daily prices are converted to month-end prices.

For each stock:

```text
Daily prices
    ↓
Last available trading day of month
    ↓
Monthly price
```

---

## 7.2 Step 2 — 12–1 Momentum

The strategy calculates:

```text
P[t-1] / P[t-13] - 1
```

This represents 12 months of momentum while excluding the most recent month.

---

## 7.3 Step 3 — 6M Momentum

The strategy calculates:

```text
P[t-1] / P[t-7] - 1
```

---

## 7.4 Step 4 — Volatility

Daily returns are calculated and a trailing 252-trading-day standard deviation is annualized.

Conceptually:

```text
Daily returns
     ↓
252-day rolling standard deviation
     ↓
× √252
     ↓
Annualized volatility
```

---

## 7.5 Step 5 — Volatility-Adjusted Momentum

Each momentum return is divided by the relevant previous-month volatility:

```text
12–1 adjusted momentum
=
12–1 return / volatility

6M adjusted momentum
=
6M return / volatility
```

---

## 7.6 Step 6 — Cross-Sectional Z-Score

For each month, stocks are compared against one another.

Conceptually:

```text
Stock score - cross-sectional mean
----------------------------------
cross-sectional standard deviation
```

This produces a relative score rather than relying only on raw percentage returns.

---

## 7.7 Step 7 — Composite Score

The final score is:

```text
Composite
=
0.50 × Z(12–1)
+
0.50 × Z(6M)
```

---

# 8. Portfolio Selection

The stocks are sorted by composite score.

The highest-ranked 20 stocks become:

```text
Official Top 20
```

The ranking uses score and then price as the secondary ordering criterion where required.

Portfolio allocation is equal-weighted.

Therefore:

```text
20 stocks
≈
5% theoretical allocation per stock
```

before considering practical cash, costs or execution differences.

---

# 9. Portfolio State

`main.py` maintains a model portfolio state:

```text
results/momentum_portfolio_state.json
```

This state is necessary because the system needs to know:

> "What was the previous official Top 20?"

Without state, the program cannot distinguish:

```text
Existing stock → HOLD
New stock      → BUY
Exited stock   → SELL
```

The state stores information such as:

* strategy
* Top N
* signal month
* update timestamp
* portfolio
* market rank
* symbol
* score

The state is the **model portfolio state**.

It is not broker/account confirmation.

---

# 10. Action Engine

At a new monthly rebalance:

```text
Previous Top 20
       +
Current Top 20
       ↓
Set comparison
```

Three groups are identified:

```text
Retained
Exited
Entered
```

### Retained

```text
Previous ∩ Current
=
HOLD
```

### Exited

```text
Previous - Current
=
SELL
```

### Entered

```text
Current - Previous
=
BUY
```

When exits and entries occur together, the engine identifies replacement activity.

---

# 11. No New Monthly Signal

This behavior is essential.

Suppose the official signal month is:

```text
2026-08-31
```

and the program is run again during September.

The September daily data may change rankings.

That does **not** mean the portfolio should immediately change.

Instead:

```text
Same official signal month
       ↓
No new rebalance
       ↓
Existing monthly portfolio continues
```

This avoids unnecessary weekly churn.

The operating guide in `main.py` explicitly states that weekly rank movement is not an exit signal and that a portfolio should be carried forward when no new month-end signal exists.

---

# 12. Market Breadth

The production engine calculates:

```text
20D EMA breadth
50D EMA breadth
200D EMA breadth
```

For each EMA:

```text
Number of stocks above EMA
/
Valid Nifty 500 stocks
× 100
```

Classification:

```text
<50%        Low
50–<70%     Medium
≥70%        High
```

## Important distinction

Breadth is **not part of the portfolio selection rule**.

It is a monitoring indicator.

Therefore:

```text
EMA breadth = Context

Momentum score = Portfolio selection
```

The project intentionally keeps the market-regime filter disabled.

---

# 13. Why No Regime Filter?

The baseline research objective is to test the pure momentum strategy before introducing another decision layer.

Therefore:

```text
USE_MARKET_REGIME_FILTER = False
```

The backtest source also explicitly states that the baseline remains OFF and that the pure momentum strategy is being evaluated first.

This keeps the production decision engine aligned with the tested baseline.

---

# 14. Backtest Engine — Reserved Validation Section

## 14.1 Purpose

`backtest.py` is not the live decision engine.

Its purpose is:

```text
Historical data
      ↓
Simulate monthly strategy
      ↓
Calculate portfolio returns
      ↓
Measure risk
      ↓
Test robustness
      ↓
Run fixed OOS validation
```

The research engine uses the same fundamental strategy definition as `main.py`.

---

# 15. Historical Backtest — RESERVED FOR FINAL PROOF

**This section is intentionally reserved for the verified final backtest results.**

When finalized, document:

### Research period

```text
Start:
End:
Years:
```

### Performance

```text
Initial capital:
Final capital:
Final multiple:
CAGR:
Maximum drawdown:
Annualized volatility:
Sharpe:
Positive months:
```

### Rolling performance

```text
Rolling 3Y CAGR median:
Rolling 3Y CAGR minimum:
Rolling 3Y CAGR ≥ target:

Rolling 5Y CAGR median:
Rolling 5Y CAGR minimum:
Rolling 5Y CAGR ≥ target:
```

The purpose of this section is to provide historical evidence for the strategy, not to convert historical performance into a forward return expectation.

---

# 16. Robustness Testing — RESERVED

The backtest tests portfolio breadth:

```text
Top 10
Top 20
Top 30
```

It also tests total trading costs:

```text
0 bps
15 bps
30 bps
50 bps
```

The strategy should be considered more thoroughly researched when its behavior remains understandable across reasonable parameter variations.

The robustness results belong to the research section and do not change the production Top 20 configuration automatically.

---

# 17. Fixed Out-of-Sample Test — RESERVED FOR PROOF

## OOS methodology

The research code defines:

```text
OOS start = 2021-01-01
```

The OOS period is intended to be a fixed historical validation period.

The strategy parameters are not optimized using the OOS period.

The research source describes the development period as approximately 2011–2020 and the OOS period as 2021 onward.

---

## OOS Results

**Reserved for verified final results from `backtest.py`.**

Document:

```text
OOS period:
OOS years:
Initial capital:
Final capital:
Final multiple:
CAGR:
Maximum drawdown:
Annualized volatility:
Sharpe:
Positive months:
Rolling 3Y:
Rolling 5Y:
```

---

# 18. Current Backtest Evidence

The current research run supplied with the project produced:

```text
Historical period:
2011-03-31 → 2026-09-30

Years:
15.50

CAGR:
38.98%

Maximum drawdown:
-26.54%

Annualized volatility:
24.57%

Sharpe:
1.47

Positive months:
69.52%

Final multiple:
164.39x
```

The fixed OOS result produced:

```text
OOS period:
2021-03-31 → 2026-09-30

Years:
5.50

CAGR:
34.32%

Maximum drawdown:
-26.54%

Annualized volatility:
25.09%

Sharpe:
1.30

Positive months:
61.19%

Final multiple:
5.07x
```

These figures are historical research observations, not forward performance forecasts.

---

# 19. Interpreting Maximum Drawdown

Maximum drawdown:

```text
-26.54%
```

does **not** mean the strategy lost 26.54% in one month.

It means the portfolio's largest historical decline from a previous peak to a subsequent trough was 26.54%.

Conceptually:

```text
Portfolio peak
     ↓
     ↓
     ↓
Portfolio trough
     ↓
-26.54%
```

The drawdown can span multiple months.

It should therefore be distinguished from:

```text
Worst monthly return
```

which is a separate statistic.

---

# 20. Backtest Limitations

The research engine explicitly identifies several limitations.

## 20.1 Survivorship Bias

The current Nifty 500 constituents are used for historical periods.

Therefore:

```text
Current universe
      ↓
Applied historically
      ↓
Survivorship bias
```

This can make historical results more favorable than a true historical constituent-by-constituent reconstruction.

---

## 20.2 Data Availability

Historical yfinance data availability differs between securities.

Some stocks may have:

* insufficient history
* missing observations
* changed listings
* unavailable tickers
* incomplete historical records

Therefore the backtest validates the implemented dataset, not a perfect historical market database.

---

## 20.3 Execution Differences

Backtest execution is theoretical.

Live results can differ because of:

* bid/ask spread
* liquidity
* slippage
* brokerage
* taxes
* order timing
* price gaps
* execution availability

The production engine therefore generates signals but does not place broker orders.

---

# 21. Production vs Research

| Area          | `main.py`              | `backtest.py`          |
| ------------- | ---------------------- | ------------------------- |
| Purpose       | Current decision       | Historical validation     |
| Data horizon  | Recent/current         | 2010 onward               |
| Signal        | Latest completed month | Historical month-by-month |
| Portfolio     | Current Top 20         | Simulated Top N           |
| Rebalance     | Monthly                | Monthly                   |
| BUY/HOLD/SELL | Yes                    | No live action engine     |
| State         | Yes                    | No production state       |
| EMA breadth   | Yes                    | Not portfolio switch      |
| Metadata      | Yes                    | Research output           |
| Robustness    | No                     | Yes                       |
| OOS           | No                     | Yes                       |
| Broker orders | No                     | No                        |

---

# 22. Relationship Between the Two Programs

The relationship should be understood as:

```text
             RESEARCH
                 │
                 ▼
        backtest.py
                 │
       Historical validation
                 │
        Robustness testing
                 │
        Fixed OOS validation
                 │
                 ▼
        Strategy specification
                 │
                 ▼
             main.py
                 │
        Current market data
                 │
        Current Top 20 signal
                 │
       Portfolio state comparison
                 │
                 ▼
      BUY / HOLD / SELL / REPLACEMENT
```

`main.py` does not need to import `backtest.py`.

The important requirement is that the production calculations remain consistent with the validated strategy definition.

---

# 23. Strategy Integrity Rules

The following rules should be treated as locked unless a deliberate research revision is performed.

### Rule 1

Do not change:

```text
12–1 momentum
```

without rerunning research.

### Rule 2

Do not change:

```text
6M momentum
```

without rerunning research.

### Rule 3

Do not change:

```text
50/50 weighting
```

without rerunning research.

### Rule 4

Do not change:

```text
Top 20
```

without reviewing the robustness evidence.

### Rule 5

Do not introduce fundamentals into the production score without separate research.

### Rule 6

Do not turn EMA breadth into a portfolio switch without separate research.

### Rule 7

Do not change monthly rebalance behavior into weekly portfolio turnover.

### Rule 8

Do not use the current incomplete month to generate an official portfolio.

---

# 24. Operational Procedure

## Normal weekend run

```powershell
cd C:\Users\natte\Documents\Project\InvestmentResearchLab\src\MomentumPortfolioLab
python main.py
```

Review:

```text
LATEST OFFICIAL PORTFOLIO
```

Then:

```text
LIVE MARKET ACTIONS
```

Then:

```text
MARKET BREADTH
```

---

# 25. Reading the Output

The most important output hierarchy is:

### 1. Official signal month

Confirm that the program is using the latest completed month-end.

### 2. Top 20

This is the actual model portfolio.

### 3. New monthly rebalance

Check:

```text
YES / NO
```

### 4. Actions

If YES:

```text
BUY
HOLD
SELL
REPLACEMENT
```

If NO:

```text
No portfolio change
```

### 5. Market breadth

Use this as context only.

Do not override the strategy based solely on breadth.

---

# 26. Example Decision Flow

Suppose:

```text
Previous Top 20:
A B C D E ...

Current Top 20:
A B C D X ...
```

If:

```text
E exited
X entered
```

then:

```text
E → SELL
X → BUY / REPLACEMENT
A B C D → HOLD
```

If the next weekend produces:

```text
same official signal month
```

then:

```text
No new rebalance
```

even if X's daily ranking moves.

---

# 27. Files and Responsibilities

## `main.py`

Production monthly decision engine.

## `backtest.py`

Historical research and validation.

## `trade_data.py`

Existing Nifty 500 universe refresh mechanism.

## `universe.py`

Generated current universe.

## `results/`

Runtime outputs and research results.

---

# 28. Maintenance Principles

When modifying this project:

1. Preserve the existing strategy unless a research change is intentional.
2. Keep `main.py` and `backtest.py` mathematically aligned.
3. Do not modify `trade_data.py` unnecessarily.
4. Keep monthly signal timing intact.
5. Do not introduce look-ahead bias.
6. Keep the OOS period fixed when validating the existing strategy.
7. Record any parameter change before using it operationally.
8. Rerun historical research after changing strategy mathematics.
9. Treat backtest performance as historical evidence, not a forecast.
10. Keep production signals separate from actual broker execution.

---

# 29. Known Research Caveat

The most important current research caveat is:

> The historical backtest uses the current Nifty 500 constituent list across historical periods.

Therefore the historical results contain survivorship bias.

This limitation also applies to the OOS analysis.

The backtest source explicitly documents this limitation.

---

# 30. Final System Definition

MomentumPortfolioLab should be understood as:

```text
A monthly systematic momentum portfolio engine
for the current Nifty 500 universe.
```

The production strategy is:

```text
Nifty 500
   ↓
12–1 momentum
   +
6M momentum
   ↓
Volatility adjusted
   ↓
Cross-sectional z-score
   ↓
50/50 composite
   ↓
Top 20
   ↓
Equal weight
   ↓
Monthly rebalance
   ↓
BUY / HOLD / SELL / REPLACEMENT
```

`main.py` is the **operational decision engine**.

`backtest.py` is the **research and validation engine**.

The historical and OOS sections are evidence supporting the strategy definition; they are not themselves live trading signals.
