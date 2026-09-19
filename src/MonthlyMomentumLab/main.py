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
4. Calculate daily EMA market breadth.
5. Convert daily data to completed monthly bars.
6. Calculate:
       - 9M momentum
       - 6M breakout
       - volume ratio
7. Apply hard eligibility filters.
8. Rank eligible stocks.
9. Display Top 30 research candidates.
10. Select Top 10 portfolio candidates.
11. Generate BUY / HOLD / SELL instructions.
12. Generate CSV reports.
13. Generate Excel report.
14. Calculate diagnostic market regime.
15. Bear overlay remains OFF by default.

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
# OPTIONAL YFINANCE IMPORT
# ============================================================

try:
    import yfinance as yf

except ImportError:

    yf = None


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
# EMA MARKET BREADTH PARAMETERS
# ============================================================

EMA_PERIODS = [
    20,
    50,
    200,
]


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


def format_indian_number(
    value,
) -> str:

    """
    Format numbers using Indian comma grouping.

    Examples:
        172500    -> 1,72,500
        5000      -> 5,000
        1250000   -> 12,50,000
    """

    try:

        if pd.isna(value):

            return ""

        number = float(value)

        if not np.isfinite(number):

            return ""

        if number.is_integer():

            return f"{int(number):,}".replace(
                ",",
                ",",
                1,
            ) if False else indian_integer_format(
                int(number)
            )

        integer_part = int(number)
        decimal_part = abs(number - integer_part)

        formatted_integer = indian_integer_format(
            abs(integer_part)
        )

        if integer_part < 0:

            formatted_integer = (
                "-" + formatted_integer
            )

        decimal_string = (
            f"{decimal_part:.2f}"
            .split(".")[1]
            .rstrip("0")
        )

        if decimal_string:

            return (
                f"{formatted_integer}."
                f"{decimal_string}"
            )

        return formatted_integer

    except (
        TypeError,
        ValueError,
    ):

        return ""


def indian_integer_format(
    number: int,
) -> str:

    """
    Convert integer to Indian comma grouping.

    172500 -> 1,72,500
    """

    negative = number < 0

    value = str(abs(int(number)))

    if len(value) <= 3:

        result = value

    else:

        last_three = value[-3:]

        remaining = value[:-3]

        groups = []

        while len(remaining) > 2:

            groups.insert(
                0,
                remaining[-2:],
            )

            remaining = remaining[:-2]

        if remaining:

            groups.insert(
                0,
                remaining,
            )

        result = (
            ",".join(groups)
            + ","
            + last_three
        )

    if negative:

        return "-" + result

    return result


def format_market_cap_column(
    df: pd.DataFrame,
) -> pd.DataFrame:

    """
    Create a display copy of Market Cap (In Cr)
    using Indian number formatting.
    """

    result = df.copy()

    if "Market Cap (In Cr)" in result.columns:

        result["Market Cap (In Cr)"] = (
            result["Market Cap (In Cr)"]
            .apply(format_indian_number)
        )

    return result


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
# NIFTY 500 EMA MARKET BREADTH
# ============================================================

def classify_breadth_percentage(
    percentage: float,
) -> str:

    if pd.isna(percentage):

        return "UNKNOWN"

    if percentage >= 70.0:

        return "High"

    if percentage >= 50.0:

        return "Medium"

    return "Low"


