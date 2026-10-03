from __future__ import annotations

import json
import math
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests


# =============================================================================
# PATHS
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent

RESULTS_DIR = BASE_DIR / "results"

MONTHLY_NAV_CSV = (
    RESULTS_DIR / "monthly_nav.csv"
)

STRATEGY_METRICS_CSV = (
    RESULTS_DIR / "strategy_metrics.csv"
)

FUND_METRICS_CSV = (
    RESULTS_DIR / "fund_metrics.csv"
)

SUMMARY_JSON = (
    RESULTS_DIR / "summary.json"
)


# =============================================================================
# CONFIGURATION
# =============================================================================

MONTHLY_SIP = 10_000.0

PORTFOLIO_SIZE = 1

# Display the current Top 5 for information only.
# Historical SIP money is invested in Top 1 only.
DISPLAY_RANKS = 5

MIN_HISTORY_MONTHS = 36

MIN_FEATURE_OBSERVATIONS = 37

BACKTEST_START = "2014-01-01"

MFAPI_ALL_FUNDS_URL = (
    "https://api.mfapi.in/mf"
)

MFAPI_SCHEME_URL = (
    "https://api.mfapi.in/mf/{code}"
)

REQUEST_TIMEOUT = 30

MAX_RETRIES = 4

REQUEST_DELAY = 0.15

USER_AGENT = (
    "Mozilla/5.0 "
    "(Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/142.0.0.0 "
    "Safari/537.36"
)

SESSION = requests.Session()

SESSION.headers.update(
    {
        "User-Agent": USER_AGENT,
        "Accept": "application/json,text/plain,*/*",
    }
)


# =============================================================================
# STRATEGIES
# =============================================================================

STRATEGIES = [
    "MOMENTUM",
    "TREND",
    "QUALITY_MOMENTUM",
    "RISK_ADJUSTED",
    "DRAWDOWN_RECOVERY",
    "CONSISTENCY",
]


# =============================================================================
# HELPERS
# =============================================================================

def ensure_results_dir() -> None:

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


def clean_text(
    value: Any,
) -> str:

    if value is None:
        return ""

    if isinstance(
        value,
        float,
    ) and math.isnan(value):

        return ""

    return str(value).strip()


def safe_float(
    value: Any,
) -> float | None:

    try:

        number = float(value)

        if not np.isfinite(number):
            return None

        return number

    except (
        TypeError,
        ValueError,
    ):

        return None


def pct(
    value: Any,
    decimals: int = 2,
) -> str:

    number = safe_float(value)

    if number is None:
        return "N/A"

    return (
        f"{number * 100:.{decimals}f}%"
    )


def fmt_money(
    value: Any,
) -> str:

    number = safe_float(value)

    if number is None:
        return "N/A"

    return (
        f"₹{number:,.0f}"
    )


def print_header(
    title: str,
) -> None:

    print()
    print("=" * 100)
    print(title)
    print("=" * 100)


def normalize_date_index(
    series: pd.Series,
) -> pd.Series:

    result = series.copy()

    result.index = pd.to_datetime(
        result.index,
        errors="coerce",
        dayfirst=True,
    )

    result = result[
        result.index.notna()
    ]

    result = result[
        ~result.index.duplicated(
            keep="last"
        )
    ]

    result = result.sort_index()

    return result


# =============================================================================
# HTTP
# =============================================================================

_LAST_REQUEST_TIME = 0.0


def api_get(
    url: str,
) -> dict[str, Any] | list[Any]:

    global _LAST_REQUEST_TIME

    for attempt in range(
        MAX_RETRIES
    ):

        elapsed = (
            time.monotonic()
            -
            _LAST_REQUEST_TIME
        )

        if elapsed < REQUEST_DELAY:

            time.sleep(
                REQUEST_DELAY
                -
                elapsed
            )

        try:

            response = SESSION.get(
                url,
                timeout=REQUEST_TIMEOUT,
            )

            _LAST_REQUEST_TIME = (
                time.monotonic()
            )

            if response.status_code == 200:

                payload = response.json()

                # MFAPI /mf returns a LIST.
                #
                # MFAPI /mf/{scheme_code} returns a DICT.
                #
                # Accept both.
                if isinstance(
                    payload,
                    (dict, list),
                ):

                    return payload

                raise RuntimeError(
                    "Unexpected API response type: "
                    f"{type(payload)}"
                )

            if response.status_code == 429:

                wait = min(
                    10.0,
                    1.5 * (
                        2 ** attempt
                    ),
                )

                time.sleep(wait)

                continue

            if response.status_code >= 500:

                wait = min(
                    10.0,
                    1.5 * (
                        2 ** attempt
                    ),
                )

                time.sleep(wait)

                continue

            raise RuntimeError(
                f"HTTP {response.status_code}: "
                f"{url}"
            )

        except requests.RequestException as exc:

            if (
                attempt
                ==
                MAX_RETRIES - 1
            ):

                raise RuntimeError(
                    f"Request failed: "
                    f"{url} | {exc}"
                ) from exc

            wait = min(
                10.0,
                1.5 * (
                    2 ** attempt
                ),
            )

            time.sleep(wait)

    raise RuntimeError(
        f"Could not retrieve API data: {url}"
    )


# =============================================================================
# UNIVERSE DISCOVERY
# =============================================================================

def is_probable_series_or_closed_scheme(
    name: str,
) -> bool:
    """
    Exclude obvious legacy/series/closed-ended style names.

    This remains dynamic: no static fund universe is maintained.
    """

    text = re.sub(
        r"\s+",
        " ",
        name.lower(),
    ).strip()

    excluded_patterns = [
        r"\bseries\s+[ivxlcdm0-9]+\b",
        r"\bseries\s+[a-z]+\b",
        r"\bseries\s+\d+\b",
        r"\bclose[d]?\s*ended\b",
        r"\bclosed\s*end(ed)?\b",
        r"\bfixed\s*maturity\b",
        r"\bfmp\b",
        r"\belss\b",
        r"\btax\s+saver\b",
        r"\bindex\b",
        r"\betf\b",
        r"\bfof\b",
        r"\bfund\s+of\s+funds\b",
    ]

    for pattern in excluded_patterns:

        if re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        ):

            return True

    return False


def discover_universe() -> pd.DataFrame:
    """
    Dynamically discovers current Direct-Growth Small Cap funds from MFAPI.

    Important:
    - No hard-coded fund list.
    - /mf is handled as a list.
    - Individual scheme endpoint is verified.
    - Obvious series / FMP / ETF / index / FoF schemes are excluded.
    """

    print_header(
        "STEP 1: DISCOVER CURRENT SMALL CAP UNIVERSE"
    )

    print(
        "Fetching current mutual fund universe from MFAPI..."
    )

    payload = api_get(
        MFAPI_ALL_FUNDS_URL
    )

    if isinstance(
        payload,
        list,
    ):

        schemes = payload

    elif isinstance(
        payload,
        dict,
    ):

        schemes = payload.get(
            "data",
            [],
        )

    else:

        raise RuntimeError(
            "MFAPI did not return a valid scheme list."
        )

    if not isinstance(
        schemes,
        list,
    ):

        raise RuntimeError(
            "MFAPI scheme list is invalid."
        )

    print(
        f"Total schemes: {len(schemes):,}"
    )

    candidates = []

    for item in schemes:

        if not isinstance(
            item,
            dict,
        ):
            continue

        code = clean_text(
            item.get(
                "schemeCode"
            )
        )

        name = clean_text(
            item.get(
                "schemeName"
            )
        )

        if not code or not name:
            continue

        name_lower = name.lower()

        if "small cap" not in name_lower:
            continue

        if "direct" not in name_lower:
            continue

        if "growth" not in name_lower:
            continue

        if is_probable_series_or_closed_scheme(
            name
        ):
            continue

        candidates.append(
            {
                "code": code,
                "name": name,
            }
        )

    # Remove duplicate scheme codes before verification.
    candidate_df = pd.DataFrame(
        candidates
    )

    if candidate_df.empty:

        raise RuntimeError(
            "No Direct-Growth Small Cap "
            "candidates were discovered."
        )

    candidate_df = (
        candidate_df
        .drop_duplicates(
            subset=["code"]
        )
        .reset_index(
            drop=True
        )
    )

    candidates = candidate_df.to_dict(
        orient="records"
    )

    print(
        "Direct + Growth + Small Cap "
        f"candidates: {len(candidates)}"
    )

    verified = []

    for index, candidate in enumerate(
        candidates,
        start=1,
    ):

        code = candidate[
            "code"
        ]

        name = candidate[
            "name"
        ]

        try:

            detail = api_get(
                MFAPI_SCHEME_URL.format(
                    code=code
                )
            )

            if not isinstance(
                detail,
                dict,
            ):

                continue

            meta = detail.get(
                "meta",
                {},
            )

            if not isinstance(
                meta,
                dict,
            ):

                meta = {}

            meta_name = clean_text(
                meta.get(
                    "scheme_name"
                )
            )

            if meta_name:

                name = meta_name

            name_lower = name.lower()

            if "small cap" not in name_lower:
                continue

            if "direct" not in name_lower:
                continue

            if "growth" not in name_lower:
                continue

            if is_probable_series_or_closed_scheme(
                name
            ):
                continue

            verified.append(
                {
                    "code": code,
                    "name": name,
                }
            )

        except Exception:
            continue

        if index % 20 == 0:

            print(
                f"  Verified "
                f"{index}/{len(candidates)}"
            )

    if not verified:

        raise RuntimeError(
            "No Direct-Growth Small Cap "
            "schemes were verified."
        )

    universe = pd.DataFrame(
        verified
    )

    universe = (
        universe
        .drop_duplicates(
            subset=["code"]
        )
        .reset_index(
            drop=True
        )
    )

    print(
        "Verified Direct-Growth Small Cap "
        f"schemes: {len(universe)}"
    )

    return universe


