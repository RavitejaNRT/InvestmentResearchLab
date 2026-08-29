# InvestmentResearchLab

InvestmentResearchLab is a Python-based quantitative research project for developing, testing, and evaluating systematic stock-selection and positional-trading strategies.

The project focuses on turning clearly defined trading ideas into **repeatable, rule-based screening and ranking engines** rather than relying on subjective chart interpretation.

## Project Goals

The primary objectives are to:

* Convert trading ideas into explicit, programmable rules.
* Identify stocks that satisfy predefined momentum and trend conditions.
* Separate different strategy definitions so they can be researched independently.
* Rank qualifying stocks based on measurable characteristics.
* Produce clear, structured output for further analysis and decision-making.
* Keep strategy logic transparent and easy to modify.
* Build a foundation for future backtesting and performance analysis.

## Strategies

The current research focuses on two related momentum strategies.

### Momentum Breakout or Recovery

**Momentum Edge**

> Established Uptrend AND (20-Day Breakout OR Controlled Retracement Recovery)

This strategy looks for stocks already exhibiting an established bullish trend and qualifying through either:

1. A recent 20-day breakout, **or**
2. A controlled retracement followed by recovery.

Implementation:

```text
src/MomBreakoutOrRecovery/
```

See the strategy-specific README for the detailed rules, calculations, configuration, and output.

### Momentum Breakout Then Recovery

**Momentum Continuation**

> Established Uptrend AND (20-Day Breakout followed by Controlled Retracement Recovery)

This is a stricter continuation setup.

A stock must first establish an uptrend, experience a qualifying 20-day breakout, subsequently undergo a controlled retracement, and then demonstrate recovery.

Implementation:

```text
src/MomBreakoutThenRecovery/
```

See the strategy-specific README for the detailed rules and implementation.

## Project Structure

```text
InvestmentResearchLab/
│
├── README.md
│
├── src/
│   │
│   ├── MomBreakoutOrRecovery/
│   │   ├── README.md
│   │   └── ...
│   │
│   └── MomBreakoutThenRecovery/
│       ├── README.md
│       └── ...
│
└── tests/
    └── ...
```

Each strategy is intentionally maintained as a separate module so that its rules, calculations, data processing, and outputs can evolve independently.

## Design Philosophy

The project follows a few principles:

### 1. Rules Before Opinions

Trading decisions should be expressed as measurable conditions wherever possible.

Instead of:

> "The stock looks strong."

The strategy should define what "strong" means through objective conditions such as trend, price action, breakout behaviour, retracement depth, recovery, volume, and other measurable factors.

### 2. Simple Before Complex

The goal is not to build the most complicated model.

A simpler strategy with clearly understood behaviour is preferable to a highly optimized system whose results are difficult to explain or reproduce.

### 3. Separate Strategy Definitions

Similar-looking strategies should not be combined simply because they share common components.

For example:

```text
Momentum Edge
    Uptrend
        AND
    (Breakout OR Recovery)
```

is intentionally different from:

```text
Momentum Continuation
    Uptrend
        AND
    Breakout
        AND
    Recovery
```

Keeping them separate allows their results and behaviour to be evaluated independently.

### 4. Reproducible Research

The same inputs and rules should produce the same screening results.

This makes it possible to compare strategy versions and understand whether changes genuinely improve the strategy.

### 5. Avoid Unnecessary Optimization

The objective is not to continuously optimize every piece of code or parameter.

Code should first be:

* Correct
* Understandable
* Maintainable
* Reproducible

Optimization should only be introduced when there is a clear reason and measurable benefit.

## Technology

The project is currently implemented in:

* Python
* Pandas
* NumPy
* yfinance
* Python virtual environments
* Git / GitHub

Additional libraries may be introduced as the research framework evolves.

## Current Status

The project is actively under development.

Current focus:

* Momentum strategy implementation
* Stock screening
* Price and volume analysis
* Strategy-specific ranking
* Structured terminal output
* Research and validation

Future development may include:

* Historical backtesting
* Performance statistics
* Risk/reward analysis
* Portfolio-level analysis
* Strategy comparison
* Trade tracking
* Visualization
* Parameter sensitivity analysis

## Important Disclaimer

InvestmentResearchLab is a **research and analysis project**.

The output of these strategies is not financial advice and should not be treated as a guaranteed prediction of future stock performance.

Historical or simulated results do not guarantee future returns. Any live trading decision should consider risk, liquidity, transaction costs, market conditions, and individual circumstances.

## Author

**Raviteja**

InvestmentResearchLab is developed as an ongoing quantitative trading and investment research project.
