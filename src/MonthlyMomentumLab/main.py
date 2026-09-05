"""
MonthlyMomentumLab
==================

Production Monthly Momentum + Breakout Research Engine

LOCKED STRATEGY
---------------

COMB_M9S0_B6_V1.5_T0_R0_N10_RB1

Meaning:

    COMB  = Momentum + Breakout
    M9    = 9-month momentum
    S0    = No skip month
    B6    = 6-month breakout
    V1.5  = Current monthly volume >= 1.5x reference volume
    T0    = No trend filter
    R0    = No market regime filter
    N10   = Top 10 stocks
    RB1   = Monthly rebalance

Production workflow:

    1. Refresh Nifty 500 universe
    2. Load universe.py
    3. Download 5 years daily OHLCV data
    4. Convert daily data to completed monthly bars
    5. Calculate 9-month momentum
    6. Calculate 6-month breakout
    7. Calculate monthly volume confirmation
    8. Rank stocks using combined score
    9. Display Top 30 research universe
   10. Select Top 10 portfolio
   11. Compare against current holdings
   12. Generate BUY / HOLD / SELL instructions
   13. Save CSV and Excel reports

IMPORTANT
---------

This is a production signal engine.

It does NOT run the full strategy grid.

The research/backtest engine is separate.

Bear-market overlay is calculated as a MONITOR only and is
disabled by default because the locked strategy contains R0
(no regime filter).

Execution model:

    Signal generated after completed month-end data.
    Orders are intended for the next trading session.

Portfolio:

    Capital = Rs. 100,000
    Target holdings = 10
    Equal weight = Rs. 10,000 per position
"""

from __future__ import annotations

# ============================================================
# STANDARD LIBRARY
# ============================================================

import importlib.util
import math
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

# ============================================================
# THIRD-PARTY
# ============================================================

import numpy as np
import pandas as pd

try:
    import openpyxl  # noqa: F401
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False


# ============================================================
# PROJECT PATHS
# ============================================================

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[2]
SRC_ROOT = CURRENT_FILE.parents[1]
LAB_ROOT = CURRENT_FILE.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))


# ============================================================
# PROJECT IMPORTS
# ============================================================

try:
    import trade_data
except Exception as exc:
    raise RuntimeError(
        f"Unable to import trade_data.py.\n"
        f"Expected location: {LAB_ROOT / 'trade_data.py'}\n"
        f"Original error: {exc}"
    ) from exc


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_NAME = "MONTHLYMOMENTUMLAB"

STRATEGY_NAME = "COMB_M9S0_B6_V1.5_T0_R0_N10_RB1"

# ------------------------------------------------------------
# Strategy parameters
# ------------------------------------------------------------

MOMENTUM_MONTHS = 9
BREAKOUT_MONTHS = 6

VOLUME_MULTIPLIER = 1.50

TOP_RESEARCH_STOCKS = 30
TOP_PORTFOLIO_STOCKS = 10

# ------------------------------------------------------------
# Data parameters
# ------------------------------------------------------------

HISTORICAL_PERIOD = "5y"

MIN_MONTHS_REQUIRED = 15

# ------------------------------------------------------------
# Portfolio parameters
# ------------------------------------------------------------

TOTAL_CAPITAL = 100_000.0

# ------------------------------------------------------------
# Bear overlay
# ------------------------------------------------------------

# IMPORTANT:
#
# The locked strategy is R0 = NO REGIME FILTER.
#
# Therefore this must remain False unless independently
# backtested and intentionally enabled.
#
ENABLE_BEAR_OVERLAY = False

# ------------------------------------------------------------
# Output parameters
# ------------------------------------------------------------

RESULTS_DIR = LAB_ROOT / "results"
CACHE_DIR = LAB_ROOT / "cache"

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

MONTHLY_CACHE_FILE = (
    CACHE_DIR / "monthly_market_cache_production_v1.pkl"
)

CURRENT_SIGNAL_FILE = (
    RESULTS_DIR / "current_monthly_signal.csv"
)

TOP30_FILE = (
    RESULTS_DIR / "current_monthly_top30.csv"
)

ORDERS_FILE = (
    RESULTS_DIR / "current_monthly_orders.csv"
)

RUN_SUMMARY_FILE = (
    RESULTS_DIR / "current_monthly_run_summary.csv"
)

HOLDINGS_FILE = (
    RESULTS_DIR / "current_holdings.csv"
)

EXCEL_FILE = (
    RESULTS_DIR / "monthly_momentum_lab_live_signal.xlsx"
)


# ============================================================
# DISPLAY HELPERS
# ============================================================

LINE = "=" * 100
THIN_LINE = "-" * 100


def print_header() -> None:

    print()
    print(LINE)
    print(PROJECT_NAME)
    print(LINE)
    print("PRODUCTION MONTHLY MOMENTUM + BREAKOUT SIGNAL ENGINE")
    print()
    print("Locked strategy:")
    print(f"    {STRATEGY_NAME}")
    print()
    print("Research design:")
    print("    Monthly signal timeframe")
    print("    9-month momentum")
    print("    6-month breakout")
    print("    1.5x monthly volume confirmation")
    print("    No trend filter")
    print("    No market regime filter")
    print("    Top 30 research universe")
    print("    Top 10 portfolio")
    print("    Monthly rebalance")
    print(LINE)
    print()


def print_stage(message: str) -> None:
    print()
    print(THIN_LINE)
    print(message)
    print(THIN_LINE)


# ============================================================
# TIMING
# ============================================================

class Timer:

    def __init__(self) -> None:
        self.start = time.perf_counter()

    def elapsed(self) -> float:
        return time.perf_counter() - self.start


