import pandas as pd
import pytest

from data_loader import load_index_data


def test_load_index_data(tmp_path):
    test_file = tmp_path / "test_index.csv"

    test_data = pd.DataFrame(
        {
            "Date": [
                "2024-01-03",
                "2024-01-02",
                "2024-01-04",
            ],
            "TRI": [
                1020.0,
                1000.0,
                1050.0,
            ],
        }
    )

    test_data.to_csv(test_file, index=False)

    loaded_data = load_index_data(test_file)

    assert list(loaded_data.columns) == ["Date", "TRI"]
    assert len(loaded_data) == 3
    assert loaded_data["Date"].is_monotonic_increasing
    assert loaded_data["TRI"].dtype.kind in "fi"


def test_missing_file():
    with pytest.raises(FileNotFoundError):
        load_index_data("does_not_exist.csv")


def test_missing_required_column(tmp_path):
    test_file = tmp_path / "invalid.csv"

    invalid_data = pd.DataFrame(
        {
            "Date": ["2024-01-02"],
            "Close": [1000.0],
        }
    )

    invalid_data.to_csv(test_file, index=False)

    with pytest.raises(ValueError, match="Missing required columns"):
        load_index_data(test_file)


def test_invalid_tri_value(tmp_path):
    test_file = tmp_path / "invalid_tri.csv"

    invalid_data = pd.DataFrame(
        {
            "Date": ["2024-01-02"],
            "TRI": ["invalid"],
        }
    )

    invalid_data.to_csv(test_file, index=False)

    with pytest.raises(ValueError, match="invalid TRI values"):
        load_index_data(test_file)