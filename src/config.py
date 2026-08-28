from pathlib import Path


# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent


# Data directories
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"


# Research parameters
MONTHLY_ALLOCATION = 20_000
INVESTMENT_DAY = 26


# Indices under research
INDICES = {
    "nifty500_momentum50": {
        "name": "Nifty 500 Momentum 50 Index",
    },
    "nifty_alpha50": {
        "name": "Nifty Alpha 50 Index",
    },
    "nifty_smallcap250_momentum_quality100": {
        "name": "Nifty Smallcap 250 Momentum Quality 100 Index",
    },
}