"""
MonthlyMomentumLab
==================

Production Monthly Momentum + Breakout Signal Engine

LOCKED RESEARCH STRATEGY
------------------------
COMB_M9S0_B6_V1.5_T0_R0_N10_RB1

Meaning:
    COMB = Momentum + Breakout
    M9   = 9-month momentum
    S0   = No skip month
    B6   = 6-month breakout
    V1.5 = Current monthly volume >= 1.5x prior 3-month average
    T0   = No trend filter
    R0   = No market regime filter
    N10  = Top 10 portfolio
    RB1  = Monthly rebalance

LIVE ELIGIBILITY RULE
---------------------
A stock is eligible for ranking only when:

    Momentum_9M >= 0
    AND
    Breakout_6M >= 0
    AND
    Volume_Ratio >= 1.50

Therefore:

    Negative 9M momentum  -> EXCLUDED
    Negative 6M breakout  -> EXCLUDED
    Negative momentum AND breakout -> EXCLUDED

PRODUCTION WORKFLOW
-------------------
1. Refresh current Nifty 500 universe.
2. Load Nifty 500 symbols.
3. Download 5 years of daily OHLCV data.
4. Convert daily data to completed monthly bars.
5. Calculate:
       - 9M momentum
       - 6M breakout
       - volume ratio
6. Apply hard eligibility filters.
7. Rank eligible stocks.
8. Display Top 30 research candidates.
9. Select Top 10 portfolio candidates.
10. Generate BUY / HOLD / SELL instructions.
11. Generate CSV reports.
12. Generate Excel report.
13. Calculate diagnostic market regime.
14. Bear overlay remains OFF by default.

SIGNAL TIMING
-------------
The signal is generated using the latest COMPLETED monthly candle.

Intended execution:
    Following trading session.

IMPORTANT
---------
The non-negative Momentum/Breakout rules are additional live
eligibility constraints. They must be independently backtested
before being considered statistically validated.

This is a research and decision-support system.
It does not guarantee future returns.
"""

# ============================================================
# IMPORTS
# ============================================================

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


# ============================================================
# PROJECT PATHS
# ============================================================

LAB_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = LAB_ROOT.parent.parent

UNIVERSE_FILE = PROJECT_ROOT / "universe.py"

RESULTS_DIR = LAB_ROOT / "results"
CACHE_DIR = LAB_ROOT / "cache"

RESULTS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

CACHE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# PROJECT IMPORT
# ============================================================

if str(LAB_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(LAB_ROOT),
    )


try:
    import trade_data

except ImportError as exc:

    raise ImportError(
        "Could not import trade_data.py. "
        f"Expected it under: {LAB_ROOT}"
    ) from exc


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_NAME = "MONTHLYMOMENTUMLAB"

STRATEGY_NAME = (
    "COMB_M9S0_B6_V1.5_T0_R0_N10_RB1"
)


# ============================================================
# CORE STRATEGY PARAMETERS
# ============================================================

MOMENTUM_MONTHS = 9

BREAKOUT_MONTHS = 6

VOLUME_MULTIPLIER = 1.50

VOLUME_AVERAGE_MONTHS = 3


# ============================================================
# LIVE HARD FILTERS
# ============================================================

REQUIRE_NON_NEGATIVE_MOMENTUM = True

REQUIRE_NON_NEGATIVE_BREAKOUT = True

REQUIRE_VOLUME_CONFIRMATION = True


# ============================================================
# PORTFOLIO PARAMETERS
# ============================================================

TOP_RESEARCH_STOCKS = 30

TOP_PORTFOLIO_STOCKS = 10

TOTAL_CAPITAL = 100_000.0


# ============================================================
# DATA PARAMETERS
# ============================================================

HISTORICAL_PERIOD = "5y"

MIN_MONTHS_REQUIRED = 15


# ============================================================
# REGIME PARAMETERS
# ============================================================

ENABLE_BEAR_OVERLAY = False


# ============================================================
# OUTPUT FILES
# ============================================================

MONTHLY_CACHE_FILE = (
    CACHE_DIR
    / "monthly_market_cache_production_v1.pkl"
)

CURRENT_SIGNAL_FILE = (
    RESULTS_DIR
    / "current_monthly_signal.csv"
)

TOP30_FILE = (
    RESULTS_DIR
    / "current_monthly_top30.csv"
)

ORDERS_FILE = (
    RESULTS_DIR
    / "current_monthly_orders.csv"
)

RUN_SUMMARY_FILE = (
    RESULTS_DIR
    / "current_monthly_run_summary.csv"
)

HOLDINGS_FILE = (
    RESULTS_DIR
    / "current_holdings.csv"
)

EXCEL_FILE = (
    RESULTS_DIR
    / "monthly_momentum_lab_live_signal.xlsx"
)


# ============================================================
# TIMER
# ============================================================

class Timer:

    def __init__(self):

        self.start = time.perf_counter()

    def elapsed(self) -> float:

        return (
            time.perf_counter()
            - self.start
        )


# ============================================================
# PRINT HELPERS
# ============================================================

def print_header(
    title: str,
) -> None:

    print()

    print(
        "=" * 100
    )

    print(
        title
    )

    print(
        "=" * 100
    )


def print_subheader(
    title: str,
) -> None:

    print()

    print(
        "-" * 100
    )

    print(
        title
    )

    print(
        "-" * 100
    )


# ============================================================
# SAFE HELPERS
# ============================================================

def clean_symbol(
    symbol: str,
) -> str:

    value = (
        str(symbol)
        .strip()
        .upper()
    )

    if not value.endswith(".NS"):

        value = (
            f"{value}.NS"
        )

    return value


def safe_float(
    value,
) -> float:

    try:

        if pd.isna(value):

            return np.nan

        return float(value)

    except (
        TypeError,
        ValueError,
    ):

        return np.nan


# ============================================================
# REFRESH NIFTY 500
# ============================================================

def refresh_universe_if_available() -> None:

    candidate_functions = [
        "refresh_nifty500_universe",
        "update_nifty500_universe",
        "refresh_universe",
        "update_universe",
    ]

    function = None

    for name in candidate_functions:

        candidate = getattr(
            trade_data,
            name,
            None,
        )

        if callable(candidate):

            function = candidate

            break

    if function is None:

        print(
            "Universe refresh function not found."
        )

        return

    print(
        "Updating Nifty 500 universe..."
    )

    function()


# ============================================================
# LOAD UNIVERSE
# ============================================================

