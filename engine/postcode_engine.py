"""
postcode_engine.py
------------------
Resolves a UK postcode to one of the three supported cities:
London, Birmingham, Manchester.

Primary method:
- Uses postcodes.io API for accurate lookup

Fallback:
- Uses Royal Mail postcode area prefixes if API fails
"""

import re
import requests

# ── Fallback mapping ──────────────────────────────────────────────────────
_AREA_TO_CITY: dict[str, str] = {
    # London
    "BR": "London",
    "CR": "London",
    "DA": "London",
    "E":  "London",
    "EC": "London",
    "EN": "London",
    "HA": "London",
    "IG": "London",
    "KT": "London",
    "N":  "London",
    "NW": "London",
    "RM": "London",
    "SE": "London",
    "SM": "London",
    "SW": "London",
    "TW": "London",
    "UB": "London",
    "W":  "London",
    "WC": "London",
    "WD": "London",

    # Birmingham
    "B":  "Birmingham",
    "CV": "Birmingham",
    "DY": "Birmingham",
    "WS": "Birmingham",
    "WV": "Birmingham",

    # Manchester
    "BL": "Manchester",
    "M":  "Manchester",
    "OL": "Manchester",
    "SK": "Manchester",
    "WN": "Manchester",
}

_TWO_LETTER = {k: v for k, v in _AREA_TO_CITY.items() if len(k) == 2}
_ONE_LETTER = {k: v for k, v in _AREA_TO_CITY.items() if len(k) == 1}

# ── Regex ────────────────────────────────────────────────────────────────
_POSTCODE_RE = re.compile(
    r"^([A-Z]{1,2})"
    r"(\d{1,2}[A-Z]?)"
    r"\s*"
    r"(\d[A-Z]{2})?$"
)

# ── API Lookup ───────────────────────────────────────────────────────────
def _resolve_via_api(cleaned: str) -> tuple[str | None, str | None]:
    try:
        res = requests.get(
            f"https://api.postcodes.io/postcodes/{cleaned}",
            timeout=3
        )

        data = res.json()

        if data.get("status") != 200:
            return None, "Invalid postcode."

        result = data["result"]
        region = result.get("region")
        district = result.get("admin_district")

        # Map API response → supported cities
        if region == "London":
            return "London", None

        elif district in [
            "Birmingham", "Coventry", "Wolverhampton",
            "Dudley", "Walsall"
        ]:
            return "Birmingham", None

        elif district in [
            "Manchester", "Salford", "Stockport",
            "Bolton", "Oldham", "Wigan"
        ]:
            return "Manchester", None

        return None, f"{district} is outside supported cities."

    except Exception as e:
        print(f"❌ API exception: {e}")
        return None, "API lookup failed"


# ── Fallback Logic ───────────────────────────────────────────────────────
def _resolve_via_prefix(cleaned: str) -> tuple[str | None, str | None]:
    area_match = re.match(r"^([A-Z]{1,2})", cleaned)

    if not area_match:
        return None, "Could not read postcode area."

    raw_area = area_match.group(1)

    city = _TWO_LETTER.get(raw_area) or _ONE_LETTER.get(raw_area[0])

    if city:
        return city, None

    return None, f"Postcode area '{raw_area}' is outside coverage."


# ── Main Resolver ────────────────────────────────────────────────────────
def resolve_postcode(raw: str) -> tuple[str | None, str | None]:
    cleaned = raw.strip().upper().replace(" ", "")

    if not cleaned:
        print("❌ Empty input received")
        return None, "Please enter a postcode."

    if not re.match(r"^[A-Z0-9]+$", cleaned):
        print(f"❌ Invalid characters in postcode: {raw}")
        return None, "Postcode must contain only letters and numbers."

    print(f"🔎 Resolving postcode: {cleaned}")

    # ── Step 1: API lookup ───────────────────────────────
    city, err = _resolve_via_api(cleaned)

    if city:
        print(f"✅ Used API lookup → {city}")
        return city, None

    if err:
        print(f"ℹ️ API response: {err}")

    # ── Step 2: Fallback ────────────────────────────────
    city, fallback_err = _resolve_via_prefix(cleaned)

    if city:
        print(f"⚠️ Used fallback prefix logic → {city}")
        return city, None

    print(f"❌ No match found: {cleaned}")
    return None, "Postcode is outside supported areas."


# ── Formatter ────────────────────────────────────────────────────────────
def format_postcode(raw: str) -> str:
    cleaned = raw.strip().upper().replace(" ", "")

    if len(cleaned) > 3:
        return f"{cleaned[:-3]} {cleaned[-3:]}"

    return cleaned