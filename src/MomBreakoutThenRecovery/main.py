"""
Momentum Continuation (MC)
--------------------------

Nifty 500 short-term positional stock ranking engine.

SETUP LOGIC
-----------

A stock qualifies only when ALL of the following occur:

    1. Established bullish trend
    2. A qualifying 20-day breakout occurred
    3. AFTER that breakout, price experienced a controlled
       5%-20% retracement
    4. Price is now recovering from that retracement
    5. Recovery is confirmed by volume

Therefore the sequence is:

    Established Uptrend
            ↓
    20-Day Breakout
            ↓
    Controlled 5%-20% Retracement
            ↓
    Bullish Recovery
            ↓
    Momentum Continuation Setup

BREAKOUT AND RETRACEMENT ARE NOT SEPARATE SETUPS.

The breakout is the first stage of the same continuation
setup. The retracement and subsequent recovery are the
confirmation stage.

IMPORTANT:
    This is a research and decision-support system.
    It does not predict future returns or guarantee profits.

    Stop-loss is an intended exit level, not a guaranteed
    maximum loss. Overnight gaps and slippage can result
    in execution below the intended stop.

DATA SOURCE:
    Yahoo Finance via yfinance

MARKET-DATE HANDLING:
    The program determines the latest market trading date
    represented in the downloaded universe.

    It does NOT require every Nifty 500 stock to have data
    on that date.

    Therefore, if the program is executed on a market holiday,
    Saturday, Sunday, or any other non-trading day, it uses
    the latest available market trading date.

    Example:

        Saturday 2026-08-29
                ↓
        Friday 2026-08-28
                ↓
        Analysis date = 2026-08-28

    Individual stocks that do not have data for the selected
    analysis date are excluded rather than causing the entire
    analysis date to move backwards.
"""

import shutil
from datetime import datetime

import pandas as pd
import numpy as np

from trade_data import (
    refresh_nifty500_universe,
    get_market_data_for_symbols,
)


# =========================================================
# CONFIGURATION
# =========================================================

STRATEGY_NAME = "Momentum Continuation (MC)"

TOP_N = 20

MIN_PRICE = 100

MIN_HISTORY_DAYS = 200

MIN_AVG_TRADED_VALUE_CRORE = 20


# =========================================================
# BREAKOUT CONFIGURATION
# =========================================================

BREAKOUT_LOOKBACK = 20

BREAKOUT_VOLUME_MULTIPLIER = 1.5


# =========================================================
# RETRACEMENT CONFIGURATION
# =========================================================

RETRACEMENT_LOOKBACK = 60

MIN_RETRACEMENT_PERCENT = 5.0

MAX_RETRACEMENT_PERCENT = 20.0

RETRACEMENT_VOLUME_MULTIPLIER = 1.2


# =========================================================
# TREND CONFIGURATION
# =========================================================

SHORT_EMA = 10

FAST_EMA = 20

MEDIUM_EMA = 50

LONG_EMA = 200


# =========================================================
# CANDLE CONFIGURATION
# =========================================================

MIN_CANDLE_BODY_PERCENT = 1.0

CLOSE_POSITION_THRESHOLD = 0.75


# =========================================================
# TRADE PLAN CONFIGURATION
# =========================================================

MIN_RISK_REWARD = 2.0

MAX_HOLDING_DAYS = 60

STOP_ATR_MULTIPLIER = 0.5

MIN_RISK_PERCENT = 2.0

MAX_TARGET_PERCENT = 30.0


# =========================================================
# RANKING METHODOLOGY
# =========================================================

SCORE_WEIGHTS = {

    "MomentumStrength": 20,

    "VolumeConfirmation": 20,

    "TrendStrength": 20,

    "ClosingStrength": 15,

    "PriceStrength": 10,

    "EMA50Position": 5,

    "Liquidity": 5,

    "RecoveryQuality": 5,
}


TOTAL_SCORE_WEIGHT = sum(
    SCORE_WEIGHTS.values()
)


if TOTAL_SCORE_WEIGHT != 100:

    raise ValueError(
        "Ranking weights must total exactly 100."
    )


# =========================================================
# MARKET DATE HANDLING
# =========================================================

def normalize_market_date(index):

    """
    Normalize a pandas DatetimeIndex to timezone-naive
    calendar dates.

    This allows comparison between Yahoo Finance data
    and the local execution date without timezone issues.
    """

    dates = pd.to_datetime(index)

    try:

        if dates.tz is not None:

            dates = dates.tz_localize(None)

    except AttributeError:

        pass

    return dates.normalize()


def get_latest_analysis_date(
    data,
    symbols
):
    """
    Determine the latest actual market date represented
    in the downloaded market data.

    IMPORTANT:

    This function intentionally does NOT calculate the
    intersection of dates across all stocks.

    The previous implementation required every stock to
    have data on the same date. If even one stock was stale
    or missing the latest day's data, the entire analysis
    date moved backwards.

    Example:

        Stock A -> 2026-08-28
        Stock B -> 2026-08-28
        Stock C -> 2026-08-27

    Previous logic:
        Common date = 2026-08-27

    New logic:
        Latest market date = 2026-08-28

    Stock C will simply be excluded later because it does
    not have data for 2026-08-28.

    This ensures that Saturday 2026-08-29 correctly uses
    Friday 2026-08-28 as the analysis date.

    Returns:
        pandas.Timestamp
    """

    latest_dates = []

    required_fields = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    for symbol in symbols:

        try:

            symbol_latest_date = None

            for field in required_fields:

                field_data = data[field]

                if symbol not in field_data.columns:

                    symbol_latest_date = None

                    break

                series = (
                    field_data[symbol]
                    .dropna()
                )

                if series.empty:

                    symbol_latest_date = None

                    break

                dates = normalize_market_date(
                    series.index
                )

                if len(dates) == 0:

                    symbol_latest_date = None

                    break

                field_latest_date = dates.max()

                if symbol_latest_date is None:

                    symbol_latest_date = field_latest_date

                else:

                    symbol_latest_date = min(
                        symbol_latest_date,
                        field_latest_date
                    )

            if symbol_latest_date is not None:

                latest_dates.append(
                    symbol_latest_date
                )

        except Exception:

            continue

    if not latest_dates:

        raise RuntimeError(
            "Unable to determine the latest market date "
            "from the downloaded market data."
        )

    return pd.Timestamp(
        max(latest_dates)
    )


def get_execution_date():

    """
    Return the local calendar date on which the program
    is executed.

    This is used only for reporting whether the selected
    market date is earlier than the execution date.
    """

    return pd.Timestamp(
        datetime.now().date()
    )