def load_universe_symbols() -> list[str]:

    possible_locations = [
        UNIVERSE_FILE,
        PROJECT_ROOT / "src" / "universe.py",
        LAB_ROOT / "universe.py",
    ]

    universe_path = None

    for path in possible_locations:

        if path.exists():

            universe_path = path

            break

    if universe_path is None:

        raise FileNotFoundError(
            "Could not find universe.py."
        )

    spec = (
        importlib.util
        .spec_from_file_location(
            "generated_universe",
            universe_path,
        )
    )

    if (
        spec is None
        or spec.loader is None
    ):

        raise ImportError(
            "Could not load universe.py."
        )

    module = (
        importlib.util
        .module_from_spec(spec)
    )

    spec.loader.exec_module(
        module
    )

    possible_names = [
        "NIFTY_500_SYMBOLS",
        "NIFTY500_SYMBOLS",
        "SYMBOLS",
        "symbols",
        "NIFTY_500",
        "NIFTY500",
    ]

    symbols = None

    for name in possible_names:

        value = getattr(
            module,
            name,
            None,
        )

        if value is not None:

            symbols = value

            break

    if symbols is None:

        raise AttributeError(
            "universe.py does not contain a recognized "
            "Nifty 500 symbol list."
        )

    if not isinstance(
        symbols,
        (
            list,
            tuple,
            set,
        ),
    ):

        raise TypeError(
            "Universe symbols must be a list, tuple or set."
        )

    cleaned = []

    for symbol in symbols:

        value = (
            str(symbol)
            .strip()
            .upper()
        )

        if not value:

            continue

        cleaned.append(
            clean_symbol(value)
        )

    symbols = sorted(
        set(cleaned)
    )

    if len(symbols) < 400:

        raise ValueError(
            f"Only {len(symbols)} symbols found. "
            "Expected a valid Nifty 500 universe."
        )

    return symbols


# ============================================================
# FIND MARKET DATA FUNCTION
# ============================================================

def find_market_data_function():

    candidate_functions = [
        "get_historical_market_data_for_symbols",
        "get_historical_market_data",
        "download_historical_market_data",
        "load_historical_market_data",
    ]

    for name in candidate_functions:

        function = getattr(
            trade_data,
            name,
            None,
        )

        if callable(function):

            return function

    raise AttributeError(
        "Could not find a historical market-data "
        "function in trade_data.py."
    )


# ============================================================
# NORMALIZE MARKET DATA
# ============================================================

def normalize_market_data(
    data: pd.DataFrame,
) -> pd.DataFrame:

    if data is None:

        raise ValueError(
            "Market data is None."
        )

    if not isinstance(
        data,
        pd.DataFrame,
    ):

        raise TypeError(
            "Market data must be a pandas DataFrame."
        )

    if data.empty:

        raise ValueError(
            "Market data is empty."
        )

    result = data.copy()

    # --------------------------------------------------------
    # MultiIndex columns
    # --------------------------------------------------------

    if isinstance(
        result.columns,
        pd.MultiIndex,
    ):

        if result.columns.nlevels != 2:

            raise ValueError(
                "Unsupported MultiIndex market-data structure."
            )

        level_0 = [
            str(x).strip()
            for x in result.columns
            .get_level_values(0)
        ]

        level_1 = [
            str(x).strip()
            for x in result.columns
            .get_level_values(1)
        ]

        price_fields = {
            "Open",
            "High",
            "Low",
            "Close",
            "Adj Close",
            "Volume",
        }

        level_0_price_count = sum(
            x in price_fields
            for x in level_0
        )

        level_1_price_count = sum(
            x in price_fields
            for x in level_1
        )

        if (
            level_0_price_count
            >=
            level_1_price_count
        ):

            result.columns = (
                pd.MultiIndex.from_arrays(
                    [
                        level_0,
                        level_1,
                    ]
                )
            )

        else:

            result.columns = (
                pd.MultiIndex.from_arrays(
                    [
                        level_1,
                        level_0,
                    ]
                )
            )

        return result

    # --------------------------------------------------------
    # Flat columns
    # --------------------------------------------------------

    result.columns = [
        str(column).strip()
        for column in result.columns
    ]

    return result


# ============================================================
# LOAD DAILY MARKET DATA
# ============================================================

def load_daily_market_data(
    symbols: list[str],
) -> tuple[pd.DataFrame, list[str]]:

    function = (
        find_market_data_function()
    )

    print()

    print(
        "Loading 5-year daily market data "
        "through trade_data.py..."
    )

    timer = Timer()

    raw_result = function(
        symbols,
        period=HISTORICAL_PERIOD,
    )

    valid_symbols = symbols.copy()

    # --------------------------------------------------------
    # Normal expected return:
    #
    #     data, valid_symbols
    # --------------------------------------------------------

    if isinstance(
        raw_result,
        tuple,
    ):

        if len(raw_result) < 1:

            raise ValueError(
                "trade_data.py returned an empty tuple."
            )

        raw_data = raw_result[0]

        if (
            len(raw_result) >= 2
            and raw_result[1] is not None
        ):

            valid_symbols = [
                clean_symbol(symbol)
                for symbol in raw_result[1]
            ]

    elif isinstance(
        raw_result,
        pd.DataFrame,
    ):

        raw_data = raw_result

    else:

        raise TypeError(
            "Unsupported market-data object returned by "
            f"trade_data.py: {type(raw_result)}"
        )

    data = normalize_market_data(
        raw_data
    )

    print(
        f"Daily data loaded in "
        f"{timer.elapsed():.2f}s"
    )

    print(
        f"Daily shape: {data.shape}"
    )

    return (
        data,
        valid_symbols,
    )


# ============================================================
# FIELD EXTRACTION
# ============================================================

def get_field(
    data: pd.DataFrame,
    field: str,
) -> pd.DataFrame:

    # --------------------------------------------------------
    # MultiIndex
    # --------------------------------------------------------

    if isinstance(
        data.columns,
        pd.MultiIndex,
    ):

        fields_level_0 = [
            str(x).strip()
            for x in data.columns
            .get_level_values(0)
        ]

        fields_level_1 = [
            str(x).strip()
            for x in data.columns
            .get_level_values(1)
        ]

        if field in fields_level_0:

            selected = data.xs(
                field,
                axis=1,
                level=0,
            )

        elif field in fields_level_1:

            selected = data.xs(
                field,
                axis=1,
                level=1,
            )

        else:

            raise KeyError(
                f"Field '{field}' not found."
            )

        selected = selected.copy()

        selected.columns = [
            clean_symbol(column)
            for column in selected.columns
        ]

        return selected

    # --------------------------------------------------------
    # Flat columns
    # --------------------------------------------------------

    columns = [
        str(column)
        for column in data.columns
    ]

    if field in columns:

        return data[
            [field]
        ].copy()

    suffix = (
        f"_{field}"
    )

    matching = [
        column
        for column in columns
        if column.endswith(
            suffix
        )
    ]

    if matching:

        result = data[
            matching
        ].copy()

        result.columns = [
            clean_symbol(
                column[
                    :-len(suffix)
                ]
            )
            for column in matching
        ]

        return result

    raise KeyError(
        f"Could not extract field '{field}'."
    )


# ============================================================
# DAILY TO COMPLETED MONTHLY
# ============================================================

