"""
Momentum Continuation
---------------------

Nifty 500 short-term positional stock ranking engine.

CORE STRATEGY:

    MOMENTUM CONTINUATION =
        ESTABLISHED UPTREND
        AND
        (
            20-DAY BREAKOUT
            OR
            CONTROLLED RETRACEMENT RECOVERY
        )

The strategy looks for stocks already in an established bullish
trend and then identifies either:

    1. A confirmed 20-day price breakout with volume confirmation

OR

    2. A controlled retracement within that established uptrend
       followed by a recovery signal.

Every run:

    1. Refresh current Nifty 500 universe.
    2. Download latest daily OHLCV data.
    3. Calculate technical indicators.
    4. Establish bullish trend.
    5. Detect 20-day breakout.
    6. Detect controlled retracement recovery.
    7. Calculate weighted setup quality score.
    8. Calculate Entry / StopLoss / Target.
    9. Rank strongest candidates.
   10. Display methodology and rules.
   11. PRINT FINAL QUALIFYING CANDIDATE TABLES LAST.

IMPORTANT:

    This is a research and decision-support system.
    It does not predict future returns or guarantee profits.

DATA SOURCE:

    Yahoo Finance via yfinance
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

STRATEGY_NAME = "Momentum Continuation"

TOP_N = 20

MIN_PRICE = 100

MIN_HISTORY_DAYS = 200

MIN_AVG_TRADED_VALUE_CRORE = 20


# =========================================================
# BREAKOUT CONFIGURATION
# =========================================================

BREAKOUT_LOOKBACK = 20

BREAKOUT_VOLUME_MULTIPLIER = 1.5

STRONG_VOLUME_MULTIPLIER = 2.0

MIN_BREAKOUT_BODY_PERCENT = 1.0

CLOSE_POSITION_THRESHOLD = 0.75


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
#
# TOTAL SCORE = 100
#
#   Breakout Strength       = 25
#   Volume Confirmation     = 20
#   Trend Strength          = 15
#   Closing Strength        = 10
#   Momentum                = 10
#   Retracement Quality     = 10
#   EMA50 Position          = 5
#   Liquidity               = 5
#
# TOTAL                    = 100
# =========================================================

SCORE_WEIGHTS = {

    "Breakout": 25,

    "Volume": 20,

    "Trend": 15,

    "ClosingStrength": 10,

    "Momentum": 10,

    "RetracementQuality": 10,

    "EMA50Score": 5,

    "LiquidityScore": 5,
}


TOTAL_SCORE_WEIGHT = sum(
    SCORE_WEIGHTS.values()
)


if TOTAL_SCORE_WEIGHT != 100:

    raise ValueError(
        "Ranking weights must total exactly 100."
    )


# =========================================================
# DATE HELPERS
# =========================================================

def format_date(value):
    """
    Convert a date-like value into DD-MMM-YYYY format.

    Examples:

        2026-08-28 -> 28-Aug-2026
        Timestamp -> 28-Aug-2026
    """

    if value is None:
        return "-"

    try:

        timestamp = pd.to_datetime(value)

        if pd.isna(timestamp):
            return "-"

        return timestamp.strftime(
            "%d-%b-%Y"
        )

    except Exception:

        return str(value)


# =========================================================
# INDICATORS
# =========================================================

def calculate_indicators(df):
    """
    Calculate all technical indicators required by the strategy.
    """

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
        df["Close"]
        *
        df["Volume"]
        /
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
    # shift(1) excludes today's candle.
    # -----------------------------------------------------

    df["High20"] = (
        df["High"]
        .shift(1)
        .rolling(BREAKOUT_LOOKBACK)
        .max()
    )

    # -----------------------------------------------------
    # Previous 60-day high
    # -----------------------------------------------------

    df["High60"] = (
        df["High"]
        .shift(1)
        .rolling(60)
        .max()
    )

    # -----------------------------------------------------
    # Previous swing lows
    # -----------------------------------------------------

    df["Low20"] = (
        df["Low"]
        .shift(1)
        .rolling(20)
        .min()
    )

    df["Low10"] = (
        df["Low"]
        .shift(1)
        .rolling(10)
        .min()
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
    # ATR14
    # -----------------------------------------------------

    previous_close = (
        df["Close"]
        .shift(1)
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
    # Returns
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
    # Candle measurements
    # -----------------------------------------------------

    df["CandleRange"] = (
        df["High"] -
        df["Low"]
    )

    df["CandleBody"] = (
        df["Close"] -
        df["Open"]
    ).abs()

    df["CandleBodyPercent"] = np.where(
        df["Close"] > 0,
        (
            df["CandleBody"] /
            df["Close"]
        ) * 100,
        np.nan,
    )

    # -----------------------------------------------------
    # Closing position
    #
    # 1.00 = close at high
    # 0.75 = upper 25%
    # 0.50 = middle
    # 0.00 = close at low
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
    # Recent swing high
    # -----------------------------------------------------

    df["RecentSwingHigh"] = (
        df["High"]
        .shift(1)
        .rolling(RETRACEMENT_LOOKBACK)
        .max()
    )

    # -----------------------------------------------------
    # Retracement from recent swing high
    # -----------------------------------------------------

    df["RetracementPercent"] = (
        1 -
        df["Close"] /
        df["RecentSwingHigh"]
    ) * 100

    # -----------------------------------------------------
    # Previous day high
    # -----------------------------------------------------

    df["PreviousDayHigh"] = (
        df["High"]
        .shift(1)
    )

    # -----------------------------------------------------
    # Previous swing low
    # -----------------------------------------------------

    df["PreviousSwingLow"] = (
        df["Low"]
        .shift(1)
        .rolling(20)
        .min()
    )

    return df


# =========================================================
# ESTABLISHED UPTREND
# =========================================================

def established_uptrend(row):
    """
    Core trend condition.

    Momentum Continuation requires:

        Close > EMA50
        EMA20 > EMA50
        EMA50 > EMA200

    Basic structure:

        Price
          >
        EMA20
          >
        EMA50
          >
        EMA200

    Close > EMA20 is intentionally NOT required here because
    a controlled retracement can temporarily bring price below
    EMA20 while remaining above EMA50.

    For a breakout, Close > EMA20 is additionally required.
    """

    required_columns = [
        "Close",
        "EMA20",
        "EMA50",
        "EMA200",
    ]

    if any(
        pd.isna(row[column])
        for column in required_columns
    ):
        return False

    return (
        row["Close"] > row["EMA50"]
        and
        row["EMA20"] > row["EMA50"]
        and
        row["EMA50"] > row["EMA200"]
    )


# =========================================================
# 20-DAY BREAKOUT DETECTION
# =========================================================

def detect_breakout(row):
    """
    Detect a confirmed 20-day bullish breakout.

    Conditions:

        Established uptrend
        Close > previous 20-day high
        Close > EMA20
        Volume >= 1.5 x 20-day average
    """

    required_columns = [
        "High20",
        "VolumeAvg20",
        "Close",
        "EMA20",
        "EMA50",
        "EMA200",
    ]

    if any(
        pd.isna(row[column])
        for column in required_columns
    ):
        return False

    if row["VolumeAvg20"] <= 0:
        return False

    return (
        established_uptrend(row)
        and
        row["Close"] > row["High20"]
        and
        row["Close"] > row["EMA20"]
        and
        row["Volume"] >= (
            BREAKOUT_VOLUME_MULTIPLIER *
            row["VolumeAvg20"]
        )
    )


# =========================================================
# CONTROLLED RETRACEMENT RECOVERY
# =========================================================

def detect_retracement(row):
    """
    Detect a controlled retracement followed by recovery.

    Conditions:

        Established uptrend
        Retracement between 5% and 20%
        Close above EMA50
        Close above previous day's high
        Volume >= 1.2 x 20-day average
    """

    required_columns = [
        "RecentSwingHigh",
        "RetracementPercent",
        "VolumeAvg20",
        "Close",
        "EMA50",
        "PreviousDayHigh",
        "EMA20",
        "EMA200",
    ]

    if any(
        pd.isna(row[column])
        for column in required_columns
    ):
        return False

    if row["VolumeAvg20"] <= 0:
        return False

    retracement = row["RetracementPercent"]

    return (
        established_uptrend(row)
        and
        retracement >= MIN_RETRACEMENT_PERCENT
        and
        retracement <= MAX_RETRACEMENT_PERCENT
        and
        row["Close"] > row["EMA50"]
        and
        row["Close"] > row["PreviousDayHigh"]
        and
        row["Volume"] >= (
            RETRACEMENT_VOLUME_MULTIPLIER *
            row["VolumeAvg20"]
        )
    )


# =========================================================
# BREAKOUT SCORE
# =========================================================

def breakout_points(row):
    """
    Maximum = 25 points.
    """

    if pd.isna(row["High20"]):
        return 0

    if row["High20"] <= 0:
        return 0

    breakout_distance = (
        row["Close"] /
        row["High20"] -
        1
    ) * 100

    score = 0

    if breakout_distance > 0:
        score += 15

    if breakout_distance >= 2:
        score += 5

    if breakout_distance >= 5:
        score += 5

    return min(
        score,
        25
    )


# =========================================================
# VOLUME SCORE
# =========================================================

def volume_points(row):
    """
    Maximum = 20 points.
    """

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

    if ratio >= 2.0:
        return 15

    if ratio >= 1.5:
        return 10

    if ratio >= 1.2:
        return 5

    return 0


# =========================================================
# TREND SCORE
# =========================================================

def trend_points(row):
    """
    Maximum = 15 points.
    """

    score = 0

    if (
        not pd.isna(row["Close"])
        and
        not pd.isna(row["EMA200"])
        and
        row["Close"] > row["EMA200"]
    ):
        score += 5

    if (
        not pd.isna(row["EMA50"])
        and
        not pd.isna(row["EMA200"])
        and
        row["EMA50"] > row["EMA200"]
    ):
        score += 5

    if (
        not pd.isna(row["EMA20"])
        and
        not pd.isna(row["EMA50"])
        and
        row["EMA20"] > row["EMA50"]
    ):
        score += 5

    return score


# =========================================================
# CLOSING STRENGTH SCORE
# =========================================================

def closing_strength_points(row):
    """
    Maximum = 10 points.
    """

    score = 0

    if (
        not pd.isna(row["CandleBodyPercent"])
        and
        row["CandleBodyPercent"]
        >= MIN_BREAKOUT_BODY_PERCENT
    ):
        score += 5

    if (
        not pd.isna(row["ClosePosition"])
        and
        row["ClosePosition"]
        >= CLOSE_POSITION_THRESHOLD
    ):
        score += 5

    return score


# =========================================================
# MOMENTUM SCORE
# =========================================================

def momentum_points(row):
    """
    Maximum = 10 points.
    """

    score = 0

    if (
        not pd.isna(row["Return20"])
        and
        row["Return20"] > 5
    ):
        score += 5

    if (
        not pd.isna(row["Return60"])
        and
        row["Return60"] > 10
    ):
        score += 5

    return score


# =========================================================
# RETRACEMENT QUALITY SCORE
# =========================================================

def retracement_points(row):
    """
    Maximum = 10 points.

    Higher points are awarded when:

        Retracement <= 15%
        Close > previous day's high
    """

    retracement = row["RetracementPercent"]

    if (
        pd.isna(retracement)
        or
        retracement < MIN_RETRACEMENT_PERCENT
        or
        retracement > MAX_RETRACEMENT_PERCENT
    ):
        return 0

    score = 0

    if retracement <= 15:
        score += 5

    if (
        not pd.isna(row["PreviousDayHigh"])
        and
        row["Close"] > row["PreviousDayHigh"]
    ):
        score += 5

    return min(
        score,
        10
    )


# =========================================================
# EMA50 SCORE
# =========================================================

def ema50_points(row):
    """
    Maximum = 5 points.
    """

    if (
        not pd.isna(row["Close"])
        and
        not pd.isna(row["EMA50"])
        and
        row["Close"] > row["EMA50"]
    ):
        return 5

    return 0


# =========================================================
# LIQUIDITY SCORE
# =========================================================

def liquidity_points(row):
    """
    Maximum = 5 points.
    """

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
# TOTAL SCORE
# =========================================================

def calculate_total_score(
    breakout,
    volume,
    trend,
    closing_strength,
    momentum,
    retracement,
    ema50,
    liquidity,
):
    """
    Maximum = 100.
    """

    score = (
        breakout +
        volume +
        trend +
        closing_strength +
        momentum +
        retracement +
        ema50 +
        liquidity
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
    """
    Calculate Entry, StopLoss and Target.
    """

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
    # Previous 52-week high
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

    # -----------------------------------------------------
    # Maximum target cap
    # -----------------------------------------------------

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

def analyze_stock(symbol, data):
    """
    Analyze one stock.
    """

    try:

        # -------------------------------------------------
        # Extract OHLCV
        # -------------------------------------------------

        df = (
            data["Close"][symbol]
            .to_frame("Close")
        )

        df["Open"] = data["Open"][symbol]

        df["High"] = data["High"][symbol]

        df["Low"] = data["Low"][symbol]

        df["Volume"] = data["Volume"][symbol]

        df = df.dropna(
            subset=[
                "Open",
                "High",
                "Low",
                "Close",
                "Volume",
            ]
        )

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
        # ESTABLISHED UPTREND
        # -------------------------------------------------

        is_established_uptrend = (
            established_uptrend(row)
        )

        if not is_established_uptrend:
            return None

        # -------------------------------------------------
        # SETUP DETECTION
        #
        # Momentum Continuation =
        #
        # Established Uptrend
        # AND
        # (
        #     20-Day Breakout
        #     OR
        #     Controlled Retracement Recovery
        # )
        # -------------------------------------------------

        is_breakout = detect_breakout(row)

        is_retracement = detect_retracement(row)

        if (
            not is_breakout
            and
            not is_retracement
        ):
            return None

        # -------------------------------------------------
        # Individual score components
        # -------------------------------------------------

        breakout = breakout_points(row)

        volume = volume_points(row)

        trend = trend_points(row)

        closing_strength = (
            closing_strength_points(row)
        )

        momentum = momentum_points(row)

        retracement = retracement_points(row)

        ema50 = ema50_points(row)

        liquidity = liquidity_points(row)

        # -------------------------------------------------
        # Total score
        # -------------------------------------------------

        total_score = calculate_total_score(
            breakout=breakout,
            volume=volume,
            trend=trend,
            closing_strength=closing_strength,
            momentum=momentum,
            retracement=retracement,
            ema50=ema50,
            liquidity=liquidity,
        )

        # -------------------------------------------------
        # Grade
        # -------------------------------------------------

        grade = score_grade(
            total_score
        )

        # -------------------------------------------------
        # Setup type
        # -------------------------------------------------

        if (
            is_breakout
            and
            is_retracement
        ):

            setup = (
                "BREAKOUT + RETRACEMENT"
            )

        elif is_breakout:

            setup = "20-DAY BREAKOUT"

        else:

            setup = (
                "RETRACEMENT RECOVERY"
            )

        # -------------------------------------------------
        # Volume ratio
        # -------------------------------------------------

        if (
            not pd.isna(row["VolumeAvg20"])
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
            not pd.isna(row["High52"])
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
        # Return result
        # -------------------------------------------------

        return {

            "Symbol":
                symbol.replace(
                    ".NS",
                    ""
                ),

            "Setup":
                setup,

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
                row["RetracementPercent"],

            "UpsideTo52WHigh":
                upside_to_52w,

            "Momentum":
                momentum,

            "Trend":
                trend,

            "Breakout":
                breakout,

            "Volume":
                volume,

            "ClosingStrength":
                closing_strength,

            "RetracementQuality":
                retracement,

            "EMA50Score":
                ema50,

            "LiquidityScore":
                liquidity,

            "Return20":
                row["Return20"],

            "Return60":
                row["Return60"],

            "AvgTradedValue20Cr":
                row["AvgTradedValue20Crore"],
        }

    except Exception:
        return None


# =========================================================
# BUILD RANKING
# =========================================================

def build_ranking(symbols, data):
    """
    Analyze all stocks and return ranked candidates.

    IMPORTANT:

    This function returns ALL qualifying candidates.

    TOP_N is applied only when preparing the final display.
    """

    results = []

    print()
    print("=" * 70)
    print("ANALYZING NIFTY 500")
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
            data
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
    #
    # 1. Score
    # 2. Risk/Reward
    # 3. Volume ratio
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
    """
    Get current terminal width.
    """

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
# SAFE DISPLAY VALUE
# =========================================================

def safe_display_string(value):
    """
    Convert ANY pandas/numpy/Python value into a safe
    string for terminal display.
    """

    if value is None:
        return "-"

    try:

        if pd.isna(value):
            return "-"

    except (TypeError, ValueError):

        pass

    return str(value)


# =========================================================
# FORMAT OUTPUT TABLE
# =========================================================

def format_output_table(df):
    """
    Prepare DataFrame for terminal output.

    Returns:

        formatted_dataframe,
        list_of_column_groups
    """

    df = df.copy()

    # -----------------------------------------------------
    # Rounding
    # -----------------------------------------------------

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
    ]

    one_decimal_columns = [

        "RetracementPercent",

        "UpsideTo52WHigh",

        "Return20",

        "Return60",
    ]

    for column in two_decimal_columns:

        if column in df.columns:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            ).round(2)

    for column in one_decimal_columns:

        if column in df.columns:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            ).round(1)

    # -----------------------------------------------------
    # Rename columns
    # -----------------------------------------------------

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

            "RetracementQuality":
                "RetraceQ",

            "AvgTradedValue20Cr":
                "AvgValueCr",
        }
    )

    # -----------------------------------------------------
    # Format percentages
    # -----------------------------------------------------

    for column in [
        "Upside%",
        "Downside%",
    ]:

        if column in df.columns:

            df[column] = df[column].apply(
                lambda x:
                    (
                        f"{x:.2f}%"
                        if pd.notna(x)
                        else "-"
                    )
            )

    # -----------------------------------------------------
    # Main columns
    # -----------------------------------------------------

    primary_columns = [

        "Rank",

        "Symbol",

        "Setup",

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

    # -----------------------------------------------------
    # Secondary columns
    # -----------------------------------------------------

    secondary_columns = [

        "MaxDays",

        "VolRatio",

        "Retrace%",

        "52W Upside%",

        "Momentum",

        "Trend",

        "Breakout",

        "Volume",

        "CloseStr",

        "RetraceQ",

        "EMA50Score",

        "LiquidityScore",

        "Return20",

        "Return60",

        "AvgValueCr",
    ]

    primary_columns = [
        column
        for column in primary_columns
        if column in df.columns
    ]

    secondary_columns = [
        column
        for column in secondary_columns
        if (
            column in df.columns
            and
            column not in primary_columns
        )
    ]

    identity_columns = [
        column
        for column in [
            "Rank",
            "Symbol",
        ]
        if column in df.columns
    ]

    # -----------------------------------------------------
    # Terminal width
    # -----------------------------------------------------

    terminal_width = get_terminal_width()

    available_width = (
        terminal_width - 2
    )

    # -----------------------------------------------------
    # Helper to calculate table width
    # -----------------------------------------------------

    def table_width(columns):

        if not columns:
            return 0

        temp = df[columns].copy()

        widths = {}

        for column in columns:

            values = (
                temp[column]
                .apply(safe_display_string)
            )

            if len(values) > 0:

                max_value_width = int(
                    values.map(
                        lambda value:
                            len(str(value))
                    ).max()
                )

            else:

                max_value_width = 0

            widths[column] = max(
                len(str(column)),
                max_value_width
            )

        total_width = (
            sum(widths.values())
            +
            max(
                len(columns) - 1,
                0
            )
        )

        return total_width

    # -----------------------------------------------------
    # Build groups
    # -----------------------------------------------------

    groups = []

    # -----------------------------------------------------
    # First try complete primary table
    # -----------------------------------------------------

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
            column
            for column in remaining_columns
            if column not in identity_columns
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

        if (
            len(current_group)
            > len(identity_columns)
        ):

            groups.append(
                current_group
            )

        return df, groups

    # -----------------------------------------------------
    # Additional secondary tables
    # -----------------------------------------------------

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
    """
    Print one horizontal table section.
    """

    print()

    if total_sections > 1:

        print(
            f"TABLE {section_number}/{total_sections}"
        )

        print(
            "-" * min(
                get_terminal_width(),
                100
            )
        )

    section = (
        df[columns]
        .copy()
    )

    # -----------------------------------------------------
    # Convert every value to a safe display string
    # -----------------------------------------------------

    for column in section.columns:

        if column in [

            "Close",

            "Entry",

            "Target",

            "StopLoss",

            "R:R",

            "VolRatio",

            "AvgValueCr",

        ]:

            numeric_values = pd.to_numeric(
                section[column],
                errors="coerce"
            )

            section[column] = (
                numeric_values
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

            numeric_values = pd.to_numeric(
                section[column],
                errors="coerce"
            )

            section[column] = (
                numeric_values
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
                .apply(safe_display_string)
            )

        elif column == "Score":

            numeric_values = pd.to_numeric(
                section[column],
                errors="coerce"
            )

            section[column] = (
                numeric_values
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

            "Breakout",

            "Volume",

            "CloseStr",

            "RetraceQ",

            "EMA50Score",

            "LiquidityScore",

        ]:

            numeric_values = pd.to_numeric(
                section[column],
                errors="coerce"
            )

            section[column] = (
                numeric_values
                .map(
                    lambda x:
                    (
                        str(int(x))
                        if pd.notna(x)
                        else "-"
                    )
                )
            )

        elif column == "Symbol":

            section[column] = (
                section[column]
                .apply(safe_display_string)
            )

        elif column == "Setup":

            section[column] = (
                section[column]
                .apply(
                    lambda x:
                    safe_display_string(x)[:24]
                )
            )

        else:

            section[column] = (
                section[column]
                .apply(safe_display_string)
            )

    # -----------------------------------------------------
    # Column widths
    # -----------------------------------------------------

    widths = {}

    for column in section.columns:

        values = (
            section[column]
            .apply(safe_display_string)
        )

        if len(values) > 0:

            max_value_width = int(
                values.map(
                    lambda value:
                        len(str(value))
                ).max()
            )

        else:

            max_value_width = 0

        widths[column] = max(
            len(str(column)),
            max_value_width
        )

    # -----------------------------------------------------
    # Header
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # Rows
    # -----------------------------------------------------

    for _, row in section.iterrows():

        line = " ".join(
            safe_display_string(
                row[column]
            ).ljust(
                widths[column]
            )
            for column in section.columns
        )

        print(line)


# =========================================================
# PRINT STRATEGY SUMMARY
# =========================================================

def print_strategy_summary():

    print()
    print("=" * 100)

    print(
        "MOMENTUM CONTINUATION STRATEGY"
    )

    print("=" * 100)

    print()

    print(
        "CORE SIGNAL:"
    )

    print()

    print(
        "Established Uptrend"
    )

    print(
        "        AND"
    )

    print(
        "    (20-Day Breakout"
    )

    print(
        "        OR"
    )

    print(
        "     Controlled Retracement Recovery)"
    )

    print()

    print(
        "Established Uptrend:"
    )

    print(
        "  Close > EMA50"
    )

    print(
        "  EMA20 > EMA50"
    )

    print(
        "  EMA50 > EMA200"
    )

    print()

    print(
        "20-Day Breakout:"
    )

    print(
        f"  Close > previous {BREAKOUT_LOOKBACK}-day high"
    )

    print(
        "  Close > EMA20"
    )

    print(
        f"  Volume >= {BREAKOUT_VOLUME_MULTIPLIER}x "
        "20-day average"
    )

    print()

    print(
        "Controlled Retracement Recovery:"
    )

    print(
        f"  Retracement = {MIN_RETRACEMENT_PERCENT}% "
        f"to {MAX_RETRACEMENT_PERCENT}%"
    )

    print(
        "  Close > EMA50"
    )

    print(
        "  Close > previous day's high"
    )

    print(
        f"  Volume >= {RETRACEMENT_VOLUME_MULTIPLIER}x "
        "20-day average"
    )

    print()

    print("=" * 100)


# =========================================================
# PRINT RANKING METHODOLOGY
# =========================================================

def print_ranking_methodology():

    print()
    print("=" * 100)

    print(
        "RANKING METHODOLOGY"
    )

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
        f"  What it measures"
    )

    print("-" * 100)

    descriptions = {

        "Breakout":
            "Breakout distance above previous 20-day high",

        "Volume":
            "Unusual volume confirmation",

        "Trend":
            "EMA20 / EMA50 / EMA200 trend alignment",

        "ClosingStrength":
            "Candle body + close near daily high",

        "Momentum":
            "20-day and 60-day price momentum",

        "RetracementQuality":
            "Controlled pullback + recovery",

        "EMA50Score":
            "Price above 50 EMA",

        "LiquidityScore":
            "20-day average traded value",
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

    print(
        "Score interpretation:"
    )

    print(
        "90–100  = A+  Exceptional setup quality"
    )

    print(
        "80–89   = A   Very strong setup"
    )

    print(
        "70–79   = B   Good setup"
    )

    print(
        "60–69   = C   Moderate setup"
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
        "It is a relative ranking score based on "
        "the predefined Momentum Continuation rules."
    )

    print("=" * 100)


# =========================================================
# PRINT RULES
# =========================================================

def print_rules():

    print()
    print("=" * 100)

    print(
        "RULES FOLLOWED"
    )

    print("-" * 100)

    print(
        "CORE MOMENTUM CONTINUATION:"
    )

    print(
        "Established Uptrend AND "
        "(20-Day Breakout OR Controlled Retracement Recovery)."
    )

    print()

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

    print()

    print(
        "ESTABLISHED UPTREND:"
    )

    print(
        "4. Close > EMA50."
    )

    print(
        "5. EMA20 > EMA50."
    )

    print(
        "6. EMA50 > EMA200."
    )

    print()

    print(
        "20-DAY BREAKOUT:"
    )

    print(
        f"7. Close above previous "
        f"{BREAKOUT_LOOKBACK}-day high."
    )

    print(
        "8. Close > EMA20."
    )

    print(
        f"9. Volume >= {BREAKOUT_VOLUME_MULTIPLIER}x "
        "20-day average volume."
    )

    print()

    print(
        "CONTROLLED RETRACEMENT RECOVERY:"
    )

    print(
        f"10. Retracement between "
        f"{MIN_RETRACEMENT_PERCENT}% and "
        f"{MAX_RETRACEMENT_PERCENT}%."
    )

    print(
        "11. Close > EMA50."
    )

    print(
        "12. Close above previous day's high."
    )

    print(
        f"13. Volume >= {RETRACEMENT_VOLUME_MULTIPLIER}x "
        "20-day average volume."
    )

    print()

    print(
        "TRADE PLAN:"
    )

    print(
        "14. Entry: Latest available closing price."
    )

    print(
        "15. Stop: Previous 20-day swing low "
        f"- {STOP_ATR_MULTIPLIER} × ATR14."
    )

    print(
        f"16. Target: Greater of 2R or previous "
        f"52-week high, capped at "
        f"{MAX_TARGET_PERCENT}%."
    )

    print(
        f"17. Minimum risk/reward: "
        f"{MIN_RISK_REWARD}:1."
    )

    print(
        f"18. Maximum holding period: "
        f"{MAX_HOLDING_DAYS} trading days."
    )

    print("=" * 100)


# =========================================================
# PRINT COLUMN DESCRIPTIONS
# =========================================================

def print_column_descriptions():

    print()
    print("=" * 100)

    print(
        "COLUMN DESCRIPTIONS"
    )

    print("-" * 100)

    column_descriptions = {

        "Rank":
            "Ranking position.",

        "Symbol":
            "NSE stock symbol.",

        "Setup":
            "20-DAY BREAKOUT or RETRACEMENT RECOVERY.",

        "Score":
            "Weighted setup-quality score out of 100.",

        "Grade":
            "Score classification: A+, A, B, C or D.",

        "Close":
            "Latest available closing price.",

        "Entry":
            "Proposed entry price, equal to latest close.",

        "Target":
            "Calculated target using 2R or previous 52-week high.",

        "StopLoss":
            "20-day swing low minus ATR component.",

        "Upside%":
            "Percentage gain from Entry to Target.",

        "Downside%":
            "Percentage loss from Entry to StopLoss.",

        "R:R":
            "Reward-to-risk ratio.",

        "MaxDays":
            "Maximum intended holding period.",

        "VolRatio":
            "Today's volume / 20-day average volume.",

        "Retrace%":
            "Decline from recent 60-day swing high.",

        "52W Upside%":
            "Distance from current price to previous 52-week high.",

        "Momentum":
            "Momentum score, maximum 10.",

        "Trend":
            "Trend score, maximum 15.",

        "Breakout":
            "Breakout score, maximum 25.",

        "Volume":
            "Volume score, maximum 20.",

        "CloseStr":
            "Closing-strength score, maximum 10.",

        "RetraceQ":
            "Retracement-quality score, maximum 10.",

        "EMA50Score":
            "Price-above-EMA50 score, maximum 5.",

        "LiquidityScore":
            "Liquidity score, maximum 5.",

        "Return20":
            "Approximate 20-trading-day return.",

        "Return60":
            "Approximate 60-trading-day return.",

        "AvgValueCr":
            "20-day average daily traded value in ₹ crore.",
    }

    for column, description in (
        column_descriptions.items()
    ):

        print(
            f"{column:<18} : {description}"
        )

    print()

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
# PRINT ANALYSIS DATES
# =========================================================

def print_analysis_dates(
    execution_date,
    latest_trading_date,
    analysis_date
):
    """
    Print the dates associated with the analysis.

    Execution Date:
        Calendar date on which the program was executed.

    Latest Trading Date:
        Latest market-data trading date available from Yahoo
        Finance.

    Analysis Date:
        Trading date whose latest available OHLCV candle is
        actually used for the stock analysis.
    """

    print()
    print("=" * 100)

    print(
        "ANALYSIS DATES"
    )

    print("-" * 100)

    print(
        f"{'Execution Date':<24}: "
        f"{format_date(execution_date)}"
    )

    print(
        f"{'Latest Trading Date':<24}: "
        f"{format_date(latest_trading_date)}"
    )

    print(
        f"{'Analysis Date':<24}: "
        f"{format_date(analysis_date)}"
    )

    print("=" * 100)


# =========================================================
# PRINT FINAL TABLES
# =========================================================

def print_final_tables(
    ranking,
    execution_date,
    latest_trading_date,
    analysis_date
):
    """
    PRINTS THE QUALIFYING CANDIDATE TABLES LAST.

    Nothing is printed after this function returns from
    display_results().

    Important:

        ranking contains ALL qualifying candidates.

        TOP_N controls how many are displayed in the
        final ranking tables.
    """

    print()
    print()
    print("=" * 100)

    print(
        "FINAL QUALIFYING CANDIDATES"
    )

    print("=" * 100)

    # -----------------------------------------------------
    # DATE BLOCK
    #
    # This is deliberately printed immediately above the
    # qualifying candidate information.
    # -----------------------------------------------------

    print_analysis_dates(
        execution_date=execution_date,
        latest_trading_date=latest_trading_date,
        analysis_date=analysis_date,
    )

    # -----------------------------------------------------
    # No qualifying candidates
    # -----------------------------------------------------

    if ranking.empty:

        print()
        print(
            "NO QUALIFYING MOMENTUM CONTINUATION "
            "CANDIDATES FOUND."
        )

        print()
        print("=" * 100)
        print("END OF FINAL RESULTS")
        print("=" * 100)

        return

    # -----------------------------------------------------
    # ALL candidates were retained in ranking.
    #
    # Only TOP_N are displayed.
    # -----------------------------------------------------

    total_qualifying = len(ranking)

    display = (
        ranking
        .head(TOP_N)
        .copy()
    )

    # -----------------------------------------------------
    # Format display tables
    # -----------------------------------------------------

    display, groups = (
        format_output_table(
            display
        )
    )

    # -----------------------------------------------------
    # Summary before the tables
    # -----------------------------------------------------

    print()

    print(
        f"Total qualifying candidates found: "
        f"{total_qualifying}"
    )

    print(
        f"Candidates displayed: "
        f"{len(display)}"
    )

    print(
        f"Ranking score maximum: "
        f"{TOTAL_SCORE_WEIGHT}/100"
    )

    print(
        f"Top N setting: "
        f"{TOP_N}"
    )

    # -----------------------------------------------------
    # Setup breakdown
    # -----------------------------------------------------

    setup_counts = (
        ranking["Setup"]
        .value_counts()
    )

    print()

    print(
        "QUALIFYING SETUP BREAKDOWN"
    )

    print(
        "-" * 100
    )

    for setup, count in setup_counts.items():

        print(
            f"{setup:<35} : {count}"
        )

    # -----------------------------------------------------
    # FINAL TABLES
    # -----------------------------------------------------

    print()

    print(
        "=" * 100
    )

    print(
        "RANKED QUALIFYING CANDIDATES"
    )

    print(
        "=" * 100
    )

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
    # Absolute end marker
    #
    # NOTHING ELSE IS PRINTED AFTER THIS.
    # -----------------------------------------------------

    print()
    print("=" * 100)

    print(
        "END OF FINAL RESULTS"
    )

    print("=" * 100)


# =========================================================
# DISPLAY RESULTS
# =========================================================

def display_results(
    ranking,
    execution_date,
    latest_trading_date,
    analysis_date
):
    """
    Display strategy information first.

    FINAL QUALIFYING CANDIDATE TABLES ARE PRINTED LAST.

    There must be NO output after print_final_tables().
    """

    print()
    print("=" * 100)

    print(
        "MOMENTUM CONTINUATION"
    )

    print(
        "NIFTY 500 SHORT-TERM POSITIONAL STOCK RANKING"
    )

    print("=" * 100)

    # -----------------------------------------------------
    # Strategy explanation
    # -----------------------------------------------------

    print_strategy_summary()

    # -----------------------------------------------------
    # Methodology
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
    # Important notes
    # -----------------------------------------------------

    print()
    print("=" * 100)

    print(
        "RESEARCH DISCLAIMER"
    )

    print("-" * 100)

    print(
        "This system ranks technical setups."
    )

    print(
        "It does not predict future returns."
    )

    print(
        "A higher score does not guarantee a better trade."
    )

    print(
        "Stop-loss is an intended exit level, "
        "not a guaranteed maximum loss."
    )

    print(
        "Overnight gaps and slippage can produce "
        "losses beyond the intended stop."
    )

    print("=" * 100)

    # =====================================================
    # FINAL OUTPUT
    #
    # IMPORTANT:
    #
    # This MUST remain the LAST function called here.
    #
    # No print statement or function that prints anything
    # should be placed after this call.
    # =====================================================

    print_final_tables(
        ranking=ranking,
        execution_date=execution_date,
        latest_trading_date=latest_trading_date,
        analysis_date=analysis_date,
    )


# =========================================================
# MAIN
# =========================================================

def main():

    # -----------------------------------------------------
    # Execution date
    #
    # This is the calendar date on which the program starts.
    # -----------------------------------------------------

    execution_date = datetime.now().date()

    print()
    print("=" * 80)

    print(
        "MOMENTUM CONTINUATION"
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

    # IMPORTANT:
    #
    # get_market_data_for_symbols() currently returns:
    #
    #     data
    #     valid_symbols
    #     latest_trading_date
    #
    # Therefore exactly THREE values are unpacked here.
    #
    # Do NOT add analysis_date to this unpacking unless
    # trade_data.py is also changed to return four values.
    # -----------------------------------------------------

    data, valid_symbols, latest_trading_date = (
        get_market_data_for_symbols(
            symbols
        )
    )

    if not valid_symbols:

        raise RuntimeError(
            "No valid market data was returned."
        )

    # -----------------------------------------------------
    # Analysis date
    #
    # The strategy analyzes the last available market
    # candle, so the analysis date is the latest trading
    # date returned by the market-data function.
    # -----------------------------------------------------

    analysis_date = latest_trading_date

    print(
        f"Market data available for "
        f"{len(valid_symbols)} stocks."
    )

    # -----------------------------------------------------
    # STEP 3 — Analysis
    # -----------------------------------------------------

    print()

    print(
        "STEP 3 — Detecting Momentum Continuation "
        "setups and calculating weighted scores..."
    )

    ranking = build_ranking(
        valid_symbols,
        data
    )

    # -----------------------------------------------------
    # STEP 4 — Display
    # -----------------------------------------------------

    display_results(
        ranking=ranking,
        execution_date=execution_date,
        latest_trading_date=latest_trading_date,
        analysis_date=analysis_date,
    )


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":

    main()