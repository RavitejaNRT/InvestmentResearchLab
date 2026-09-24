"""
| List                                         |     Rating | What it measures                                | My assessment                                                                                                                                                        |
| -------------------------------------------- | ---------: | ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **List 1 — Typical Return Leaders**          | **8.5/10** | Median 1Y rolling return                        | Excellent for identifying stocks with genuinely high typical returns, but can tolerate large drawdowns.                                                              |
| **List 2 — Most Consistent >20% Returns**    |   **9/10** | % of rolling periods >20%                       | Very useful and intuitive. Strong measure of repeatability, but doesn't adequately penalize severe downside.                                                         |
| **List 3 — Downside Stability Leaders**      |   **8/10** | P10 + Worst 1Y                                  | Excellent risk-control perspective, but can favor defensive/moderate-return stocks.                                                                                  |
| **List 4 — Balanced Consistency Candidates** | **8.5/10** | Hit Rate → P10 → Worst → History → Median       | Good multi-factor screening, but **priority ordering is not mathematically proportional**; a small difference in Hit Rate can dominate a large difference in Median. |
| **List 5 — Overall Balanced Leaders**        | **9.5/10** | 50% Median + 25% Hit Rate + 15% P10 + 10% Worst | **Best overall research list of the five** because it combines return, consistency and downside into one transparent quantitative score.                             |

ROLLING CONSISTENCY LAB
NIFTY 500 — 1-YEAR ROLLING RETURN CONSISTENCY RESEARCH

PURPOSE
-------
This research identifies Nifty 500 stocks that historically showed:
1. High typical 1-year rolling returns
2. High frequency of 1-year rolling returns above 20%
3. Stronger downside characteristics
4. A balanced combination of consistency and downside characteristics
5. An overall balanced profile using a mathematical composite score

IMPORTANT
---------
This is historical descriptive research.

It does NOT predict future returns and does NOT guarantee future performance.

Lists 1–4 use different priority orders intentionally.

List 5 is different:
    It uses a weighted composite score based on percentile ranks of:
        - Median 1Y Rolling       = 50%
        - Hit Rate >20%           = 25%
        - P10                     = 15%
        - Worst 1Y                = 10%

There is NO composite score in Lists 1–4.
List 5 is the only list that uses a composite score.

DATA
----
Universe:
    Latest Nifty 500 universe refreshed through trade_data.py

Price history:
    Yahoo Finance monthly data

Rolling return:
    12-month rolling return using monthly closing prices

Qualification:
    Minimum 48 rolling observations
    Median 1-year rolling return > 20%

Current market information:
    Yahoo Finance daily data
    Sector / Industry / Market Cap / Market Price

DO NOT MODIFY trade_data.py.
"""

import os
import time
import importlib.util
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import yfinance as yf


# =============================================================================
# RUN CONFIGURATION
# =============================================================================

START_TIME = time.time()
RUN_TIMESTAMP = pd.Timestamp.now()

LAB_DIR = os.path.dirname(os.path.abspath(__file__))

TRADE_DATA_FILE = os.path.join(
    LAB_DIR,
    "trade_data.py"
)

UNIVERSE_FILE = os.path.join(
    LAB_DIR,
    "universe.py"
)

RESULTS_DIR = os.path.join(
    LAB_DIR,
    "results"
)

OUTPUT_FILE = os.path.join(
    RESULTS_DIR,
    "rolling_consistency_lab_results.xlsx"
)

METADATA_CACHE_FILE = os.path.join(
    RESULTS_DIR,
    "rolling_consistency_metadata_cache.pkl"
)


# =============================================================================
# RESEARCH PARAMETERS
# =============================================================================

HISTORY_YEARS = 15
DATA_INTERVAL = "1mo"

MIN_ROLLING_PERIODS = 48
MEDIAN_THRESHOLD = 20.0

TOP_N = 30
RECENT_PERIODS = 12

DOWNLOAD_BATCH_SIZE = 100
METADATA_WORKERS = 12

EMA_PERIODS = [20, 50, 200]
EMA_HISTORY_PERIOD = "2y"


# =============================================================================
# LIST 5 COMPOSITE CONFIGURATION
# =============================================================================

LIST5_MEDIAN_WEIGHT = 0.50
LIST5_HIT_RATE_WEIGHT = 0.25
LIST5_P10_WEIGHT = 0.15
LIST5_WORST_WEIGHT = 0.10


# =============================================================================
# DISPLAY HELPERS
# =============================================================================

def print_header(title):
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def print_subheader(title):
    print()
    print("-" * 80)
    print(title)
    print("-" * 80)


def safe_float(value):
    try:
        if value is None:
            return np.nan

        if pd.isna(value):
            return np.nan

        return float(value)

    except Exception:
        return np.nan


def format_indian_number(value):
    """
    Format numbers using Indian comma grouping.

    Examples:
        172500        -> 1,72,500
        121234567     -> 12,12,34,567
        5000          -> 5,000
    """

    try:
        if value is None or pd.isna(value):
            return ""

        value = float(value)

        sign = "-" if value < 0 else ""
        value = abs(value)

        integer_part = int(value)
        decimal_part = value - integer_part

        integer_text = str(integer_part)

        if len(integer_text) > 3:

            last_three = integer_text[-3:]
            remaining = integer_text[:-3]

            groups = []

            while len(remaining) > 2:
                groups.insert(
                    0,
                    remaining[-2:]
                )
                remaining = remaining[:-2]

            if remaining:
                groups.insert(
                    0,
                    remaining
                )

            formatted_integer = (
                ",".join(groups)
                + ","
                + last_three
            )

        else:
            formatted_integer = integer_text

        if decimal_part > 0.0000001:

            decimal_text = (
                f"{decimal_part:.2f}"
                .split(".")[1]
                .rstrip("0")
            )

            return (
                sign
                + formatted_integer
                + "."
                + decimal_text
            )

        return sign + formatted_integer

    except Exception:
        return str(value)


def format_console_number(value):
    try:
        if value is None or pd.isna(value):
            return ""

        return format_indian_number(value)

    except Exception:
        return str(value)


# =============================================================================
# LOAD trade_data.py
# =============================================================================

print_header("ROLLING CONSISTENCY LAB")

print("Loading trade_data.py...")
print(f"Path: {TRADE_DATA_FILE}")

if not os.path.exists(TRADE_DATA_FILE):
    raise FileNotFoundError(
        f"trade_data.py not found:\n{TRADE_DATA_FILE}"
    )

trade_spec = importlib.util.spec_from_file_location(
    "rolling_consistency_trade_data",
    TRADE_DATA_FILE
)

trade_data = importlib.util.module_from_spec(trade_spec)
trade_spec.loader.exec_module(trade_data)


# =============================================================================
# REFRESH CURRENT NIFTY 500 UNIVERSE
# =============================================================================

print_subheader("Refreshing Current Nifty 500 Universe")

trade_data.refresh_nifty500_universe()

if not os.path.exists(UNIVERSE_FILE):
    raise FileNotFoundError(
        f"Generated universe.py not found:\n{UNIVERSE_FILE}"
    )

print(f"Universe file: {UNIVERSE_FILE}")