def format_seconds(seconds: float) -> str:

    if seconds < 60:
        return f"{seconds:.2f}s"

    minutes = int(seconds // 60)
    remaining = seconds - minutes * 60

    return f"{minutes}m {remaining:.1f}s"


# ============================================================
# GENERIC HELPERS
# ============================================================

def safe_float(value: Any) -> Optional[float]:

    try:

        if value is None:
            return None

        value = float(value)

        if not math.isfinite(value):
            return None

        return value

    except Exception:
        return None


def clean_symbol(symbol: Any) -> str:

    if symbol is None:
        return ""

    symbol = str(symbol).strip().upper()

    if not symbol:
        return ""

    if symbol.endswith(".NS"):
        return symbol

    return f"{symbol}.NS"


def strip_exchange_suffix(symbol: Any) -> str:

    symbol = str(symbol).strip().upper()

    if symbol.endswith(".NS"):
        return symbol[:-3]

    return symbol


def flatten_columns(data: pd.DataFrame) -> pd.DataFrame:

    data = data.copy()

    if not isinstance(data.columns, pd.MultiIndex):
        return data

    new_columns = []

    for col in data.columns:

        parts = [
            str(x).strip()
            for x in col
            if str(x).strip().lower() != "nan"
        ]

        new_columns.append("_".join(parts))

    data.columns = new_columns

    return data


def normalize_index(data: pd.DataFrame) -> pd.DataFrame:

    data = data.copy()

    try:
        data.index = pd.to_datetime(
            data.index,
            errors="coerce",
        )

        data = data.loc[~data.index.isna()]

        data = data.sort_index()

    except Exception:
        pass

    return data


# ============================================================
# UNIVERSE LOADING
# ============================================================

def refresh_universe_if_available() -> None:

    """
    Use the existing trade_data.py universe refresh function
    if available.

    We intentionally do not implement another Nifty 500 scraper
    here because trade_data.py is the project's existing data
    foundation.
    """

    candidates = [
        "refresh_nifty500_universe",
        "refresh_nifty_500_universe",
        "update_nifty500_universe",
        "update_nifty_500_universe",
    ]

    for function_name in candidates:

        function = getattr(
            trade_data,
            function_name,
            None,
        )

        if callable(function):

            print(
                f"Universe refresh function : "
                f"{function_name}"
            )

            try:
                result = function()

                if result is not None:
                    print(
                        f"Universe refresh result   : "
                        f"{type(result).__name__}"
                    )

            except TypeError:

                # Some existing implementations may not
                # require arguments but may expose a slightly
                # different callable contract.
                try:
                    function()
                except Exception as exc:
                    print(
                        "WARNING: Universe refresh failed."
                    )
                    print(f"Reason: {exc}")

            except Exception as exc:

                print(
                    "WARNING: Universe refresh failed."
                )
                print(f"Reason: {exc}")

            return

    print(
        "Universe refresh function : "
        "Not available in trade_data.py"
    )


def load_universe_symbols() -> List[str]:

    """
    Load symbols from the project's existing universe.py.

    Expected location:

        InvestmentResearchLab/universe.py
    """

    universe_candidates = [
        PROJECT_ROOT / "universe.py",
        SRC_ROOT / "universe.py",
        LAB_ROOT / "universe.py",
    ]

    universe_file = None

    for candidate in universe_candidates:

        if candidate.exists():
            universe_file = candidate
            break

    if universe_file is None:

        raise FileNotFoundError(
            "Could not find universe.py.\n"
            "Expected one of:\n"
            + "\n".join(
                f"  {p}"
                for p in universe_candidates
            )
        )

    print(
        f"Universe file              : "
        f"{universe_file}"
    )

    spec = importlib.util.spec_from_file_location(
        "monthly_momentum_universe",
        universe_file,
    )

    if spec is None or spec.loader is None:

        raise RuntimeError(
            f"Could not load universe.py: "
            f"{universe_file}"
        )

    module = importlib.util.module_from_spec(spec)

    spec.loader.exec_module(module)

    possible_names = [
        "NIFTY_500_SYMBOLS",
        "NIFTY500_SYMBOLS",
        "SYMBOLS",
        "symbols",
        "NIFTY_500",
        "NIFTY500",
    ]

    raw_symbols = None

    for name in possible_names:

        if hasattr(module, name):

            value = getattr(module, name)

            if isinstance(
                value,
                (list, tuple, set),
            ):
                raw_symbols = value
                break

    if raw_symbols is None:

        raise RuntimeError(
            "Could not find a symbol list in universe.py.\n"
            f"Checked: {possible_names}"
        )

    symbols = []

    seen = set()

    for symbol in raw_symbols:

        cleaned = clean_symbol(symbol)

        if not cleaned:
            continue

        if cleaned in seen:
            continue

        seen.add(cleaned)
        symbols.append(cleaned)

    if not symbols:

        raise RuntimeError(
            "Universe loaded successfully but "
            "contains zero symbols."
        )

    print(
        f"Universe symbols           : "
        f"{len(symbols)}"
    )

    return symbols


# ============================================================
# MARKET DATA FUNCTION DISCOVERY
# ============================================================

def find_market_data_function() -> Callable[..., Any]:

    """
    Find the existing historical market data loader.

    Current project function:

        get_historical_market_data_for_symbols
    """

    candidates = [
        "get_historical_market_data_for_symbols",
        "get_historical_market_data",
        "download_historical_market_data",
        "load_historical_market_data",
    ]

    for function_name in candidates:

        function = getattr(
            trade_data,
            function_name,
            None,
        )

        if callable(function):

            print(
                f"Loader function           : "
                f"{function_name}"
            )

            return function

    raise AttributeError(
        "Could not find a historical market data "
        "function in trade_data.py.\n"
        f"Expected one of: {candidates}"
    )


# ============================================================
# MARKET DATA NORMALIZATION
# ============================================================

def normalize_market_data(
    raw_data: pd.DataFrame,
    symbols: Sequence[str],
) -> pd.DataFrame:

    """
    Normalize yfinance/trade_data output into:

        index = DatetimeIndex

        columns = MultiIndex
            level 0 = OHLCV field
            level 1 = symbol

    Target structure:

        Open
        High
        Low
        Close
        Adj Close
        Volume

    Each containing Nifty symbols.
    """

    if raw_data is None:
        raise ValueError(
            "Market data is None."
        )

    if not isinstance(
        raw_data,
        pd.DataFrame,
    ):
        raise TypeError(
            f"Market data must be a DataFrame, "
            f"got {type(raw_data)}"
        )

    data = raw_data.copy()

    if data.empty:
        raise ValueError(
            "Market data DataFrame is empty."
        )

    data = normalize_index(data)

    if data.empty:
        raise ValueError(
            "Market data became empty after "
            "datetime normalization."
        )

    # --------------------------------------------------------
    # Already normalized MultiIndex
    # --------------------------------------------------------

    if isinstance(
        data.columns,
        pd.MultiIndex,
    ):

        level0 = [
            str(x).strip().lower()
            for x in data.columns.get_level_values(0)
        ]

        level1 = [
            str(x).strip().upper()
            for x in data.columns.get_level_values(1)
        ]

        price_names = {
            "open",
            "high",
            "low",
            "close",
            "adj close",
            "adj_close",
            "volume",
        }

        level0_price_count = sum(
            x in price_names
            for x in level0
        )

        level1_price_count = sum(
            x in price_names
            for x in level1
        )

        # Standard yfinance:
        #
        # (Price, Ticker)
        #
        if level0_price_count >= level1_price_count:

            normalized_columns = []

            for price, symbol in data.columns:

                price = str(price).strip()

                symbol = clean_symbol(symbol)

                if price.lower() == "adj_close":
                    price = "Adj Close"

                normalized_columns.append(
                    (
                        price,
                        symbol,
                    )
                )

            data.columns = pd.MultiIndex.from_tuples(
                normalized_columns,
                names=[
                    "Field",
                    "Symbol",
                ],
            )

            return data

        # Alternative:
        #
        # (Ticker, Price)
        #
        normalized_columns = []

        for symbol, price in data.columns:

            symbol = clean_symbol(symbol)

            price = str(price).strip()

            if price.lower() == "adj_close":
                price = "Adj Close"

            normalized_columns.append(
                (
                    price,
                    symbol,
                )
            )

        data.columns = pd.MultiIndex.from_tuples(
            normalized_columns,
            names=[
                "Field",
                "Symbol",
            ],
        )

        return data

    # --------------------------------------------------------
    # Single-level columns
    # --------------------------------------------------------

    # If only one symbol was downloaded, trade_data may return:
    #
    # Open, High, Low, Close, Volume
    #
    price_columns = {
        "open",
        "high",
        "low",
        "close",
        "adj close",
        "adj_close",
        "volume",
    }

    normalized_single = [
        str(col).strip()
        for col in data.columns
    ]

    if all(
        col.lower() in price_columns
        for col in normalized_single
    ):

        symbol = (
            clean_symbol(symbols[0])
            if symbols
            else "UNKNOWN.NS"
        )

        tuples = []

        for col in normalized_single:

            clean_col = col

            if clean_col.lower() == "adj_close":
                clean_col = "Adj Close"

            tuples.append(
                (
                    clean_col,
                    symbol,
                )
            )

        data.columns = pd.MultiIndex.from_tuples(
            tuples,
            names=[
                "Field",
                "Symbol",
            ],
        )

        return data

    # --------------------------------------------------------
    # Flat ticker columns
    # --------------------------------------------------------

    # Attempt to interpret columns such as:
    #
    # RELIANCE.NS_Close
    # RELIANCE.NS_Volume
    #
    flat_columns = []

    for col in data.columns:

        text = str(col).strip()

        matched = False

        for field in [
            "Adj Close",
            "Close",
            "Open",
            "High",
            "Low",
            "Volume",
        ]:

            suffix = "_" + field

            if text.endswith(suffix):

                symbol = text[
                    : -len(suffix)
                ]

                flat_columns.append(
                    (
                        field,
                        clean_symbol(symbol),
                    )
                )

                matched = True
                break

        if not matched:
            flat_columns.append(
                (
                    text,
                    "",
                )
            )

    if all(
        field in price_columns
        for field, _ in [
            (
                str(x[0]).lower(),
                x[1],
            )
            for x in flat_columns
        ]
    ):

        data.columns = pd.MultiIndex.from_tuples(
            flat_columns,
            names=[
                "Field",
                "Symbol",
            ],
        )

        return data

    raise ValueError(
        "Unsupported market-data column structure.\n"
        f"Column type: {type(data.columns)}\n"
        f"First columns: {list(data.columns[:10])}"
    )


# ============================================================
# LOAD DAILY MARKET DATA
# ============================================================

def load_daily_market_data(
    symbols: Sequence[str],
) -> Tuple[pd.DataFrame, List[str]]:

    """
    Load historical daily market data from trade_data.py.

    IMPORTANT:

    The project's trade_data.py returns:

        data, valid_symbols

    rather than only:

        data

    This function explicitly handles that tuple.
    """

    function = find_market_data_function()

    print(
        f"Symbols                    : "
        f"{len(symbols)}"
    )

    print(
        f"Period                     : "
        f"{HISTORICAL_PERIOD}"
    )

    # --------------------------------------------------------
    # Call existing project loader
    # --------------------------------------------------------

    try:

        raw_result = function(
            symbols,
            period=HISTORICAL_PERIOD,
        )

    except TypeError:

        # Fallback for implementations using a different
        # parameter name or positional-only period.

        try:

            raw_result = function(
                symbols,
                HISTORICAL_PERIOD,
            )

        except Exception as exc:

            raise RuntimeError(
                "Historical market data loader failed.\n"
                f"Original error: {exc}"
            ) from exc

    except Exception as exc:

        raise RuntimeError(
            "Historical market data loader failed.\n"
            f"Original error: {exc}"
        ) from exc

    # --------------------------------------------------------
    # IMPORTANT FIX:
    #
    # trade_data.py returns:
    #
    #     data, valid_symbols
    #
    # --------------------------------------------------------

    valid_symbols: List[str] = []

    if isinstance(
        raw_result,
        tuple,
    ):

        if len(raw_result) < 1:

            raise RuntimeError(
                "trade_data.py returned an empty tuple."
            )

        raw_data = raw_result[0]

        if len(raw_result) >= 2:

            candidate_valid_symbols = (
                raw_result[1]
            )

            if candidate_valid_symbols is not None:

                try:

                    valid_symbols = [
                        clean_symbol(x)
                        for x in candidate_valid_symbols
                        if clean_symbol(x)
                    ]

                except Exception:
                    valid_symbols = []

    elif isinstance(
        raw_result,
        pd.DataFrame,
    ):

        # Support loaders that return DataFrame only.
        raw_data = raw_result

    else:

        raise RuntimeError(
            "Unsupported market-data object returned "
            "by trade_data.py: "
            f"{type(raw_result)}"
        )

    # --------------------------------------------------------
    # Validate
    # --------------------------------------------------------

    if not isinstance(
        raw_data,
        pd.DataFrame,
    ):

        raise RuntimeError(
            "trade_data.py returned an unsupported "
            "data object inside its result: "
            f"{type(raw_data)}"
        )

    if raw_data.empty:

        raise RuntimeError(
            "trade_data.py returned an empty DataFrame."
        )

    # If trade_data.py did not provide valid symbols,
    # derive them from requested symbols.
    if not valid_symbols:

        valid_symbols = [
            clean_symbol(x)
            for x in symbols
            if clean_symbol(x)
        ]

    # --------------------------------------------------------
    # Normalize
    # --------------------------------------------------------

    data = normalize_market_data(
        raw_data,
        valid_symbols,
    )

    # --------------------------------------------------------
    # Remove completely empty columns
    # --------------------------------------------------------

    data = data.dropna(
        axis=1,
        how="all",
    )

    # --------------------------------------------------------
    # Final validation
    # --------------------------------------------------------

    if data.empty:

        raise RuntimeError(
            "Normalized market data is empty."
        )

    close_count = 0

    if isinstance(
        data.columns,
        pd.MultiIndex,
    ):

        fields = [
            str(x).strip().lower()
            for x in data.columns.get_level_values(0)
        ]

        close_count = fields.count("close")

    if close_count == 0:

        raise RuntimeError(
            "Normalized market data contains no "
            "Close columns."
        )

    print()
    print(
        f"Requested symbols          : "
        f"{len(symbols)}"
    )

    print(
        f"Valid symbols              : "
        f"{len(valid_symbols)}"
    )

    print(
        f"Invalid symbols            : "
        f"{max(0, len(symbols) - len(valid_symbols))}"
    )

    print(
        f"Daily data shape           : "
        f"{data.shape}"
    )

    print(
        f"Daily start                : "
        f"{data.index.min().date()}"
    )

    print(
        f"Daily end                  : "
        f"{data.index.max().date()}"
    )

    return data, valid_symbols


# ============================================================
# FIELD EXTRACTION
# ============================================================

def get_field(
    data: pd.DataFrame,
    field: str,
) -> pd.DataFrame:

    """
    Extract one OHLCV field from normalized MultiIndex data.
    """

    if not isinstance(
        data.columns,
        pd.MultiIndex,
    ):

        raise ValueError(
            "Expected MultiIndex market data."
        )

    field_lower = field.lower()

    fields = (
        data.columns
        .get_level_values(0)
        .astype(str)
        .str.strip()
        .str.lower()
    )

    matching_columns = [
        col
        for col, field_name in zip(
            data.columns,
            fields,
        )
        if field_name == field_lower
    ]

    if not matching_columns:

        raise KeyError(
            f"Field '{field}' not found in market data."
        )

    result = data.loc[:, matching_columns].copy()

    symbols = [
        clean_symbol(col[1])
        for col in matching_columns
    ]

    result.columns = symbols

    # Remove duplicate symbol columns if any.
    result = result.loc[
        :,
        ~result.columns.duplicated(),
    ]

    return result


# ============================================================
# COMPLETED MONTHLY DATA
# ============================================================

def convert_daily_to_completed_monthly(
    data: pd.DataFrame,
) -> pd.DataFrame:

    """
    Convert daily OHLCV data into completed calendar-month bars.

    IMPORTANT:

    The current incomplete month is excluded.

    This prevents the production signal from using a partially
    completed month.
    """

    close = get_field(
        data,
        "Close",
    )

    high = get_field(
        data,
        "High",
    )

    low = get_field(
        data,
        "Low",
    )

    volume = get_field(
        data,
        "Volume",
    )

    # --------------------------------------------------------
    # Month-end OHLCV
    # --------------------------------------------------------

    monthly_close = close.resample(
        "ME"
    ).last()

    monthly_high = high.resample(
        "ME"
    ).max()

    monthly_low = low.resample(
        "ME"
    ).min()

    monthly_volume = volume.resample(
        "ME"
    ).sum(min_count=1)

    # --------------------------------------------------------
    # Exclude current incomplete month
    # --------------------------------------------------------

    today = pd.Timestamp.now().normalize()

    current_month_start = (
        today.to_period("M")
        .to_timestamp()
    )

    monthly_close = monthly_close.loc[
        monthly_close.index
        < current_month_start
    ]

    monthly_high = monthly_high.loc[
        monthly_high.index
        < current_month_start
    ]

    monthly_low = monthly_low.loc[
        monthly_low.index
        < current_month_start
    ]

    monthly_volume = monthly_volume.loc[
        monthly_volume.index
        < current_month_start
    ]

    # --------------------------------------------------------
    # Build standardized monthly DataFrame
    # --------------------------------------------------------

    monthly_parts = []

    for symbol in monthly_close.columns:

        frame = pd.DataFrame(
            {
                "Close": monthly_close[symbol],
                "High": monthly_high[symbol],
                "Low": monthly_low[symbol],
                "Volume": monthly_volume[symbol],
            }
        )

        frame["Symbol"] = symbol

        frame = frame.reset_index()

        monthly_parts.append(frame)

    if not monthly_parts:

        raise RuntimeError(
            "No monthly data could be constructed."
        )

    monthly = pd.concat(
        monthly_parts,
        ignore_index=True,
    )

    monthly.rename(
        columns={
            "Date": "Month",
        },
        inplace=True,
    )

    monthly["Month"] = pd.to_datetime(
        monthly["Month"],
        errors="coerce",
    )

    monthly["Symbol"] = (
        monthly["Symbol"]
        .astype(str)
        .map(clean_symbol)
    )

    monthly = monthly.dropna(
        subset=[
            "Month",
            "Close",
        ]
    )

    monthly = monthly.sort_values(
        [
            "Symbol",
            "Month",
        ]
    )

    monthly = monthly.reset_index(
        drop=True
    )

    return monthly


# ============================================================
# MONTHLY DATA CACHE
# ============================================================

def save_monthly_cache(
    monthly: pd.DataFrame,
) -> None:

    try:

        monthly.to_pickle(
            MONTHLY_CACHE_FILE
        )

    except Exception as exc:

        print(
            "WARNING: Could not save monthly cache."
        )

        print(
            f"Reason: {exc}"
        )


def load_monthly_cache() -> Optional[pd.DataFrame]:

    if not MONTHLY_CACHE_FILE.exists():
        return None

    try:

        monthly = pd.read_pickle(
            MONTHLY_CACHE_FILE
        )

        if not isinstance(
            monthly,
            pd.DataFrame,
        ):
            return None

        if monthly.empty:
            return None

        return monthly

    except Exception:

        return None


# ============================================================
# MONTHLY FEATURE ENGINE
# ============================================================

def calculate_monthly_features(
    monthly: pd.DataFrame,
) -> pd.DataFrame:

    """
    Calculate the locked production features.

    Momentum:
        9-month price momentum

    Breakout:
        Current month close relative to the highest
        high of the previous 6 completed months.

    Volume:
        Current month volume relative to the average
        of the previous 3 completed months.

    The current month is therefore evaluated only after
    completion.
    """

    data = monthly.copy()

    data = data.sort_values(
        [
            "Symbol",
            "Month",
        ]
    )

    # --------------------------------------------------------
    # Momentum
    # --------------------------------------------------------

    data["Momentum_9M"] = (
        data
        .groupby("Symbol")["Close"]
        .transform(
            lambda x: (
                x / x.shift(MOMENTUM_MONTHS) - 1.0
            )
        )
    )

    # --------------------------------------------------------
    # Breakout
    # --------------------------------------------------------

    prior_high = (
        data
        .groupby("Symbol")["High"]
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
        data["Close"] / prior_high - 1.0
    )

    # --------------------------------------------------------
    # Volume confirmation
    # --------------------------------------------------------

    prior_volume_average = (
        data
        .groupby("Symbol")["Volume"]
        .transform(
            lambda x:
            x.shift(1)
            .rolling(
                3,
                min_periods=3,
            )
            .mean()
        )
    )

    data["Volume_Ratio"] = (
        data["Volume"]
        / prior_volume_average
    )

    data["Volume_Pass"] = (
        data["Volume_Ratio"]
        >= VOLUME_MULTIPLIER
    )

    # --------------------------------------------------------
    # Combined score
    # --------------------------------------------------------

    data["Combined_Score"] = (
        data["Momentum_9M"].fillna(0.0)
        + data["Breakout_6M"].fillna(0.0)
    )

    return data


# ============================================================
# SIGNAL GENERATION
# ============================================================

def generate_current_signal(
    features: pd.DataFrame,
) -> Tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.Timestamp,
]:

    if features.empty:

        raise RuntimeError(
            "Feature DataFrame is empty."
        )

    latest_month = (
        features["Month"]
        .max()
    )

    current = features.loc[
        features["Month"] == latest_month
    ].copy()

    if current.empty:

        raise RuntimeError(
            "No stocks found for latest completed month."
        )

    # --------------------------------------------------------
    # Basic eligibility
    # --------------------------------------------------------

    current = current[
        current["Close"].notna()
    ].copy()

    current = current[
        current["Momentum_9M"].notna()
        & current["Breakout_6M"].notna()
        & current["Volume_Ratio"].notna()
    ].copy()

    # --------------------------------------------------------
    # Volume filter
    # --------------------------------------------------------

    current = current[
        current["Volume_Ratio"]
        >= VOLUME_MULTIPLIER
    ].copy()

    # --------------------------------------------------------
    # Ranking
    # --------------------------------------------------------

    current = current.sort_values(
        [
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
    )

    current = current.reset_index(
        drop=True
    )

    current["Research_Rank"] = (
        np.arange(
            1,
            len(current) + 1,
        )
    )

    top30 = current.head(
        TOP_RESEARCH_STOCKS
    ).copy()

    top10 = current.head(
        TOP_PORTFOLIO_STOCKS
    ).copy()

    # --------------------------------------------------------
    # Portfolio allocation
    # --------------------------------------------------------

    if not top10.empty:

        position_weight = (
            1.0 / len(top10)
        )

        position_capital = (
            TOTAL_CAPITAL
            / len(top10)
        )

        top10["Target_Weight"] = (
            position_weight
        )

        top10["Target_Capital"] = (
            position_capital
        )

    else:

        top10["Target_Weight"] = []
        top10["Target_Capital"] = []

    return (
        current,
        top10,
        latest_month,
    )


# ============================================================
# REGIME MONITOR
# ============================================================

def calculate_regime_monitor(
    monthly: pd.DataFrame,
) -> Dict[str, Any]:

    """
    Optional market regime monitor.

    IMPORTANT:

    This is NOT part of the locked R0 strategy.

    It exists only as a diagnostic monitor.

    Because the existing project data is primarily stock-level,
    this function uses the cross-sectional median stock close
    as a broad market proxy.

    Do not use it as an active portfolio filter unless
    independently backtested.
    """

    pivot = monthly.pivot_table(
        index="Month",
        columns="Symbol",
        values="Close",
        aggfunc="last",
    )

    if pivot.empty:

        return {
            "regime": "UNKNOWN",
            "market_proxy": np.nan,
            "ma_10m": np.nan,
            "ma_10m_previous": np.nan,
        }

    market_proxy = (
        pivot.median(
            axis=1,
            skipna=True,
        )
    )

    ma_10m = (
        market_proxy
        .rolling(
            10,
            min_periods=10,
        )
        .mean()
    )

    if len(ma_10m.dropna()) < 2:

        return {
            "regime": "UNKNOWN",
            "market_proxy": safe_float(
                market_proxy.iloc[-1]
            ),
            "ma_10m": np.nan,
            "ma_10m_previous": np.nan,
        }

    current_proxy = (
        market_proxy.iloc[-1]
    )

    current_ma = (
        ma_10m.iloc[-1]
    )

    previous_ma = (
        ma_10m.iloc[-2]
    )

    if (
        pd.isna(current_proxy)
        or pd.isna(current_ma)
        or pd.isna(previous_ma)
    ):

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
        "regime": regime,
        "market_proxy": safe_float(
            current_proxy
        ),
        "ma_10m": safe_float(
            current_ma
        ),
        "ma_10m_previous": safe_float(
            previous_ma
        ),
    }


