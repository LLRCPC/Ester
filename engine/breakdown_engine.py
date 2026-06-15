from engine.cost_engine import calculate_element_cost


def calculate_cost_breakdown(
    *,
    db: dict,
    location: str,
    spec_level: str,
    element_areas_m2: dict,
) -> dict:
    """
    Assemble the full cost breakdown.

    Three kinds of element are recognised, by the rate's `rate_unit`:

      • Area  (£/m2, £/ft2)  — costed as area × rate
      • Count (£/nr)         — costed as number × rate
      • On-cost (%)          — a percentage applied AFTER the works subtotal

    On-costs use "Model A" stacking (sequential / compounding): each on-cost
    is applied to the running total INCLUDING the on-costs already added
    before it. The order is the elements' `sort_order`, so the database
    controls the sequence (e.g. Prelims → OH&P → Risk → Contingency).

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
        {element_id: value} — area in m² for area elements, a count for
        count elements. On-cost elements take no entry.

    Returns
    -------
    dict
        {
            "elements":       [...work items (area + count)...],
            "works_subtotal": float,   # construction works only
            "on_costs":       [{element_id, element_name, pct, base, amount}, ...],
            "total_cost":     float,   # grand total incl. on-costs
        }
    """

    # Work in sort_order so on-costs stack in the intended sequence.
    elements_sorted = sorted(
        db["elements"],
        key=lambda e: e.get("sort_order", 0),
    )

    work_items   = []
    on_cost_defs = []          # list of (element, pct) preserved in sort order
    works_subtotal = 0.0

    for element in elements_sorted:
        element_id = element["element_id"]

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

        rate_unit = rate_row.get("rate_unit", "£/m2")

        # On-costs are not works — collect them to apply after the subtotal.
        if rate_unit == "%":
            on_cost_defs.append((element, float(rate_row["rate"])))
            continue

        result = calculate_element_cost(
            db=db,
            element=element,
            rate_row=rate_row,
            element_areas_m2=element_areas_m2,
        )
        works_subtotal += result["total_cost"]
        work_items.append(result)

    # ── Apply on-costs — Model A (sequential / compounding) ────────────────
    running  = works_subtotal
    on_costs = []
    for element, pct in on_cost_defs:
        base   = running                       # includes earlier on-costs
        amount = round(base * pct / 100.0, 0)
        running += amount
        on_costs.append({
            "element_id":   element["element_id"],
            "element_name": element["element_name"],
            "pct":          pct,
            "base":         round(base, 0),
            "amount":       amount,
        })

    return {
        "elements":       work_items,
        "works_subtotal": round(works_subtotal, 0),
        "on_costs":       on_costs,
        "total_cost":     round(running, 0),
    }