# =========================================================
# INDICATORS
# =========================================================

def calculate_indicators(df):

    df = df.copy()

    # -----------------------------------------------------
    # EMAs
    # -----------------------------------------------------

    df["EMA10"] = (
        df["Close"]
        .ewm(
            span=SHORT_EMA,
            adjust=False
        )
        .mean()
    )

    df["EMA20"] = (
        df["Close"]
        .ewm(
            span=FAST_EMA,
            adjust=False
        )
        .mean()
    )

    df["EMA50"] = (
        df["Close"]
        .ewm(
            span=MEDIUM_EMA,
            adjust=False
        )
        .mean()
    )

    df["EMA200"] = (
        df["Close"]
        .ewm(
            span=LONG_EMA,
            adjust=False
        )
        .mean()
    )

    # -----------------------------------------------------
    # Volume averages
    # -----------------------------------------------------

    df["VolumeAvg20"] = (
        df["Volume"]
        .rolling(20)
        .mean()
    )

    df["VolumeAvg50"] = (
        df["Volume"]
        .rolling(50)
        .mean()
    )

    # -----------------------------------------------------
    # Traded value
    # -----------------------------------------------------

    df["TradedValueCrore"] = (
        df["Close"] *
        df["Volume"] /
        10_000_000
    )

    df["AvgTradedValue20Crore"] = (
        df["TradedValueCrore"]
        .rolling(20)
        .mean()
    )

    # -----------------------------------------------------
    # Previous 20-day high
    #
    # Today's candle excluded.
    # -----------------------------------------------------

    df["High20"] = (
        df["High"]
        .shift(1)
        .rolling(BREAKOUT_LOOKBACK)
        .max()
    )

    # -----------------------------------------------------
    # Previous 52-week high
    # -----------------------------------------------------

    df["High52"] = (
        df["High"]
        .shift(1)
        .rolling(252)
        .max()
    )

    # -----------------------------------------------------
    # Previous 20-day low
    # -----------------------------------------------------

    df["Low20"] = (
        df["Low"]
        .shift(1)
        .rolling(20)
        .min()
    )

    # -----------------------------------------------------
    # ATR14
    # -----------------------------------------------------

    previous_close = (
        df["Close"].shift(1)
    )

    true_range_1 = (
        df["High"] -
        df["Low"]
    )

    true_range_2 = (
        df["High"] -
        previous_close
    ).abs()

    true_range_3 = (
        df["Low"] -
        previous_close
    ).abs()

    true_range = pd.concat(
        [
            true_range_1,
            true_range_2,
            true_range_3,
        ],
        axis=1,
    ).max(axis=1)

    df["ATR14"] = (
        true_range
        .rolling(14)
        .mean()
    )

    # -----------------------------------------------------
    # Momentum
    # -----------------------------------------------------

    df["Return20"] = (
        df["Close"] /
        df["Close"].shift(20) -
        1
    ) * 100

    df["Return60"] = (
        df["Close"] /
        df["Close"].shift(60) -
        1
    ) * 100

    # -----------------------------------------------------
    # Candle range
    # -----------------------------------------------------

    df["CandleRange"] = (
        df["High"] -
        df["Low"]
    )

    # -----------------------------------------------------
    # Candle body
    # -----------------------------------------------------

    df["CandleBody"] = (
        df["Close"] -
        df["Open"]
    ).abs()

    df["CandleBodyPercent"] = (
        df["CandleBody"] /
        df["Close"]
    ) * 100

    # -----------------------------------------------------
    # Close position
    # -----------------------------------------------------

    df["ClosePosition"] = np.where(
        df["CandleRange"] > 0,
        (
            df["Close"] -
            df["Low"]
        ) /
        df["CandleRange"],
        0,
    )

    # -----------------------------------------------------
    # Previous day's high
    # -----------------------------------------------------

    df["PreviousDayHigh"] = (
        df["High"].shift(1)
    )

    return df


# =========================================================
# ESTABLISHED UPTREND
# =========================================================

def established_uptrend(row):

    return (
        row["Close"] > row["EMA50"]
        and
        row["EMA20"] > row["EMA50"]
        and
        row["EMA50"] > row["EMA200"]
    )


# =========================================================
# BREAKOUT TEST FOR A HISTORICAL DAY
# =========================================================

def is_breakout_day(df, position):

    if position < BREAKOUT_LOOKBACK:

        return False

    row = df.iloc[position]

    previous_high = (
        df["High"]
        .iloc[
            position - BREAKOUT_LOOKBACK:
            position
        ]
        .max()
    )

    volume_avg = (
        df["Volume"]
        .iloc[
            position - BREAKOUT_LOOKBACK:
            position
        ]
        .mean()
    )

    if pd.isna(previous_high):

        return False

    if pd.isna(volume_avg) or volume_avg <= 0:

        return False

    return (
        row["Close"] > previous_high
        and
        row["Close"] > row["EMA20"]
        and
        row["EMA20"] > row["EMA50"]
        and
        row["Volume"] >= (
            BREAKOUT_VOLUME_MULTIPLIER *
            volume_avg
        )
    )


# =========================================================
# FIND BREAKOUT → RETRACEMENT → RECOVERY SEQUENCE
# =========================================================