# =============================================================================
# LOAD GENERATED UNIVERSE
# =============================================================================

universe_spec = importlib.util.spec_from_file_location(
    "rolling_consistency_universe",
    UNIVERSE_FILE
)

universe_module = importlib.util.module_from_spec(universe_spec)
universe_spec.loader.exec_module(universe_module)

symbols = list(universe_module.symbols)

print(
    f"Current Nifty 500 universe symbols: "
    f"{format_console_number(len(symbols))}"
)


# =============================================================================
# CLOSE PRICE EXTRACTION
# =============================================================================

def extract_close(data):
    """
    Extract Close prices from a yfinance download.

    Supports:
        - Single-level columns
        - Multi-level columns
    """

    if data is None or data.empty:
        return pd.DataFrame()

    if isinstance(data.columns, pd.MultiIndex):

        if "Close" in data.columns.get_level_values(0):

            close = data["Close"].copy()

        elif "Close" in data.columns.get_level_values(1):

            close = data.xs(
                "Close",
                axis=1,
                level=1
            ).copy()

        else:
            return pd.DataFrame()

    else:

        if "Close" not in data.columns:
            return pd.DataFrame()

        close = data[["Close"]].copy()

        if len(close.columns) == 1:
            close.columns = [
                data.columns.name or "Close"
            ]

    return close


# =============================================================================
# DOWNLOAD MONTHLY PRICE DATA
# =============================================================================

def download_monthly_data(symbol_list):

    print_subheader("Downloading Monthly Price History")

    period_text = f"{HISTORY_YEARS}y"

    all_data = {}

    total = len(symbol_list)

    for start in range(
        0,
        total,
        DOWNLOAD_BATCH_SIZE
    ):

        batch = symbol_list[
            start:start + DOWNLOAD_BATCH_SIZE
        ]

        batch_number = (
            start // DOWNLOAD_BATCH_SIZE
        ) + 1

        total_batches = (
            total + DOWNLOAD_BATCH_SIZE - 1
        ) // DOWNLOAD_BATCH_SIZE

        print(
            f"Batch {format_console_number(batch_number)}/"
            f"{format_console_number(total_batches)} "
            f"({format_console_number(len(batch))} symbols)..."
        )

        try:

            data = yf.download(
                tickers=batch,
                period=period_text,
                interval=DATA_INTERVAL,
                auto_adjust=False,
                group_by="column",
                threads=True,
                progress=False
            )

            if data is not None and not data.empty:

                if isinstance(data.columns, pd.MultiIndex):

                    level0 = list(
                        data.columns.get_level_values(0)
                    )

                    level1 = list(
                        data.columns.get_level_values(1)
                    )

                    if "Close" in level0:

                        close_data = data["Close"]

                        for symbol in batch:

                            if symbol in close_data.columns:

                                series = (
                                    close_data[symbol]
                                    .dropna()
                                )

                                if not series.empty:
                                    all_data[symbol] = series

                    elif "Close" in level1:

                        close_data = data.xs(
                            "Close",
                            axis=1,
                            level=1
                        )

                        for symbol in batch:

                            if symbol in close_data.columns:

                                series = (
                                    close_data[symbol]
                                    .dropna()
                                )

                                if not series.empty:
                                    all_data[symbol] = series

                else:

                    if "Close" in data.columns:

                        if len(batch) == 1:

                            series = (
                                data["Close"]
                                .dropna()
                            )

                            if not series.empty:
                                all_data[batch[0]] = series

        except Exception as exc:

            print(
                f"  Batch download failed: {exc}"
            )

        # Individual retry for symbols not obtained
        for symbol in batch:

            if symbol in all_data:
                continue

            try:

                single = yf.download(
                    symbol,
                    period=period_text,
                    interval=DATA_INTERVAL,
                    auto_adjust=False,
                    progress=False,
                    threads=False
                )

                if single is not None and not single.empty:

                    close = extract_close(single)

                    if not close.empty:

                        if symbol in close.columns:

                            series = (
                                close[symbol]
                                .dropna()
                            )

                        else:

                            series = (
                                close.iloc[:, 0]
                                .dropna()
                            )

                        if not series.empty:
                            all_data[symbol] = series

            except Exception:
                pass

        print(
            f"  Collected: "
            f"{format_console_number(len(all_data))} / "
            f"{format_console_number(total)}"
        )

    failed = [
        symbol
        for symbol in symbol_list
        if symbol not in all_data
    ]

    return all_data, failed


# =============================================================================
# CALCULATE STOCK METRICS
# =============================================================================

def calculate_stock_metrics(symbol, prices):

    try:

        if prices is None or len(prices) < 13:
            return None

        prices = pd.Series(prices).copy()

        prices.index = pd.to_datetime(
            prices.index
        )

        prices = prices.sort_index()
        prices = prices.dropna()

        if len(prices) < 13:
            return None

        # ---------------------------------------------------------------------
        # 12-MONTH ROLLING RETURN
        # ---------------------------------------------------------------------

        rolling_return = (
            prices / prices.shift(12) - 1
        ) * 100

        rolling_return = rolling_return.dropna()

        if len(rolling_return) < MIN_ROLLING_PERIODS:
            return None

        median_rolling = rolling_return.median()

        if pd.isna(median_rolling):
            return None

        if median_rolling <= MEDIAN_THRESHOLD:
            return None

        # ---------------------------------------------------------------------
        # CORE METRICS
        # ---------------------------------------------------------------------

        periods = len(rolling_return)

        best_1y = rolling_return.max()
        worst_1y = rolling_return.min()

        periods_above_threshold = (
            rolling_return > MEDIAN_THRESHOLD
        ).sum()

        hit_rate = (
            periods_above_threshold / periods
        ) * 100

        positive_periods = (
            rolling_return > 0
        ).sum()

        positive_rate = (
            positive_periods / periods
        ) * 100

        negative_periods = (
            rolling_return < 0
        ).sum()

        negative_rate = (
            negative_periods / periods
        ) * 100

        # ---------------------------------------------------------------------
        # DISTRIBUTION METRICS
        # ---------------------------------------------------------------------

        p10 = rolling_return.quantile(0.10)
        p25 = rolling_return.quantile(0.25)
        p75 = rolling_return.quantile(0.75)
        p90 = rolling_return.quantile(0.90)

        std_dev = rolling_return.std()
        iqr = p75 - p25

        downside_returns = rolling_return[
            rolling_return < 0
        ]

        if len(downside_returns) > 0:

            average_downside = downside_returns.mean()
            median_downside = downside_returns.median()

        else:

            average_downside = np.nan
            median_downside = np.nan

        # ---------------------------------------------------------------------
        # LONGEST >20% STREAK
        # ---------------------------------------------------------------------

        above_threshold = (
            rolling_return > MEDIAN_THRESHOLD
        )

        longest_streak = 0
        current_streak = 0

        for value in above_threshold:

            if value:

                current_streak += 1

                if current_streak > longest_streak:
                    longest_streak = current_streak

            else:

                current_streak = 0

        # ---------------------------------------------------------------------
        # RECENT 12 MONTHS
        # ---------------------------------------------------------------------

        recent = rolling_return.tail(
            RECENT_PERIODS
        )

        recent_median = recent.median()

        recent_hit_rate = (
            recent.gt(MEDIAN_THRESHOLD).mean()
        ) * 100

        recent_positive_rate = (
            recent.gt(0).mean()
        ) * 100

        # ---------------------------------------------------------------------
        # OVERALL PRICE CAGR
        # ---------------------------------------------------------------------

        first_price = prices.iloc[0]
        last_price = prices.iloc[-1]

        first_date = prices.index[0]
        last_date = prices.index[-1]

        years = (
            (last_date - first_date).days / 365.25
        )

        if (
            first_price > 0
            and last_price > 0
            and years > 0
        ):

            overall_cagr = (
                (last_price / first_price)
                ** (1 / years)
                - 1
            ) * 100

        else:

            overall_cagr = np.nan

        # ---------------------------------------------------------------------
        # DATA PERIOD
        # ---------------------------------------------------------------------

        data_start = prices.index.min()
        data_end = prices.index.max()

        data_period_available = (
            f"{data_start.strftime('%b-%Y')} "
            f"to "
            f"{data_end.strftime('%b-%Y')}"
        )

        listing_month_year = ""

        # ---------------------------------------------------------------------
        # RESULT
        # ---------------------------------------------------------------------

        return {
            "Stock": symbol,

            "Median 1Y Rolling": median_rolling,
            "Best 1Y": best_1y,
            "Worst 1Y": worst_1y,

            "Periods Considered": periods,
            "Periods >20%": periods_above_threshold,
            "Hit Rate >20%": hit_rate,

            "Positive Periods": positive_periods,
            "Positive Rate": positive_rate,

            "Negative Periods": negative_periods,
            "Negative Rate": negative_rate,

            "P10": p10,
            "P25": p25,
            "P75": p75,
            "P90": p90,

            "1Y Std Dev": std_dev,
            "1Y IQR": iqr,

            "Average Downside": average_downside,
            "Median Downside": median_downside,

            "Longest >20% Streak": longest_streak,

            "Recent 12M Median": recent_median,
            "Recent 12M Hit Rate >20%": recent_hit_rate,
            "Recent 12M Positive Rate": recent_positive_rate,

            "Overall Price CAGR": overall_cagr,

            "Data Period Available": data_period_available,
            "Yahoo Data Start": data_start.strftime("%Y-%m-%d"),
            "Yahoo Data End": data_end.strftime("%Y-%m-%d"),

            "Listing Month-Year": listing_month_year
        }

    except Exception as exc:

        print(
            f"Metric calculation failed for {symbol}: {exc}"
        )

        return None


