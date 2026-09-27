"""
================================================================================
MomentumPortfolioLab
================================================================================

OHLCV-ONLY MONTHLY MOMENTUM PORTFOLIO BACKTEST

RESEARCH STRATEGY
-----------------
Baseline strategy:

    Universe       : Current Nifty 500
    Data           : OHLCV only
    Momentum       : 12-1 momentum + 6-month momentum
    Adjustment     : Volatility adjusted
    Ranking        : Cross-sectional z-score
    Portfolio      : Top 20
    Weighting      : Equal weight
    Rebalance      : Monthly

ROBUSTNESS TESTS
----------------
The same research run also tests:

    1. Top 10
    2. Top 20
    3. Top 30

Transaction-cost sensitivity:

    0 bps
    15 bps
    30 bps
    50 bps

OOS TEST
--------
A fixed strategy is evaluated on a later out-of-sample period.

The OOS period does NOT optimize parameters.

IMPORTANT
---------
trade_data.py is NOT modified.

trade_data.py is imported dynamically and ONLY:

    refresh_nifty500_universe()

is called.

The current Nifty 500 universe is used for all historical periods,
therefore historical results contain survivorship bias.
"""

from __future__ import annotations

import importlib.util
import math
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import yfinance as yf


# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_DIR = Path(__file__).resolve().parent

RESULTS_DIR = PROJECT_DIR / "results"

TRADE_DATA_FILE = PROJECT_DIR / "trade_data.py"

UNIVERSE_FILE = PROJECT_DIR / "universe.py"


# =============================================================================
# BACKTEST PERIOD
# =============================================================================

START_DATE = "2011-01-01"

DOWNLOAD_START_DATE = "2010-01-01"

END_DATE = None


# =============================================================================
# OOS PERIOD
# =============================================================================
#
# This is a fixed historical split.
#
# The strategy parameters are NOT optimized using the OOS period.
#
# Train / development period:
#
#     2011-03 through 2020-12 approximately
#
# OOS:
#
#     2021 onward
#
# The exact available monthly dates determine the actual first OOS month.
# =============================================================================

OOS_START_DATE = "2021-01-01"


# =============================================================================
# BASELINE PORTFOLIO
# =============================================================================

TOP_N = 20

INITIAL_CAPITAL = 1_000_000.0


# =============================================================================
# TRANSACTION COST
# =============================================================================
#
# Baseline:
#
#     transaction cost = 10 bps
#     slippage          = 5 bps
#     total             = 15 bps
#
# Robustness test treats total cost directly.
# =============================================================================

TRANSACTION_COST_BPS = 10.0

SLIPPAGE_BPS = 5.0

TOTAL_COST_BPS = (
    TRANSACTION_COST_BPS
    +
    SLIPPAGE_BPS
)


# =============================================================================
# ROBUSTNESS SETTINGS
# =============================================================================

ROBUSTNESS_TOP_N = [
    10,
    20,
    30,
]

ROBUSTNESS_TOTAL_COST_BPS = [
    0.0,
    15.0,
    30.0,
    50.0,
]


# =============================================================================
# DATA SETTINGS
# =============================================================================

MIN_TRADING_DAYS = 260

VOL_LOOKBACK_DAYS = 252


# =============================================================================
# STRATEGY SETTINGS
# =============================================================================

MOMENTUM_12_1_WEIGHT = 0.50

MOMENTUM_6M_WEIGHT = 0.50


# =============================================================================
# OPTIONAL MARKET REGIME
# =============================================================================
#
# Baseline remains OFF.
#
# We do NOT include a regime filter in the robustness comparison because
# the objective is first to establish whether the pure momentum strategy
# itself is robust.
# =============================================================================

USE_MARKET_REGIME_FILTER = False

MARKET_MA_MONTHS = 10

NEGATIVE_REGIME_EXPOSURE = 0.0


# =============================================================================
# DISPLAY
# =============================================================================

pd.set_option(
    "display.width",
    200,
)

pd.set_option(
    "display.max_columns",
    100,
)

pd.set_option(
    "display.max_rows",
    100,
)


# =============================================================================
# LOGGING
# =============================================================================

def log(message: str = "") -> None:
    print(
        message,
        flush=True,
    )


# =============================================================================
# RESULTS DIRECTORY
# =============================================================================

def ensure_results_dir() -> None:
    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


# =============================================================================
# STEP 1
# REFRESH NIFTY 500
# =============================================================================

def run_trade_data() -> None:
    """
    Import the existing trade_data.py and call ONLY:

        refresh_nifty500_universe()

    trade_data.py is deliberately NOT executed as a subprocess.
    """

    if not TRADE_DATA_FILE.exists():
        raise FileNotFoundError(
            "trade_data.py not found:\n"
            f"{TRADE_DATA_FILE}"
        )

    log()
    log("=" * 100)
    log("STEP 1 — BUILDING NIFTY 500 UNIVERSE")
    log("=" * 100)

    log(
        f"trade_data.py : {TRADE_DATA_FILE}"
    )

    log()

    spec = importlib.util.spec_from_file_location(
        "momentum_portfolio_trade_data",
        str(TRADE_DATA_FILE),
    )

    if spec is None:
        raise RuntimeError(
            "Could not create import specification for trade_data.py."
        )

    if spec.loader is None:
        raise RuntimeError(
            "Could not create loader for trade_data.py."
        )

    module = importlib.util.module_from_spec(
        spec,
    )

    try:
        spec.loader.exec_module(
            module,
        )

    except Exception as exc:
        raise RuntimeError(
            "Could not import trade_data.py.\n\n"
            f"Error: {exc}"
        ) from exc

    refresh_function = getattr(
        module,
        "refresh_nifty500_universe",
        None,
    )

    if refresh_function is None:
        raise AttributeError(
            "The existing trade_data.py does not contain:\n\n"
            "refresh_nifty500_universe()"
        )

    log(
        "Calling existing refresh_nifty500_universe()..."
    )

    try:
        symbols = refresh_function()

    except Exception as exc:
        raise RuntimeError(
            "Nifty 500 universe refresh failed.\n\n"
            f"Error: {exc}"
        ) from exc

    if not UNIVERSE_FILE.exists():
        raise FileNotFoundError(
            "trade_data.py completed but universe.py was not created:\n"
            f"{UNIVERSE_FILE}"
        )

    if symbols is None:
        raise RuntimeError(
            "refresh_nifty500_universe() returned None."
        )

    try:
        count = len(symbols)

    except TypeError as exc:
        raise RuntimeError(
            "refresh_nifty500_universe() did not return "
            "a valid symbol collection."
        ) from exc

    log()
    log(
        f"Universe created : {UNIVERSE_FILE}"
    )
    log(
        f"Symbols returned : {count}"
    )