def detect_momentum_continuation(df):

    """
    Detect the complete sequence:

        1. Established uptrend
        2. 20-day breakout
        3. Breakout is followed by a 5%-20% retracement
        4. Current day recovers from the retracement
        5. Recovery volume >= 1.2x average
    """

    current_position = len(df) - 1

    current = df.iloc[current_position]

    # -----------------------------------------------------
    # Current day must be in established uptrend
    # -----------------------------------------------------

    if not established_uptrend(current):

        return None

    # -----------------------------------------------------
    # Current recovery conditions
    # -----------------------------------------------------

    if pd.isna(current["PreviousDayHigh"]):

        return None

    if pd.isna(current["VolumeAvg20"]):

        return None

    if current["VolumeAvg20"] <= 0:

        return None

    if (
        current["Close"] <=
        current["PreviousDayHigh"]
    ):

        return None

    current_volume_ratio = (
        current["Volume"] /
        current["VolumeAvg20"]
    )

    if (
        current_volume_ratio <
        RETRACEMENT_VOLUME_MULTIPLIER
    ):

        return None

    # -----------------------------------------------------
    # Search backwards for a qualifying breakout.
    # -----------------------------------------------------

    search_start = max(
        BREAKOUT_LOOKBACK,
        current_position -
        RETRACEMENT_LOOKBACK
    )

    breakout_positions = []

    for position in range(
        search_start,
        current_position
    ):

        if is_breakout_day(
            df,
            position
        ):

            breakout_positions.append(
                position
            )

    if not breakout_positions:

        return None

    # -----------------------------------------------------
    # Test each breakout, starting with the most recent.
    # -----------------------------------------------------

    for breakout_position in reversed(
        breakout_positions
    ):

        breakout_row = (
            df.iloc[breakout_position]
        )

        breakout_close = (
            breakout_row["Close"]
        )

        breakout_high = (
            breakout_row["High"]
        )

        # -------------------------------------------------
        # Need at least one day AFTER breakout.
        # -------------------------------------------------

        if (
            breakout_position + 1
            >= current_position
        ):

            continue

        # -------------------------------------------------
        # Look at price action after breakout.
        # -------------------------------------------------

        post_breakout = df.iloc[
            breakout_position + 1:
            current_position
        ]

        if post_breakout.empty:

            continue

        post_breakout_high = max(
            breakout_high,
            post_breakout["High"].max()
        )

        if pd.isna(post_breakout_high):

            continue

        # -------------------------------------------------
        # Current retracement from post-breakout peak.
        # -------------------------------------------------

        retracement_percent = (
            1 -
            current["Close"] /
            post_breakout_high
        ) * 100

        # -------------------------------------------------
        # Retracement must be 5%-20%.
        # -------------------------------------------------

        if (
            retracement_percent <
            MIN_RETRACEMENT_PERCENT
        ):

            continue

        if (
            retracement_percent >
            MAX_RETRACEMENT_PERCENT
        ):

            continue

        # -------------------------------------------------
        # Verify actual retracement occurred.
        # -------------------------------------------------

        post_breakout_low = (
            post_breakout["Low"].min()
        )

        if pd.isna(post_breakout_low):

            continue

        retracement_from_peak = (
            1 -
            post_breakout_low /
            post_breakout_high
        ) * 100

        if (
            retracement_from_peak <
            MIN_RETRACEMENT_PERCENT
        ):

            continue

        if (
            retracement_from_peak >
            MAX_RETRACEMENT_PERCENT
        ):

            continue

        # -------------------------------------------------
        # Find position of retracement low.
        # -------------------------------------------------

        low_position = (
            post_breakout["Low"]
            .idxmin()
        )

        try:

            low_integer_position = (
                df.index.get_loc(
                    low_position
                )
            )

        except Exception:

            continue

        if (
            low_integer_position >=
            current_position
        ):

            continue

        # -------------------------------------------------
        # Recovery confirmation
        # -------------------------------------------------

        if (
            current["Close"] <=
            current["PreviousDayHigh"]
        ):

            continue

        # -------------------------------------------------
        # Valid sequence found.
        # -------------------------------------------------

        return {

            "BreakoutPosition":
                breakout_position,

            "BreakoutDate":
                df.index[
                    breakout_position
                ],

            "BreakoutPrice":
                breakout_close,

            "BreakoutHigh":
                breakout_high,

            "PostBreakoutHigh":
                post_breakout_high,

            "RetracementLow":
                post_breakout_low,

            "RetracementPercent":
                retracement_percent,

            "CurrentVolumeRatio":
                current_volume_ratio,
        }

    return None


# =========================================================
# MOMENTUM STRENGTH SCORE
# =========================================================

def momentum_strength_points(row):

    score = 0

    return20 = row["Return20"]

    return60 = row["Return60"]

    if pd.isna(return20):

        return20 = 0

    if pd.isna(return60):

        return60 = 0

    if return20 >= 15:

        score += 10

    elif return20 >= 10:

        score += 8

    elif return20 >= 5:

        score += 5

    elif return20 > 0:

        score += 2

    if return60 >= 30:

        score += 10

    elif return60 >= 20:

        score += 8

    elif return60 >= 10:

        score += 5

    elif return60 > 0:

        score += 2

    return min(score, 20)


# =========================================================
# VOLUME CONFIRMATION SCORE
# =========================================================

def volume_confirmation_points(row):

    if (
        pd.isna(row["VolumeAvg20"])
        or
        row["VolumeAvg20"] <= 0
    ):

        return 0

    ratio = (
        row["Volume"] /
        row["VolumeAvg20"]
    )

    if ratio >= 3.0:

        return 20

    if ratio >= 2.5:

        return 17

    if ratio >= 2.0:

        return 15

    if ratio >= 1.5:

        return 10

    if ratio >= 1.2:

        return 5

    return 0


# =========================================================
# TREND STRENGTH SCORE
# =========================================================

def trend_strength_points(row):

    score = 0

    if row["Close"] > row["EMA200"]:

        score += 5

    if row["EMA50"] > row["EMA200"]:

        score += 5

    if row["EMA20"] > row["EMA50"]:

        score += 5

    if row["EMA10"] > row["EMA20"]:

        score += 5

    return score


# =========================================================
# CLOSING STRENGTH SCORE
# =========================================================

def closing_strength_points(row):

    score = 0

    if (
        not pd.isna(
            row["CandleBodyPercent"]
        )
        and
        row["CandleBodyPercent"]
        >= MIN_CANDLE_BODY_PERCENT
    ):

        score += 7

    if (
        not pd.isna(
            row["ClosePosition"]
        )
        and
        row["ClosePosition"]
        >= CLOSE_POSITION_THRESHOLD
    ):

        score += 8

    return min(score, 15)


# =========================================================
# PRICE STRENGTH SCORE
# =========================================================

def price_strength_points(row):

    if (
        pd.isna(row["High52"])
        or
        row["High52"] <= 0
    ):

        return 0

    distance = (
        1 -
        row["Close"] /
        row["High52"]
    ) * 100

    if distance <= 0:

        return 10

    if distance <= 5:

        return 9

    if distance <= 10:

        return 7

    if distance <= 15:

        return 5

    if distance <= 20:

        return 3

    return 0


# =========================================================
# EMA50 POSITION SCORE
# =========================================================

def ema50_position_points(row):

    if row["Close"] > row["EMA50"]:

        return 5

    return 0


# =========================================================
# LIQUIDITY SCORE
# =========================================================

def liquidity_points(row):

    if (
        not pd.isna(
            row["AvgTradedValue20Crore"]
        )
        and
        row["AvgTradedValue20Crore"]
        >= MIN_AVG_TRADED_VALUE_CRORE
    ):

        return 5

    return 0


# =========================================================
# RECOVERY QUALITY SCORE
# =========================================================