def calculate_ema_market_breadth(
    daily_data: pd.DataFrame,
) -> dict:

    """
    Calculate Nifty 500 EMA market breadth.

    Breadth is measured on the latest common available
    market-data date.

    For each stock:
        Close > 20D EMA
        Close > 50D EMA
        Close > 200D EMA

    Classification:
        >= 70%      High
        50% to <70% Medium
        <50%        Low
    """

    print_header(
        "CALCULATING NIFTY 500 EMA MARKET BREADTH"
    )

    if daily_data.empty:

        return {
            "Program_Run_Date": pd.Timestamp.now().date(),
            "Latest_Data_Date": pd.NaT,
            "Earliest_Latest_Data_Date": pd.NaT,
            "Valid_Stocks": 0,
            "Above_20D": 0,
            "Above_20D_Pct": np.nan,
            "Above_20D_Class": "UNKNOWN",
            "Above_50D": 0,
            "Above_50D_Pct": np.nan,
            "Above_50D_Class": "UNKNOWN",
            "Above_200D": 0,
            "Above_200D_Pct": np.nan,
            "Above_200D_Class": "UNKNOWN",
            "Pattern": "No market data available.",
        }

    data = daily_data.copy()

    if not isinstance(
        data.index,
        pd.DatetimeIndex,
    ):

        data.index = pd.to_datetime(
            data.index
        )

    data = data.sort_index()

    close_df = get_field(
        data,
        "Close",
    ).copy()

    close_df.index = pd.to_datetime(
        close_df.index
    )

    close_df = close_df.sort_index()

    close_df = close_df.apply(
        pd.to_numeric,
        errors="coerce",
    )

    # --------------------------------------------------------
    # Latest available data date
    # --------------------------------------------------------

    available_counts = (
        close_df.notna()
        .sum(axis=1)
    )

    available_counts = (
        available_counts[
            available_counts > 0
        ]
    )

    if available_counts.empty:

        return {
            "Program_Run_Date": pd.Timestamp.now().date(),
            "Latest_Data_Date": pd.NaT,
            "Earliest_Latest_Data_Date": pd.NaT,
            "Valid_Stocks": 0,
            "Above_20D": 0,
            "Above_20D_Pct": np.nan,
            "Above_20D_Class": "UNKNOWN",
            "Above_50D": 0,
            "Above_50D_Pct": np.nan,
            "Above_50D_Class": "UNKNOWN",
            "Above_200D": 0,
            "Above_200D_Pct": np.nan,
            "Above_200D_Class": "UNKNOWN",
            "Pattern": "No valid closing-price data available.",
        }

    latest_date = (
        available_counts.index.max()
    )

    # --------------------------------------------------------
    # Latest available data by date
    # --------------------------------------------------------

    latest_counts = (
        available_counts[
            available_counts.index
            >= latest_date
        ]
    )

    print(
        f"Program run date: "
        f"{pd.Timestamp.now().date()}"
    )

    print(
        f"Latest available market-data date: "
        f"{latest_date.date()}"
    )

    # Earliest date among stocks having latest data.
    # This is normally the same as latest_date for a
    # synchronized Nifty 500 dataset.
    latest_stock_dates = []

    for symbol in close_df.columns:

        series = close_df[symbol].dropna()

        if not series.empty:

            latest_stock_dates.append(
                series.index.max()
            )

    earliest_latest_data_date = (
        min(latest_stock_dates)
        if latest_stock_dates
        else pd.NaT
    )

    print(
        f"Earliest latest-data date: "
        f"{earliest_latest_data_date.date()}"
        if not pd.isna(
            earliest_latest_data_date
        )
        else
        "Earliest latest-data date: N/A"
    )

    print()

    print(
        "Latest available data by date:"
    )

    # Show latest date count.
    print(
        f"{latest_date.date()}: "
        f"{int(available_counts.loc[latest_date]):,} stocks"
    )

    # --------------------------------------------------------
    # Calculate EMA
    # --------------------------------------------------------

    ema20 = (
        close_df
        .ewm(
            span=20,
            adjust=False,
            min_periods=20,
        )
        .mean()
    )

    ema50 = (
        close_df
        .ewm(
            span=50,
            adjust=False,
            min_periods=50,
        )
        .mean()
    )

    ema200 = (
        close_df
        .ewm(
            span=200,
            adjust=False,
            min_periods=200,
        )
        .mean()
    )

    # --------------------------------------------------------
    # Use stocks having data on latest_date
    # --------------------------------------------------------

    latest_close = close_df.loc[
        latest_date
    ]

    latest_ema20 = ema20.loc[
        latest_date
    ]

    latest_ema50 = ema50.loc[
        latest_date
    ]

    latest_ema200 = ema200.loc[
        latest_date
    ]

    valid_20 = (
        latest_close.notna()
        & latest_ema20.notna()
    )

    valid_50 = (
        latest_close.notna()
        & latest_ema50.notna()
    )

    valid_200 = (
        latest_close.notna()
        & latest_ema200.notna()
    )

    # A stock is considered valid for the breadth date
    # when a close exists on the latest available date.
    valid_stocks = int(
        latest_close.notna().sum()
    )

    # --------------------------------------------------------
    # Breadth calculations
    # --------------------------------------------------------

    above_20 = int(
        (
            (
                latest_close
                > latest_ema20
            )
            & valid_20
        ).sum()
    )

    above_50 = int(
        (
            (
                latest_close
                > latest_ema50
            )
            & valid_50
        ).sum()
    )

    above_200 = int(
        (
            (
                latest_close
                > latest_ema200
            )
            & valid_200
        ).sum()
    )

    pct_20 = (
        above_20
        / valid_stocks
        * 100.0
        if valid_stocks
        else np.nan
    )

    pct_50 = (
        above_50
        / valid_stocks
        * 100.0
        if valid_stocks
        else np.nan
    )

    pct_200 = (
        above_200
        / valid_stocks
        * 100.0
        if valid_stocks
        else np.nan
    )

    class_20 = classify_breadth_percentage(
        pct_20
    )

    class_50 = classify_breadth_percentage(
        pct_50
    )

    class_200 = classify_breadth_percentage(
        pct_200
    )

    # --------------------------------------------------------
    # Pattern
    # --------------------------------------------------------

    classifications = [
        class_20,
        class_50,
        class_200,
    ]

    if all(
        value == "High"
        for value in classifications
    ):

        pattern = (
            "High participation across short-, "
            "medium-, and long-term trends."
        )

    elif all(
        value == "Low"
        for value in classifications
    ):

        pattern = (
            "Low participation across short-, "
            "medium-, and long-term trends."
        )

    elif all(
        value == "Medium"
        for value in classifications
    ):

        pattern = (
            "Medium participation across short-, "
            "medium-, and long-term trends."
        )

    else:

        pattern = (
            "Mixed participation across short-, "
            "medium-, and long-term trends."
        )

    # --------------------------------------------------------
    # Display
    # --------------------------------------------------------

    print()

    print(
        f"Breadth date: "
        f"{latest_date.date()}"
    )

    print(
        f"Valid Nifty 500 stocks: "
        f"{valid_stocks:,}"
    )

    print(
        f"Above 20D EMA: "
        f"{above_20:,} "
        f"({pct_20:.2f}%) — "
        f"{class_20}"
    )

    print(
        f"Above 50D EMA: "
        f"{above_50:,} "
        f"({pct_50:.2f}%) — "
        f"{class_50}"
    )

    print(
        f"Above 200D EMA: "
        f"{above_200:,} "
        f"({pct_200:.2f}%) — "
        f"{class_200}"
    )

    print(
        f"Market Breadth Pattern: "
        f"{pattern}"
    )

    return {
        "Program_Run_Date": pd.Timestamp.now().date(),
        "Latest_Data_Date": latest_date,
        "Earliest_Latest_Data_Date": earliest_latest_data_date,
        "Valid_Stocks": valid_stocks,
        "Above_20D": above_20,
        "Above_20D_Pct": pct_20,
        "Above_20D_Class": class_20,
        "Above_50D": above_50,
        "Above_50D_Pct": pct_50,
        "Above_50D_Class": class_50,
        "Above_200D": above_200,
        "Above_200D_Pct": pct_200,
        "Above_200D_Class": class_200,
        "Pattern": pattern,
    }