# =============================================================================
# CALCULATE ALL METRICS
# =============================================================================

def calculate_all_metrics(price_data):

    print_subheader("Calculating Rolling-Return Metrics")

    results = []

    total = len(price_data)

    for index, (symbol, prices) in enumerate(
        price_data.items(),
        start=1
    ):

        result = calculate_stock_metrics(
            symbol,
            prices
        )

        if result is not None:
            results.append(result)

        if index % 50 == 0 or index == total:

            print(
                f"Processed "
                f"{format_console_number(index)}/"
                f"{format_console_number(total)} "
                f"| Qualified: "
                f"{format_console_number(len(results))}"
            )

    if not results:
        return pd.DataFrame()

    return pd.DataFrame(results)


# =============================================================================
# METADATA CACHE
# =============================================================================

def load_metadata_cache():

    if not os.path.exists(METADATA_CACHE_FILE):
        return {}

    try:

        cache = pd.read_pickle(
            METADATA_CACHE_FILE
        )

        if isinstance(cache, dict):
            return cache

    except Exception as exc:

        print(
            f"Could not load metadata cache: {exc}"
        )

    return {}


def save_metadata_cache(cache):

    os.makedirs(
        RESULTS_DIR,
        exist_ok=True
    )

    try:

        pd.to_pickle(
            cache,
            METADATA_CACHE_FILE
        )

    except Exception as exc:

        print(
            f"Could not save metadata cache: {exc}"
        )


# =============================================================================
# STOCK METADATA
# =============================================================================

def get_stock_metadata(symbol):

    try:

        ticker = yf.Ticker(symbol)
        info = ticker.info

        return {
            "Sector": info.get("sector", ""),
            "Industry": info.get("industry", ""),
            "Market Cap": safe_float(
                info.get("marketCap")
            )
        }

    except Exception:

        return {
            "Sector": "",
            "Industry": "",
            "Market Cap": np.nan
        }


def add_stock_metadata(df):

    print_subheader(
        "Adding Sector, Industry and Market Capitalisation"
    )

    if df.empty:
        return df

    cache = load_metadata_cache()

    symbols_to_fetch = [
        symbol
        for symbol in df["Stock"]
        if symbol not in cache
    ]

    print(
        f"Metadata already cached: "
        f"{format_console_number(len(df) - len(symbols_to_fetch))}"
    )

    print(
        f"Metadata to fetch: "
        f"{format_console_number(len(symbols_to_fetch))}"
    )

    if symbols_to_fetch:

        with ThreadPoolExecutor(
            max_workers=METADATA_WORKERS
        ) as executor:

            futures = {
                executor.submit(
                    get_stock_metadata,
                    symbol
                ): symbol
                for symbol in symbols_to_fetch
            }

            for future in as_completed(futures):

                symbol = futures[future]

                try:

                    cache[symbol] = future.result()

                except Exception:

                    cache[symbol] = {
                        "Sector": "",
                        "Industry": "",
                        "Market Cap": np.nan
                    }

        save_metadata_cache(cache)

    sectors = []
    industries = []
    market_caps = []

    for symbol in df["Stock"]:

        metadata = cache.get(
            symbol,
            {}
        )

        sectors.append(
            metadata.get("Sector", "")
        )

        industries.append(
            metadata.get("Industry", "")
        )

        market_caps.append(
            metadata.get("Market Cap", np.nan)
        )

    metadata_df = pd.DataFrame({
        "Sector": sectors,
        "Industry": industries,
        "Market Price": np.nan,
        "Market Cap (In Cr)": [
            (
                value / 10_000_000
                if pd.notna(value)
                else np.nan
            )
            for value in market_caps
        ]
    })

    stock_position = df.columns.get_loc(
        "Stock"
    )

    left = df.iloc[
        :,
        :stock_position + 1
    ]

    right = df.iloc[
        :,
        stock_position + 1:
    ]

    result = pd.concat(
        [
            left.reset_index(drop=True),
            metadata_df.reset_index(drop=True),
            right.reset_index(drop=True)
        ],
        axis=1
    )

    return result


# =============================================================================
# CURRENT DAILY DATA
# =============================================================================

