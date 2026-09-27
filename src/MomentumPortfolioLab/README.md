# MomentumPortfolioLab

## Monthly Momentum Portfolio Decision Engine

MomentumPortfolioLab is an OHLCV-based quantitative equity research and portfolio-decision engine for the current Nifty 500 universe.

The **primary production component is `main.py`**.

`main.py` applies a monthly momentum methodology to the latest completed market month, identifies the current Top 20 portfolio, compares it with the previously saved model portfolio, and produces actionable **BUY / HOLD / SELL / REPLACEMENT** signals.

The project also contains `backtest.py`, which is the historical research and validation engine used to evaluate the strategy over a long historical period, perform robustness testing, and provide a fixed out-of-sample (OOS) validation section.

---

# 1. Project Objective

The objective of MomentumPortfolioLab is to implement a simple, systematic, rules-based momentum portfolio process:

```text
Current Nifty 500
       ↓
Historical OHLCV
       ↓
12–1 Momentum
       +
6-Month Momentum
       ↓
Volatility Adjustment
       ↓
Cross-Sectional Ranking
       ↓
50% + 50% Composite Score
       ↓
Top 20
       ↓
Monthly Portfolio
       ↓
BUY / HOLD / SELL / REPLACEMENT
```

The strategy deliberately does **not** use:

* Fundamental analysis
* Earnings estimates
* Analyst ratings
* Valuation ratios
* Discretionary stock selection
* Market-regime switching
* Daily rank-based portfolio churn

---

# 2. Primary Production Engine — `main.py`

`main.py` is the most important file in this project.

Its job is not to backtest the strategy.

Its job is to answer:

> **"Based on the latest completed month-end, what is the current Top 20 momentum portfolio and what changed versus the previous official portfolio?"**

The production engine:

1. Refreshes the current Nifty 500 universe.
2. Downloads market OHLCV data.
3. Calculates the momentum strategy score.
4. Uses the latest completed month-end.
5. Selects the Top 20 stocks.
6. Retrieves current metadata.
7. Calculates Nifty 500 EMA breadth.
8. Loads the previous model portfolio state.
9. Determines BUY / HOLD / SELL / REPLACEMENT actions.
10. Saves the current signal, actions, breadth and portfolio state.

`main.py` deliberately calls only `refresh_nifty500_universe()` from the existing `trade_data.py`; it does not execute the `trade_data.py` main program.

---

# 3. Strategy Definition

## 3.1 Universe

The strategy operates on the **current Nifty 500 constituent universe**.

The universe is refreshed through:

```text
trade_data.py
    ↓
refresh_nifty500_universe()
    ↓
universe.py
```

`trade_data.py` is not modified by MomentumPortfolioLab.

---

# 4. Momentum Methodology

The production strategy uses two momentum components.

## 4.1 12–1 Momentum

The 12–1 component measures approximately one year of price momentum while excluding the most recent month.

Conceptually:

```text
Price at previous completed month
/
Price 12 months before previous completed month
- 1
```

The current incomplete month is therefore not used to create the official monthly portfolio.

---

## 4.2 6-Month Momentum

The second component measures approximately six months of momentum.

Conceptually:

```text
Price at previous completed month
/
Price 6 months before previous completed month
- 1
```

---

# 5. Volatility Adjustment

Momentum is adjusted using trailing volatility.

The purpose is to prevent raw momentum alone from determining the ranking.

Conceptually:

```text
Momentum Return
/
Trailing Volatility
```

Higher volatility therefore affects the momentum score rather than being ignored.

---

# 6. Cross-Sectional Ranking

The volatility-adjusted momentum values are converted into cross-sectional z-scores.

The ranking is performed across the available Nifty 500 stocks for each signal period.

The final composite score is:

```text
50% × 12–1 Momentum Score
+
50% × 6M Momentum Score
```

Therefore:

```text
12–1 weight = 50%
6M weight   = 50%
```

---

# 7. Portfolio Construction

The production portfolio contains:

```text
Top N = 20 stocks
```

The stocks with the highest composite momentum scores form the official portfolio.

Portfolio construction is:

```text
Top 20
+
Equal weight
+
Monthly rebalance
```

There is no fundamental or discretionary override.

---

# 8. Monthly Signal Discipline

This is one of the most important design principles of the project.