# ============================================================
# CURRENT HOLDINGS
# ============================================================

def load_current_holdings() -> List[str]:

    """
    Read current holdings from:

        results/current_holdings.csv

    Expected column:

        Symbol

    If the file does not exist, the portfolio is assumed to
    have no existing positions.
    """

    if not HOLDINGS_FILE.exists():

        return []

    try:

        holdings = pd.read_csv(
            HOLDINGS_FILE
        )

    except Exception as exc:

        print(
            "WARNING: Could not read current holdings."
        )

        print(
            f"Reason: {exc}"
        )

        return []

    if holdings.empty:

        return []

    symbol_column = None

    for candidate in [
        "Symbol",
        "symbol",
        "Ticker",
        "ticker",
    ]:

        if candidate in holdings.columns:

            symbol_column = candidate
            break

    if symbol_column is None:

        print(
            "WARNING: current_holdings.csv has no "
            "Symbol column."
        )

        return []

    symbols = []

    for symbol in holdings[
        symbol_column
    ].tolist():

        cleaned = clean_symbol(symbol)

        if cleaned:
            symbols.append(cleaned)

    return sorted(
        set(symbols)
    )


# ============================================================
# ORDER GENERATION
# ============================================================

def generate_orders(
    top10: pd.DataFrame,
    current_holdings: Sequence[str],
) -> pd.DataFrame:

    """
    Generate monthly rebalance instructions.

    Rules:

        Current holding still in Top 10
            -> HOLD

        Current holding no longer in Top 10
            -> SELL

        New Top 10 stock
            -> BUY

    Equal weight portfolio.
    """

    target_symbols = [
        clean_symbol(x)
        for x in top10["Symbol"].tolist()
    ]

    current_symbols = [
        clean_symbol(x)
        for x in current_holdings
    ]

    target_set = set(target_symbols)
    current_set = set(current_symbols)

    rows = []

    # --------------------------------------------------------
    # SELL
    # --------------------------------------------------------

    for symbol in sorted(
        current_set - target_set
    ):

        rows.append(
            {
                "Symbol": symbol,
                "Action": "SELL",
                "Target_Weight": 0.0,
                "Target_Capital": 0.0,
                "Reason": "Dropped from Top 10",
            }
        )

    # --------------------------------------------------------
    # HOLD / BUY
    # --------------------------------------------------------

    for _, row in top10.iterrows():

        symbol = clean_symbol(
            row["Symbol"]
        )

        if symbol in current_set:

            action = "HOLD"
            reason = "Remains in Top 10"

        else:

            action = "BUY"
            reason = "New Top 10 entrant"

        rows.append(
            {
                "Symbol": symbol,
                "Action": action,
                "Target_Weight": safe_float(
                    row.get(
                        "Target_Weight",
                        np.nan,
                    )
                ),
                "Target_Capital": safe_float(
                    row.get(
                        "Target_Capital",
                        np.nan,
                    )
                ),
                "Reason": reason,
            }
        )

    if not rows:

        return pd.DataFrame(
            columns=[
                "Symbol",
                "Action",
                "Target_Weight",
                "Target_Capital",
                "Reason",
            ]
        )

    orders = pd.DataFrame(rows)

    action_order = {
        "SELL": 1,
        "BUY": 2,
        "HOLD": 3,
    }

    orders["_order"] = (
        orders["Action"]
        .map(action_order)
        .fillna(99)
    )

    orders = orders.sort_values(
        [
            "_order",
            "Symbol",
        ]
    )

    orders = orders.drop(
        columns="_order"
    )

    orders = orders.reset_index(
        drop=True
    )

    return orders


