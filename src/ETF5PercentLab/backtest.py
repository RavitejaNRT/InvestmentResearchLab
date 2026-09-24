"""
ETF5PercentLab - final research/backtest.py

Purpose
-------
Last research iteration before moving to main.py.

Production definition:
    Signal  : Day D completed close
    Entry   : Day D+1 open
    Target  : Entry open * 1.05
    Stop    : NONE
    Horizon : 20 trading days
    Speed   : trading days to first +5% hit

Design:
    1. Download 10 years of daily ETF data in one yfinance call.
    2. Build technical/state features.
    3. Build complete historical observations without look-ahead.
    4. Discover candidate rules on TRAIN only.
    5. Validate selected rules on later OOS data.
    6. Discover ETF-specific rules using TRAIN only and validate on OOS.
    7. Build today's production estimates:
         ETF-specific OOS rule -> global OOS rule -> nearest historical analog fallback.
    8. Save rules to JSON so main.py can later run quickly without rediscovery.
    9. Optional sequential diagnostic is OFF by default because it is research-only.

Normal run:
    python backtest.py

Optional sequential diagnostic:
    python backtest.py --sequential

Notes
-----
- This is research, not a guarantee of future returns.
- "Expected days" is restricted-mean time over the 20-day horizon:
      hit  -> actual first-hit day
      miss -> 20
- Rules are selected using TRAIN data and only then evaluated on later OOS data.
- Because many candidate rules are searched, OOS results can still contain
  multiple-testing / data-mining bias. This is the final practical research
  iteration requested by the user; main.py should display evidence/method
  transparently rather than treating every estimate as equal certainty.
"""

from __future__ import annotations

import argparse
import json
import math
import time
import warnings
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# =============================================================================
# PATHS / CONSTANTS
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

EXCEL_PATH = RESULTS_DIR / "etf_5percent_condition_discovery_results.xlsx"
OBS_CSV_PATH = RESULTS_DIR / "etf_5percent_condition_discovery_observations.csv"
RULES_JSON_PATH = RESULTS_DIR / "etf_5percent_production_rules.json"

TARGET_PCT = 0.05
HORIZON = 20
HIT_HORIZONS = (5, 10, 15, 20)
DATA_PERIOD = "10y"
MARKET_CLOSE_TIME = (15, 35)  # IST

# Final practical research thresholds.
MIN_GLOBAL_TRAIN_OBS = 40
MIN_GLOBAL_TRAIN_HITS = 10
MIN_GLOBAL_TRAIN_HIT_RATE = 0.55
MIN_GLOBAL_TRAIN_ETF_COVERAGE = 3

MIN_GLOBAL_TEST_OBS = 20
MIN_GLOBAL_TEST_HITS = 5
MIN_GLOBAL_TEST_HIT_RATE = 0.50
MIN_GLOBAL_TEST_ETF_COVERAGE = 2

MIN_ETF_TRAIN_OBS = 25
MIN_ETF_TRAIN_HITS = 8
MIN_ETF_TRAIN_HIT_RATE = 0.55

MIN_ETF_TEST_OBS = 20
MIN_ETF_TEST_HITS = 4
MIN_ETF_TEST_HIT_RATE = 0.50

TOP_GLOBAL_TRAIN_FOR_OOS = 250
TOP_GLOBAL_OOS_RULES = 30

TOP_ETF_TRAIN_FOR_OOS = 100
TOP_ETF_OOS_RULES_PER_ETF = 5

ANALOG_K = 40
ANALOG_MIN_HISTORY = 20

# Sequential diagnostic is deliberately OFF by default.
# Use: python backtest.py --sequential
RUN_SEQUENTIAL_DEFAULT = False

# =============================================================================
# ETF UNIVERSE
# =============================================================================

ETF_META = {
    "AUTOBEES": {
        "category": "Indian Sector - Auto",
        "symbol": "AUTOBEES.NS",
    },
    "BANKBEES": {
        "category": "Indian Sector - Banks",
        "symbol": "BANKBEES.NS",
    },
    "CPSEETF": {
        "category": "Indian Sector - CPSE",
        "symbol": "CPSEETF.NS",
    },
    "FMCGIETF": {
        "category": "Indian Sector - FMCG",
        "symbol": "FMCGIETF.NS",
    },
    "GOLDBEES": {
        "category": "Commodity - Gold",
        "symbol": "GOLDBEES.NS",
    },
    "HNGSNGBEES": {
        "category": "International - Hang Seng",
        "symbol": "HNGSNGBEES.NS",
    },
    "ITBEES": {
        "category": "Indian Sector - IT",
        "symbol": "ITBEES.NS",
    },
    "MAFANG": {
        "category": "International - FANG+",
        "symbol": "MAFANG.NS",
    },
    "METALIETF": {
        "category": "Indian Sector - Metal",
        "symbol": "METALIETF.NS",
    },
    "MON100": {
        "category": "International - NASDAQ 100",
        "symbol": "MON100.NS",
    },
    "NIFTYBEES": {
        "category": "Indian Broad Market - Nifty 50",
        "symbol": "NIFTYBEES.NS",
    },
    "OILIETF": {
        "category": "Indian Sector - Oil & Gas",
        "symbol": "OILIETF.NS",
    },
    "PHARMABEES": {
        "category": "Indian Sector - Pharma",
        "symbol": "PHARMABEES.NS",
    },
    "PSUBNKBEES": {
        "category": "Indian Sector - PSU Banks",
        "symbol": "PSUBNKBEES.NS",
    },
    "PVTBANIETF": {
        "category": "Indian Sector - Private Banks",
        "symbol": "PVTBANIETF.NS",
    },
    "SILVERBEES": {
        "category": "Commodity - Silver",
        "symbol": "SILVERBEES.NS",
    },
}

TICKERS = [v["symbol"] for v in ETF_META.values()]
TICKER_TO_ETF = {v["symbol"]: k for k, v in ETF_META.items()}

# =============================================================================
# FEATURES
# =============================================================================

FEATURE_WEIGHTS = {
    "RET_5": 1.00,
    "RET_10": 1.00,
    "RET_20": 1.10,
    "RET_40": 1.00,
    "RET_60": 1.00,
    "RET_120": 0.80,
    "RET_252": 0.80,
    "RS_20": 1.00,
    "RS_40": 1.00,
    "RS_60": 1.00,
    "RS_120": 0.80,
    "DIST_SMA20": 1.00,
    "DIST_SMA50": 1.00,
    "DIST_SMA100": 0.80,
    "DIST_SMA200": 0.80,
    "DIST_HIGH_20": 0.90,
    "DIST_HIGH_50": 0.90,
    "DIST_HIGH_100": 0.80,
    "DIST_HIGH_252": 0.80,
    "BREAKOUT_20": 0.90,
    "BREAKOUT_50": 0.90,
    "RSI14": 0.70,
    "VOLUME_RATIO_20": 0.60,
}

ANALOG_FEATURES = list(FEATURE_WEIGHTS.keys())

# =============================================================================
# RULE CONDITION LIBRARY
# =============================================================================

CONDITIONS: list[dict] = []


def add_condition(
    feature: str,
    op: str,
    v1: float | None,
    v2: float | None,
    label: str,
    group: str | None = None,
) -> None:
    CONDITIONS.append(
        {
            "id": len(CONDITIONS),
            "feature": feature,
            "op": op,
            "v1": v1,
            "v2": v2,
            "label": label,
            "group": group or feature,
        }
    )


def add_range_states(
    feature: str,
    states: list[tuple[float | None, float | None, str]],
    group: str | None = None,
) -> None:
    for lo, hi, label in states:
        if lo is None:
            add_condition(feature, "lt", hi, None, f"{feature} < {hi:.0%}", group)
        elif hi is None:
            add_condition(feature, "ge", lo, None, f"{feature} >= {lo:.0%}", group)
        else:
            add_condition(
                feature,
                "range",
                lo,
                hi,
                f"{feature} {lo:.0%} to {hi:.0%}",
                group,
            )


# Compact but broad state/range library.
# Rules can contain at most one condition from each feature group.
add_range_states(
    "RET_5",
    [
        (None, -0.05, ""),
        (-0.05, 0.00, ""),
        (0.00, 0.05, ""),
        (0.05, None, ""),
    ],
)
add_range_states(
    "RET_10",
    [
        (None, 0.00, ""),
        (0.00, 0.05, ""),
        (0.05, None, ""),
    ],
)
add_range_states(
    "RET_20",
    [
        (None, 0.00, ""),
        (0.00, 0.10, ""),
        (0.10, None, ""),
    ],
)
add_range_states(
    "RET_40",
    [
        (None, 0.00, ""),
        (0.00, 0.10, ""),
        (0.10, None, ""),
    ],
)
add_range_states(
    "RET_60",
    [
        (None, 0.00, ""),
        (0.00, 0.10, ""),
        (0.10, None, ""),
    ],
)
add_range_states(
    "RET_120",
    [
        (None, 0.00, ""),
        (0.00, 0.20, ""),
        (0.20, None, ""),
    ],
)
add_range_states(
    "RET_252",
    [
        (None, 0.00, ""),
        (0.00, 0.20, ""),
        (0.20, None, ""),
    ],
)

add_range_states(
    "RS_20",
    [
        (None, 0.00, ""),
        (0.00, 0.05, ""),
        (0.05, None, ""),
    ],
)
add_range_states(
    "RS_40",
    [
        (None, 0.00, ""),
        (0.00, 0.05, ""),
        (0.05, None, ""),
    ],
)
add_range_states(
    "RS_60",
    [
        (None, 0.00, ""),
        (0.00, 0.05, ""),
        (0.05, None, ""),
    ],
)
add_range_states(
    "RS_120",
    [
        (None, 0.00, ""),
        (0.00, 0.05, ""),
        (0.05, None, ""),
    ],
)