def recovery_quality_points(
    retracement_percent
):

    if pd.isna(retracement_percent):

        return 0

    if (
        retracement_percent >= 5
        and
        retracement_percent <= 10
    ):

        return 5

    if (
        retracement_percent > 10
        and
        retracement_percent <= 15
    ):

        return 4

    if (
        retracement_percent > 15
        and
        retracement_percent <= 20
    ):

        return 2

    return 0


# =========================================================
# TOTAL SCORE
# =========================================================

def calculate_total_score(
    momentum,
    volume,
    trend,
    closing_strength,
    price_strength,
    ema50,
    liquidity,
    recovery_quality,
):

    score = (
        momentum +
        volume +
        trend +
        closing_strength +
        price_strength +
        ema50 +
        liquidity +
        recovery_quality
    )

    return min(
        score,
        TOTAL_SCORE_WEIGHT
    )


# =========================================================
# SCORE GRADE
# =========================================================

def score_grade(score):

    if score >= 90:

        return "A+"

    if score >= 80:

        return "A"

    if score >= 70:

        return "B"

    if score >= 60:

        return "C"

    return "D"


# =========================================================
# TRADE PLAN
# =========================================================

def calculate_trade_plan(row):

    entry = row["Close"]

    atr = row["ATR14"]

    swing_low = row["Low20"]

    high52 = row["High52"]

    if pd.isna(entry):

        return None

    if pd.isna(atr) or atr <= 0:

        return None

    if pd.isna(swing_low):

        return None

    # -----------------------------------------------------
    # Stop-loss
    # -----------------------------------------------------

    stop_loss = (
        swing_low -
        atr * STOP_ATR_MULTIPLIER
    )

    if stop_loss >= entry:

        return None

    # -----------------------------------------------------
    # Risk
    # -----------------------------------------------------

    risk_amount = (
        entry -
        stop_loss
    )

    downside_percent = (
        risk_amount /
        entry
    ) * 100

    # -----------------------------------------------------
    # Minimum practical risk
    # -----------------------------------------------------

    if downside_percent < MIN_RISK_PERCENT:

        minimum_stop = (
            entry *
            (
                1 -
                MIN_RISK_PERCENT /
                100
            )
        )

        stop_loss = min(
            stop_loss,
            minimum_stop
        )

        risk_amount = (
            entry -
            stop_loss
        )

        downside_percent = (
            risk_amount /
            entry
        ) * 100

    # -----------------------------------------------------
    # Minimum 2R target
    # -----------------------------------------------------

    minimum_target = (
        entry +
        risk_amount *
        MIN_RISK_REWARD
    )

    # -----------------------------------------------------
    # 52-week high
    # -----------------------------------------------------

    if (
        not pd.isna(high52)
        and
        high52 > entry
    ):

        resistance_target = high52

    else:

        resistance_target = minimum_target

    # -----------------------------------------------------
    # Target
    # -----------------------------------------------------

    target = max(
        minimum_target,
        resistance_target
    )

    maximum_target = (
        entry *
        (
            1 +
            MAX_TARGET_PERCENT /
            100
        )
    )

    target = min(
        target,
        maximum_target
    )

    # -----------------------------------------------------
    # Reward
    # -----------------------------------------------------

    reward_amount = (
        target -
        entry
    )

    if reward_amount <= 0:

        return None

    upside_percent = (
        reward_amount /
        entry
    ) * 100

    # -----------------------------------------------------
    # Risk / reward
    # -----------------------------------------------------

    risk_reward = (
        reward_amount /
        risk_amount
    )

    if risk_reward < MIN_RISK_REWARD:

        return None

    return {

        "Entry": entry,

        "Target": target,

        "StopLoss": stop_loss,

        "UpsidePercent": upside_percent,

        "DownsidePercent": downside_percent,

        "RiskReward": risk_reward,

        "MaxHoldingDays": MAX_HOLDING_DAYS,
    }


# =========================================================
# ANALYZE ONE STOCK
# =========================================================

