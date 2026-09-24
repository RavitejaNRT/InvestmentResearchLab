"""
ETF5PercentLab — Production Signal Engine

Research source:
    results/etf_5percent_production_rules.json

Observation source:
    results/etf_5percent_condition_discovery_observations.csv

Production definition:
    Signal : Latest completed Day D close
    Entry  : Day D+1 open
    Target : Entry open * 1.05
    Stop   : NONE
    Horizon: 20 trading days

Production hierarchy:
    1. ETF-specific OOS-validated rule
    2. Global OOS-validated rule
    3. Nearest same-ETF historical analog
    4. ETF historical baseline

Important:
    This script DOES NOT rerun rule discovery.
    This script DOES NOT rerun the backtest.
    This script DOES NOT rerun OOS validation.

It only:
    - Loads saved research
    - Downloads fresh ETF market data
    - Builds current features
    - Matches saved OOS rules
    - Uses historical analog fallback where required
    - Ranks ETFs by expected trading days to +5%
    - Saves current production signal
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
import warnings
from datetime import datetime, time as dt_time
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf


# =============================================================================
# CONFIGURATION
# =============================================================================

IST = ZoneInfo("Asia/Kolkata")

TARGET_PCT = 0.05
HORIZON_DAYS = 20

MARKET_CLOSE_TIME = dt_time(15, 35)

DOWNLOAD_PERIOD = "2y"

METHOD_ETF_SPECIFIC = "ETF-SPECIFIC OOS RULE"
METHOD_GLOBAL = "GLOBAL OOS RULE"
METHOD_ANALOG = "NEAREST_HISTORICAL_ANALOG"
METHOD_BASELINE = "ETF HISTORICAL BASELINE"

ANALOG_K = 40
ANALOG_MIN_HISTORY = 20


# =============================================================================
# ETF UNIVERSE
# =============================================================================

ETF_UNIVERSE = {
    "AUTOBEES": {
        "symbol": "AUTOBEES.NS",
        "category": "Indian Sector - Auto",
    },
    "BANKBEES": {
        "symbol": "BANKBEES.NS",
        "category": "Indian Sector - Banks",
    },
    "CPSEETF": {
        "symbol": "CPSEETF.NS",
        "category": "Indian Sector - CPSE",
    },
    "FMCGIETF": {
        "symbol": "FMCGIETF.NS",
        "category": "Indian Sector - FMCG",
    },
    "GOLDBEES": {
        "symbol": "GOLDBEES.NS",
        "category": "Commodity - Gold",
    },
    "HNGSNGBEES": {
        "symbol": "HNGSNGBEES.NS",
        "category": "International - Hang Seng",
    },
    "ITBEES": {
        "symbol": "ITBEES.NS",
        "category": "Indian Sector - IT",
    },
    "MAFANG": {
        "symbol": "MAFANG.NS",
        "category": "International - FANG+",
    },
    "METALIETF": {
        "symbol": "METALIETF.NS",
        "category": "Indian Sector - Metal",
    },
    "MON100": {
        "symbol": "MON100.NS",
        "category": "International - NASDAQ 100",
    },
    "NIFTYBEES": {
        "symbol": "NIFTYBEES.NS",
        "category": "Indian Broad Market - Nifty 50",
    },
    "OILIETF": {
        "symbol": "OILIETF.NS",
        "category": "Indian Sector - Oil & Gas",
    },
    "PHARMABEES": {
        "symbol": "PHARMABEES.NS",
        "category": "Indian Sector - Pharma",
    },
    "PSUBNKBEES": {
        "symbol": "PSUBNKBEES.NS",
        "category": "Indian Sector - PSU Banks",
    },
    "PVTBANIETF": {
        "symbol": "PVTBANIETF.NS",
        "category": "Indian Sector - Private Banks",
    },
    "SILVERBEES": {
        "symbol": "SILVERBEES.NS",
        "category": "Commodity - Silver",
    },
}


FEATURES = [
    "RET_5",
    "RET_10",
    "RET_20",
    "RET_40",
    "RET_60",
    "RET_120",
    "RET_252",
    "RS_20",
    "RS_40",
    "RS_60",
    "RS_120",
    "DIST_SMA20",
    "DIST_SMA50",
    "DIST_SMA100",
    "DIST_SMA200",
    "DIST_HIGH_20",
    "DIST_HIGH_50",
    "DIST_HIGH_100",
    "DIST_HIGH_252",
    "BREAKOUT_20",
    "BREAKOUT_50",
    "RSI14",
    "VOLUME_RATIO_20",
]


FEATURE_WEIGHTS = {
    "RET_5": 1.0,
    "RET_10": 1.0,
    "RET_20": 1.1,
    "RET_40": 1.0,
    "RET_60": 1.0,
    "RET_120": 0.8,
    "RET_252": 0.8,
    "RS_20": 1.0,
    "RS_40": 1.0,
    "RS_60": 1.0,
    "RS_120": 0.8,
    "DIST_SMA20": 1.0,
    "DIST_SMA50": 1.0,
    "DIST_SMA100": 0.8,
    "DIST_SMA200": 0.8,
    "DIST_HIGH_20": 0.9,
    "DIST_HIGH_50": 0.9,
    "DIST_HIGH_100": 0.8,
    "DIST_HIGH_252": 0.8,
    "BREAKOUT_20": 0.9,
    "BREAKOUT_50": 0.9,
    "RSI14": 0.7,
    "VOLUME_RATIO_20": 0.6,
}


# =============================================================================
# PATHS
# =============================================================================

CURRENT_FILE = Path(__file__).resolve()

ETF_LAB_DIR = CURRENT_FILE.parent
SRC_DIR = ETF_LAB_DIR.parent
PROJECT_ROOT = SRC_DIR.parent

RESULTS_DIR = ETF_LAB_DIR / "results"

RESEARCH_JSON = RESULTS_DIR / "etf_5percent_production_rules.json"
OBSERVATIONS_CSV = RESULTS_DIR / "etf_5percent_condition_discovery_observations.csv"

CURRENT_SIGNAL_CSV = RESULTS_DIR / "etf_5percent_current_signal.csv"


# =============================================================================
# DISPLAY
# =============================================================================

def separator(char="=", length=100):
    print(char * length)


def section(title):
    print()
    separator()
    print(title)
    separator()


def safe_float(value, default=np.nan):
    try:
        if value is None:
            return default

        x = float(value)

        if not np.isfinite(x):
            return default

        return x

    except Exception:
        return default


def pct(value, decimals=2):
    """
    Format a decimal proportion as a percentage.

    Example:
        0.35 -> 35.00%
        -0.10 -> -10.00%
    """

    value = safe_float(value)

    if not np.isfinite(value):
        return "N/A"

    return f"{value * 100:.{decimals}f}%"


def days(value):
    value = safe_float(value)

    if not np.isfinite(value):
        return "N/A"

    return f"{value:.2f} trading days"


# =============================================================================
# RULE DISPLAY FORMATTING
# =============================================================================

PERCENT_FEATURES = {
    "RET_5",
    "RET_10",
    "RET_20",
    "RET_40",
    "RET_60",
    "RET_120",
    "RET_252",
    "RS_20",
    "RS_40",
    "RS_60",
    "RS_120",
    "DIST_SMA20",
    "DIST_SMA50",
    "DIST_SMA100",
    "DIST_SMA200",
    "DIST_HIGH_20",
    "DIST_HIGH_50",
    "DIST_HIGH_100",
    "DIST_HIGH_252",
    "BREAKOUT_20",
    "BREAKOUT_50",
}

ABSOLUTE_FEATURES = {
    "RSI14",
}

MULTIPLE_FEATURES = {
    "VOLUME_RATIO_20",
}


def format_rule_value(feature, value):
    """
    Format one rule threshold according to the feature's native units.

    DISPLAY ONLY.

    Examples:
        RET_20 = 0.10  -> 10.00%
        RS_120 = 0.05  -> 5.00%
        RSI14 = 35     -> 35.00
        VOLUME_RATIO_20 = 1.2 -> 1.20x
    """

    value = safe_float(value)

    if not np.isfinite(value):
        return "N/A"

    feature = str(feature).strip().upper()

    if feature in PERCENT_FEATURES:
        return f"{value * 100:.2f}%"

    if feature in ABSOLUTE_FEATURES:
        return f"{value:.2f}"

    if feature in MULTIPLE_FEATURES:
        return f"{value:.2f}x"

    return f"{value:.4f}"


def format_condition(condition):
    """
    Convert a structured saved condition into readable rule text.
    """

    if not isinstance(condition, dict):
        return ""

    feature = str(
        condition.get("feature", "")
    ).strip()

    if not feature:
        return ""

    op = str(
        condition.get("op", "")
    ).strip().lower()

    v1 = condition.get("v1")
    v2 = condition.get("v2")

    op_display = {
        "lt": "<",
        "le": "<=",
        "gt": ">",
        "ge": ">=",
        "range": "range",
    }.get(op, op)

    if op == "range":
        return (
            f"{feature} "
            f"{format_rule_value(feature, v1)} "
            f"to "
            f"{format_rule_value(feature, v2)}"
        )

    if op_display:
        return (
            f"{feature} {op_display} "
            f"{format_rule_value(feature, v1)}"
        )

    return (
        f"{feature} "
        f"{format_rule_value(feature, v1)}"
    )


def format_rule_for_display(rule):
    """
    Build rule text from structured conditions.

    This deliberately avoids blindly displaying rule['rule']
    because older research files may contain incorrectly formatted
    display text.

    Underlying research values are NOT changed.
    """

    if not isinstance(rule, dict):
        return ""

    conditions = rule.get(
        "conditions",
        []
    )

    if isinstance(
        conditions,
        list
    ) and conditions:

        formatted = []

        for condition in conditions:

            text = format_condition(
                condition
            )

            if text:
                formatted.append(
                    text
                )

        if formatted:
            return " AND ".join(
                formatted
            )

    raw_rule = rule.get(
        "rule",
        ""
    )

    if raw_rule is None:
        return ""

    return str(
        raw_rule
    )


# =============================================================================
# FRIENDLY DISPLAY HELPERS
# =============================================================================

def method_description(method):
    """
    Explain where the estimate came from.
    """

    if method == METHOD_ETF_SPECIFIC:
        return (
            "A validated historical rule specifically "
            "identified for this ETF."
        )

    if method == METHOD_GLOBAL:
        return (
            "A validated historical rule that applies "
            "across the ETF research universe."
        )

    if method == METHOD_ANALOG:
        return (
            "No validated rule matched, so the estimate "
            "uses the closest historical situations for this ETF."
        )

    if method == METHOD_BASELINE:
        return (
            "No validated rule or sufficient analog matched, "
            "so the ETF's historical average is used."
        )

    return "Historical research method."


def explain_feature(feature):
    """
    Human-readable explanation of technical features.
    """

    explanations = {
        "RET_5": "5-day price return",
        "RET_10": "10-day price return",
        "RET_20": "20-day price return",
        "RET_40": "40-day price return",
        "RET_60": "60-day price return",
        "RET_120": "120-day price return",
        "RET_252": "1-year price return",
        "RS_20": "20-day performance relative to NiftyBEES",
        "RS_40": "40-day performance relative to NiftyBEES",
        "RS_60": "60-day performance relative to NiftyBEES",
        "RS_120": "120-day performance relative to NiftyBEES",
        "DIST_SMA20": "distance from 20-day average",
        "DIST_SMA50": "distance from 50-day average",
        "DIST_SMA100": "distance from 100-day average",
        "DIST_SMA200": "distance from 200-day average",
        "DIST_HIGH_20": "distance from 20-day high",
        "DIST_HIGH_50": "distance from 50-day high",
        "DIST_HIGH_100": "distance from 100-day high",
        "DIST_HIGH_252": "distance from 1-year high",
        "BREAKOUT_20": "20-day breakout distance",
        "BREAKOUT_50": "50-day breakout distance",
        "RSI14": "14-day RSI momentum indicator",
        "VOLUME_RATIO_20": "volume compared with its 20-day average",
    }

    return explanations.get(
        str(feature).upper(),
        str(feature),
    )


def explain_condition(condition):
    """
    Turn a technical condition into a short explanatory sentence.

    Example:
        RS_120 >= 5.00%

    becomes:
        120-day relative strength is at least 5.00% above NiftyBEES.
    """

    if not isinstance(condition, dict):
        return ""

    feature = str(
        condition.get("feature", "")
    ).strip().upper()

    op = str(
        condition.get("op", "")
    ).strip().lower()

    v1 = safe_float(
        condition.get("v1")
    )

    v2 = safe_float(
        condition.get("v2")
    )

    if not feature or not np.isfinite(v1):
        return ""

    value_text = format_rule_value(
        feature,
        v1
    )

    feature_text = explain_feature(
        feature
    )

    if feature == "RSI14":

        if op == "lt":
            return (
                f"RSI is below {value_text}, "
                "which indicates relatively weak recent momentum."
            )

        if op == "le":
            return (
                f"RSI is at or below {value_text}."
            )

        if op == "gt":
            return (
                f"RSI is above {value_text}, "
                "indicating stronger recent momentum."
            )

        if op == "ge":
            return (
                f"RSI is at least {value_text}."
            )

    if feature.startswith("RS_"):

        period = feature.split("_")[1].replace(
            "20", "20-day"
        ).replace(
            "40", "40-day"
        ).replace(
            "60", "60-day"
        ).replace(
            "120", "120-day"
        )

        if op == "ge":
            return (
                f"{period} relative performance is at least "
                f"{value_text} versus NiftyBEES."
            )

        if op == "gt":
            return (
                f"{period} relative performance is above "
                f"{value_text} versus NiftyBEES."
            )

        if op == "lt":
            return (
                f"{period} relative performance is below "
                f"{value_text} versus NiftyBEES."
            )

        if op == "le":
            return (
                f"{period} relative performance is at or below "
                f"{value_text} versus NiftyBEES."
            )

    if feature.startswith("DIST_HIGH_"):

        period = feature.replace(
            "DIST_HIGH_",
            ""
        )

        if period == "252":
            period_text = "1-year"
        else:
            period_text = f"{period}-day"

        if op == "lt":
            return (
                f"Price is more than "
                f"{abs(v1) * 100:.2f}% below the "
                f"{period_text} high."
            )

        if op == "le":
            return (
                f"Price is at least "
                f"{abs(v1) * 100:.2f}% below the "
                f"{period_text} high."
            )

        if op == "ge":
            return (
                f"Price is within "
                f"{abs(v1) * 100:.2f}% of the "
                f"{period_text} high or above."
            )

    if feature.startswith("DIST_SMA"):

        period = feature.replace(
            "DIST_SMA",
            ""
        )

        if op == "lt":
            return (
                f"Price is below its {period}-day average "
                f"by at least {abs(v1) * 100:.2f}%."
            )

        if op == "le":
            return (
                f"Price is at or below its {period}-day average "
                f"by {abs(v1) * 100:.2f}% or more."
            )

        if op == "ge":
            return (
                f"Price is at least {v1 * 100:.2f}% above "
                f"its {period}-day average."
            )

    if feature.startswith("RET_"):

        period = feature.replace(
            "RET_",
            ""
        )

        if period == "252":
            period_text = "1-year"
        else:
            period_text = f"{period}-day"

        if op == "lt":
            return (
                f"{period_text} return is below {value_text}."
            )

        if op == "le":
            return (
                f"{period_text} return is at or below {value_text}."
            )

        if op == "gt":
            return (
                f"{period_text} return is above {value_text}."
            )

        if op == "ge":
            return (
                f"{period_text} return is at least {value_text}."
            )

    if feature.startswith("BREAKOUT_"):

        period = feature.replace(
            "BREAKOUT_",
            ""
        )

        if op == "lt":
            return (
                f"Price is more than {abs(v1) * 100:.2f}% "
                f"below the {period}-day breakout level."
            )

        if op == "ge":
            return (
                f"Price is at or above the {period}-day breakout level "
                f"threshold of {value_text}."
            )

    if feature == "VOLUME_RATIO_20":

        if op == "ge":
            return (
                f"Trading volume is at least {value_text} "
                "times its 20-day average."
            )

        if op == "gt":
            return (
                f"Trading volume is above {value_text} "
                "times its 20-day average."
            )

        if op == "lt":
            return (
                f"Trading volume is below {value_text} "
                "times its 20-day average."
            )

    # Generic fallback
    return (
        f"{feature_text} {op} {value_text}."
    )


def explain_rule(rule):
    """
    Create a readable explanation of a structured rule.
    """

    if not isinstance(rule, dict):
        return ""

    conditions = rule.get(
        "conditions",
        []
    )

    if not isinstance(
        conditions,
        list
    ):
        return ""

    explanations = []

    for condition in conditions:

        text = explain_condition(
            condition
        )

        if text:
            explanations.append(
                text
            )

    return " ".join(
        explanations
    )


# =============================================================================
# TIME / SIGNAL DATE
# =============================================================================

def get_current_ist():
    return datetime.now(IST)


def get_signal_cutoff(current_dt):
    """
    Determine the latest completed Indian market date.

    After 15:35 IST:
        today's close is considered available.

    Before 15:35 IST:
        today's close is NOT considered complete.
    """

    if current_dt.time() >= MARKET_CLOSE_TIME:
        return current_dt.date()

    return (
        current_dt - pd.Timedelta(days=1)
    ).date()


# =============================================================================
# JSON
# =============================================================================

def load_research():

    if not RESEARCH_JSON.exists():

        raise FileNotFoundError(
            f"Required research file not found:\n"
            f"{RESEARCH_JSON}\n\n"
            "Check that the research file exists under "
            "the project's results folder."
        )

    if not OBSERVATIONS_CSV.exists():

        raise FileNotFoundError(
            f"Required observations file not found:\n"
            f"{OBSERVATIONS_CSV}\n\n"
            "Check that the research JSON and observations CSV "
            "exist under the project's results folder."
        )

    with open(
        RESEARCH_JSON,
        "r",
        encoding="utf-8",
    ) as f:

        research = json.load(f)

    observations = pd.read_csv(
        OBSERVATIONS_CSV
    )

    return research, observations


# =============================================================================
# YFINANCE DATA EXTRACTION
# =============================================================================

def extract_symbol_frame(downloaded, symbol):

    if downloaded is None or downloaded.empty:
        return None

    try:

        if isinstance(
            downloaded.columns,
            pd.MultiIndex,
        ):

            if symbol in downloaded.columns.get_level_values(-1):

                frame = downloaded.xs(
                    symbol,
                    axis=1,
                    level=-1,
                    drop_level=True,
                )

                return frame.copy()

            if symbol in downloaded.columns.get_level_values(0):

                frame = downloaded.xs(
                    symbol,
                    axis=1,
                    level=0,
                    drop_level=True,
                )

                return frame.copy()

        required = {
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        }

        if required.intersection(
            set(downloaded.columns)
        ):

            return downloaded.copy()

    except Exception:
        pass

    return None


# =============================================================================
# DOWNLOAD
# =============================================================================

def download_market_data(signal_cutoff):

    section(
        "DOWNLOADING CURRENT ETF DATA"
    )

    symbols = [
        x["symbol"]
        for x in ETF_UNIVERSE.values()
    ]

    print(
        f"ETF count : {len(symbols)}"
    )

    print(
        f"History   : {DOWNLOAD_PERIOD}"
    )

    print(
        f"Cutoff    : {signal_cutoff}"
    )

    print()
    print(
        "Downloading market data..."
    )

    start = time.perf_counter()

    with warnings.catch_warnings():

        warnings.simplefilter(
            "ignore"
        )

        data = yf.download(
            tickers=symbols,
            period=DOWNLOAD_PERIOD,
            interval="1d",
            auto_adjust=False,
            progress=True,
            group_by="column",
            threads=True,
        )

    elapsed = (
        time.perf_counter()
        - start
    )

    frames = {}

    invalid = []

    for etf, info in ETF_UNIVERSE.items():

        symbol = info["symbol"]

        frame = extract_symbol_frame(
            data,
            symbol,
        )

        if frame is None or frame.empty:

            invalid.append(etf)
            continue

        required_columns = [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]

        if not all(
            c in frame.columns
            for c in required_columns
        ):

            invalid.append(etf)
            continue

        frame = frame[
            required_columns
        ].copy()

        frame.index = pd.to_datetime(
            frame.index
        )

        try:

            if frame.index.tz is not None:

                frame.index = (
                    frame.index.tz_localize(None)
                )

        except Exception:
            pass

        frame = frame.sort_index()

        for c in required_columns:

            frame[c] = pd.to_numeric(
                frame[c],
                errors="coerce",
            )

        frame = frame.dropna(
            subset=["Close"]
        )

        frame = frame[
            frame.index.date <= signal_cutoff
        ]

        if frame.empty:

            invalid.append(etf)
            continue

        frames[etf] = frame

    print()
    print(
        f"Download time : {elapsed:.2f} sec"
    )

    print(
        f"Valid ETFs    : {len(frames)}"
    )

    print(
        f"Invalid ETFs  : {len(invalid)}"
    )

    if invalid:

        print(
            f"Invalid list  : {', '.join(invalid)}"
        )

    if not frames:

        raise RuntimeError(
            "No ETF market data was downloaded successfully."
        )

    return frames


# =============================================================================
# TECHNICAL FEATURES
# =============================================================================

def calculate_rsi(close, period=14):
    """
    Wilder-style RSI using exponential smoothing.
    """

    delta = close.diff()

    gain = delta.clip(
        lower=0.0
    )

    loss = -delta.clip(
        upper=0.0
    )

    avg_gain = gain.ewm(
        alpha=1.0 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    avg_loss = loss.ewm(
        alpha=1.0 / period,
        adjust=False,
        min_periods=period,
    ).mean()

    rs = (
        avg_gain
        /
        avg_loss.replace(
            0,
            np.nan,
        )
    )

    rsi = (
        100.0
        -
        (
            100.0
            /
            (1.0 + rs)
        )
    )

    rsi = rsi.where(
        avg_loss != 0,
        np.where(
            avg_gain > 0,
            100.0,
            50.0,
        ),
    )

    return rsi


def build_features(frames):

    section(
        "BUILDING CURRENT FEATURES"
    )

    start = time.perf_counter()

    if "NIFTYBEES" not in frames:

        raise RuntimeError(
            "NIFTYBEES data is required for RS features "
            "but was not downloaded."
        )

    nifty_close = frames[
        "NIFTYBEES"
    ]["Close"].copy()

    nifty_returns = {}

    for n in [
        20,
        40,
        60,
        120,
    ]:

        nifty_returns[n] = (
            nifty_close
            /
            nifty_close.shift(n)
            -
            1.0
        )

    feature_frames = {}

    for etf, frame in frames.items():

        close = frame["Close"].copy()
        high = frame["High"].copy()
        volume = frame["Volume"].copy()

        f = pd.DataFrame(
            index=frame.index
        )

        # ------------------------------------------------------------------
        # Returns
        # ------------------------------------------------------------------

        for n in [
            5,
            10,
            20,
            40,
            60,
            120,
            252,
        ]:

            f[f"RET_{n}"] = (
                close
                /
                close.shift(n)
                -
                1.0
            )

        # ------------------------------------------------------------------
        # Relative strength vs NIFTYBEES
        # ------------------------------------------------------------------

        for n in [
            20,
            40,
            60,
            120,
        ]:

            etf_ret = (
                close
                /
                close.shift(n)
                -
                1.0
            )

            benchmark_ret = (
                nifty_returns[n]
                .reindex(f.index)
            )

            f[f"RS_{n}"] = (
                etf_ret
                -
                benchmark_ret
            )

        # ------------------------------------------------------------------
        # SMA distances
        # ------------------------------------------------------------------

        for n in [
            20,
            50,
            100,
            200,
        ]:

            sma = close.rolling(
                n,
                min_periods=n,
            ).mean()

            f[f"DIST_SMA{n}"] = (
                close
                /
                sma
                -
                1.0
            )

        # ------------------------------------------------------------------
        # Distance from rolling high
        # ------------------------------------------------------------------

        for n in [
            20,
            50,
            100,
            252,
        ]:

            rolling_high = high.rolling(
                n,
                min_periods=n,
            ).max()

            f[f"DIST_HIGH_{n}"] = (
                close
                /
                rolling_high
                -
                1.0
            )

        # ------------------------------------------------------------------
        # Breakout features
        # ------------------------------------------------------------------

        f["BREAKOUT_20"] = (
            f["DIST_HIGH_20"]
        )

        f["BREAKOUT_50"] = (
            f["DIST_HIGH_50"]
        )

        # ------------------------------------------------------------------
        # RSI
        # ------------------------------------------------------------------

        f["RSI14"] = calculate_rsi(
            close,
            14,
        )

        # ------------------------------------------------------------------
        # Volume ratio
        # ------------------------------------------------------------------

        avg_volume = volume.rolling(
            20,
            min_periods=20,
        ).mean()

        f["VOLUME_RATIO_20"] = (
            volume
            /
            avg_volume
        )

        f = f.replace(
            [np.inf, -np.inf],
            np.nan,
        )

        feature_frames[etf] = f

    elapsed = (
        time.perf_counter()
        - start
    )

    print(
        f"Feature time : {elapsed:.2f} sec"
    )

    return feature_frames


# =============================================================================
# RULE CONDITION MATCHING
# =============================================================================

def condition_matches(
    value,
    condition,
):

    value = safe_float(value)

    if not np.isfinite(value):
        return False

    op = str(
        condition.get(
            "op",
            "",
        )
    ).lower()

    v1 = safe_float(
        condition.get("v1")
    )

    v2 = safe_float(
        condition.get("v2")
    )

    if not np.isfinite(v1):
        return False

    if op == "lt":
        return value < v1

    if op == "le":
        return value <= v1

    if op == "gt":
        return value > v1

    if op == "ge":
        return value >= v1

    if op == "range":

        if not np.isfinite(v2):
            return False

        return (
            v1
            <= value
            <
            v2
        )

    return False


def rule_matches(
    current_row,
    rule,
):

    conditions = rule.get(
        "conditions",
        [],
    )

    if not conditions:
        return False

    for condition in conditions:

        feature = condition.get(
            "feature"
        )

        if feature not in current_row.index:
            return False

        value = current_row[
            feature
        ]

        if not condition_matches(
            value,
            condition,
        ):

            return False

    return True


# =============================================================================
# RULE STATISTICS
# =============================================================================

def get_rule_test_observations(rule):

    candidates = [
        "test_observations",
        "oos_observations",
        "test_obs",
        "oos_obs",
        "test_n",
        "oos_n",
        "test_count",
        "oos_count",
        "Evidence",
        "evidence",
    ]

    for key in candidates:

        if key not in rule:
            continue

        value = safe_float(
            rule.get(key),
            np.nan,
        )

        if (
            np.isfinite(value)
            and value >= 0
        ):

            return int(
                round(value)
            )

    return 0


def get_rule_test_hits(rule):

    candidates = [
        "test_hits",
        "oos_hits",
        "test_hit_count",
        "oos_hit_count",
    ]

    for key in candidates:

        if key not in rule:
            continue

        value = safe_float(
            rule.get(key),
            np.nan,
        )

        if (
            np.isfinite(value)
            and value >= 0
        ):

            return int(
                round(value)
            )

    return 0


def get_rule_hit_rate(rule):

    candidates = [
        "test_hit_rate",
        "oos_hit_rate",
        "Predicted_Hit_Rate",
        "predicted_hit_rate",
    ]

    for key in candidates:

        if key not in rule:
            continue

        value = safe_float(
            rule.get(key),
            np.nan,
        )

        if np.isfinite(value):
            return value

    n = get_rule_test_observations(
        rule
    )

    h = get_rule_test_hits(
        rule
    )

    if n > 0:
        return h / n

    return np.nan


def get_rule_expected_days(rule):

    candidates = [
        "test_expected_days_20",
        "oos_expected_days_20",
        "Predicted_Expected_Days_20",
        "predicted_expected_days_20",
    ]

    for key in candidates:

        if key not in rule:
            continue

        value = safe_float(
            rule.get(key),
            np.nan,
        )

        if np.isfinite(value):
            return value

    return np.nan


def get_rule_median_days(rule):

    candidates = [
        "test_median_days",
        "oos_median_days",
        "Predicted_Median_Days",
        "predicted_median_days",
    ]

    for key in candidates:

        if key not in rule:
            continue

        value = safe_float(
            rule.get(key),
            np.nan,
        )

        if np.isfinite(value):
            return value

    return np.nan


# =============================================================================
# RULE AGGREGATION
# =============================================================================

def aggregate_rule_results(
    matched_rules
):

    if not matched_rules:

        return {
            "hit_rate": np.nan,
            "expected_days": np.nan,
            "median_days": np.nan,
            "evidence": 0,
        }

    valid = []

    for rule in matched_rules:

        n = get_rule_test_observations(
            rule
        )

        hit_rate = get_rule_hit_rate(
            rule
        )

        expected = get_rule_expected_days(
            rule
        )

        median = get_rule_median_days(
            rule
        )

        if n <= 0:
            continue

        if not np.isfinite(hit_rate):
            continue

        if not np.isfinite(expected):
            continue

        valid.append(
            {
                "n": n,
                "hit_rate": hit_rate,
                "expected": expected,
                "median": median,
            }
        )

    if not valid:

        return {
            "hit_rate": np.nan,
            "expected_days": np.nan,
            "median_days": np.nan,
            "evidence": 0,
        }

    total_n = sum(
        x["n"]
        for x in valid
    )

    weighted_hit = (
        sum(
            x["hit_rate"] * x["n"]
            for x in valid
        )
        /
        total_n
    )

    weighted_expected = (
        sum(
            x["expected"] * x["n"]
            for x in valid
        )
        /
        total_n
    )

    median_values = [
        x
        for x in valid
        if np.isfinite(x["median"])
    ]

    if median_values:

        weighted_median = (
            sum(
                x["median"] * x["n"]
                for x in median_values
            )
            /
            sum(
                x["n"]
                for x in median_values
            )
        )

    else:

        weighted_median = np.nan

    return {
        "hit_rate": weighted_hit,
        "expected_days": weighted_expected,
        "median_days": weighted_median,
        "evidence": total_n,
    }


# =============================================================================
# BEST RULE
# =============================================================================

def choose_best_rule(
    matched_rules
):

    if not matched_rules:
        return None

    ranked = []

    for rule in matched_rules:

        expected = get_rule_expected_days(
            rule
        )

        hit_rate = get_rule_hit_rate(
            rule
        )

        evidence = get_rule_test_observations(
            rule
        )

        if not np.isfinite(expected):
            continue

        ranked.append(
            (
                expected,
                -safe_float(
                    hit_rate,
                    -np.inf,
                ),
                -evidence,
                rule,
            )
        )

    if not ranked:
        return None

    ranked.sort(
        key=lambda x: (
            x[0],
            x[1],
            x[2],
        )
    )

    return ranked[0][3]


# =============================================================================
# SAME-ETF HISTORICAL ANALOG
# =============================================================================

def normalise_observation_columns(df):

    out = df.copy()

    rename = {}

    for col in out.columns:

        clean = str(col).strip()

        normalized = (
            clean
            .replace(" ", "_")
            .replace("-", "_")
            .replace("/", "_")
        )

        rename[col] = normalized

    out = out.rename(
        columns=rename
    )

    return out


def find_column(
    df,
    candidates,
):

    lookup = {
        str(c).lower(): c
        for c in df.columns
    }

    for candidate in candidates:

        key = candidate.lower()

        if key in lookup:
            return lookup[key]

    return None


def get_observation_etf_column(df):

    return find_column(
        df,
        [
            "ETF",
            "etf",
            "Symbol",
            "symbol",
            "ticker",
            "Ticker",
        ],
    )


def get_observation_date_column(df):

    return find_column(
        df,
        [
            "Signal_Date",
            "signal_date",
            "SignalDate",
            "Date",
            "date",
            "timestamp",
        ],
    )


def get_observation_hit_column(df):

    return find_column(
        df,
        [
            "Hit",
            "hit",
            "Target_Hit",
            "target_hit",
            "Success",
            "success",
            "Hit_Within_20",
            "hit_within_20",
        ],
    )


def get_observation_days_column(df):

    return find_column(
        df,
        [
            "Hit_Day",
            "hit_day",
            "HitDays",
            "hit_days",
            "Days_To_Target",
            "days_to_target",
            "Target_Day",
            "target_day",
            "Expected_Days_20",
            "expected_days_20",
        ],
    )


def convert_hit_value(value):

    if pd.isna(value):
        return np.nan

    if isinstance(value, bool):

        return (
            1.0
            if value
            else 0.0
        )

    if isinstance(value, str):

        x = value.strip().lower()

        if x in {
            "true",
            "yes",
            "y",
            "hit",
            "success",
            "1",
        }:

            return 1.0

        if x in {
            "false",
            "no",
            "n",
            "miss",
            "failure",
            "0",
        }:

            return 0.0

    try:

        x = float(value)

        if np.isfinite(x):
            return x

    except Exception:
        pass

    return np.nan


def prepare_observations(
    observations
):

    df = normalise_observation_columns(
        observations
    )

    etf_col = get_observation_etf_column(
        df
    )

    if etf_col is None:

        raise RuntimeError(
            "Could not identify ETF column in the observations CSV."
        )

    df["_ETF_"] = (
        df[etf_col]
        .astype(str)
        .str.strip()
    )

    date_col = get_observation_date_column(
        df
    )

    if date_col is not None:

        df["_DATE_"] = pd.to_datetime(
            df[date_col],
            errors="coerce",
        )

        try:

            if df["_DATE_"].dt.tz is not None:

                df["_DATE_"] = (
                    df["_DATE_"]
                    .dt.tz_localize(None)
                )

        except Exception:
            pass

    else:

        df["_DATE_"] = pd.NaT

    hit_col = get_observation_hit_column(
        df
    )

    if hit_col is not None:

        df["_HIT_"] = (
            df[hit_col]
            .map(convert_hit_value)
        )

    else:

        df["_HIT_"] = np.nan

    days_col = get_observation_days_column(
        df
    )

    if days_col is not None:

        df["_DAYS_"] = pd.to_numeric(
            df[days_col],
            errors="coerce",
        )

    else:

        df["_DAYS_"] = np.nan

    return df


def get_feature_column(
    df,
    feature,
):

    if feature in df.columns:
        return feature

    lookup = {
        str(c).lower(): c
        for c in df.columns
    }

    return lookup.get(
        feature.lower()
    )


def calculate_robust_distance(
    current_row,
    historical_df,
):

    if historical_df.empty:

        return pd.Series(
            dtype=float
        )

    distances = pd.Series(
        np.nan,
        index=historical_df.index,
        dtype=float,
    )

    available_features = []

    for feature in FEATURES:

        hist_col = get_feature_column(
            historical_df,
            feature,
        )

        if hist_col is None:
            continue

        current_value = safe_float(
            current_row.get(
                feature,
                np.nan,
            ),
            np.nan,
        )

        if not np.isfinite(
            current_value
        ):
            continue

        hist_values = pd.to_numeric(
            historical_df[hist_col],
            errors="coerce",
        )

        hist_values = (
            hist_values.replace(
                [np.inf, -np.inf],
                np.nan,
            )
        )

        finite_hist = hist_values[
            np.isfinite(hist_values)
        ]

        if finite_hist.empty:
            continue

        median = float(
            finite_hist.median()
        )

        absolute_deviation = np.abs(
            finite_hist.to_numpy(
                dtype=float
            )
            -
            median
        )

        absolute_deviation = (
            absolute_deviation[
                np.isfinite(
                    absolute_deviation
                )
            ]
        )

        if len(
            absolute_deviation
        ) == 0:

            scale = np.nan

        else:

            scale = float(
                np.median(
                    absolute_deviation
                )
            )

        if (
            not np.isfinite(scale)
            or scale <= 1e-12
        ):

            std = float(
                finite_hist.std()
            )

            if (
                np.isfinite(std)
                and std > 1e-12
            ):

                scale = std

            else:

                scale = 1.0

        current_delta = (
            current_value
            -
            median
        ) / scale

        if not np.isfinite(
            current_delta
        ):
            continue

        available_features.append(
            (
                feature,
                hist_col,
                scale,
                median,
                current_value,
            )
        )

    if not available_features:
        return distances

    distance_sum = pd.Series(
        0.0,
        index=historical_df.index,
    )

    weight_sum = pd.Series(
        0.0,
        index=historical_df.index,
    )

    for (
        feature,
        hist_col,
        scale,
        median,
        current_value,
    ) in available_features:

        hist_values = pd.to_numeric(
            historical_df[hist_col],
            errors="coerce",
        ).replace(
            [np.inf, -np.inf],
            np.nan,
        )

        hist_array = (
            hist_values.to_numpy(
                dtype=float
            )
        )

        valid = np.isfinite(
            hist_array
        )

        if not valid.any():
            continue

        z = np.full(
            len(hist_array),
            np.nan,
            dtype=float,
        )

        z[valid] = (
            hist_array[valid]
            -
            median
        ) / scale

        valid_z = np.isfinite(z)

        if not valid_z.any():
            continue

        weight = float(
            FEATURE_WEIGHTS.get(
                feature,
                1.0,
            )
        )

        positions = np.flatnonzero(
            valid_z
        )

        distance_sum.iloc[
            positions
        ] += (
            np.abs(
                z[valid_z]
            )
            *
            weight
        )

        weight_sum.iloc[
            positions
        ] += weight

    valid_rows = (
        weight_sum > 0
    )

    distances.loc[
        valid_rows
    ] = (
        distance_sum.loc[
            valid_rows
        ]
        /
        weight_sum.loc[
            valid_rows
        ]
    )

    distances = distances.replace(
        [np.inf, -np.inf],
        np.nan,
    )

    return distances


def analog_estimate(
    etf,
    current_row,
    observations,
    signal_date,
):

    if observations.empty:
        return None

    df = observations.copy()

    etf_mask = (
        df["_ETF_"]
        .astype(str)
        .str.upper()
        ==
        etf.upper()
    )

    df = df.loc[
        etf_mask
    ].copy()

    if df.empty:
        return None

    if "_DATE_" in df.columns:

        if pd.notna(
            df["_DATE_"]
        ).any():

            signal_timestamp = pd.Timestamp(
                signal_date
            )

            valid_date = (
                df["_DATE_"].isna()
                |
                (
                    df["_DATE_"]
                    <
                    signal_timestamp
                )
            )

            df = df.loc[
                valid_date
            ].copy()

    if len(df) < ANALOG_MIN_HISTORY:
        return None

    distances = calculate_robust_distance(
        current_row=current_row,
        historical_df=df,
    )

    finite_distance = distances[
        np.isfinite(distances)
    ]

    if len(finite_distance) < ANALOG_MIN_HISTORY:
        return None

    k = min(
        ANALOG_K,
        len(finite_distance),
    )

    nearest_index = (
        finite_distance
        .sort_values()
        .head(k)
        .index
    )

    nearest = df.loc[
        nearest_index
    ].copy()

    # ------------------------------------------------------------------
    # Hit rate
    # ------------------------------------------------------------------

    hit_values = nearest[
        "_HIT_"
    ].map(convert_hit_value)

    hit_values = hit_values[
        np.isfinite(hit_values)
    ]

    if len(hit_values) > 0:

        hit_rate = float(
            hit_values.mean()
        )

    else:

        hit_rate = np.nan

    # ------------------------------------------------------------------
    # Expected days
    # ------------------------------------------------------------------

    day_values = pd.to_numeric(
        nearest["_DAYS_"],
        errors="coerce",
    )

    day_values = day_values.replace(
        [np.inf, -np.inf],
        np.nan,
    )

    if day_values.notna().any():

        days_array = (
            day_values.to_numpy(
                dtype=float
            )
        )

        hit_array = (
            nearest["_HIT_"]
            .to_numpy(dtype=float)
        )

        expected_values = np.full(
            len(nearest),
            np.nan,
            dtype=float,
        )

        valid_days = np.isfinite(
            days_array
        )

        expected_values[
            valid_days
        ] = np.minimum(
            days_array[
                valid_days
            ],
            HORIZON_DAYS,
        )

        miss_mask = (
            np.isfinite(hit_array)
            &
            (hit_array <= 0)
        )

        expected_values[
            miss_mask & ~valid_days
        ] = HORIZON_DAYS

        valid_expected = (
            expected_values[
                np.isfinite(
                    expected_values
                )
            ]
        )

        if len(valid_expected) > 0:

            expected_days = float(
                np.mean(
                    valid_expected
                )
            )

        else:

            expected_days = np.nan

    else:

        expected_days = np.nan

    # ------------------------------------------------------------------
    # Precomputed expected days fallback
    # ------------------------------------------------------------------

    if not np.isfinite(
        expected_days
    ):

        candidate = find_column(
            nearest,
            [
                "Expected_Days_20",
                "expected_days_20",
                "Predicted_Expected_Days_20",
                "predicted_expected_days_20",
            ],
        )

        if candidate is not None:

            values = pd.to_numeric(
                nearest[candidate],
                errors="coerce",
            )

            values = values.replace(
                [np.inf, -np.inf],
                np.nan,
            ).dropna()

            if len(values) > 0:

                expected_days = float(
                    values.mean()
                )

    # ------------------------------------------------------------------
    # Median hit days
    # ------------------------------------------------------------------

    hit_days = day_values[
        day_values > 0
    ]

    if len(hit_days) > 0:

        median_days = float(
            hit_days.median()
        )

    else:

        median_days = np.nan

    if not np.isfinite(
        expected_days
    ):

        return None

    return {
        "hit_rate": hit_rate,
        "expected_days": expected_days,
        "median_days": median_days,
        "evidence": int(
            len(nearest)
        ),
        "nearest_observations": int(
            len(nearest)
        ),
    }


# =============================================================================
# ETF HISTORICAL BASELINE
# =============================================================================

def baseline_estimate(
    etf,
    observations,
    signal_date,
):

    if observations.empty:
        return None

    df = observations.copy()

    mask = (
        df["_ETF_"]
        .astype(str)
        .str.upper()
        ==
        etf.upper()
    )

    df = df.loc[
        mask
    ].copy()

    if df.empty:
        return None

    if "_DATE_" in df.columns:

        signal_timestamp = pd.Timestamp(
            signal_date
        )

        dated = df["_DATE_"].notna()

        df = df.loc[
            ~dated
            |
            (
                df["_DATE_"]
                <
                signal_timestamp
            )
        ].copy()

    if len(df) < ANALOG_MIN_HISTORY:
        return None

    hits = df[
        "_HIT_"
    ].map(convert_hit_value)

    hits = hits[
        np.isfinite(hits)
    ]

    if len(hits) == 0:
        return None

    hit_rate = float(
        hits.mean()
    )

    days_values = pd.to_numeric(
        df["_DAYS_"],
        errors="coerce",
    )

    days_values = days_values.replace(
        [np.inf, -np.inf],
        np.nan,
    )

    valid_days = days_values[
        np.isfinite(days_values)
    ]

    if len(valid_days) > 0:

        expected_days = float(
            valid_days.mean()
        )

        median_days = float(
            valid_days.median()
        )

    else:

        expected_days = np.nan
        median_days = np.nan

    if not np.isfinite(
        expected_days
    ):

        return None

    return {
        "hit_rate": hit_rate,
        "expected_days": expected_days,
        "median_days": median_days,
        "evidence": int(
            len(df)
        ),
    }


# =============================================================================
# FEATURE SNAPSHOT
# =============================================================================

def get_current_row(
    feature_frame
):

    if feature_frame.empty:
        return None

    frame = feature_frame.dropna(
        subset=(
            ["Close"]
            if "Close"
            in feature_frame.columns
            else None
        )
    )

    if frame.empty:
        return None

    return frame.iloc[-1]


# =============================================================================
# CURRENT SIGNAL ESTIMATION
# =============================================================================

def estimate_current_signal(
    etf,
    category,
    feature_frame,
    specific_rules,
    global_rules,
    observations,
    signal_date,
):

    if feature_frame.empty:
        return None

    current = feature_frame.iloc[-1]

    # ------------------------------------------------------------------
    # 1. ETF-specific OOS rules
    # ------------------------------------------------------------------

    etf_rules = specific_rules.get(
        etf,
        []
    )

    matched_specific = [
        rule
        for rule in etf_rules
        if rule_matches(
            current,
            rule,
        )
    ]

    if matched_specific:

        aggregate = aggregate_rule_results(
            matched_specific
        )

        best_rule = choose_best_rule(
            matched_specific
        )

        best_rule_text = (
            format_rule_for_display(
                best_rule
            )
            if best_rule is not None
            else ""
        )

        best_rule_explanation = (
            explain_rule(
                best_rule
            )
            if best_rule is not None
            else ""
        )

        best_hit = (
            get_rule_hit_rate(
                best_rule
            )
            if best_rule is not None
            else np.nan
        )

        best_expected = (
            get_rule_expected_days(
                best_rule
            )
            if best_rule is not None
            else np.nan
        )

        rationale = (
            f"{len(matched_specific)} "
            f"ETF-specific OOS-validated rule(s) "
            f"match today's market state. "
            f"Historical evidence: "
            f"{aggregate['evidence']:,} observations. "
        )

        if best_rule_text:

            rationale += (
                f"Best rule: {best_rule_text}. "
                f"Historical hit rate: "
                f"{pct(best_hit, 1)}. "
                f"Historical expected time: "
                f"{days(best_expected)}."
            )

        result = {
            "ETF": etf,
            "Category": category,
            "Signal_Date": pd.Timestamp(
                signal_date
            ).strftime(
                "%Y-%m-%d"
            ),
            "Current_Close": safe_float(
                current.get(
                    "Close",
                    np.nan,
                )
            ),
            "Method": METHOD_ETF_SPECIFIC,
            "Matched_Rules": len(
                matched_specific
            ),
            "Evidence": aggregate[
                "evidence"
            ],
            "Predicted_Hit_Rate": aggregate[
                "hit_rate"
            ],
            "Predicted_Median_Days": aggregate[
                "median_days"
            ],
            "Predicted_Expected_Days_20": aggregate[
                "expected_days"
            ],
            "Best_Matching_Rule": best_rule_text,
            "Rule_Explanation": best_rule_explanation,
            "Rationale": rationale,
        }

        return add_feature_values(
            result,
            current,
        )

    # ------------------------------------------------------------------
    # 2. Global OOS rules
    # ------------------------------------------------------------------

    matched_global = [
        rule
        for rule in global_rules
        if rule_matches(
            current,
            rule,
        )
    ]

    if matched_global:

        aggregate = aggregate_rule_results(
            matched_global
        )

        best_rule = choose_best_rule(
            matched_global
        )

        best_rule_text = (
            format_rule_for_display(
                best_rule
            )
            if best_rule is not None
            else ""
        )

        best_rule_explanation = (
            explain_rule(
                best_rule
            )
            if best_rule is not None
            else ""
        )

        best_hit = (
            get_rule_hit_rate(
                best_rule
            )
            if best_rule is not None
            else np.nan
        )

        best_expected = (
            get_rule_expected_days(
                best_rule
            )
            if best_rule is not None
            else np.nan
        )

        rationale = (
            f"{len(matched_global)} "
            f"global OOS-validated rule(s) "
            f"match today's market state. "
            f"Historical evidence: "
            f"{aggregate['evidence']:,} observations. "
        )

        if best_rule_text:

            rationale += (
                f"Best rule: {best_rule_text}. "
                f"Historical hit rate: "
                f"{pct(best_hit, 1)}. "
                f"Historical expected time: "
                f"{days(best_expected)}."
            )

        result = {
            "ETF": etf,
            "Category": category,
            "Signal_Date": pd.Timestamp(
                signal_date
            ).strftime(
                "%Y-%m-%d"
            ),
            "Current_Close": safe_float(
                current.get(
                    "Close",
                    np.nan,
                )
            ),
            "Method": METHOD_GLOBAL,
            "Matched_Rules": len(
                matched_global
            ),
            "Evidence": aggregate[
                "evidence"
            ],
            "Predicted_Hit_Rate": aggregate[
                "hit_rate"
            ],
            "Predicted_Median_Days": aggregate[
                "median_days"
            ],
            "Predicted_Expected_Days_20": aggregate[
                "expected_days"
            ],
            "Best_Matching_Rule": best_rule_text,
            "Rule_Explanation": best_rule_explanation,
            "Rationale": rationale,
        }

        return add_feature_values(
            result,
            current,
        )

    # ------------------------------------------------------------------
    # 3. Same-ETF nearest historical analog
    # ------------------------------------------------------------------

    analog = analog_estimate(
        etf=etf,
        current_row=current,
        observations=observations,
        signal_date=signal_date,
    )

    if analog is not None:

        result = {
            "ETF": etf,
            "Category": category,
            "Signal_Date": pd.Timestamp(
                signal_date
            ).strftime(
                "%Y-%m-%d"
            ),
            "Current_Close": safe_float(
                current.get(
                    "Close",
                    np.nan,
                )
            ),
            "Method": METHOD_ANALOG,
            "Matched_Rules": 0,
            "Evidence": analog[
                "evidence"
            ],
            "Predicted_Hit_Rate": analog[
                "hit_rate"
            ],
            "Predicted_Median_Days": analog[
                "median_days"
            ],
            "Predicted_Expected_Days_20": analog[
                "expected_days"
            ],
            "Best_Matching_Rule": "",
            "Rule_Explanation": "",
            "Rationale": (
                "No validated ETF-specific or global "
                "rule matched. The estimate uses the "
                f"{analog['evidence']} closest historical "
                "situations for this ETF."
            ),
        }

        return add_feature_values(
            result,
            current,
        )

    # ------------------------------------------------------------------
    # 4. ETF historical baseline
    # ------------------------------------------------------------------

    baseline = baseline_estimate(
        etf=etf,
        observations=observations,
        signal_date=signal_date,
    )

    if baseline is not None:

        result = {
            "ETF": etf,
            "Category": category,
            "Signal_Date": pd.Timestamp(
                signal_date
            ).strftime(
                "%Y-%m-%d"
            ),
            "Current_Close": safe_float(
                current.get(
                    "Close",
                    np.nan,
                )
            ),
            "Method": METHOD_BASELINE,
            "Matched_Rules": 0,
            "Evidence": baseline[
                "evidence"
            ],
            "Predicted_Hit_Rate": baseline[
                "hit_rate"
            ],
            "Predicted_Median_Days": baseline[
                "median_days"
            ],
            "Predicted_Expected_Days_20": baseline[
                "expected_days"
            ],
            "Best_Matching_Rule": "",
            "Rule_Explanation": "",
            "Rationale": (
                "No validated ETF-specific or global "
                "rule matched and nearest historical "
                "analog evidence was insufficient. "
                f"The estimate uses {baseline['evidence']} "
                "eligible historical observations."
            ),
        }

        return add_feature_values(
            result,
            current,
        )

    return None


def add_feature_values(
    result,
    current,
):

    for feature in FEATURES:

        result[feature] = safe_float(
            current.get(
                feature,
                np.nan,
            )
        )

    return result


# =============================================================================
# DATA FRAME PREPARATION
# =============================================================================

def prepare_feature_frames(
    frames,
    feature_frames,
):

    output = {}

    for etf, feature_frame in feature_frames.items():

        market = frames[etf]

        merged = feature_frame.copy()

        for column in [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]:

            merged[column] = (
                market[column]
                .reindex(
                    merged.index
                )
            )

        output[etf] = merged

    return output


# =============================================================================
# FRIENDLY RESULT DISPLAY
# =============================================================================

def print_signal_row(
    row
):

    rank = int(
        row["Rank"]
    )

    etf = str(
        row["ETF"]
    )

    category = str(
        row["Category"]
    )

    expected = days(
        row["Predicted_Expected_Days_20"]
    )

    hit_rate = pct(
        row["Predicted_Hit_Rate"],
        2,
    )

    median = days(
        row["Predicted_Median_Days"]
    )

    evidence = int(
        row["Evidence"]
    )

    method = str(
        row["Method"]
    )

    print()
    print(
        f"{rank:2d}. {etf} — {category}"
    )

    print(
        f"    Historical time to +5% : "
        f"~{expected}"
    )

    print(
        f"    Historical hit rate     : "
        f"{hit_rate} "
        f"(reached +5% within {HORIZON_DAYS} trading days)"
    )

    if median != "N/A":

        print(
            f"    Median successful time  : "
            f"~{median}"
        )

    print(
        f"    Historical evidence     : "
        f"{evidence:,} observations"
    )

    print(
        f"    Research method         : "
        f"{method}"
    )

    print(
        f"    What this means         : "
        f"{method_description(method)}"
    )

    rule = str(
        row.get(
            "Best_Matching_Rule",
            ""
        )
    ).strip()

    explanation = str(
        row.get(
            "Rule_Explanation",
            ""
        )
    ).strip()

    if rule:

        print(
            f"    Matched condition       : "
            f"{rule}"
        )

    if explanation:

        print(
            f"    Condition explained     : "
            f"{explanation}"
        )


# =============================================================================
# MAIN
# =============================================================================

def main():

    total_start = time.perf_counter()

    current_dt = get_current_ist()

    signal_cutoff = get_signal_cutoff(
        current_dt
    )

    print()

    separator()

    print(
        "ETF5PercentLab — PRODUCTION SIGNAL"
    )

    separator()

    print(
        f"Current IST : "
        f"{current_dt.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    print()

    print(
        "SIGNAL INTERPRETATION"
    )

    print(
        "  Today's close is used after 15:35 IST."
    )

    print(
        "  The model asks: "
        "historically, how quickly did similar situations reach +5%?"
    )

    print(
        f"  Research horizon: {HORIZON_DAYS} trading days."
    )

    print()

    print(
        f"Data cutoff : {signal_cutoff}"
    )

    # ----------------------------------------------------------------------
    # LOAD SAVED RESEARCH
    # ----------------------------------------------------------------------

    section(
        "LOADING SAVED ETF 5% RESEARCH"
    )

    print(
        "Research file:"
    )

    print(
        f"  {RESEARCH_JSON}"
    )

    print()

    print(
        "Historical observations:"
    )

    print(
        f"  {OBSERVATIONS_CSV}"
    )

    research, observations_raw = (
        load_research()
    )

    observations = prepare_observations(
        observations_raw
    )

    print()

    print(
        f"Historical observations loaded : "
        f"{len(observations):,}"
    )

    # ----------------------------------------------------------------------
    # RESEARCH STATUS
    # ----------------------------------------------------------------------

    section(
        "SAVED RESEARCH STATUS"
    )

    metadata = research.get(
        "metadata",
        {}
    )

    global_rules = research.get(
        "global_oos_rules",
        []
    )

    specific_rules = research.get(
        "etf_specific_oos_rules",
        {}
    )

    print(
        "Research version : "
        f"{metadata.get('version', 'UNKNOWN')}"
    )

    print(
        "Generated        : "
        f"{metadata.get('generated_at', 'UNKNOWN')}"
    )

    print(
        "Research cutoff  : "
        f"{metadata.get('research_cutoff', 'UNKNOWN')}"
    )

    print(
        "Train/OOS split  : "
        f"{metadata.get('train_test_split_date', 'UNKNOWN')}"
    )

    print(
        "Global OOS rules : "
        f"{len(global_rules)}"
    )

    specific_count = sum(
        len(v)
        for v in specific_rules.values()
        if isinstance(v, list)
    )

    print(
        "ETF-specific OOS : "
        f"{specific_count}"
    )

    print()

    print(
        "Rule values:"
    )

    print(
        "  RSI14            = absolute 0–100"
    )

    print(
        "  Returns / RS     = percentages"
    )

    print(
        "  Distance         = percentages"
    )

    print(
        "  Volume ratio     = x times average"
    )

    # ----------------------------------------------------------------------
    # DOWNLOAD CURRENT MARKET DATA
    # ----------------------------------------------------------------------

    frames = download_market_data(
        signal_cutoff=signal_cutoff
    )

    # ----------------------------------------------------------------------
    # FEATURES
    # ----------------------------------------------------------------------

    feature_frames = build_features(
        frames
    )

    feature_frames = prepare_feature_frames(
        frames,
        feature_frames,
    )

    # ----------------------------------------------------------------------
    # SIGNAL ESTIMATION
    # ----------------------------------------------------------------------

    section(
        "CURRENT SIGNAL ESTIMATION"
    )

    signal_start = time.perf_counter()

    results = []

    for etf, info in ETF_UNIVERSE.items():

        if etf not in feature_frames:
            continue

        try:

            result = estimate_current_signal(
                etf=etf,
                category=info["category"],
                feature_frame=feature_frames[etf],
                specific_rules=specific_rules,
                global_rules=global_rules,
                observations=observations,
                signal_date=signal_cutoff,
            )

            if result is not None:

                results.append(
                    result
                )

        except Exception as exc:

            print(
                f"WARNING: {etf} signal estimation failed: {exc}"
            )

    signal_elapsed = (
        time.perf_counter()
        - signal_start
    )

    print(
        f"Current signal calculation : "
        f"{signal_elapsed:.2f} sec"
    )

    if not results:

        raise RuntimeError(
            "No current ETF signals could be generated."
        )

    # ----------------------------------------------------------------------
    # DATAFRAME
    # ----------------------------------------------------------------------

    result_df = pd.DataFrame(
        results
    )

    result_df = result_df[
        np.isfinite(
            pd.to_numeric(
                result_df[
                    "Predicted_Expected_Days_20"
                ],
                errors="coerce",
            )
        )
    ].copy()

    if result_df.empty:

        raise RuntimeError(
            "No ETF has a valid expected +5% trading-day estimate."
        )

    # ----------------------------------------------------------------------
    # RANKING
    # ----------------------------------------------------------------------

    result_df = result_df.sort_values(
        by=[
            "Predicted_Expected_Days_20",
            "Predicted_Hit_Rate",
            "Evidence",
        ],
        ascending=[
            True,
            False,
            False,
        ],
        kind="mergesort",
    ).reset_index(
        drop=True
    )

    result_df.insert(
        0,
        "Rank",
        np.arange(
            1,
            len(result_df) + 1,
        ),
    )

    # ----------------------------------------------------------------------
    # DISPLAY
    # ----------------------------------------------------------------------

    section(
        "CURRENT ETF RESEARCH RESULTS"
    )

    print(
        "How to read this:"
    )

    print(
        f"  • Time to +5% = historical average time to reach +5%, "
        f"capped at {HORIZON_DAYS} trading days."
    )

    print(
        "  • Hit rate     = percentage of matching historical cases "
        "that reached +5% within the research horizon."
    )

    print(
        "  • Evidence     = number of historical observations behind "
        "the estimate."
    )

    print(
        "  • Method       = where the historical evidence came from."
    )

    print(
        "  • Lower historical time means the historical pattern "
        "reached +5% sooner; it is NOT a guarantee of future performance."
    )

    print()

    for _, row in result_df.iterrows():

        print_signal_row(
            row
        )

    # ----------------------------------------------------------------------
    # TOP CANDIDATE
    # ----------------------------------------------------------------------

    top = result_df.iloc[0]

    section(
        "CURRENT RESEARCH LEADER"
    )

    print(
        f"ETF                : "
        f"{top['ETF']}"
    )

    print(
        f"Category           : "
        f"{top['Category']}"
    )

    print(
        f"Signal date        : "
        f"{top['Signal_Date']}"
    )

    print(
        f"Current close      : "
        f"₹{safe_float(top['Current_Close']):,.2f}"
    )

    print()

    print(
        "Historical result:"
    )

    print(
        f"  Time to +5%       : "
        f"~{days(top['Predicted_Expected_Days_20'])}"
    )

    print(
        f"  Hit rate          : "
        f"{pct(top['Predicted_Hit_Rate'], 2)}"
    )

    print(
        f"  Median successful : "
        f"~{days(top['Predicted_Median_Days'])}"
    )

    print(
        f"  Evidence          : "
        f"{int(top['Evidence']):,} observations"
    )

    print(
        f"  Method            : "
        f"{top['Method']}"
    )

    print()

    print(
        "Why it appears first:"
    )

    print(
        "  It has the lowest historical expected time "
        "to reach +5% among the ETFs with valid estimates."
    )

    print()

    print(
        "IMPORTANT:"
    )

    print(
        "  This is a historical research result."
    )

    print(
        "  It is NOT a guaranteed forecast."
    )

    print(
        "  The ranking only reflects the saved research model "
        "and current feature match."
    )

    # ----------------------------------------------------------------------
    # TOP RULE
    # ----------------------------------------------------------------------

    top_rule = str(
        top.get(
            "Best_Matching_Rule",
            ""
        )
    ).strip()

    top_explanation = str(
        top.get(
            "Rule_Explanation",
            ""
        )
    ).strip()

    if top_rule:

        section(
            f"WHY {top['ETF']} MATCHED"
        )

        print(
            "Saved historical condition:"
        )

        print(
            f"  {top_rule}"
        )

        if top_explanation:

            print()

            print(
                "What the condition means:"
            )

            print(
                f"  {top_explanation}"
            )

        print()

        print(
            "The current ETF matches this saved research condition "
            "using today's latest completed market data."
        )

    # ----------------------------------------------------------------------
    # PRODUCTION DEFINITION
    # ----------------------------------------------------------------------

    section(
        "PRODUCTION TRADE DEFINITION"
    )

    print(
        "Signal:"
    )

    print(
        "  Latest completed Day D close"
    )

    print()

    print(
        "Entry:"
    )

    print(
        "  Day D+1 open"
    )

    print()

    print(
        "Target:"
    )

    print(
        "  Entry open × 1.05 = +5%"
    )

    print()

    print(
        "Stop:"
    )

    print(
        "  NONE"
    )

    print()

    print(
        "Research horizon:"
    )

    print(
        f"  {HORIZON_DAYS} trading days"
    )

    # ----------------------------------------------------------------------
    # SAVE
    # ----------------------------------------------------------------------

    section(
        "CURRENT SIGNAL OUTPUT"
    )

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    primary_columns = [
        "Rank",
        "ETF",
        "Category",
        "Signal_Date",
        "Current_Close",
        "Predicted_Expected_Days_20",
        "Predicted_Hit_Rate",
        "Predicted_Median_Days",
        "Method",
        "Evidence",
        "Matched_Rules",
        "Best_Matching_Rule",
        "Rule_Explanation",
        "Rationale",
    ]

    feature_columns = [
        x
        for x in FEATURES
        if x in result_df.columns
    ]

    final_columns = [
        x
        for x in (
            primary_columns
            +
            feature_columns
        )
        if x in result_df.columns
    ]

    result_df = result_df[
        final_columns
    ]

    result_df.to_csv(
        CURRENT_SIGNAL_CSV,
        index=False,
    )

    print(
        "Current production signal saved:"
    )

    print(
        f"  {CURRENT_SIGNAL_CSV}"
    )

    # ----------------------------------------------------------------------
    # FINAL STATUS
    # ----------------------------------------------------------------------

    total_elapsed = (
        time.perf_counter()
        - total_start
    )

    section(
        "FINAL STATUS"
    )

    print(
        "Research used:"
    )

    print(
        "  Saved production JSON"
    )

    print()

    print(
        "Research recalculated:"
    )

    print(
        "  NO — discovery, backtest and OOS validation were NOT rerun."
    )

    print()

    print(
        "Current market data:"
    )

    print(
        "  Fresh ETF download"
    )

    print()

    print(
        "Decision hierarchy:"
    )

    print(
        "  ETF-specific validated rule"
    )

    print(
        "      ↓"
    )

    print(
        "  Global validated rule"
    )

    print(
        "      ↓"
    )

    print(
        "  Same-ETF historical analog"
    )

    print(
        "      ↓"
    )

    print(
        "  ETF historical baseline"
    )

    print()

    print(
        "Ranking:"
    )

    print(
        "  Lowest historical expected time to +5% first"
    )

    print()

    print(
        "Final interpretation:"
    )

    print(
        "  The engine identifies which current ETF conditions "
        "most closely resemble historical situations that reached +5%."
    )

    print(
        "  It does not guarantee that the same outcome will occur again."
    )

    print()

    print(
        f"Total runtime : {total_elapsed:.2f} sec"
    )

    separator()


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print()

        separator()

        print(
            "PROGRAM INTERRUPTED"
        )

        separator()

        sys.exit(130)

    except Exception as exc:

        print()

        separator()

        print(
            "PROGRAM ERROR"
        )

        separator()

        print(
            str(exc)
        )

        print()

        import traceback

        traceback.print_exc()

        separator()

        sys.exit(1)