# =============================================================================
# NAV PARSING
# =============================================================================

def parse_mfapi_nav_data(
    payload: dict[str, Any] | list[Any],
) -> pd.Series:

    if not isinstance(
        payload,
        dict,
    ):

        return pd.Series(
            dtype=float
        )

    data = payload.get(
        "data",
        [],
    )

    if not isinstance(
        data,
        list,
    ):

        return pd.Series(
            dtype=float
        )

    dates = []
    values = []

    for item in data:

        if not isinstance(
            item,
            dict,
        ):
            continue

        date_text = clean_text(
            item.get(
                "date"
            )
        )

        nav_value = safe_float(
            item.get(
                "nav"
            )
        )

        if not date_text:
            continue

        if (
            nav_value is None
            or
            nav_value <= 0
        ):
            continue

        date = pd.to_datetime(
            date_text,
            errors="coerce",
            dayfirst=True,
        )

        if pd.isna(date):
            continue

        dates.append(
            date.normalize()
        )

        values.append(
            nav_value
        )

    if not dates:
        return pd.Series(
            dtype=float
        )

    series = pd.Series(
        values,
        index=pd.DatetimeIndex(
            dates
        ),
        dtype=float,
    )

    series = series[
        ~series.index.duplicated(
            keep="last"
        )
    ]

    series = series.sort_index()

    series = series[
        np.isfinite(series)
        &
        (series > 0)
    ]

    return series


def download_one_nav(
    code: str,
) -> pd.Series:

    payload = api_get(
        MFAPI_SCHEME_URL.format(
            code=code
        )
    )

    return parse_mfapi_nav_data(
        payload
    )


def download_nav_history(
    universe: pd.DataFrame,
    latest_date: pd.Timestamp,
) -> dict[str, pd.Series]:

    print_header(
        "STEP 2: DOWNLOAD HISTORICAL NAV DATA"
    )

    nav_data = {}

    total = len(universe)

    for position, row in universe.iterrows():

        code = clean_text(
            row["code"]
        )

        name = clean_text(
            row["name"]
        )

        try:

            series = download_one_nav(
                code
            )

            if series.empty:
                continue

            series = series[
                series.index
                <=
                latest_date
            ]

            if series.empty:
                continue

            nav_data[
                code
            ] = series

            print(
                f"{position + 1:>3} "
                f"{name:<65} "
                f"{len(series):>5}"
            )

        except Exception as exc:

            print(
                f"{position + 1:>3} "
                f"{name:<65} "
                f"FAILED: {exc}"
            )

    print()
    print(
        f"NAV datasets downloaded: "
        f"{len(nav_data)}"
    )

    return nav_data


# =============================================================================
# MONTHLY NAV
# =============================================================================

def build_monthly_nav(
    nav_data: dict[str, pd.Series],
    start_date: str,
    end_date: pd.Timestamp,
) -> pd.DataFrame:

    monthly = {}

    start = pd.Timestamp(
        start_date
    )

    end = pd.Timestamp(
        end_date
    )

    for code, series in nav_data.items():

        normalized = normalize_date_index(
            series
        )

        if normalized.empty:
            continue

        monthly_series = (
            normalized
            .resample("ME")
            .last()
        )

        monthly_series = monthly_series[
            (
                monthly_series.index
                >=
                start
            )
            &
            (
                monthly_series.index
                <=
                end
            )
        ]

        if not monthly_series.empty:

            monthly[
                code
            ] = monthly_series

    if not monthly:

        return pd.DataFrame()

    result = pd.DataFrame(
        monthly
    )

    result.index = pd.to_datetime(
        result.index
    )

    result = result.sort_index()

    return result


# =============================================================================
# NAV LOOKUPS
# =============================================================================

def find_first_nav_after(
    code: str,
    decision_date: pd.Timestamp,
    nav_data: dict[str, pd.Series],
) -> tuple[pd.Timestamp | None, float | None]:

    series = nav_data.get(
        code
    )

    if series is None or series.empty:

        return None, None

    normalized = normalize_date_index(
        series
    )

    # STRICTLY AFTER decision date.
    valid = normalized[
        normalized.index
        >
        decision_date
    ]

    valid = valid[
        np.isfinite(valid)
        &
        (valid > 0)
    ]

    if valid.empty:

        return None, None

    purchase_date = valid.index[0]

    purchase_nav = safe_float(
        valid.iloc[0]
    )

    if purchase_nav is None:

        return None, None

    return (
        purchase_date,
        purchase_nav,
    )


def find_valuation_nav(
    code: str,
    valuation_date: pd.Timestamp,
    nav_data: dict[str, pd.Series],
) -> float | None:

    series = nav_data.get(
        code
    )

    if series is None or series.empty:

        return None

    normalized = normalize_date_index(
        series
    )

    valid = normalized[
        normalized.index
        <=
        valuation_date
    ]

    valid = valid[
        np.isfinite(valid)
        &
        (valid > 0)
    ]

    if valid.empty:

        return None

    return safe_float(
        valid.iloc[-1]
    )


# =============================================================================
# FUND METRICS
# =============================================================================

def max_drawdown_from_series(
    series: pd.Series,
) -> float:

    clean = pd.to_numeric(
        series,
        errors="coerce",
    ).dropna()

    if clean.empty:
        return np.nan

    running_max = clean.cummax()

    drawdown = (
        clean / running_max
    ) - 1.0

    return float(
        drawdown.min()
    )


def annualized_sharpe(
    monthly_returns: pd.Series,
) -> float:

    returns = pd.to_numeric(
        monthly_returns,
        errors="coerce",
    ).dropna()

    if len(returns) < 2:
        return np.nan

    std = float(
        returns.std(
            ddof=1
        )
    )

    if (
        not np.isfinite(std)
        or
        std <= 0
    ):
        return np.nan

    return float(
        returns.mean()
        /
        std
        *
        np.sqrt(12)
    )


def annualized_sortino(
    monthly_returns: pd.Series,
) -> float:

    returns = pd.to_numeric(
        monthly_returns,
        errors="coerce",
    ).dropna()

    if len(returns) < 2:
        return np.nan

    downside = returns[
        returns < 0
    ]

    if downside.empty:
        return np.nan

    downside_deviation = math.sqrt(
        float(
            (
                downside ** 2
            ).mean()
        )
    )

    if (
        not np.isfinite(
            downside_deviation
        )
        or
        downside_deviation <= 0
    ):

        return np.nan

    return float(
        returns.mean()
        /
        downside_deviation
        *
        np.sqrt(12)
    )


