"""
================================================================================
MomentumPortfolioLab — MONTHLY MOMENTUM PORTFOLIO DECISION ENGINE
================================================================================

Purpose
-------
Run this program once every weekend.

The engine:
1. Refreshes the current Nifty 500 universe using the EXISTING trade_data.py.
2. Downloads recent OHLCV data.
3. Calculates the SAME momentum methodology used in backtest.py.
4. Uses the latest COMPLETED MONTH-END for portfolio selection.
5. Uses the latest completed trading day for current prices and market breadth.
6. Compares the new official monthly portfolio with the saved portfolio state.
7. Produces BUY / HOLD / SELL / REPLACEMENT actions.
8. Calculates Nifty 500 EMA market breadth.
9. Displays Sector, Industry and Market Cap for the selected portfolio.
10. Saves all outputs under results/.

IMPORTANT
---------
trade_data.py is NOT modified.
Only refresh_nifty500_universe() is called from it.
Its main() function is deliberately NOT executed.

LIVE STRATEGY
-------------
Top N                       : 20
12-1 Momentum               : 50%
6-Month Momentum            : 50%
Volatility adjustment       : Yes
Rebalance                   : Monthly
Weekend execution           : Monitoring / action check
Fundamentals                : No
Market regime filter        : No
Transaction cost assumption : 15 bps in research

PORTFOLIO LOGIC
---------------
The backtest is monthly.

Therefore:
- Do NOT replace stocks every weekend merely because their daily rank changes.
- The official portfolio changes only when a new completed month-end signal exists.
- During the month, existing holdings remain HOLD.
- At a new monthly rebalance:

      Existing stock remains Top 20 -> HOLD
      Existing stock leaves Top 20    -> SELL
      New stock enters Top 20         -> BUY
      SELL + BUY together             -> REPLACEMENT

FIRST RUN
---------
If no portfolio state exists:
- All current Top 20 stocks are treated as BUY.
- The state file is created.
- Subsequent weekend runs compare against that state.

MARKET BREADTH
--------------
20D EMA
50D EMA
200D EMA

Breadth classification:
    < 50%       = Low
    50% to <70% = Medium
    >= 70%      = High

The breadth section is informational only.
It does NOT alter the tested momentum portfolio.

================================================================================
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf


# =============================================================================
# PATHS
# =============================================================================

PROJECT_DIR = Path(__file__).resolve().parent
RESULTS_DIR = PROJECT_DIR / "results"

TRADE_DATA_FILE = PROJECT_DIR / "trade_data.py"
UNIVERSE_FILE = PROJECT_DIR / "universe.py"

STATE_FILE = RESULTS_DIR / "momentum_portfolio_state.json"
SIGNAL_FILE = RESULTS_DIR / "momentum_portfolio_signal.csv"
ACTIONS_FILE = RESULTS_DIR / "momentum_portfolio_actions.csv"
BREADTH_FILE = RESULTS_DIR / "momentum_portfolio_market_breadth.csv"
BREADTH_DETAILS_FILE = (
    RESULTS_DIR / "momentum_portfolio_market_breadth_details.csv"
)
METADATA_CACHE_FILE = (
    RESULTS_DIR / "momentum_portfolio_metadata_cache.json"
)


# =============================================================================
# STRATEGY SETTINGS — LOCKED TO BACKTEST
# =============================================================================

TOP_N = 20

MOMENTUM_12M_WEIGHT = 0.50
MOMENTUM_6M_WEIGHT = 0.50

VOL_LOOKBACK_DAYS = 252

# Same research assumption.
TRANSACTION_COST_BPS = 10.0
SLIPPAGE_BPS = 5.0
TOTAL_COST_BPS = TRANSACTION_COST_BPS + SLIPPAGE_BPS

# Minimum daily observations required for reliable EMA calculations.
MIN_DAILY_OBSERVATIONS = 50

# Recent data window is enough for:
# - 252-day volatility
# - 13 month-end observations
# - EMA 200
#
# 3 years gives comfortable buffer.
DOWNLOAD_PERIOD = "3y"


# =============================================================================
# DISPLAY SETTINGS
# =============================================================================

LINE = "=" * 96


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def print_header(title: str) -> None:
    print()
    print(LINE)
    print(title)
    print(LINE)


def safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None

        if isinstance(value, float) and math.isnan(value):
            return None

        result = float(value)

        if not math.isfinite(result):
            return None

        return result

    except Exception:
        return None


def format_number(
    value: Any,
    decimals: int = 2
) -> str:

    number = safe_float(value)

    if number is None:
        return "-"

    return f"{number:,.{decimals}f}"


def format_indian_integer(value: Any) -> str:
    """
    Indian number grouping.

    Example:
        111225678 -> 11,12,25,678
    """

    number = safe_float(value)

    if number is None:
        return "-"

    number = int(round(number))

    sign = ""

    if number < 0:
        sign = "-"
        number = abs(number)

    text = str(number)

    if len(text) <= 3:
        return sign + text

    last_three = text[-3:]
    remaining = text[:-3]

    groups = []

    while len(remaining) > 2:
        groups.insert(0, remaining[-2:])
        remaining = remaining[:-2]

    if remaining:
        groups.insert(0, remaining)

    return sign + ",".join(
        groups + [last_three]
    )


def format_market_cap_crore(
    market_cap_rupees: Any
) -> str:
    """
    Convert rupee market cap into ₹ Cr using Indian grouping.

    1 Crore = ₹10,000,000
    """

    value = safe_float(market_cap_rupees)

    if value is None:
        return "-"

    crore = value / 10_000_000

    return (
        f"{format_indian_integer(crore)} Cr"
    )


def normalize_symbol(symbol: str) -> str:
    symbol = str(symbol).strip().upper()

    if not symbol.endswith(".NS"):
        symbol += ".NS"

    return symbol


# =============================================================================
# DATE HANDLING
# =============================================================================

def get_program_run_timestamp() -> pd.Timestamp:
    """
    Use the machine's current local date/time.

    This is also used as the hard upper bound for downloaded market data.
    """

    return pd.Timestamp.now()


PROGRAM_RUN_TIMESTAMP = get_program_run_timestamp()
PROGRAM_RUN_DATE = PROGRAM_RUN_TIMESTAMP.normalize()


# =============================================================================
# TRADE DATA IMPORT
# =============================================================================

def load_trade_data_module():
    """
    Dynamically import trade_data.py without executing its main().

    This prevents the Unicode / console issues caused by executing the
    large trade_data.py script directly.
    """

    if not TRADE_DATA_FILE.exists():
        raise FileNotFoundError(
            f"trade_data.py not found:\n{TRADE_DATA_FILE}"
        )

    spec = importlib.util.spec_from_file_location(
        "momentum_portfolio_trade_data",
        TRADE_DATA_FILE
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            "Could not create import specification for trade_data.py."
        )

    module = importlib.util.module_from_spec(spec)

    sys.modules[
        "momentum_portfolio_trade_data"
    ] = module

    spec.loader.exec_module(module)

    return module


def refresh_universe() -> list[str]:

    print_header(
        "STEP 1 — BUILDING / REFRESHING NIFTY 500 UNIVERSE"
    )

    print(
        f"trade_data.py : {TRADE_DATA_FILE}"
    )

    print()
    print(
        "Calling existing refresh_nifty500_universe()..."
    )

    module = load_trade_data_module()

    if not hasattr(
        module,
        "refresh_nifty500_universe"
    ):
        raise AttributeError(
            "trade_data.py does not contain "
            "refresh_nifty500_universe()."
        )

    symbols = module.refresh_nifty500_universe()

    symbols = [
        normalize_symbol(symbol)
        for symbol in symbols
        if str(symbol).strip()
    ]

    symbols = sorted(
        set(symbols)
    )

    print()
    print(
        f"Universe created : {UNIVERSE_FILE}"
    )

    print(
        f"Symbols returned : {len(symbols)}"
    )

    return symbols


def load_generated_universe() -> list[str]:

    print_header(
        "STEP 2 — LOADING GENERATED UNIVERSE"
    )

    if not UNIVERSE_FILE.exists():
        raise FileNotFoundError(
            f"Generated universe.py not found:\n"
            f"{UNIVERSE_FILE}"
        )

    namespace: dict[str, Any] = {}

    with open(
        UNIVERSE_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        source = file.read()

    exec(
        source,
        namespace
    )

    symbols = namespace.get(
        "symbols"
    )

    if not isinstance(
        symbols,
        list
    ):
        raise ValueError(
            "universe.py does not contain "
            "a valid symbols list."
        )

    symbols = [
        normalize_symbol(symbol)
        for symbol in symbols
        if str(symbol).strip()
    ]

    symbols = sorted(
        set(symbols)
    )

    print(
        f"Nifty 500 universe : "
        f"{len(symbols)} symbols"
    )

    return symbols


# =============================================================================
# HISTORICAL OHLCV DOWNLOAD
# =============================================================================

def download_market_data(
    symbols: list[str]
) -> tuple[pd.DataFrame, list[str]]:

    print_header(
        "STEP 3 — DOWNLOADING RECENT OHLCV"
    )

    print(
        f"Symbols       : {len(symbols)}"
    )

    print(
        f"Download      : {DOWNLOAD_PERIOD}"
    )

    print(
        f"Program date  : "
        f"{PROGRAM_RUN_DATE.date()}"
    )

    start_time = time.perf_counter()

    data = yf.download(
        symbols,
        period=DOWNLOAD_PERIOD,
        interval="1d",
        auto_adjust=False,
        progress=True,
        group_by="column",
        threads=True,
    )

    elapsed = (
        time.perf_counter()
        - start_time
    )

    if data is None or data.empty:
        raise RuntimeError(
            "yfinance returned no market data."
        )

    # -------------------------------------------------------------------------
    # HARD FUTURE-DATE PROTECTION
    # -------------------------------------------------------------------------

    data = data.copy()

    data.index = pd.to_datetime(
        data.index
    )

    if getattr(
        data.index,
        "tz",
        None
    ) is not None:

        data.index = (
            data.index
            .tz_localize(None)
        )

    before_filter_rows = len(data)

    data = data.loc[
        data.index.normalize()
        <= PROGRAM_RUN_DATE
    ].copy()

    removed_future_rows = (
        before_filter_rows
        - len(data)
    )

    if removed_future_rows > 0:

        print()

        print(
            f"Future-dated rows ignored : "
            f"{removed_future_rows}"
        )

    # -------------------------------------------------------------------------
    # VALID SYMBOLS
    # -------------------------------------------------------------------------

    valid_symbols: list[str] = []
    invalid_symbols: list[str] = []

    for symbol in symbols:

        try:

            close_prices = (
                data["Close"][symbol]
            )

            if close_prices.dropna().empty:

                invalid_symbols.append(
                    symbol
                )

            else:

                valid_symbols.append(
                    symbol
                )

        except (
            KeyError,
            TypeError
        ):

            invalid_symbols.append(
                symbol
            )

    print()

    print(
        f"Download completed in "
        f"{elapsed:.1f} seconds."
    )

    print(
        f"Requested symbols : "
        f"{len(symbols)}"
    )

    print(
        f"Valid symbols     : "
        f"{len(valid_symbols)}"
    )

    print(
        f"Invalid symbols   : "
        f"{len(invalid_symbols)}"
    )

    if invalid_symbols:

        print()
        print(
            "First invalid symbols:"
        )

        for symbol in invalid_symbols[:20]:

            print(
                f"  {symbol}"
            )

    return (
        data,
        valid_symbols
    )


# =============================================================================
# DATAFRAME HELPERS
# =============================================================================

def get_close_frame(
    data: pd.DataFrame
) -> pd.DataFrame:

    if "Close" not in data.columns:
        raise RuntimeError(
            "Downloaded data does not contain "
            "Close prices."
        )

    close = data["Close"].copy()

    close = close.apply(
        pd.to_numeric,
        errors="coerce"
    )

    close = close.sort_index()

    return close


def get_volume_frame(
    data: pd.DataFrame
) -> pd.DataFrame:

    if "Volume" not in data.columns:

        return pd.DataFrame(
            index=data.index
        )

    volume = data["Volume"].copy()

    volume = volume.apply(
        pd.to_numeric,
        errors="coerce"
    )

    volume = volume.sort_index()

    return volume


# =============================================================================
# MOMENTUM CALCULATION
# =============================================================================

def calculate_monthly_strategy_scores(
    close: pd.DataFrame
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame
]:
    """
    SAME core logic as the backtest.

    For month T:

        12-1 momentum =
            P[T-1] / P[T-13] - 1

        6-month momentum =
            P[T-1] / P[T-7] - 1

    Volatility is based on daily returns and annualized over 252 days.

    The volatility used for a month-end signal is shifted so that the
    signal only uses information available before that month-end.

    Composite:
        50% risk-adjusted 12-1 momentum
        50% risk-adjusted 6M momentum

    Cross-sectional z-scores are used before combining the two factors.
    """

    print_header(
        "STEP 4 — CALCULATING MONTHLY MOMENTUM SCORES"
    )

    # -------------------------------------------------------------------------
    # Monthly close
    # -------------------------------------------------------------------------

    monthly_close = (
        close
        .resample("ME")
        .last()
    )

    # IMPORTANT:
    # Do not allow a future month-end into the live engine.

    monthly_close = monthly_close.loc[
        monthly_close.index.normalize()
        <= PROGRAM_RUN_DATE
    ]

    # -------------------------------------------------------------------------
    # Daily volatility
    # -------------------------------------------------------------------------

    daily_returns = (
        close.pct_change()
    )

    daily_volatility = (
        daily_returns
        .rolling(
            VOL_LOOKBACK_DAYS,
            min_periods=VOL_LOOKBACK_DAYS
        )
        .std()
        * np.sqrt(252.0)
    )

    # Month-end volatility.

    monthly_volatility = (
        daily_volatility
        .resample("ME")
        .last()
    )

    # Shift by one month.

    signal_volatility = (
        monthly_volatility.shift(1)
    )

    # -------------------------------------------------------------------------
    # Momentum
    # -------------------------------------------------------------------------

    momentum_12_1 = (
        monthly_close.shift(1)
        / monthly_close.shift(13)
        - 1.0
    )

    momentum_6m = (
        monthly_close.shift(1)
        / monthly_close.shift(7)
        - 1.0
    )

    # -------------------------------------------------------------------------
    # Risk adjustment
    # -------------------------------------------------------------------------

    safe_volatility = (
        signal_volatility
        .replace(0, np.nan)
    )

    risk_adj_12_1 = (
        momentum_12_1
        / safe_volatility
    )

    risk_adj_6m = (
        momentum_6m
        / safe_volatility
    )

    # -------------------------------------------------------------------------
    # Cross-sectional z-score
    # -------------------------------------------------------------------------

    def cross_sectional_zscore(
        row: pd.Series
    ) -> pd.Series:

        valid = row.dropna()

        if len(valid) < 2:

            return pd.Series(
                np.nan,
                index=row.index
            )

        mean = valid.mean()

        std = valid.std(
            ddof=0
        )

        if (
            std == 0
            or not np.isfinite(std)
        ):

            return pd.Series(
                np.nan,
                index=row.index
            )

        return (
            row - mean
        ) / std

    z12 = risk_adj_12_1.apply(
        cross_sectional_zscore,
        axis=1
    )

    z6 = risk_adj_6m.apply(
        cross_sectional_zscore,
        axis=1
    )

    composite = (
        MOMENTUM_12M_WEIGHT * z12
        + MOMENTUM_6M_WEIGHT * z6
    )

    print(
        f"Monthly observations : "
        f"{len(monthly_close)}"
    )

    if not monthly_close.empty:

        print(
            f"Monthly range        : "
            f"{monthly_close.index.min().date()} "
            f"→ "
            f"{monthly_close.index.max().date()}"
        )

    return (
        monthly_close,
        composite,
        signal_volatility
    )


# =============================================================================
# LATEST OFFICIAL MONTH-END SIGNAL
# =============================================================================

def get_latest_completed_month_end(
    monthly_close: pd.DataFrame
) -> pd.Timestamp:
    """
    Find the latest month-end that is actually completed as of the
    program's current date.

    This prevents the engine from using a future month-end.
    """

    if monthly_close.empty:

        raise RuntimeError(
            "No monthly market data available."
        )

    current_month_start = (
        PROGRAM_RUN_DATE
        .replace(day=1)
    )

    eligible = monthly_close.index[
        monthly_close.index
        < current_month_start
    ]

    if len(eligible) == 0:

        raise RuntimeError(
            "No completed month-end is available."
        )

    return eligible.max()


def build_latest_signal(
    close: pd.DataFrame,
    monthly_close: pd.DataFrame,
    composite: pd.DataFrame,
    signal_month: pd.Timestamp,
) -> pd.DataFrame:

    print_header(
        "STEP 5 — BUILDING OFFICIAL MONTHLY PORTFOLIO SIGNAL"
    )

    print(
        f"Official signal month : "
        f"{signal_month.strftime('%Y-%m-%d')}"
    )

    # The composite index is month-end.

    if signal_month not in composite.index:

        raise RuntimeError(
            f"No composite score exists for "
            f"{signal_month.date()}."
        )

    scores = (
        composite
        .loc[signal_month]
        .dropna()
    )

    scores = scores.sort_values(
        ascending=False
    )

    scores = scores.head(
        TOP_N
    )

    # -------------------------------------------------------------------------
    # Current latest trading price
    # -------------------------------------------------------------------------

    latest_data_date = (
        close.index.max()
    )

    latest_prices = (
        close.loc[latest_data_date]
    )

    records = []

    for rank, (
        symbol,
        score
    ) in enumerate(
        scores.items(),
        start=1
    ):

        current_price = safe_float(
            latest_prices.get(symbol)
        )

        signal_month_price = safe_float(
            monthly_close
            .loc[signal_month]
            .get(symbol)
        )

        records.append(
            {
                "market_rank": rank,
                "symbol": symbol,
                "signal_date":
                    signal_month.strftime(
                        "%Y-%m-%d"
                    ),
                "latest_data_date":
                    latest_data_date.strftime(
                        "%Y-%m-%d"
                    ),
                "signal_month_price":
                    signal_month_price,
                "price": current_price,
                "score": safe_float(score),
            }
        )

    result = pd.DataFrame(
        records
    )

    if result.empty:

        raise RuntimeError(
            "No stocks qualified for the "
            "latest portfolio."
        )

    return result


# =============================================================================
# METADATA — SECTOR / INDUSTRY / MARKET CAP
# =============================================================================

def load_metadata_cache() -> dict[str, Any]:

    if not METADATA_CACHE_FILE.exists():
        return {}

    try:

        with open(
            METADATA_CACHE_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        if isinstance(
            data,
            dict
        ):

            return data

    except Exception:

        pass

    return {}


def save_metadata_cache(
    cache: dict[str, Any]
) -> None:

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        METADATA_CACHE_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            cache,
            file,
            indent=2,
            ensure_ascii=False
        )


def fetch_symbol_metadata(
    symbol: str
) -> tuple[str, dict[str, Any]]:
    """
    Fetch metadata for one symbol.

    Sector / industry generally require Ticker.info.
    Market cap is taken from marketCap when available.

    This is only done for the Top 20, not all 500 stocks, keeping the
    weekend run reasonably fast.
    """

    try:

        ticker = yf.Ticker(
            symbol
        )

        info = {}

        try:

            info = ticker.info

        except Exception:

            info = {}

        if not isinstance(
            info,
            dict
        ):

            info = {}

        sector = info.get(
            "sector"
        )

        industry = info.get(
            "industry"
        )

        market_cap = info.get(
            "marketCap"
        )

        # Try fast_info if marketCap was unavailable.

        if market_cap is None:

            try:

                fast_info = (
                    ticker.fast_info
                )

                if fast_info:

                    market_cap = (
                        fast_info.get(
                            "market_cap"
                        )
                    )

            except Exception:

                pass

        return symbol, {
            "sector": sector or "-",
            "industry": industry or "-",
            "market_cap_rupees":
                safe_float(market_cap),
        }

    except Exception:

        return symbol, {
            "sector": "-",
            "industry": "-",
            "market_cap_rupees": None,
        }


def enrich_with_metadata(
    signal: pd.DataFrame
) -> pd.DataFrame:

    print_header(
        "STEP 6 — ADDING SECTOR / INDUSTRY / MARKET CAP"
    )

    cache = load_metadata_cache()

    symbols_to_fetch = []

    for symbol in signal["symbol"]:

        cached = cache.get(
            symbol
        )

        if isinstance(
            cached,
            dict
        ):

            continue

        symbols_to_fetch.append(
            symbol
        )

    print(
        f"Top portfolio symbols : "
        f"{len(signal)}"
    )

    print(
        f"Metadata cache hits   : "
        f"{len(signal) - len(symbols_to_fetch)}"
    )

    print(
        f"Metadata downloads    : "
        f"{len(symbols_to_fetch)}"
    )

    # -------------------------------------------------------------------------
    # Fetch only Top 20 metadata concurrently.
    # -------------------------------------------------------------------------

    if symbols_to_fetch:

        with ThreadPoolExecutor(
            max_workers=min(
                8,
                len(symbols_to_fetch)
            )
        ) as executor:

            futures = {
                executor.submit(
                    fetch_symbol_metadata,
                    symbol
                ): symbol
                for symbol in symbols_to_fetch
            }

            for future in as_completed(
                futures
            ):

                symbol = futures[
                    future
                ]

                try:

                    returned_symbol, metadata = (
                        future.result()
                    )

                    cache[
                        returned_symbol
                    ] = metadata

                except Exception:

                    cache[symbol] = {
                        "sector": "-",
                        "industry": "-",
                        "market_cap_rupees":
                            None,
                    }

    save_metadata_cache(
        cache
    )

    signal = signal.copy()

    signal["sector"] = signal[
        "symbol"
    ].map(
        lambda x:
            cache.get(
                x,
                {}
            ).get(
                "sector",
                "-"
            )
    )

    signal["industry"] = signal[
        "symbol"
    ].map(
        lambda x:
            cache.get(
                x,
                {}
            ).get(
                "industry",
                "-"
            )
    )

    signal["Market Cap (In Cr)"] = signal[
        "symbol"
    ].map(
        lambda x:
            format_market_cap_crore(
                cache.get(
                    x,
                    {}
                ).get(
                    "market_cap_rupees"
                )
            )
    )

    return signal


# =============================================================================
# MARKET BREADTH
# =============================================================================

def calculate_ema(
    series: pd.Series,
    span: int
) -> pd.Series:

    return series.ewm(
        span=span,
        adjust=False,
        min_periods=span
    ).mean()


def classify_breadth(
    percentage: float
) -> str:

    if percentage < 50.0:
        return "Low"

    if percentage < 70.0:
        return "Medium"

    return "High"


def breadth_pattern(
    pct20: float,
    pct50: float,
    pct200: float
) -> str:

    if (
        pct20 < pct50
        and pct50 < pct200
    ):

        return (
            "Short-term participation is weaker than "
            "medium- and long-term participation."
        )

    if (
        pct20 > pct50
        and pct50 > pct200
    ):

        return (
            "Short-term participation is stronger than "
            "medium- and long-term participation."
        )

    if (
        pct20 < 50
        and pct50 < 50
        and pct200 < 50
    ):

        return (
            "Participation is weak across short-, medium-, "
            "and long-term horizons."
        )

    if (
        pct20 >= 70
        and pct50 >= 70
        and pct200 >= 70
    ):

        return (
            "Broad participation is strong across short-, "
            "medium-, and long-term horizons."
        )

    return (
        "Market participation is mixed across the "
        "short-, medium-, and long-term horizons."
    )


def calculate_market_breadth(
    close: pd.DataFrame,
    symbols: list[str]
) -> tuple[
    pd.DataFrame,
    pd.DataFrame
]:

    print_header(
        "CALCULATING NIFTY 500 EMA MARKET BREADTH "
        "(Low if <50, Medium if 50-70, High if >70)"
    )

    program_date = (
        PROGRAM_RUN_DATE.strftime(
            "%Y-%m-%d"
        )
    )

    print(
        f"Program run date: {program_date}"
    )

    # -------------------------------------------------------------------------
    # Determine each stock's latest available date.
    # -------------------------------------------------------------------------

    latest_by_symbol: dict[
        str,
        pd.Timestamp
    ] = {}

    for symbol in symbols:

        if symbol not in close.columns:
            continue

        series = (
            close[symbol]
            .dropna()
        )

        if series.empty:
            continue

        latest_by_symbol[
            symbol
        ] = series.index.max()

    if not latest_by_symbol:

        raise RuntimeError(
            "Could not determine latest "
            "market-data dates."
        )

    latest_dates = list(
        latest_by_symbol.values()
    )

    latest_available_market_date = max(
        latest_dates
    )

    earliest_latest_data_date = min(
        latest_dates
    )

    print(
        "Latest available market-data date: "
        f"{latest_available_market_date.strftime('%Y-%m-%d')}"
    )

    print(
        "Earliest latest-data date: "
        f"{earliest_latest_data_date.strftime('%Y-%m-%d')}"
    )

    # -------------------------------------------------------------------------
    # Date distribution.
    # -------------------------------------------------------------------------

    date_counts: dict[
        str,
        int
    ] = {}

    for date_value in latest_dates:

        date_text = (
            date_value.strftime(
                "%Y-%m-%d"
            )
        )

        date_counts[
            date_text
        ] = (
            date_counts.get(
                date_text,
                0
            )
            + 1
        )

    print()
    print(
        "Latest available data by date:"
    )

    for date_text in sorted(
        date_counts.keys(),
        reverse=True
    )[:10]:

        print(
            f"{date_text}: "
            f"{date_counts[date_text]} stocks"
        )

    # -------------------------------------------------------------------------
    # Use latest common market date.
    # -------------------------------------------------------------------------

    breadth_date = (
        latest_available_market_date
    )

    valid_symbols = []

    above20 = 0
    above50 = 0
    above200 = 0

    rows = []

    for symbol in symbols:

        if symbol not in close.columns:
            continue

        series = (
            close[symbol]
            .dropna()
        )

        if len(series) < MIN_DAILY_OBSERVATIONS:
            continue

        if breadth_date not in series.index:

            # A stale stock is not allowed to use a different date
            # for the common breadth denominator.

            continue

        price = safe_float(
            series.loc[breadth_date]
        )

        if price is None:
            continue

        ema20 = (
            calculate_ema(
                series,
                20
            ).get(
                breadth_date
            )
        )

        ema50 = (
            calculate_ema(
                series,
                50
            ).get(
                breadth_date
            )
        )

        ema200 = (
            calculate_ema(
                series,
                200
            ).get(
                breadth_date
            )
        )

        if (
            pd.isna(ema20)
            or pd.isna(ema50)
            or pd.isna(ema200)
        ):

            continue

        valid_symbols.append(
            symbol
        )

        is_above20 = (
            price > float(ema20)
        )

        is_above50 = (
            price > float(ema50)
        )

        is_above200 = (
            price > float(ema200)
        )

        above20 += int(
            is_above20
        )

        above50 += int(
            is_above50
        )

        above200 += int(
            is_above200
        )

        rows.append(
            {
                "date":
                    breadth_date.strftime(
                        "%Y-%m-%d"
                    ),
                "symbol": symbol,
                "price": price,
                "ema20": float(ema20),
                "ema50": float(ema50),
                "ema200": float(ema200),
                "above_20d_ema":
                    is_above20,
                "above_50d_ema":
                    is_above50,
                "above_200d_ema":
                    is_above200,
            }
        )

    valid_count = len(
        valid_symbols
    )

    if valid_count == 0:

        raise RuntimeError(
            "No valid stocks available "
            "for EMA breadth."
        )

    pct20 = (
        above20
        / valid_count
        * 100.0
    )

    pct50 = (
        above50
        / valid_count
        * 100.0
    )

    pct200 = (
        above200
        / valid_count
        * 100.0
    )

    label20 = classify_breadth(
        pct20
    )

    label50 = classify_breadth(
        pct50
    )

    label200 = classify_breadth(
        pct200
    )

    pattern = breadth_pattern(
        pct20,
        pct50,
        pct200
    )

    print()

    print(
        f"Breadth date: "
        f"{breadth_date.strftime('%Y-%m-%d')}"
    )

    print(
        f"Valid Nifty 500 stocks: "
        f"{valid_count}"
    )

    print(
        f"Above 20D EMA: "
        f"{above20} "
        f"({pct20:.2f}%) — "
        f"{label20}"
    )

    print(
        f"Above 50D EMA: "
        f"{above50} "
        f"({pct50:.2f}%) — "
        f"{label50}"
    )

    print(
        f"Above 200D EMA: "
        f"{above200} "
        f"({pct200:.2f}%) — "
        f"{label200}"
    )

    print(
        f"Market Breadth Pattern: "
        f"{pattern}"
    )

    breadth_summary = pd.DataFrame(
        [
            {
                "date":
                    breadth_date.strftime(
                        "%Y-%m-%d"
                    ),
                "metric":
                    "Above 20D EMA",
                "stocks":
                    above20,
                "valid_stocks":
                    valid_count,
                "percentage":
                    pct20,
                "classification":
                    label20,
            },
            {
                "date":
                    breadth_date.strftime(
                        "%Y-%m-%d"
                    ),
                "metric":
                    "Above 50D EMA",
                "stocks":
                    above50,
                "valid_stocks":
                    valid_count,
                "percentage":
                    pct50,
                "classification":
                    label50,
            },
            {
                "date":
                    breadth_date.strftime(
                        "%Y-%m-%d"
                    ),
                "metric":
                    "Above 200D EMA",
                "stocks":
                    above200,
                "valid_stocks":
                    valid_count,
                "percentage":
                    pct200,
                "classification":
                    label200,
            },
        ]
    )

    breadth_details = pd.DataFrame(
        rows
    )

    return (
        breadth_summary,
        breadth_details
    )


# =============================================================================
# PORTFOLIO STATE
# =============================================================================

def load_portfolio_state() -> dict[str, Any] | None:

    if not STATE_FILE.exists():
        return None

    try:

        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            state = json.load(
                file
            )

        if isinstance(
            state,
            dict
        ):

            return state

    except Exception as exc:

        print()

        print(
            "WARNING: Existing portfolio state "
            "could not be read."
        )

        print(
            f"Reason: {exc}"
        )

    return None


def save_portfolio_state(
    signal: pd.DataFrame,
    signal_month: pd.Timestamp
) -> None:

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    portfolio = []

    for _, row in signal.iterrows():

        portfolio.append(
            {
                "market_rank":
                    int(
                        row["market_rank"]
                    ),
                "symbol":
                    str(
                        row["symbol"]
                    ),
                "score":
                    safe_float(
                        row["score"]
                    ),
            }
        )

    state = {
        "strategy":
            "MomentumPortfolioLab",
        "top_n":
            TOP_N,
        "signal_month":
            signal_month.strftime(
                "%Y-%m-%d"
            ),
        "created_or_updated":
            PROGRAM_RUN_TIMESTAMP.isoformat(),
        "portfolio":
            portfolio,
    }

    with open(
        STATE_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            state,
            file,
            indent=2,
            ensure_ascii=False
        )


# =============================================================================
# ACTION ENGINE
# =============================================================================

def build_actions(
    signal: pd.DataFrame,
    previous_state: dict[str, Any] | None,
    signal_month: pd.Timestamp,
) -> tuple[
    pd.DataFrame,
    bool
]:

    print_header(
        "STEP 7 — LIVE BUY / HOLD / SELL / REPLACEMENT DECISION"
    )

    current_symbols = list(
        signal["symbol"]
    )

    current_rank = {
        str(row["symbol"]):
            int(row["market_rank"])
        for _, row in signal.iterrows()
    }

    current_score = {
        str(row["symbol"]):
            safe_float(row["score"])
        for _, row in signal.iterrows()
    }

    # -------------------------------------------------------------------------
    # FIRST RUN
    # -------------------------------------------------------------------------

    if previous_state is None:

        print()
        print(
            "No previous portfolio state found."
        )

        print(
            "This is treated as the "
            "FIRST LIVE PORTFOLIO."
        )

        actions = []

        for _, row in signal.iterrows():

            actions.append(
                {
                    "action": "BUY",
                    "symbol":
                        row["symbol"],
                    "market_rank":
                        int(
                            row["market_rank"]
                        ),
                    "previous_rank":
                        "-",
                    "price":
                        row["price"],
                    "score":
                        row["score"],
                    "reason":
                        (
                            "Fresh-position: stock is in "
                            "the current Top 20 and no "
                            "previous portfolio exists."
                        ),
                }
            )

        return (
            pd.DataFrame(actions),
            True
        )

    # -------------------------------------------------------------------------
    # PREVIOUS PORTFOLIO
    # -------------------------------------------------------------------------

    previous_portfolio = (
        previous_state.get(
            "portfolio",
            []
        )
    )

    previous_symbols = []

    previous_rank = {}

    previous_score = {}

    for item in previous_portfolio:

        symbol = normalize_symbol(
            item.get(
                "symbol",
                ""
            )
        )

        if not symbol:
            continue

        previous_symbols.append(
            symbol
        )

        previous_rank[symbol] = (
            item.get(
                "market_rank",
                "-"
            )
        )

        previous_score[symbol] = (
            safe_float(
                item.get(
                    "score"
                )
            )
        )

    previous_symbols = list(
        dict.fromkeys(
            previous_symbols
        )
    )

    previous_signal_month = (
        previous_state.get(
            "signal_month"
        )
    )

    # -------------------------------------------------------------------------
    # Is this a new monthly signal?
    # -------------------------------------------------------------------------

    current_signal_month = (
        signal_month.strftime(
            "%Y-%m-%d"
        )
    )

    new_monthly_signal = (
        previous_signal_month
        != current_signal_month
    )

    print()

    print(
        f"Previous signal month : "
        f"{previous_signal_month or '-'}"
    )

    print(
        f"Current signal month  : "
        f"{current_signal_month}"
    )

    print(
        f"New monthly signal    : "
        f"{'YES' if new_monthly_signal else 'NO'}"
    )

    actions = []

    # -------------------------------------------------------------------------
    # NO NEW MONTH-END SIGNAL
    #
    # Do not churn the portfolio based on current ranking.
    # -------------------------------------------------------------------------

    if not new_monthly_signal:

        for _, row in signal.iterrows():

            symbol = str(
                row["symbol"]
            )

            if symbol in previous_symbols:

                actions.append(
                    {
                        "action":
                            "HOLD",
                        "symbol":
                            symbol,
                        "market_rank":
                            int(
                                row["market_rank"]
                            ),
                        "previous_rank":
                            previous_rank.get(
                                symbol,
                                "-"
                            ),
                        "price":
                            row["price"],
                        "score":
                            row["score"],
                        "reason":
                            (
                                "No new month-end "
                                "rebalance. Continue "
                                "holding the existing "
                                "monthly portfolio."
                            ),
                    }
                )

        # Stocks in previous state that are not in current signal are NOT
        # automatically sold during the month.
        #
        # This protects the monthly-tested strategy from weekly churn.

        if not actions:

            for symbol in previous_symbols:

                actions.append(
                    {
                        "action":
                            "HOLD",
                        "symbol":
                            symbol,
                        "market_rank":
                            "-",
                        "previous_rank":
                            previous_rank.get(
                                symbol,
                                "-"
                            ),
                        "price":
                            np.nan,
                        "score":
                            np.nan,
                        "reason":
                            (
                                "No new month-end "
                                "rebalance. Existing "
                                "monthly position "
                                "remains active."
                            ),
                    }
                )

        return (
            pd.DataFrame(actions),
            False
        )

    # -------------------------------------------------------------------------
    # NEW MONTHLY SIGNAL
    # -------------------------------------------------------------------------

    current_set = set(
        current_symbols
    )

    previous_set = set(
        previous_symbols
    )

    retained = (
        current_set.intersection(
            previous_set
        )
    )

    sold = (
        previous_set
        - current_set
    )

    bought = (
        current_set
        - previous_set
    )

    # -------------------------------------------------------------------------
    # HOLD
    # -------------------------------------------------------------------------

    for symbol in sorted(
        retained,
        key=lambda x:
            current_rank.get(
                x,
                999
            )
    ):

        row = signal.loc[
            signal["symbol"] == symbol
        ].iloc[0]

        actions.append(
            {
                "action":
                    "HOLD",
                "symbol":
                    symbol,
                "market_rank":
                    int(
                        current_rank[symbol]
                    ),
                "previous_rank":
                    previous_rank.get(
                        symbol,
                        "-"
                    ),
                "price":
                    row["price"],
                "score":
                    current_score[symbol],
                "reason":
                    (
                        "Stock remains inside the official "
                        "Top 20 at the new monthly rebalance."
                    ),
            }
        )

    # -------------------------------------------------------------------------
    # BUY
    # -------------------------------------------------------------------------

    bought_rows = []

    for symbol in sorted(
        bought,
        key=lambda x:
            current_rank.get(
                x,
                999
            )
    ):

        row = signal.loc[
            signal["symbol"] == symbol
        ].iloc[0]

        bought_rows.append(
            {
                "action":
                    "BUY",
                "symbol":
                    symbol,
                "market_rank":
                    int(
                        current_rank[symbol]
                    ),
                "previous_rank":
                    "-",
                "price":
                    row["price"],
                "score":
                    current_score[symbol],
                "reason":
                    (
                        "New stock entered the official "
                        "Top 20 at the monthly rebalance."
                    ),
            }
        )

    # -------------------------------------------------------------------------
    # SELL
    # -------------------------------------------------------------------------

    sold_rows = []

    for symbol in sorted(
        sold,
        key=lambda x:
            previous_rank.get(
                x,
                999
            )
            if isinstance(
                previous_rank.get(
                    x,
                    999
                ),
                int
            )
            else 999
    ):

        sold_rows.append(
            {
                "action":
                    "SELL",
                "symbol":
                    symbol,
                "market_rank":
                    "-",
                "previous_rank":
                    previous_rank.get(
                        symbol,
                        "-"
                    ),
                "price":
                    np.nan,
                "score":
                    np.nan,
                "reason":
                    (
                        "Stock exited the official "
                        "Top 20 at the monthly rebalance."
                    ),
            }
        )

    # -------------------------------------------------------------------------
    # REPLACEMENT
    #
    # If there are equal numbers of entrants and exits, explicitly label
    # the pairs as replacements.
    # -------------------------------------------------------------------------

    replacement_count = min(
        len(bought_rows),
        len(sold_rows)
    )

    replacement_rows = []

    for i in range(
        replacement_count
    ):

        buy_row = bought_rows[i]
        sell_row = sold_rows[i]

        replacement_rows.append(
            {
                "action":
                    "REPLACEMENT",
                "symbol":
                    buy_row["symbol"],
                "market_rank":
                    buy_row["market_rank"],
                "previous_rank":
                    "-",
                "price":
                    buy_row["price"],
                "score":
                    buy_row["score"],
                "reason":
                    (
                        f"Replace {sell_row['symbol']} "
                        f"(previous rank "
                        f"{sell_row['previous_rank']}) "
                        f"with {buy_row['symbol']} "
                        f"(new rank "
                        f"{buy_row['market_rank']})."
                    ),
            }
        )

    # -------------------------------------------------------------------------
    # Add unmatched buys.
    # -------------------------------------------------------------------------

    for row in bought_rows[
        replacement_count:
    ]:

        row = row.copy()

        row["reason"] = (
            row["reason"]
            + " No one-for-one replacement "
            + "pairing was required."
        )

        replacement_rows.append(
            row
        )

    # -------------------------------------------------------------------------
    # Add unmatched sells.
    # -------------------------------------------------------------------------

    for row in sold_rows[
        replacement_count:
    ]:

        replacement_rows.append(
            row
        )

    # -------------------------------------------------------------------------
    # Final action order
    # -------------------------------------------------------------------------

    action_order = {
        "REPLACEMENT": 1,
        "BUY": 2,
        "SELL": 3,
        "HOLD": 4,
    }

    final_rows = (
        replacement_rows
        + actions
    )

    action_df = pd.DataFrame(
        final_rows
    )

    if not action_df.empty:

        action_df["_order"] = (
            action_df["action"]
            .map(action_order)
            .fillna(99)
        )

        action_df = (
            action_df
            .sort_values(
                by=[
                    "_order",
                    "market_rank"
                ],
                na_position="last"
            )
            .drop(
                columns=["_order"]
            )
        )

    return (
        action_df.reset_index(
            drop=True
        ),
        True
    )


# =============================================================================
# LIVE ACTION DISPLAY
# =============================================================================

def print_live_actions(
    actions: pd.DataFrame,
    signal_month: pd.Timestamp,
    new_monthly_signal: bool
) -> None:

    print_header(
        "LIVE MARKET ACTIONS — WHAT TO DO"
    )

    print(
        f"Official signal month : "
        f"{signal_month.strftime('%Y-%m-%d')}"
    )

    print(
        f"New monthly rebalance : "
        f"{'YES' if new_monthly_signal else 'NO'}"
    )

    print()

    if actions.empty:

        print(
            "No action rows generated."
        )

        return

    # -------------------------------------------------------------------------
    # Action summary
    # -------------------------------------------------------------------------

    counts = (
        actions["action"]
        .value_counts()
        .to_dict()
    )

    print(
        "Action summary: "
        + " | ".join(
            f"{key}={value}"
            for key, value in counts.items()
        )
    )

    print()

    # -------------------------------------------------------------------------
    # Human-readable instructions
    # -------------------------------------------------------------------------

    if new_monthly_signal:

        print(
            "WHAT TO DO IN THE LIVE MARKET:"
        )

        print()

        if "REPLACEMENT" in actions[
            "action"
        ].values:

            print(
                "1. REPLACEMENT → On the next practical "
                "trading session, SELL the old holding "
                "named in the reason and BUY the new "
                "Top 20 stock shown in the symbol column."
            )

        if "BUY" in actions[
            "action"
        ].values:

            print(
                "2. BUY → Add the stock to the portfolio."
            )

        if "SELL" in actions[
            "action"
        ].values:

            print(
                "3. SELL → Exit the stock because it left "
                "the official monthly Top 20."
            )

        if "HOLD" in actions[
            "action"
        ].values:

            print(
                "4. HOLD → Keep the existing position; "
                "do not churn it because of short-term "
                "rank movement."
            )

        print()

        print(
            "Position sizing: keep the same equal-weight "
            "approach used in the backtest."
        )

        print(
            f"Research transaction/slippage assumption: "
            f"{TOTAL_COST_BPS:.0f} bps total."
        )

    else:

        print(
            "NO NEW MONTHLY REBALANCE."
        )

        print()

        print(
            "This weekend is a monitoring run."
        )

        print(
            "Do NOT sell or buy merely because the "
            "displayed rank has moved during the month."
        )

        print(
            "Continue holding the current monthly portfolio."
        )

    print()

    print(
        "IMPORTANT: This program generates research/"
        "trading signals; it does not place broker orders."
    )


# =============================================================================
# PORTFOLIO TABLE DISPLAY
# =============================================================================

def print_portfolio_table(
    signal: pd.DataFrame
) -> None:

    print_header(
        f"LATEST OFFICIAL PORTFOLIO — TOP {TOP_N}"
    )

    display = signal.copy()

    display["price"] = (
        display["price"]
        .map(
            lambda x:
                format_number(
                    x,
                    2
                )
        )
    )

    display["score"] = (
        display["score"]
        .map(
            lambda x:
                format_number(
                    x,
                    3
                )
        )
    )

    display["signal_month_price"] = (
        display["signal_month_price"]
        .map(
            lambda x:
                format_number(
                    x,
                    2
                )
        )
    )

    columns = [
        "market_rank",
        "symbol",
        "sector",
        "industry",
        "price",
        "Market Cap (In Cr)",
        "score",
    ]

    print(
        display[columns].to_string(
            index=False
        )
    )


# =============================================================================
# ACTION TABLE DISPLAY
# =============================================================================

def print_action_table(
    actions: pd.DataFrame
) -> None:

    print_header(
        "ACTION TABLE"
    )

    if actions.empty:

        print(
            "No action rows."
        )

        return

    display = actions.copy()

    display["price"] = (
        display["price"]
        .map(
            lambda x:
                format_number(
                    x,
                    2
                )
                if safe_float(x) is not None
                else "-"
        )
    )

    display["score"] = (
        display["score"]
        .map(
            lambda x:
                format_number(
                    x,
                    3
                )
                if safe_float(x) is not None
                else "-"
        )
    )

    columns = [
        "action",
        "symbol",
        "market_rank",
        "previous_rank",
        "price",
        "score",
        "reason",
    ]

    print(
        display[columns].to_string(
            index=False
        )
    )


# =============================================================================
# SAVE OUTPUTS
# =============================================================================

def save_outputs(
    signal: pd.DataFrame,
    actions: pd.DataFrame,
    breadth_summary: pd.DataFrame,
    breadth_details: pd.DataFrame,
) -> None:

    print_header(
        "STEP 8 — SAVING LIVE OUTPUTS"
    )

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    signal.to_csv(
        SIGNAL_FILE,
        index=False
    )

    actions.to_csv(
        ACTIONS_FILE,
        index=False
    )

    breadth_summary.to_csv(
        BREADTH_FILE,
        index=False
    )

    breadth_details.to_csv(
        BREADTH_DETAILS_FILE,
        index=False
    )

    print(
        f"Signal   : {SIGNAL_FILE}"
    )

    print(
        f"Actions  : {ACTIONS_FILE}"
    )

    print(
        f"Breadth  : {BREADTH_FILE}"
    )

    print(
        f"Details  : {BREADTH_DETAILS_FILE}"
    )

    print(
        f"State    : {STATE_FILE}"
    )


# =============================================================================
# FINAL WEEKEND OPERATING GUIDE
# =============================================================================

def print_weekend_operating_guide(
    signal_month: pd.Timestamp,
    breadth_summary: pd.DataFrame,
    new_monthly_signal: bool,
) -> None:

    print_header(
        "WEEKEND LIVE-MARKET OPERATING GUIDE"
    )

    print(
        "1. RUN:"
    )

    print(
        "   Run main.py once after the latest "
        "trading week is complete."
    )

    print()

    print(
        "2. PORTFOLIO SELECTION:"
    )

    print(
        f"   Official strategy signal = "
        f"{signal_month.strftime('%Y-%m-%d')} "
        f"month-end."
    )

    print(
        "   Do not use the current partial month "
        "to create a new portfolio."
    )

    print()

    print(
        "3. BUY:"
    )

    print(
        "   BUY means the stock entered the official "
        "Top 20."
    )

    print(
        "   Use equal-weight allocation as in the backtest."
    )

    print()

    print(
        "4. HOLD:"
    )

    print(
        "   HOLD means keep the position."
    )

    print(
        "   Weekly rank movement alone is NOT an exit signal."
    )

    print()

    print(
        "5. SELL:"
    )

    print(
        "   SELL means the stock exited the official "
        "Top 20 at a new monthly rebalance."
    )

    print()

    print(
        "6. REPLACEMENT:"
    )

    print(
        "   SELL the exiting stock and BUY the entering stock."
    )

    print()

    print(
        "7. MARKET BREADTH:"
    )

    print(
        "   EMA breadth is a MARKET-CONDITION MONITOR."
    )

    print(
        "   It is NOT a portfolio switch because the "
        "backtest did not use a regime filter."
    )

    print()

    print(
        "8. WEEKEND RESET:"
    )

    if new_monthly_signal:

        print(
            "   NEW MONTHLY SIGNAL detected → portfolio "
            "comparison has been performed."
        )

    else:

        print(
            "   No new month-end signal → portfolio is "
            "carried forward without rank-based churn."
        )

    print()

    print(
        "9. ORDER TIMING:"
    )

    print(
        "   The signal is calculated only after the "
        "month-end data is completed."
    )

    print(
        "   Actual execution should occur in the next "
        "available trading session."
    )

    print()

    print(
        "10. IMPORTANT:"
    )

    print(
        "    Backtest returns assume theoretical execution "
        "at the signal point. Live execution price, liquidity, "
        "brokerage, taxes and slippage can differ."
    )

    print()

    # -------------------------------------------------------------------------
    # Breadth quick summary
    # -------------------------------------------------------------------------

    if not breadth_summary.empty:

        print(
            "CURRENT MARKET BREADTH:"
        )

        for _, row in breadth_summary.iterrows():

            print(
                f"   {row['metric']}: "
                f"{row['percentage']:.2f}% — "
                f"{row['classification']}"
            )


# =============================================================================
# RUNTIME DISPLAY
# =============================================================================

def print_runtime(
    start_timestamp: datetime
) -> None:

    end_timestamp = datetime.now()

    elapsed = (
        end_timestamp
        - start_timestamp
    ).total_seconds()

    print_header(
        "PROGRAM RUNTIME"
    )

    print(
        f"Start timestamp : "
        f"{start_timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    print(
        f"End timestamp   : "
        f"{end_timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    print(
        f"Elapsed seconds : "
        f"{elapsed:.2f}"
    )

    minutes = int(
        elapsed // 60
    )

    seconds = elapsed % 60

    print(
        f"Total runtime   : "
        f"{minutes:02d}:{seconds:05.2f}"
    )


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:

    start_datetime = datetime.now()

    print()
    print(LINE)

    print(
        "       MomentumPortfolioLab — "
        "MONTHLY MOMENTUM PORTFOLIO DECISION ENGINE"
    )

    print(LINE)

    print()

    print(
        f"Program run timestamp : "
        f"{PROGRAM_RUN_TIMESTAMP.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    print(
        f"Program run date      : "
        f"{PROGRAM_RUN_DATE.strftime('%Y-%m-%d')}"
    )

    print(
        f"Top N                 : {TOP_N}"
    )

    print(
        f"12-1 Momentum weight  : "
        f"{MOMENTUM_12M_WEIGHT:.0%}"
    )

    print(
        f"6M Momentum weight    : "
        f"{MOMENTUM_6M_WEIGHT:.0%}"
    )

    print(
        f"Transaction cost      : "
        f"{TRANSACTION_COST_BPS:.1f} bps"
    )

    print(
        f"Slippage              : "
        f"{SLIPPAGE_BPS:.1f} bps"
    )

    print(
        f"Total research cost   : "
        f"{TOTAL_COST_BPS:.1f} bps"
    )

    print(
        "Fundamentals          : No"
    )

    print(
        "Market regime filter  : No"
    )

    try:

        # =====================================================================
        # 1. UNIVERSE
        # =====================================================================

        refresh_universe()

        symbols = (
            load_generated_universe()
        )

        # =====================================================================
        # 2. MARKET DATA
        # =====================================================================

        data, valid_symbols = (
            download_market_data(
                symbols
            )
        )

        close = (
            get_close_frame(
                data
            )
        )

        # Keep only valid downloaded symbols.

        available_symbols = [
            symbol
            for symbol in valid_symbols
            if symbol in close.columns
        ]

        close = close[
            available_symbols
        ].copy()

        # =====================================================================
        # 3. STRATEGY SCORE
        # =====================================================================

        (
            monthly_close,
            composite,
            signal_volatility,
        ) = (
            calculate_monthly_strategy_scores(
                close
            )
        )

        # =====================================================================
        # 4. COMPLETED MONTH-END
        # =====================================================================

        signal_month = (
            get_latest_completed_month_end(
                monthly_close
            )
        )

        # =====================================================================
        # 5. LATEST TOP 20
        # =====================================================================

        signal = (
            build_latest_signal(
                close=close,
                monthly_close=monthly_close,
                composite=composite,
                signal_month=signal_month,
            )
        )

        # =====================================================================
        # 6. METADATA
        # =====================================================================

        signal = (
            enrich_with_metadata(
                signal
            )
        )

        # =====================================================================
        # 7. MARKET BREADTH
        # =====================================================================

        (
            breadth_summary,
            breadth_details,
        ) = (
            calculate_market_breadth(
                close=close,
                symbols=symbols,
            )
        )

        # =====================================================================
        # 8. PREVIOUS STATE
        # =====================================================================

        previous_state = (
            load_portfolio_state()
        )

        # =====================================================================
        # 9. ACTIONS
        # =====================================================================

        (
            actions,
            new_monthly_signal,
        ) = (
            build_actions(
                signal=signal,
                previous_state=previous_state,
                signal_month=signal_month,
            )
        )

        # =====================================================================
        # 10. DISPLAY PORTFOLIO
        # =====================================================================

        print_portfolio_table(
            signal
        )

        # =====================================================================
        # 11. DISPLAY ACTIONS
        # =====================================================================

        print_live_actions(
            actions=actions,
            signal_month=signal_month,
            new_monthly_signal=new_monthly_signal,
        )

        print_action_table(
            actions
        )

        # =====================================================================
        # 12. SAVE OUTPUTS
        # =====================================================================

        save_outputs(
            signal=signal,
            actions=actions,
            breadth_summary=breadth_summary,
            breadth_details=breadth_details,
        )

        # =====================================================================
        # 13. UPDATE STATE
        #
        # IMPORTANT:
        # The state is updated to the official Top 20 after each run.
        #
        # During a non-rebalance week, the same monthly signal is preserved.
        # =====================================================================

        save_portfolio_state(
            signal=signal,
            signal_month=signal_month,
        )

        # =====================================================================
        # 14. OPERATING GUIDE
        # =====================================================================

        print_weekend_operating_guide(
            signal_month=signal_month,
            breadth_summary=breadth_summary,
            new_monthly_signal=new_monthly_signal,
        )

        # =====================================================================
        # SUCCESS
        # =====================================================================

        print_header(
            "PROGRAM COMPLETED SUCCESSFULLY"
        )

        print(
            "MomentumPortfolioLab monthly momentum "
            "decision engine completed."
        )

    except KeyboardInterrupt:

        print()

        print_header(
            "PROGRAM STOPPED"
        )

        print(
            "Execution interrupted by user."
        )

        raise

    except Exception as exc:

        print()

        print_header(
            "PROGRAM ERROR"
        )

        print(
            f"Error : {exc}"
        )

        print()

        print(
            "The existing trade_data.py was not modified."
        )

        raise

    finally:

        print_runtime(
            start_datetime
        )


if __name__ == "__main__":
    main()