def download_current_daily_data(symbol_list):

    print_subheader(
        "Downloading Current Daily Market Data"
    )

    daily_data = {}

    total = len(symbol_list)

    for start in range(
        0,
        total,
        DOWNLOAD_BATCH_SIZE
    ):

        batch = symbol_list[
            start:start + DOWNLOAD_BATCH_SIZE
        ]

        try:

            data = yf.download(
                tickers=batch,
                period=EMA_HISTORY_PERIOD,
                interval="1d",
                auto_adjust=False,
                group_by="column",
                threads=True,
                progress=False
            )

            if data is None or data.empty:
                continue

            if isinstance(data.columns, pd.MultiIndex):

                if "Close" in data.columns.get_level_values(0):

                    close_data = data["Close"]

                    for symbol in batch:

                        if symbol in close_data.columns:

                            series = (
                                close_data[symbol]
                                .dropna()
                            )

                            if not series.empty:
                                daily_data[symbol] = series

            else:

                if (
                    "Close" in data.columns
                    and len(batch) == 1
                ):

                    series = (
                        data["Close"]
                        .dropna()
                    )

                    if not series.empty:
                        daily_data[batch[0]] = series

        except Exception:
            pass

        print(
            f"Daily data collected: "
            f"{format_console_number(len(daily_data))} / "
            f"{format_console_number(total)}"
        )

    failed = [
        symbol
        for symbol in symbol_list
        if symbol not in daily_data
    ]

    return daily_data, failed


# =============================================================================
# EMA BREADTH LABEL
# =============================================================================

def breadth_label(value):

    if pd.isna(value):
        return "Unavailable"

    if value > 70:
        return "High"

    if value >= 50:
        return "Medium"

    return "Low"


# =============================================================================
# NIFTY 500 EMA MARKET BREADTH
# =============================================================================

def calculate_nifty500_ema_breadth(
    daily_data,
    universe_symbols
):

    print_header(
        "CALCULATING NIFTY 500 EMA MARKET BREADTH"
    )

    program_date = pd.Timestamp.now().normalize()

    print(
        f"Program run date: "
        f"{program_date.strftime('%Y-%m-%d')}"
    )

    if not daily_data:
        return pd.DataFrame()

    latest_dates = []

    for symbol, series in daily_data.items():

        if series is None or series.empty:
            continue

        latest_dates.append(
            pd.to_datetime(series.index.max())
        )

    if not latest_dates:
        return pd.DataFrame()

    latest_available_date = max(
        latest_dates
    )

    print(
        f"Latest available market-data date: "
        f"{latest_available_date.strftime('%Y-%m-%d')}"
    )

    breadth_rows = []

    for period in EMA_PERIODS:

        above = 0
        below = 0
        unavailable = 0

        for symbol in universe_symbols:

            series = daily_data.get(symbol)

            if series is None or series.empty:

                unavailable += 1
                continue

            series = series.dropna()

            if len(series) < period:

                unavailable += 1
                continue

            latest_price = series.iloc[-1]

            ema = (
                series
                .ewm(
                    span=period,
                    adjust=False
                )
                .mean()
                .iloc[-1]
            )

            if pd.isna(latest_price) or pd.isna(ema):

                unavailable += 1

            elif latest_price > ema:

                above += 1

            else:

                below += 1

        denominator = above + below

        if denominator > 0:

            percentage = (
                above / denominator
            ) * 100

        else:

            percentage = np.nan

        status = breadth_label(
            percentage
        )

        breadth_rows.append({
            "EMA": f"{period}D EMA",
            "Stocks Above EMA": above,
            "Stocks Below EMA": below,
            "Unavailable / Excluded": unavailable,
            "Stocks Considered": denominator,
            "Breadth %": percentage,
            "Breadth": status
        })

        print(
            f"{period}D EMA: "
            f"{format_console_number(above)} / "
            f"{format_console_number(denominator)} "
            f"({percentage:.2f}%) "
            f"| {status}"
        )

    breadth_df = pd.DataFrame(
        breadth_rows
    )

    status_map = {
        row["EMA"]: row["Breadth"]
        for _, row in breadth_df.iterrows()
    }

    status_20 = status_map.get(
        "20D EMA",
        "Unavailable"
    )

    status_50 = status_map.get(
        "50D EMA",
        "Unavailable"
    )

    status_200 = status_map.get(
        "200D EMA",
        "Unavailable"
    )

    if (
        status_20 == "High"
        and status_50 == "High"
        and status_200 == "High"
    ):

        regime = "Strong Bullish"

    elif (
        status_20 == "High"
        and status_50 == "High"
        and status_200 in ["Medium", "High"]
    ):

        regime = "Bullish"

    elif (
        status_20 == "Low"
        and status_50 == "Low"
        and status_200 == "Low"
    ):

        regime = "Strong Bearish"

    elif (
        status_200 == "Low"
        and not (
            status_20 == "High"
            and status_50 == "High"
        )
    ):

        regime = "Bearish"

    else:

        regime = "Transitional"

    print()
    print(
        f"Market regime: {regime}"
    )

    return breadth_df


# =============================================================================
# ADD CURRENT PRICES
# =============================================================================

def add_current_prices(
    df,
    daily_data
):

    if df.empty:
        return df

    current_prices = []

    for symbol in df["Stock"]:

        series = daily_data.get(symbol)

        if series is None or series.empty:

            current_prices.append(np.nan)

        else:

            current_prices.append(
                safe_float(
                    series.dropna().iloc[-1]
                )
            )

    df = df.copy()

    df["Market Price"] = current_prices

    return df


# =============================================================================
# RANKING
# =============================================================================

def rank_dataframe(
    df,
    sort_columns,
    ascending=None
):

    if df.empty:
        return df

    if ascending is None:

        ascending = [
            False
            for _ in sort_columns
        ]

    return (
        df.sort_values(
            by=sort_columns,
            ascending=ascending,
            na_position="last"
        )
        .reset_index(drop=True)
    )


def add_rank_column(df):
    """
    Add Rank as the first column.

    Rank represents the final order of the dataframe.
    """

    if df.empty:
        return df

    result = df.copy()

    if "Rank" in result.columns:

        result = result.drop(
            columns=["Rank"]
        )

    result.insert(
        0,
        "Rank",
        range(
            1,
            len(result) + 1
        )
    )

    return result


# =============================================================================
# LIST 5 — OVERALL BALANCED SCORE
# =============================================================================

def create_list5_overall_balanced(df):

    """
    Create List 5 using a weighted percentile composite.

    Components:
        50% Median 1Y Rolling
        25% Hit Rate >20%
        15% P10
        10% Worst 1Y
    """

    if df.empty:
        return pd.DataFrame()

    result = df.copy()

    # -------------------------------------------------------------------------
    # Percentile ranks
    # -------------------------------------------------------------------------

    result["Median Percentile"] = (
        result["Median 1Y Rolling"]
        .rank(
            method="average",
            pct=True
        )
        * 100
    )

    result["Hit Rate Percentile"] = (
        result["Hit Rate >20%"]
        .rank(
            method="average",
            pct=True
        )
        * 100
    )

    result["P10 Percentile"] = (
        result["P10"]
        .rank(
            method="average",
            pct=True
        )
        * 100
    )

    result["Worst 1Y Percentile"] = (
        result["Worst 1Y"]
        .rank(
            method="average",
            pct=True
        )
        * 100
    )

    # -------------------------------------------------------------------------
    # Weighted composite
    # -------------------------------------------------------------------------

    result["Overall Balanced Score"] = (
        result["Median Percentile"]
        * LIST5_MEDIAN_WEIGHT

        + result["Hit Rate Percentile"]
        * LIST5_HIT_RATE_WEIGHT

        + result["P10 Percentile"]
        * LIST5_P10_WEIGHT

        + result["Worst 1Y Percentile"]
        * LIST5_WORST_WEIGHT
    )

    # -------------------------------------------------------------------------
    # Rank by composite score.
    # -------------------------------------------------------------------------

    result = rank_dataframe(
        result,
        [
            "Overall Balanced Score",
            "Median 1Y Rolling",
            "Hit Rate >20%",
            "P10",
            "Worst 1Y",
            "Periods Considered"
        ],
        [
            False,
            False,
            False,
            False,
            False,
            False
        ]
    ).head(TOP_N)

    # Rank must be first column.
    result = add_rank_column(
        result
    )

    return result