def convert_daily_to_completed_monthly(
    data: pd.DataFrame,
) -> pd.DataFrame:

    timer = Timer()

    print()

    print(
        "Converting daily OHLCV to completed monthly data..."
    )

    if not isinstance(
        data.index,
        pd.DatetimeIndex,
    ):

        data.index = pd.to_datetime(
            data.index
        )

    data = data.sort_index()

    # --------------------------------------------------------
    # Extract fields
    # --------------------------------------------------------

    close_df = get_field(
        data,
        "Close",
    )

    high_df = get_field(
        data,
        "High",
    )

    low_df = get_field(
        data,
        "Low",
    )

    volume_df = get_field(
        data,
        "Volume",
    )

    # --------------------------------------------------------
    # Exclude current incomplete month
    # --------------------------------------------------------

    today = (
        pd.Timestamp.now()
        .normalize()
    )

    current_month_start = (
        today.replace(
            day=1
        )
    )

    close_completed = (
        close_df.loc[
            close_df.index
            < current_month_start
        ]
    )

    high_completed = (
        high_df.loc[
            high_df.index
            < current_month_start
        ]
    )

    low_completed = (
        low_df.loc[
            low_df.index
            < current_month_start
        ]
    )

    volume_completed = (
        volume_df.loc[
            volume_df.index
            < current_month_start
        ]
    )

    if close_completed.empty:

        raise ValueError(
            "No completed monthly data available."
        )

    # --------------------------------------------------------
    # Resample
    # --------------------------------------------------------

    close_monthly = (
        close_completed
        .resample("ME")
        .last()
    )

    high_monthly = (
        high_completed
        .resample("ME")
        .max()
    )

    low_monthly = (
        low_completed
        .resample("ME")
        .min()
    )

    volume_monthly = (
        volume_completed
        .resample("ME")
        .sum()
    )

    # --------------------------------------------------------
    # Symbols common to all OHLCV fields
    # --------------------------------------------------------

    symbols = sorted(
        set(close_monthly.columns)
        &
        set(high_monthly.columns)
        &
        set(low_monthly.columns)
        &
        set(volume_monthly.columns)
    )

    if not symbols:

        raise ValueError(
            "No symbols have complete monthly OHLCV data."
        )

    # --------------------------------------------------------
    # Build long format
    # --------------------------------------------------------

    records = []

    for symbol in symbols:

        temp = pd.DataFrame(
            {
                "Date": close_monthly.index,
                "Symbol": symbol,
                "Close": close_monthly[
                    symbol
                ].values,
                "High": high_monthly[
                    symbol
                ].values,
                "Low": low_monthly[
                    symbol
                ].values,
                "Volume": volume_monthly[
                    symbol
                ].values,
            }
        )

        temp = temp.dropna(
            subset=[
                "Close",
            ]
        )

        if temp.empty:

            continue

        records.append(
            temp
        )

    if not records:

        raise ValueError(
            "No usable monthly records were created."
        )

    monthly = pd.concat(
        records,
        ignore_index=True,
    )

    monthly["Date"] = pd.to_datetime(
        monthly["Date"]
    )

    monthly["Symbol"] = (
        monthly["Symbol"]
        .astype(str)
        .map(clean_symbol)
    )

    # --------------------------------------------------------
    # Numeric conversion
    # --------------------------------------------------------

    for column in [
        "Close",
        "High",
        "Low",
        "Volume",
    ]:

        monthly[column] = pd.to_numeric(
            monthly[column],
            errors="coerce",
        )

    # --------------------------------------------------------
    # Valid price rows
    # --------------------------------------------------------

    monthly = monthly[
        monthly["Close"] > 0
    ].copy()

    monthly = monthly.sort_values(
        [
            "Symbol",
            "Date",
        ]
    ).reset_index(
        drop=True
    )

    unique_symbols = (
        monthly["Symbol"]
        .nunique()
    )

    unique_months = (
        monthly["Date"]
        .nunique()
    )

    print(
        f"Monthly conversion completed in "
        f"{timer.elapsed():.2f}s"
    )

    print(
        f"Symbols : {unique_symbols:,}"
    )

    print(
        f"Months  : {unique_months:,}"
    )

    if not monthly.empty:

        print(
            f"Range   : "
            f"{monthly['Date'].min().date()} -> "
            f"{monthly['Date'].max().date()}"
        )

    return monthly


# ============================================================
# SAVE MONTHLY CACHE
# ============================================================

def save_monthly_cache(
    monthly: pd.DataFrame,
) -> None:

    try:

        monthly.to_pickle(
            MONTHLY_CACHE_FILE
        )

        print()

        print(
            "Monthly market cache saved:"
        )

        print(
            MONTHLY_CACHE_FILE
        )

    except Exception as exc:

        print()

        print(
            "WARNING: Could not save monthly cache:"
        )

        print(
            exc
        )


# ============================================================
# LOAD MONTHLY CACHE
# ============================================================

def load_monthly_cache() -> Optional[pd.DataFrame]:

    if not MONTHLY_CACHE_FILE.exists():

        return None

    try:

        data = pd.read_pickle(
            MONTHLY_CACHE_FILE
        )

        if (
            isinstance(data, pd.DataFrame)
            and not data.empty
        ):

            return data

    except Exception:

        return None

    return None


# ============================================================
# FEATURE ENGINE
# ============================================================

def calculate_monthly_features(
    monthly: pd.DataFrame,
) -> pd.DataFrame:

    timer = Timer()

    print()

    print_subheader(
        "FEATURE ENGINE"
    )

    data = monthly.copy()

    data = data.sort_values(
        [
            "Symbol",
            "Date",
        ]
    ).reset_index(
        drop=True
    )

    grouped_close = (
        data
        .groupby(
            "Symbol"
        )["Close"]
    )

    grouped_high = (
        data
        .groupby(
            "Symbol"
        )["High"]
    )

    grouped_volume = (
        data
        .groupby(
            "Symbol"
        )["Volume"]
    )

    # ========================================================
    # 9-MONTH MOMENTUM
    # ========================================================

    data["Momentum_9M"] = (
        grouped_close
        .transform(
            lambda x:
            x
            / x.shift(
                MOMENTUM_MONTHS
            )
            - 1.0
        )
    )

    # ========================================================
    # 6-MONTH BREAKOUT
    # ========================================================
    #
    # Current close versus highest high of the previous
    # six completed monthly bars.
    #
    # shift(1) prevents current-month leakage.
    # ========================================================

    prior_high = (
        grouped_high
        .transform(
            lambda x:
            x.shift(1)
            .rolling(
                BREAKOUT_MONTHS,
                min_periods=BREAKOUT_MONTHS,
            )
            .max()
        )
    )

    data["Breakout_6M"] = (
        data["Close"]
        / prior_high
        - 1.0
    )

    # ========================================================
    # PRIOR 3-MONTH AVERAGE VOLUME
    # ========================================================

    prior_volume_average = (
        grouped_volume
        .transform(
            lambda x:
            x.shift(1)
            .rolling(
                VOLUME_AVERAGE_MONTHS,
                min_periods=VOLUME_AVERAGE_MONTHS,
            )
            .mean()
        )
    )

    # ========================================================
    # VOLUME RATIO
    # ========================================================

    data["Volume_Ratio"] = np.where(
        prior_volume_average > 0,
        data["Volume"]
        / prior_volume_average,
        np.nan,
    )

    # ========================================================
    # VOLUME PASS
    # ========================================================

    data["Volume_Pass"] = (
        data["Volume_Ratio"]
        >= VOLUME_MULTIPLIER
    )

    # ========================================================
    # COMBINED SCORE
    # ========================================================

    data["Combined_Score"] = (
        data["Momentum_9M"]
        + data["Breakout_6M"]
    )

    print(
        f"Features built in "
        f"{timer.elapsed():.2f}s"
    )

    return data