def calculate_fund_features(
    monthly_nav: pd.DataFrame,
    decision_date: pd.Timestamp,
) -> pd.DataFrame:

    rows = []

    if monthly_nav.empty:

        return pd.DataFrame()

    for code in monthly_nav.columns:

        series = monthly_nav[
            code
        ].dropna()

        series = series[
            series.index
            <=
            decision_date
        ]

        if len(series) < MIN_FEATURE_OBSERVATIONS:

            continue

        current_nav = safe_float(
            series.iloc[-1]
        )

        if current_nav is None:
            continue

        def historical_return(
            months: int,
        ) -> float:

            if len(series) <= months:
                return np.nan

            old_value = safe_float(
                series.iloc[-1 - months]
            )

            if (
                old_value is None
                or
                old_value <= 0
            ):

                return np.nan

            return (
                current_nav
                /
                old_value
            ) - 1.0

        ret_12 = historical_return(
            12
        )

        ret_24 = historical_return(
            24
        )

        ret_36 = historical_return(
            36
        )

        ret_6 = historical_return(
            6
        )

        monthly_returns = (
            series
            .pct_change()
            .dropna()
        )

        sharpe = annualized_sharpe(
            monthly_returns
        )

        sortino = annualized_sortino(
            monthly_returns
        )

        max_dd = max_drawdown_from_series(
            series
        )

        profitable_months = (
            float(
                (
                    monthly_returns > 0
                ).mean()
            )
            if not monthly_returns.empty
            else np.nan
        )

        # 12-month moving average.
        if len(series) >= 12:

            ma_12 = float(
                series
                .rolling(12)
                .mean()
                .iloc[-1]
            )

            if (
                np.isfinite(ma_12)
                and
                ma_12 != 0
            ):

                trend_ratio = (
                    current_nav
                    /
                    ma_12
                ) - 1.0

            else:

                trend_ratio = np.nan

        else:

            trend_ratio = np.nan

        # Highest NAV over available 100-month history.
        high_window = series.tail(
            100
        )

        highest_100 = safe_float(
            high_window.max()
        )

        if (
            highest_100 is not None
            and
            highest_100 > 0
        ):

            distance_high = (
                current_nav
                /
                highest_100
            ) - 1.0

        else:

            distance_high = np.nan

        momentum_acceleration = (
            ret_6 - ret_12
            if (
                np.isfinite(ret_6)
                and
                np.isfinite(ret_12)
            )
            else np.nan
        )

        # Recovery score:
        #
        # 50% drawdown recovery component
        # 50% trend component.
        #
        # Less negative drawdown is better.
        if np.isfinite(max_dd):

            drawdown_component = (
                1.0 + max_dd
            )

        else:

            drawdown_component = np.nan

        if np.isfinite(trend_ratio):

            trend_component = (
                1.0 + trend_ratio
            )

        else:

            trend_component = np.nan

        if (
            np.isfinite(
                drawdown_component
            )
            and
            np.isfinite(
                trend_component
            )
        ):

            recovery_score = (
                0.50
                *
                drawdown_component
                +
                0.50
                *
                trend_component
            )

        else:

            recovery_score = np.nan

        rows.append(
            {
                "code": code,
                "current_nav": current_nav,
                "ret_6": ret_6,
                "ret_12": ret_12,
                "ret_24": ret_24,
                "ret_36": ret_36,
                "sharpe": sharpe,
                "sortino": sortino,
                "max_drawdown": max_dd,
                "profitable_months": profitable_months,
                "trend_ratio": trend_ratio,
                "distance_high": distance_high,
                "momentum_acceleration":
                    momentum_acceleration,
                "recovery_score":
                    recovery_score,
            }
        )

    if not rows:

        return pd.DataFrame()

    return pd.DataFrame(
        rows
    )


# =============================================================================
# SCORING
# =============================================================================

def percentile_score(
    series: pd.Series,
    higher_is_better: bool = True,
) -> pd.Series:

    numeric = pd.to_numeric(
        series,
        errors="coerce",
    )

    if numeric.notna().sum() == 0:

        return pd.Series(
            np.nan,
            index=series.index,
            dtype=float,
        )

    rank = numeric.rank(
        method="average",
        pct=True,
    )

    if higher_is_better:

        return rank

    return 1.0 - rank


def normalized_metric(
    series: pd.Series,
    higher_is_better: bool = True,
) -> pd.Series:

    return percentile_score(
        series,
        higher_is_better,
    )


def add_strategy_score(
    features: pd.DataFrame,
    strategy_name: str,
) -> pd.DataFrame:

    if features.empty:

        return pd.DataFrame()

    result = features.copy()

    component_definitions = {
        "m12_score": (
            "ret_12",
            True,
        ),
        "m24_score": (
            "ret_24",
            True,
        ),
        "m36_score": (
            "ret_36",
            True,
        ),
        "trend_score": (
            "trend_ratio",
            True,
        ),
        "sharpe_score": (
            "sharpe",
            True,
        ),
        "sortino_score": (
            "sortino",
            True,
        ),
        "drawdown_score": (
            "max_drawdown",
            True,
        ),
        "profitable_score": (
            "profitable_months",
            True,
        ),
        "distance_high_score": (
            "distance_high",
            True,
        ),
        "acceleration_score": (
            "momentum_acceleration",
            True,
        ),
        "recovery_score_norm": (
            "recovery_score",
            True,
        ),
    }

    for output_name, (
        source_name,
        higher_is_better,
    ) in component_definitions.items():

        result[
            output_name
        ] = percentile_score(
            result[source_name],
            higher_is_better,
        )

    weights_by_strategy = {

        "MOMENTUM": {
            "m12_score": 0.50,
            "m24_score": 0.25,
            "m36_score": 0.25,
        },

        "TREND": {
            "m12_score": 0.30,
            "m24_score": 0.15,
            "trend_score": 0.35,
            "acceleration_score": 0.20,
        },

        "QUALITY_MOMENTUM": {
            "m12_score": 0.30,
            "m24_score": 0.15,
            "trend_score": 0.15,
            "sharpe_score": 0.15,
            "sortino_score": 0.10,
            "profitable_score": 0.15,
        },

        "RISK_ADJUSTED": {
            "m12_score": 0.25,
            "m24_score": 0.10,
            "m36_score": 0.10,
            "sharpe_score": 0.20,
            "sortino_score": 0.20,
            "drawdown_score": 0.15,
        },

        "DRAWDOWN_RECOVERY": {
            "m12_score": 0.20,
            "trend_score": 0.20,
            "drawdown_score": 0.20,
            "distance_high_score": 0.15,
            "recovery_score_norm": 0.25,
        },

        "CONSISTENCY": {
            "m12_score": 0.20,
            "m24_score": 0.15,
            "m36_score": 0.10,
            "sharpe_score": 0.15,
            "sortino_score": 0.15,
            "profitable_score": 0.25,
        },
    }

    weights = weights_by_strategy.get(
        strategy_name
    )

    if weights is None:

        raise ValueError(
            f"Unknown strategy: {strategy_name}"
        )

    numerator = pd.Series(
        0.0,
        index=result.index,
    )

    denominator = pd.Series(
        0.0,
        index=result.index,
    )

    for metric, weight in weights.items():

        score = pd.to_numeric(
            result[metric],
            errors="coerce",
        )

        valid = score.notna()

        numerator.loc[valid] += (
            score.loc[valid]
            *
            weight
        )

        denominator.loc[valid] += (
            weight
        )

    result[
        "strategy_score"
    ] = (
        numerator
        /
        denominator.replace(
            0,
            np.nan,
        )
    )

    result = result.sort_values(
        [
            "strategy_score",
            "ret_12",
            "ret_24",
            "code",
        ],
        ascending=[
            False,
            False,
            False,
            True,
        ],
        na_position="last",
    ).reset_index(
        drop=True
    )

    return result


# =============================================================================
# XIRR
# =============================================================================

def xnpv(
    rate: float,
    cashflows: list[tuple[pd.Timestamp, float]],
) -> float:

    if not cashflows:
        return np.nan

    first_date = cashflows[0][0]

    total = 0.0

    for date, amount in cashflows:

        days = (
            date - first_date
        ).days

        denominator = (
            1.0 + rate
        ) ** (
            days / 365.0
        )

        if denominator == 0:
            return np.nan

        total += (
            amount
            /
            denominator
        )

    return total


def calculate_xirr(
    cashflows: list[
        tuple[pd.Timestamp, float]
    ],
) -> float:

    if len(cashflows) < 2:

        return np.nan

    cashflows = sorted(
        cashflows,
        key=lambda x: x[0],
    )

    has_positive = any(
        amount > 0
        for _, amount in cashflows
    )

    has_negative = any(
        amount < 0
        for _, amount in cashflows
    )

    if not has_positive or not has_negative:

        return np.nan

    # First try a broad grid to find a sign change.
    grid = np.concatenate(
        [
            np.linspace(
                -0.9999,
                1.0,
                400,
            ),
            np.linspace(
                1.01,
                10.0,
                300,
            ),
        ]
    )

    previous_rate = None
    previous_value = None

    for rate in grid:

        try:

            value = xnpv(
                float(rate),
                cashflows,
            )

        except Exception:

            previous_rate = None
            previous_value = None
            continue

        if not np.isfinite(value):

            previous_rate = None
            previous_value = None
            continue

        if (
            previous_value is not None
            and
            np.sign(value)
            !=
            np.sign(previous_value)
        ):

            low = previous_rate
            high = float(rate)

            for _ in range(200):

                mid = (
                    low + high
                ) / 2.0

                mid_value = xnpv(
                    mid,
                    cashflows,
                )

                if not np.isfinite(
                    mid_value
                ):

                    break

                if abs(
                    mid_value
                ) < 1e-10:

                    return mid

                low_value = xnpv(
                    low,
                    cashflows,
                )

                if (
                    np.sign(mid_value)
                    ==
                    np.sign(low_value)
                ):

                    low = mid

                else:

                    high = mid

            return (
                low + high
            ) / 2.0

        previous_rate = float(rate)
        previous_value = float(value)

    return np.nan


