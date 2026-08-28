from pathlib import Path

import pandas as pd

from config import RAW_DATA_DIR


def load_index_data(file_path: str | Path) -> pd.DataFrame:
    """
    Load historical index data from a CSV file.

    The function accepts either:
    - A filename, which is searched for inside data/raw/
    - A full or relative Path to a CSV file

    Expected CSV columns:
        Date
        TRI

    Returns:
        pandas DataFrame sorted by Date.
    """
    file_path = Path(file_path)

    if not file_path.is_absolute():
        if file_path.parent == Path("."):
            file_path = RAW_DATA_DIR / file_path

    if not file_path.exists():
        raise FileNotFoundError(
            f"Historical data file not found: {file_path}"
        )

    data = pd.read_csv(file_path)

    required_columns = {"Date", "TRI"}
    missing_columns = required_columns - set(data.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {sorted(missing_columns)}"
        )

    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    data["TRI"] = pd.to_numeric(data["TRI"], errors="coerce")

    if data["Date"].isna().any():
        raise ValueError("Historical data contains invalid dates.")

    if data["TRI"].isna().any():
        raise ValueError("Historical data contains invalid TRI values.")

    if (data["TRI"] <= 0).any():
        raise ValueError("TRI values must be greater than zero.")

    if data["Date"].duplicated().any():
        raise ValueError("Historical data contains duplicate dates.")

    data = data.sort_values("Date").reset_index(drop=True)

    return data