# =============================================================================
# CREATE ALL RANKINGS
# =============================================================================

def create_rankings(df):

    if df.empty:

        return {
            "typical_return": pd.DataFrame(),
            "consistency": pd.DataFrame(),
            "downside": pd.DataFrame(),
            "balanced": pd.DataFrame(),
            "overall_balanced": pd.DataFrame()
        }

    # =========================================================================
    # LIST 1
    # =========================================================================

    typical_return = rank_dataframe(
        df.copy(),
        [
            "Median 1Y Rolling",
            "Hit Rate >20%",
            "P10",
            "Periods Considered"
        ],
        [
            False,
            False,
            False,
            False
        ]
    ).head(TOP_N)

    typical_return = add_rank_column(
        typical_return
    )

    # =========================================================================
    # LIST 2
    # =========================================================================

    consistency = rank_dataframe(
        df.copy(),
        [
            "Hit Rate >20%",
            "Median 1Y Rolling",
            "P10",
            "Worst 1Y",
            "Periods Considered"
        ],
        [
            False,
            False,
            False,
            False,
            False
        ]
    ).head(TOP_N)

    consistency = add_rank_column(
        consistency
    )

    # =========================================================================
    # LIST 3
    # =========================================================================

    downside = rank_dataframe(
        df.copy(),
        [
            "P10",
            "Worst 1Y",
            "Hit Rate >20%",
            "Periods Considered",
            "Median 1Y Rolling"
        ],
        [
            False,
            False,
            False,
            False,
            False
        ]
    ).head(TOP_N)

    downside = add_rank_column(
        downside
    )

    # =========================================================================
    # LIST 4
    # =========================================================================

    balanced = rank_dataframe(
        df.copy(),
        [
            "Hit Rate >20%",
            "P10",
            "Worst 1Y",
            "Periods Considered",
            "Median 1Y Rolling"
        ],
        [
            False,
            False,
            False,
            False,
            False
        ]
    ).head(TOP_N)

    balanced = add_rank_column(
        balanced
    )

    # =========================================================================
    # LIST 5
    # =========================================================================

    overall_balanced = create_list5_overall_balanced(
        df
    )

    return {
        "typical_return": typical_return,
        "consistency": consistency,
        "downside": downside,
        "balanced": balanced,
        "overall_balanced": overall_balanced
    }


# =============================================================================
# DISPLAY RANKING
# =============================================================================

def display_ranking(
    df,
    title,
    question,
    insights,
    include_score=False
):

    print_header(title)

    print(
        f"WHAT THIS LIST ANSWERS:\n"
        f"{question}"
    )

    print()

    print(
        "WHAT TO LOOK FOR:"
    )

    for item in insights:
        print(f"  • {item}")

    print()

    if df.empty:

        print("No stocks qualified for this list.")
        return

    display_columns = [
        "Rank",
        "Stock",
        "Sector",
        "Industry",
        "Market Price",
        "Market Cap (In Cr)",
        "Median 1Y Rolling",
        "Hit Rate >20%",
        "P10",
        "Worst 1Y",
        "Periods Considered"
    ]

    if include_score:

        display_columns = [
            "Rank",
            "Stock",
            "Sector",
            "Industry",
            "Market Price",
            "Market Cap (In Cr)",
            "Overall Balanced Score",
            "Median 1Y Rolling",
            "Hit Rate >20%",
            "P10",
            "Worst 1Y",
            "Periods Considered"
        ]

    display_columns = [
        column
        for column in display_columns
        if column in df.columns
    ]

    display_df = df[
        display_columns
    ].copy()

    if "Market Cap (In Cr)" in display_df.columns:

        display_df["Market Cap (In Cr)"] = (
            display_df["Market Cap (In Cr)"]
            .apply(format_indian_number)
        )

    if "Periods Considered" in display_df.columns:

        display_df["Periods Considered"] = (
            display_df["Periods Considered"]
            .apply(format_console_number)
        )

    if "Overall Balanced Score" in display_df.columns:

        display_df["Overall Balanced Score"] = (
            display_df["Overall Balanced Score"]
            .apply(
                lambda value:
                f"{value:.2f}"
                if pd.notna(value)
                else ""
            )
        )

    print(
        display_df.to_string(
            index=False
        )
    )


# =============================================================================
# EXCEL FORMATTING
# =============================================================================

def format_excel_sheet(
    writer,
    sheet_name,
    dataframe
):

    workbook = writer.book
    worksheet = writer.sheets[sheet_name]

    worksheet.freeze_panes = "A2"

    if len(dataframe.columns) > 0:

        worksheet.auto_filter.ref = (
            worksheet.dimensions
        )

    for cell in worksheet[1]:

        cell.font = cell.font.copy(
            bold=True
        )

    columns = list(
        dataframe.columns
    )

    for index, column in enumerate(
        columns,
        start=1
    ):

        letter = (
            __import__("openpyxl")
            .utils
            .get_column_letter(index)
        )

        max_length = len(
            str(column)
        )

        for value in dataframe[column].head(1000):

            if pd.isna(value):
                continue

            max_length = max(
                max_length,
                len(str(value))
            )

        width = min(
            max(max_length + 2, 12),
            40
        )

        worksheet.column_dimensions[
            letter
        ].width = width

        if (
            "Rolling" in column
            or "Rate" in column
            or column in [
                "Best 1Y",
                "Worst 1Y",
                "P10",
                "P25",
                "P75",
                "P90",
                "1Y Std Dev",
                "1Y IQR",
                "Average Downside",
                "Median Downside",
                "Overall Price CAGR",
                "Breadth %"
            ]
        ):

            for cell in worksheet[
                letter
            ][1:]:

                cell.number_format = (
                    '0.00"%"'
                )

        if column == "Overall Balanced Score":

            for cell in worksheet[
                letter
            ][1:]:

                cell.number_format = (
                    '0.00'
                )

        if column in [
            "Median Percentile",
            "Hit Rate Percentile",
            "P10 Percentile",
            "Worst 1Y Percentile"
        ]:

            for cell in worksheet[
                letter
            ][1:]:

                cell.number_format = (
                    '0.00'
                )

        if column == "Market Price":

            for cell in worksheet[
                letter
            ][1:]:

                cell.number_format = (
                    '₹#,##0.00'
                )

        if column == "Market Cap (In Cr)":

            for row_number in range(
                2,
                len(dataframe) + 2
            ):

                original_value = dataframe.iloc[
                    row_number - 2
                ][column]

                cell = worksheet.cell(
                    row=row_number,
                    column=index
                )

                if pd.isna(original_value):

                    cell.value = ""

                else:

                    cell.value = format_indian_number(
                        original_value
                    )


