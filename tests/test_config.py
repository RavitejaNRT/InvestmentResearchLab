from config import (
    MONTHLY_ALLOCATION,
    INVESTMENT_DAY,
    INDICES,
    RAW_DATA_DIR,
    PROCESSED_DATA_DIR,
)


def test_monthly_allocation():
    assert MONTHLY_ALLOCATION == 20_000


def test_investment_day():
    assert INVESTMENT_DAY == 26


def test_three_indices_configured():
    assert len(INDICES) == 3


def test_data_directories():
    assert RAW_DATA_DIR.name == "raw"
    assert PROCESSED_DATA_DIR.name == "processed"