# =============================================================================
# PORTFOLIO METRICS
# =============================================================================

def calculate_portfolio_metrics(
    portfolio_history: pd.DataFrame,
    purchase_history: pd.DataFrame,
) -> dict[str, Any]:

    empty_result = {
        "xirr": np.nan,
        "twr_return": np.nan,
        "volatility": np.nan,
        "max_drawdown": np.nan,
        "sharpe": np.nan,
        "sortino": np.nan,
        "calmar": np.nan,
        "contributions": 0.0,
        "sip_count": 0,
        "final_value": np.nan,
    }

    if portfolio_history.empty:

        return empty_result

    history = portfolio_history.copy()

    history[
        "date"
    ] = pd.to_datetime(
        history["date"],
        errors="coerce",
    )

    history = history.dropna(
        subset=["date"]
    )

    history = history.sort_values(
        "date"
    ).reset_index(
        drop=True
    )

    history = history[
        history["portfolio_value"].notna()
    ].copy()

    if history.empty:

        return empty_result

    contributions = float(
        pd.to_numeric(
            history.get(
                "contribution",
                0.0,
            ),
            errors="coerce",
        )
        .fillna(0.0)
        .sum()
    )

    sip_count = int(
        (
            pd.to_numeric(
                history.get(
                    "contribution",
                    0.0,
                ),
                errors="coerce",
            )
            .fillna(0.0)
            > 0
        ).sum()
    )

    final_value = safe_float(
        history[
            "portfolio_value"
        ].iloc[-1]
    )

    # -------------------------------------------------------------------------
    # XIRR
    # -------------------------------------------------------------------------

    cashflows = []

    if not purchase_history.empty:

        purchases = purchase_history.copy()

        purchases[
            "purchase_date"
        ] = pd.to_datetime(
            purchases[
                "purchase_date"
            ],
            errors="coerce",
        )

        purchases = purchases.dropna(
            subset=[
                "purchase_date"
            ]
        )

        for _, row in purchases.iterrows():

            amount = safe_float(
                row.get(
                    "amount"
                )
            )

            date = row.get(
                "purchase_date"
            )

            if (
                amount is None
                or
                pd.isna(date)
            ):
                continue

            cashflows.append(
                (
                    pd.Timestamp(date),
                    -amount,
                )
            )

    if (
        final_value is not None
        and
        not history.empty
    ):

        final_date = pd.Timestamp(
            history[
                "date"
            ].iloc[-1]
        )

        cashflows.append(
            (
                final_date,
                final_value,
            )
        )

    xirr = calculate_xirr(
        cashflows
    )

    # -------------------------------------------------------------------------
    # TWR
    # -------------------------------------------------------------------------

    values = history[
        "portfolio_value"
    ].astype(float)

    contribution_series = pd.to_numeric(
        history.get(
            "contribution",
            pd.Series(
                0.0,
                index=history.index,
            ),
        ),
        errors="coerce",
    ).fillna(0.0)

    twr_returns = []

    previous_value = None

    for current_value, contribution in zip(
        values,
        contribution_series,
    ):

        if previous_value is not None:

            denominator = (
                previous_value
                +
                contribution
            )

            if (
                denominator > 0
                and
                np.isfinite(
                    current_value
                )
            ):

                monthly_return = (
                    current_value
                    /
                    denominator
                ) - 1.0

                if np.isfinite(
                    monthly_return
                ):

                    twr_returns.append(
                        monthly_return
                    )

        previous_value = current_value

    if twr_returns:

        twr_return = float(
            np.prod(
                1.0
                +
                np.asarray(
                    twr_returns
                )
            )
            - 1.0
        )

        twr_series = pd.Series(
            twr_returns
        )

        volatility = float(
            twr_series.std(
                ddof=1
            )
            *
            np.sqrt(12)
        ) if len(
            twr_series
        ) > 1 else np.nan

        sharpe = annualized_sharpe(
            twr_series
        )

        sortino = annualized_sortino(
            twr_series
        )

    else:

        twr_return = np.nan
        volatility = np.nan
        sharpe = np.nan
        sortino = np.nan

    # -------------------------------------------------------------------------
    # Portfolio drawdown.
    # -------------------------------------------------------------------------

    running_max = (
        values.cummax()
    )

    drawdowns = (
        values
        /
        running_max
    ) - 1.0

    max_drawdown = float(
        drawdowns.min()
    )

    # -------------------------------------------------------------------------
    # Calmar.
    # -------------------------------------------------------------------------

    if (
        xirr is not None
        and
        np.isfinite(xirr)
        and
        np.isfinite(max_drawdown)
        and
        max_drawdown < 0
    ):

        calmar = (
            xirr
            /
            abs(max_drawdown)
        )

    else:

        calmar = np.nan

    return {
        "xirr": xirr,
        "twr_return": twr_return,
        "volatility": volatility,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "contributions": contributions,
        "sip_count": sip_count,
        "final_value": final_value,
    }


# =============================================================================
# PURCHASE CANDIDATE RESOLUTION
# =============================================================================

