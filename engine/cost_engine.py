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
    Calculate cost for a single element using explicit area input.
    """

    # Quantity (m²)
    quantity_m2 = calculate_quantity(
        element_id=element["element_id"],
        element_areas_m2=element_areas_m2,
    )

    # Convert rate to £/m²
    base_rate = rate_row["rate"]
    rate_unit = rate_row["rate_unit"]

    rate_gbp_m2 = convert_rate(
        base_rate,
        from_unit=rate_unit,
        to_unit="£/m2",
    )

    total_cost = quantity_m2 * rate_gbp_m2

    return {
        "element_id": element["element_id"],
        "element_name": element["element_name"],
        "area_m2": round(quantity_m2, 2),
        "rate_gbp_m2": round(rate_gbp_m2, 2),
        "total_cost": round(total_cost, 0),
    }