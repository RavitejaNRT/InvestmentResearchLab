"""
SECTOR LEADERSHIP LAB
=====================

Current Nifty 500 sector leadership research.

Strategy / functionality:
    - Current Nifty 500 universe
    - Sector / Industry metadata
    - Market-cap analysis
    - Sector market-cap leaders
    - Sector momentum leaders
    - Sector investable leaders
    - Current sector leadership
    - Historical sector leadership
    - Stock leadership
    - Current candidates

IMPORTANT:
    - trade_data.py is located in the SAME folder as this main.py.
    - DO NOT MODIFY trade_data.py.
    - .NS is preserved when calling trade_data.py.
    - .NS is removed only for internal joins/display.
    - Existing strategy weights and decision logic are preserved.
"""

import os
import sys
import time
import pickle
import warnings
import importlib.util
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf


# =====================================================================
# PATHS
# =====================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

RESULTS_DIR = os.path.join(
    BASE_DIR,
    "results",
)

OUTPUT_FILE = os.path.join(
    RESULTS_DIR,
    "sector_leadership_results.xlsx",
)

METADATA_CACHE_FILE = os.path.join(
    RESULTS_DIR,
    "sector_metadata_cache.pkl",
)

# trade_data.py is in the SAME folder as main.py
TRADE_DATA_FILE = os.path.join(
    BASE_DIR,
    "trade_data.py",
)

os.makedirs(
    RESULTS_DIR,
    exist_ok=True,
)


# =====================================================================
# LOAD trade_data.py
# =====================================================================

def load_trade_data_module():

    if not os.path.isfile(TRADE_DATA_FILE):

        print()
        print("=" * 100)
        print("ERROR: Could not load trade_data.py")
        print("=" * 100)
        print()
        print("Expected location:")
        print(TRADE_DATA_FILE)
        print()
        print("Error: trade_data.py not found at:")
        print(TRADE_DATA_FILE)
        print()

        raise FileNotFoundError(
            f"trade_data.py not found at:\n{TRADE_DATA_FILE}"
        )

    try:

        spec = importlib.util.spec_from_file_location(
            "sector_leadership_trade_data",
            TRADE_DATA_FILE,
        )

        if spec is None or spec.loader is None:

            raise ImportError(
                "Could not create import specification."
            )

        module = importlib.util.module_from_spec(
            spec
        )

        spec.loader.exec_module(module)

        required_functions = [
            "refresh_nifty500_universe",
            "get_historical_market_data_for_symbols",
        ]

        missing = [
            function_name
            for function_name in required_functions
            if not hasattr(module, function_name)
        ]

        if missing:

            raise ImportError(
                "trade_data.py is missing required functions: "
                + ", ".join(missing)
            )

        print()
        print("=" * 100)
        print("trade_data.py LOADED")
        print("=" * 100)
        print()
        print(f"Location : {TRADE_DATA_FILE}")
        print()

        return module

    except Exception as exc:

        print()
        print("=" * 100)
        print("ERROR: Could not load trade_data.py")
        print("=" * 100)
        print()
        print(f"Location : {TRADE_DATA_FILE}")
        print()
        print(f"Error : {exc}")
        print()

        raise


trade_data = load_trade_data_module()

refresh_nifty500_universe = (
    trade_data.refresh_nifty500_universe
)

get_historical_market_data_for_symbols = (
    trade_data.get_historical_market_data_for_symbols
)


# =====================================================================
# CONFIGURATION
# =====================================================================

HISTORICAL_PERIOD = "5y"

MIN_HISTORY_DAYS = 252

TOP_SECTORS_TO_RESEARCH = 10

TOP_STOCKS_TO_DISPLAY = 30


# =====================================================================
# SECTOR LEADERSHIP WEIGHTS
# =====================================================================

SECTOR_WEIGHT_3M = 0.15
SECTOR_WEIGHT_6M = 0.25
SECTOR_WEIGHT_12M = 0.30
SECTOR_WEIGHT_24M = 0.10
SECTOR_WEIGHT_TREND = 0.10
SECTOR_WEIGHT_HISTORY = 0.10


# =====================================================================
# STOCK LEADERSHIP WEIGHTS
# =====================================================================

STOCK_WEIGHT_3M_RS = 0.15
STOCK_WEIGHT_6M_RS = 0.20
STOCK_WEIGHT_12M_RS = 0.25
STOCK_WEIGHT_SECTOR_RS = 0.20
STOCK_WEIGHT_TREND = 0.20


warnings.filterwarnings("ignore")


# =====================================================================
# SYMBOL HELPERS
# =====================================================================

def clean_symbol(symbol):

    if symbol is None:
        return ""

    symbol = str(symbol).strip().upper()

    if symbol.endswith(".NS"):
        symbol = symbol[:-3]

    return symbol


def yahoo_symbol(symbol):

    symbol = str(symbol).strip().upper()

    if not symbol.endswith(".NS"):
        symbol += ".NS"

    return symbol


def yahoo_symbols(symbols):

    result = []

    for symbol in symbols:

        if symbol is None:
            continue

        symbol = yahoo_symbol(symbol)

        if symbol not in result:
            result.append(symbol)

    return result


# =====================================================================
# DATAFRAME SAFETY
# =====================================================================

def ensure_unique_columns(df):

    if df is None:
        return df

    result = df.copy()

    if result.columns.duplicated().any():

        result = result.loc[
            :,
            ~result.columns.duplicated(
                keep="first"
            ),
        ].copy()

    return result


def safe_numeric(series):

    return pd.to_numeric(
        series,
        errors="coerce",
    )


# =====================================================================
# PERCENTILE
# =====================================================================

def percentile_rank(series):

    series = safe_numeric(series)

    if series.dropna().empty:

        return pd.Series(
            np.nan,
            index=series.index,
            dtype=float,
        )

    return (
        series.rank(
            pct=True,
            method="average",
        )
        * 100.0
    )


# =====================================================================
# WEIGHTED SCORE
# =====================================================================

def weighted_score(
    values,
    weights,
):

    numerator = 0.0
    denominator = 0.0

    for key, weight in weights.items():

        value = values.get(key)

        if pd.isna(value):
            continue

        numerator += (
            float(value) * weight
        )

        denominator += weight

    if denominator == 0:
        return np.nan

    return numerator / denominator


# =====================================================================
# INDIAN NUMBER FORMATTING
# =====================================================================

def indian_number(value):

    if pd.isna(value):
        return ""

    try:
        value = float(value)

    except Exception:
        return str(value)

    sign = ""

    if value < 0:

        sign = "-"
        value = abs(value)

    # First create a normal US-style formatted number.
    if value >= 100:

        formatted = f"{value:,.0f}"

    else:

        formatted = (
            f"{value:,.2f}"
            .rstrip("0")
            .rstrip(".")
        )

    # IMPORTANT:
    # Remove existing commas before applying Indian grouping.
    # This prevents results such as:
    # 1,,66,3,,141
    # and correctly produces:
    # 16,63,141
    integer, dot, decimal = (
        formatted.partition(".")
    )

    integer = integer.replace(",", "")

    if len(integer) > 3:

        last_three = integer[-3:]
        remaining = integer[:-3]

        groups = []

        while remaining:

            groups.insert(
                0,
                remaining[-2:],
            )

            remaining = remaining[:-2]

        integer = ",".join(
            groups + [last_three]
        )

    if decimal:

        return (
            f"{sign}{integer}.{decimal}"
        )

    return (
        f"{sign}{integer}"
    )