Although `main.py` is intended to be run during the weekend for monitoring, the strategy itself is **monthly**.

The program must therefore not replace stocks every weekend merely because their daily or temporary ranking has changed.

The official portfolio changes only when a **new completed month-end signal** exists.

### During an existing month

```text
No new month-end
       ↓
No portfolio rebalance
       ↓
Existing portfolio remains active
```

### At a new month-end

```text
New Top 20
     ↓
Compare with previous Top 20
     ↓
BUY / HOLD / SELL / REPLACEMENT
```

---

# 9. BUY / HOLD / SELL / REPLACEMENT Logic

## BUY

A stock is classified as:

```text
BUY
```

when it enters the official Top 20 and was not part of the previous official portfolio.

---

## HOLD

A stock is:

```text
HOLD
```

when it remains inside the official Top 20.

Daily rank movement does not by itself create an exit.

---

## SELL

A stock is:

```text
SELL
```

when it leaves the official Top 20 at a new monthly rebalance.

---

## REPLACEMENT

When stocks leave and new stocks enter at the same rebalance, the engine explicitly identifies replacement activity.

Conceptually:

```text
Old Top 20
    ↓
Stock exits

New Top 20
    ↓
New stock enters

Result:
REPLACEMENT
```

---

# 10. First Run

On the first run, there may be no previous portfolio state.

In that situation:

```text
No previous state
       ↓
Current Top 20
       ↓
All 20 treated as BUY
       ↓
Portfolio state saved
```

Subsequent runs compare against that saved model state.

This state represents the **strategy/model portfolio**, not broker-confirmed live holdings.

The program does not place broker orders.

---

# 11. Weekend Operating Model

The intended operating frequency is weekend monitoring.

The recommended workflow is:

```text
Weekend
   ↓
Run main.py
   ↓
Refresh universe
   ↓
Download latest data
   ↓
Calculate current strategy
   ↓
Identify latest completed month-end
   ↓
Check whether a new monthly signal exists
```

### If there is no new month-end

```text
Monitoring only
+
No rank-based churn
+
Continue existing portfolio
```

### If there is a new month-end

```text
Compare previous Top 20
        ↓
BUY / HOLD / SELL / REPLACEMENT
```

Actual execution should occur in the next practical trading session after the signal is available.

---

# 12. Market Breadth

`main.py` also calculates Nifty 500 market breadth using:

* 20D EMA
* 50D EMA
* 200D EMA

Classification:

```text
< 50%        → Low
50% to <70%  → Medium
≥ 70%        → High
```

The breadth output is a **market-condition monitor**.

It does not change the Top 20 portfolio.

This is intentional because the tested baseline strategy does not use a market-regime filter.

Therefore:

```text
Momentum ranking
       ↓
Determines portfolio

EMA breadth
       ↓
Provides market context
       ↓
Does NOT override portfolio
```

---

# 13. Metadata

The Top 20 output is enriched with available market information including:

* Sector
* Industry
* Market capitalization
* Current price
* Momentum score
* Market rank

This makes the output easier to interpret without changing the underlying ranking methodology.

---

# 14. Transaction-Cost Assumption

The research baseline uses:

```text
Transaction cost = 10 bps
Slippage         = 5 bps
Total            = 15 bps
```

This is primarily a **research/backtest assumption**.

It should not be interpreted as a guaranteed live execution cost.

Actual brokerage, taxes, spread, liquidity and slippage can differ.

---

# 15. Output Files

The production engine stores results under:

```text
MomentumPortfolioLab
└── results
```

Primary files:

```text
momentum_portfolio_signal.csv
momentum_portfolio_actions.csv
momentum_portfolio_market_breadth.csv
momentum_portfolio_market_breadth_details.csv
momentum_portfolio_metadata_cache.json
momentum_portfolio_state.json
```

### `momentum_portfolio_signal.csv`

Contains the current official Top 20 signal.

### `momentum_portfolio_actions.csv`

Contains:

```text
BUY
HOLD
SELL
REPLACEMENT
```

and associated ranking/price/score/reason information.

### `momentum_portfolio_market_breadth.csv`

Contains the summarized EMA breadth.

### `momentum_portfolio_market_breadth_details.csv`

Contains stock-level breadth information.

### `momentum_portfolio_state.json`

Stores the previous official model portfolio so future runs can identify changes.

