import streamlit as st
from engine.unit_engine import convert_area, convert_rate
from engine.session_helpers import resolve_spec


def _get_rate_row(db: dict, element_id: str, location: str, spec_level: str) -> dict | None:
    """Return the raw rate row for an element/location/spec level, or None."""
    loc = (location or "").strip().lower()
    qrt = resolve_spec(spec_level).lower()

    for r in db["rates"]:
        if (
            r["element_id"] == element_id
            and r["location"].strip().lower() == loc
            and r["quartile"].strip().lower() == qrt
        ):
            return r
    return None


def _element_kind(element: dict) -> str:
    """
    Classify an element as 'area', 'count', or 'on_cost' using the element's
    own columns, so it works even before any rates are loaded.
    """
    rate_unit = (element.get("default_rate_unit") or "").strip()
    basis     = (element.get("area_basis") or "").strip().lower()
    category  = (element.get("category") or "").strip().lower()

    if rate_unit == "%" or category == "on costs":
        return "on_cost"
    if rate_unit == "£/nr" or basis == "nr":
        return "count"
    return "area"


def render(db: dict):
    st.markdown(
        """
        ### Element Areas
        Enter the quantity for each element.

        - **Most elements** are entered by area — **% of GIA** or a manual area in **m² / ft²**
        - **Cat A fit out** defaults to **100% of NIA**
        - **Per-number items** (lifts, WCs, stairs) are entered as a **count**
        - **On Costs** (prelims, OH&P, risk, contingency) are *not* entered here —
          they are percentages applied automatically on the Cost Breakdown
        """,
        unsafe_allow_html=True,
    )

    # ── Guards ───────────────────────────────────────
    location = st.session_state.get("location", "")
    areas = st.session_state.get("element_areas_m2", {})

    if not location and not any(v > 0 for v in areas.values()):
        st.warning("⚠️ Please select a location on the Project Setup page first.")
        if st.button("← Project Setup"):
            st.session_state.page_idx = 1
            st.rerun()
        return

    # ── Session defaults ────────────────────────────
    st.session_state.setdefault("element_areas_m2", {})
    st.session_state.setdefault("element_initialised", {})

    spec_level = resolve_spec(st.session_state.get("quartile", "Standard"))

    # Use proposed areas (after extension) if available, otherwise fall back
    # to existing building areas from Project Setup.
    gia_m2 = st.session_state.get("proposed_gia_m2") or st.session_state.get("gia_m2", 0.0)
    nia_m2 = st.session_state.get("proposed_nia_m2") or st.session_state.get("nia_m2", 0.0)

    running_total = 0.0

    # ── Group elements by category (on-cost elements are not shown here) ──
    categories: dict[str, list] = {}
    for el in db["elements"]:
        if _element_kind(el) == "on_cost":
            continue
        cat = el.get("category", "General")
        categories.setdefault(cat, []).append(el)

    # How many elements are actually shown on this page (excludes on-costs)
    num_displayable = sum(len(v) for v in categories.values())

    for category, elements in categories.items():
        st.markdown(f"#### {category}", unsafe_allow_html=True)

        for element in elements:
            element_id = element["element_id"]
            name = element["element_name"]
            kind = _element_kind(element)

            st.session_state.element_areas_m2.setdefault(element_id, 0.0)
            st.session_state.element_initialised.setdefault(element_id, False)

            rate_row = _get_rate_row(db, element_id, location, spec_level)

            # ═══════════════════════════════════════════════════════════════
            # COUNT ELEMENTS (£/nr) — entered as a plain number
            # ═══════════════════════════════════════════════════════════════
            if kind == "count":
                unit_rate = rate_row["rate"] if rate_row else None
                current   = st.session_state.element_areas_m2[element_id]
                cost_hint = (
                    f" — £{current * unit_rate:,.0f}"
                    if (unit_rate and current > 0) else ""
                )

                with st.expander(f"{name}{cost_hint}"):
                    col_input, col_cost = st.columns([3, 1])

                    with col_input:
                        count = st.number_input(
                            f"Number of — {name}",
                            min_value=0,
                            step=1,
                            format="%d",
                            value=int(current),
                        )
                        st.session_state.element_areas_m2[element_id] = float(count)

                    with col_cost:
                        if rate_row is None:
                            st.caption("No rate found")
                        elif count == 0:
                            st.markdown("—")
                        else:
                            el_cost = count * unit_rate
                            running_total += el_cost
                            st.markdown(f"**£{el_cost:,.0f}**")
                            st.caption(f"£{unit_rate:,.0f}/nr")
                continue

            # ═══════════════════════════════════════════════════════════════
            # AREA ELEMENTS (£/m² or £/ft²) — unchanged behaviour
            # ═══════════════════════════════════════════════════════════════
            is_cat_a = element.get("area_basis") == "NIA"

            # Convert the stored rate to £/m² for the area maths
            rate = None
            if rate_row is not None:
                rate = convert_rate(
                    rate_row["rate"],
                    from_unit=rate_row.get("rate_unit", "£/m2"),
                    to_unit="£/m2",
                )

            # ── ONE-TIME Cat A DEFAULT (100% NIA) ──────
            if (
                is_cat_a
                and nia_m2 > 0
                and not st.session_state.element_initialised[element_id]
            ):
                st.session_state.element_areas_m2[element_id] = nia_m2
                st.session_state.element_initialised[element_id] = True

            current_m2 = st.session_state.element_areas_m2[element_id]
            cost_hint = (
                f" — £{current_m2 * rate:,.0f}"
                if rate and current_m2 > 0
                else ""
            )

            with st.expander(f"{name}{cost_hint}"):
                col_input, col_cost = st.columns([3, 1])

                with col_input:
                    mode_key = f"{element_id}_mode"

                    if is_cat_a:
                        st.session_state.setdefault(mode_key, "NIA default")
                        modes = ["NIA default", "Manual area"]
                    else:
                        st.session_state.setdefault(mode_key, "% of GIA")
                        modes = ["% of GIA", "Manual area"]

                    mode = st.radio(
                        "Input method",
                        modes,
                        horizontal=True,
                        key=mode_key,
                    )

                    if mode == "NIA default":
                        if nia_m2 <= 0:
                            st.warning("Enter NIA on the Project Setup page.")
                        else:
                            st.caption(
                                f"→ {nia_m2:,.0f} m² / "
                                f"{convert_area(nia_m2, 'm2', 'ft2'):,.0f} ft² "
                                f"(100% of NIA)"
                            )

                    elif mode == "% of GIA":
                        pct_key = f"{element_id}_pct"
                        pct = st.number_input(
                            "Percentage of GIA",
                            min_value=0.0,
                            max_value=200.0,
                            step=1.0,
                            format="%.1f",
                            key=pct_key,
                        )
                        if pct > 0 and gia_m2 > 0:
                            calc_m2 = gia_m2 * (pct / 100)
                            st.session_state.element_areas_m2[element_id] = calc_m2
                            st.caption(
                                f"→ {calc_m2:,.0f} m² / "
                                f"{convert_area(calc_m2, 'm2', 'ft2'):,.0f} ft²"
                            )

                    else:
                        unit_key = f"{element_id}_unit"
                        st.session_state.setdefault(unit_key, "m²")

                        unit = st.radio(
                            "Unit",
                            ["m²", "ft²"],
                            horizontal=True,
                            key=unit_key,
                        )

                        display_val = (
                            current_m2
                            if unit == "m²"
                            else convert_area(current_m2, "m2", "ft2")
                        )

                        entered = st.number_input(
                            f"Area ({unit})",
                            min_value=0.0,
                            step=10.0 if unit == "m²" else 100.0,
                            format="%.1f",
                            value=display_val,
                        )

                        st.session_state.element_areas_m2[element_id] = (
                            entered
                            if unit == "m²"
                            else convert_area(entered, "ft2", "m2")
                        )

                        # Show the equivalent in the other unit
                        saved_m2 = st.session_state.element_areas_m2[element_id]
                        if saved_m2 > 0:
                            alt = (
                                f"{convert_area(saved_m2, 'm2', 'ft2'):,.0f} ft²"
                                if unit == "m²"
                                else f"{saved_m2:,.0f} m²"
                            )
                            st.caption(f"≈ {alt}")

                with col_cost:
                    area_m2 = st.session_state.element_areas_m2[element_id]

                    if rate is None:
                        st.caption("No rate found")
                    elif area_m2 == 0:
                        st.markdown("—")
                    else:
                        el_cost = area_m2 * rate
                        running_total += el_cost
                        st.markdown(f"**£{el_cost:,.0f}**")
                        rate_ft2 = convert_rate(rate, "£/m2", "£/ft2")
                        st.caption(
                            f"£{rate:,.0f}/m² · £{rate_ft2:,.2f}/ft²"
                        )

    # ── Footer ──────────────────────────────────────
    st.markdown("---")
    st.caption(
        "Subtotal below is construction works only. On Costs "
        "(prelims, OH&P, risk, contingency) are added on the Cost Breakdown."
    )
    col_a, col_b, col_c, col_d = st.columns(4)

    with col_a:
        st.metric("Works subtotal", f"£{running_total:,.0f}")
    with col_b:
        if gia_m2 > 0 and running_total > 0:
            st.metric("Rate / m² GIA", f"£{running_total / gia_m2:,.0f}")
    with col_c:
        if gia_m2 > 0 and running_total > 0:
            gia_ft2 = convert_area(gia_m2, "m2", "ft2")
            st.metric("Rate / ft² GIA", f"£{running_total / gia_ft2:,.2f}")
    with col_d:
        n_entered = sum(v > 0 for v in st.session_state.element_areas_m2.values())
        st.metric("Elements entered", f"{n_entered} of {num_displayable}")

    # ── Navigation ──────────────────────────────────
    any_entered = any(v > 0 for v in st.session_state.element_areas_m2.values())

    col_back, col_spacer, col_next = st.columns([1, 4, 1])

    with col_back:
        if st.button("← Building Config", use_container_width=True):
            st.session_state.page_idx = 3  # back to Building Overview
            st.rerun()

    with col_next:
        if st.button(
            "Next: Breakdown →",
            disabled=not any_entered,
            type="primary",
            use_container_width=True,
        ):
            st.session_state.page_idx = 5  # forward to Cost Breakdown
            st.rerun()

    if not any_entered:
        st.caption("Enter at least one quantity to proceed to the cost breakdown.")