def format_market_cap(value):

    if pd.isna(value):
        return "N/A"

    return (
        f"{indian_number(value)} Cr"
    )


def add_market_cap_display_columns(df):

    if df is None or df.empty:
        return df

    result = ensure_unique_columns(df)

    mappings = {
        "Market Cap Cr": "Market Cap",
        "Leader Market Cap Cr": "Leader Market Cap",
        "Total Market Cap Cr": "Total Market Cap",
        "Median Market Cap Cr": "Median Market Cap",
    }

    for source, display_name in mappings.items():

        if source in result.columns:

            result[
                f"{display_name} Display"
            ] = result[source].apply(
                format_market_cap
            )

    return result


# =====================================================================
# METADATA CACHE
# =====================================================================

def load_metadata_cache():

    if not os.path.exists(
        METADATA_CACHE_FILE
    ):
        return {}

    try:

        with open(
            METADATA_CACHE_FILE,
            "rb",
        ) as file:

            data = pickle.load(file)

        if isinstance(data, dict):
            return data

    except Exception:
        pass

    return {}


def save_metadata_cache(cache):

    try:

        with open(
            METADATA_CACHE_FILE,
            "wb",
        ) as file:

            pickle.dump(
                cache,
                file,
                protocol=pickle.HIGHEST_PROTOCOL,
            )

    except Exception as exc:

        print(
            f"Warning: Could not save metadata cache: {exc}"
        )


# =====================================================================
# SINGLE STOCK METADATA
# =====================================================================

def get_single_stock_metadata(symbol):

    clean = clean_symbol(symbol)

    try:

        ticker_symbol = yahoo_symbol(symbol)

        ticker = yf.Ticker(
            ticker_symbol
        )

        info = ticker.info

        if not isinstance(info, dict):
            info = {}

        company = (
            info.get("longName")
            or info.get("shortName")
            or info.get("displayName")
            or clean
        )

        sector = info.get("sector")

        industry = info.get("industry")

        market_cap = info.get("marketCap")

        if market_cap is not None:

            try:

                market_cap_cr = (
                    float(market_cap)
                    / 10_000_000
                )

            except Exception:

                market_cap_cr = np.nan

        else:

            market_cap_cr = np.nan

        return {
            "Symbol": clean,
            "Company": company,
            "Sector": sector,
            "Industry": industry,
            "Market Cap Cr": market_cap_cr,
        }

    except Exception:

        return {
            "Symbol": clean,
            "Company": clean,
            "Sector": np.nan,
            "Industry": np.nan,
            "Market Cap Cr": np.nan,
        }


# =====================================================================
# SECTOR METADATA
# =====================================================================