def analyze_stock(
    symbol,
    data,
    analysis_date
):

    try:

        df = (
            data["Close"][symbol]
            .to_frame("Close")
        )

        df["Open"] = data["Open"][symbol]

        df["High"] = data["High"][symbol]

        df["Low"] = data["Low"][symbol]

        df["Volume"] = data["Volume"][symbol]

        # -------------------------------------------------
        # Normalize dates
        # -------------------------------------------------

        normalized_dates = (
            normalize_market_date(
                df.index
            )
        )

        df.index = normalized_dates

        # -------------------------------------------------
        # Remove duplicate dates
        # -------------------------------------------------

        df = (
            df[
                ~df.index.duplicated(
                    keep="last"
                )
            ]
        )

        # -------------------------------------------------
        # Use ONLY data up to selected analysis date.
        # -------------------------------------------------

        df = df.loc[
            df.index <= analysis_date
        ]

        df = df.dropna(
            subset=[
                "Open",
                "High",
                "Low",
                "Close",
                "Volume",
            ]
        )

        # -------------------------------------------------
        # Stock must have data on selected analysis date.
        # -------------------------------------------------

        if df.empty:

            return None

        if df.index[-1] != analysis_date:

            return None

        if len(df) < MIN_HISTORY_DAYS:

            return None

        # -------------------------------------------------
        # Indicators
        # -------------------------------------------------

        df = calculate_indicators(df)

        row = df.iloc[-1]

        # -------------------------------------------------
        # Basic price filter
        # -------------------------------------------------

        if row["Close"] < MIN_PRICE:

            return None

        # -------------------------------------------------
        # Liquidity filter
        # -------------------------------------------------

        if (
            pd.isna(
                row["AvgTradedValue20Crore"]
            )
            or
            row["AvgTradedValue20Crore"]
            < MIN_AVG_TRADED_VALUE_CRORE
        ):

            return None

        # -------------------------------------------------
        # Momentum Continuation sequence
        # -------------------------------------------------

        sequence = (
            detect_momentum_continuation(df)
        )

        if sequence is None:

            return None

        # -------------------------------------------------
        # Retracement percentage
        # -------------------------------------------------

        retracement_percent = (
            sequence["RetracementPercent"]
        )

        # -------------------------------------------------
        # Individual scores
        # -------------------------------------------------

        momentum = (
            momentum_strength_points(row)
        )

        volume = (
            volume_confirmation_points(row)
        )

        trend = (
            trend_strength_points(row)
        )

        closing_strength = (
            closing_strength_points(row)
        )

        price_strength = (
            price_strength_points(row)
        )

        ema50 = (
            ema50_position_points(row)
        )

        liquidity = (
            liquidity_points(row)
        )

        recovery_quality = (
            recovery_quality_points(
                retracement_percent
            )
        )

        # -------------------------------------------------
        # Total score
        # -------------------------------------------------

        total_score = calculate_total_score(

            momentum=momentum,

            volume=volume,

            trend=trend,

            closing_strength=closing_strength,

            price_strength=price_strength,

            ema50=ema50,

            liquidity=liquidity,

            recovery_quality=recovery_quality,
        )

        grade = score_grade(
            total_score
        )

        # -------------------------------------------------
        # Volume ratio
        # -------------------------------------------------

        if (
            not pd.isna(
                row["VolumeAvg20"]
            )
            and
            row["VolumeAvg20"] > 0
        ):

            volume_ratio = (
                row["Volume"] /
                row["VolumeAvg20"]
            )

        else:

            volume_ratio = 0

        # -------------------------------------------------
        # Distance from 52-week high
        # -------------------------------------------------

        if (
            not pd.isna(
                row["High52"]
            )
            and
            row["High52"] > row["Close"]
        ):

            upside_to_52w = (
                row["High52"] /
                row["Close"] -
                1
            ) * 100

        else:

            upside_to_52w = 0

        # -------------------------------------------------
        # Trade plan
        # -------------------------------------------------

        trade_plan = (
            calculate_trade_plan(row)
        )

        if trade_plan is None:

            return None

        # -------------------------------------------------
        # Result
        # -------------------------------------------------

        return {

            "Symbol":
                symbol.replace(
                    ".NS",
                    ""
                ),

            "Setup":
                STRATEGY_NAME,

            "Close":
                row["Close"],

            "Score":
                total_score,

            "Grade":
                grade,

            "Entry":
                trade_plan["Entry"],

            "Target":
                trade_plan["Target"],

            "StopLoss":
                trade_plan["StopLoss"],

            "UpsidePercent":
                trade_plan["UpsidePercent"],

            "DownsidePercent":
                trade_plan["DownsidePercent"],

            "RiskReward":
                trade_plan["RiskReward"],

            "MaxHoldingDays":
                trade_plan["MaxHoldingDays"],

            "VolumeRatio":
                volume_ratio,

            "RetracementPercent":
                retracement_percent,

            "UpsideTo52WHigh":
                upside_to_52w,

            "Momentum":
                momentum,

            "Trend":
                trend,

            "Volume":
                volume,

            "ClosingStrength":
                closing_strength,

            "PriceStrength":
                price_strength,

            "EMA50Score":
                ema50,

            "LiquidityScore":
                liquidity,

            "RecoveryQuality":
                recovery_quality,

            "Return20":
                row["Return20"],

            "Return60":
                row["Return60"],

            "AvgTradedValue20Cr":
                row["AvgTradedValue20Crore"],

            "BreakoutDate":
                sequence["BreakoutDate"],

            "BreakoutPrice":
                sequence["BreakoutPrice"],

            "BreakoutHigh":
                sequence["BreakoutHigh"],

            "RetracementLow":
                sequence["RetracementLow"],
        }

    except Exception:

        return None


# =========================================================
# BUILD RANKING
# =========================================================

def build_ranking(
    symbols,
    data,
    analysis_date
):

    results = []

    print()
    print("=" * 70)
    print("ANALYZING NIFTY 500")
    print(
        f"Analysis date: "
        f"{analysis_date.strftime('%Y-%m-%d')}"
    )
    print("=" * 70)

    for i, symbol in enumerate(
        symbols,
        start=1
    ):

        print(
            f"\rAnalyzing "
            f"{i}/{len(symbols)} : "
            f"{symbol}",
            end=""
        )

        result = analyze_stock(
            symbol,
            data,
            analysis_date
        )

        if result is not None:

            results.append(result)

    print()

    if not results:

        return pd.DataFrame()

    ranking = pd.DataFrame(
        results
    )

    # -----------------------------------------------------
    # Ranking priority
    # -----------------------------------------------------

    ranking = ranking.sort_values(
        by=[
            "Score",
            "RiskReward",
            "VolumeRatio",
        ],
        ascending=[
            False,
            False,
            False,
        ],
    )

    ranking = ranking.reset_index(
        drop=True
    )

    ranking.insert(
        0,
        "Rank",
        ranking.index + 1
    )

    return ranking


# =========================================================
# TERMINAL WIDTH
# =========================================================

def get_terminal_width():

    try:

        width = shutil.get_terminal_size(
            fallback=(160, 40)
        ).columns

        return max(
            width,
            100
        )

    except Exception:

        return 160


# =========================================================
# FORMAT OUTPUT TABLE
# =========================================================

