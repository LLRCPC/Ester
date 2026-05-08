def calculate_quantity(
    *,
    element_id: str,
    element_areas_m2: dict,
) -> float:
    """
    Return canonical area for the element (m²).
    """

    area = element_areas_m2.get(element_id, 0.0)

    if area < 0:
        raise ValueError("Area cannot be negative")

    return area