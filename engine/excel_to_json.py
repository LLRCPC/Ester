"""
excel_to_json.py
----------------
Converts the V8 Excel cost database to JSON.
Run manually:   python excel_to_json.py
Auto-sync:      python watch_excel.py  (watches for changes)
"""

from pathlib import Path
import pandas as pd
import json
from datetime import datetime

EXCEL_PATH = Path(__file__).parent.parent / "data" / "fitout_cost_database_v8.xlsx"
JSON_PATH  = Path(__file__).parent.parent / "data" / "fitout_cost_database_v8.json"

REQUIRED_COLUMNS = {
    "elements":       {"element_id", "element_name", "category"},
    "quantity_rules": {"element_id", "quantity_method", "default_pct", "unit"},
    "rates":          {"element_id", "location", "quartile", "rate", "rate_unit"},
}

VALID_RATE_UNITS = {"£/m2", "£/ft2"}


def convert_excel_to_json() -> dict:
    if not EXCEL_PATH.exists():
        raise FileNotFoundError(f"Excel file not found: {EXCEL_PATH}")

    sheets = {}
    for sheet in ("elements", "quantity_rules", "rates"):
        df = pd.read_excel(EXCEL_PATH, sheet_name=sheet)

        # Strip whitespace from all string columns
        str_cols = df.select_dtypes(include="object").columns
        for col in str_cols:
            df[col] = df[col].str.strip()

        # Drop trailing empty rows (Excel often writes extra blank rows)
        if "element_id" in df.columns:
            df = df.dropna(subset=["element_id"])

        # Validate required columns
        missing = REQUIRED_COLUMNS[sheet] - set(df.columns)
        if missing:
            raise ValueError(
                f"Sheet '{sheet}' is missing required columns: {sorted(missing)}"
            )

        sheets[sheet] = df

    # Validate rates
    rates_df = sheets["rates"]

    bad_units = rates_df[~rates_df["rate_unit"].isin(VALID_RATE_UNITS)]
    if not bad_units.empty:
        raise ValueError(
            f"Invalid rate_unit values in 'rates' sheet:\n"
            f"{bad_units[['element_id', 'rate_unit']].to_string()}\n"
            f"Expected one of: {VALID_RATE_UNITS}"
        )

    if rates_df["rate"].isnull().any():
        raise ValueError("'rates' sheet contains null rate values.")

    if (rates_df["rate"] < 0).any():
        raise ValueError("'rates' sheet contains negative rate values.")

    data = {
        "meta": {
            "source_file": EXCEL_PATH.name,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        },
        "elements":       sheets["elements"].to_dict(orient="records"),
        "quantity_rules": sheets["quantity_rules"].to_dict(orient="records"),
        "rates":          sheets["rates"].to_dict(orient="records"),
    }

    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✅ JSON rebuilt from {EXCEL_PATH.name}")
    print(f"   {len(data['elements'])} elements, {len(data['rates'])} rate rows")
    print(f"   Written → {JSON_PATH}")

    return data


if __name__ == "__main__":
    convert_excel_to_json()