add_range_states(
    "DIST_SMA20",
    [
        (None, -0.05, ""),
        (-0.05, 0.00, ""),
        (0.00, 0.05, ""),
        (0.05, None, ""),
    ],
)
add_range_states(
    "DIST_SMA50",
    [
        (None, -0.05, ""),
        (-0.05, 0.00, ""),
        (0.00, 0.05, ""),
        (0.05, None, ""),
    ],
)
add_range_states(
    "DIST_SMA100",
    [
        (None, -0.05, ""),
        (-0.05, 0.00, ""),
        (0.00, 0.05, ""),
        (0.05, None, ""),
    ],
)
add_range_states(
    "DIST_SMA200",
    [
        (None, -0.05, ""),
        (-0.05, 0.00, ""),
        (0.00, 0.05, ""),
        (0.05, None, ""),
    ],
)

add_range_states(
    "DIST_HIGH_20",
    [
        (None, -0.10, ""),
        (-0.10, -0.05, ""),
        (-0.05, 0.00, ""),
        (0.00, None, ""),
    ],
)
add_range_states(
    "DIST_HIGH_50",
    [
        (None, -0.10, ""),
        (-0.10, -0.05, ""),
        (-0.05, 0.00, ""),
        (0.00, None, ""),
    ],
)
add_range_states(
    "DIST_HIGH_100",
    [
        (None, -0.10, ""),
        (-0.10, -0.05, ""),
        (-0.05, 0.00, ""),
        (0.00, None, ""),
    ],
)
add_range_states(
    "DIST_HIGH_252",
    [
        (None, -0.10, ""),
        (-0.10, -0.05, ""),
        (-0.05, 0.00, ""),
        (0.00, None, ""),
    ],
)

add_range_states(
    "BREAKOUT_20",
    [
        (None, -0.05, ""),
        (-0.05, 0.00, ""),
        (0.00, None, ""),
    ],
)
add_range_states(
    "BREAKOUT_50",
    [
        (None, -0.05, ""),
        (-0.05, 0.00, ""),
        (0.00, None, ""),
    ],
)

add_range_states(
    "RSI14",
    [
        (None, 35.0, ""),
        (35.0, 50.0, ""),
        (50.0, 65.0, ""),
        (65.0, None, ""),
    ],
)

add_range_states(
    "VOLUME_RATIO_20",
    [
        (None, 0.75, ""),
        (0.75, 1.00, ""),
        (1.00, 1.25, ""),
        (1.25, None, ""),
    ],
)

# Triples are restricted to the most useful state groups to keep the search
# broad enough but still fast.
TRIPLE_GROUPS = {
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
    "DIST_HIGH_20",
    "DIST_HIGH_50",
    "BREAKOUT_20",
    "BREAKOUT_50",
    "RSI14",
    "VOLUME_RATIO_20",
}


def rule_text(condition_indices: tuple[int, ...] | list[int]) -> str:
    return " AND ".join(CONDITIONS[i]["label"] for i in condition_indices)


def generate_candidates() -> list[tuple[int, ...]]:
    """
    Generate singles, pairs and selected triples.
    Conditions from the same feature group are never combined.
    """
    candidates: list[tuple[int, ...]] = []

    # Singles.
    for i in range(len(CONDITIONS)):
        candidates.append((i,))

    # Pairs.
    for i in range(len(CONDITIONS)):
        gi = CONDITIONS[i]["group"]
        for j in range(i + 1, len(CONDITIONS)):
            if gi == CONDITIONS[j]["group"]:
                continue
            candidates.append((i, j))

    # Triples.
    n = len(CONDITIONS)
    for i in range(n):
        gi = CONDITIONS[i]["group"]
        if gi not in TRIPLE_GROUPS:
            continue
        for j in range(i + 1, n):
            gj = CONDITIONS[j]["group"]
            if gj not in TRIPLE_GROUPS or gj == gi:
                continue
            for k in range(j + 1, n):
                gk = CONDITIONS[k]["group"]
                if gk not in TRIPLE_GROUPS:
                    continue
                if gk == gi or gk == gj:
                    continue
                candidates.append((i, j, k))

    return candidates


# =============================================================================
# DATA HELPERS
# =============================================================================

def now_ist() -> datetime:
    return datetime.now(ZoneInfo("Asia/Kolkata"))


def get_cutoff() -> tuple[pd.Timestamp, str]:
    now = now_ist()
    current_time = (now.hour, now.minute)

    if current_time >= MARKET_CLOSE_TIME:
        return pd.Timestamp(now.date()), "Today's completed close"

    return (
        pd.Timestamp(now.date()) - pd.Timedelta(days=1),
        "Latest prior completed close",
    )