# =============================================================================
# WRITE EXCEL
# =============================================================================

def write_excel(
    research_df,
    rankings,
    breadth_df,
    rolling_returns_df,
    universe_df,
    rejected_df,
    failed_downloads_df
):

    print_subheader(
        "Writing Excel Research Workbook"
    )

    os.makedirs(
        RESULTS_DIR,
        exist_ok=True
    )

    summary_rows = [
        {
            "Section": "Research Purpose",
            "Description":
                "Historical analysis of Nifty 500 1-year rolling-return "
                "consistency."
        },
        {
            "Section": "Universe",
            "Description":
                "Latest Nifty 500 universe refreshed through trade_data.py."
        },
        {
            "Section": "History",
            "Description":
                f"{HISTORY_YEARS} years of Yahoo Finance monthly price data."
        },
        {
            "Section": "Rolling Return",
            "Description":
                "12-month rolling return calculated from monthly closing prices."
        },
        {
            "Section": "Minimum History",
            "Description":
                f"At least {MIN_ROLLING_PERIODS} rolling observations."
        },
        {
            "Section": "Qualification Rule",
            "Description":
                f"Median 1Y rolling return must be greater than "
                f"{MEDIAN_THRESHOLD:.0f}%."
        },
        {
            "Section": "List 1 — Typical Return Leaders",
            "Description":
                "Highest typical 1-year rolling return. Primary metric = "
                "Median 1Y Rolling."
        },
        {
            "Section": "List 2 — Most Consistent >20%",
            "Description":
                "Stocks that exceeded 20% most frequently. Primary metric = "
                "Hit Rate >20%."
        },
        {
            "Section": "List 3 — Downside Stability",
            "Description":
                "Stocks with stronger lower-end rolling-return characteristics. "
                "Primary metric = P10."
        },
        {
            "Section": "List 4 — Balanced Candidates",
            "Description":
                "Qualified stocks prioritized by hit rate and then downside "
                "characteristics. This is a priority-order ranking."
        },
        {
            "Section": "List 5 — Overall Balanced Leaders",
            "Description":
                "Weighted mathematical composite using percentile ranks "
                "of Median 1Y Rolling, Hit Rate >20%, P10 and Worst 1Y."
        },
        {
            "Section": "List 5 Composite Weights",
            "Description":
                "Median 50% + Hit Rate >20% 25% + P10 15% + Worst 1Y 10%."
        },
        {
            "Section": "List 5 Method",
            "Description":
                "Each metric is converted to a percentile rank across all "
                "qualified stocks before applying the weighted composite."
        },
        {
            "Section": "Composite Score",
            "Description":
                "Lists 1–4 use NO composite score. List 5 is the only list "
                "that uses a composite score."
        },
        {
            "Section": "Historical Interpretation",
            "Description":
                "Past rolling-return behavior is descriptive and does not "
                "guarantee future performance."
        },
        {
            "Section": "Median 1Y Rolling",
            "Description":
                "Typical 1-year rolling return across all available monthly "
                "observations."
        },
        {
            "Section": "Hit Rate >20%",
            "Description":
                "Percentage of rolling 1-year periods whose return exceeded 20%."
        },
        {
            "Section": "P10",
            "Description":
                "10th percentile of rolling 1-year returns; higher values "
                "indicate a stronger lower-tail history."
        },
        {
            "Section": "Worst 1Y",
            "Description":
                "Single worst observed 1-year rolling return; a less-negative "
                "value indicates a better historical worst case."
        },
        {
            "Section": "Periods Considered",
            "Description":
                "Number of rolling 1-year observations used; more observations "
                "provide more historical evidence."
        },
        {
            "Section": "Recent 12M Metrics",
            "Description":
                "Recent behavior over the latest 12 rolling observations; "
                "different from full-history behavior."
        },
        {
            "Section": "Overall Price CAGR",
            "Description":
                "Start-to-end CAGR over the available monthly price history; "
                "different from rolling-return consistency."
        },
        {
            "Section": "Data Period Available",
            "Description":
                "Yahoo Finance price-data availability, NOT the official "
                "NSE listing date."
        },
        {
            "Section": "Listing Month-Year",
            "Description":
                "Blank because trade_data.py supplies symbols but not official "
                "listing dates."
        },
        {
            "Section": "Number Formatting",
            "Description":
                "Large absolute numbers such as Market Cap are displayed using "
                "Indian grouping, e.g. 12,12,34,567."
        }
    ]

    summary_df = pd.DataFrame(
        summary_rows
    )

    sheet_names = {
        "typical_return":
            "1 Typical Return Leaders",

        "consistency":
            "2 Most Consistent >20%",

        "downside":
            "3 Downside Stability",

        "balanced":
            "4 Balanced Candidates",

        "overall_balanced":
            "5 Overall Balanced"
    }

    with pd.ExcelWriter(
        OUTPUT_FILE,
        engine="openpyxl"
    ) as writer:

        summary_df.to_excel(
            writer,
            sheet_name="Summary",
            index=False
        )

        for key, sheet_name in sheet_names.items():

            rankings[key].to_excel(
                writer,
                sheet_name=sheet_name,
                index=False
            )

        research_df.to_excel(
            writer,
            sheet_name="Full Research Data",
            index=False
        )

        breadth_df.to_excel(
            writer,
            sheet_name="EMA Market Breadth",
            index=False
        )

        rolling_returns_df.to_excel(
            writer,
            sheet_name="Rolling Returns",
            index=False
        )

        universe_df.to_excel(
            writer,
            sheet_name="Universe",
            index=False
        )

        rejected_df.to_excel(
            writer,
            sheet_name="Rejected",
            index=False
        )

        failed_downloads_df.to_excel(
            writer,
            sheet_name="Failed Downloads",
            index=False
        )

        format_excel_sheet(
            writer,
            "Summary",
            summary_df
        )

        for key, sheet_name in sheet_names.items():

            format_excel_sheet(
                writer,
                sheet_name,
                rankings[key]
            )

        format_excel_sheet(
            writer,
            "Full Research Data",
            research_df
        )

        format_excel_sheet(
            writer,
            "EMA Market Breadth",
            breadth_df
        )

        format_excel_sheet(
            writer,
            "Rolling Returns",
            rolling_returns_df
        )

        format_excel_sheet(
            writer,
            "Universe",
            universe_df
        )

        format_excel_sheet(
            writer,
            "Rejected",
            rejected_df
        )

        format_excel_sheet(
            writer,
            "Failed Downloads",
            failed_downloads_df
        )

    print()
    print(
        f"Excel file created:\n{OUTPUT_FILE}"
    )


# =============================================================================
# BREADTH SUMMARY VALUES
# =============================================================================

def breadth_value(
    breadth_df,
    ema_name
):

    if breadth_df.empty:
        return np.nan

    rows = breadth_df[
        breadth_df["EMA"] == ema_name
    ]

    if rows.empty:
        return np.nan

    return safe_float(
        rows.iloc[0]["Breadth %"]
    )