# ============================================================
# SAVE REPORTS
# ============================================================

def save_csv_reports(
    ranked: pd.DataFrame,
    top10: pd.DataFrame,
    orders: pd.DataFrame,
    signal_month: pd.Timestamp,
    regime: Dict[str, Any],
    runtime_seconds: float,
) -> None:

    # --------------------------------------------------------
    # Current signal
    # --------------------------------------------------------

    signal = top10.copy()

    signal["Signal_Month"] = signal_month

    signal["Strategy"] = STRATEGY_NAME

    signal["Execution"] = (
        "Next trading session"
    )

    signal["Regime_Monitor"] = (
        regime.get("regime")
    )

    signal["Bear_Overlay_Enabled"] = (
        ENABLE_BEAR_OVERLAY
    )

    signal.to_csv(
        CURRENT_SIGNAL_FILE,
        index=False,
    )

    # --------------------------------------------------------
    # Top 30
    # --------------------------------------------------------

    top30 = ranked.head(
        TOP_RESEARCH_STOCKS
    ).copy()

    top30["Signal_Month"] = signal_month

    top30["Strategy"] = STRATEGY_NAME

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
    # Run summary
    # --------------------------------------------------------

    summary = pd.DataFrame(
        [
            {
                "Run_Timestamp": datetime.now().isoformat(
                    timespec="seconds"
                ),
                "Strategy": STRATEGY_NAME,
                "Signal_Month": signal_month,
                "Requested_Universe": len(
                    ranked["Symbol"].unique()
                ),
                "Eligible_Stocks": len(ranked),
                "Portfolio_Size": len(top10),
                "Total_Capital": TOTAL_CAPITAL,
                "Capital_Per_Position": (
                    TOTAL_CAPITAL / len(top10)
                    if len(top10) > 0
                    else 0.0
                ),
                "Regime_Monitor": regime.get(
                    "regime"
                ),
                "Bear_Overlay_Enabled": (
                    ENABLE_BEAR_OVERLAY
                ),
                "Runtime_Seconds": runtime_seconds,
                "Runtime": format_seconds(
                    runtime_seconds
                ),
            }
        ]
    )

    summary.to_csv(
        RUN_SUMMARY_FILE,
        index=False,
    )


