from engine.cost_engine import calculate_element_cost


def calculate_cost_breakdown(
    *,
    db: dict,
    location: str,
    spec_level: str,
    element_areas_m2: dict,
) -> dict:
    """
    Assemble the full cost breakdown using explicit user-entered areas.

    Parameters
    ----------
    db : dict
        Loaded cost database (elements, quantity_rules, rates)
    location : str
        e.g. "London"
    spec_level : str
        Rate band: Budget, Standard, High Spec, Bespoke.
        (Stored in the database column still named "quartile".)
    element_areas_m2 : dict
        {element_id: area_m2} — all areas in canonical m²

    Returns
    -------
    dict
        {"elements": [...], "total_cost": float}
    """

    results = []
    total_cost = 0.0

    for element in db["elements"]:
        element_id = element["element_id"]

        # FIX: next() without a default raises StopIteration if the rate
        # is missing — guard with None and raise a clear error
        rate_row = next(
            (
                r for r in db["rates"]
                if r["element_id"] == element_id
                and r["location"] == location
                and r["quartile"] == spec_level
            ),
            None,
        )

        if rate_row is None:
            raise ValueError(
                f"No rate found for element '{element_id}' | "
                f"location '{location}' | spec level '{spec_level}'. "
                f"Publish rates for this spec level from the admin pages."
            )

        result = calculate_element_cost(
            db=db,
            element=element,
            rate_row=rate_row,
            element_areas_m2=element_areas_m2,
        )

        total_cost += result["total_cost"]
        results.append(result)

    return {
        "elements": results,
        "total_cost": round(total_cost, 0),
    }