---

# 16. Project Structure

Recommended structure:

```text
MomentumPortfolioLab/
│
├── main.py
├── backtest.py
├── trade_data.py
├── universe.py
├── README.md
├── PROJECT_DOCUMENTATION.md
│
└── results/
    ├── momentum_portfolio_signal.csv
    ├── momentum_portfolio_actions.csv
    ├── momentum_portfolio_market_breadth.csv
    ├── momentum_portfolio_market_breadth_details.csv
    ├── momentum_portfolio_metadata_cache.json
    ├── momentum_portfolio_state.json
    │
    ├── momentum_portfolio_backtest.xlsx
    ├── momentum_portfolio_monthly_returns.csv
    ├── momentum_portfolio_history.csv
    ├── momentum_portfolio_latest_signal.csv
    ├── momentum_portfolio_topn_robustness.csv
    ├── momentum_portfolio_cost_robustness.csv
    ├── momentum_portfolio_oos_monthly_returns.csv
    └── momentum_portfolio_oos_portfolio_history.csv
```

---

# 17. Backtest and OOS Validation — Reserved Research Section

> **This section is intentionally reserved for the historical proof produced by `backtest.py`.**

The backtest is not the production decision engine.

It exists to answer:

> **"How did the exact strategy behave historically?"**

The completed validation section should document:

### Historical Backtest

* Research period
* CAGR
* Maximum drawdown
* Annualized volatility
* Sharpe
* Positive-month percentage
* Final multiple
* Rolling 3Y CAGR
* Rolling 5Y CAGR

### Robustness

* Top 10
* Top 20
* Top 30
* 0 bps
* 15 bps
* 30 bps
* 50 bps

### Fixed OOS Test

The OOS section should document:

* Fixed OOS start date
* OOS CAGR
* OOS maximum drawdown
* OOS volatility
* OOS Sharpe
* OOS positive months
* OOS rolling results

### Important

The OOS period must remain a **fixed validation period**.

It should not be used to continuously optimize the production parameters.

The current research code explicitly defines the OOS start as `2021-01-01` and states that OOS does not optimize parameters.

---

# 18. Research Limitations

The most important limitation is survivorship bias.

The historical backtest uses the **current Nifty 500 constituent list for historical periods**.

Therefore:

```text
Historical backtest
       +
Current constituents
       ↓
Survivorship bias
```

This means historical performance should not be interpreted as a perfectly reconstructed historical Nifty 500 portfolio.

Other limitations include:

* yfinance data availability can vary by stock.
* Listing history varies across securities.
* Corporate actions and historical data quality can affect results.
* Backtest execution assumptions may differ from live execution.
* Brokerage, taxes, liquidity and market impact can differ.
* Historical CAGR is not a guarantee of future CAGR.
* The OOS test remains subject to current-universe survivorship bias.

The backtest code explicitly documents the current-universe survivorship limitation.

---

# 19. What the System Does NOT Do

MomentumPortfolioLab does not:

* Place broker orders.
* Guarantee returns.
* Forecast a specific future CAGR.
* Use fundamentals.
* Use analyst opinions.
* Use discretionary stock selection.
* Change the portfolio every weekend.
* Use EMA breadth as an automatic portfolio switch.
* Treat current displayed rank movement as a sell signal.

---

# 20. Core Philosophy

The project intentionally separates **research** from **execution of the model**.

```text
backtest.py
     ↓
Historical research
     ↓
Robustness
     ↓
OOS validation
     ↓
Strategy specification
     ↓
main.py
     ↓
Current market application
     ↓
Monthly portfolio decision
```

The production engine should remain mechanically aligned with the tested strategy.

---

# 21. Quick Start

From PowerShell:

```powershell
cd C:\Users\natte\Documents\Project\InvestmentResearchLab\src\MomentumPortfolioLab
```

Run the production decision engine:

```powershell
python main.py
```

Run the historical research:

```powershell
python "backtest.py"
```

---

# 22. One-Line Definition

**MomentumPortfolioLab is a monthly Top-20 Nifty 500 momentum portfolio engine using 50% 12–1 momentum + 50% 6M momentum, volatility adjustment, cross-sectional ranking and equal weighting, with `main.py` serving as the production decision engine and `backtest.py` serving as the historical/OOS validation engine.**