# =============================================================================
# STEP 2
# LOAD UNIVERSE
# =============================================================================

def load_universe() -> List[str]:
    """
    Load symbols from generated universe.py.
    """

    log()
    log("=" * 100)
    log("STEP 2 — LOADING GENERATED UNIVERSE")
    log("=" * 100)

    if not UNIVERSE_FILE.exists():
        raise FileNotFoundError(
            f"universe.py not found:\n{UNIVERSE_FILE}"
        )

    spec = importlib.util.spec_from_file_location(
        "momentum_portfolio_universe",
        str(UNIVERSE_FILE),
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            "Could not load universe.py."
        )

    module = importlib.util.module_from_spec(
        spec,
    )

    spec.loader.exec_module(
        module,
    )

    if not hasattr(
        module,
        "symbols",
    ):
        raise AttributeError(
            "universe.py does not contain "
            "the expected 'symbols' variable."
        )

    raw_symbols = getattr(
        module,
        "symbols",
    )

    if not isinstance(
        raw_symbols,
        (list, tuple, set),
    ):
        raise TypeError(
            "universe.py 'symbols' must be a list, tuple or set."
        )

    symbols = []

    for symbol in raw_symbols:

        if symbol is None:
            continue

        symbol = str(
            symbol
        ).strip().upper()

        if not symbol:
            continue

        if not symbol.endswith(
            ".NS"
        ):
            symbol += ".NS"

        symbols.append(
            symbol
        )

    symbols = sorted(
        set(symbols)
    )

    log(
        f"Nifty 500 universe : {len(symbols)} symbols"
    )

    if len(symbols) < 400:
        log()
        log(
            "WARNING: Fewer than 400 symbols were loaded."
        )

    return symbols


# =============================================================================
# STEP 3
# DOWNLOAD OHLCV
# =============================================================================

def download_ohlcv(
    symbols: List[str],
) -> pd.DataFrame:
    """
    Download historical OHLCV through yfinance.

    Adjusted close is used because the strategy needs a price series
    that handles corporate actions consistently.
    """

    log()
    log("=" * 100)
    log("STEP 3 — DOWNLOADING HISTORICAL OHLCV")
    log("=" * 100)

    log(
        f"Symbols       : {len(symbols)}"
    )

    log(
        f"Download from : {DOWNLOAD_START_DATE}"
    )

    log(
        f"Download to   : {END_DATE or 'latest'}"
    )

    log()

    start_time = time.time()

    data = yf.download(
        tickers=symbols,
        start=DOWNLOAD_START_DATE,
        end=END_DATE,
        interval="1d",
        auto_adjust=True,
        progress=True,
        group_by="column",
        threads=True,
    )

    elapsed = (
        time.time()
        -
        start_time
    )

    if data is None or data.empty:
        raise RuntimeError(
            "yfinance returned no historical data."
        )

    log()

    log(
        f"Download completed in {elapsed:.1f} seconds."
    )

    if isinstance(
        data.columns,
        pd.MultiIndex,
    ):

        level0 = (
            data.columns
            .get_level_values(0)
        )

        if "Close" not in level0:
            raise RuntimeError(
                "Close prices were not found in yfinance response."
            )

        close = (
            data["Close"]
            .copy()
        )

    else:

        if "Close" not in data.columns:
            raise RuntimeError(
                "Close prices were not found in yfinance response."
            )

        close = (
            data[
                ["Close"]
            ]
            .copy()
        )

        if len(symbols) == 1:
            close.columns = [
                symbols[0]
            ]

    close.index = pd.to_datetime(
        close.index
    )

    if getattr(
        close.index,
        "tz",
        None,
    ) is not None:

        close.index = (
            close.index
            .tz_localize(None)
        )

    close = (
        close
        .sort_index()
    )

    valid_symbols = []

    invalid_symbols = []

    for symbol in symbols:

        if symbol not in close.columns:
            invalid_symbols.append(
                symbol
            )
            continue

        series = (
            close[symbol]
            .dropna()
        )

        if len(series) < MIN_TRADING_DAYS:
            invalid_symbols.append(
                symbol
            )
        else:
            valid_symbols.append(
                symbol
            )

    close = (
        close[
            valid_symbols
        ]
        .copy()
    )

    log(
        f"Requested symbols : {len(symbols)}"
    )

    log(
        f"Valid symbols     : {len(valid_symbols)}"
    )

    log(
        f"Invalid symbols   : {len(invalid_symbols)}"
    )

    if invalid_symbols:

        log()
        log(
            "First invalid symbols:"
        )

        for symbol in invalid_symbols[:20]:
            log(
                f"  {symbol}"
            )

    if len(valid_symbols) < 100:
        raise RuntimeError(
            "Too few valid symbols after OHLCV validation."
        )

    return close


# =============================================================================
# STEP 4
# MONTH-END PRICES
# =============================================================================

def get_month_end_prices(
    close: pd.DataFrame,
) -> pd.DataFrame:
    """
    Convert daily closes to the last available trading-day close
    of each calendar month.
    """

    monthly_prices = (
        close
        .resample("ME")
        .last()
    )

    monthly_prices = (
        monthly_prices
        .dropna(
            how="all"
        )
    )

    return monthly_prices


# =============================================================================
# TRAILING VOLATILITY
# =============================================================================

def calculate_monthly_volatility(
    close: pd.DataFrame,
) -> pd.DataFrame:
    """
    Trailing annualized daily volatility.

    At every date only historical data through that date is used.
    """

    daily_returns = (
        close
        .pct_change()
    )

    rolling_std = (
        daily_returns
        .rolling(
            window=VOL_LOOKBACK_DAYS,
            min_periods=int(
                VOL_LOOKBACK_DAYS * 0.80
            ),
        )
        .std()
    )

    annualized_volatility = (
        rolling_std
        *
        np.sqrt(252)
    )

    monthly_volatility = (
        annualized_volatility
        .resample("ME")
        .last()
    )

    return monthly_volatility