def resolve_monthly_purchase_candidates(
    scored: pd.DataFrame,
    decision_date: pd.Timestamp,
    nav_data: dict[str, pd.Series],
    portfolio_size: int,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:

    purchases = []

    unavailable = []

    if scored.empty:

        return purchases, unavailable

    amount_per_fund = (
        MONTHLY_SIP
        /
        portfolio_size
    )

    # IMPORTANT:
    #
    # Historical SIP uses ONLY the highest-ranked eligible fund.
    # If Rank 1 has no valid purchase NAV strictly after the decision date,
    # continue down the ranking only to find a replacement for that ONE SIP.
    # Other ranked funds are informational and receive no SIP allocation.
    #

    for strategy_rank, row in scored.iterrows():

        if len(purchases) >= portfolio_size:
            break

        code = clean_text(
            row.get(
                "code"
            )
        )

        if not code:
            continue

        name = clean_text(
            row.get(
                "name",
                code,
            )
        )

        purchase_date, purchase_nav = (
            find_first_nav_after(
                code,
                decision_date,
                nav_data,
            )
        )

        if (
            purchase_date is None
            or
            purchase_nav is None
        ):

            unavailable.append(
                {
                    "decision_date":
                        decision_date,
                    "code":
                        code,
                    "name":
                        name,
                    "strategy_rank":
                        int(
                            strategy_rank
                            +
                            1
                        ),
                    "month_action":
                        "candidate replaced",
                    "reason":
                        "purchase NAV unavailable",
                }
            )

            continue

        units = (
            amount_per_fund
            /
            purchase_nav
        )

        purchases.append(
            {
                "decision_date":
                    decision_date,
                "purchase_date":
                    purchase_date,
                "portfolio_rank":
                    len(purchases)
                    +
                    1,
                "strategy_rank":
                    int(
                        strategy_rank
                        +
                        1
                    ),
                "code":
                    code,
                "name":
                    name,
                "amount":
                    amount_per_fund,
                "purchase_nav":
                    purchase_nav,
                "units":
                    units,
                "strategy_score":
                    safe_float(
                        row.get(
                            "strategy_score"
                        )
                    ),
            }
        )

    return purchases, unavailable


# =============================================================================
# STRATEGY BACKTEST
# =============================================================================

def run_strategy_backtest(
    strategy_name: str,
    monthly_nav: pd.DataFrame,
    nav_data: dict[str, pd.Series],
    fund_info: pd.DataFrame,
    decision_dates: pd.DatetimeIndex,
) -> dict[str, Any]:

    print()
    print(
        f"Running {strategy_name}..."
    )

    selection_history = []

    score_history = []

    purchase_history = []

    skipped_dates = []

    amount_per_fund = (
        MONTHLY_SIP
        /
        PORTFOLIO_SIZE
    )

    for decision_date in decision_dates:

        features = calculate_fund_features(
            monthly_nav,
            decision_date,
        )

        if features.empty:

            skipped_dates.append(
                {
                    "decision_date":
                        decision_date,
                    "month_action":
                        "skipped",
                    "reason":
                        "no eligible fund features",
                }
            )

            continue

        scored = add_strategy_score(
            features,
            strategy_name,
        )

        if scored.empty:

            skipped_dates.append(
                {
                    "decision_date":
                        decision_date,
                    "month_action":
                        "skipped",
                    "reason":
                        "no strategy scores",
                }
            )

            continue

        names = fund_info[
            [
                "code",
                "name",
            ]
        ].copy()

        scored = scored.merge(
            names,
            on="code",
            how="left",
        )

        # Store complete historical ranking.
        for strategy_rank, row in scored.iterrows():

            score_history.append(
                {
                    "decision_date":
                        decision_date,
                    "strategy":
                        strategy_name,
                    "strategy_rank":
                        int(
                            strategy_rank
                            +
                            1
                        ),
                    "code":
                        clean_text(
                            row["code"]
                        ),
                    "name":
                        clean_text(
                            row.get(
                                "name",
                                row["code"],
                            )
                        ),
                    "strategy_score":
                        safe_float(
                            row.get(
                                "strategy_score"
                            )
                        ),
                    "current_nav":
                        safe_float(
                            row.get(
                                "current_nav"
                            )
                        ),
                    "ret_6":
                        safe_float(
                            row.get(
                                "ret_6"
                            )
                        ),
                    "ret_12":
                        safe_float(
                            row.get(
                                "ret_12"
                            )
                        ),
                    "ret_24":
                        safe_float(
                            row.get(
                                "ret_24"
                            )
                        ),
                    "ret_36":
                        safe_float(
                            row.get(
                                "ret_36"
                            )
                        ),
                    "trend_ratio":
                        safe_float(
                            row.get(
                                "trend_ratio"
                            )
                        ),
                    "sharpe":
                        safe_float(
                            row.get(
                                "sharpe"
                            )
                        ),
                    "sortino":
                        safe_float(
                            row.get(
                                "sortino"
                            )
                        ),
                    "max_drawdown":
                        safe_float(
                            row.get(
                                "max_drawdown"
                            )
                        ),
                    "profitable_months":
                        safe_float(
                            row.get(
                                "profitable_months"
                            )
                        ),
                    "distance_high":
                        safe_float(
                            row.get(
                                "distance_high"
                            )
                        ),
                    "momentum_acceleration":
                        safe_float(
                            row.get(
                                "momentum_acceleration"
                            )
                        ),
                    "recovery_score":
                        safe_float(
                            row.get(
                                "recovery_score"
                            )
                        ),
                }
            )

        purchases, unavailable = (
            resolve_monthly_purchase_candidates(
                scored,
                decision_date,
                nav_data,
                PORTFOLIO_SIZE,
            )
        )

        # Candidate failures are diagnostic only.
        #
        # They do not cancel the monthly SIP if five replacement candidates
        # were successfully found.
        skipped_dates.extend(
            unavailable
        )

        if len(purchases) < PORTFOLIO_SIZE:

            skipped_dates.append(
                {
                    "decision_date":
                        decision_date,
                    "month_action":
                        "skipped",
                    "reason":
                        "Rank 1 and all replacement candidates had no "
                        "usable post-decision NAV",
                    "usable_candidates":
                        len(purchases),
                    "required_candidates":
                        PORTFOLIO_SIZE,
                }
            )

            continue

        # Exactly one monthly SIP is committed here.
        for purchase in purchases:

            purchase_history.append(
                {
                    "strategy":
                        strategy_name,
                    **purchase,
                }
            )

        selected_codes = [
            purchase[
                "code"
            ]
            for purchase in purchases
        ]

        selection_history.append(
            {
                "decision_date":
                    decision_date,
                "strategy":
                    strategy_name,
                "portfolio_size":
                    PORTFOLIO_SIZE,
                "monthly_sip":
                    MONTHLY_SIP,
                "selected_codes":
                    "|".join(
                        selected_codes
                    ),
                "purchase_funds":
                    PORTFOLIO_SIZE,
                "unavailable_candidates":
                    len(unavailable),
            }
        )

    purchase_df = pd.DataFrame(
        purchase_history
    )

    if not purchase_df.empty:

        purchase_df[
            "purchase_date"
        ] = pd.to_datetime(
            purchase_df[
                "purchase_date"
            ]
        )

        purchase_df[
            "decision_date"
        ] = pd.to_datetime(
            purchase_df[
                "decision_date"
            ]
        )

        purchase_df = purchase_df.sort_values(
            [
                "purchase_date",
                "portfolio_rank",
                "code",
            ]
        ).reset_index(
            drop=True
        )

    # -------------------------------------------------------------------------
    # Portfolio valuation.
    # -------------------------------------------------------------------------

    if purchase_df.empty:

        portfolio_history = pd.DataFrame(
            columns=[
                "date",
                "portfolio_value",
                "contribution",
            ]
        )

    else:

        first_purchase_month = (
            purchase_df[
                "purchase_date"
            ]
            .min()
            .to_period("M")
            .to_timestamp("M")
        )

        valuation_dates = (
            pd.date_range(
                start=first_purchase_month,
                end=monthly_nav.index.max(),
                freq="ME",
            )
        )

        holdings_units: dict[
            str,
            float
        ] = {}

        purchase_idx = 0

        portfolio_rows = []

        for valuation_date in valuation_dates:

            contribution = 0.0

            while (
                purchase_idx
                <
                len(purchase_df)
                and
                purchase_df.iloc[
                    purchase_idx
                ][
                    "purchase_date"
                ]
                <=
                valuation_date
            ):

                purchase = purchase_df.iloc[
                    purchase_idx
                ]

                code = clean_text(
                    purchase["code"]
                )

                units = safe_float(
                    purchase["units"]
                )

                amount = safe_float(
                    purchase["amount"]
                )

                if (
                    units is not None
                    and
                    amount is not None
                ):

                    holdings_units[
                        code
                    ] = (
                        holdings_units.get(
                            code,
                            0.0,
                        )
                        +
                        units
                    )

                    contribution += amount

                purchase_idx += 1

            total_value = 0.0

            valuation_valid = True

            for code, units in holdings_units.items():

                nav = find_valuation_nav(
                    code,
                    valuation_date,
                    nav_data,
                )

                if nav is None:

                    valuation_valid = False

                    break

                total_value += (
                    units
                    *
                    nav
                )

            if valuation_valid:

                portfolio_rows.append(
                    {
                        "date":
                            valuation_date,
                        "portfolio_value":
                            total_value,
                        "contribution":
                            contribution,
                    }
                )

            else:

                portfolio_rows.append(
                    {
                        "date":
                            valuation_date,
                        "portfolio_value":
                            np.nan,
                        "contribution":
                            contribution,
                    }
                )

        portfolio_history = pd.DataFrame(
            portfolio_rows
        )

    metrics = calculate_portfolio_metrics(
        portfolio_history,
        purchase_df,
    )

    selection_count = len(
        selection_history
    )

    skipped_month_count = 0

    if skipped_dates:

        skipped_frame = pd.DataFrame(
            skipped_dates
        )

        if not skipped_frame.empty:

            if "month_action" in skipped_frame.columns:

                skipped_month_count = int(
                    (
                        skipped_frame[
                            "month_action"
                        ]
                        ==
                        "skipped"
                    ).sum()
                )

    else:

        skipped_frame = pd.DataFrame()

    # -------------------------------------------------------------------------
    # Print results.
    # -------------------------------------------------------------------------

    print(
        f"  Decisions / SIPs : "
        f"{selection_count}"
    )

    if selection_history:

        print(
            f"  First decision   : "
            f"{pd.Timestamp(selection_history[0]['decision_date']).date()}"
        )

        print(
            f"  Last decision    : "
            f"{pd.Timestamp(selection_history[-1]['decision_date']).date()}"
        )

    print(
        f"  Skipped months   : "
        f"{skipped_month_count}"
    )

    if not skipped_frame.empty:

        reason_counts = (
            skipped_frame[
                skipped_frame[
                    "month_action"
                ]
                ==
                "skipped"
            ]
            .get(
                "reason",
                pd.Series(
                    dtype=str
                ),
            )
            .value_counts()
        )

        if not reason_counts.empty:

            print(
                "  Skip reasons:"
            )

            for reason, count in reason_counts.items():

                print(
                    f"    {reason}: {count}"
                )

    print(
        f"  XIRR       : "
        f"{pct(metrics['xirr'])}"
    )

    print(
        f"  TWR Return : "
        f"{pct(metrics['twr_return'])}"
    )

    print(
        f"  Volatility : "
        f"{pct(metrics['volatility'])}"
    )

    print(
        f"  Max DD     : "
        f"{pct(metrics['max_drawdown'])}"
    )

    sharpe = metrics[
        "sharpe"
    ]

    sortino = metrics[
        "sortino"
    ]

    calmar = metrics[
        "calmar"
    ]

    print(
        "  Sharpe     : "
        + (
            f"{sharpe:.3f}"
            if safe_float(sharpe)
            is not None
            else "N/A"
        )
    )

    print(
        "  Sortino    : "
        + (
            f"{sortino:.3f}"
            if safe_float(sortino)
            is not None
            else "N/A"
        )
    )

    print(
        "  Calmar     : "
        + (
            f"{calmar:.3f}"
            if safe_float(calmar)
            is not None
            else "N/A"
        )
    )

    print(
        f"  Contributions: "
        f"{fmt_money(metrics['contributions'])}"
    )

    print(
        f"  SIP count  : "
        f"{metrics['sip_count']}"
    )

    print(
        f"  Final value : "
        f"{fmt_money(metrics['final_value'])}"
    )

    return {
        "strategy":
            strategy_name,
        "selection_history":
            pd.DataFrame(
                selection_history
            ),
        "score_history":
            pd.DataFrame(
                score_history
            ),
        "purchase_history":
            purchase_df,
        "portfolio_history":
            portfolio_history,
        "skipped_dates":
            skipped_frame,
        "metrics":
            metrics,
    }


# =============================================================================
# SAVE STRATEGY OUTPUT
# =============================================================================

def save_strategy_output(
    result: dict[str, Any],
) -> None:

    strategy_name = result[
        "strategy"
    ]

    suffix = strategy_name.lower()

    selection_df = result[
        "selection_history"
    ]

    scores_df = result[
        "score_history"
    ]

    purchases_df = result[
        "purchase_history"
    ]

    portfolio_df = result[
        "portfolio_history"
    ]

    skipped_df = result[
        "skipped_dates"
    ]

    selection_df.to_csv(
        RESULTS_DIR
        /
        f"selection_history_{suffix}.csv",
        index=False,
    )

    scores_df.to_csv(
        RESULTS_DIR
        /
        f"strategy_scores_{suffix}.csv",
        index=False,
    )

    purchases_df.to_csv(
        RESULTS_DIR
        /
        f"purchase_history_{suffix}.csv",
        index=False,
    )

    portfolio_df.to_csv(
        RESULTS_DIR
        /
        f"portfolio_history_{suffix}.csv",
        index=False,
    )

    skipped_df.to_csv(
        RESULTS_DIR
        /
        f"skipped_months_{suffix}.csv",
        index=False,
    )


# =============================================================================
# MARKET REGIME
# =============================================================================

def calculate_market_regime(
    latest_features: pd.DataFrame,
) -> dict[str, Any]:

    if latest_features.empty:

        return {
            "regime": "UNAVAILABLE",
            "breadth": np.nan,
            "positive_momentum": np.nan,
            "median_momentum": np.nan,
            "median_trend": np.nan,
        }

    valid = latest_features[
        latest_features[
            "ret_12"
        ].notna()
        &
        latest_features[
            "trend_ratio"
        ].notna()
    ].copy()

    if valid.empty:

        return {
            "regime": "UNAVAILABLE",
            "breadth": np.nan,
            "positive_momentum": np.nan,
            "median_momentum": np.nan,
            "median_trend": np.nan,
        }

    breadth = float(
        (
            valid[
                "trend_ratio"
            ]
            > 0
        ).mean()
    )

    positive_momentum = float(
        (
            valid[
                "ret_12"
            ]
            > 0
        ).mean()
    )

    median_momentum = float(
        valid[
            "ret_12"
        ].median()
    )

    median_trend = float(
        valid[
            "trend_ratio"
        ].median()
    )

    if (
        breadth >= 0.70
        and
        positive_momentum >= 0.70
        and
        median_momentum > 0.10
        and
        median_trend > 0.03
    ):

        regime = "BULL"

    elif (
        breadth < 0.40
        and
        positive_momentum < 0.40
        and
        median_momentum < -0.05
    ):

        regime = "BEAR"

    elif (
        breadth >= 0.50
        and
        positive_momentum >= 0.45
        and
        median_trend > 0
        and
        median_momentum <= 0.10
    ):

        regime = "RECOVERY"

    else:

        regime = "NEUTRAL"

    return {
        "regime": regime,
        "breadth": breadth,
        "positive_momentum":
            positive_momentum,
        "median_momentum":
            median_momentum,
        "median_trend":
            median_trend,
    }


# =============================================================================
# CURRENT TOP 5
# =============================================================================

def get_current_top5(
    strategy_name: str,
    monthly_nav: pd.DataFrame,
    latest_date: pd.Timestamp,
    fund_info: pd.DataFrame,
) -> pd.DataFrame:

    features = calculate_fund_features(
        monthly_nav,
        latest_date,
    )

    if features.empty:

        return pd.DataFrame()

    scored = add_strategy_score(
        features,
        strategy_name,
    )

    if scored.empty:

        return pd.DataFrame()

    top5 = (
        scored
        .head(DISPLAY_RANKS)
        .copy()
        .reset_index(
            drop=True
        )
    )

    top5.insert(
        0,
        "rank",
        np.arange(
            1,
            len(top5) + 1,
        ),
    )

    names = fund_info[
        [
            "code",
            "name",
        ]
    ].copy()

    top5 = top5.merge(
        names,
        on="code",
        how="left",
    )

    top5[
        "calmar"
    ] = np.where(
        (
            top5[
                "ret_12"
            ].notna()
            &
            top5[
                "max_drawdown"
            ].notna()
            &
            (
                top5[
                    "max_drawdown"
                ]
                < 0
            )
        ),
        top5[
            "ret_12"
        ]
        /
        top5[
            "max_drawdown"
        ].abs(),
        np.nan,
    )

    columns = [
        "rank",
        "code",
        "name",
        "strategy_score",
        "current_nav",
        "ret_12",
        "ret_24",
        "ret_36",
        "trend_ratio",
        "sharpe",
        "sortino",
        "calmar",
        "max_drawdown",
        "distance_high",
        "profitable_months",
        "momentum_acceleration",
        "recovery_score",
    ]

    columns = [
        column
        for column in columns
        if column in top5.columns
    ]

    return top5[
        columns
    ]


# =============================================================================
# STRATEGY COMPARISON
# =============================================================================

def percentile_rank(
    series: pd.Series,
    higher_is_better: bool = True,
) -> pd.Series:

    numeric = pd.to_numeric(
        series,
        errors="coerce",
    )

    rank = numeric.rank(
        method="average",
        pct=True,
    )

    if higher_is_better:

        return rank

    return 1.0 - rank


def build_strategy_comparison(
    results: dict[
        str,
        dict[str, Any],
    ],
) -> pd.DataFrame:

    rows = []

    for strategy_name, result in results.items():

        metrics = result[
            "metrics"
        ]

        rows.append(
            {
                "strategy":
                    strategy_name,
                "xirr":
                    metrics[
                        "xirr"
                    ],
                "twr_return":
                    metrics[
                        "twr_return"
                    ],
                "volatility":
                    metrics[
                        "volatility"
                    ],
                "max_drawdown":
                    metrics[
                        "max_drawdown"
                    ],
                "sharpe":
                    metrics[
                        "sharpe"
                    ],
                "sortino":
                    metrics[
                        "sortino"
                    ],
                "calmar":
                    metrics[
                        "calmar"
                    ],
                "contributions":
                    metrics[
                        "contributions"
                    ],
                "sip_count":
                    metrics[
                        "sip_count"
                    ],
                "final_value":
                    metrics[
                        "final_value"
                    ],
            }
        )

    comparison = pd.DataFrame(
        rows
    )

    if comparison.empty:

        return comparison

    # -------------------------------------------------------------------------
    # Historical risk-adjusted composite.
    # -------------------------------------------------------------------------

    component_scores = {}

    component_scores[
        "xirr"
    ] = percentile_rank(
        comparison[
            "xirr"
        ],
        True,
    )

    component_scores[
        "sharpe"
    ] = percentile_rank(
        comparison[
            "sharpe"
        ],
        True,
    )

    component_scores[
        "sortino"
    ] = percentile_rank(
        comparison[
            "sortino"
        ],
        True,
    )

    component_scores[
        "calmar"
    ] = percentile_rank(
        comparison[
            "calmar"
        ],
        True,
    )

    component_scores[
        "max_drawdown"
    ] = percentile_rank(
        comparison[
            "max_drawdown"
        ],
        True,
    )

    weights = {
        "xirr": 0.30,
        "sharpe": 0.20,
        "sortino": 0.20,
        "calmar": 0.15,
        "max_drawdown": 0.15,
    }

    numerator = pd.Series(
        0.0,
        index=comparison.index,
    )

    denominator = pd.Series(
        0.0,
        index=comparison.index,
    )

    for metric, weight in weights.items():

        score = component_scores[
            metric
        ]

        valid = score.notna()

        numerator.loc[valid] += (
            score.loc[valid]
            *
            weight
        )

        denominator.loc[valid] += (
            weight
        )

    comparison[
        "risk_adjusted_composite"
    ] = (
        numerator
        /
        denominator.replace(
            0,
            np.nan,
        )
    )

    return comparison


# =============================================================================
# DESCRIPTIVE STRATEGY SELECTION
# =============================================================================

def choose_strategy_descriptively(
    comparison: pd.DataFrame,
) -> tuple[
    str | None,
    str | None,
]:

    if comparison.empty:

        return None, None

    valid_xirr = comparison[
        comparison[
            "xirr"
        ].notna()
    ]

    valid_risk = comparison[
        comparison[
            "risk_adjusted_composite"
        ].notna()
    ]

    strongest_return = None

    strongest_risk_adjusted = None

    if not valid_xirr.empty:

        strongest_return = str(
            valid_xirr
            .sort_values(
                "xirr",
                ascending=False,
            )
            .iloc[0][
                "strategy"
            ]
        )

    if not valid_risk.empty:

        strongest_risk_adjusted = str(
            valid_risk
            .sort_values(
                "risk_adjusted_composite",
                ascending=False,
            )
            .iloc[0][
                "strategy"
            ]
        )

    return (
        strongest_return,
        strongest_risk_adjusted,
    )


# =============================================================================
# CURRENT FUND METRICS
# =============================================================================

def build_current_fund_metrics(
    monthly_nav: pd.DataFrame,
    latest_date: pd.Timestamp,
    fund_info: pd.DataFrame,
) -> pd.DataFrame:

    features = calculate_fund_features(
        monthly_nav,
        latest_date,
    )

    if features.empty:

        return pd.DataFrame()

    result = features.merge(
        fund_info[
            [
                "code",
                "name",
            ]
        ],
        on="code",
        how="left",
    )

    result = result.sort_values(
        [
            "ret_12",
            "ret_24",
            "ret_36",
        ],
        ascending=[
            False,
            False,
            False,
        ],
        na_position="last",
    ).reset_index(
        drop=True
    )

    return result


# =============================================================================
# SUMMARY
# =============================================================================

def write_summary(
    latest_date: pd.Timestamp,
    monthly_nav: pd.DataFrame,
    universe: pd.DataFrame,
    comparison: pd.DataFrame,
    market_regime: dict[str, Any],
    strongest_return: str | None,
    strongest_risk_adjusted: str | None,
) -> None:

    strategies = {}

    if not comparison.empty:

        for _, row in comparison.iterrows():

            strategy = str(
                row[
                    "strategy"
                ]
            )

            strategies[
                strategy
            ] = {
                "xirr":
                    safe_float(
                        row[
                            "xirr"
                        ]
                    ),
                "twr_return":
                    safe_float(
                        row[
                            "twr_return"
                        ]
                    ),
                "volatility":
                    safe_float(
                        row[
                            "volatility"
                        ]
                    ),
                "max_drawdown":
                    safe_float(
                        row[
                            "max_drawdown"
                        ]
                    ),
                "sharpe":
                    safe_float(
                        row[
                            "sharpe"
                        ]
                    ),
                "sortino":
                    safe_float(
                        row[
                            "sortino"
                        ]
                    ),
                "calmar":
                    safe_float(
                        row[
                            "calmar"
                        ]
                    ),
                "risk_adjusted_composite":
                    safe_float(
                        row[
                            "risk_adjusted_composite"
                        ]
                    ),
                "contributions":
                    safe_float(
                        row[
                            "contributions"
                        ]
                    ),
                "sip_count":
                    int(
                        row[
                            "sip_count"
                        ]
                    ),
                "final_value":
                    safe_float(
                        row[
                            "final_value"
                        ]
                    ),
            }

    summary = {
        "lab":
            "SmallCapSIPLab",

        "generated_at":
            datetime.now().isoformat(),

        "backtest_start":
            BACKTEST_START,

        "backtest_end":
            str(
                latest_date.date()
            ),

        "monthly_sip":
            MONTHLY_SIP,

        "portfolio_size":
            PORTFOLIO_SIZE,

        "min_history_months":
            MIN_HISTORY_MONTHS,

        "universe_size":
            len(universe),

        "monthly_nav_funds":
            len(monthly_nav.columns),

        "historical_methodology": {

            "universe":
                (
                    "Current Direct-Growth Small Cap "
                    "mutual-fund universe discovered "
                    "dynamically from MFAPI"
                ),

            "survivorship_bias":
                True,

            "decision_frequency":
                "Monthly",

            "decision_date":
                "Completed month-end",

            "purchase_nav":
                (
                    "First valid NAV strictly after "
                    "the decision date"
                ),

            "purchase_nav_fallback":
                (
                    "If a ranked candidate has no usable "
                    "future NAV, the next-ranked eligible "
                    "candidate is considered"
                ),

            "monthly_sip":
                MONTHLY_SIP,

            "portfolio_size":
                PORTFOLIO_SIZE,

            "informational_ranks_displayed":
                DISPLAY_RANKS,

            "sip_allocation":
                "100% to Rank 1; Ranks 2-5 informational only",

            "existing_holdings_rebalanced":
                False,

            "new_sip_money":
                "Allocated 100% to current Top 1; Ranks 2-5 informational only",
        },

        "market": {
            "latest_completed_month":
                str(
                    latest_date.date()
                ),
            **market_regime,
        },

        "strongest_return_strategy":
            strongest_return,

        "strongest_risk_adjusted_strategy":
            strongest_risk_adjusted,

        "strategies":
            strategies,
    }

    with SUMMARY_JSON.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            summary,
            file,
            indent=2,
            ensure_ascii=False,
            default=str,
        )