def format_output_table(df):

    df = df.copy()

    two_decimal_columns = [

        "Close",
        "Entry",
        "Target",
        "StopLoss",
        "UpsidePercent",
        "DownsidePercent",
        "RiskReward",
        "VolumeRatio",
        "AvgTradedValue20Cr",
        "BreakoutPrice",
        "BreakoutHigh",
        "RetracementLow",
    ]

    one_decimal_columns = [

        "RetracementPercent",
        "UpsideTo52WHigh",
        "Return20",
        "Return60",
    ]

    for column in two_decimal_columns:

        if column in df.columns:

            df[column] = (
                df[column]
                .round(2)
            )

    for column in one_decimal_columns:

        if column in df.columns:

            df[column] = (
                df[column]
                .round(1)
            )

    df = df.rename(
        columns={

            "UpsidePercent":
                "Upside%",

            "DownsidePercent":
                "Downside%",

            "RetracementPercent":
                "Retrace%",

            "UpsideTo52WHigh":
                "52W Upside%",

            "RiskReward":
                "R:R",

            "MaxHoldingDays":
                "MaxDays",

            "VolumeRatio":
                "VolRatio",

            "ClosingStrength":
                "CloseStr",

            "PriceStrength":
                "PriceStr",

            "RecoveryQuality":
                "RecoveryQ",

            "AvgTradedValue20Cr":
                "AvgValueCr",

            "BreakoutPrice":
                "BOPrice",

            "BreakoutHigh":
                "BOHigh",

            "RetracementLow":
                "RetraceLow",
        }
    )

    for column in [
        "Upside%",
        "Downside%",
    ]:

        if column in df.columns:

            df[column] = (
                df[column]
                .map(
                    lambda x:
                    (
                        f"{x:.2f}%"
                        if pd.notna(x)
                        else "-"
                    )
                )
            )

    primary_columns = [

        "Rank",
        "Symbol",
        "Score",
        "Grade",
        "Close",
        "Entry",
        "Target",
        "Upside%",
        "StopLoss",
        "Downside%",
        "R:R",
    ]

    secondary_columns = [

        "MaxDays",
        "VolRatio",
        "Retrace%",
        "52W Upside%",
        "Momentum",
        "Trend",
        "Volume",
        "CloseStr",
        "PriceStr",
        "RecoveryQ",
        "EMA50Score",
        "LiquidityScore",
        "Return20",
        "Return60",
        "AvgValueCr",
        "BreakoutDate",
        "BOPrice",
        "BOHigh",
        "RetraceLow",
    ]

    primary_columns = [
        col
        for col in primary_columns
        if col in df.columns
    ]

    secondary_columns = [
        col
        for col in secondary_columns
        if (
            col in df.columns
            and col not in primary_columns
        )
    ]

    identity_columns = [

        col
        for col in [
            "Rank",
            "Symbol",
        ]
        if col in df.columns
    ]

    terminal_width = (
        get_terminal_width()
    )

    available_width = (
        terminal_width - 2
    )

    def table_width(columns):

        temp = df[columns].copy()

        widths = {}

        for column in columns:

            values = (
                temp[column]
                .astype(str)
            )

            max_value_width = (
                values.map(len).max()
                if len(values) > 0
                else 0
            )

            widths[column] = max(
                len(str(column)),
                max_value_width
            )

        return (
            sum(widths.values())
            +
            len(columns) - 1
        )

    groups = []

    if (
        primary_columns
        and
        table_width(primary_columns)
        <= available_width
    ):

        groups.append(
            primary_columns.copy()
        )

        remaining_columns = (
            secondary_columns.copy()
        )

    else:

        remaining_columns = (
            primary_columns +
            secondary_columns
        )

        remaining_columns = [
            col
            for col in remaining_columns
            if col not in identity_columns
        ]

        current_group = (
            identity_columns.copy()
        )

        for column in remaining_columns:

            test_group = (
                current_group +
                [column]
            )

            if (
                len(current_group)
                > len(identity_columns)
                and
                table_width(test_group)
                > available_width
            ):

                groups.append(
                    current_group
                )

                current_group = (
                    identity_columns.copy()
                )

                current_group.append(
                    column
                )

            else:

                current_group = test_group

        if current_group:

            groups.append(
                current_group
            )

        return df, groups

    current_group = (
        identity_columns.copy()
    )

    for column in remaining_columns:

        test_group = (
            current_group +
            [column]
        )

        if (
            len(current_group)
            > len(identity_columns)
            and
            table_width(test_group)
            > available_width
        ):

            groups.append(
                current_group
            )

            current_group = (
                identity_columns.copy()
            )

            current_group.append(
                column
            )

        else:

            current_group = test_group

    if (
        len(current_group)
        > len(identity_columns)
    ):

        groups.append(
            current_group
        )

    return df, groups


# =========================================================
# PRINT TABLE SECTION
# =========================================================

def print_table_section(
    df,
    columns,
    section_number,
    total_sections
):

    print()

    if total_sections > 1:

        print(
            f"TABLE {section_number}/{total_sections}"
        )

    section = (
        df[columns]
        .copy()
    )

    for column in section.columns:

        if column in [

            "Close",
            "Entry",
            "Target",
            "StopLoss",
            "R:R",
            "VolRatio",
            "AvgValueCr",
            "BOPrice",
            "BOHigh",
            "RetraceLow",

        ]:

            section[column] = (
                section[column]
                .map(
                    lambda x:
                    (
                        f"{x:.2f}"
                        if pd.notna(x)
                        else "-"
                    )
                )
            )

        elif column in [

            "Retrace%",
            "52W Upside%",
            "Return20",
            "Return60",

        ]:

            section[column] = (
                section[column]
                .map(
                    lambda x:
                    (
                        f"{x:.1f}"
                        if pd.notna(x)
                        else "-"
                    )
                )
            )

        elif column in [

            "Upside%",
            "Downside%",

        ]:

            section[column] = (
                section[column]
                .astype(str)
            )

        elif column == "Score":

            section[column] = (
                section[column]
                .map(
                    lambda x:
                    (
                        str(int(x))
                        if pd.notna(x)
                        else "-"
                    )
                )
            )

        elif column in [

            "Rank",
            "MaxDays",
            "Momentum",
            "Trend",
            "Volume",
            "CloseStr",
            "PriceStr",
            "RecoveryQ",
            "EMA50Score",
            "LiquidityScore",

        ]:

            section[column] = (
                section[column]
                .map(
                    lambda x:
                    (
                        str(int(x))
                        if pd.notna(x)
                        else "-"
                    )
                )
            )

        else:

            section[column] = (
                section[column]
                .astype(str)
            )

    widths = {}

    for column in section.columns:

        max_value_width = (
            section[column]
            .astype(str)
            .map(len)
            .max()
        )

        widths[column] = max(
            len(str(column)),
            max_value_width
        )

    header = " ".join(
        str(column).ljust(
            widths[column]
        )
        for column in section.columns
    )

    separator = " ".join(
        "-" * widths[column]
        for column in section.columns
    )

    print(header)

    print(separator)

    for _, row in section.iterrows():

        line = " ".join(
            str(row[column]).ljust(
                widths[column]
            )
            for column in section.columns
        )

        print(line)


# =========================================================
# PRINT RANKING METHODOLOGY
# =========================================================

def print_ranking_methodology():

    print()

    print("=" * 100)

    print("RANKING METHODOLOGY")

    print("=" * 100)

    print()

    print(
        "The Momentum Continuation score is a weighted "
        "setup-quality score with a maximum of 100 points."
    )

    print()

    print(
        f"{'Component':<28}"
        f"{'Weight':>10}"
        f"{'Maximum':>12}"
        f"{'What it measures'}"
    )

    print("-" * 100)

    descriptions = {

        "MomentumStrength":
            "20-day and 60-day price momentum",

        "VolumeConfirmation":
            "Current volume versus 20-day average",

        "TrendStrength":
            "EMA10 / EMA20 / EMA50 / EMA200 alignment",

        "ClosingStrength":
            "Candle body + close near daily high",

        "PriceStrength":
            "Proximity to previous 52-week high",

        "EMA50Position":
            "Price above 50 EMA",

        "Liquidity":
            "20-day average traded value",

        "RecoveryQuality":
            "Controlled post-breakout retracement",
    }

    for component, weight in SCORE_WEIGHTS.items():

        print(
            f"{component:<28}"
            f"{weight:>10}"
            f"{weight:>12}"
            f"  {descriptions[component]}"
        )

    print("-" * 100)

    print(
        f"{'TOTAL':<28}"
        f"{TOTAL_SCORE_WEIGHT:>10}"
        f"{TOTAL_SCORE_WEIGHT:>12}"
    )

    print()

    print("SETUP LOGIC")

    print("-" * 100)

    print(
        "Momentum Continuation = Established Uptrend"
    )

    print(
        "                       AND"
    )

    print(
        "                       20-Day Breakout"
    )

    print(
        "                       followed by"
    )

    print(
        "                       Controlled 5%-20% Retracement"
    )

    print(
        "                       followed by"
    )

    print(
        "                       Bullish Recovery"
    )

    print()

    print(
        "The sequence is mandatory."
    )

    print(
        "A retracement recovery without a preceding "
        "qualifying breakout does NOT qualify."
    )

    print()

    print(
        "Ranking priority:"
    )

    print(
        "1. Higher Momentum Continuation Score"
    )

    print(
        "2. Higher Risk/Reward"
    )

    print(
        "3. Higher Volume Ratio"
    )

    print()

    print("Score interpretation:")

    print(
        "90-100  = A+  Exceptional setup quality"
    )

    print(
        "80-89   = A   Very strong setup"
    )

    print(
        "70-79   = B   Good setup"
    )

    print(
        "60-69   = C   Moderate setup"
    )

    print(
        "<60     = D   Weak setup"
    )

    print()

    print(
        "IMPORTANT:"
    )

    print(
        "The score is NOT a probability of profit."
    )

    print(
        "It is NOT an expected return."
    )

    print(
        "It is a relative ranking score."
    )

    print("=" * 100)