# =============================================================================
# CROSS-SECTIONAL Z SCORE
# =============================================================================

def cross_sectional_zscore(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Cross-sectional z-score for every month.
    """

    mean = (
        df
        .mean(
            axis=1
        )
    )

    std = (
        df
        .std(
            axis=1,
            ddof=0,
        )
    )

    std = (
        std
        .replace(
            0,
            np.nan,
        )
    )

    return (
        df
        .sub(
            mean,
            axis=0,
        )
        .div(
            std,
            axis=0,
        )
    )


# =============================================================================
# STEP 5
# MOMENTUM
# =============================================================================

def calculate_momentum_scores(
    monthly_prices: pd.DataFrame,
    monthly_volatility: pd.DataFrame,
) -> Tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    """
    Calculate:

        12-1 momentum
        6-month momentum
        volatility-adjusted momentum
        composite cross-sectional score

    Signal month T uses information only through T-1.

        12-1:
            P[t-1] / P[t-13] - 1

        6M:
            P[t-1] / P[t-7] - 1
    """

    previous_month_price = (
        monthly_prices
        .shift(1)
    )

    price_13_months_back = (
        monthly_prices
        .shift(13)
    )

    price_7_months_back = (
        monthly_prices
        .shift(7)
    )

    momentum_12_1_return = (
        previous_month_price
        /
        price_13_months_back
        -
        1.0
    )

    momentum_6m_return = (
        previous_month_price
        /
        price_7_months_back
        -
        1.0
    )

    previous_month_volatility = (
        monthly_volatility
        .shift(1)
    )

    previous_month_volatility = (
        previous_month_volatility
        .replace(
            0,
            np.nan,
        )
    )

    momentum_12_1 = (
        momentum_12_1_return
        /
        previous_month_volatility
    )

    momentum_6m = (
        momentum_6m_return
        /
        previous_month_volatility
    )

    z_12_1 = (
        cross_sectional_zscore(
            momentum_12_1
        )
    )

    z_6m = (
        cross_sectional_zscore(
            momentum_6m
        )
    )

    composite = (
        MOMENTUM_12_1_WEIGHT
        *
        z_12_1
        +
        MOMENTUM_6M_WEIGHT
        *
        z_6m
    )

    return (
        momentum_12_1_return,
        momentum_6m_return,
        composite,
    )


# =============================================================================
# PORTFOLIO SELECTION
# =============================================================================

def select_portfolio(
    score_row: pd.Series,
    price_row: pd.Series,
    top_n: int,
) -> List[str]:
    """
    Select highest-ranked stocks.
    """

    ranking = pd.DataFrame(
        {
            "score": score_row,
            "price": price_row,
        }
    )

    ranking = (
        ranking
        .replace(
            [
                np.inf,
                -np.inf,
            ],
            np.nan,
        )
        .dropna(
            subset=[
                "score",
                "price",
            ]
        )
    )

    if ranking.empty:
        return []

    ranking = (
        ranking
        .sort_values(
            by=[
                "score",
                "price",
            ],
            ascending=[
                False,
                False,
            ],
        )
    )

    return list(
        ranking
        .head(top_n)
        .index
    )


# =============================================================================
# MARKET REGIME
# =============================================================================

def calculate_market_regime(
    monthly_prices: pd.DataFrame,
) -> pd.Series:
    """
    Equal-weighted Nifty 500 price proxy.

    Baseline is OFF.
    """

    market_proxy = (
        monthly_prices
        .mean(
            axis=1
        )
    )

    moving_average = (
        market_proxy
        .rolling(
            MARKET_MA_MONTHS,
            min_periods=MARKET_MA_MONTHS,
        )
        .mean()
    )

    return (
        market_proxy
        >
        moving_average
    )


# =============================================================================
# TURNOVER
# =============================================================================

def calculate_turnover(
    old_portfolio: List[str],
    new_portfolio: List[str],
    top_n: int,
) -> float:
    """
    Equal-weight turnover.

    If 4 stocks are replaced in a 20-stock portfolio:

        turnover = 20%
    """

    old_set = set(
        old_portfolio
    )

    new_set = set(
        new_portfolio
    )

    if not old_set:
        return (
            1.0
            if new_set
            else 0.0
        )

    sells = (
        old_set
        -
        new_set
    )

    buys = (
        new_set
        -
        old_set
    )

    denominator = (
        2.0
        *
        top_n
    )

    if denominator <= 0:
        return 0.0

    turnover = (
        len(sells)
        +
        len(buys)
    ) / denominator

    return float(
        turnover
    )


# =============================================================================
# GENERIC BACKTEST ENGINE
# =============================================================================

def run_backtest_engine(
    monthly_prices: pd.DataFrame,
    scores: pd.DataFrame,
    top_n: int,
    total_cost_bps: float,
    start_date: str | None = None,
    end_date: str | None = None,
) -> Tuple[
    pd.DataFrame,
    pd.DataFrame,
]:
    """
    Generic monthly walk-forward backtest.

    Signal at month T:

        - calculate using information through T-1
        - select portfolio at T
        - hold from T close to T+1 close

    This engine is reused for:

        baseline
        Top 10
        Top 20
        Top 30
        cost sensitivity
        OOS
    """

    prices = monthly_prices.copy()

    score_data = scores.copy()

    if start_date is not None:

        timestamp = pd.Timestamp(
            start_date
        )

        prices = (
            prices
            .loc[
                prices.index >= timestamp
            ]
        )

        score_data = (
            score_data
            .loc[
                score_data.index >= timestamp
            ]
        )

    if end_date is not None:

        timestamp = pd.Timestamp(
            end_date
        )

        prices = (
            prices
            .loc[
                prices.index <= timestamp
            ]
        )

        score_data = (
            score_data
            .loc[
                score_data.index <= timestamp
            ]
        )

    if len(prices) < 3:
        raise RuntimeError(
            "Insufficient monthly observations for backtest."
        )

    market_regime = (
        calculate_market_regime(
            prices
        )
    )

    dates = (
        prices.index
    )

    portfolio_records = []

    monthly_records = []

    capital = (
        INITIAL_CAPITAL
    )

    previous_portfolio: List[str] = []

    for i in range(
        1,
        len(dates) - 1,
    ):

        signal_date = (
            dates[i]
        )

        next_date = (
            dates[i + 1]
        )

        if signal_date not in score_data.index:
            continue

        score_row = (
            score_data
            .loc[
                signal_date
            ]
        )

        price_row = (
            prices
            .loc[
                signal_date
            ]
        )

        new_portfolio = (
            select_portfolio(
                score_row,
                price_row,
                top_n,
            )
        )

        if len(new_portfolio) < top_n:
            continue

        turnover = (
            calculate_turnover(
                previous_portfolio,
                new_portfolio,
                top_n,
            )
        )

        entry_prices = (
            prices
            .loc[
                signal_date,
                new_portfolio,
            ]
        )

        exit_prices = (
            prices
            .loc[
                next_date,
                new_portfolio,
            ]
        )

        stock_returns = (
            exit_prices
            /
            entry_prices
            -
            1.0
        )

        stock_returns = (
            stock_returns
            .replace(
                [
                    np.inf,
                    -np.inf,
                ],
                np.nan,
            )
            .dropna()
        )

        minimum_valid = max(
            5,
            int(
                top_n
                *
                0.70
            ),
        )

        if len(stock_returns) < minimum_valid:
            continue

        gross_return = float(
            stock_returns
            .mean()
        )

        regime_positive = bool(
            market_regime
            .loc[
                signal_date
            ]
        )

        if USE_MARKET_REGIME_FILTER:

            if not regime_positive:

                gross_return *= (
                    NEGATIVE_REGIME_EXPOSURE
                )

        trading_cost = (
            turnover
            *
            total_cost_bps
            /
            10000.0
        )

        net_return = (
            gross_return
            -
            trading_cost
        )

        capital_before = (
            capital
        )

        capital *= (
            1.0
            +
            net_return
        )

        portfolio_records.append(
            {
                "signal_date":
                    signal_date,

                "investment_month":
                    next_date,

                "portfolio":
                    "|".join(
                        new_portfolio
                    ),

                "portfolio_size":
                    len(
                        new_portfolio
                    ),

                "turnover":
                    turnover,

                "gross_return":
                    gross_return,

                "trading_cost":
                    trading_cost,

                "net_return":
                    net_return,

                "capital_before":
                    capital_before,

                "capital_after":
                    capital,

                "market_regime_positive":
                    regime_positive,
            }
        )

        monthly_records.append(
            {
                "date":
                    next_date,

                "return":
                    net_return,

                "capital":
                    capital,
            }
        )

        previous_portfolio = (
            new_portfolio
        )

    portfolio_df = pd.DataFrame(
        portfolio_records
    )

    monthly_df = pd.DataFrame(
        monthly_records
    )

    if portfolio_df.empty:
        raise RuntimeError(
            "Backtest produced no portfolio observations."
        )

    return (
        portfolio_df,
        monthly_df,
    )


# =============================================================================
# PERFORMANCE CALCULATION
# =============================================================================

def calculate_performance(
    monthly_df: pd.DataFrame,
) -> Dict[str, float]:
    """
    Calculate portfolio statistics.
    """

    returns = (
        monthly_df[
            "return"
        ]
        .astype(float)
    )

    wealth = (
        1.0
        +
        returns
    ).cumprod()

    final_multiple = float(
        wealth.iloc[-1]
    )

    dates = pd.to_datetime(
        monthly_df[
            "date"
        ]
    )

    start_date = (
        dates.iloc[0]
    )

    end_date = (
        dates.iloc[-1]
    )

    days = max(
        1,
        (
            end_date
            -
            start_date
        ).days,
    )

    years = (
        days
        /
        365.25
    )

    cagr = (
        final_multiple
        **
        (
            1.0
            /
            years
        )
        -
        1.0
    )

    running_max = (
        wealth
        .cummax()
    )

    drawdown = (
        wealth
        /
        running_max
        -
        1.0
    )

    max_drawdown = float(
        drawdown.min()
    )

    monthly_std = returns.std(
        ddof=1
    )

    annualized_volatility = (
        monthly_std
        *
        math.sqrt(12)
    )

    if (
        len(returns) > 1
        and
        monthly_std > 0
    ):

        sharpe = (
            returns.mean()
            /
            monthly_std
            *
            math.sqrt(12)
        )

    else:

        sharpe = np.nan

    positive_months = float(
        (
            returns
            >
            0
        )
        .mean()
    )

    wealth_series = pd.Series(
        wealth.values,
        index=dates,
    )

    rolling_3y = (
        wealth_series
        /
        wealth_series.shift(36)
    ) ** (
        12.0
        /
        36.0
    ) - 1.0

    rolling_3y = (
        rolling_3y
        .dropna()
    )

    rolling_5y = (
        wealth_series
        /
        wealth_series.shift(60)
    ) ** (
        12.0
        /
        60.0
    ) - 1.0

    rolling_5y = (
        rolling_5y
        .dropna()
    )

    return {

        "Start Date":
            start_date,

        "End Date":
            end_date,

        "Years":
            years,

        "Initial Capital":
            INITIAL_CAPITAL,

        "Final Capital":
            INITIAL_CAPITAL
            *
            final_multiple,

        "Final Multiple":
            final_multiple,

        "CAGR":
            cagr,

        "Max Drawdown":
            max_drawdown,

        "Annualized Volatility":
            annualized_volatility,

        "Sharpe":
            sharpe,

        "Positive Months":
            positive_months,

        "Months":
            len(
                returns
            ),

        "Rolling 3Y CAGR Median":
            (
                float(
                    rolling_3y
                    .median()
                )
                if not rolling_3y.empty
                else np.nan
            ),

        "Rolling 3Y CAGR Minimum":
            (
                float(
                    rolling_3y
                    .min()
                )
                if not rolling_3y.empty
                else np.nan
            ),

        "Rolling 3Y CAGR >= 27%":
            (
                float(
                    (
                        rolling_3y
                        >=
                        0.27
                    )
                    .mean()
                )
                if not rolling_3y.empty
                else np.nan
            ),

        "Rolling 5Y CAGR Median":
            (
                float(
                    rolling_5y
                    .median()
                )
                if not rolling_5y.empty
                else np.nan
            ),

        "Rolling 5Y CAGR Minimum":
            (
                float(
                    rolling_5y
                    .min()
                )
                if not rolling_5y.empty
                else np.nan
            ),

        "Rolling 5Y CAGR >= 27%":
            (
                float(
                    (
                        rolling_5y
                        >=
                        0.27
                    )
                    .mean()
                )
                if not rolling_5y.empty
                else np.nan
            ),
    }


# =============================================================================
# ANNUAL RETURNS
# =============================================================================

def calculate_annual_returns(
    monthly_df: pd.DataFrame,
) -> pd.DataFrame:

    temp = (
        monthly_df
        .copy()
    )

    temp["date"] = pd.to_datetime(
        temp["date"]
    )

    temp["year"] = (
        temp["date"]
        .dt.year
    )

    annual = (
        temp
        .groupby(
            "year"
        )["return"]
        .apply(
            lambda x:
            (
                1.0 + x
            ).prod()
            -
            1.0
        )
        .reset_index()
    )

    annual.columns = [
        "Year",
        "Return",
    ]

    return annual


# =============================================================================
# PORTFOLIO HISTORY
# =============================================================================

def expand_portfolio_history(
    portfolio_df: pd.DataFrame,
) -> pd.DataFrame:

    rows = []

    for _, row in (
        portfolio_df
        .iterrows()
    ):

        symbols = (
            str(
                row[
                    "portfolio"
                ]
            )
            .split("|")
        )

        for rank, symbol in enumerate(
            symbols,
            start=1,
        ):

            rows.append(
                {

                    "signal_date":
                        row[
                            "signal_date"
                        ],

                    "investment_month":
                        row[
                            "investment_month"
                        ],

                    "rank":
                        rank,

                    "symbol":
                        symbol,

                    "turnover":
                        row[
                            "turnover"
                        ],

                    "gross_portfolio_return":
                        row[
                            "gross_return"
                        ],

                    "net_portfolio_return":
                        row[
                            "net_return"
                        ],

                    "capital_after":
                        row[
                            "capital_after"
                        ],
                }
            )

    return pd.DataFrame(
        rows
    )


# =============================================================================
# LATEST SIGNAL
# =============================================================================

def generate_latest_signal(
    monthly_prices: pd.DataFrame,
    scores: pd.DataFrame,
    top_n: int,
) -> pd.DataFrame:
    """
    Generate latest available ranking.
    """

    if scores.empty:
        return pd.DataFrame()

    latest_date = (
        scores
        .index[-1]
    )

    score_row = (
        scores
        .loc[
            latest_date
        ]
    )

    price_row = (
        monthly_prices
        .loc[
            latest_date
        ]
    )

    selected = (
        select_portfolio(
            score_row,
            price_row,
            top_n,
        )
    )

    ranking = pd.DataFrame(
        {
            "symbol":
                score_row.index,

            "score":
                score_row.values,

            "price":
                price_row
                .reindex(
                    score_row.index
                )
                .values,
        }
    )

    ranking = (
        ranking
        .replace(
            [
                np.inf,
                -np.inf,
            ],
            np.nan,
        )
        .dropna(
            subset=[
                "score",
            ]
        )
        .sort_values(
            by="score",
            ascending=False,
        )
    )

    rows = []

    for rank, (_, row) in enumerate(
        ranking
        .head(top_n)
        .iterrows(),
        start=1,
    ):

        symbol = (
            row[
                "symbol"
            ]
        )

        rows.append(
            {

                "signal_date":
                    latest_date,

                "rank":
                    rank,

                "symbol":
                    symbol,

                "score":
                    row[
                        "score"
                    ],

                "price":
                    row[
                        "price"
                    ],

                "action":
                    (
                        "BUY / HOLD"
                        if symbol in selected
                        else "WATCH"
                    ),
            }
        )

    return pd.DataFrame(
        rows
    )


# =============================================================================
# ROBUSTNESS — TOP N
# =============================================================================

def run_top_n_robustness(
    monthly_prices: pd.DataFrame,
    scores: pd.DataFrame,
) -> pd.DataFrame:
    """
    Test Top 10 / Top 20 / Top 30 with baseline 15 bps total cost.
    """

    rows = []

    for top_n in ROBUSTNESS_TOP_N:

        log(
            f"Running Top {top_n} robustness test..."
        )

        _, monthly_df = (
            run_backtest_engine(
                monthly_prices,
                scores,
                top_n=top_n,
                total_cost_bps=TOTAL_COST_BPS,
            )
        )

        performance = (
            calculate_performance(
                monthly_df
            )
        )

        rows.append(
            {

                "Top N":
                    top_n,

                "Total Cost (bps)":
                    TOTAL_COST_BPS,

                "CAGR":
                    performance[
                        "CAGR"
                    ],

                "Max Drawdown":
                    performance[
                        "Max Drawdown"
                    ],

                "Sharpe":
                    performance[
                        "Sharpe"
                    ],

                "Annualized Volatility":
                    performance[
                        "Annualized Volatility"
                    ],

                "Positive Months":
                    performance[
                        "Positive Months"
                    ],

                "Final Multiple":
                    performance[
                        "Final Multiple"
                    ],

                "Rolling 3Y CAGR Median":
                    performance[
                        "Rolling 3Y CAGR Median"
                    ],

                "Rolling 5Y CAGR Median":
                    performance[
                        "Rolling 5Y CAGR Median"
                    ],

                "Rolling 3Y >=27%":
                    performance[
                        "Rolling 3Y CAGR >= 27%"
                    ],

                "Rolling 5Y >=27%":
                    performance[
                        "Rolling 5Y CAGR >= 27%"
                    ],
            }
        )

    return pd.DataFrame(
        rows
    )


# =============================================================================
# ROBUSTNESS — TRANSACTION COST
# =============================================================================

def run_cost_robustness(
    monthly_prices: pd.DataFrame,
    scores: pd.DataFrame,
) -> pd.DataFrame:
    """
    Test total transaction costs:

        0
        15
        30
        50 bps

    using the baseline Top 20 portfolio.
    """

    rows = []

    for total_cost_bps in ROBUSTNESS_TOTAL_COST_BPS:

        log(
            f"Running cost sensitivity: {total_cost_bps:.0f} bps..."
        )

        _, monthly_df = (
            run_backtest_engine(
                monthly_prices,
                scores,
                top_n=TOP_N,
                total_cost_bps=total_cost_bps,
            )
        )

        performance = (
            calculate_performance(
                monthly_df
            )
        )

        rows.append(
            {

                "Top N":
                    TOP_N,

                "Total Cost (bps)":
                    total_cost_bps,

                "CAGR":
                    performance[
                        "CAGR"
                    ],

                "Max Drawdown":
                    performance[
                        "Max Drawdown"
                    ],

                "Sharpe":
                    performance[
                        "Sharpe"
                    ],

                "Annualized Volatility":
                    performance[
                        "Annualized Volatility"
                    ],

                "Positive Months":
                    performance[
                        "Positive Months"
                    ],

                "Final Multiple":
                    performance[
                        "Final Multiple"
                    ],

                "Rolling 3Y CAGR Median":
                    performance[
                        "Rolling 3Y CAGR Median"
                    ],

                "Rolling 5Y CAGR Median":
                    performance[
                        "Rolling 5Y CAGR Median"
                    ],
            }
        )

    return pd.DataFrame(
        rows
    )


# =============================================================================
# OOS TEST
# =============================================================================

def run_oos_test(
    monthly_prices: pd.DataFrame,
    scores: pd.DataFrame,
) -> Tuple[
    pd.DataFrame,
    pd.DataFrame,
    Dict[str, float],
]:
    """
    Run the fixed baseline strategy from OOS_START_DATE onward.

    No optimization occurs in this function.
    """

    log()
    log("=" * 100)
    log("OOS TEST — FIXED BASELINE STRATEGY")
    log("=" * 100)

    log(
        f"OOS start : {OOS_START_DATE}"
    )

    portfolio_df, monthly_df = (
        run_backtest_engine(
            monthly_prices,
            scores,
            top_n=TOP_N,
            total_cost_bps=TOTAL_COST_BPS,
            start_date=OOS_START_DATE,
        )
    )

    performance = (
        calculate_performance(
            monthly_df
        )
    )

    return (
        portfolio_df,
        monthly_df,
        performance,
    )


# =============================================================================
# SAVE RESULTS
# =============================================================================

def save_results(
    portfolio_df: pd.DataFrame,
    monthly_df: pd.DataFrame,
    performance: Dict[str, float],
    annual_df: pd.DataFrame,
    portfolio_history: pd.DataFrame,
    latest_signal: pd.DataFrame,
    top_n_robustness: pd.DataFrame,
    cost_robustness: pd.DataFrame,
    oos_portfolio_df: pd.DataFrame,
    oos_monthly_df: pd.DataFrame,
    oos_performance: Dict[str, float],
) -> None:

    ensure_results_dir()

    excel_file = (
        RESULTS_DIR
        /
        "momentum_portfolio_backtest.xlsx"
    )

    monthly_csv = (
        RESULTS_DIR
        /
        "momentum_portfolio_monthly_returns.csv"
    )

    portfolio_csv = (
        RESULTS_DIR
        /
        "momentum_portfolio_history.csv"
    )

    latest_csv = (
        RESULTS_DIR
        /
        "momentum_portfolio_latest_signal.csv"
    )

    top_n_csv = (
        RESULTS_DIR
        /
        "momentum_portfolio_topn_robustness.csv"
    )

    cost_csv = (
        RESULTS_DIR
        /
        "momentum_portfolio_cost_robustness.csv"
    )

    oos_monthly_csv = (
        RESULTS_DIR
        /
        "momentum_portfolio_oos_monthly_returns.csv"
    )

    oos_portfolio_csv = (
        RESULTS_DIR
        /
        "momentum_portfolio_oos_portfolio_history.csv"
    )

    performance_df = pd.DataFrame(
        list(
            performance.items()
        ),
        columns=[
            "Metric",
            "Value",
        ],
    )

    oos_performance_df = pd.DataFrame(
        list(
            oos_performance.items()
        ),
        columns=[
            "Metric",
            "Value",
        ],
    )

    with pd.ExcelWriter(
        excel_file,
        engine="openpyxl",
    ) as writer:

        performance_df.to_excel(
            writer,
            sheet_name="Performance",
            index=False,
        )

        oos_performance_df.to_excel(
            writer,
            sheet_name="OOS Performance",
            index=False,
        )

        top_n_robustness.to_excel(
            writer,
            sheet_name="TopN Robustness",
            index=False,
        )

        cost_robustness.to_excel(
            writer,
            sheet_name="Cost Robustness",
            index=False,
        )

        annual_df.to_excel(
            writer,
            sheet_name="Annual Returns",
            index=False,
        )

        monthly_df.to_excel(
            writer,
            sheet_name="Monthly Returns",
            index=False,
        )

        portfolio_df.to_excel(
            writer,
            sheet_name="Monthly Portfolio",
            index=False,
        )

        portfolio_history.to_excel(
            writer,
            sheet_name="Portfolio Holdings",
            index=False,
        )

        latest_signal.to_excel(
            writer,
            sheet_name="Latest Signal",
            index=False,
        )

        oos_monthly_df.to_excel(
            writer,
            sheet_name="OOS Monthly Returns",
            index=False,
        )

        oos_portfolio_df.to_excel(
            writer,
            sheet_name="OOS Portfolio",
            index=False,
        )

    monthly_df.to_csv(
        monthly_csv,
        index=False,
    )

    portfolio_history.to_csv(
        portfolio_csv,
        index=False,
    )

    latest_signal.to_csv(
        latest_csv,
        index=False,
    )

    top_n_robustness.to_csv(
        top_n_csv,
        index=False,
    )

    cost_robustness.to_csv(
        cost_csv,
        index=False,
    )

    oos_monthly_df.to_csv(
        oos_monthly_csv,
        index=False,
    )

    oos_portfolio_df.to_csv(
        oos_portfolio_csv,
        index=False,
    )

    log()
    log("=" * 100)
    log("RESULT FILES")
    log("=" * 100)

    log(
        f"Excel : {excel_file}"
    )

    log(
        f"CSV   : {monthly_csv}"
    )

    log(
        f"CSV   : {portfolio_csv}"
    )

    log(
        f"CSV   : {latest_csv}"
    )

    log(
        f"CSV   : {top_n_csv}"
    )

    log(
        f"CSV   : {cost_csv}"
    )

    log(
        f"CSV   : {oos_monthly_csv}"
    )

    log(
        f"CSV   : {oos_portfolio_csv}"
    )


# =============================================================================
# PRINT PERFORMANCE
# =============================================================================

def print_performance_block(
    title: str,
    performance: Dict[str, float],
) -> None:

    def pct(value):

        if pd.isna(value):
            return "N/A"

        return (
            f"{value * 100:.2f}%"
        )

    log()
    log("=" * 100)
    log(title)
    log("=" * 100)

    log(
        f"Period                 : "
        f"{performance['Start Date'].date()} "
        f"→ "
        f"{performance['End Date'].date()}"
    )

    log(
        f"Years                  : "
        f"{performance['Years']:.2f}"
    )

    log(
        f"Initial capital        : "
        f"Rs.{performance['Initial Capital']:,.0f}"
    )

    log(
        f"Final capital          : "
        f"Rs.{performance['Final Capital']:,.0f}"
    )

    log(
        f"Final multiple         : "
        f"{performance['Final Multiple']:.2f}x"
    )

    log(
        f"CAGR                   : "
        f"{pct(performance['CAGR'])}"
    )

    log(
        f"Maximum drawdown       : "
        f"{pct(performance['Max Drawdown'])}"
    )

    log(
        f"Annualized volatility  : "
        f"{pct(performance['Annualized Volatility'])}"
    )

    log(
        f"Sharpe                 : "
        f"{performance['Sharpe']:.2f}"
    )

    log(
        f"Positive months        : "
        f"{pct(performance['Positive Months'])}"
    )

    log(
        f"Months                 : "
        f"{performance['Months']}"
    )

    log(
        f"Rolling 3Y CAGR median : "
        f"{pct(performance['Rolling 3Y CAGR Median'])}"
    )

    log(
        f"Rolling 3Y CAGR min    : "
        f"{pct(performance['Rolling 3Y CAGR Minimum'])}"
    )

    log(
        f"Rolling 3Y CAGR >=27%  : "
        f"{pct(performance['Rolling 3Y CAGR >= 27%'])}"
    )

    log(
        f"Rolling 5Y CAGR median : "
        f"{pct(performance['Rolling 5Y CAGR Median'])}"
    )

    log(
        f"Rolling 5Y CAGR min    : "
        f"{pct(performance['Rolling 5Y CAGR Minimum'])}"
    )

    log(
        f"Rolling 5Y CAGR >=27%  : "
        f"{pct(performance['Rolling 5Y CAGR >= 27%'])}"
    )


# =============================================================================
# PRINT ROBUSTNESS
# =============================================================================

def print_robustness_results(
    top_n_robustness: pd.DataFrame,
    cost_robustness: pd.DataFrame,
) -> None:

    def pct(value):

        if pd.isna(value):
            return "N/A"

        return (
            f"{value * 100:.2f}%"
        )

    log()
    log("=" * 100)
    log("TOP N ROBUSTNESS")
    log("=" * 100)

    for _, row in (
        top_n_robustness
        .iterrows()
    ):

        log(
            f"Top {int(row['Top N']):>2} "
            f"| CAGR={pct(row['CAGR']):>8} "
            f"| MaxDD={pct(row['Max Drawdown']):>8} "
            f"| Sharpe={row['Sharpe']:.2f} "
            f"| 3Y>=27={pct(row['Rolling 3Y >=27%'])}"
        )

    log()
    log("=" * 100)
    log("TRANSACTION-COST ROBUSTNESS")
    log("=" * 100)

    for _, row in (
        cost_robustness
        .iterrows()
    ):

        log(
            f"Cost={row['Total Cost (bps)']:>5.0f} bps "
            f"| CAGR={pct(row['CAGR']):>8} "
            f"| MaxDD={pct(row['Max Drawdown']):>8} "
            f"| Sharpe={row['Sharpe']:.2f}"
        )


# =============================================================================
# PRINT LATEST SIGNAL
# =============================================================================

def print_latest_signal(
    latest_signal: pd.DataFrame,
) -> None:

    log()
    log("=" * 100)
    log("LATEST PORTFOLIO SIGNAL — TOP 20")
    log("=" * 100)

    if latest_signal.empty:

        log(
            "No latest signal available."
        )

        return

    for _, row in (
        latest_signal
        .iterrows()
    ):

        log(
            f"{int(row['rank']):>2}. "
            f"{str(row['symbol']):<20} "
            f"Score={row['score']:>8.3f} "
            f"Price={row['price']:>10.2f}"
        )


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:

    overall_start = time.time()

    log()
    log("=" * 100)
    log(
        "       MomentumPortfolioLab — OHLCV MONTHLY MOMENTUM BACKTEST"
    )
    log("=" * 100)

    log()

    log(
        f"Project directory : {PROJECT_DIR}"
    )

    log(
        f"Top N             : {TOP_N}"
    )

    log(
        f"Initial capital   : Rs.{INITIAL_CAPITAL:,.0f}"
    )

    log(
        f"Transaction cost  : {TRANSACTION_COST_BPS:.1f} bps"
    )

    log(
        f"Slippage          : {SLIPPAGE_BPS:.1f} bps"
    )

    log(
        f"Total cost        : {TOTAL_COST_BPS:.1f} bps"
    )

    log(
        f"Market regime     : {USE_MARKET_REGIME_FILTER}"
    )

    # =========================================================================
    # STEP 1
    # =========================================================================

    run_trade_data()

    # =========================================================================
    # STEP 2
    # =========================================================================

    symbols = (
        load_universe()
    )

    # =========================================================================
    # STEP 3
    # =========================================================================

    close = (
        download_ohlcv(
            symbols
        )
    )

    # =========================================================================
    # STEP 4
    # =========================================================================

    log()
    log("=" * 100)
    log("STEP 4 — PREPARING MONTHLY DATA")
    log("=" * 100)

    monthly_prices = (
        get_month_end_prices(
            close
        )
    )

    monthly_volatility = (
        calculate_monthly_volatility(
            close
        )
    )

    common_dates = (
        monthly_prices
        .index
        .intersection(
            monthly_volatility.index
        )
    )

    monthly_prices = (
        monthly_prices
        .loc[
            common_dates
        ]
    )

    monthly_volatility = (
        monthly_volatility
        .loc[
            common_dates
        ]
    )

    log(
        f"Monthly observations : "
        f"{len(monthly_prices)}"
    )

    if not monthly_prices.empty:

        log(
            f"Monthly range        : "
            f"{monthly_prices.index.min().date()} "
            f"→ "
            f"{monthly_prices.index.max().date()}"
        )

    # =========================================================================
    # STEP 5
    # =========================================================================

    log()
    log("=" * 100)
    log("STEP 5 — CALCULATING MOMENTUM SCORES")
    log("=" * 100)

    (
        momentum_12_1,
        momentum_6m,
        scores,
    ) = calculate_momentum_scores(
        monthly_prices,
        monthly_volatility,
    )

    # =========================================================================
    # RESEARCH PERIOD
    # =========================================================================

    start_timestamp = pd.Timestamp(
        START_DATE
    )

    scores = (
        scores
        .loc[
            scores.index >= start_timestamp
        ]
    )

    monthly_prices = (
        monthly_prices
        .loc[
            monthly_prices.index >= start_timestamp
        ]
    )

    monthly_volatility = (
        monthly_volatility
        .loc[
            monthly_volatility.index >= start_timestamp
        ]
    )

    # =========================================================================
    # STEP 6
    # BASELINE BACKTEST
    # =========================================================================

    log()
    log("=" * 100)
    log("STEP 6 — BASELINE MONTHLY WALK-FORWARD BACKTEST")
    log("=" * 100)

    (
        portfolio_df,
        monthly_df,
    ) = run_backtest_engine(
        monthly_prices,
        scores,
        top_n=TOP_N,
        total_cost_bps=TOTAL_COST_BPS,
    )

    performance = (
        calculate_performance(
            monthly_df
        )
    )

    # =========================================================================
    # ANNUAL RETURNS
    # =========================================================================

    annual_df = (
        calculate_annual_returns(
            monthly_df
        )
    )

    # =========================================================================
    # PORTFOLIO HISTORY
    # =========================================================================

    portfolio_history = (
        expand_portfolio_history(
            portfolio_df
        )
    )

    # =========================================================================
    # LATEST SIGNAL
    # =========================================================================

    latest_signal = (
        generate_latest_signal(
            monthly_prices,
            scores,
            TOP_N,
        )
    )

    # =========================================================================
    # ROBUSTNESS TEST 1
    # TOP N
    # =========================================================================

    log()
    log("=" * 100)
    log("STEP 7 — TOP N ROBUSTNESS")
    log("=" * 100)

    top_n_robustness = (
        run_top_n_robustness(
            monthly_prices,
            scores,
        )
    )

    # =========================================================================
    # ROBUSTNESS TEST 2
    # TRANSACTION COST
    # =========================================================================

    log()
    log("=" * 100)
    log("STEP 8 — TRANSACTION COST ROBUSTNESS")
    log("=" * 100)

    cost_robustness = (
        run_cost_robustness(
            monthly_prices,
            scores,
        )
    )

    # =========================================================================
    # OOS
    # =========================================================================

    (
        oos_portfolio_df,
        oos_monthly_df,
        oos_performance,
    ) = run_oos_test(
        monthly_prices,
        scores,
    )

    # =========================================================================
    # SAVE
    # =========================================================================

    save_results(
        portfolio_df=portfolio_df,
        monthly_df=monthly_df,
        performance=performance,
        annual_df=annual_df,
        portfolio_history=portfolio_history,
        latest_signal=latest_signal,
        top_n_robustness=top_n_robustness,
        cost_robustness=cost_robustness,
        oos_portfolio_df=oos_portfolio_df,
        oos_monthly_df=oos_monthly_df,
        oos_performance=oos_performance,
    )

    # =========================================================================
    # PRINT BASELINE
    # =========================================================================

    print_performance_block(
        "BASELINE BACKTEST RESULT",
        performance,
    )

    # =========================================================================
    # PRINT OOS
    # =========================================================================

    print_performance_block(
        "OUT-OF-SAMPLE RESULT",
        oos_performance,
    )

    # =========================================================================
    # PRINT ROBUSTNESS
    # =========================================================================

    print_robustness_results(
        top_n_robustness,
        cost_robustness,
    )

    # =========================================================================
    # LATEST SIGNAL
    # =========================================================================

    print_latest_signal(
        latest_signal
    )

    # =========================================================================
    # LIMITATIONS
    # =========================================================================

    log()
    log("=" * 100)
    log("IMPORTANT RESEARCH LIMITATIONS")
    log("=" * 100)

    log(
        "1. The backtest uses the CURRENT Nifty 500 constituent list."
    )

    log(
        "2. Historical results therefore contain survivorship bias."
    )

    log(
        "3. yfinance availability varies by stock and listing history."
    )

    log(
        "4. Historical CAGR is not a guarantee of future CAGR."
    )

    log(
        "5. The OOS test is still subject to current-universe survivorship bias."
    )

    log(
        "6. The strategy is monthly rebalanced; weekly execution will be handled separately."
    )

    log(
        "7. No fundamentals are used."
    )

    log(
        "8. No market-regime filter is used in the baseline."
    )

    # =========================================================================
    # FINAL RUNTIME
    # =========================================================================

    elapsed = (
        time.time()
        -
        overall_start
    )

    log()
    log("=" * 100)

    log(
        f"TOTAL RUNTIME : {elapsed:.1f} seconds"
    )

    log("=" * 100)


# =============================================================================
# PROGRAM ENTRY
# =============================================================================

if __name__ == "__main__":
    main()