# ============================================================
# CURRENT SIGNAL
# ============================================================

def generate_current_signal(
    features: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.Timestamp,
]:

    timer = Timer()

    print()

    print_subheader(
        "CURRENT SIGNAL GENERATION"
    )

    if features.empty:

        raise ValueError(
            "Feature dataframe is empty."
        )

    latest_date = (
        features["Date"]
        .max()
    )

    latest = features[
        features["Date"]
        == latest_date
    ].copy()

    if latest.empty:

        raise ValueError(
            "No rows found for latest completed month."
        )

    # --------------------------------------------------------
    # Convert numeric columns
    # --------------------------------------------------------

    required_columns = [
        "Close",
        "Momentum_9M",
        "Breakout_6M",
        "Volume_Ratio",
    ]

    for column in required_columns:

        latest[column] = pd.to_numeric(
            latest[column],
            errors="coerce",
        )

    # --------------------------------------------------------
    # Base validity
    # --------------------------------------------------------

    eligible = latest[
        latest["Close"].notna()
        &
        latest["Momentum_9M"].notna()
        &
        latest["Breakout_6M"].notna()
        &
        latest["Volume_Ratio"].notna()
    ].copy()

    initial_count = len(
        eligible
    )

    # ========================================================
    # FILTER 1
    #
    # Momentum_9M >= 0
    # ========================================================

    if REQUIRE_NON_NEGATIVE_MOMENTUM:

        eligible = eligible[
            eligible["Momentum_9M"]
            >= 0.0
        ].copy()

    momentum_filter_count = len(
        eligible
    )

    # ========================================================
    # FILTER 2
    #
    # Breakout_6M >= 0
    # ========================================================

    if REQUIRE_NON_NEGATIVE_BREAKOUT:

        eligible = eligible[
            eligible["Breakout_6M"]
            >= 0.0
        ].copy()

    breakout_filter_count = len(
        eligible
    )

    # ========================================================
    # FILTER 3
    #
    # Volume_Ratio >= 1.50
    # ========================================================

    if REQUIRE_VOLUME_CONFIRMATION:

        eligible = eligible[
            eligible["Volume_Ratio"]
            >= VOLUME_MULTIPLIER
        ].copy()

    final_eligible_count = len(
        eligible
    )

    # ========================================================
    # RANKING
    # ========================================================

    if not eligible.empty:

        eligible = eligible.sort_values(
            by=[
                "Combined_Score",
                "Momentum_9M",
                "Breakout_6M",
                "Volume_Ratio",
            ],
            ascending=[
                False,
                False,
                False,
                False,
            ],
        ).reset_index(
            drop=True
        )

        eligible.insert(
            0,
            "Research_Rank",
            np.arange(
                1,
                len(eligible) + 1,
            ),
        )

    else:

        eligible["Research_Rank"] = (
            pd.Series(
                dtype="int64"
            )
        )

    # ========================================================
    # TOP 30
    # ========================================================

    top30 = eligible.head(
        TOP_RESEARCH_STOCKS
    ).copy()

    # ========================================================
    # TOP 10
    # ========================================================

    top10 = eligible.head(
        TOP_PORTFOLIO_STOCKS
    ).copy()

    # ========================================================
    # CAPITAL ALLOCATION
    # ========================================================
    #
    # N10 means each position gets 10% of capital.
    #
    # ₹100,000 / 10 = ₹10,000.
    #
    # If fewer than 10 stocks qualify, the unused capital
    # remains CASH.
    # ========================================================

    if not top10.empty:

        top10["Target_Weight"] = (
            1.0
            / TOP_PORTFOLIO_STOCKS
        )

        top10["Target_Capital"] = (
            TOTAL_CAPITAL
            / TOP_PORTFOLIO_STOCKS
        )

    else:

        top10["Target_Weight"] = (
            pd.Series(
                dtype="float64"
            )
        )

        top10["Target_Capital"] = (
            pd.Series(
                dtype="float64"
            )
        )

    # --------------------------------------------------------
    # Signal
    # --------------------------------------------------------

    top10["Signal"] = "BUY"

    # --------------------------------------------------------
    # Status columns
    # --------------------------------------------------------

    top30["Eligibility_Status"] = (
        "QUALIFIED"
    )

    top10["Portfolio_Status"] = (
        "PORTFOLIO"
    )

    # ========================================================
    # SAFETY CHECK
    # ========================================================
    #
    # Nothing with negative Momentum_9M or Breakout_6M can
    # appear in Top 30 or Top 10.
    # ========================================================

    if not top30.empty:

        if (
            top30["Momentum_9M"]
            < 0
        ).any():

            raise RuntimeError(
                "SAFETY CHECK FAILED: "
                "Negative Momentum_9M found in Top 30."
            )

        if (
            top30["Breakout_6M"]
            < 0
        ).any():

            raise RuntimeError(
                "SAFETY CHECK FAILED: "
                "Negative Breakout_6M found in Top 30."
            )

    if not top10.empty:

        if (
            top10["Momentum_9M"]
            < 0
        ).any():

            raise RuntimeError(
                "SAFETY CHECK FAILED: "
                "Negative Momentum_9M found in Top 10."
            )

        if (
            top10["Breakout_6M"]
            < 0
        ).any():

            raise RuntimeError(
                "SAFETY CHECK FAILED: "
                "Negative Breakout_6M found in Top 10."
            )

    # ========================================================
    # DISPLAY FILTER COUNTS
    # ========================================================

    print(
        f"Latest completed month : "
        f"{latest_date.date()}"
    )

    print(
        f"Initial valid candidates : "
        f"{initial_count:,}"
    )

    print(
        f"After Momentum >= 0       : "
        f"{momentum_filter_count:,}"
    )

    print(
        f"After Breakout >= 0       : "
        f"{breakout_filter_count:,}"
    )

    print(
        f"After Volume >= "
        f"{VOLUME_MULTIPLIER:.2f}x : "
        f"{final_eligible_count:,}"
    )

    print(
        f"Top 30 research stocks    : "
        f"{len(top30):,}"
    )

    print(
        f"Top 10 portfolio stocks   : "
        f"{len(top10):,}"
    )

    print(
        f"Signal generation completed in "
        f"{timer.elapsed():.2f}s"
    )

    return (
        eligible,
        top30,
        top10,
        latest_date,
    )