# =============================================================================
# PRINT STRATEGY COMPARISON
# =============================================================================

def print_strategy_comparison(
    comparison: pd.DataFrame,
) -> None:

    print_header(
        "STRATEGY COMPARISON"
    )

    if comparison.empty:

        print(
            "No strategy comparison available."
        )

        return

    for _, row in comparison.iterrows():

        xirr = safe_float(
            row["xirr"]
        )

        twr = safe_float(
            row["twr_return"]
        )

        volatility = safe_float(
            row["volatility"]
        )

        max_dd = safe_float(
            row["max_drawdown"]
        )

        sharpe = safe_float(
            row["sharpe"]
        )

        sortino = safe_float(
            row["sortino"]
        )

        calmar = safe_float(
            row["calmar"]
        )

        risk_score = safe_float(
            row[
                "risk_adjusted_composite"
            ]
        )

        if (
            sharpe is not None
            and
            sortino is not None
            and
            calmar is not None
            and
            risk_score is not None
        ):

            print(
                f"{str(row['strategy']):<22}"
                f" XIRR {pct(xirr):>8}"
                f" | TWR {pct(twr):>8}"
                f" | Vol {pct(volatility):>8}"
                f" | DD {pct(max_dd):>8}"
                f" | Sharpe "
                f"{sharpe:.3f}"
                f" | Sortino "
                f"{sortino:.3f}"
                f" | Calmar "
                f"{calmar:.3f}"
                f" | RiskScore "
                f"{risk_score:.2f}"
            )

        else:

            print(
                f"{str(row['strategy']):<22}"
                f" XIRR {pct(xirr):>8}"
                f" | TWR {pct(twr):>8}"
                f" | Vol {pct(volatility):>8}"
                f" | DD {pct(max_dd):>8}"
            )


