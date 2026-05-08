import json
import os
from pathlib import Path

JSON_PATH = Path(__file__).parent.parent / "data" / "fitout_cost_database_v8.json"

REQUIRED_RATE_FIELDS = {"element_id", "location", "quartile", "rate", "rate_unit"}
VALID_RATE_UNITS = {"£/m2", "£/ft2"}


def load_cost_database() -> dict:
    """
    Load the V8 cost database from JSON.
    Excel is never accessed at runtime — use watch_excel.py to keep JSON in sync.
    """
    if not JSON_PATH.exists():
        raise FileNotFoundError(
            f"Cost database not found at: {JSON_PATH}\n"
            "Run `python excel_to_json.py` to generate it from Excel."
        )

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    for key in ("elements", "quantity_rules", "rates"):
        if key not in data:
            raise KeyError(f"JSON database is missing required key: '{key}'")

    _validate_rates(data["rates"])

    return {
        "elements":       data["elements"],
        "quantity_rules": data["quantity_rules"],
        "rates":          data["rates"],
        "_mtime":         os.path.getmtime(JSON_PATH),  # stored so app can detect changes
    }


def get_json_mtime() -> float:
    """Return the modification time of the JSON file (used to detect updates)."""
    return os.path.getmtime(JSON_PATH) if JSON_PATH.exists() else 0.0


def _validate_rates(rates: list[dict]):
    for i, row in enumerate(rates):
        missing = REQUIRED_RATE_FIELDS - set(row.keys())
        if missing:
            raise ValueError(f"Rate row {i} is missing fields: {sorted(missing)}")

        rate_unit = row["rate_unit"]
        if rate_unit not in VALID_RATE_UNITS:
            raise ValueError(
                f"Rate row {i} has unsupported rate_unit '{rate_unit}'. "
                f"Expected one of: {VALID_RATE_UNITS}"
            )

        if row["rate"] < 0:
            raise ValueError(
                f"Rate row {i} ({row['element_id']}) has negative rate: {row['rate']}"
            )