# ============================================================
# REGIME MONITOR
# ============================================================

def calculate_regime_monitor(
    monthly: pd.DataFrame,
) -> dict:

    if monthly.empty:

        return {
            "Regime": "UNKNOWN",
            "Market_Proxy": np.nan,
            "Market_10M_MA": np.nan,
            "Previous_10M_MA": np.nan,
        }

    pivot = monthly.pivot_table(
        index="Date",
        columns="Symbol",
        values="Close",
        aggfunc="last",
    )

    market_proxy = (
        pivot
        .median(
            axis=1,
            skipna=True,
        )
        .dropna()
    )

    if len(market_proxy) < 11:

        return {
            "Regime": "UNKNOWN",
            "Market_Proxy": (
                market_proxy.iloc[-1]
                if len(market_proxy)
                else np.nan
            ),
            "Market_10M_MA": np.nan,
            "Previous_10M_MA": np.nan,
        }

    ma10 = (
        market_proxy
        .rolling(
            10,
            min_periods=10,
        )
        .mean()
    )

    current_proxy = (
        market_proxy.iloc[-1]
    )

    current_ma = (
        ma10.iloc[-1]
    )

    previous_ma = (
        ma10.iloc[-2]
    )

    if pd.isna(current_ma):

        regime = "UNKNOWN"

    elif (
        current_proxy > current_ma
        and current_ma > previous_ma
    ):

        regime = "GREEN"

    elif (
        current_proxy < current_ma
        and current_ma < previous_ma
    ):

        regime = "RED"

    else:

        regime = "YELLOW"

    return {
        "Regime": regime,
        "Market_Proxy": current_proxy,
        "Market_10M_MA": current_ma,
        "Previous_10M_MA": previous_ma,
    }


# ============================================================
# CURRENT HOLDINGS
# ============================================================

def load_current_holdings() -> set[str]:

    if not HOLDINGS_FILE.exists():

        print()

        print(
            "No current holdings file found."
        )

        return set()

    try:

        holdings = pd.read_csv(
            HOLDINGS_FILE
        )

    except Exception as exc:

        print()

        print(
            "WARNING: Could not read current holdings:"
        )

        print(
            exc
        )

        return set()

    symbol_column = None

    for column in [
        "Symbol",
        "symbol",
        "Ticker",
        "ticker",
    ]:

        if column in holdings.columns:

            symbol_column = column

            break

    if symbol_column is None:

        print(
            "WARNING: Holdings file does not contain "
            "Symbol/Ticker column."
        )

        return set()

    symbols = set()

    for symbol in holdings[
        symbol_column
    ].dropna():

        symbols.add(
            clean_symbol(symbol)
        )

    return symbols


# ============================================================
# ORDER GENERATION
# ============================================================

def generate_orders(
    top10: pd.DataFrame,
    current_holdings: set[str],
) -> pd.DataFrame:

    if top10.empty:

        target_symbols = set()

    else:

        target_symbols = set(
            top10["Symbol"]
            .map(clean_symbol)
        )

    orders = []

    # ========================================================
    # SELL ORDERS
    # ========================================================

    for symbol in sorted(
        current_holdings
        - target_symbols
    ):

        orders.append(
            {
                "Symbol": symbol,
                "Action": "SELL",
                "Reason": (
                    "No longer in current Top 10"
                ),
                "Target_Weight": 0.0,
                "Target_Capital": 0.0,
                "Momentum_9M": np.nan,
                "Breakout_6M": np.nan,
                "Volume_Ratio": np.nan,
                "Combined_Score": np.nan,
            }
        )

    # ========================================================
    # BUY / HOLD ORDERS
    # ========================================================

    for _, row in top10.iterrows():

        symbol = clean_symbol(
            row["Symbol"]
        )

        if symbol in current_holdings:

            action = "HOLD"

            reason = (
                "Still in current Top 10"
            )

        else:

            action = "BUY"

            reason = (
                "New Top 10 entrant"
            )

        orders.append(
            {
                "Symbol": symbol,
                "Action": action,
                "Reason": reason,
                "Target_Weight": safe_float(
                    row["Target_Weight"]
                ),
                "Target_Capital": safe_float(
                    row["Target_Capital"]
                ),
                "Momentum_9M": safe_float(
                    row["Momentum_9M"]
                ),
                "Breakout_6M": safe_float(
                    row["Breakout_6M"]
                ),
                "Volume_Ratio": safe_float(
                    row["Volume_Ratio"]
                ),
                "Combined_Score": safe_float(
                    row["Combined_Score"]
                ),
            }
        )

    # ========================================================
    # EMPTY ORDERS
    # ========================================================

    if not orders:

        return pd.DataFrame(
            columns=[
                "Symbol",
                "Action",
                "Reason",
                "Target_Weight",
                "Target_Capital",
                "Momentum_9M",
                "Breakout_6M",
                "Volume_Ratio",
                "Combined_Score",
            ]
        )

    result = pd.DataFrame(
        orders
    )

    # ========================================================
    # ORDER SORTING
    # ========================================================

    action_order = {
        "SELL": 1,
        "BUY": 2,
        "HOLD": 3,
    }

    result["_ActionOrder"] = (
        result["Action"]
        .map(action_order)
        .fillna(99)
    )

    result = result.sort_values(
        [
            "_ActionOrder",
            "Combined_Score",
        ],
        ascending=[
            True,
            False,
        ],
    )

    result = result.drop(
        columns=[
            "_ActionOrder",
        ]
    )

    result = result.reset_index(
        drop=True
    )

    return result


# ============================================================
# SAVE CSV REPORTS
# ============================================================