# =========================================================
# PRINT RULES
# =========================================================

def print_rules():

    print()

    print("=" * 100)

    print("RULES FOLLOWED")

    print("-" * 100)

    print(
        "1. Universe: Current Nifty 500 constituents."
    )

    print(
        f"2. Price filter: Close >= ₹{MIN_PRICE}."
    )

    print(
        f"3. Liquidity filter: 20-day average traded "
        f"value >= ₹{MIN_AVG_TRADED_VALUE_CRORE} crore."
    )

    print(
        "4. SINGLE SETUP: Momentum Continuation."
    )

    print(
        "5. Established uptrend: Close > EMA50."
    )

    print(
        "6. Trend alignment: EMA20 > EMA50 > EMA200."
    )

    print(
        f"7. First stage: Close breaks above the previous "
        f"{BREAKOUT_LOOKBACK}-day high."
    )

    print(
        f"8. Breakout volume: >= "
        f"{BREAKOUT_VOLUME_MULTIPLIER}x "
        f"20-day average volume."
    )

    print(
        f"9. After breakout: price must experience a "
        f"controlled {MIN_RETRACEMENT_PERCENT}%-"
        f"{MAX_RETRACEMENT_PERCENT}% retracement."
    )

    print(
        "10. Retracement must occur AFTER the breakout."
    )

    print(
        "11. Current recovery: Close > previous day's high."
    )

    print(
        f"12. Recovery volume: >= "
        f"{RETRACEMENT_VOLUME_MULTIPLIER}x "
        f"20-day average volume."
    )

    print(
        "13. Entry: Latest available closing price "
        "on the selected market trading date."
    )

    print(
        "14. Stop: Previous 20-day swing low "
        f"- {STOP_ATR_MULTIPLIER} x ATR14."
    )

    print(
        f"15. Target: Greater of 2R or previous "
        f"52-week high, capped at "
        f"{MAX_TARGET_PERCENT}%."
    )

    print(
        f"16. Minimum risk/reward: "
        f"{MIN_RISK_REWARD}:1."
    )

    print(
        f"17. Maximum holding period: "
        f"{MAX_HOLDING_DAYS} trading days."
    )

    print(
        "18. Market holiday/weekend handling: "
        "latest available market trading date is used."
    )

    print(
        "19. Stocks without data on the selected analysis "
        "date are excluded individually."
    )

    print("=" * 100)


# =========================================================
# PRINT COLUMN DESCRIPTIONS
# =========================================================

def print_column_descriptions():

    print()

    print("=" * 100)

    print("COLUMN DESCRIPTIONS")

    print("-" * 100)

    column_descriptions = {

        "Rank":
            "Ranking position.",

        "Symbol":
            "NSE stock symbol.",

        "Score":
            "Weighted Momentum Continuation score out of 100.",

        "Grade":
            "Score classification.",

        "Close":
            "Latest available closing price on the analysis date.",

        "Entry":
            "Proposed entry price, equal to latest close.",

        "Target":
            "Calculated target using 2R or previous 52-week high.",

        "StopLoss":
            "20-day swing low minus 0.5 ATR14.",

        "Upside%":
            "Percentage gain from Entry to Target.",

        "Downside%":
            "Percentage loss from Entry to StopLoss.",

        "R:R":
            "Reward-to-risk ratio.",

        "MaxDays":
            "Maximum intended holding period.",

        "VolRatio":
            "Current volume / 20-day average volume.",

        "Retrace%":
            "Current retracement from post-breakout peak.",

        "52W Upside%":
            "Distance from current price to previous 52-week high.",

        "Momentum":
            "Momentum score, maximum 20.",

        "Trend":
            "Trend score, maximum 20.",

        "Volume":
            "Volume confirmation score, maximum 20.",

        "CloseStr":
            "Closing-strength score, maximum 15.",

        "PriceStr":
            "Price-strength score, maximum 10.",

        "RecoveryQ":
            "Post-breakout retracement/recovery quality, maximum 5.",

        "EMA50Score":
            "Price-above-EMA50 score, maximum 5.",

        "LiquidityScore":
            "Liquidity score, maximum 5.",

        "Return20":
            "Approximate 20-trading-day return.",

        "Return60":
            "Approximate 60-trading-day return.",

        "AvgValueCr":
            "20-day average daily traded value.",

        "BreakoutDate":
            "Date of qualifying 20-day breakout.",

        "BOPrice":
            "Closing price on breakout day.",

        "BOHigh":
            "High on breakout day.",

        "RetraceLow":
            "Lowest price during post-breakout retracement.",
    }

    for column, description in (
        column_descriptions.items()
    ):

        print(
            f"{column:<18} : {description}"
        )

    print()

    print("=" * 100)

    print(
        "IMPORTANT: Score is a ranking metric, "
        "not a forecast."
    )

    print(
        "IMPORTANT: Upside% is a calculated target distance, "
        "not an expected return."
    )

    print(
        "IMPORTANT: StopLoss is an intended exit level. "
        "Gaps and slippage can produce a larger loss."
    )

    print("=" * 100)


# =========================================================
# PRINT FINAL STATUS
#
# THIS IS INTENTIONALLY THE LAST SECTION.
# =========================================================

