from engine.cost_engine import calculate_element_cost


def _element_kind(element: dict) -> str:
    """
    Classify an element as 'on_cost', 'count' or 'area' using the element's
    OWN columns (not the rate). This lets us decide what to do even when no
    rate has been published yet for this element.

    Mirrors the same logic used on the Element Areas page so the two pages
    always agree about what each element is.
    """
    rate_unit = (element.get("default_rate_unit") or "").strip()
    basis     = (element.get("area_basis") or "").strip().lower()
    category  = (element.get("category") or "").strip().lower()

    if rate_unit == "%" or category == "on costs":
        return "on_cost"
    if rate_unit == "£/nr" or basis == "nr":
        return "count"
    return "area"


def calculate_cost_breakdown(
    *,
    db: dict,
    location: str,
    spec_level: str,
    element_areas_m2: dict,
) -> dict:
    """
    Assemble the full cost breakdown.

    Three kinds of element are recognised:

      • Area  (£/m2, £/ft2)  — costed as area × rate
      • Count (£/nr)         — costed as number × rate
      • On-cost (%)          — a percentage applied AFTER the works subtotal

    On-costs use "Model A" stacking (sequential / compounding): each on-cost
    is applied to the running total INCLUDING the on-costs already added
    before it. The order is the elements' `sort_order`, so the database
    controls the sequence (e.g. Prelims → OH&P → Risk → Contingency).

    IMPORTANT — missing rates no longer crash the estimate:
      • A work element with a quantity of 0 is simply skipped — it adds
        nothing to the cost, so it doesn't matter if it has no rate.
      • A work element with a quantity but NO published rate is left out of
        the total and its name is reported back in `missing_rates`, so the
        Cost Breakdown page can warn the user instead of erroring.
      • An on-cost (%) with no published rate is likewise skipped and
        reported, rather than stopping the whole calculation.

    Returns
    -------
    dict
        {
            "elements":       [...work items (area + count)...],
            "works_subtotal": float,
            "on_costs":       [{element_id, element_name, pct, base, amount}, ...],
            "total_cost":     float,
            "missing_rates":  [element_name, ...],   # entered but un-priced
        }
    """

    # Work in sort_order so on-costs stack in the intended sequence.
    elements_sorted = sorted(
        db["elements"],
        key=lambda e: e.get("sort_order", 0),
    )

    work_items     = []
    on_cost_defs   = []        # list of (element, pct) preserved in sort order
    missing_rates  = []        # names of entered elements with no rate
    works_subtotal = 0.0

    for element in elements_sorted:
        element_id = element["element_id"]
        kind       = _element_kind(element)

        rate_row = next(
            (
                r for r in db["rates"]
                if r["element_id"] == element_id
                and r["location"] == location
                and r["quartile"] == spec_level
            ),
            None,
        )

        # ── On-costs (%) ──────────────────────────────────────────────────
        if kind == "on_cost":
            if rate_row is None:
                missing_rates.append(element.get("element_name", element_id))
                continue
            on_cost_defs.append((element, float(rate_row["rate"])))
            continue

        # ── Work elements (area or count) ─────────────────────────────────
        quantity = element_areas_m2.get(element_id, 0.0) or 0.0

        # Nothing entered → no cost, no rate needed.
        if quantity <= 0:
            continue

        # Entered, but no rate published → leave out and flag it.
        if rate_row is None:
            missing_rates.append(element.get("element_name", element_id))
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
        "missing_rates":  missing_rates,
    }
