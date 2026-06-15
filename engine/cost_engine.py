from engine.quantity_engine import calculate_quantity
from engine.unit_engine import convert_rate


def calculate_element_cost(
    *,
    db: dict,
    element: dict,
    rate_row: dict,
    element_areas_m2: dict,
):
    """
    Calculate cost for a single WORK element (area-based or count-based).

    Two kinds of element are handled here:

      • Area elements  (rate_unit "£/m2" or "£/ft2")
        quantity is an area in m²; cost = area × (rate converted to £/m²)

      • Count elements (rate_unit "£/nr")
        quantity is a plain number (e.g. number of lifts);
        cost = number × rate, with no area conversion.

    Percentage on-costs (rate_unit "%") are NOT handled here — they are
    applied separately, after the works subtotal, by breakdown_engine.

    Note: `element_areas_m2` is the shared {element_id: value} store. For
    area elements the value is an area in m²; for count elements it is a
    simple count. The maths (quantity × rate) is identical either way.
    """

    element_id   = element["element_id"]
    element_name = element["element_name"]
    rate_unit    = rate_row.get("rate_unit", "£/m2")

    # The stored quantity — area in m² for area elements, a count for count elements
    quantity = calculate_quantity(
        element_id=element_id,
        element_areas_m2=element_areas_m2,
    )

    # ── Count element (£/nr) ───────────────────────────────────────────────
    if rate_unit == "£/nr":
        unit_rate  = rate_row["rate"]
        total_cost = quantity * unit_rate
        return {
            "element_id":   element_id,
            "element_name": element_name,
            "kind":         "count",
            "quantity":     round(quantity, 2),
            "rate":         round(unit_rate, 2),
            "rate_unit":    "£/nr",
            "total_cost":   round(total_cost, 0),
            # kept for backward compatibility with code that reads these keys
            "area_m2":      round(quantity, 2),
            "rate_gbp_m2":  round(unit_rate, 2),
        }

    # ── Area element (£/m2 or £/ft2) ───────────────────────────────────────
    rate_gbp_m2 = convert_rate(
        rate_row["rate"],
        from_unit=rate_unit,
        to_unit="£/m2",
    )
    total_cost = quantity * rate_gbp_m2

    return {
        "element_id":   element_id,
        "element_name": element_name,
        "kind":         "area",
        "area_m2":      round(quantity, 2),
        "rate_gbp_m2":  round(rate_gbp_m2, 2),
        "rate_unit":    "£/m2",
        "total_cost":   round(total_cost, 0),
    }