def breadth_status(
    breadth_df,
    ema_name
):

    if breadth_df.empty:
        return "Unavailable"

    rows = breadth_df[
        breadth_df["EMA"] == ema_name
    ]

    if rows.empty:
        return "Unavailable"

    return rows.iloc[0]["Breadth"]


# =============================================================================
# FINAL COLUMN ORDER
# =============================================================================

def finalize_column_order(df):

    if df.empty:
        return df

    preferred = [
        "Stock",
        "Sector",
        "Industry",
        "Market Price",
        "Market Cap (In Cr)",

        "Overall Balanced Score",

        "Median 1Y Rolling",
        "Hit Rate >20%",

        "Best 1Y",
        "Worst 1Y",

        "P10",
        "P25",
        "P75",
        "P90",

        "Periods Considered",
        "Periods >20%",

        "Positive Periods",
        "Positive Rate",

        "Negative Periods",
        "Negative Rate",

        "1Y Std Dev",
        "1Y IQR",

        "Average Downside",
        "Median Downside",

        "Longest >20% Streak",

        "Recent 12M Median",
        "Recent 12M Hit Rate >20%",
        "Recent 12M Positive Rate",

        "Overall Price CAGR",

        "Data Period Available",
        "Yahoo Data Start",
        "Yahoo Data End",
        "Listing Month-Year"
    ]

    existing = [
        column
        for column in preferred
        if column in df.columns
    ]

    remaining = [
        column
        for column in df.columns
        if column not in existing
    ]

    return df[
        existing + remaining
    ]


# =============================================================================
# MAIN
# =============================================================================