def save_excel_report(
    ranked: pd.DataFrame,
    top10: pd.DataFrame,
    orders: pd.DataFrame,
    signal_month: pd.Timestamp,
    regime: Dict[str, Any],
    runtime_seconds: float,
) -> None:

    if not OPENPYXL_AVAILABLE:

        print(
            "WARNING: openpyxl not installed."
        )

        print(
            "Excel report skipped."
        )

        return

    try:

        with pd.ExcelWriter(
            EXCEL_FILE,
            engine="openpyxl",
        ) as writer:

            # ------------------------------------------------
            # Signal
            # ------------------------------------------------

            signal = top10.copy()

            signal["Signal_Month"] = signal_month

            signal["Strategy"] = STRATEGY_NAME

            signal["Execution"] = (
                "Next trading session"
            )

            signal["Regime_Monitor"] = (
                regime.get("regime")
            )

            signal["Bear_Overlay_Enabled"] = (
                ENABLE_BEAR_OVERLAY
            )

            signal.to_excel(
                writer,
                sheet_name="LIVE_SIGNAL",
                index=False,
            )

            # ------------------------------------------------
            # Top 30
            # ------------------------------------------------

            top30 = ranked.head(
                TOP_RESEARCH_STOCKS
            ).copy()

            top30.to_excel(
                writer,
                sheet_name="TOP_30",
                index=False,
            )

            # ------------------------------------------------
            # Orders
            # ------------------------------------------------

            orders.to_excel(
                writer,
                sheet_name="ORDERS",
                index=False,
            )

            # ------------------------------------------------
            # Summary
            # ------------------------------------------------

            summary = pd.DataFrame(
                [
                    {
                        "Run Timestamp": datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        "Strategy": STRATEGY_NAME,
                        "Signal Month": signal_month,
                        "Universe": len(
                            ranked["Symbol"].unique()
                        ),
                        "Eligible Stocks": len(
                            ranked
                        ),
                        "Portfolio Size": len(
                            top10
                        ),
                        "Capital": TOTAL_CAPITAL,
                        "Capital / Position": (
                            TOTAL_CAPITAL
                            / len(top10)
                            if len(top10) > 0
                            else 0.0
                        ),
                        "Regime Monitor": (
                            regime.get("regime")
                        ),
                        "Bear Overlay Enabled": (
                            ENABLE_BEAR_OVERLAY
                        ),
                        "Runtime": format_seconds(
                            runtime_seconds
                        ),
                    }
                ]
            )

            summary.to_excel(
                writer,
                sheet_name="RUN_SUMMARY",
                index=False,
            )

            # ------------------------------------------------
            # Strategy rules
            # ------------------------------------------------

            rules = pd.DataFrame(
                {
                    "Parameter": [
                        "Strategy",
                        "Momentum",
                        "Skip Month",
                        "Breakout",
                        "Volume",
                        "Trend Filter",
                        "Regime Filter",
                        "Portfolio Size",
                        "Rebalance",
                        "Capital",
                        "Execution",
                    ],
                    "Value": [
                        STRATEGY_NAME,
                        "9 months",
                        "0 months",
                        "6 months",
                        ">= 1.50x reference",
                        "None",
                        "None (R0)",
                        "Top 10",
                        "Monthly",
                        "Rs. 100,000",
                        "Next trading session",
                    ],
                }
            )

            rules.to_excel(
                writer,
                sheet_name="STRATEGY_RULES",
                index=False,
            )

    except Exception as exc:

        print(
            "WARNING: Excel report could not be created."
        )

        print(
            f"Reason: {exc}"
        )


