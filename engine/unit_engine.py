"""
V7 Unit Engine
--------------
Centralised conversion logic for:
- Area units (m2 <-> ft2)
- Rate units (£/m2 <-> £/ft2)

All internal AREA calculations should use:
- Area: m2
- Rate: £/m2

Phase 2 note:
- "£/nr" (count) and "%" (on-cost) rates are NOT area-based, so they are
  never converted. convert_rate() returns them unchanged if it ever sees
  them, so a stray call can't crash the app.
"""

# Conversion constants
FT2_PER_M2 = 10.76391041671

# Rate units that are not area-based and must never be converted
NON_AREA_RATE_UNITS = {"£/nr", "%", "N/A"}


# -------------------------------------------------
# Area conversions
# -------------------------------------------------

def ft2_to_m2(area_ft2: float) -> float:
    if area_ft2 < 0:
        raise ValueError("Area cannot be negative")
    return area_ft2 / FT2_PER_M2


def m2_to_ft2(area_m2: float) -> float:
    if area_m2 < 0:
        raise ValueError("Area cannot be negative")
    return area_m2 * FT2_PER_M2


def convert_area(area: float, from_unit: str, to_unit: str) -> float:
    if from_unit == to_unit:
        return area

    if from_unit == "ft2" and to_unit == "m2":
        return ft2_to_m2(area)

    if from_unit == "m2" and to_unit == "ft2":
        return m2_to_ft2(area)

    raise ValueError(f"Unsupported area unit conversion: {from_unit} -> {to_unit}")


# -------------------------------------------------
# Rate conversions
# -------------------------------------------------

def gbp_per_ft2_to_gbp_per_m2(rate_ft2: float) -> float:
    if rate_ft2 < 0:
        raise ValueError("Rate cannot be negative")
    return rate_ft2 * FT2_PER_M2


def gbp_per_m2_to_gbp_per_ft2(rate_m2: float) -> float:
    if rate_m2 < 0:
        raise ValueError("Rate cannot be negative")
    return rate_m2 / FT2_PER_M2


def convert_rate(rate: float, from_unit: str, to_unit: str) -> float:
    """
    Convert rates between £/m2 and £/ft2.

    Count (£/nr) and percentage (%) rates are not area-based, so they are
    returned unchanged — there is no meaningful per-area conversion for them.
    """

    if from_unit == to_unit:
        return rate

    # Never convert count or percentage rates — pass them straight through.
    if from_unit in NON_AREA_RATE_UNITS or to_unit in NON_AREA_RATE_UNITS:
        return rate

    if from_unit == "£/ft2" and to_unit == "£/m2":
        return gbp_per_ft2_to_gbp_per_m2(rate)

    if from_unit == "£/m2" and to_unit == "£/ft2":
        return gbp_per_m2_to_gbp_per_ft2(rate)

    raise ValueError(f"Unsupported rate unit conversion: {from_unit} -> {to_unit}")