def normalize_index(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    idx = pd.to_datetime(out.index, errors="coerce")

    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert("Asia/Kolkata").tz_localize(None)

    out.index = idx
    out = out[~out.index.isna()]
    out = out[~out.index.duplicated(keep="last")]
    out = out.sort_index()
    return out


def extract_field(
    raw: pd.DataFrame,
    ticker: str,
    field: str,
) -> pd.Series | None:
    """
    Robustly handles yfinance MultiIndex orientation:
        (PriceField, Ticker)
    and
        (Ticker, PriceField)
    plus simple single-level columns.
    """
    field = field.lower()
    ticker = ticker.lower()

    if isinstance(raw.columns, pd.MultiIndex):
        for col in raw.columns:
            parts = [str(x).lower() for x in col]
            if field in parts and ticker in parts:
                s = raw[col]
                if isinstance(s, pd.DataFrame):
                    s = s.iloc[:, 0]
                return pd.to_numeric(s, errors="coerce")

        # Some yfinance versions return the field at level 0.
        try:
            level0 = [str(x).lower() for x in raw.columns.get_level_values(0)]
            if field in level0:
                sub = raw.xs(field, axis=1, level=0)
                if isinstance(sub, pd.DataFrame):
                    for c in sub.columns:
                        if str(c).lower() == ticker:
                            return pd.to_numeric(sub[c], errors="coerce")
        except Exception:
            pass

        # Or ticker at level 0.
        try:
            level0 = [str(x).lower() for x in raw.columns.get_level_values(0)]
            if ticker in level0:
                sub = raw.xs(ticker, axis=1, level=0)
                if isinstance(sub, pd.DataFrame):
                    for c in sub.columns:
                        if str(c).lower() == field:
                            return pd.to_numeric(sub[c], errors="coerce")
        except Exception:
            pass

        return None

    for col in raw.columns:
        if str(col).lower() == field:
            return pd.to_numeric(raw[col], errors="coerce")

    return None


def download_market_data(cutoff: pd.Timestamp) -> dict[str, pd.DataFrame]:
    print("=" * 100)
    print("DOWNLOADING MARKET DATA")
    print("=" * 100)
    print(f"ETF count : {len(TICKERS)}")
    print(f"History   : {DATA_PERIOD}")
    print()

    started = time.perf_counter()

    try:
        raw = yf.download(
            TICKERS,
            period=DATA_PERIOD,
            interval="1d",
            auto_adjust=False,
            progress=True,
            group_by="column",
            threads=True,
        )
    except Exception as exc:
        raise RuntimeError(f"yfinance download failed: {exc}") from exc

    data: dict[str, pd.DataFrame] = {}
    invalid: list[str] = []

    for ticker in TICKERS:
        frames = {}
        for field in ("Open", "High", "Low", "Close", "Volume"):
            s = extract_field(raw, ticker, field)
            if s is not None:
                frames[field] = s

        if "Open" not in frames or "High" not in frames or "Close" not in frames:
            invalid.append(ticker)
            continue

        df = pd.concat(frames, axis=1)
        df = normalize_index(df)
        df = df.loc[df.index <= cutoff]
        df = df.dropna(subset=["Open", "High", "Close"])

        if len(df) < 100:
            invalid.append(ticker)
            continue

        df.index.name = "Date"
        data[TICKER_TO_ETF[ticker]] = df

    elapsed = time.perf_counter() - started

    print()
    print(f"Download time : {elapsed:.2f} sec")
    print(f"Valid ETFs    : {len(data)}")
    print(f"Invalid ETFs  : {len(invalid)}")

    if invalid:
        print("Invalid tickers:", ", ".join(invalid))

    print()
    print("ETF data coverage:")
    for etf in ETF_META:
        if etf not in data:
            continue
        df = data[etf]
        print(
            f"  {etf:<14} {len(df):>5} days | "
            f"{df.index.min().date()} -> {df.index.max().date()}"
        )

    if "NIFTYBEES" not in data:
        raise RuntimeError("NIFTYBEES data is required as the RS benchmark.")

    print()
    return data


# =============================================================================
# FEATURE ENGINEERING
# =============================================================================

def rsi_wilder(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    # If there are gains and no losses, RSI is 100.
    rsi = rsi.mask((avg_loss == 0) & (avg_gain > 0), 100.0)
    return rsi


def build_features_for_etf(
    df: pd.DataFrame,
    benchmark_close: pd.Series,
) -> pd.DataFrame:
    out = df.copy()
    close = out["Close"]
    volume = out["Volume"] if "Volume" in out.columns else pd.Series(index=out.index, dtype=float)

    for n in (5, 10, 20, 40, 60, 120, 252):
        out[f"RET_{n}"] = close.pct_change(n)

    for n in (20, 50, 100, 200):
        sma = close.rolling(n).mean()
        out[f"DIST_SMA{n}"] = close / sma - 1.0

    for n in (20, 50, 100, 252):
        rh = close.rolling(n).max()
        out[f"DIST_HIGH_{n}"] = close / rh - 1.0

        prior_high = close.shift(1).rolling(n).max()
        out[f"BREAKOUT_{n if n in (20, 50) else 20}"] = (
            close / prior_high - 1.0
            if n in (20, 50)
            else out.get(f"BREAKOUT_{n}", pd.Series(index=out.index, dtype=float))
        )

    out["RSI14"] = rsi_wilder(close)

    if len(volume) > 0:
        prior_volume_avg = volume.shift(1).rolling(20).mean()
        out["VOLUME_RATIO_20"] = volume / prior_volume_avg

    benchmark_close = benchmark_close.reindex(out.index).ffill()

    for n in (20, 40, 60, 120):
        etf_ret = close.pct_change(n)
        nifty_ret = benchmark_close.pct_change(n)
        out[f"RS_{n}"] = ((1.0 + etf_ret) / (1.0 + nifty_ret)) - 1.0

    # Remove the accidental duplicate possibility from the generic breakout loop.
    # Explicitly recompute the intended breakout fields.
    for n in (20, 50):
        prior_high = close.shift(1).rolling(n).max()
        out[f"BREAKOUT_{n}"] = close / prior_high - 1.0

    return out


def build_all_features(
    market_data: dict[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    print("=" * 100)
    print("BUILDING FEATURES")
    print("=" * 100)

    started = time.perf_counter()

    benchmark = market_data["NIFTYBEES"]["Close"]

    feature_data = {}
    for etf, df in market_data.items():
        feature_data[etf] = build_features_for_etf(df, benchmark)

    elapsed = time.perf_counter() - started
    print(f"Feature time : {elapsed:.2f} sec")
    print()
    return feature_data


# =============================================================================
# OBSERVATION CONSTRUCTION
# =============================================================================

def build_observations_for_etf(
    etf: str,
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Correct label construction.

    Signal:
        D close

    Entry:
        D+1 open

    Target:
        D+1 open * 1.05

    Hit:
        Any High from D+1 through D+20 >= target

    Incomplete future windows are excluded.
    """
    entry_open = df["Open"].shift(-1)
    target = entry_open * (1.0 + TARGET_PCT)

    future_highs = pd.concat(
        [
            df["High"].shift(-i).rename(f"H{i}")
            for i in range(1, HORIZON + 1)
        ],
        axis=1,
    )

    hit_matrix = future_highs.ge(target, axis=0)
    hit_arr = hit_matrix.to_numpy(dtype=bool)

    has_hit = hit_arr.any(axis=1)
    first = np.argmax(hit_arr, axis=1) + 1

    complete = (
        future_highs.notna().all(axis=1)
        & entry_open.notna()
        & target.notna()
    )

    dates = df.index.to_numpy(dtype="datetime64[ns]")
    valid_pos = np.flatnonzero(complete)

    hit_valid = has_hit[valid_pos]
    hit_valid_pos = np.flatnonzero(hit_valid)

    target_dates = np.full(
        len(valid_pos),
        np.datetime64("NaT"),
        dtype="datetime64[ns]",
    )

    if len(hit_valid_pos):
        target_dates[hit_valid_pos] = dates[
            valid_pos[hit_valid_pos] + first[valid_pos[hit_valid_pos]]
        ]

    signal_dates = dates[valid_pos]
    entry_dates = dates[valid_pos + 1]

    out = df.iloc[valid_pos].copy()

    out["ETF"] = etf
    out["Signal_Date"] = pd.to_datetime(signal_dates)
    out["Entry_Date"] = pd.to_datetime(entry_dates)
    out["Entry_Open"] = entry_open.iloc[valid_pos].to_numpy(dtype=float)
    out["Target_Price"] = target.iloc[valid_pos].to_numpy(dtype=float)
    out["Hit_5pct"] = hit_valid.astype(bool)

    days = np.full(len(valid_pos), np.nan, dtype=float)
    days[hit_valid_pos] = first[valid_pos[hit_valid_pos]].astype(float)

    out["Days_To_5pct"] = days
    out["Censored_Days"] = np.where(
        hit_valid,
        days,
        float(HORIZON),
    )

    out["Target_Date"] = pd.to_datetime(target_dates)

    return out.reset_index(drop=True)


def build_observations(
    feature_data: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    print("=" * 100)
    print("BUILDING HISTORICAL OBSERVATIONS")
    print("=" * 100)

    started = time.perf_counter()

    frames = []
    for etf, df in feature_data.items():
        obs = build_observations_for_etf(etf, df)
        obs["Category"] = ETF_META[etf]["category"]
        frames.append(obs)

    observations = pd.concat(frames, ignore_index=True)
    observations["Signal_Date"] = pd.to_datetime(observations["Signal_Date"])
    observations["Entry_Date"] = pd.to_datetime(observations["Entry_Date"])
    observations["Target_Date"] = pd.to_datetime(observations["Target_Date"])

    observations = observations.sort_values(
        ["Signal_Date", "ETF"]
    ).reset_index(drop=True)

    elapsed = time.perf_counter() - started

    hit_rate = observations["Hit_5pct"].mean()
    median_days = observations.loc[
        observations["Hit_5pct"], "Days_To_5pct"
    ].median()
    expected_days = observations["Censored_Days"].mean()

    print(f"Observations : {len(observations):,}")
    print(f"Hit rate     : {hit_rate:.2%}")
    print(f"Median hit   : {median_days:.2f} trading days")
    print(f"Expected days: {expected_days:.2f}")
    print(f"Observation time : {elapsed:.2f} sec")
    print()

    return observations


# =============================================================================
# TRAIN / TEST SPLIT
# =============================================================================

def chronological_split(
    observations: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp]:
    dates = np.sort(observations["Signal_Date"].dropna().unique())

    if len(dates) < 10:
        raise RuntimeError("Not enough unique dates for chronological split.")

    # Approximately 70/30 chronological split.
    split_index = int(len(dates) * 0.70)
    split_index = min(max(split_index, 1), len(dates) - 1)
    split_date = pd.Timestamp(dates[split_index])

    train = observations[
        observations["Signal_Date"] < split_date
    ].copy()

    test = observations[
        observations["Signal_Date"] >= split_date
    ].copy()

    return train, test, split_date


def print_split_summary(
    train: pd.DataFrame,
    test: pd.DataFrame,
    split_date: pd.Timestamp,
) -> None:
    print("=" * 100)
    print("CHRONOLOGICAL TRAIN / OOS SPLIT")
    print("=" * 100)

    print(
        f"Train : {train['Signal_Date'].min().date()} -> "
        f"{train['Signal_Date'].max().date()} | "
        f"{len(train):,} observations"
    )
    print(
        f"OOS   : {test['Signal_Date'].min().date()} -> "
        f"{test['Signal_Date'].max().date()} | "
        f"{len(test):,} observations"
    )
    print(f"Split : {split_date.date()}")

    for label, frame in (("Train", train), ("OOS", test)):
        if len(frame):
            print(
                f"{label:<5} hit rate={frame['Hit_5pct'].mean():.2%} | "
                f"expected days={frame['Censored_Days'].mean():.2f}"
            )
    print()


# =============================================================================
# FAST NUMPY RULE ENGINE
# =============================================================================

def make_atomic_masks(
    frame: pd.DataFrame,
) -> dict[int, np.ndarray]:
    """
    Precompute every atomic condition once.
    Inner rule evaluation then uses only NumPy bitwise AND.
    """
    masks: dict[int, np.ndarray] = {}

    for condition in CONDITIONS:
        feature = condition["feature"]

        if feature not in frame.columns:
            masks[condition["id"]] = np.zeros(len(frame), dtype=bool)
            continue

        values = pd.to_numeric(
            frame[feature],
            errors="coerce",
        ).to_numpy(dtype=float)

        finite = np.isfinite(values)
        op = condition["op"]
        v1 = condition["v1"]
        v2 = condition["v2"]

        if op == "lt":
            mask = finite & (values < float(v1))
        elif op == "ge":
            mask = finite & (values >= float(v1))
        elif op == "range":
            mask = finite & (values >= float(v1)) & (values < float(v2))
        else:
            raise ValueError(f"Unknown condition op: {op}")

        masks[condition["id"]] = mask

    return masks


def combine_mask(
    atomic_masks: dict[int, np.ndarray],
    condition_indices: tuple[int, ...] | list[int],
) -> np.ndarray:
    if not condition_indices:
        raise ValueError("A rule must contain at least one condition.")

    mask = atomic_masks[condition_indices[0]].copy()

    for idx in condition_indices[1:]:
        mask &= atomic_masks[idx]

    return mask


def calculate_rule_metrics(
    mask: np.ndarray,
    hit: np.ndarray,
    days: np.ndarray,
    censored: np.ndarray,
    etf: np.ndarray | None = None,
) -> dict | None:
    n = int(mask.sum())
    if n == 0:
        return None

    matched_hits = hit[mask]
    hits = int(matched_hits.sum())

    if hits == 0:
        median_days = float("nan")
    else:
        median_days = float(np.nanmedian(days[mask & hit]))

    expected_days = float(np.nanmean(censored[mask]))
    hit_rate = hits / n

    result = {
        "observations": n,
        "hits": hits,
        "hit_rate": hit_rate,
        "median_days": median_days,
        "expected_days_20": expected_days,
    }

    if etf is not None:
        matched_etfs = etf[mask]
        result["etf_coverage"] = int(pd.unique(matched_etfs).size)

    return result


def discovery_score_key(rule: dict) -> tuple:
    return (
        rule["train_expected_days_20"],
        -rule["train_hit_rate"],
        -rule["train_observations"],
    )


def oos_score_key(rule: dict) -> tuple:
    return (
        rule["test_expected_days_20"],
        -rule["test_hit_rate"],
        -rule["test_observations"],
    )


def discover_train_rules(
    frame: pd.DataFrame,
    candidates: list[tuple[int, ...]],
    *,
    min_obs: int,
    min_hits: int,
    min_hit_rate: float,
    min_etf_coverage: int | None = None,
    top_n: int,
) -> tuple[list[dict], int]:
    """
    Discover rules using TRAIN ONLY.

    Returns:
        top_n rules sorted by TRAIN expected time,
        total number of valid train rules.
    """
    if frame.empty:
        return [], 0

    atomic = make_atomic_masks(frame)

    hit = frame["Hit_5pct"].to_numpy(dtype=bool)
    days = frame["Days_To_5pct"].to_numpy(dtype=float)
    censored = frame["Censored_Days"].to_numpy(dtype=float)

    etf = (
        frame["ETF"].astype(str).to_numpy()
        if "ETF" in frame.columns
        else None
    )

    valid: list[dict] = []

    for condition_indices in candidates:
        mask = combine_mask(atomic, condition_indices)

        metrics = calculate_rule_metrics(
            mask,
            hit,
            days,
            censored,
            etf,
        )

        if metrics is None:
            continue

        if metrics["observations"] < min_obs:
            continue

        if metrics["hits"] < min_hits:
            continue

        if metrics["hit_rate"] < min_hit_rate:
            continue

        if (
            min_etf_coverage is not None
            and metrics.get("etf_coverage", 0) < min_etf_coverage
        ):
            continue

        valid.append(
            {
                "condition_indices": list(condition_indices),
                "rule": rule_text(condition_indices),
                "train_observations": metrics["observations"],
                "train_hits": metrics["hits"],
                "train_hit_rate": metrics["hit_rate"],
                "train_median_days": metrics["median_days"],
                "train_expected_days_20": metrics["expected_days_20"],
                "train_etf_coverage": metrics.get("etf_coverage"),
            }
        )

    valid.sort(key=discovery_score_key)
    return valid[:top_n], len(valid)


def validate_rules_oos(
    rules: list[dict],
    frame: pd.DataFrame,
    *,
    min_obs: int,
    min_hits: int,
    min_hit_rate: float,
    min_etf_coverage: int | None = None,
    top_n: int,
) -> list[dict]:
    if frame.empty or not rules:
        return []

    atomic = make_atomic_masks(frame)

    hit = frame["Hit_5pct"].to_numpy(dtype=bool)
    days = frame["Days_To_5pct"].to_numpy(dtype=float)
    censored = frame["Censored_Days"].to_numpy(dtype=float)

    etf = (
        frame["ETF"].astype(str).to_numpy()
        if "ETF" in frame.columns
        else None
    )

    validated = []

    for source_rule in rules:
        condition_indices = tuple(source_rule["condition_indices"])
        mask = combine_mask(atomic, condition_indices)

        metrics = calculate_rule_metrics(
            mask,
            hit,
            days,
            censored,
            etf,
        )

        if metrics is None:
            continue

        if metrics["observations"] < min_obs:
            continue

        if metrics["hits"] < min_hits:
            continue

        if metrics["hit_rate"] < min_hit_rate:
            continue

        if (
            min_etf_coverage is not None
            and metrics.get("etf_coverage", 0) < min_etf_coverage
        ):
            continue

        rule = dict(source_rule)
        rule.update(
            {
                "test_observations": metrics["observations"],
                "test_hits": metrics["hits"],
                "test_hit_rate": metrics["hit_rate"],
                "test_median_days": metrics["median_days"],
                "test_expected_days_20": metrics["expected_days_20"],
                "test_etf_coverage": metrics.get("etf_coverage"),
            }
        )
        validated.append(rule)

    validated.sort(key=oos_score_key)
    return validated[:top_n]


# =============================================================================
# GLOBAL RULE DISCOVERY
# =============================================================================

def discover_global_rules(
    train: pd.DataFrame,
    test: pd.DataFrame,
    candidates: list[tuple[int, ...]],
) -> tuple[list[dict], list[dict], int]:
    print("=" * 100)
    print("GLOBAL RULE DISCOVERY + OOS VALIDATION")
    print("=" * 100)

    started = time.perf_counter()

    train_rules, valid_count = discover_train_rules(
        train,
        candidates,
        min_obs=MIN_GLOBAL_TRAIN_OBS,
        min_hits=MIN_GLOBAL_TRAIN_HITS,
        min_hit_rate=MIN_GLOBAL_TRAIN_HIT_RATE,
        min_etf_coverage=MIN_GLOBAL_TRAIN_ETF_COVERAGE,
        top_n=TOP_GLOBAL_TRAIN_FOR_OOS,
    )

    oos_rules = validate_rules_oos(
        train_rules,
        test,
        min_obs=MIN_GLOBAL_TEST_OBS,
        min_hits=MIN_GLOBAL_TEST_HITS,
        min_hit_rate=MIN_GLOBAL_TEST_HIT_RATE,
        min_etf_coverage=MIN_GLOBAL_TEST_ETF_COVERAGE,
        top_n=TOP_GLOBAL_OOS_RULES,
    )

    elapsed = time.perf_counter() - started

    print(f"Candidate rules           : {len(candidates):,}")
    print(f"Valid TRAIN rules         : {valid_count:,}")
    print(f"TRAIN rules sent to OOS   : {len(train_rules):,}")
    print(f"Validated OOS rules       : {len(oos_rules):,}")
    print(f"Discovery/OOS time        : {elapsed:.2f} sec")
    print()

    if oos_rules:
        print("TOP GLOBAL OOS RULES")
        print("-" * 100)
        for i, rule in enumerate(oos_rules[:20], 1):
            print(
                f"{i:>2}. {rule['rule']} | "
                f"Train N={rule['train_observations']} "
                f"HR={rule['train_hit_rate']:.1%} | "
                f"OOS N={rule['test_observations']} "
                f"HR={rule['test_hit_rate']:.1%} "
                f"Median={rule['test_median_days']:.1f}d "
                f"Expected={rule['test_expected_days_20']:.2f}d"
            )
        print()

    return train_rules, oos_rules, valid_count


# =============================================================================
# ETF-SPECIFIC RULE DISCOVERY
# =============================================================================

def discover_etf_specific_rules(
    train: pd.DataFrame,
    test: pd.DataFrame,
    candidates: list[tuple[int, ...]],
) -> tuple[dict[str, list[dict]], list[dict], int]:
    print("=" * 100)
    print("ETF-SPECIFIC RULE DISCOVERY + OOS VALIDATION")
    print("=" * 100)

    started = time.perf_counter()

    all_validated: dict[str, list[dict]] = {}
    flat_rows: list[dict] = []
    total_valid_train_rules = 0

    for etf in ETF_META:
        train_e = train[train["ETF"] == etf]
        test_e = test[test["ETF"] == etf]

        if len(train_e) < MIN_ETF_TRAIN_OBS:
            all_validated[etf] = []
            continue

        train_rules, valid_count = discover_train_rules(
            train_e,
            candidates,
            min_obs=MIN_ETF_TRAIN_OBS,
            min_hits=MIN_ETF_TRAIN_HITS,
            min_hit_rate=MIN_ETF_TRAIN_HIT_RATE,
            min_etf_coverage=None,
            top_n=TOP_ETF_TRAIN_FOR_OOS,
        )

        total_valid_train_rules += valid_count

        oos_rules = validate_rules_oos(
            train_rules,
            test_e,
            min_obs=MIN_ETF_TEST_OBS,
            min_hits=MIN_ETF_TEST_HITS,
            min_hit_rate=MIN_ETF_TEST_HIT_RATE,
            min_etf_coverage=None,
            top_n=TOP_ETF_OOS_RULES_PER_ETF,
        )

        for rule in oos_rules:
            rule = dict(rule)
            rule["ETF"] = etf
            all_validated.setdefault(etf, []).append(rule)
            flat_rows.append(rule)

        print(
            f"{etf:<14} Train={len(train_e):>5} | "
            f"OOS={len(test_e):>5} | "
            f"valid train rules={valid_count:>5} | "
            f"OOS rules kept={len(oos_rules):>2}"
        )

    elapsed = time.perf_counter() - started

    for etf in ETF_META:
        all_validated.setdefault(etf, [])

    print()
    print(f"Total valid ETF-specific TRAIN rules : {total_valid_train_rules:,}")
    print(f"Validated ETF-specific OOS rules     : {len(flat_rows):,}")
    print(f"ETF-specific discovery time          : {elapsed:.2f} sec")
    print()

    return all_validated, flat_rows, total_valid_train_rules


# =============================================================================
# PRODUCTION ESTIMATION
# =============================================================================

def condition_holds_value(value: float, condition: dict) -> bool:
    if not np.isfinite(value):
        return False

    op = condition["op"]
    v1 = condition["v1"]
    v2 = condition["v2"]

    if op == "lt":
        return value < float(v1)

    if op == "ge":
        return value >= float(v1)

    if op == "range":
        return float(v1) <= value < float(v2)

    return False


def rule_matches_row(
    row: pd.Series,
    rule: dict,
) -> bool:
    for condition_index in rule["condition_indices"]:
        condition = CONDITIONS[condition_index]
        feature = condition["feature"]

        if feature not in row.index:
            return False

        value = row[feature]

        try:
            value = float(value)
        except Exception:
            return False

        if not condition_holds_value(value, condition):
            return False

    return True


def aggregate_rule_predictions(
    matched_rules: list[dict],
) -> dict:
    """
    Combine multiple matching validated rules.

    Weight = sqrt(OOS observations), which gives larger samples more influence
    without allowing one very large rule to dominate completely.
    """
    if not matched_rules:
        raise ValueError("No rules to aggregate.")

    weights = np.array(
        [
            math.sqrt(max(1, int(r["test_observations"])))
            for r in matched_rules
        ],
        dtype=float,
    )

    expected = np.array(
        [float(r["test_expected_days_20"]) for r in matched_rules],
        dtype=float,
    )
    hit_rate = np.array(
        [float(r["test_hit_rate"]) for r in matched_rules],
        dtype=float,
    )

    weight_sum = weights.sum()

    predicted_expected = float(np.average(expected, weights=weights))
    predicted_hit = float(np.average(hit_rate, weights=weights))

    best_rule = min(
        matched_rules,
        key=lambda r: (
            float(r["test_expected_days_20"]),
            -float(r["test_hit_rate"]),
        ),
    )

    evidence = int(
        sum(int(r["test_observations"]) for r in matched_rules)
    )

    return {
        "predicted_hit_rate": predicted_hit,
        "predicted_expected_days_20": predicted_expected,
        "predicted_median_days": float(best_rule["test_median_days"]),
        "evidence": evidence,
        "matched_rules": len(matched_rules),
        "best_rule": best_rule,
    }


def analog_prediction(
    etf: str,
    observations: pd.DataFrame,
    current_row: pd.Series,
) -> dict:
    """
    Same-ETF nearest historical analog fallback.

    Only observations strictly before today's signal date are used.
    """
    current_date = pd.Timestamp(current_row["Signal_Date"])

    hist = observations[
        (observations["ETF"] == etf)
        & (observations["Signal_Date"] < current_date)
    ].copy()

    usable_features = [
        f for f in ANALOG_FEATURES
        if f in hist.columns and f in current_row.index
    ]

    if len(hist) < ANALOG_MIN_HISTORY or not usable_features:
        # Absolute fallback: same ETF historical baseline.
        if len(hist) == 0:
            return {
                "predicted_hit_rate": np.nan,
                "predicted_expected_days_20": float(HORIZON),
                "predicted_median_days": float(HORIZON),
                "evidence": 0,
                "analog_k": 0,
                "average_distance": np.nan,
                "method": "ETF_BASELINE_FALLBACK",
            }

        return {
            "predicted_hit_rate": float(hist["Hit_5pct"].mean()),
            "predicted_expected_days_20": float(hist["Censored_Days"].mean()),
            "predicted_median_days": (
                float(hist.loc[hist["Hit_5pct"], "Days_To_5pct"].median())
                if hist["Hit_5pct"].any()
                else float(HORIZON)
            ),
            "evidence": int(len(hist)),
            "analog_k": int(len(hist)),
            "average_distance": np.nan,
            "method": "ETF_BASELINE_FALLBACK",
        }

    valid = hist[usable_features].notna().all(axis=1)
    hist = hist.loc[valid].copy()

    if len(hist) < ANALOG_MIN_HISTORY:
        return {
            "predicted_hit_rate": float(hist["Hit_5pct"].mean()),
            "predicted_expected_days_20": float(hist["Censored_Days"].mean()),
            "predicted_median_days": (
                float(hist.loc[hist["Hit_5pct"], "Days_To_5pct"].median())
                if hist["Hit_5pct"].any()
                else float(HORIZON)
            ),
            "evidence": int(len(hist)),
            "analog_k": int(len(hist)),
            "average_distance": np.nan,
            "method": "ETF_BASELINE_FALLBACK",
        }

    x = hist[usable_features].to_numpy(dtype=float)
    current = np.array(
        [float(current_row[f]) for f in usable_features],
        dtype=float,
    )

    # Robust scaling using median absolute deviation.
    med = np.nanmedian(x, axis=0)
    mad = np.nanmedian(np.abs(x - med), axis=0) * 1.4826

    std = np.nanstd(x, axis=0)
    scale = np.where(
        np.isfinite(mad) & (mad > 1e-9),
        mad,
        std,
    )
    scale = np.where(
        np.isfinite(scale) & (scale > 1e-9),
        scale,
        1.0,
    )

    weights = np.array(
        [FEATURE_WEIGHTS.get(f, 1.0) for f in usable_features],
        dtype=float,
    )

    z = (x - current) / scale
    distance = np.sqrt(
        np.sum(weights * z * z, axis=1)
        / max(weights.sum(), 1e-9)
    )

    k = min(ANALOG_K, len(hist))

    if k == len(hist):
        idx = np.arange(len(hist))
    else:
        idx = np.argpartition(distance, k - 1)[:k]

    analogs = hist.iloc[idx].copy()
    analog_dist = distance[idx]

    hit_rate = float(analogs["Hit_5pct"].mean())
    expected_days = float(analogs["Censored_Days"].mean())

    if analogs["Hit_5pct"].any():
        median_days = float(
            analogs.loc[
                analogs["Hit_5pct"],
                "Days_To_5pct",
            ].median()
        )
    else:
        median_days = float(HORIZON)

    return {
        "predicted_hit_rate": hit_rate,
        "predicted_expected_days_20": expected_days,
        "predicted_median_days": median_days,
        "evidence": int(len(analogs)),
        "analog_k": int(len(analogs)),
        "average_distance": float(np.mean(analog_dist)),
        "method": "NEAREST_HISTORICAL_ANALOG",
    }


def current_production_ranking(
    feature_data: dict[str, pd.DataFrame],
    observations: pd.DataFrame,
    global_oos_rules: list[dict],
    etf_specific_rules: dict[str, list[dict]],
    cutoff: pd.Timestamp,
) -> pd.DataFrame:
    rows = []

    for etf in ETF_META:
        if etf not in feature_data:
            continue

        df = feature_data[etf]
        if df.empty:
            continue

        current_date = df.index.max()
        current = df.loc[current_date].copy()

        current["Signal_Date"] = current_date

        specific_matches = [
            rule
            for rule in etf_specific_rules.get(etf, [])
            if rule_matches_row(current, rule)
        ]

        if specific_matches:
            prediction = aggregate_rule_predictions(specific_matches)
            method = "ETF-SPECIFIC OOS RULE"
            best_rule = prediction["best_rule"]

            rationale = (
                f"{len(specific_matches)} ETF-specific OOS-validated rule(s) "
                f"match today's state. "
                f"Combined OOS evidence={prediction['evidence']} observations. "
                f"Best matched rule: {best_rule['rule']} "
                f"(OOS hit={best_rule['test_hit_rate']:.1%}, "
                f"expected={best_rule['test_expected_days_20']:.2f} days)."
            )

        else:
            global_matches = [
                rule
                for rule in global_oos_rules
                if rule_matches_row(current, rule)
            ]

            if global_matches:
                prediction = aggregate_rule_predictions(global_matches)
                method = "GLOBAL OOS RULE"
                best_rule = prediction["best_rule"]

                rationale = (
                    f"No ETF-specific OOS rule matched. "
                    f"{len(global_matches)} global OOS-validated rule(s) "
                    f"match today's state. "
                    f"Combined OOS evidence={prediction['evidence']} observations. "
                    f"Best matched rule: {best_rule['rule']} "
                    f"(OOS hit={best_rule['test_hit_rate']:.1%}, "
                    f"expected={best_rule['test_expected_days_20']:.2f} days)."
                )

            else:
                prediction = analog_prediction(
                    etf,
                    observations,
                    pd.Series(
                        {
                            **current.to_dict(),
                            "Signal_Date": current_date,
                        }
                    ),
                )
                method = prediction["method"]
                best_rule = None

                rationale = (
                    f"No validated ETF-specific or global rule matched. "
                    f"Estimate uses {prediction['evidence']} nearest historical "
                    f"same-ETF analog(s) before {current_date.date()}. "
                    f"This is a fallback estimate, not OOS rule evidence."
                )

        row = {
            "ETF": etf,
            "Category": ETF_META[etf]["category"],
            "Signal_Date": current_date,
            "Current_Close": float(current["Close"]),
            "Method": method,
            "Matched_Rules": int(prediction.get("matched_rules", 0)),
            "Evidence": int(prediction.get("evidence", 0)),
            "Predicted_Hit_Rate": float(
                prediction["predicted_hit_rate"]
            ),
            "Predicted_Median_Days": float(
                prediction["predicted_median_days"]
            ),
            "Predicted_Expected_Days_20": float(
                prediction["predicted_expected_days_20"]
            ),
            "Best_Matching_Rule": (
                best_rule["rule"]
                if best_rule is not None
                else ""
            ),
            "Rationale": rationale,
        }

        for feature in ANALOG_FEATURES:
            if feature in current.index:
                row[feature] = current[feature]

        rows.append(row)

    ranking = pd.DataFrame(rows)

    if ranking.empty:
        return ranking

    ranking = ranking.sort_values(
        [
            "Predicted_Expected_Days_20",
            "Predicted_Hit_Rate",
            "Evidence",
        ],
        ascending=[True, False, False],
    ).reset_index(drop=True)

    ranking.insert(0, "Rank", np.arange(1, len(ranking) + 1))

    return ranking


# =============================================================================
# SUMMARY TABLES
# =============================================================================

def make_etf_summary(observations: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for etf in ETF_META:
        frame = observations[observations["ETF"] == etf]

        if frame.empty:
            continue

        hit = frame["Hit_5pct"].astype(bool)

        rows.append(
            {
                "ETF": etf,
                "Category": ETF_META[etf]["category"],
                "Observations": len(frame),
                "Hit_Rate_20D": frame["Hit_5pct"].mean(),
                "Median_Hit_Days": (
                    frame.loc[hit, "Days_To_5pct"].median()
                    if hit.any()
                    else np.nan
                ),
                "Expected_Days_20D": frame["Censored_Days"].mean(),
                "Hit_5D": (
                    (hit & (frame["Days_To_5pct"] <= 5)).mean()
                ),
                "Hit_10D": (
                    (hit & (frame["Days_To_5pct"] <= 10)).mean()
                ),
                "Hit_15D": (
                    (hit & (frame["Days_To_5pct"] <= 15)).mean()
                ),
                "Hit_20D": (
                    (hit & (frame["Days_To_5pct"] <= 20)).mean()
                ),
            }
        )

    return pd.DataFrame(rows)


def make_horizon_summary(observations: pd.DataFrame) -> pd.DataFrame:
    rows = []

    total = len(observations)

    for h in HIT_HORIZONS:
        hits = int(
            (
                observations["Hit_5pct"]
                & (observations["Days_To_5pct"] <= h)
            ).sum()
        )

        rows.append(
            {
                "Horizon_Trading_Days": h,
                "Observations": total,
                "Hits_By_Horizon": hits,
                "Hit_Rate": hits / total if total else np.nan,
            }
        )

    return pd.DataFrame(rows)


def make_rule_dataframe(rules: list[dict]) -> pd.DataFrame:
    if not rules:
        return pd.DataFrame()

    rows = []

    for rule in rules:
        row = dict(rule)
        row["Conditions"] = " | ".join(
            CONDITIONS[i]["label"]
            for i in rule["condition_indices"]
        )
        row.pop("condition_indices", None)
        rows.append(row)

    return pd.DataFrame(rows)


def make_condition_dataframe() -> pd.DataFrame:
    return pd.DataFrame(CONDITIONS)


# =============================================================================
# OPTIONAL SEQUENTIAL DIAGNOSTIC
# =============================================================================

def sequential_prior_stats(
    history: pd.DataFrame,
    dates: np.ndarray,
    rule: dict,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    For each requested date, return statistics from matching observations
    strictly BEFORE that date.

    This avoids same-day look-ahead by using searchsorted(..., side='left').
    """
    if history.empty:
        n = len(dates)
        return (
            np.zeros(n, dtype=int),
            np.zeros(n, dtype=int),
            np.zeros(n, dtype=float),
        )

    atomic = make_atomic_masks(history)
    mask = combine_mask(
        atomic,
        tuple(rule["condition_indices"]),
    )

    matched = history.loc[mask]

    if matched.empty:
        n = len(dates)
        return (
            np.zeros(n, dtype=int),
            np.zeros(n, dtype=int),
            np.zeros(n, dtype=float),
        )

    matched_dates = matched["Signal_Date"].to_numpy(
        dtype="datetime64[ns]"
    )
    matched_hit = matched["Hit_5pct"].to_numpy(dtype=bool)
    matched_cens = matched["Censored_Days"].to_numpy(dtype=float)

    order = np.argsort(matched_dates)
    matched_dates = matched_dates[order]
    matched_hit = matched_hit[order]
    matched_cens = matched_cens[order]

    # Aggregate by date so all observations on the same date are excluded.
    unique_dates, inverse = np.unique(
        matched_dates,
        return_inverse=True,
    )

    daily_n = np.bincount(
        inverse,
        minlength=len(unique_dates),
    ).astype(int)

    daily_hits = np.bincount(
        inverse,
        weights=matched_hit.astype(float),
        minlength=len(unique_dates),
    ).astype(int)

    daily_cens = np.bincount(
        inverse,
        weights=matched_cens,
        minlength=len(unique_dates),
    ).astype(float)

    cum_n = np.cumsum(daily_n)
    cum_hits = np.cumsum(daily_hits)
    cum_cens = np.cumsum(daily_cens)

    positions = np.searchsorted(
        unique_dates,
        dates,
        side="left",
    )

    prior_n = np.where(
        positions > 0,
        cum_n[positions - 1],
        0,
    ).astype(int)

    prior_hits = np.where(
        positions > 0,
        cum_hits[positions - 1],
        0,
    ).astype(int)

    prior_cens = np.where(
        positions > 0,
        cum_cens[positions - 1],
        0.0,
    )

    return prior_n, prior_hits, prior_cens


def run_sequential_diagnostic(
    observations: pd.DataFrame,
    train: pd.DataFrame,
    test: pd.DataFrame,
    global_rules: list[dict],
    etf_rules: dict[str, list[dict]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Fast fixed-rule chronological diagnostic.

    Important:
        This is NOT another rule-discovery process.
        It uses the final validated rule library and only prior outcomes
        when estimating each OOS observation.

    If no rule matches with enough prior evidence, it uses the ETF's
    expanding historical baseline.

    This diagnostic is optional because it is not needed by main.py.
    """
    print("=" * 100)
    print("OPTIONAL SEQUENTIAL OOS DIAGNOSTIC")
    print("=" * 100)

    started = time.perf_counter()

    test = test.sort_values(["Signal_Date", "ETF"]).reset_index(drop=True)
    observations = observations.sort_values(
        ["Signal_Date", "ETF"]
    ).reset_index(drop=True)

    # Global prior stats are pooled across ETFs.
    all_dates = test["Signal_Date"].to_numpy(dtype="datetime64[ns]")

    global_prior = {}
    for rule in global_rules:
        pn, ph, pc = sequential_prior_stats(
            observations,
            all_dates,
            rule,
        )
        global_prior[id(rule)] = (pn, ph, pc)

    # ETF-specific prior stats.
    specific_prior: dict[str, dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]]] = {}

    for etf in ETF_META:
        etf_test = test[test["ETF"] == etf]
        dates = etf_test["Signal_Date"].to_numpy(dtype="datetime64[ns]")

        specific_prior[etf] = {}

        history_e = observations[observations["ETF"] == etf]

        for rule in etf_rules.get(etf, []):
            specific_prior[etf][id(rule)] = sequential_prior_stats(
                history_e,
                dates,
                rule,
            )

    # Expanding ETF baseline.
    baseline_prior: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}

    for etf in ETF_META:
        etf_test = test[test["ETF"] == etf]
        dates = etf_test["Signal_Date"].to_numpy(dtype="datetime64[ns]")

        hist = observations[observations["ETF"] == etf].copy()

        if hist.empty:
            baseline_prior[etf] = (
                np.zeros(len(dates), dtype=int),
                np.zeros(len(dates), dtype=int),
                np.zeros(len(dates), dtype=float),
            )
            continue

        hist_dates = hist["Signal_Date"].to_numpy(dtype="datetime64[ns]")
        order = np.argsort(hist_dates)
        hist_dates = hist_dates[order]
        hist_hit = hist["Hit_5pct"].to_numpy(dtype=bool)[order]
        hist_cens = hist["Censored_Days"].to_numpy(dtype=float)[order]

        unique_dates, inverse = np.unique(
            hist_dates,
            return_inverse=True,
        )

        daily_n = np.bincount(
            inverse,
            minlength=len(unique_dates),
        ).astype(int)
        daily_hits = np.bincount(
            inverse,
            weights=hist_hit.astype(float),
            minlength=len(unique_dates),
        ).astype(int)
        daily_cens = np.bincount(
            inverse,
            weights=hist_cens,
            minlength=len(unique_dates),
        ).astype(float)

        cum_n = np.cumsum(daily_n)
        cum_hits = np.cumsum(daily_hits)
        cum_cens = np.cumsum(daily_cens)

        pos = np.searchsorted(
            unique_dates,
            dates,
            side="left",
        )

        baseline_prior[etf] = (
            np.where(pos > 0, cum_n[pos - 1], 0).astype(int),
            np.where(pos > 0, cum_hits[pos - 1], 0).astype(int),
            np.where(pos > 0, cum_cens[pos - 1], 0.0),
        )

    predictions = []

    for etf in ETF_META:
        etf_test = test[test["ETF"] == etf].copy().reset_index(drop=True)

        if etf_test.empty:
            continue

        specific = etf_rules.get(etf, [])

        for i, row in etf_test.iterrows():
            prediction = None
            method = "ETF_EXPANDING_BASELINE"
            evidence = 0

            # Specific rules first.
            matched = []
            for rule in specific:
                if not rule_matches_row(row, rule):
                    continue

                pn, ph, pc = specific_prior[etf][id(rule)]
                n = int(pn[i])

                if n >= MIN_ETF_TEST_OBS:
                    matched.append(
                        (
                            rule,
                            n,
                            int(ph[i]),
                            float(pc[i]),
                        )
                    )

            if matched:
                weights = np.array(
                    [math.sqrt(max(1, x[1])) for x in matched],
                    dtype=float,
                )
                hit_rates = np.array(
                    [
                        x[2] / x[1]
                        for x in matched
                    ],
                    dtype=float,
                )
                expected = np.array(
                    [
                        x[3] / x[1]
                        for x in matched
                    ],
                    dtype=float,
                )

                prediction = {
                    "hit_rate": float(
                        np.average(hit_rates, weights=weights)
                    ),
                    "expected_days": float(
                        np.average(expected, weights=weights)
                    ),
                }
                method = "SEQUENTIAL_ETF_RULE"
                evidence = int(sum(x[1] for x in matched))

            # Global rules if no ETF-specific rule qualifies.
            if prediction is None:
                matched = []

                for rule in global_rules:
                    if not rule_matches_row(row, rule):
                        continue

                    pn, ph, pc = global_prior[id(rule)]
                    n = int(pn[i])

                    if n >= MIN_GLOBAL_TEST_OBS:
                        matched.append(
                            (
                                rule,
                                n,
                                int(ph[i]),
                                float(pc[i]),
                            )
                        )

                if matched:
                    weights = np.array(
                        [math.sqrt(max(1, x[1])) for x in matched],
                        dtype=float,
                    )
                    hit_rates = np.array(
                        [x[2] / x[1] for x in matched],
                        dtype=float,
                    )
                    expected = np.array(
                        [x[3] / x[1] for x in matched],
                        dtype=float,
                    )

                    prediction = {
                        "hit_rate": float(
                            np.average(hit_rates, weights=weights)
                        ),
                        "expected_days": float(
                            np.average(expected, weights=weights)
                        ),
                    }
                    method = "SEQUENTIAL_GLOBAL_RULE"
                    evidence = int(sum(x[1] for x in matched))

            # Expanding same-ETF baseline if no validated rule qualifies.
            if prediction is None:
                pn, ph, pc = baseline_prior[etf]
                n = int(pn[i])

                if n > 0:
                    prediction = {
                        "hit_rate": float(ph[i] / n),
                        "expected_days": float(pc[i] / n),
                    }
                    evidence = n
                else:
                    prediction = {
                        "hit_rate": 0.0,
                        "expected_days": float(HORIZON),
                    }
                    evidence = 0

            actual_hit = bool(row["Hit_5pct"])
            actual_days = (
                float(row["Days_To_5pct"])
                if actual_hit
                else float(HORIZON)
            )

            predictions.append(
                {
                    "Signal_Date": row["Signal_Date"],
                    "ETF": etf,
                    "Method": method,
                    "Evidence": evidence,
                    "Predicted_Hit_Rate": prediction["hit_rate"],
                    "Predicted_Expected_Days": prediction["expected_days"],
                    "Actual_Hit": actual_hit,
                    "Actual_Days_Censored": actual_days,
                }
            )

    seq = pd.DataFrame(predictions)

    if seq.empty:
        return pd.DataFrame(), pd.DataFrame()

    summary = pd.DataFrame(
        [
            {
                "Test_Observations": len(seq),
                "Hits": int(seq["Actual_Hit"].sum()),
                "Hit_Rate": seq["Actual_Hit"].mean(),
                "Average_Censored_Days": seq["Actual_Days_Censored"].mean(),
                "Average_Hit_Days": (
                    seq.loc[
                        seq["Actual_Hit"],
                        "Actual_Days_Censored",
                    ].mean()
                    if seq["Actual_Hit"].any()
                    else np.nan
                ),
                "Rule_Used_Rate": (
                    seq["Method"]
                    .isin(
                        [
                            "SEQUENTIAL_ETF_RULE",
                            "SEQUENTIAL_GLOBAL_RULE",
                        ]
                    )
                    .mean()
                ),
            }
        ]
    )

    horizon_rows = []
    for h in HIT_HORIZONS:
        hits = int(
            (
                seq["Actual_Hit"]
                & (seq["Actual_Days_Censored"] <= h)
            ).sum()
        )
        horizon_rows.append(
            {
                "Horizon_Trading_Days": h,
                "Observations": len(seq),
                "Hits_By_Horizon": hits,
                "Hit_Rate": hits / len(seq),
            }
        )

    horizon_df = pd.DataFrame(horizon_rows)

    elapsed = time.perf_counter() - started

    print(
        f"Sequential OOS observations : {len(seq):,}"
    )
    print(
        f"Sequential hit rate         : "
        f"{seq['Actual_Hit'].mean():.2%}"
    )
    print(
        f"Average censored days       : "
        f"{seq['Actual_Days_Censored'].mean():.2f}"
    )
    print(
        f"Average hit days            : "
        f"{seq.loc[seq['Actual_Hit'], 'Actual_Days_Censored'].mean():.2f}"
        if seq["Actual_Hit"].any()
        else "Average hit days            : n/a"
    )
    print(f"Sequential diagnostic time  : {elapsed:.2f} sec")
    print()

    return summary, horizon_df


# =============================================================================
# JSON / EXCEL OUTPUT
# =============================================================================

def clean_for_json(value):
    if isinstance(value, dict):
        return {str(k): clean_for_json(v) for k, v in value.items()}

    if isinstance(value, list):
        return [clean_for_json(v) for v in value]

    if isinstance(value, tuple):
        return [clean_for_json(v) for v in value]

    if isinstance(value, (np.integer,)):
        return int(value)

    if isinstance(value, (np.floating,)):
        if not np.isfinite(value):
            return None
        return float(value)

    if isinstance(value, (np.bool_,)):
        return bool(value)

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    if isinstance(value, float):
        if not math.isfinite(value):
            return None

    return value


def serialize_rule_for_json(rule: dict) -> dict:
    out = {}

    for key, value in rule.items():
        if key == "condition_indices":
            out[key] = list(value)
        else:
            out[key] = value

    out["conditions"] = [
        CONDITIONS[i]
        for i in rule["condition_indices"]
    ]

    return clean_for_json(out)


def save_json(
    global_oos_rules: list[dict],
    etf_specific_rules: dict[str, list[dict]],
    current_ranking: pd.DataFrame,
    split_date: pd.Timestamp,
    cutoff: pd.Timestamp,
    generated_at: str,
) -> None:
    payload = {
        "metadata": {
            "version": "ETF5PercentLab-final-research-v1",
            "generated_at": generated_at,
            "research_cutoff": cutoff.isoformat(),
            "signal_definition": "Day D completed close",
            "entry_definition": "Day D+1 open",
            "target_definition": "Day D+1 open * 1.05",
            "target_pct": TARGET_PCT,
            "stop_definition": "NONE",
            "horizon_days": HORIZON,
            "speed_definition": "Trading days from D+1 through first High >= target",
            "train_test_split_date": split_date.isoformat(),
            "rule_selection": (
                "Candidates discovered on TRAIN only; selected TRAIN rules "
                "then validated on later OOS data."
            ),
            "production_hierarchy": [
                "ETF-specific OOS-validated rule",
                "Global OOS-validated rule",
                "Nearest same-ETF historical analog fallback",
                "ETF historical baseline fallback if analog history is insufficient",
            ],
            "multiple_testing_warning": (
                "Many candidate rules are searched. OOS validation reduces "
                "but does not eliminate data-mining/selection bias."
            ),
        },
        "universe": {
            etf: {
                "category": meta["category"],
                "symbol": meta["symbol"],
            }
            for etf, meta in ETF_META.items()
        },
        "feature_weights": FEATURE_WEIGHTS,
        "condition_definitions": CONDITIONS,
        "global_oos_rules": [
            serialize_rule_for_json(r)
            for r in global_oos_rules
        ],
        "etf_specific_oos_rules": {
            etf: [
                serialize_rule_for_json(r)
                for r in rules
            ]
            for etf, rules in etf_specific_rules.items()
        },
        "fallback": {
            "analog_k": ANALOG_K,
            "analog_min_history": ANALOG_MIN_HISTORY,
            "features": ANALOG_FEATURES,
        },
        "current_signal_snapshot": (
            current_ranking.to_dict(orient="records")
            if not current_ranking.empty
            else []
        ),
    }

    with open(RULES_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(
            clean_for_json(payload),
            f,
            indent=2,
            ensure_ascii=False,
        )


def format_excel_sheet(writer, sheet_name: str) -> None:
    ws = writer.book[sheet_name]

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    for cell in ws[1]:
        cell.font = cell.font.copy(bold=True)

    for column_cells in ws.columns:
        column_letter = column_cells[0].column_letter
        max_len = 0

        for cell in column_cells[:200]:
            value = "" if cell.value is None else str(cell.value)
            max_len = max(max_len, len(value))

        ws.column_dimensions[column_letter].width = min(
            max(max_len + 2, 10),
            42,
        )


def save_excel(
    observations: pd.DataFrame,
    etf_summary: pd.DataFrame,
    global_train_rules: list[dict],
    global_oos_rules: list[dict],
    etf_specific_flat: list[dict],
    current_ranking: pd.DataFrame,
    horizon_summary: pd.DataFrame,
    sequential_summary: pd.DataFrame | None = None,
    sequential_horizon: pd.DataFrame | None = None,
    sequential_detail: pd.DataFrame | None = None,
) -> None:
    print("=" * 100)
    print("WRITING EXCEL")
    print("=" * 100)

    started = time.perf_counter()

    train_df = make_rule_dataframe(global_train_rules)
    oos_df = make_rule_dataframe(global_oos_rules)
    etf_specific_df = make_rule_dataframe(etf_specific_flat)

    condition_df = make_condition_dataframe()

    with pd.ExcelWriter(
        EXCEL_PATH,
        engine="openpyxl",
        datetime_format="yyyy-mm-dd",
    ) as writer:
        etf_summary.to_excel(
            writer,
            sheet_name="ETF Summary",
            index=False,
        )

        train_df.to_excel(
            writer,
            sheet_name="Discovered Rules",
            index=False,
        )

        oos_df.to_excel(
            writer,
            sheet_name="OOS Validation",
            index=False,
        )

        etf_specific_df.to_excel(
            writer,
            sheet_name="ETF Specific OOS Validation",
            index=False,
        )

        horizon_summary.to_excel(
            writer,
            sheet_name="Target Horizons",
            index=False,
        )

        current_ranking.to_excel(
            writer,
            sheet_name="Current Signal",
            index=False,
        )

        condition_df.to_excel(
            writer,
            sheet_name="Rule Conditions",
            index=False,
        )

        observations.to_excel(
            writer,
            sheet_name="Observations",
            index=False,
        )

        if sequential_summary is not None:
            sequential_summary.to_excel(
                writer,
                sheet_name="Sequential Test",
                index=False,
            )

        if sequential_horizon is not None:
            sequential_horizon.to_excel(
                writer,
                sheet_name="Sequential Horizons",
                index=False,
            )

        if sequential_detail is not None:
            sequential_detail.to_excel(
                writer,
                sheet_name="Sequential Detail",
                index=False,
            )

        for sheet in writer.book.sheetnames:
            format_excel_sheet(writer, sheet)

    elapsed = time.perf_counter() - started
    print(f"Excel time : {elapsed:.2f} sec")
    print(f"Saved      : {EXCEL_PATH}")
    print()


# =============================================================================
# PRINTING
# =============================================================================

def print_current_ranking(ranking: pd.DataFrame) -> None:
    print("=" * 100)
    print("FINAL CURRENT ETF ORDER — FASTEST EXPECTED +5% FIRST")
    print("=" * 100)

    if ranking.empty:
        print("No current ranking available.")
        print()
        return

    for _, row in ranking.iterrows():
        expected = row["Predicted_Expected_Days_20"]
        hit = row["Predicted_Hit_Rate"]
        evidence = row["Evidence"]

        print(
            f"{int(row['Rank']):>2}. "
            f"{row['ETF']:<14} | "
            f"Expected={expected:>5.2f}d | "
            f"Hit={hit:>6.2%} | "
            f"Method={row['Method']:<26} | "
            f"Evidence={evidence:>4}"
        )
        print(f"    Rationale: {row['Rationale']}")

    print()
    first = ranking.iloc[0]

    print("=" * 100)
    print("TENTATIVE CURRENT RESEARCH SELECTION")
    print("=" * 100)
    print(
        f"{first['ETF']} | "
        f"Expected +5% time={first['Predicted_Expected_Days_20']:.2f} "
        f"trading days | "
        f"Historical hit estimate={first['Predicted_Hit_Rate']:.2%} | "
        f"Method={first['Method']}"
    )
    print(
        "Important: this is the fastest historical estimate under the "
        "research model, not a forecast or guarantee."
    )
    print()


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ETF5PercentLab final +5% condition discovery backtest"
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Run optional chronological fixed-rule sequential diagnostic.",
    )
    parser.add_argument(
        "--no-excel",
        action="store_true",
        help="Skip Excel output.",
    )
    args = parser.parse_args()

    total_started = time.perf_counter()

    now = now_ist()
    cutoff, signal_mode = get_cutoff()

    print("=" * 100)
    print("ETF 5% SPEED DISCOVERY BACKTEST — FINAL RESEARCH ITERATION")
    print("=" * 100)
    print("Signal : Latest COMPLETED Day D close")
    print("Entry  : Day D+1 open")
    print("Target : +5%")
    print("Stop   : NONE")
    print(f"Primary research horizon : {HORIZON} trading days")
    print(f"Started : {now:%Y-%m-%d %H:%M:%S}")
    print()
    print(f"Signal mode : {signal_mode}")
    print(f"Data cutoff : {cutoff.date()}")
    print(f"Current IST : {now:%Y-%m-%d %H:%M:%S} IST")
    print()
    print(
        "Sequential diagnostic : "
        + ("ON" if args.sequential else "OFF")
    )
    print()

    # -------------------------------------------------------------------------
    # 1. DATA
    # -------------------------------------------------------------------------
    market_data = download_market_data(cutoff)

    # -------------------------------------------------------------------------
    # 2. FEATURES
    # -------------------------------------------------------------------------
    feature_data = build_all_features(market_data)

    # -------------------------------------------------------------------------
    # 3. OBSERVATIONS
    # -------------------------------------------------------------------------
    observations = build_observations(feature_data)

    if observations.empty:
        raise RuntimeError("No historical observations were created.")

    observations.to_csv(
        OBS_CSV_PATH,
        index=False,
        date_format="%Y-%m-%d",
    )

    print(f"Observations CSV saved: {OBS_CSV_PATH}")
    print()

    # -------------------------------------------------------------------------
    # 4. TRAIN / OOS
    # -------------------------------------------------------------------------
    train, test, split_date = chronological_split(observations)
    print_split_summary(train, test, split_date)

    # -------------------------------------------------------------------------
    # 5. RULE CANDIDATES
    # -------------------------------------------------------------------------
    candidates = generate_candidates()

    print("=" * 100)
    print("RULE LIBRARY")
    print("=" * 100)
    print(f"Atomic conditions : {len(CONDITIONS)}")
    print(f"Candidate rules   : {len(candidates):,}")
    print()

    # -------------------------------------------------------------------------
    # 6. GLOBAL DISCOVERY + OOS
    # -------------------------------------------------------------------------
    global_train_rules, global_oos_rules, global_valid_count = (
        discover_global_rules(
            train,
            test,
            candidates,
        )
    )

    # -------------------------------------------------------------------------
    # 7. ETF-SPECIFIC DISCOVERY + OOS
    # -------------------------------------------------------------------------
    etf_specific_rules, etf_specific_flat, _ = (
        discover_etf_specific_rules(
            train,
            test,
            candidates,
        )
    )

    # -------------------------------------------------------------------------
    # 8. CURRENT PRODUCTION SIGNAL
    # -------------------------------------------------------------------------
    print("=" * 100)
    print("CURRENT SIGNAL ESTIMATION")
    print("=" * 100)

    started_current = time.perf_counter()

    current_ranking = current_production_ranking(
        feature_data=feature_data,
        observations=observations,
        global_oos_rules=global_oos_rules,
        etf_specific_rules=etf_specific_rules,
        cutoff=cutoff,
    )

    print(
        f"Current signal time : "
        f"{time.perf_counter() - started_current:.2f} sec"
    )
    print()

    print_current_ranking(current_ranking)

    # -------------------------------------------------------------------------
    # 9. SUMMARIES
    # -------------------------------------------------------------------------
    etf_summary = make_etf_summary(observations)
    horizon_summary = make_horizon_summary(observations)

    # -------------------------------------------------------------------------
    # 10. OPTIONAL SEQUENTIAL
    # -------------------------------------------------------------------------
    sequential_summary = None
    sequential_horizon = None
    sequential_detail = None

    if args.sequential:
        (
            sequential_summary,
            sequential_horizon,
        ) = run_sequential_diagnostic(
            observations,
            train,
            test,
            global_oos_rules,
            etf_specific_rules,
        )
    else:
        print("=" * 100)
        print("SEQUENTIAL OOS DIAGNOSTIC")
        print("=" * 100)
        print(
            "SKIPPED by default. "
            "Run `python backtest.py --sequential` if you want it."
        )
        print(
            "This keeps the normal research iteration fast; "
            "sequential validation is diagnostic only."
        )
        print()

    # -------------------------------------------------------------------------
    # 11. JSON FOR FUTURE main.py
    # -------------------------------------------------------------------------
    generated_at = now_ist().isoformat()

    save_json(
        global_oos_rules=global_oos_rules,
        etf_specific_rules=etf_specific_rules,
        current_ranking=current_ranking,
        split_date=split_date,
        cutoff=cutoff,
        generated_at=generated_at,
    )

    print(f"Production rule JSON saved: {RULES_JSON_PATH}")
    print()

    # -------------------------------------------------------------------------
    # 12. EXCEL
    # -------------------------------------------------------------------------
    if args.no_excel:
        print("Excel output skipped by --no-excel.")
        print()
    else:
        save_excel(
            observations=observations,
            etf_summary=etf_summary,
            global_train_rules=global_train_rules,
            global_oos_rules=global_oos_rules,
            etf_specific_flat=etf_specific_flat,
            current_ranking=current_ranking,
            horizon_summary=horizon_summary,
            sequential_summary=sequential_summary,
            sequential_horizon=sequential_horizon,
            sequential_detail=sequential_detail,
        )

    # -------------------------------------------------------------------------
    # 13. FINAL
    # -------------------------------------------------------------------------
    total_elapsed = time.perf_counter() - total_started

    print("=" * 100)
    print("FINAL OUTPUTS")
    print("=" * 100)
    print(f"Excel : {EXCEL_PATH}")
    print(f"CSV   : {OBS_CSV_PATH}")
    print(f"JSON  : {RULES_JSON_PATH}")
    print()
    print(f"Total runtime : {total_elapsed:.2f} sec")
    print()
    print(
        "Research hierarchy locked for the next step:"
    )
    print(
        "ETF-specific OOS rule -> Global OOS rule -> "
        "Nearest same-ETF analog -> ETF baseline"
    )
    print(
        "Fastest current candidate = lowest Predicted_Expected_Days_20."
    )
    print(
        "main.py can now consume the JSON without repeating rule discovery."
    )
    print("=" * 100)


if __name__ == "__main__":
    main()