def print_final_status(
    analysis_date,
    execution_date,
    ranking
):

    print()

    print("=" * 100)

    print(
        f"Execution date : "
        f"{execution_date.strftime('%Y-%m-%d')}"
    )

    print(
        f"Analysis date  : "
        f"{analysis_date.strftime('%Y-%m-%d')}"
    )

    if analysis_date < execution_date:

        print(
            "Market status  : Market is not trading today. "
            "Using latest available trading day."
        )

    else:

        print(
            "Market status  : Using latest available trading day."
        )

    if ranking.empty:

        print()

        print(
            "NO QUALIFYING CANDIDATES FOUND."
        )

    print("=" * 100)


# =========================================================
# DISPLAY RESULTS
# =========================================================

def display_results(
    ranking,
    analysis_date,
    execution_date
):

    print()

    print("=" * 100)

    print("MOMENTUM CONTINUATION (MC)")

    print("NIFTY 500 SHORT-TERM POSITIONAL STOCK RANKING")

    print("=" * 100)

    # -----------------------------------------------------
    # IMPORTANT:
    #
    # The execution date / analysis date / market status
    # block is intentionally NOT printed here.
    #
    # It is printed LAST by print_final_status().
    # -----------------------------------------------------

    if ranking.empty:

        # -------------------------------------------------
        # Even when there are no candidates, print the
        # complete methodology before the final status.
        # -------------------------------------------------

        print_ranking_methodology()

        print_rules()

        print_column_descriptions()

        # -------------------------------------------------
        # FINAL STATUS — MUST BE LAST
        # -------------------------------------------------

        print_final_status(
            analysis_date,
            execution_date,
            ranking
        )

        return

    display = (
        ranking
        .head(TOP_N)
        .copy()
    )

    # -----------------------------------------------------
    # Explanatory information
    # -----------------------------------------------------

    print()

    print(
        f"Showing top {len(display)} candidates."
    )

    print(
        f"Ranking score maximum: "
        f"{TOTAL_SCORE_WEIGHT}/100"
    )

    print()

    print(
        "The candidates shown below have passed the complete"
    )

    print(
        "sequence:"
    )

    print()

    print(
        "Established Uptrend"
    )

    print(
        "       ↓"
    )

    print(
        "20-Day Breakout"
    )

    print(
        "       ↓"
    )

    print(
        "Controlled 5%-20% Retracement"
    )

    print(
        "       ↓"
    )

    print(
        "Bullish Recovery"
    )

    print()

    # -----------------------------------------------------
    # Ranking methodology
    # -----------------------------------------------------

    print_ranking_methodology()

    # -----------------------------------------------------
    # Rules
    # -----------------------------------------------------

    print_rules()

    # -----------------------------------------------------
    # Column descriptions
    # -----------------------------------------------------

    print_column_descriptions()

    # -----------------------------------------------------
    # Prepare final table
    # -----------------------------------------------------

    display, groups = (
        format_output_table(
            display
        )
    )

    # =====================================================
    # ANALYSIS DATES
    # =====================================================

    print()

    print("=" * 100)

    print("ANALYSIS DATES")

    print("-" * 100)

    print(
        f"{'Execution Date':<25}: "
        f"{execution_date.strftime('%d-%b-%Y')}"
    )

    print(
        f"{'Latest Trading Date':<25}: "
        f"{analysis_date.strftime('%d-%b-%Y')}"
    )

    print(
        f"{'Analysis Date':<25}: "
        f"{analysis_date.strftime('%d-%b-%Y')}"
    )

    print("=" * 100)

    # =====================================================
    # FINAL OUTPUT TABLES
    # =====================================================

    print()

    print("=" * 100)

    print("FINAL RANKED CANDIDATES")

    print("=" * 100)

    total_sections = len(groups)

    for i, columns in enumerate(
        groups,
        start=1
    ):

        print_table_section(
            display,
            columns,
            i,
            total_sections
        )

    # -----------------------------------------------------
    # FINAL STATUS
    #
    # This is intentionally the LAST thing printed.
    # -----------------------------------------------------

    print_final_status(
        analysis_date,
        execution_date,
        ranking
    )


# =========================================================
# MAIN
# =========================================================

def main():

    print()

    print("=" * 80)

    print(
        "MOMENTUM CONTINUATION (MC)"
    )

    print(
        "NIFTY 500 SHORT-TERM POSITIONAL STOCK RANKING"
    )

    print("=" * 80)

    # -----------------------------------------------------
    # STEP 1 — Universe
    # -----------------------------------------------------

    print()

    print(
        "STEP 1 — Refreshing Nifty 500 universe..."
    )

    symbols = (
        refresh_nifty500_universe()
    )

    if not symbols:

        raise RuntimeError(
            "Nifty 500 universe is empty."
        )

    print(
        f"Universe ready: "
        f"{len(symbols)} symbols"
    )

    # -----------------------------------------------------
    # STEP 2 — Market data
    # -----------------------------------------------------

    print()

    print(
        "STEP 2 — Downloading latest "
        "1-year daily market data..."
    )

    data, valid_symbols = (
        get_market_data_for_symbols(
            symbols
        )
    )

    if not valid_symbols:

        raise RuntimeError(
            "No valid market data was returned."
        )

    print(
        f"Market data available for "
        f"{len(valid_symbols)} stocks."
    )

    # -----------------------------------------------------
    # STEP 2A — Determine latest market trading date
    # -----------------------------------------------------

    print()

    print(
        "STEP 2A — Determining latest market "
        "trading date..."
    )

    analysis_date = (
        get_latest_analysis_date(
            data,
            valid_symbols
        )
    )

    execution_date = (
        get_execution_date()
    )

    print(
        f"Latest market trading date: "
        f"{analysis_date.strftime('%Y-%m-%d')}"
    )

    # -----------------------------------------------------
    # Market-date explanation
    #
    # This is only an execution-progress message.
    # The formal status block is printed LAST.
    # -----------------------------------------------------

    if analysis_date < execution_date:

        print(
            "Today is not represented by the downloaded "
            "market data. Using the latest available "
            "trading day."
        )

    else:

        print(
            "Execution date has market data. "
            "Using today's trading data."
        )

    # -----------------------------------------------------
    # STEP 3 — Analysis
    # -----------------------------------------------------

    print()

    print(
        "STEP 3 — Detecting Momentum Continuation "
        "sequences and calculating weighted scores..."
    )

    ranking = build_ranking(
        valid_symbols,
        data,
        analysis_date
    )

    # -----------------------------------------------------
    # STEP 4 — Display
    # -----------------------------------------------------

    display_results(
        ranking,
        analysis_date,
        execution_date
    )


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":

    main()