def get_sector_metadata(symbols):

    print()
    print("=" * 100)
    print(
        "STEP 2 - Loading sector / industry / market-cap metadata"
    )
    print("=" * 100)

    cache = load_metadata_cache()

    records = []

    total = len(symbols)

    for count, symbol in enumerate(
        symbols,
        start=1,
    ):

        clean = clean_symbol(symbol)

        if clean in cache:

            item = cache[clean]

            if not isinstance(item, dict):

                item = (
                    get_single_stock_metadata(
                        symbol
                    )
                )

        else:

            item = (
                get_single_stock_metadata(
                    symbol
                )
            )

            cache[clean] = item

        if "Company" not in item:

            item["Company"] = item.get(
                "Symbol",
                clean,
            )

        records.append(item)

        if (
            count % 25 == 0
            or count == total
        ):

            print(
                f"Metadata: {count}/{total}",
                end="\r",
            )

        time.sleep(0.02)

    print()

    save_metadata_cache(cache)

    metadata = pd.DataFrame(records)

    metadata = ensure_unique_columns(
        metadata
    )

    required_columns = [
        "Symbol",
        "Company",
        "Sector",
        "Industry",
        "Market Cap Cr",
    ]

    for column in required_columns:

        if column not in metadata.columns:

            if column == "Company":

                metadata[column] = (
                    metadata["Symbol"]
                )

            else:

                metadata[column] = np.nan

    metadata = metadata[
        required_columns
    ].copy()

    metadata["Symbol"] = (
        metadata["Symbol"]
        .apply(clean_symbol)
    )

    metadata["Company"] = (
        metadata["Company"]
        .fillna(metadata["Symbol"])
        .astype(str)
        .str.strip()
    )

    metadata["Sector"] = (
        metadata["Sector"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
    )

    metadata["Industry"] = (
        metadata["Industry"]
        .fillna("Unknown")
        .astype(str)
        .str.strip()
    )

    metadata["Market Cap Cr"] = (
        safe_numeric(
            metadata["Market Cap Cr"]
        )
    )

    metadata = (
        metadata
        .drop_duplicates(
            subset=["Symbol"],
            keep="first",
        )
        .reset_index(drop=True)
    )

    print()
    print(
        f"Metadata records : {len(metadata)}"
    )

    print(
        "Valid sectors    : "
        f"{metadata['Sector'].ne('Unknown').sum()}"
    )

    print(
        "Market caps      : "
        f"{metadata['Market Cap Cr'].notna().sum()}"
    )

    return metadata


# =====================================================================
# NORMALIZE PRICE DATA
# =====================================================================

def normalize_price_data(data):

    if data is None:
        return pd.DataFrame()

    # -----------------------------------------------------------------
    # Dictionary
    # -----------------------------------------------------------------

    if isinstance(data, dict):

        frames = {}

        for symbol, frame in data.items():

            if frame is None:
                continue

            if isinstance(frame, pd.Series):

                series = frame.copy()

            elif isinstance(frame, pd.DataFrame):

                if "Close" in frame.columns:

                    series = frame["Close"]

                elif len(frame.columns) > 0:

                    series = frame.iloc[:, 0]

                else:

                    continue

            else:

                continue

            series = pd.to_numeric(
                series,
                errors="coerce",
            )

            frames[
                clean_symbol(symbol)
            ] = series

        if not frames:
            return pd.DataFrame()

        result = pd.concat(
            frames,
            axis=1,
        )

        result.columns = [
            clean_symbol(column)
            for column in result.columns
        ]

        result = result.loc[
            :,
            ~result.columns.duplicated(
                keep="first"
            ),
        ]

        return result.sort_index()

    # -----------------------------------------------------------------
    # DataFrame
    # -----------------------------------------------------------------

    if not isinstance(
        data,
        pd.DataFrame,
    ):
        return pd.DataFrame()

    df = data.copy()

    # -----------------------------------------------------------------
    # MultiIndex
    # -----------------------------------------------------------------

    if isinstance(
        df.columns,
        pd.MultiIndex,
    ):

        level0 = list(
            df.columns.get_level_values(0)
        )

        if "Close" in level0:

            result = df["Close"].copy()

        else:

            level1 = list(
                df.columns.get_level_values(1)
            )

            if "Close" in level1:

                result = df.xs(
                    "Close",
                    axis=1,
                    level=1,
                ).copy()

            else:

                result = df.copy()

    else:

        if "Close" in df.columns:

            close = df["Close"]

            if isinstance(
                close,
                pd.Series,
            ):

                result = close.to_frame(
                    name="Close"
                )

            else:

                result = close.copy()

        else:

            result = df.copy()

    if isinstance(
        result,
        pd.Series,
    ):

        result = result.to_frame()

    result = result.copy()

    result.columns = [
        clean_symbol(column)
        for column in result.columns
    ]

    result = result.loc[
        :,
        ~result.columns.duplicated(
            keep="first"
        ),
    ]

    result = result.apply(
        pd.to_numeric,
        errors="coerce",
    )

    return result.sort_index()


# =====================================================================
# RETURNS
# =====================================================================

def calculate_return(
    series,
    periods,
):

    series = pd.to_numeric(
        series,
        errors="coerce",
    ).dropna()

    if len(series) <= periods:
        return np.nan

    try:

        return (
            (
                series.iloc[-1]
                / series.iloc[-periods - 1]
            )
            - 1
        ) * 100

    except Exception:

        return np.nan


def calculate_all_returns(series):

    return {

        "1M Return %":
            calculate_return(
                series,
                21,
            ),

        "3M Return %":
            calculate_return(
                series,
                63,
            ),

        "6M Return %":
            calculate_return(
                series,
                126,
            ),

        "9M Return %":
            calculate_return(
                series,
                189,
            ),

        "12M Return %":
            calculate_return(
                series,
                252,
            ),

        "24M Return %":
            calculate_return(
                series,
                504,
            ),
    }


# =====================================================================
# TREND
# =====================================================================

def calculate_trend_score(series):

    series = pd.to_numeric(
        series,
        errors="coerce",
    ).dropna()

    if len(series) < MIN_HISTORY_DAYS:

        return {

            "Trend Score": np.nan,

            "Trend Status":
                "Insufficient Data",

            "Close":
                series.iloc[-1]
                if len(series)
                else np.nan,
        }

    close = series.iloc[-1]

    dma50 = (
        series
        .rolling(50)
        .mean()
        .iloc[-1]
    )

    dma200 = (
        series
        .rolling(200)
        .mean()
        .iloc[-1]
    )

    if len(series) >= 220:

        dma200_previous = (
            series
            .rolling(200)
            .mean()
            .iloc[-21]
        )

    else:

        dma200_previous = np.nan

    score = 0

    if (
        pd.notna(dma200)
        and close > dma200
    ):

        score += 40

    if (
        pd.notna(dma50)
        and pd.notna(dma200)
        and dma50 > dma200
    ):

        score += 30

    if (
        pd.notna(dma200)
        and pd.notna(dma200_previous)
        and dma200 > dma200_previous
    ):

        score += 30

    if score >= 70:

        status = "Strong"

    elif score >= 40:

        status = "Neutral"

    else:

        status = "Weak"

    return {

        "Trend Score":
            float(score),

        "Trend Status":
            status,

        "Close":
            close,

        "DMA 50":
            dma50,

        "DMA 200":
            dma200,
    }


# =====================================================================
# STOCK ANALYSIS
# =====================================================================

def build_stock_analysis(
    prices,
    metadata,
):

    print()
    print("=" * 100)
    print(
        "STEP 4 - Building stock analysis"
    )
    print("=" * 100)

    metadata = ensure_unique_columns(
        metadata
    )

    metadata_lookup = (
        metadata
        .drop_duplicates("Symbol")
        .set_index("Symbol")
        .to_dict("index")
    )

    records = []

    for symbol in prices.columns:

        symbol_clean = clean_symbol(symbol)

        series = prices[symbol].dropna()

        if len(series) < MIN_HISTORY_DAYS:
            continue

        returns = calculate_all_returns(
            series
        )

        trend = calculate_trend_score(
            series
        )

        meta = metadata_lookup.get(
            symbol_clean,
            {},
        )

        record = {

            "Symbol":
                symbol_clean,

            "Company":
                meta.get(
                    "Company",
                    symbol_clean,
                ),

            "Sector":
                meta.get(
                    "Sector",
                    "Unknown",
                ),

            "Industry":
                meta.get(
                    "Industry",
                    "Unknown",
                ),

            "Market Cap Cr":
                meta.get(
                    "Market Cap Cr",
                    np.nan,
                ),

            **returns,

            **trend,
        }

        records.append(record)

    result = pd.DataFrame(records)

    if result.empty:
        return result

    result = ensure_unique_columns(
        result
    )

    return result


# =====================================================================
# CURRENT SECTOR ANALYSIS
# =====================================================================

def build_sector_current_analysis(
    stock_analysis,
):

    if stock_analysis.empty:
        return pd.DataFrame()

    print()
    print("=" * 100)
    print(
        "STEP 5 - Building current sector analysis"
    )
    print("=" * 100)

    grouped = (
        stock_analysis
        .groupby(
            "Sector",
            dropna=False,
        )
    )

    records = []

    for sector, group in grouped:

        records.append({

            "Sector":
                sector,

            "Stocks":
                len(group),

            "Median 1M Return %":
                group[
                    "1M Return %"
                ].median(),

            "Median 3M Return %":
                group[
                    "3M Return %"
                ].median(),

            "Median 6M Return %":
                group[
                    "6M Return %"
                ].median(),

            "Median 9M Return %":
                group[
                    "9M Return %"
                ].median(),

            "Median 12M Return %":
                group[
                    "12M Return %"
                ].median(),

            "Median 24M Return %":
                group[
                    "24M Return %"
                ].median(),

            "Median Trend Score":
                group[
                    "Trend Score"
                ].median(),
        })

    return pd.DataFrame(records)


# =====================================================================
# SECTOR MARKET CAP
# =====================================================================

def build_sector_market_cap_analysis(
    stock_analysis,
):

    if stock_analysis.empty:
        return pd.DataFrame()

    print()
    print("=" * 100)
    print(
        "STEP 6 - Building sector market-cap analysis"
    )
    print("=" * 100)

    df = ensure_unique_columns(
        stock_analysis
    )

    records = []

    for sector, group in df.groupby(
        "Sector",
        dropna=False,
    ):

        market_caps = (
            safe_numeric(
                group["Market Cap Cr"]
            )
            .dropna()
        )

        records.append({

            "Sector":
                sector,

            "Stocks":
                len(group),

            "Total Market Cap Cr":
                market_caps.sum()
                if not market_caps.empty
                else np.nan,

            "Median Market Cap Cr":
                market_caps.median()
                if not market_caps.empty
                else np.nan,
        })

    result = pd.DataFrame(records)

    if result.empty:
        return result

    result = result.sort_values(
        "Total Market Cap Cr",
        ascending=False,
        na_position="last",
    ).reset_index(drop=True)

    return result


# =====================================================================
# SECTOR MARKET CAP LEADERS
# =====================================================================

def identify_market_cap_leaders(
    metadata,
):

    print()
    print("=" * 100)
    print(
        "STEP 6 - Identifying sector market-cap leaders"
    )
    print("=" * 100)

    metadata = ensure_unique_columns(
        metadata
    )

    required = [
        "Sector",
        "Symbol",
        "Company",
        "Market Cap Cr",
        "Industry",
    ]

    for column in required:

        if column not in metadata.columns:

            if column == "Company":

                metadata[column] = (
                    metadata["Symbol"]
                )

            else:

                metadata[column] = np.nan

    valid = metadata[
        metadata["Sector"].notna()
        & metadata["Market Cap Cr"].notna()
    ].copy()

    valid = ensure_unique_columns(
        valid
    )

    if valid.empty:

        return pd.DataFrame(
            columns=[
                "Sector",
                "Market Cap Leader",
                "Company",
                "Leader Market Cap Cr",
                "Leader Industry",
            ]
        )

    valid["Market Cap Cr"] = safe_numeric(
        valid["Market Cap Cr"]
    )

    idx = (
        valid
        .groupby("Sector")["Market Cap Cr"]
        .idxmax()
    )

    leaders = valid.loc[
        idx,
        [
            "Sector",
            "Symbol",
            "Company",
            "Market Cap Cr",
            "Industry",
        ],
    ].copy()

    leaders = ensure_unique_columns(
        leaders
    )

    leaders = leaders.rename(
        columns={
            "Symbol":
                "Market Cap Leader",

            "Market Cap Cr":
                "Leader Market Cap Cr",

            "Industry":
                "Leader Industry",
        }
    )

    leaders["Company"] = (
        leaders["Company"]
        .fillna(
            leaders["Market Cap Leader"]
        )
        .astype(str)
    )

    leaders = leaders.sort_values(
        "Leader Market Cap Cr",
        ascending=False,
        na_position="last",
    ).reset_index(drop=True)

    return leaders


# =====================================================================
# HISTORICAL SECTOR ANALYSIS
# =====================================================================

def build_historical_sector_analysis(
    prices,
    metadata,
):

    print()
    print("=" * 100)
    print(
        "STEP 7 - Building historical sector analysis"
    )
    print("=" * 100)

    if prices.empty:
        return pd.DataFrame()

    metadata = ensure_unique_columns(
        metadata
    )

    sector_lookup = (
        metadata
        .drop_duplicates("Symbol")
        .set_index("Symbol")["Sector"]
        .to_dict()
    )

    monthly_prices = (
        prices
        .resample("ME")
        .last()
    )

    monthly_returns = (
        monthly_prices
        .pct_change()
        * 100
    )

    records = []

    sectors = sorted(
        {
            sector_lookup.get(
                clean_symbol(symbol),
                "Unknown",
            )
            for symbol
            in monthly_returns.columns
        }
    )

    for sector in sectors:

        sector_symbols = [

            symbol

            for symbol
            in monthly_returns.columns

            if sector_lookup.get(
                clean_symbol(symbol),
                "Unknown",
            ) == sector
        ]

        if not sector_symbols:
            continue

        sector_data = (
            monthly_returns[
                sector_symbols
            ]
        )

        median_monthly = (
            sector_data
            .median(
                axis=1,
                skipna=True,
            )
            .dropna()
        )

        if median_monthly.empty:
            continue

        cumulative_index = (
            (
                1
                + median_monthly / 100
            )
            .cumprod()
            * 100
        )

        def rolling_return(months):

            if len(cumulative_index) <= months:
                return np.nan

            try:

                return (
                    (
                        cumulative_index.iloc[-1]
                        /
                        cumulative_index.iloc[
                            -months - 1
                        ]
                    )
                    - 1
                ) * 100

            except Exception:

                return np.nan

        # -------------------------------------------------------------
        # Historical top-3 frequency
        # -------------------------------------------------------------

        top3_frequency = np.nan

        if len(sector_data) >= 3:

            historical_values = (
                sector_data
                .median(
                    axis=1,
                    skipna=True,
                )
                .dropna()
            )

            if not historical_values.empty:

                top3_frequency = (
                    (
                        historical_values
                        >=
                        historical_values
                        .rolling(
                            min(
                                12,
                                len(
                                    historical_values
                                )
                            ),
                            min_periods=1,
                        )
                        .mean()
                    )
                    .mean()
                    * 100
                )

        records.append({

            "Sector":
                sector,

            "Historical 12M Return %":
                rolling_return(12),

            "Historical 6M Return %":
                rolling_return(6),

            "Historical 3M Return %":
                rolling_return(3),

            "Historical Top-3 Frequency %":
                top3_frequency,

            "Historical Months":
                len(median_monthly),
        })

    return pd.DataFrame(records)


# =====================================================================
# SECTOR LEADERSHIP
# =====================================================================

def build_sector_leadership(
    sector_current,
    historical_sector,
):

    print()
    print("=" * 100)
    print(
        "STEP 8 - Calculating sector leadership scores"
    )
    print("=" * 100)

    if sector_current.empty:
        return pd.DataFrame()

    current = sector_current.copy()

    if (
        historical_sector is not None
        and not historical_sector.empty
    ):

        current = current.merge(
            historical_sector,
            on="Sector",
            how="left",
        )

    else:

        for column in [
            "Historical 12M Return %",
            "Historical 6M Return %",
            "Historical 3M Return %",
            "Historical Top-3 Frequency %",
        ]:

            current[column] = np.nan

    current["Score 3M"] = percentile_rank(
        current["Median 3M Return %"]
    )

    current["Score 6M"] = percentile_rank(
        current["Median 6M Return %"]
    )

    current["Score 12M"] = percentile_rank(
        current["Median 12M Return %"]
    )

    current["Score 24M"] = percentile_rank(
        current["Median 24M Return %"]
    )

    current["Score Trend"] = percentile_rank(
        current["Median Trend Score"]
    )

    current["Score History"] = percentile_rank(
        current[
            "Historical Top-3 Frequency %"
        ]
    )

    weights = {

        "3M":
            SECTOR_WEIGHT_3M,

        "6M":
            SECTOR_WEIGHT_6M,

        "12M":
            SECTOR_WEIGHT_12M,

        "24M":
            SECTOR_WEIGHT_24M,

        "Trend":
            SECTOR_WEIGHT_TREND,

        "History":
            SECTOR_WEIGHT_HISTORY,
    }

    scores = []

    for _, row in current.iterrows():

        score = weighted_score(

            {

                "3M":
                    row["Score 3M"],

                "6M":
                    row["Score 6M"],

                "12M":
                    row["Score 12M"],

                "24M":
                    row["Score 24M"],

                "Trend":
                    row["Score Trend"],

                "History":
                    row["Score History"],
            },

            weights,
        )

        scores.append(score)

    current[
        "Sector Leadership Score"
    ] = scores

    statuses = []

    for _, row in current.iterrows():

        score = row[
            "Sector Leadership Score"
        ]

        trend = row[
            "Median Trend Score"
        ]

        ret12 = row[
            "Median 12M Return %"
        ]

        if pd.isna(score):

            status = "INSUFFICIENT DATA"

        elif (
            score >= 70
            and (
                pd.isna(trend)
                or trend >= 60
            )
            and (
                pd.isna(ret12)
                or ret12 > 0
            )
        ):

            status = "LEADING"

        elif score >= 50:

            status = "NEUTRAL"

        else:

            status = "WEAK"

        statuses.append(status)

    current["Sector Status"] = statuses

    current = current.sort_values(
        "Sector Leadership Score",
        ascending=False,
        na_position="last",
    ).reset_index(drop=True)

    current["Sector Rank"] = (
        current[
            "Sector Leadership Score"
        ]
        .rank(
            ascending=False,
            method="min",
        )
    )

    return current


# =====================================================================
# STOCK LEADERSHIP
# =====================================================================

def build_stock_leadership(
    stock_analysis,
    sector_analysis,
):

    print()
    print("=" * 100)
    print(
        "STEP 9 - Calculating stock leadership"
    )
    print("=" * 100)

    if stock_analysis.empty:
        return pd.DataFrame()

    stocks = ensure_unique_columns(
        stock_analysis.copy()
    )

    sector_medians = (
        stocks
        .groupby("Sector")[
            [
                "3M Return %",
                "6M Return %",
                "12M Return %",
            ]
        ]
        .median()
        .rename(
            columns={

                "3M Return %":
                    "Sector Median 3M",

                "6M Return %":
                    "Sector Median 6M",

                "12M Return %":
                    "Sector Median 12M",
            }
        )
        .reset_index()
    )

    stocks = stocks.merge(
        sector_medians,
        on="Sector",
        how="left",
    )

    stocks["3M Sector RS %"] = (
        stocks["3M Return %"]
        - stocks["Sector Median 3M"]
    )

    stocks["6M Sector RS %"] = (
        stocks["6M Return %"]
        - stocks["Sector Median 6M"]
    )

    stocks["12M Sector RS %"] = (
        stocks["12M Return %"]
        - stocks["Sector Median 12M"]
    )

    stocks["Score 3M RS"] = percentile_rank(
        stocks["3M Return %"]
    )

    stocks["Score 6M RS"] = percentile_rank(
        stocks["6M Return %"]
    )

    stocks["Score 12M RS"] = percentile_rank(
        stocks["12M Return %"]
    )

    stocks["Score Trend"] = percentile_rank(
        stocks["Trend Score"]
    )

    stocks["Score Sector RS"] = percentile_rank(
        stocks["12M Sector RS %"]
    )

    weights = {

        "3M":
            STOCK_WEIGHT_3M_RS,

        "6M":
            STOCK_WEIGHT_6M_RS,

        "12M":
            STOCK_WEIGHT_12M_RS,

        "Sector RS":
            STOCK_WEIGHT_SECTOR_RS,

        "Trend":
            STOCK_WEIGHT_TREND,
    }

    scores = []

    for _, row in stocks.iterrows():

        scores.append(
            weighted_score(

                {

                    "3M":
                        row["Score 3M RS"],

                    "6M":
                        row["Score 6M RS"],

                    "12M":
                        row["Score 12M RS"],

                    "Sector RS":
                        row["Score Sector RS"],

                    "Trend":
                        row["Score Trend"],
                },

                weights,
            )
        )

    stocks[
        "Stock Leadership Score"
    ] = scores

    # -------------------------------------------------------------
    # MARKET-CAP LEADER
    # -------------------------------------------------------------

    stocks["Market Cap Leader"] = False

    valid_market_cap = stocks[
        stocks["Market Cap Cr"].notna()
    ].copy()

    if not valid_market_cap.empty:

        valid_market_cap[
            "Market Cap Cr"
        ] = safe_numeric(
            valid_market_cap[
                "Market Cap Cr"
            ]
        )

        idx = (
            valid_market_cap
            .groupby("Sector")[
                "Market Cap Cr"
            ]
            .idxmax()
        )

        stocks.loc[
            idx,
            "Market Cap Leader",
        ] = True

    # -------------------------------------------------------------
    # MOMENTUM LEADER
    # -------------------------------------------------------------

    stocks["Momentum Leader"] = False

    valid_momentum = stocks[
        stocks["12M Return %"].notna()
    ].copy()

    if not valid_momentum.empty:

        idx = (
            valid_momentum
            .groupby("Sector")[
                "12M Return %"
            ]
            .idxmax()
        )

        stocks.loc[
            idx,
            "Momentum Leader",
        ] = True

    # -------------------------------------------------------------
    # INVESTABLE LEADER
    # -------------------------------------------------------------

    stocks["Investable Leader"] = False

    valid_investable = stocks[
        stocks[
            "Stock Leadership Score"
        ].notna()
    ].copy()

    if not valid_investable.empty:

        idx = (
            valid_investable
            .groupby("Sector")[
                "Stock Leadership Score"
            ]
            .idxmax()
        )

        stocks.loc[
            idx,
            "Investable Leader",
        ] = True

    stocks[
        "Stock Leadership Rank"
    ] = (
        stocks[
            "Stock Leadership Score"
        ]
        .rank(
            ascending=False,
            method="min",
        )
    )

    stocks = stocks.sort_values(
        "Stock Leadership Score",
        ascending=False,
        na_position="last",
    ).reset_index(drop=True)

    return stocks


# =====================================================================
# CURRENT CANDIDATES
# =====================================================================

def build_current_candidates(
    stock_leadership,
    sector_leadership,
):

    print()
    print("=" * 100)
    print(
        "STEP 10 - Building current candidates"
    )
    print("=" * 100)

    if stock_leadership.empty:
        return pd.DataFrame()

    stocks = ensure_unique_columns(
        stock_leadership.copy()
    )

    sector_data = (
        sector_leadership[
            [
                "Sector",
                "Sector Leadership Score",
                "Sector Status",
            ]
        ]
        .copy()
    )

    stocks = stocks.merge(
        sector_data,
        on="Sector",
        how="left",
    )

    # -------------------------------------------------------------
    # Existing stock momentum score
    #
    # 3M  = 25%
    # 6M  = 35%
    # 12M = 40%
    # -------------------------------------------------------------

    score_3m = percentile_rank(
        stocks["3M Return %"]
    )

    score_6m = percentile_rank(
        stocks["6M Return %"]
    )

    score_12m = percentile_rank(
        stocks["12M Return %"]
    )

    stocks[
        "Stock Momentum Score"
    ] = (
        score_3m * 0.25
        + score_6m * 0.35
        + score_12m * 0.40
    )

    # -------------------------------------------------------------
    # Existing candidate stock score
    #
    # Momentum = 60%
    # Trend    = 40%
    # -------------------------------------------------------------

    momentum_pct = percentile_rank(
        stocks["Stock Momentum Score"]
    )

    trend_pct = percentile_rank(
        stocks["Trend Score"]
    )

    stocks[
        "Candidate Stock Score"
    ] = (
        momentum_pct * 0.60
        + trend_pct * 0.40
    )

    # -------------------------------------------------------------
    # Relative strength
    # -------------------------------------------------------------

    stocks[
        "12M Relative Strength %"
    ] = (
        stocks["12M Return %"]
        - stocks["Sector Median 12M"]
    )

    stocks[
        "12M RS Percentile"
    ] = percentile_rank(
        stocks["12M Relative Strength %"]
    )

    # -------------------------------------------------------------
    # Final leadership score
    #
    # Sector      = 40%
    # Stock       = 40%
    # 12M RS      = 20%
    # -------------------------------------------------------------

    stocks[
        "Final Leadership Score"
    ] = (
        stocks[
            "Sector Leadership Score"
        ] * 0.40
        + stocks[
            "Candidate Stock Score"
        ] * 0.40
        + stocks[
            "12M RS Percentile"
        ] * 0.20
    )

    # -------------------------------------------------------------
    # Decision
    # -------------------------------------------------------------

    decisions = []

    leadership_conditions = []

    for _, row in stocks.iterrows():

        sector_score = row[
            "Sector Leadership Score"
        ]

        stock_score = row[
            "Candidate Stock Score"
        ]

        trend = row[
            "Trend Score"
        ]

        rs12 = row[
            "12M Relative Strength %"
        ]

        sector_status = row[
            "Sector Status"
        ]

        # ---------------------------------------------------------
        # BUY / HOLD
        # ---------------------------------------------------------

        buy_hold = (

            pd.notna(sector_score)
            and sector_score >= 70

            and

            pd.notna(stock_score)
            and stock_score >= 70

            and

            (
                pd.isna(trend)
                or trend >= 70
            )

            and

            (
                pd.isna(rs12)
                or rs12 > 0
            )
        )

        # ---------------------------------------------------------
        # WATCH
        # ---------------------------------------------------------

        watch = (

            pd.notna(sector_score)
            and sector_score >= 60

            and

            pd.notna(stock_score)
            and stock_score >= 55
        )

        # ---------------------------------------------------------
        # EXIT
        # ---------------------------------------------------------

        exit_condition = (

            sector_status == "WEAK"

            or

            (
                pd.notna(sector_score)
                and sector_score < 40
            )

            or

            (
                pd.notna(trend)
                and trend < 40
            )
        )

        if buy_hold:

            decision = "BUY / HOLD"

        elif watch:

            decision = "WATCH"

        elif exit_condition:

            decision = "EXIT"

        else:

            decision = "NEUTRAL"

        decisions.append(decision)

        # ---------------------------------------------------------
        # Leadership condition
        # ---------------------------------------------------------

        if (

            pd.notna(sector_score)
            and sector_score >= 70

            and

            pd.notna(stock_score)
            and stock_score >= 70

            and

            pd.notna(trend)
            and trend >= 70
        ):

            leadership = (
                "LEADERSHIP INTACT"
            )

        elif (

            pd.notna(sector_score)
            and sector_score >= 50
        ):

            leadership = (
                "LEADERSHIP SOFTENING"
            )

        else:

            leadership = (
                "LEADERSHIP BROKEN"
            )

        leadership_conditions.append(
            leadership
        )

    stocks["Decision"] = decisions

    stocks[
        "Leadership Condition"
    ] = leadership_conditions

    stocks = stocks.sort_values(
        "Final Leadership Score",
        ascending=False,
        na_position="last",
    ).reset_index(drop=True)

    stocks["Candidate Rank"] = (
        stocks[
            "Final Leadership Score"
        ]
        .rank(
            ascending=False,
            method="min",
        )
    )

    return stocks


# =====================================================================
# TOP SECTORS
# =====================================================================

def get_top_sectors(
    sector_leadership,
):

    if sector_leadership.empty:
        return pd.DataFrame()

    return (
        sector_leadership
        .head(TOP_SECTORS_TO_RESEARCH)
        .copy()
    )


# =====================================================================
# DISPLAY HELPERS
# =====================================================================

def safe_display(
    value,
    decimals=2,
):

    if pd.isna(value):
        return "N/A"

    try:

        return (
            f"{float(value):.{decimals}f}"
        )

    except Exception:

        return str(value)


def safe_text(
    value,
    default="N/A",
):

    if value is None:
        return default

    try:

        if pd.isna(value):
            return default

    except Exception:
        pass

    text_value = str(value).strip()

    if not text_value:
        return default

    return text_value


# =====================================================================
# PRINT TOP SECTORS
# =====================================================================

def print_top_sectors(
    sector_leadership,
):

    print()
    print("=" * 100)
    print("TOP SECTORS")
    print("=" * 100)

    if sector_leadership.empty:

        print(
            "No sector data available."
        )

        return

    display = (
        sector_leadership
        .head(TOP_SECTORS_TO_RESEARCH)
    )

    for rank, (_, row) in enumerate(
        display.iterrows(),
        start=1,
    ):

        sector_name = safe_text(
            row.get("Sector")
        )

        score = safe_display(
            row.get(
                "Sector Leadership Score"
            )
        )

        status = safe_text(
            row.get(
                "Sector Status"
            )
        )

        print(
            f"{rank:>2}. "
            f"{sector_name[:35]:<35} "
            f"Score: {score} | {status}"
        )


# =====================================================================
# PRINT SECTOR LEADERS
# =====================================================================

def print_sector_leaders(
    sector_leadership,
    market_cap_leaders,
    stock_leadership,
):

    print()
    print("=" * 100)
    print("SECTOR LEADERS")
    print("=" * 100)

    if market_cap_leaders.empty:

        print(
            "No market-cap leaders available."
        )

        return

    # -------------------------------------------------------------
    # Momentum leaders
    # -------------------------------------------------------------

    momentum = pd.DataFrame()

    if (
        not stock_leadership.empty
        and "Momentum Leader" in stock_leadership.columns
    ):

        momentum = (
            stock_leadership[
                stock_leadership[
                    "Momentum Leader"
                ]
            ]
            [
                [
                    "Sector",
                    "Symbol",
                    "Company",
                    "12M Return %",
                ]
            ]
            .rename(
                columns={

                    "Symbol":
                        "Momentum Leader",

                    "Company":
                        "Momentum Leader Company",

                    "12M Return %":
                        "Momentum Leader 12M Return %",
                }
            )
        )

    # -------------------------------------------------------------
    # Investable leaders
    # -------------------------------------------------------------

    investable = pd.DataFrame()

    if (
        not stock_leadership.empty
        and "Investable Leader" in stock_leadership.columns
    ):

        investable = (
            stock_leadership[
                stock_leadership[
                    "Investable Leader"
                ]
            ]
            [
                [
                    "Sector",
                    "Symbol",
                    "Company",
                    "Stock Leadership Score",
                ]
            ]
            .rename(
                columns={

                    "Symbol":
                        "Investable Leader",

                    "Company":
                        "Investable Leader Company",

                    "Stock Leadership Score":
                        "Investable Leader Score",
                }
            )
        )

    result = market_cap_leaders.copy()

    if not momentum.empty:

        result = result.merge(
            momentum,
            on="Sector",
            how="left",
        )

    if not investable.empty:

        result = result.merge(
            investable,
            on="Sector",
            how="left",
        )

    sector_summary = (
        sector_leadership[
            [
                "Sector",
                "Sector Leadership Score",
                "Sector Status",
            ]
        ]
        .copy()
    )

    result = result.merge(
        sector_summary,
        on="Sector",
        how="left",
    )

    for _, row in result.iterrows():

        sector_name = safe_text(
            row.get("Sector")
        )

        market_cap_leader = safe_text(
            row.get(
                "Market Cap Leader"
            )
        )

        company = safe_text(
            row.get("Company")
        )

        leader_market_cap = format_market_cap(
            row.get(
                "Leader Market Cap Cr"
            )
        )

        momentum_leader = safe_text(
            row.get(
                "Momentum Leader"
            )
        )

        momentum_company = safe_text(
            row.get(
                "Momentum Leader Company"
            )
        )

        momentum_return = safe_display(
            row.get(
                "Momentum Leader 12M Return %"
            )
        )

        investable_leader = safe_text(
            row.get(
                "Investable Leader"
            )
        )

        investable_company = safe_text(
            row.get(
                "Investable Leader Company"
            )
        )

        investable_score = safe_display(
            row.get(
                "Investable Leader Score"
            )
        )

        sector_score = safe_display(
            row.get(
                "Sector Leadership Score"
            )
        )

        sector_status = safe_text(
            row.get(
                "Sector Status"
            )
        )

        print()

        print(
            f"Sector : {sector_name}"
        )

        print(
            f"  Market-cap leader : "
            f"{market_cap_leader} | "
            f"{company} | "
            f"{leader_market_cap}"
        )

        print(
            f"  Momentum leader   : "
            f"{momentum_leader} | "
            f"{momentum_company} | "
            f"{momentum_return}%"
        )

        print(
            f"  Investable leader : "
            f"{investable_leader} | "
            f"{investable_company} | "
            f"Score {investable_score}"
        )

        print(
            f"  Sector score      : "
            f"{sector_score} | "
            f"{sector_status}"
        )


# =====================================================================
# PRINT CANDIDATES
# =====================================================================

def print_candidates(
    candidates,
):

    print()
    print("=" * 100)
    print(
        "CURRENT BUY / HOLD CANDIDATES"
    )
    print("=" * 100)

    if candidates.empty:

        print(
            "No candidates."
        )

        return

    selected = candidates[
        candidates[
            "Decision"
        ].isin(
            [
                "BUY / HOLD",
                "WATCH",
            ]
        )
    ].head(
        TOP_STOCKS_TO_DISPLAY
    )

    if selected.empty:

        print(
            "No BUY / HOLD or WATCH candidates."
        )

        return

    for rank, (_, row) in enumerate(
        selected.iterrows(),
        start=1,
    ):

        symbol = safe_text(
            row.get("Symbol"),
            "",
        )

        company = safe_text(
            row.get("Company"),
            "",
        )

        sector = safe_text(
            row.get("Sector"),
            "",
        )

        score = safe_display(
            row.get(
                "Final Leadership Score"
            )
        )

        decision = safe_text(
            row.get("Decision")
        )

        print(
            f"{rank:>2}. "
            f"{symbol:<15} "
            f"{company[:28]:<28} "
            f"{sector[:22]:<22} "
            f"Score {score} | {decision}"
        )


# =====================================================================
# EXCEL OUTPUT
# =====================================================================

def write_excel(
    sector_leadership,
    sector_leaders,
    candidates,
    stock_leadership,
    metadata,
    historical,
    sector_market_cap,
):

    print()
    print("=" * 100)
    print(
        "STEP 11 - Writing Excel output"
    )
    print("=" * 100)

    sector_leadership_out = (
        add_market_cap_display_columns(
            sector_leadership
        )
    )

    sector_leaders_out = (
        add_market_cap_display_columns(
            sector_leaders
        )
    )

    candidates_out = (
        add_market_cap_display_columns(
            candidates
        )
    )

    stock_leadership_out = (
        add_market_cap_display_columns(
            stock_leadership
        )
    )

    metadata_out = (
        add_market_cap_display_columns(
            metadata
        )
    )

    sector_market_cap_out = (
        add_market_cap_display_columns(
            sector_market_cap
        )
    )

    historical_out = (
        historical.copy()
    )

    with pd.ExcelWriter(
        OUTPUT_FILE,
        engine="openpyxl",
    ) as writer:

        sector_leadership_out.to_excel(
            writer,
            sheet_name="Sector Dashboard",
            index=False,
        )

        # -------------------------------------------------------------
        # Build combined Sector Leaders sheet
        # -------------------------------------------------------------

        if (
            not sector_leaders_out.empty
            and not stock_leadership.empty
        ):

            momentum = pd.DataFrame()

            if "Momentum Leader" in stock_leadership.columns:

                momentum = (
                    stock_leadership[
                        stock_leadership[
                            "Momentum Leader"
                        ]
                    ]
                    [
                        [
                            "Sector",
                            "Symbol",
                            "Company",
                            "12M Return %",
                        ]
                    ]
                    .rename(
                        columns={

                            "Symbol":
                                "Momentum Leader",

                            "Company":
                                "Momentum Leader Company",

                            "12M Return %":
                                "Momentum Leader 12M Return %",
                        }
                    )
                )

            investable = pd.DataFrame()

            if "Investable Leader" in stock_leadership.columns:

                investable = (
                    stock_leadership[
                        stock_leadership[
                            "Investable Leader"
                        ]
                    ]
                    [
                        [
                            "Sector",
                            "Symbol",
                            "Company",
                            "Stock Leadership Score",
                        ]
                    ]
                    .rename(
                        columns={

                            "Symbol":
                                "Investable Leader",

                            "Company":
                                "Investable Leader Company",

                            "Stock Leadership Score":
                                "Investable Leader Score",
                        }
                    )
                )

            if not momentum.empty:

                sector_leaders_out = (
                    sector_leaders_out
                    .merge(
                        momentum,
                        on="Sector",
                        how="left",
                    )
                )

            if not investable.empty:

                sector_leaders_out = (
                    sector_leaders_out
                    .merge(
                        investable,
                        on="Sector",
                        how="left",
                    )
                )

            sector_leaders_out = (
                sector_leaders_out
                .merge(
                    sector_leadership[
                        [
                            "Sector",
                            "Sector Leadership Score",
                            "Sector Status",
                        ]
                    ],
                    on="Sector",
                    how="left",
                )
            )

        sector_leaders_out.to_excel(
            writer,
            sheet_name="Sector Leaders",
            index=False,
        )

        candidates_out.to_excel(
            writer,
            sheet_name="Current Candidates",
            index=False,
        )

        stock_leadership_out.to_excel(
            writer,
            sheet_name="Stock Leadership",
            index=False,
        )

        metadata_out.to_excel(
            writer,
            sheet_name="Universe Metadata",
            index=False,
        )

        historical_out.to_excel(
            writer,
            sheet_name="Historical Sectors",
            index=False,
        )

        sector_market_cap_out.to_excel(
            writer,
            sheet_name="Sector Market Cap",
            index=False,
        )

    print()
    print(
        f"Excel written : {OUTPUT_FILE}"
    )


# =====================================================================
# MAIN
# =====================================================================

def main():

    program_start = (
        time.perf_counter()
    )

    print()
    print("=" * 100)
    print(
        "SECTOR LEADERSHIP LAB"
    )
    print("=" * 100)

    print(
        "Purpose : Current Nifty 500 sector and stock leadership research"
    )

    print(
        f"Historical period : {HISTORICAL_PERIOD}"
    )

    print(
        "Started : "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    # =================================================================
    # STEP 1 - UNIVERSE
    # =================================================================

    step_start = (
        time.perf_counter()
    )

    print()
    print("=" * 100)
    print(
        "STEP 1 - Refreshing Nifty 500 universe"
    )
    print("=" * 100)

    # trade_data.py returns .NS symbols.
    # Preserve .NS when passing into trade_data.
    raw_symbols = (
        refresh_nifty500_universe()
    )

    symbols = yahoo_symbols(
        raw_symbols
    )

    symbols = list(
        dict.fromkeys(symbols)
    )

    print()
    print(
        f"Current Nifty 500 universe : "
        f"{len(symbols)}"
    )

    print(
        f"STEP 1 runtime : "
        f"{time.perf_counter() - step_start:.2f} seconds"
    )

    # =================================================================
    # STEP 2 - METADATA
    # =================================================================

    step_start = (
        time.perf_counter()
    )

    metadata = (
        get_sector_metadata(
            symbols
        )
    )

    print(
        f"STEP 2 runtime : "
        f"{time.perf_counter() - step_start:.2f} seconds"
    )

    # =================================================================
    # STEP 3 - MARKET DATA
    # =================================================================

    step_start = (
        time.perf_counter()
    )

    print()
    print("=" * 100)
    print(
        "STEP 3 - Downloading historical market data"
    )
    print("=" * 100)

    print()
    print(
        "Passing .NS symbols to trade_data.py"
    )

    print(
        f"Requested symbols : "
        f"{len(symbols)}"
    )

    raw_data, valid_symbols = (
        get_historical_market_data_for_symbols(
            symbols,
            period=HISTORICAL_PERIOD,
        )
    )

    prices = normalize_price_data(
        raw_data
    )

    if prices.empty:

        raise RuntimeError(
            "No usable historical price data was returned."
        )

    print()
    print(
        f"Price columns received : "
        f"{len(prices.columns)}"
    )

    print(
        f"Valid symbols           : "
        f"{len(valid_symbols)}"
    )

    print(
        f"Price date range        : "
        f"{prices.index.min()} -> "
        f"{prices.index.max()}"
    )

    print(
        f"STEP 3 runtime : "
        f"{time.perf_counter() - step_start:.2f} seconds"
    )

    # =================================================================
    # STEP 4 - STOCK ANALYSIS
    # =================================================================

    step_start = (
        time.perf_counter()
    )

    stock_analysis = (
        build_stock_analysis(
            prices,
            metadata,
        )
    )

    print(
        f"Stocks analyzed : "
        f"{len(stock_analysis)}"
    )

    print(
        f"STEP 4 runtime : "
        f"{time.perf_counter() - step_start:.2f} seconds"
    )

    # =================================================================
    # STEP 5 - CURRENT SECTOR ANALYSIS
    # =================================================================

    step_start = (
        time.perf_counter()
    )

    sector_current = (
        build_sector_current_analysis(
            stock_analysis
        )
    )

    print(
        f"Sectors analyzed : "
        f"{len(sector_current)}"
    )

    print(
        f"STEP 5 runtime : "
        f"{time.perf_counter() - step_start:.2f} seconds"
    )

    # =================================================================
    # STEP 6 - MARKET CAP / LEADERS
    # =================================================================

    step_start = (
        time.perf_counter()
    )

    sector_market_cap = (
        build_sector_market_cap_analysis(
            stock_analysis
        )
    )

    sector_market_cap_leaders = (
        identify_market_cap_leaders(
            metadata
        )
    )

    print(
        f"Market-cap leader sectors : "
        f"{len(sector_market_cap_leaders)}"
    )

    print(
        f"STEP 6 runtime : "
        f"{time.perf_counter() - step_start:.2f} seconds"
    )

    # =================================================================
    # STEP 7 - HISTORICAL SECTORS
    # =================================================================

    step_start = (
        time.perf_counter()
    )

    historical = (
        build_historical_sector_analysis(
            prices,
            metadata,
        )
    )

    print(
        f"Historical sector records : "
        f"{len(historical)}"
    )

    print(
        f"STEP 7 runtime : "
        f"{time.perf_counter() - step_start:.2f} seconds"
    )

    # =================================================================
    # STEP 8 - SECTOR LEADERSHIP
    # =================================================================

    step_start = (
        time.perf_counter()
    )

    sector_leadership = (
        build_sector_leadership(
            sector_current,
            historical,
        )
    )

    print(
        f"Sector leadership records : "
        f"{len(sector_leadership)}"
    )

    print(
        f"STEP 8 runtime : "
        f"{time.perf_counter() - step_start:.2f} seconds"
    )

    # =================================================================
    # STEP 9 - STOCK LEADERSHIP
    # =================================================================

    step_start = (
        time.perf_counter()
    )

    stock_leadership = (
        build_stock_leadership(
            stock_analysis,
            sector_leadership,
        )
    )

    print(
        f"Stock leadership records : "
        f"{len(stock_leadership)}"
    )

    print(
        f"STEP 9 runtime : "
        f"{time.perf_counter() - step_start:.2f} seconds"
    )

    # =================================================================
    # STEP 10 - CURRENT CANDIDATES
    # =================================================================

    step_start = (
        time.perf_counter()
    )

    candidates = (
        build_current_candidates(
            stock_leadership,
            sector_leadership,
        )
    )

    print(
        f"Candidate records : "
        f"{len(candidates)}"
    )

    print(
        f"STEP 10 runtime : "
        f"{time.perf_counter() - step_start:.2f} seconds"
    )

    # =================================================================
    # STEP 11 - EXCEL
    # =================================================================

    step_start = (
        time.perf_counter()
    )

    write_excel(

        sector_leadership=
            sector_leadership,

        sector_leaders=
            sector_market_cap_leaders,

        candidates=
            candidates,

        stock_leadership=
            stock_leadership,

        metadata=
            metadata,

        historical=
            historical,

        sector_market_cap=
            sector_market_cap,
    )

    print(
        f"STEP 11 runtime : "
        f"{time.perf_counter() - step_start:.2f} seconds"
    )

    # =================================================================
    # CONSOLE SUMMARY
    # =================================================================

    print_top_sectors(
        sector_leadership
    )

    print_sector_leaders(
        sector_leadership,
        sector_market_cap_leaders,
        stock_leadership,
    )

    print_candidates(
        candidates
    )

    # =================================================================
    # FINAL RUNTIME
    # =================================================================

    total_runtime = (
        time.perf_counter()
        - program_start
    )

    print()
    print("=" * 100)
    print(
        "SECTOR LEADERSHIP LAB COMPLETED"
    )
    print("=" * 100)

    print()
    print(
        f"Output file : "
        f"{OUTPUT_FILE}"
    )

    print(
        f"Total runtime : "
        f"{total_runtime / 60:.2f} minutes "
        f"({total_runtime:.2f} seconds)"
    )

    print()
    print(
        "Completed : "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    print("=" * 100)


# =====================================================================
# SINGLE ENTRY POINT
# =====================================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print()
        print("=" * 100)
        print(
            "PROGRAM INTERRUPTED BY USER"
        )
        print("=" * 100)

        sys.exit(1)

    except Exception as exc:

        print()
        print("=" * 100)
        print(
            "PROGRAM FAILED"
        )
        print("=" * 100)

        print()
        print(
            f"Error type : "
            f"{type(exc).__name__}"
        )

        print(
            f"Error      : "
            f"{exc}"
        )

        print()
        print(
            "The existing trade_data.py was NOT modified."
        )

        print("=" * 100)
        raise