# =============================================================================
# PRINT CURRENT TOP 5
# =============================================================================

def print_current_top5(
    strategy_name: str,
    top5: pd.DataFrame,
) -> None:

    print_header(
        f"CURRENT TOP 5 - {strategy_name}"
    )

    if top5.empty:

        print(
            "No current Top 5 available."
        )

        return

    for _, row in top5.iterrows():

        score = safe_float(
            row[
                "strategy_score"
            ]
        )

        print(
            f"{int(row['rank']):>2}. "
            f"{str(row['name']):<60}"
            f" Score "
            f"{score:.4f}"
            f" | 12M "
            f"{pct(row['ret_12'])}"
            f" | 36M "
            f"{pct(row['ret_36'])}"
            f" | Trend "
            f"{pct(row['trend_ratio'])}"
            f" | DD "
            f"{pct(row['max_drawdown'])}"
        )


# =============================================================================
# LATEST COMPLETED MONTH
# =============================================================================

def get_latest_completed_month_end() -> pd.Timestamp:

    today = (
        pd.Timestamp.today()
        .normalize()
    )

    if today.is_month_end:

        return today

    return (
        today
        -
        pd.offsets.MonthEnd(1)
    )


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:

    start_time = time.time()

    ensure_results_dir()

    latest_date = (
        get_latest_completed_month_end()
    )

    print()
    print("=" * 100)
    print(
        "SMALLCAPSIPLAB - HISTORICAL SIP RESEARCH"
    )
    print("=" * 100)

    print(
        f"Backtest period : "
        f"{BACKTEST_START} -> "
        f"{latest_date.date()}"
    )

    print(
        f"Monthly SIP     : "
        f"{fmt_money(MONTHLY_SIP)}"
    )

    print(
        f"Historical SIP portfolio size : "
        f"{PORTFOLIO_SIZE}"
    )

    print(
        f"Informational ranks displayed  : Top {DISPLAY_RANKS}"
    )

    print(
        "Historical SIP allocation      : 100% to Rank 1"
    )

    # =========================================================================
    # STEP 1
    # =========================================================================

    universe = discover_universe()

    if universe.empty:

        raise RuntimeError(
            "Current Small Cap universe is empty."
        )

    # =========================================================================
    # STEP 2
    # =========================================================================

    nav_data = download_nav_history(
        universe,
        latest_date,
    )

    if not nav_data:

        raise RuntimeError(
            "No NAV datasets were downloaded."
        )

    fund_info = universe[
        universe[
            "code"
        ]
        .astype(str)
        .isin(
            list(
                nav_data.keys()
            )
        )
    ].copy()

    if fund_info.empty:

        raise RuntimeError(
            "No downloaded NAV datasets match "
            "the discovered universe."
        )

    # =========================================================================
    # STEP 3
    # =========================================================================

    print_header(
        "STEP 3:"
    )

    monthly_nav = build_monthly_nav(
        nav_data,
        BACKTEST_START,
        latest_date,
    )

    if monthly_nav.empty:

        raise RuntimeError(
            "Monthly NAV dataframe is empty."
        )

    print(
        f"Monthly period: "
        f"{monthly_nav.index.min().date()}"
        f" -> "
        f"{monthly_nav.index.max().date()}"
    )

    history_counts = (
        monthly_nav
        .notna()
        .sum()
    )

    funds_with_min_history = int(
        (
            history_counts
            >=
            MIN_HISTORY_MONTHS
        ).sum()
    )

    strategy_eligible = int(
        (
            history_counts
            >=
            MIN_FEATURE_OBSERVATIONS
        ).sum()
    )

    print(
        f"Funds with >= "
        f"{MIN_HISTORY_MONTHS} months: "
        f"{funds_with_min_history}"
    )

    print(
        f"Strategy-eligible funds with >= "
        f"{MIN_FEATURE_OBSERVATIONS} monthly observations: "
        f"{strategy_eligible}"
    )

    monthly_nav.to_csv(
        MONTHLY_NAV_CSV
    )

    # -------------------------------------------------------------------------
    # 36M return requires current month + 36 months of prior history.
    # Therefore start at index position 36.
    # -------------------------------------------------------------------------

    if len(
        monthly_nav.index
    ) <= MIN_HISTORY_MONTHS:

        raise RuntimeError(
            "Not enough monthly observations "
            "to create historical decision dates."
        )

    decision_dates = (
        monthly_nav.index[
            MIN_HISTORY_MONTHS:
        ]
    )

    decision_dates = decision_dates[
        decision_dates <= latest_date
    ]

    if len(decision_dates) == 0:

        raise RuntimeError(
            "No historical decision dates available."
        )

    print()
    print(
        f"Historical decision dates: "
        f"{decision_dates.min().date()}"
        f" -> "
        f"{decision_dates.max().date()}"
        f" ({len(decision_dates)} months)"
    )

    # =========================================================================
    # STEP 4
    # =========================================================================

    print_header(
        "STEP 4: HISTORICAL STRATEGY RESULTS"
    )

    results = {}

    for strategy_name in STRATEGIES:

        result = run_strategy_backtest(
            strategy_name,
            monthly_nav,
            nav_data,
            fund_info,
            decision_dates,
        )

        results[
            strategy_name
        ] = result

        save_strategy_output(
            result
        )

    # =========================================================================
    # STRATEGY COMPARISON
    # =========================================================================

    comparison = build_strategy_comparison(
        results
    )

    comparison.to_csv(
        STRATEGY_METRICS_CSV,
        index=False,
    )

    print_strategy_comparison(
        comparison
    )

    # =========================================================================
    # STEP 5: CURRENT MARKET
    # =========================================================================

    print_header(
        "STEP 5: CURRENT MARKET"
    )

    latest_features = calculate_fund_features(
        monthly_nav,
        latest_date,
    )

    market_regime = calculate_market_regime(
        latest_features
    )

    print(
        f"Latest completed month: "
        f"{latest_date.strftime('%Y-%m')}"
    )

    print(
        f"Regime: "
        f"{market_regime['regime']}"
    )

    print(
        f"Above 12M MA breadth: "
        f"{pct(market_regime['breadth'])}"
    )

    print(
        f"Positive 12M momentum: "
        f"{pct(market_regime['positive_momentum'])}"
    )

    print(
        f"Median 12M momentum: "
        f"{pct(market_regime['median_momentum'])}"
    )

    print(
        f"Median trend: "
        f"{pct(market_regime['median_trend'])}"
    )

    # =========================================================================
    # STRATEGY DESCRIPTIVE SUMMARY
    # =========================================================================

    (
        strongest_return,
        strongest_risk_adjusted,
    ) = choose_strategy_descriptively(
        comparison
    )

    print()

    print(
        "Highest historical XIRR strategy : "
        f"{strongest_return}"
    )

    print(
        "Highest historical risk-adjusted composite"
        f"                      : "
        f"{strongest_risk_adjusted}"
    )

    # =========================================================================
    # CURRENT FUND METRICS
    # =========================================================================

    fund_metrics = build_current_fund_metrics(
        monthly_nav,
        latest_date,
        fund_info,
    )

    fund_metrics.to_csv(
        FUND_METRICS_CSV,
        index=False,
    )

    # =========================================================================
    # CURRENT TOP 5 FOR SELECTED STRATEGIES
    # =========================================================================

    strategies_to_display = []

    for strategy in [
        strongest_return,
        strongest_risk_adjusted,
    ]:

        if (
            strategy
            and
            strategy not in strategies_to_display
        ):

            strategies_to_display.append(
                strategy
            )

    for strategy_name in strategies_to_display:

        top5 = get_current_top5(
            strategy_name,
            monthly_nav,
            latest_date,
            fund_info,
        )

        top5.to_csv(
            RESULTS_DIR
            /
            f"current_top5_{strategy_name.lower()}.csv",
            index=False,
        )

        print_current_top5(
            strategy_name,
            top5,
        )

    # =========================================================================
    # SUMMARY
    # =========================================================================

    write_summary(
        latest_date,
        monthly_nav,
        universe,
        comparison,
        market_regime,
        strongest_return,
        strongest_risk_adjusted,
    )

    # =========================================================================
    # VALIDATION
    # =========================================================================

    print_header(
        "VALIDATION"
    )

    validation_pass = True

    expected_completed_months = (
        len(decision_dates)
    )

    for strategy_name in STRATEGIES:

        result = results[
            strategy_name
        ]

        decision_count = len(
            result[
                "selection_history"
            ]
        )

        sip_count = int(
            result[
                "metrics"
            ][
                "sip_count"
            ]
        )

        xirr = safe_float(
            result[
                "metrics"
            ][
                "xirr"
            ]
        )

        print(
            f"{strategy_name:<22}"
            f" decisions={decision_count:>3}"
            f" | SIPs={sip_count:>3}"
            f" | XIRR="
            f"{pct(xirr)}"
        )

        # A completed decision always represents exactly one Top-1 SIP.
        # Therefore decision_count and sip_count must always agree.
        if decision_count != sip_count:

            validation_pass = False

        if (
            decision_count
            >
            expected_completed_months
        ):

            validation_pass = False

    if validation_pass:

        print()
        print(
            "PASS: Every completed strategy decision "
            "has exactly one corresponding SIP month."
        )

    else:

        print()
        print(
            "FAIL: At least one strategy has a "
            "decision/SIP mismatch."
        )

    # =========================================================================
    # PURCHASE NAV DIAGNOSTIC
    # =========================================================================

    print()
    print(
        "=" * 100
    )

    print(
        "PURCHASE NAV DIAGNOSTIC"
    )

    print(
        "=" * 100
    )

    for strategy_name in STRATEGIES:

        result = results[
            strategy_name
        ]

        selection_count = len(
            result[
                "selection_history"
            ]
        )

        purchase_df = result[
            "purchase_history"
        ]

        if purchase_df.empty:

            purchase_count = 0

        else:

            purchase_count = (
                purchase_df[
                    "decision_date"
                ]
                .nunique()
            )

        candidate_failures = 0

        skipped_df = result[
            "skipped_dates"
        ]

        if not skipped_df.empty:

            if (
                "month_action"
                in
                skipped_df.columns
            ):

                candidate_failures = int(
                    (
                        skipped_df[
                            "month_action"
                        ]
                        ==
                        "candidate replaced"
                    ).sum()
                )

        print(
            f"{strategy_name:<22}"
            f" completed_months="
            f"{selection_count:>3}"
            f" | purchase_months="
            f"{purchase_count:>3}"
            f" | candidate_NAV_failures="
            f"{candidate_failures:>3}"
        )

    # =========================================================================
    # FINAL
    # =========================================================================

    elapsed = (
        time.time()
        -
        start_time
    )

    print()

    print(
        f"Results saved to: "
        f"{RESULTS_DIR}"
    )

    print()

    print("=" * 100)

    print(
        "SMALLCAPSIPLAB COMPLETE"
    )

    print("=" * 100)

    print(
        f"Runtime: {elapsed:.1f} seconds"
    )


# =============================================================================
# PROGRAM ENTRY
# =============================================================================

if __name__ == "__main__":

    main()