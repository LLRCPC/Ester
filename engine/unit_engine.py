"""
V7 Unit Engine
--------------
Centralised conversion logic for:
- Area units (m2 <-> ft2)
- Rate units (£/m2 <-> £/ft2)

All internal calculations should use:
- Area: m2
- Rate: £/m2
"""

# Conversion constants
FT2_PER_M2 = 10.76391041671


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
    """

    if from_unit == to_unit:
        return rate

    if from_unit == "£/ft2" and to_unit == "£/m2":
        return gbp_per_ft2_to_gbp_per_m2(rate)

    if from_unit == "£/m2" and to_unit == "£/ft2":
        return gbp_per_m2_to_gbp_per_ft2(rate)

    raise ValueError(f"Unsupported rate unit conversion: {from_unit} -> {to_unit}")