# ============================================================
# DISPLAY SIGNAL
# ============================================================

def display_signal(
    ranked: pd.DataFrame,
    top10: pd.DataFrame,
    orders: pd.DataFrame,
    signal_month: pd.Timestamp,
    regime: Dict[str, Any],
) -> None:

    print()
    print(LINE)
    print("CURRENT MONTHLY SIGNAL")
    print(LINE)

    print(
        f"Signal month               : "
        f"{signal_month.strftime('%Y-%m-%d')}"
    )

    print(
        f"Execution                  : "
        f"Next trading session"
    )

    print(
        f"Strategy                   : "
        f"{STRATEGY_NAME}"
    )

    print(
        f"Universe                   : "
        f"{ranked['Symbol'].nunique()}"
    )

    print(
        f"Eligible stocks            : "
        f"{len(ranked)}"
    )

    print(
        f"Regime monitor             : "
        f"{regime.get('regime')}"
    )

    print(
        f"Bear overlay enabled       : "
        f"{ENABLE_BEAR_OVERLAY}"
    )

    # --------------------------------------------------------
    # Top 30
    # --------------------------------------------------------

    print()
    print(LINE)
    print(
        f"TOP {TOP_RESEARCH_STOCKS} RESEARCH STOCKS"
    )
    print(LINE)

    display_columns = [
        "Research_Rank",
        "Symbol",
        "Close",
        "Momentum_9M",
        "Breakout_6M",
        "Volume_Ratio",
        "Combined_Score",
    ]

    available_columns = [
        col
        for col in display_columns
        if col in ranked.columns
    ]

    display_top30 = ranked.head(
        TOP_RESEARCH_STOCKS
    )[available_columns].copy()

    if not display_top30.empty:

        print(
            display_top30.to_string(
                index=False,
                formatters={
                    "Close": (
                        lambda x:
                        f"{x:,.2f}"
                    ),
                    "Momentum_9M": (
                        lambda x:
                        f"{x * 100:.2f}%"
                    ),
                    "Breakout_6M": (
                        lambda x:
                        f"{x * 100:.2f}%"
                    ),
                    "Volume_Ratio": (
                        lambda x:
                        f"{x:.2f}x"
                    ),
                    "Combined_Score": (
                        lambda x:
                        f"{x * 100:.2f}%"
                    ),
                },
            )
        )

    # --------------------------------------------------------
    # Top 10
    # --------------------------------------------------------

    print()
    print(LINE)
    print(
        f"PORTFOLIO — TOP {TOP_PORTFOLIO_STOCKS}"
    )
    print(LINE)

    if top10.empty:

        print(
            "NO ELIGIBLE STOCKS."
        )

        print(
            "Portfolio remains 100% CASH."
        )

    else:

        print(
            f"Total capital             : "
            f"Rs. {TOTAL_CAPITAL:,.2f}"
        )

        print(
            f"Position size             : "
            f"Rs. {TOTAL_CAPITAL / len(top10):,.2f}"
        )

        print()

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

        portfolio_columns = [
            col
            for col in portfolio_columns
            if col in top10.columns
        ]

        print(
            top10[
                portfolio_columns
            ].to_string(
                index=False,
                formatters={
                    "Close": (
                        lambda x:
                        f"{x:,.2f}"
                    ),
                    "Momentum_9M": (
                        lambda x:
                        f"{x * 100:.2f}%"
                    ),
                    "Breakout_6M": (
                        lambda x:
                        f"{x * 100:.2f}%"
                    ),
                    "Volume_Ratio": (
                        lambda x:
                        f"{x:.2f}x"
                    ),
                    "Combined_Score": (
                        lambda x:
                        f"{x * 100:.2f}%"
                    ),
                    "Target_Capital": (
                        lambda x:
                        f"Rs. {x:,.2f}"
                    ),
                },
            )
        )

    # --------------------------------------------------------
    # Orders
    # --------------------------------------------------------

    print()
    print(LINE)
    print("REBALANCE ORDERS")
    print(LINE)

    if orders.empty:

        print(
            "No orders."
        )

    else:

        print(
            orders.to_string(
                index=False,
                formatters={
                    "Target_Weight": (
                        lambda x:
                        f"{x * 100:.2f}%"
                    ),
                    "Target_Capital": (
                        lambda x:
                        f"Rs. {x:,.2f}"
                    ),
                },
            )
        )

    print()
    print(LINE)


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    overall_timer = Timer()

    print_header()

    run_timestamp = datetime.now()

    print(
        f"Run timestamp              : "
        f"{run_timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    # ========================================================
    # 1. REFRESH UNIVERSE
    # ========================================================

    stage_timer = Timer()

    print_stage(
        "STAGE 1 — REFRESH NIFTY 500 UNIVERSE"
    )

    refresh_universe_if_available()

    print(
        f"Universe refresh time      : "
        f"{format_seconds(stage_timer.elapsed())}"
    )

    # ========================================================
    # 2. LOAD UNIVERSE
    # ========================================================

    stage_timer = Timer()

    print_stage(
        "STAGE 2 — LOAD UNIVERSE"
    )

    symbols = load_universe_symbols()

    print(
        f"Universe loading time      : "
        f"{format_seconds(stage_timer.elapsed())}"
    )

    # ========================================================
    # 3. LOAD DAILY MARKET DATA
    # ========================================================

    stage_timer = Timer()

    print_stage(
        "STAGE 3 — DOWNLOAD DAILY MARKET DATA"
    )

    daily_data, valid_symbols = (
        load_daily_market_data(
            symbols
        )
    )

    print(
        f"Daily market data          : "
        f"{format_seconds(stage_timer.elapsed())}"
    )

    # ========================================================
    # 4. CONVERT TO MONTHLY
    # ========================================================

    stage_timer = Timer()

    print_stage(
        "STAGE 4 — CONVERT TO COMPLETED MONTHLY BARS"
    )

    monthly = (
        convert_daily_to_completed_monthly(
            daily_data
        )
    )

    # --------------------------------------------------------
    # Validate months
    # --------------------------------------------------------

    completed_months = (
        monthly["Month"]
        .drop_duplicates()
        .sort_values()
    )

    number_of_months = len(
        completed_months
    )

    usable_symbols = (
        monthly
        .groupby("Symbol")["Month"]
        .nunique()
    )

    usable_symbol_count = int(
        (
            usable_symbols
            >= MIN_MONTHS_REQUIRED
        ).sum()
    )

    print(
        f"Completed monthly months  : "
        f"{number_of_months}"
    )

    print(
        f"Usable monthly symbols     : "
        f"{usable_symbol_count}"
    )

    if number_of_months < MIN_MONTHS_REQUIRED:

        raise RuntimeError(
            f"Only {number_of_months} completed "
            f"months available.\n"
            f"Minimum required: "
            f"{MIN_MONTHS_REQUIRED}"
        )

    if usable_symbol_count == 0:

        raise RuntimeError(
            "No symbols have enough monthly history."
        )

    save_monthly_cache(
        monthly
    )

    print(
        f"Monthly conversion         : "
        f"{format_seconds(stage_timer.elapsed())}"
    )

    # ========================================================
    # 5. FEATURE ENGINE
    # ========================================================

    stage_timer = Timer()

    print_stage(
        "STAGE 5 — CALCULATE MOMENTUM + BREAKOUT FEATURES"
    )

    features = calculate_monthly_features(
        monthly
    )

    print(
        f"Feature engine             : "
        f"{format_seconds(stage_timer.elapsed())}"
    )

    # ========================================================
    # 6. CURRENT SIGNAL
    # ========================================================

    stage_timer = Timer()

    print_stage(
        "STAGE 6 — GENERATE CURRENT MONTHLY SIGNAL"
    )

    ranked, top10, signal_month = (
        generate_current_signal(
            features
        )
    )

    if ranked.empty:

        raise RuntimeError(
            "No stocks passed the production filters."
        )

    print(
        f"Signal generation          : "
        f"{format_seconds(stage_timer.elapsed())}"
    )

    # ========================================================
    # 7. REGIME MONITOR
    # ========================================================

    stage_timer = Timer()

    print_stage(
        "STAGE 7 — CALCULATE REGIME MONITOR"
    )

    regime = calculate_regime_monitor(
        monthly
    )

    print(
        f"Regime monitor             : "
        f"{regime.get('regime')}"
    )

    print(
        f"Market proxy               : "
        f"{regime.get('market_proxy')}"
    )

    print(
        f"10M MA                     : "
        f"{regime.get('ma_10m')}"
    )

    print(
        f"10M MA previous            : "
        f"{regime.get('ma_10m_previous')}"
    )

    print(
        f"Regime calculation         : "
        f"{format_seconds(stage_timer.elapsed())}"
    )

    # ========================================================
    # 8. CURRENT HOLDINGS
    # ========================================================

    stage_timer = Timer()

    print_stage(
        "STAGE 8 — LOAD CURRENT HOLDINGS"
    )

    current_holdings = (
        load_current_holdings()
    )

    print(
        f"Current holdings           : "
        f"{len(current_holdings)}"
    )

    if current_holdings:

        print(
            "Existing positions:"
        )

        for symbol in current_holdings:
            print(
                f"    {symbol}"
            )

    else:

        print(
            "No current holdings file found."
        )

        print(
            "Portfolio treated as empty."
        )

    print(
        f"Holdings loading           : "
        f"{format_seconds(stage_timer.elapsed())}"
    )

    # ========================================================
    # 9. GENERATE ORDERS
    # ========================================================

    stage_timer = Timer()

    print_stage(
        "STAGE 9 — GENERATE REBALANCE ORDERS"
    )

    orders = generate_orders(
        top10,
        current_holdings,
    )

    print(
        f"Order generation           : "
        f"{format_seconds(stage_timer.elapsed())}"
    )

    # ========================================================
    # 10. SAVE REPORTS
    # ========================================================

    stage_timer = Timer()

    print_stage(
        "STAGE 10 — SAVE REPORTS"
    )

    save_csv_reports(
        ranked=ranked,
        top10=top10,
        orders=orders,
        signal_month=signal_month,
        regime=regime,
        runtime_seconds=overall_timer.elapsed(),
    )

    save_excel_report(
        ranked=ranked,
        top10=top10,
        orders=orders,
        signal_month=signal_month,
        regime=regime,
        runtime_seconds=overall_timer.elapsed(),
    )

    print(
        f"Report generation          : "
        f"{format_seconds(stage_timer.elapsed())}"
    )

    # ========================================================
    # 11. DISPLAY FINAL SIGNAL
    # ========================================================

    display_signal(
        ranked=ranked,
        top10=top10,
        orders=orders,
        signal_month=signal_month,
        regime=regime,
    )

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    total_runtime = (
        overall_timer.elapsed()
    )

    print()
    print(LINE)
    print("RUN COMPLETE")
    print(LINE)

    print(
        f"Strategy                   : "
        f"{STRATEGY_NAME}"
    )

    print(
        f"Signal month               : "
        f"{signal_month.strftime('%Y-%m-%d')}"
    )

    print(
        f"Universe                   : "
        f"{len(symbols)}"
    )

    print(
        f"Valid daily symbols        : "
        f"{len(valid_symbols)}"
    )

    print(
        f"Usable monthly symbols     : "
        f"{usable_symbol_count}"
    )

    print(
        f"Completed months           : "
        f"{number_of_months}"
    )

    print(
        f"Eligible stocks            : "
        f"{len(ranked)}"
    )

    print(
        f"Portfolio stocks           : "
        f"{len(top10)}"
    )

    print(
        f"Regime monitor             : "
        f"{regime.get('regime')}"
    )

    print(
        f"Bear overlay               : "
        f"{'ON' if ENABLE_BEAR_OVERLAY else 'OFF'}"
    )

    print(
        f"Total runtime              : "
        f"{format_seconds(total_runtime)}"
    )

    print()
    print("Output files:")
    print(
        f"    {CURRENT_SIGNAL_FILE}"
    )
    print(
        f"    {TOP30_FILE}"
    )
    print(
        f"    {ORDERS_FILE}"
    )
    print(
        f"    {RUN_SUMMARY_FILE}"
    )

    if OPENPYXL_AVAILABLE:
        print(
            f"    {EXCEL_FILE}"
        )

    print()
    print(
        "IMPORTANT:"
    )

    print(
        "    This production engine does NOT run the "
        "strategy grid."
    )

    print(
        "    It uses the locked strategy configuration."
    )

    print(
        "    Bear overlay remains OFF because the locked "
        "strategy is R0."
    )

    print()
    print(LINE)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print()
        print(LINE)
        print(
            "PROGRAM INTERRUPTED BY USER"
        )
        print(LINE)
        sys.exit(130)

    except Exception as exc:

        print()
        print(LINE)
        print(
            "PROGRAM FAILED"
        )
        print(LINE)

        print(
            f"Error: {exc}"
        )

        print()

        import traceback

        traceback.print_exc()

        print()
        print(
            "Check the error above before proceeding."
        )

        print(LINE)

        sys.exit(1)