# ============================================================
# FETCH STOCK METADATA
# ============================================================

def fetch_stock_metadata(
    symbols: list[str],
) -> pd.DataFrame:

    """
    Fetch current Yahoo Finance metadata for requested
    symbols.

    Output:
        Symbol
        Market Cap (In Cr)
        Sector
        Industry

    Market cap is converted from rupees to Crores:

        ₹172,500,00,00,000 / 1,00,00,000
        = ₹172,500 Cr

    Metadata is informational only and does not affect
    ranking, eligibility, allocation, or signals.
    """

    columns = [
        "Symbol",
        "Market Cap (In Cr)",
        "Sector",
        "Industry",
    ]

    if not symbols:

        return pd.DataFrame(
            columns=columns
        )

    if yf is None:

        print()

        print(
            "WARNING: yfinance is not available."
        )

        print(
            "Market Cap, Sector and Industry will be blank."
        )

        return pd.DataFrame(
            {
                "Symbol": [
                    clean_symbol(symbol)
                    for symbol in symbols
                ],
                "Market Cap (In Cr)": np.nan,
                "Sector": "",
                "Industry": "",
            }
        )

    print()

    print(
        "Fetching Market Cap / Sector / Industry metadata "
        "for Top 30 stocks..."
    )

    timer = Timer()

    records = []

    for index, symbol in enumerate(
        symbols,
        start=1,
    ):

        symbol = clean_symbol(
            symbol
        )

        market_cap_cr = np.nan
        sector = ""
        industry = ""

        try:

            ticker = yf.Ticker(
                symbol
            )

            info = ticker.info

            market_cap = info.get(
                "marketCap"
            )

            if market_cap is not None:

                market_cap_cr = (
                    float(market_cap)
                    / 10_000_000.0
                )

            sector_value = info.get(
                "sector"
            )

            industry_value = info.get(
                "industry"
            )

            if sector_value is not None:

                sector = str(
                    sector_value
                ).strip()

            if industry_value is not None:

                industry = str(
                    industry_value
                ).strip()

        except Exception:

            pass

        records.append(
            {
                "Symbol": symbol,
                "Market Cap (In Cr)": market_cap_cr,
                "Sector": sector,
                "Industry": industry,
            }
        )

        if index % 10 == 0:

            print(
                f"Metadata processed: "
                f"{index}/{len(symbols)}"
            )

    result = pd.DataFrame(
        records,
        columns=columns,
    )

    print(
        f"Metadata completed in "
        f"{timer.elapsed():.2f}s"
    )

    return result