def save_csv_reports(
    ranked: pd.DataFrame,
    top30: pd.DataFrame,
    top10: pd.DataFrame,
    orders: pd.DataFrame,
    universe_count: int,
    valid_daily_symbols: int,
    usable_monthly_symbols: int,
    completed_months: int,
    latest_date: pd.Timestamp,
    regime_info: dict,
    runtime_seconds: float,
) -> None:

    # --------------------------------------------------------
    # Full qualified signal
    # --------------------------------------------------------

    ranked.to_csv(
        CURRENT_SIGNAL_FILE,
        index=False,
    )

    # --------------------------------------------------------
    # Top 30
    # --------------------------------------------------------

    top30.to_csv(
        TOP30_FILE,
        index=False,
    )

    # --------------------------------------------------------
    # Orders
    # --------------------------------------------------------

    orders.to_csv(
        ORDERS_FILE,
        index=False,
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    eligible_count = len(
        ranked
    )

    portfolio_count = len(
        top10
    )

    capital_allocated = (
        portfolio_count
        * (
            TOTAL_CAPITAL
            / TOP_PORTFOLIO_STOCKS
        )
    )

    cash_remaining = (
        TOTAL_CAPITAL
        - capital_allocated
    )

    summary = pd.DataFrame(
        [
            {
                "Run_Timestamp": pd.Timestamp.now(),
                "Signal_Month": latest_date,
                "Strategy": STRATEGY_NAME,
                "Universe": universe_count,
                "Valid_Daily_Symbols": valid_daily_symbols,
                "Usable_Monthly_Symbols": usable_monthly_symbols,
                "Completed_Months": completed_months,
                "Eligible_Stocks": eligible_count,
                "Top30_Stocks": min(
                    eligible_count,
                    TOP_RESEARCH_STOCKS,
                ),
                "Portfolio_Stocks": portfolio_count,
                "Capital_Allocated": capital_allocated,
                "Cash_Remaining": cash_remaining,
                "Momentum_Filter": (
                    "Momentum_9M >= 0"
                    if REQUIRE_NON_NEGATIVE_MOMENTUM
                    else "OFF"
                ),
                "Breakout_Filter": (
                    "Breakout_6M >= 0"
                    if REQUIRE_NON_NEGATIVE_BREAKOUT
                    else "OFF"
                ),
                "Volume_Filter": (
                    f"Volume_Ratio >= "
                    f"{VOLUME_MULTIPLIER:.2f}"
                    if REQUIRE_VOLUME_CONFIRMATION
                    else "OFF"
                ),
                "Regime": regime_info[
                    "Regime"
                ],
                "Bear_Overlay_Enabled": (
                    ENABLE_BEAR_OVERLAY
                ),
                "Runtime_Seconds": runtime_seconds,
            }
        ]
    )

    summary.to_csv(
        RUN_SUMMARY_FILE,
        index=False,
    )


# ============================================================
# EXCEL REPORT
# ============================================================

def save_excel_report(
    ranked: pd.DataFrame,
    top30: pd.DataFrame,
    top10: pd.DataFrame,
    orders: pd.DataFrame,
    universe_count: int,
    valid_daily_symbols: int,
    usable_monthly_symbols: int,
    completed_months: int,
    latest_date: pd.Timestamp,
    regime_info: dict,
    runtime_seconds: float,
) -> None:

    try:

        with pd.ExcelWriter(
            EXCEL_FILE,
            engine="openpyxl",
        ) as writer:

            # ------------------------------------------------
            # Top 30
            # ------------------------------------------------

            top30.to_excel(
                writer,
                sheet_name="Top 30",
                index=False,
            )

            # ------------------------------------------------
            # Top 10
            # ------------------------------------------------

            top10.to_excel(
                writer,
                sheet_name="Top 10",
                index=False,
            )

            # ------------------------------------------------
            # Orders
            # ------------------------------------------------

            orders.to_excel(
                writer,
                sheet_name="Orders",
                index=False,
            )

            # ------------------------------------------------
            # Full eligible universe
            # ------------------------------------------------

            ranked.to_excel(
                writer,
                sheet_name="Eligible Universe",
                index=False,
            )

            # ------------------------------------------------
            # Run Summary
            # ------------------------------------------------

            capital_allocated = (
                len(top10)
                * (
                    TOTAL_CAPITAL
                    / TOP_PORTFOLIO_STOCKS
                )
            )

            cash_remaining = (
                TOTAL_CAPITAL
                - capital_allocated
            )

            summary = pd.DataFrame(
                [
                    {
                        "Metric": "Strategy",
                        "Value": STRATEGY_NAME,
                    },
                    {
                        "Metric": "Signal Month",
                        "Value": latest_date,
                    },
                    {
                        "Metric": "Universe",
                        "Value": universe_count,
                    },
                    {
                        "Metric": "Valid Daily Symbols",
                        "Value": valid_daily_symbols,
                    },
                    {
                        "Metric": "Usable Monthly Symbols",
                        "Value": usable_monthly_symbols,
                    },
                    {
                        "Metric": "Completed Months",
                        "Value": completed_months,
                    },
                    {
                        "Metric": "Eligible Stocks",
                        "Value": len(ranked),
                    },
                    {
                        "Metric": "Top 30",
                        "Value": len(top30),
                    },
                    {
                        "Metric": "Top 10",
                        "Value": len(top10),
                    },
                    {
                        "Metric": "Capital Allocated",
                        "Value": capital_allocated,
                    },
                    {
                        "Metric": "Cash Remaining",
                        "Value": cash_remaining,
                    },
                    {
                        "Metric": "Momentum Rule",
                        "Value": (
                            "Momentum_9M >= 0"
                            if REQUIRE_NON_NEGATIVE_MOMENTUM
                            else "OFF"
                        ),
                    },
                    {
                        "Metric": "Breakout Rule",
                        "Value": (
                            "Breakout_6M >= 0"
                            if REQUIRE_NON_NEGATIVE_BREAKOUT
                            else "OFF"
                        ),
                    },
                    {
                        "Metric": "Volume Rule",
                        "Value": (
                            f"Volume_Ratio >= "
                            f"{VOLUME_MULTIPLIER:.2f}x"
                            if REQUIRE_VOLUME_CONFIRMATION
                            else "OFF"
                        ),
                    },
                    {
                        "Metric": "Regime",
                        "Value": regime_info[
                            "Regime"
                        ],
                    },
                    {
                        "Metric": "Bear Overlay",
                        "Value": (
                            "ENABLED"
                            if ENABLE_BEAR_OVERLAY
                            else "DISABLED"
                        ),
                    },
                    {
                        "Metric": "Runtime Seconds",
                        "Value": runtime_seconds,
                    },
                ]
            )

            summary.to_excel(
                writer,
                sheet_name="Run Summary",
                index=False,
            )

            # ------------------------------------------------
            # Regime
            # ------------------------------------------------

            regime_df = pd.DataFrame(
                [
                    {
                        "Metric": key,
                        "Value": value,
                    }
                    for key, value
                    in regime_info.items()
                ]
            )

            regime_df.to_excel(
                writer,
                sheet_name="Regime Monitor",
                index=False,
            )

        print()

        print(
            "Excel report saved:"
        )

        print(
            EXCEL_FILE
        )

    except Exception as exc:

        print()

        print(
            "WARNING: Excel report could not be created:"
        )

        print(
            exc
        )


# ============================================================
# DISPLAY SIGNAL
# ============================================================

def display_signal(
    ranked: pd.DataFrame,
    top30: pd.DataFrame,
    top10: pd.DataFrame,
    orders: pd.DataFrame,
    universe_count: int,
    valid_daily_symbols: int,
    usable_monthly_symbols: int,
    completed_months: int,
    latest_date: pd.Timestamp,
    regime_info: dict,
) -> None:

    print()

    print(
        "=" * 100
    )

    print(
        "CURRENT MONTHLY SIGNAL"
    )

    print(
        "=" * 100
    )

    print(
        f"Signal month        : "
        f"{latest_date.date()}"
    )

    print(
        f"Universe            : "
        f"{universe_count:,}"
    )

    print(
        f"Valid daily symbols : "
        f"{valid_daily_symbols:,}"
    )

    print(
        f"Usable monthly      : "
        f"{usable_monthly_symbols:,}"
    )

    print(
        f"Completed months    : "
        f"{completed_months:,}"
    )

    print(
        f"Eligible stocks     : "
        f"{len(ranked):,}"
    )

    print(
        f"Top 30 research     : "
        f"{len(top30):,}"
    )

    print(
        f"Top 10 portfolio    : "
        f"{len(top10):,}"
    )

    # ========================================================
    # HARD FILTERS
    # ========================================================

    print()

    print(
        "HARD ELIGIBILITY FILTERS"
    )

    print(
        "-" * 100
    )

    print(
        "Momentum_9M >= 0     : "
        "ON"
    )

    print(
        "Breakout_6M >= 0     : "
        "ON"
    )

    print(
        f"Volume_Ratio >= "
        f"{VOLUME_MULTIPLIER:.2f}x : "
        "ON"
    )

    # ========================================================
    # TOP 30
    # ========================================================

    print()

    print(
        "TOP 30 QUALIFIED STOCKS"
    )

    print(
        "-" * 100
    )

    if top30.empty:

        print(
            "No stocks satisfy all eligibility conditions."
        )

    else:

        display_columns = [
            "Research_Rank",
            "Symbol",
            "Close",
            "Momentum_9M",
            "Breakout_6M",
            "Volume_Ratio",
            "Combined_Score",
        ]

        available = [
            column
            for column in display_columns
            if column in top30.columns
        ]

        table = top30[
            available
        ].copy()

        # ----------------------------------------------------
        # Percent columns
        # ----------------------------------------------------

        for column in [
            "Momentum_9M",
            "Breakout_6M",
            "Combined_Score",
        ]:

            if column in table.columns:

                table[column] = (
                    table[column]
                    * 100
                ).round(2)

        # ----------------------------------------------------
        # Volume
        # ----------------------------------------------------

        if "Volume_Ratio" in table.columns:

            table["Volume_Ratio"] = (
                table["Volume_Ratio"]
                .round(2)
            )

        # ----------------------------------------------------
        # Price
        # ----------------------------------------------------

        if "Close" in table.columns:

            table["Close"] = (
                table["Close"]
                .round(2)
            )

        print(
            table.to_string(
                index=False
            )
        )

    # ========================================================
    # TOP 10
    # ========================================================

    print()

    print(
        "TOP 10 PORTFOLIO"
    )

    print(
        "-" * 100
    )

    if top10.empty:

        print(
            "NO QUALIFIED STOCKS."
        )

    else:

        portfolio_columns = [
            "Research_Rank",
            "Symbol",
            "Close",
            "Momentum_9M",
            "Breakout_6M",
            "Volume_Ratio",
            "Combined_Score",
            "Target_Capital",
        ]

        available = [
            column
            for column in portfolio_columns
            if column in top10.columns
        ]

        portfolio = top10[
            available
        ].copy()

        for column in [
            "Momentum_9M",
            "Breakout_6M",
            "Combined_Score",
        ]:

            if column in portfolio.columns:

                portfolio[column] = (
                    portfolio[column]
                    * 100
                ).round(2)

        if "Volume_Ratio" in portfolio.columns:

            portfolio["Volume_Ratio"] = (
                portfolio["Volume_Ratio"]
                .round(2)
            )

        if "Close" in portfolio.columns:

            portfolio["Close"] = (
                portfolio["Close"]
                .round(2)
            )

        if "Target_Capital" in portfolio.columns:

            portfolio["Target_Capital"] = (
                portfolio["Target_Capital"]
                .round(2)
            )

        print(
            portfolio.to_string(
                index=False
            )
        )

        capital_per_position = (
            TOTAL_CAPITAL
            / TOP_PORTFOLIO_STOCKS
        )

        capital_allocated = (
            len(top10)
            * capital_per_position
        )

        cash_remaining = (
            TOTAL_CAPITAL
            - capital_allocated
        )

        print()

        print(
            f"Capital per position : "
            f"₹{capital_per_position:,.2f}"
        )

        print(
            f"Capital allocated     : "
            f"₹{capital_allocated:,.2f}"
        )

        print(
            f"Cash remaining        : "
            f"₹{cash_remaining:,.2f}"
        )

    # ========================================================
    # REGIME
    # ========================================================

    print()

    print(
        "REGIME"
    )

    print(
        "-" * 100
    )

    print(
        f"Market regime monitor : "
        f"{regime_info['Regime']}"
    )

    print(
        "Bear overlay          : "
        f"{'ON' if ENABLE_BEAR_OVERLAY else 'OFF'}"
    )

    # ========================================================
    # ORDERS
    # ========================================================

    print()

    print(
        "ORDERS"
    )

    print(
        "-" * 100
    )

    if orders.empty:

        print(
            "No orders."
        )

    else:

        print(
            orders.to_string(
                index=False
            )
        )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    program_start = time.perf_counter()

    # ========================================================
    # HEADER
    # ========================================================

    print_header(
        PROJECT_NAME
    )

    print(
        "FAST MONTHLY MOMENTUM + BREAKOUT "
        "PRODUCTION SIGNAL ENGINE"
    )

    print()

    print(
        f"Strategy : {STRATEGY_NAME}"
    )

    print()

    print(
        "NEW LIVE FILTER:"
    )

    print(
        "  Momentum_9M must be >= 0"
    )

    print(
        "  Breakout_6M must be >= 0"
    )

    print(
        "  Volume_Ratio must be >= 1.50x"
    )

    # ========================================================
    # STEP 1
    #
    # UNIVERSE
    # ========================================================

    print_subheader(
        "STEP 1 — PROJECT DATA"
    )

    refresh_timer = Timer()

    refresh_universe_if_available()

    symbols = (
        load_universe_symbols()
    )

    universe_count = len(
        symbols
    )

    print(
        f"Universe file : "
        f"{UNIVERSE_FILE}"
    )

    print(
        f"Symbols       : "
        f"{universe_count:,}"
    )

    print(
        f"Universe refresh/load time : "
        f"{refresh_timer.elapsed():.2f}s"
    )

    # ========================================================
    # STEP 2
    #
    # DAILY MARKET DATA
    # ========================================================

    print_subheader(
        "STEP 2 — MARKET DATA"
    )

    (
        daily_data,
        valid_symbols,
    ) = load_daily_market_data(
        symbols
    )

    valid_daily_symbol_count = len(
        set(
            clean_symbol(symbol)
            for symbol in valid_symbols
        )
    )

    # ========================================================
    # STEP 3
    #
    # MONTHLY DATA
    # ========================================================

    print_subheader(
        "STEP 3 — MONTHLY DATA"
    )

    monthly = (
        convert_daily_to_completed_monthly(
            daily_data
        )
    )

    usable_monthly_symbols = (
        monthly["Symbol"]
        .nunique()
    )

    completed_months = (
        monthly["Date"]
        .nunique()
    )

    if completed_months < MIN_MONTHS_REQUIRED:

        raise ValueError(
            f"Only {completed_months} completed months "
            f"available. Minimum required is "
            f"{MIN_MONTHS_REQUIRED}."
        )

    save_monthly_cache(
        monthly
    )

    # ========================================================
    # STEP 4
    #
    # FEATURES
    # ========================================================

    features = (
        calculate_monthly_features(
            monthly
        )
    )

    # ========================================================
    # STEP 5
    #
    # CURRENT SIGNAL
    # ========================================================

    (
        ranked,
        top30,
        top10,
        latest_date,
    ) = generate_current_signal(
        features
    )

    # ========================================================
    # STEP 6
    #
    # REGIME MONITOR
    # ========================================================

    print_subheader(
        "REGIME MONITOR"
    )

    regime_info = (
        calculate_regime_monitor(
            monthly
        )
    )

    print(
        f"Regime       : "
        f"{regime_info['Regime']}"
    )

    if not pd.isna(
        regime_info["Market_Proxy"]
    ):

        print(
            f"Market proxy : "
            f"{regime_info['Market_Proxy']:.3f}"
        )

    if not pd.isna(
        regime_info["Market_10M_MA"]
    ):

        print(
            f"10M MA       : "
            f"{regime_info['Market_10M_MA']:.3f}"
        )

    if not pd.isna(
        regime_info["Previous_10M_MA"]
    ):

        print(
            f"Previous MA  : "
            f"{regime_info['Previous_10M_MA']:.3f}"
        )

    print()

    print(
        "NOTE: Regime monitor is diagnostic only."
    )

    print(
        "Locked R0 strategy remains unchanged."
    )

    print(
        f"Bear overlay enabled : "
        f"{ENABLE_BEAR_OVERLAY}"
    )

    # ========================================================
    # STEP 7
    #
    # CURRENT HOLDINGS
    # ========================================================

    print_subheader(
        "CURRENT HOLDINGS"
    )

    current_holdings = (
        load_current_holdings()
    )

    print(
        f"Current holdings : "
        f"{len(current_holdings):,}"
    )

    # ========================================================
    # STEP 8
    #
    # ORDER GENERATION
    # ========================================================

    orders = generate_orders(
        top10=top10,
        current_holdings=current_holdings,
    )

    # ========================================================
    # STEP 9
    #
    # FINAL RUNTIME
    # ========================================================

    program_end = time.perf_counter()

    runtime_seconds = (
        program_end
        - program_start
    )

    # ========================================================
    # STEP 10
    #
    # SAVE CSV REPORTS
    # ========================================================

    save_csv_reports(
        ranked=ranked,
        top30=top30,
        top10=top10,
        orders=orders,
        universe_count=universe_count,
        valid_daily_symbols=valid_daily_symbol_count,
        usable_monthly_symbols=usable_monthly_symbols,
        completed_months=completed_months,
        latest_date=latest_date,
        regime_info=regime_info,
        runtime_seconds=runtime_seconds,
    )

    # ========================================================
    # STEP 11
    #
    # SAVE EXCEL
    # ========================================================

    save_excel_report(
        ranked=ranked,
        top30=top30,
        top10=top10,
        orders=orders,
        universe_count=universe_count,
        valid_daily_symbols=valid_daily_symbol_count,
        usable_monthly_symbols=usable_monthly_symbols,
        completed_months=completed_months,
        latest_date=latest_date,
        regime_info=regime_info,
        runtime_seconds=runtime_seconds,
    )

    # ========================================================
    # STEP 12
    #
    # DISPLAY
    # ========================================================

    display_signal(
        ranked=ranked,
        top30=top30,
        top10=top10,
        orders=orders,
        universe_count=universe_count,
        valid_daily_symbols=valid_daily_symbol_count,
        usable_monthly_symbols=usable_monthly_symbols,
        completed_months=completed_months,
        latest_date=latest_date,
        regime_info=regime_info,
    )

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print()

    print(
        "=" * 100
    )

    print(
        "PRODUCTION RUN COMPLETE"
    )

    print(
        "=" * 100
    )

    print(
        f"Universe              : "
        f"{universe_count:,}"
    )

    print(
        f"Valid daily symbols   : "
        f"{valid_daily_symbol_count:,}"
    )

    print(
        f"Usable monthly symbols: "
        f"{usable_monthly_symbols:,}"
    )

    print(
        f"Completed months      : "
        f"{completed_months:,}"
    )

    print(
        f"Eligible stocks       : "
        f"{len(ranked):,}"
    )

    print(
        f"Top 30 stocks         : "
        f"{len(top30):,}"
    )

    print(
        f"Top 10 stocks         : "
        f"{len(top10):,}"
    )

    print(
        f"Regime                : "
        f"{regime_info['Regime']}"
    )

    print(
        f"Bear overlay          : "
        f"{'ON' if ENABLE_BEAR_OVERLAY else 'OFF'}"
    )

    print()

    print(
        "HARD FILTERS:"
    )

    print(
        "  Momentum_9M >= 0     : ON"
    )

    print(
        "  Breakout_6M >= 0     : ON"
    )

    print(
        f"  Volume_Ratio >= "
        f"{VOLUME_MULTIPLIER:.2f}x : ON"
    )

    print()

    print(
        f"Total runtime         : "
        f"{runtime_seconds:.2f}s"
    )

    print()

    print(
        "OUTPUT FILES:"
    )

    print(
        f"  {CURRENT_SIGNAL_FILE}"
    )

    print(
        f"  {TOP30_FILE}"
    )

    print(
        f"  {ORDERS_FILE}"
    )

    print(
        f"  {RUN_SUMMARY_FILE}"
    )

    print(
        f"  {EXCEL_FILE}"
    )

    print()

    print(
        "IMPORTANT:"
    )

    print(
        "Negative Momentum_9M and negative Breakout_6M "
        "are excluded before ranking."
    )

    print(
        "The additional non-negative filters should be "
        "backtested before treating the modified strategy "
        "as statistically validated."
    )

    print(
        "=" * 100
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print()

        print(
            "Program stopped by user."
        )

        sys.exit(1)

    except Exception as exc:

        print()

        print(
            "=" * 100
        )

        print(
            "PROGRAM FAILED"
        )

        print(
            "=" * 100
        )

        print(
            f"Error: {type(exc).__name__}: {exc}"
        )

        print()

        sys.exit(1)