def main():

    warnings.filterwarnings(
        "ignore"
    )

    print_header(
        "ROLLING CONSISTENCY LAB — RESEARCH RUN"
    )

    print(
        f"Run timestamp: "
        f"{RUN_TIMESTAMP.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    print()
    print("Research configuration:")

    print(
        f"  Historical data      : "
        f"{format_console_number(HISTORY_YEARS)} years"
    )

    print(
        f"  Interval             : {DATA_INTERVAL}"
    )

    print(
        f"  Rolling return       : "
        f"{format_console_number(12)} months"
    )

    print(
        f"  Minimum observations : "
        f"{format_console_number(MIN_ROLLING_PERIODS)}"
    )

    print(
        f"  Median threshold     : "
        f"> {MEDIAN_THRESHOLD:.0f}%"
    )

    print(
        f"  Ranking list size    : "
        f"Top {format_console_number(TOP_N)}"
    )

    print()
    print(
        "  List 5 composite     : "
        "50% Median + 25% Hit Rate + 15% P10 + 10% Worst 1Y"
    )

    # -------------------------------------------------------------------------
    # MONTHLY DATA
    # -------------------------------------------------------------------------

    price_data, failed_downloads = (
        download_monthly_data(
            symbols
        )
    )

    print()

    print(
        f"Successful monthly price downloads: "
        f"{format_console_number(len(price_data))}"
    )

    print(
        f"Failed monthly price downloads: "
        f"{format_console_number(len(failed_downloads))}"
    )

    # -------------------------------------------------------------------------
    # METRICS
    # -------------------------------------------------------------------------

    research_df = calculate_all_metrics(
        price_data
    )

    if research_df.empty:

        raise RuntimeError(
            "No stocks qualified for the research."
        )

    print()

    print(
        f"Qualified stocks: "
        f"{format_console_number(len(research_df))}"
    )

    # -------------------------------------------------------------------------
    # METADATA
    # -------------------------------------------------------------------------

    research_df = add_stock_metadata(
        research_df
    )

    # -------------------------------------------------------------------------
    # CURRENT DAILY DATA
    # -------------------------------------------------------------------------

    daily_data, daily_failed = (
        download_current_daily_data(
            symbols
        )
    )

    # -------------------------------------------------------------------------
    # CURRENT PRICES
    # -------------------------------------------------------------------------

    research_df = add_current_prices(
        research_df,
        daily_data
    )

    # -------------------------------------------------------------------------
    # EMA BREADTH
    # -------------------------------------------------------------------------

    breadth_df = (
        calculate_nifty500_ema_breadth(
            daily_data,
            symbols
        )
    )

    # -------------------------------------------------------------------------
    # FINAL COLUMN ORDER
    # -------------------------------------------------------------------------

    research_df = finalize_column_order(
        research_df
    )

    # -------------------------------------------------------------------------
    # RANKINGS
    # -------------------------------------------------------------------------

    rankings = create_rankings(
        research_df
    )

    # -------------------------------------------------------------------------
    # CONSOLE DISPLAY — LIST 1
    # -------------------------------------------------------------------------

    display_ranking(
        rankings["typical_return"],
        "LIST 1 — TYPICAL RETURN LEADERS",
        "Which qualified stocks have the highest typical 1-year rolling return?",
        [
            "Start with Median 1Y Rolling — this is the primary ranking metric.",
            "Then check Hit Rate >20% — how frequently the stock cleared 20%.",
            "Check P10 — how strong the lower end of its rolling-return history was.",
            "Check Periods Considered — more observations provide more historical evidence.",
            "A high median does not automatically mean high consistency."
        ]
    )

    # -------------------------------------------------------------------------
    # CONSOLE DISPLAY — LIST 2
    # -------------------------------------------------------------------------

    display_ranking(
        rankings["consistency"],
        "LIST 2 — MOST CONSISTENT >20% RETURNS",
        "Which qualified stocks achieved a 1-year rolling return above 20% most frequently?",
        [
            "Start with Hit Rate >20% — this is the primary ranking metric.",
            "Then check Median 1Y Rolling — the typical return remains important.",
            "Check P10 — whether the lower part of the return distribution was stronger.",
            "Check Worst 1Y — the single weakest rolling 1-year observation.",
            "Check Periods Considered — more history gives more observations behind the result."
        ]
    )

    # -------------------------------------------------------------------------
    # CONSOLE DISPLAY — LIST 3
    # -------------------------------------------------------------------------

    display_ranking(
        rankings["downside"],
        "LIST 3 — DOWNSIDE STABILITY LEADERS",
        "Which qualified stocks have the stronger lower-end rolling-return profile?",
        [
            "Start with P10 — this is the primary ranking metric.",
            "Higher P10 means the lower 10% portion of rolling outcomes was stronger.",
            "Then check Worst 1Y — less-negative values indicate a better historical worst case.",
            "Check Hit Rate >20% — downside stability alone does not mean frequent >20% returns.",
            "Check Periods Considered — confirm that the evidence base is substantial.",
            "Median 1Y Rolling is deliberately lower in this ranking priority."
        ]
    )

    # -------------------------------------------------------------------------
    # CONSOLE DISPLAY — LIST 4
    # -------------------------------------------------------------------------

    display_ranking(
        rankings["balanced"],
        "LIST 4 — BALANCED CONSISTENCY CANDIDATES",
        "Which qualified stocks combine frequent >20% rolling returns with stronger downside characteristics?",
        [
            "Start with Hit Rate >20% — frequency of >20% returns is the first priority.",
            "Then check P10 — the lower-tail profile is the second priority.",
            "Check Worst 1Y — how bad the weakest rolling year was.",
            "Check Periods Considered — assess how much historical evidence exists.",
            "Finally check Median 1Y Rolling — typical return is a later tie-break priority.",
            "This is a priority-order ranking, NOT a composite score."
        ]
    )

    # -------------------------------------------------------------------------
    # CONSOLE DISPLAY — LIST 5
    # -------------------------------------------------------------------------

    display_ranking(
        rankings["overall_balanced"],
        "LIST 5 — OVERALL BALANCED LEADERS",
        "Which qualified stocks have the strongest overall combination of "
        "typical return, >20% consistency and downside characteristics?",
        [
            "This is the only list using a mathematical composite score.",
            "Median 1Y Rolling contributes 50%.",
            "Hit Rate >20% contributes 25%.",
            "P10 contributes 15%.",
            "Worst 1Y contributes 10%.",
            "Each metric is first converted to a percentile rank across all qualified stocks.",
            "Higher Overall Balanced Score means stronger relative performance across all four metrics.",
            "This is still historical descriptive research and does not predict future returns."
        ],
        include_score=True
    )

    # -------------------------------------------------------------------------
    # ROLLING RETURNS DATASET
    # -------------------------------------------------------------------------

    rolling_returns_rows = []

    for symbol, prices in price_data.items():

        try:

            prices = pd.Series(prices).dropna()

            prices.index = pd.to_datetime(
                prices.index
            )

            prices = prices.sort_index()

            rolling = (
                prices / prices.shift(12) - 1
            ) * 100

            rolling = rolling.dropna()

            for date, value in rolling.items():

                rolling_returns_rows.append({
                    "Stock": symbol,
                    "Date": date,
                    "1Y Rolling Return": value
                })

        except Exception:
            continue

    rolling_returns_df = pd.DataFrame(
        rolling_returns_rows
    )

    # -------------------------------------------------------------------------
    # UNIVERSE DATASET
    # -------------------------------------------------------------------------

    universe_df = pd.DataFrame({
        "Stock": symbols
    })

    # -------------------------------------------------------------------------
    # REJECTED DATASET
    # -------------------------------------------------------------------------

    qualified_symbols = set(
        research_df["Stock"]
    )

    rejected_rows = []

    for symbol in symbols:

        if symbol in qualified_symbols:
            continue

        prices = price_data.get(symbol)

        if prices is None or len(prices) < 13:

            reason = (
                "Insufficient price history"
            )

        else:

            prices = pd.Series(
                prices
            ).dropna()

            rolling = (
                prices / prices.shift(12)
                - 1
            ).dropna() * 100

            if len(rolling) < MIN_ROLLING_PERIODS:

                reason = (
                    "Fewer than minimum rolling periods"
                )

            elif rolling.median() <= MEDIAN_THRESHOLD:

                reason = (
                    f"Median 1Y rolling return "
                    f"<= {MEDIAN_THRESHOLD:.0f}%"
                )

            else:

                reason = (
                    "Did not qualify"
                )

        rejected_rows.append({
            "Stock": symbol,
            "Reason": reason
        })

    rejected_df = pd.DataFrame(
        rejected_rows
    )

    # -------------------------------------------------------------------------
    # FAILED DOWNLOADS
    # -------------------------------------------------------------------------

    failed_downloads_df = pd.DataFrame({
        "Stock": failed_downloads
    })

    # -------------------------------------------------------------------------
    # WRITE EXCEL
    # -------------------------------------------------------------------------

    write_excel(
        research_df,
        rankings,
        breadth_df,
        rolling_returns_df,
        universe_df,
        rejected_df,
        failed_downloads_df
    )

    # -------------------------------------------------------------------------
    # FINAL SUMMARY
    # -------------------------------------------------------------------------

    print_header(
        "RESEARCH RUN SUMMARY"
    )

    print(
        f"Current Nifty 500 universe : "
        f"{format_console_number(len(symbols))}"
    )

    print(
        f"Successful monthly downloads : "
        f"{format_console_number(len(price_data))}"
    )

    print(
        f"Failed monthly downloads     : "
        f"{format_console_number(len(failed_downloads))}"
    )

    print(
        f"Qualified stocks              : "
        f"{format_console_number(len(research_df))}"
    )

    print(
        f"Minimum rolling periods       : "
        f"{format_console_number(MIN_ROLLING_PERIODS)}"
    )

    print(
        f"Median threshold              : "
        f"> {MEDIAN_THRESHOLD:.0f}%"
    )

    if not breadth_df.empty:

        print()
        print(
            "Current Nifty 500 EMA breadth:"
        )

        for _, row in breadth_df.iterrows():

            print(
                f"  {row['EMA']}: "
                f"{format_console_number(row['Stocks Above EMA'])} / "
                f"{format_console_number(row['Stocks Considered'])} "
                f"({row['Breadth %']:.2f}%) "
                f"| {row['Breadth']}"
            )

    # -------------------------------------------------------------------------
    # RANKING INTERPRETATION GUIDE
    # -------------------------------------------------------------------------

    print_header(
        "HOW TO INTERPRET THE FIVE LISTS"
    )

    print(
        "1. Typical Return Leaders"
    )

    print(
        "   Main question: What is the typical 1-year rolling return?"
    )

    print(
        "   Primary metric: Median 1Y Rolling"
    )

    print()

    print(
        "2. Most Consistent >20% Returns"
    )

    print(
        "   Main question: How often did the stock exceed 20% over a rolling year?"
    )

    print(
        "   Primary metric: Hit Rate >20%"
    )

    print()

    print(
        "3. Downside Stability Leaders"
    )

    print(
        "   Main question: How strong was the lower end of the rolling-return distribution?"
    )

    print(
        "   Primary metric: P10"
    )

    print()

    print(
        "4. Balanced Consistency Candidates"
    )

    print(
        "   Main question: Which qualified stocks combine frequent >20% outcomes "
        "with stronger downside characteristics?"
    )

    print(
        "   Priority: Hit Rate >20% -> P10 -> Worst 1Y -> History -> Median"
    )

    print(
        "   This is a priority-order ranking, NOT a composite score."
    )

    print()

    print(
        "5. Overall Balanced Leaders"
    )

    print(
        "   Main question: Which stocks have the strongest overall combination "
        "across return, consistency and downside metrics?"
    )

    print(
        "   Composite: 50% Median + 25% Hit Rate + 15% P10 + 10% Worst 1Y"
    )

    print(
        "   Each component is percentile-ranked across all qualified stocks."
    )

    print(
        "   Higher Overall Balanced Score means stronger relative performance "
        "across all four dimensions."
    )

    print()

    print(
        "IMPORTANT: List 5 is a mathematical research ranking, "
        "not a prediction or guarantee of future performance."
    )

    # -------------------------------------------------------------------------
    # RUNTIME
    # -------------------------------------------------------------------------

    runtime_seconds = time.time() - START_TIME

    print()
    print(
        f"Total program runtime: "
        f"{runtime_seconds:.2f} seconds"
    )

    print()
    print(
        "Output file:"
    )

    print(
        OUTPUT_FILE
    )

    print()
    print("=" * 80)
    print("ROLLING CONSISTENCY LAB — COMPLETED")
    print("=" * 80)
    


# =============================================================================
# RUN
# =============================================================================

if __name__ == "__main__":
    main()