# ============================================================
# ATTACH STOCK METADATA
# ============================================================

def attach_stock_metadata(
    df: pd.DataFrame,
) -> pd.DataFrame:

    if df.empty:

        result = df.copy()

        for column in [
            "Market Cap (In Cr)",
            "Sector",
            "Industry",
        ]:

            if column not in result.columns:

                result[column] = (
                    pd.Series(
                        dtype="object"
                    )
                )

        return result

    symbols = (
        df["Symbol"]
        .astype(str)
        .map(clean_symbol)
        .drop_duplicates()
        .tolist()
    )

    metadata = fetch_stock_metadata(
        symbols
    )

    result = df.copy()

    result["Symbol"] = (
        result["Symbol"]
        .astype(str)
        .map(clean_symbol)
    )

    result = result.merge(
        metadata,
        on="Symbol",
        how="left",
    )

    # --------------------------------------------------------
    # Arrange:
    #
    # Research_Rank
    # Symbol
    # Sector
    # Industry
    # Close
    # Market Cap (In Cr)
    # ...
    # --------------------------------------------------------

    preferred_order = [
        "Research_Rank",
        "Symbol",
        "Sector",
        "Industry",
        "Close",
        "Market Cap (In Cr)",
    ]

    remaining = [
        column
        for column in result.columns
        if column not in preferred_order
    ]

    result = result[
        [
            column
            for column in preferred_order
            if column in result.columns
        ]
        + remaining
    ]

    return result


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
        -
        target_symbols
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
    breadth_info: dict,
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
                "EMA_Breadth_Date": breadth_info[
                    "Latest_Data_Date"
                ],
                "EMA20_Above_Count": breadth_info[
                    "Above_20D"
                ],
                "EMA20_Above_Pct": breadth_info[
                    "Above_20D_Pct"
                ],
                "EMA20_Breadth_Class": breadth_info[
                    "Above_20D_Class"
                ],
                "EMA50_Above_Count": breadth_info[
                    "Above_50D"
                ],
                "EMA50_Above_Pct": breadth_info[
                    "Above_50D_Pct"
                ],
                "EMA50_Breadth_Class": breadth_info[
                    "Above_50D_Class"
                ],
                "EMA200_Above_Count": breadth_info[
                    "Above_200D"
                ],
                "EMA200_Above_Pct": breadth_info[
                    "Above_200D_Pct"
                ],
                "EMA200_Breadth_Class": breadth_info[
                    "Above_200D_Class"
                ],
                "Market_Breadth_Pattern": breadth_info[
                    "Pattern"
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
    breadth_info: dict,
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
                        "Metric": "EMA Breadth Date",
                        "Value": breadth_info[
                            "Latest_Data_Date"
                        ],
                    },
                    {
                        "Metric": "Above 20D EMA",
                        "Value": (
                            f"{breadth_info['Above_20D']:,} "
                            f"({breadth_info['Above_20D_Pct']:.2f}%) "
                            f"— {breadth_info['Above_20D_Class']}"
                        ),
                    },
                    {
                        "Metric": "Above 50D EMA",
                        "Value": (
                            f"{breadth_info['Above_50D']:,} "
                            f"({breadth_info['Above_50D_Pct']:.2f}%) "
                            f"— {breadth_info['Above_50D_Class']}"
                        ),
                    },
                    {
                        "Metric": "Above 200D EMA",
                        "Value": (
                            f"{breadth_info['Above_200D']:,} "
                            f"({breadth_info['Above_200D_Pct']:.2f}%) "
                            f"— {breadth_info['Above_200D_Class']}"
                        ),
                    },
                    {
                        "Metric": "Market Breadth Pattern",
                        "Value": breadth_info[
                            "Pattern"
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

            # ------------------------------------------------
            # EMA Breadth
            # ------------------------------------------------

            breadth_df = pd.DataFrame(
                [
                    {
                        "Metric": "Program Run Date",
                        "Value": breadth_info[
                            "Program_Run_Date"
                        ],
                    },
                    {
                        "Metric": "Latest Data Date",
                        "Value": breadth_info[
                            "Latest_Data_Date"
                        ],
                    },
                    {
                        "Metric": "Earliest Latest-Data Date",
                        "Value": breadth_info[
                            "Earliest_Latest_Data_Date"
                        ],
                    },
                    {
                        "Metric": "Valid Nifty 500 Stocks",
                        "Value": breadth_info[
                            "Valid_Stocks"
                        ],
                    },
                    {
                        "Metric": "Above 20D EMA",
                        "Value": (
                            f"{breadth_info['Above_20D']:,} "
                            f"({breadth_info['Above_20D_Pct']:.2f}%) "
                            f"— {breadth_info['Above_20D_Class']}"
                        ),
                    },
                    {
                        "Metric": "Above 50D EMA",
                        "Value": (
                            f"{breadth_info['Above_50D']:,} "
                            f"({breadth_info['Above_50D_Pct']:.2f}%) "
                            f"— {breadth_info['Above_50D_Class']}"
                        ),
                    },
                    {
                        "Metric": "Above 200D EMA",
                        "Value": (
                            f"{breadth_info['Above_200D']:,} "
                            f"({breadth_info['Above_200D_Pct']:.2f}%) "
                            f"— {breadth_info['Above_200D_Class']}"
                        ),
                    },
                    {
                        "Metric": "Market Breadth Pattern",
                        "Value": breadth_info[
                            "Pattern"
                        ],
                    },
                ]
            )

            breadth_df.to_excel(
                writer,
                sheet_name="EMA Market Breadth",
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
            "Sector",
            "Industry",
            "Close",
            "Market Cap (In Cr)",
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

        # ----------------------------------------------------
        # Market Cap Indian formatting
        # ----------------------------------------------------

        if "Market Cap (In Cr)" in table.columns:

            table["Market Cap (In Cr)"] = (
                table["Market Cap (In Cr)"]
                .apply(format_indian_number)
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
            "Sector",
            "Industry",
            "Close",
            "Market Cap (In Cr)",
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

        if "Market Cap (In Cr)" in portfolio.columns:

            portfolio["Market Cap (In Cr)"] = (
                portfolio["Market Cap (In Cr)"]
                .apply(format_indian_number)
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

    program_start_timestamp = pd.Timestamp.now()

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
    # EMA MARKET BREADTH
    # ========================================================

    breadth_info = (
        calculate_ema_market_breadth(
            daily_data
        )
    )

    # ========================================================
    # STEP 4
    #
    # MONTHLY DATA
    # ========================================================

    print_subheader(
        "STEP 4 — MONTHLY DATA"
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
    # STEP 5
    #
    # FEATURES
    # ========================================================

    features = (
        calculate_monthly_features(
            monthly
        )
    )

    # ========================================================
    # STEP 6
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
    # STEP 7
    #
    # STOCK METADATA
    # ========================================================

    # Metadata is attached after ranking so only the
    # Top 30 research candidates require Yahoo metadata
    # lookups. It has NO effect on strategy calculations.
    top30 = attach_stock_metadata(
        top30
    )

    # Top 10 is taken from the already ranked Top 30.
    # Merge metadata from Top 30 instead of making another
    # set of Yahoo requests.
    metadata_columns = [
        "Symbol",
        "Market Cap (In Cr)",
        "Sector",
        "Industry",
    ]

    metadata_lookup = top30[
        [
            column
            for column in metadata_columns
            if column in top30.columns
        ]
    ].drop_duplicates(
        subset=["Symbol"]
    )

    top10 = top10.merge(
        metadata_lookup,
        on="Symbol",
        how="left",
    )

    preferred_top10_order = [
        "Research_Rank",
        "Symbol",
        "Sector",
        "Industry",
        "Close",
        "Market Cap (In Cr)",
    ]

    remaining_top10 = [
        column
        for column in top10.columns
        if column not in preferred_top10_order
    ]

    top10 = top10[
        [
            column
            for column in preferred_top10_order
            if column in top10.columns
        ]
        + remaining_top10
    ]

    # ========================================================
    # STEP 8
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
    # STEP 9
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
    # STEP 10
    #
    # ORDER GENERATION
    # ========================================================

    orders = generate_orders(
        top10=top10,
        current_holdings=current_holdings,
    )

    # ========================================================
    # STEP 11
    #
    # FINAL RUNTIME
    # ========================================================

    program_end_timestamp = pd.Timestamp.now()

    program_end = time.perf_counter()

    runtime_seconds = (
        program_end
        - program_start
    )

    # ========================================================
    # STEP 12
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
        breadth_info=breadth_info,
        runtime_seconds=runtime_seconds,
    )

    # ========================================================
    # STEP 13
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
        breadth_info=breadth_info,
        runtime_seconds=runtime_seconds,
    )

    # ========================================================
    # STEP 14
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
    # EMA MARKET BREADTH SUMMARY
    # ========================================================

    print()

    print(
        "=" * 80
    )

    print(
        "EMA MARKET BREADTH SUMMARY"
    )

    print(
        "=" * 80
    )

    print(
        f"Breadth date        : "
        f"{breadth_info['Latest_Data_Date'].date()}"
    )

    print(
        f"Valid Nifty 500     : "
        f"{breadth_info['Valid_Stocks']:,}"
    )

    print(
        f"Above 20D EMA       : "
        f"{breadth_info['Above_20D']:,} "
        f"({breadth_info['Above_20D_Pct']:.2f}%) "
        f"— {breadth_info['Above_20D_Class']}"
    )

    print(
        f"Above 50D EMA       : "
        f"{breadth_info['Above_50D']:,} "
        f"({breadth_info['Above_50D_Pct']:.2f}%) "
        f"— {breadth_info['Above_50D_Class']}"
    )

    print(
        f"Above 200D EMA      : "
        f"{breadth_info['Above_200D']:,} "
        f"({breadth_info['Above_200D_Pct']:.2f}%) "
        f"— {breadth_info['Above_200D_Class']}"
    )

    print(
        f"Market Breadth      : "
        f"{breadth_info['Pattern']}"
    )

    # ========================================================
    # PROGRAM RUNTIME
    # ========================================================

    print()

    print(
        "=" * 80
    )

    print(
        "PROGRAM RUNTIME"
    )

    print(
        "=" * 80
    )

    elapsed_hours = int(
        runtime_seconds
        // 3600
    )

    elapsed_minutes = int(
        (
            runtime_seconds
            % 3600
        )
        // 60
    )

    elapsed_seconds = (
        runtime_seconds
        % 60
    )

    total_runtime_formatted = (
        f"{elapsed_hours:02d}:"
        f"{elapsed_minutes:02d}:"
        f"{elapsed_seconds:05.2f}"
    )

    print(
        f"Start timestamp : "
        f"{program_start_timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    print(
        f"End timestamp   : "
        f"{program_end_timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    print(
        f"Elapsed seconds : "
        f"{runtime_seconds:.2f}"
    )

    print(
        f"Total runtime   : "
        f"{total_runtime_formatted}"
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
        "EMA MARKET BREADTH:"
    )

    print(
        f"  Breadth date          : "
        f"{breadth_info['Latest_Data_Date'].date()}"
    )

    print(
        f"  Above 20D EMA         : "
        f"{breadth_info['Above_20D']:,} "
        f"({breadth_info['Above_20D_Pct']:.2f}%) "
        f"— {breadth_info['Above_20D_Class']}"
    )

    print(
        f"  Above 50D EMA         : "
        f"{breadth_info['Above_50D']:,} "
        f"({breadth_info['Above_50D_Pct']:.2f}%) "
        f"— {breadth_info['Above_50D_Class']}"
    )

    print(
        f"  Above 200D EMA        : "
        f"{breadth_info['Above_200D']:,} "
        f"({breadth_info['Above_200D_Pct']:.2f}%) "
        f"— {breadth_info['Above_200D_Class']}"
    )

    print(
        f"  Pattern               : "
        f"{breadth_info['Pattern']}"
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

    print()

    print(
        "Metadata columns are informational only:"
    )

    print(
        "Market Cap (In Cr), Sector and Industry "
        "do not affect eligibility, ranking or portfolio allocation."
    )

    print()

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
