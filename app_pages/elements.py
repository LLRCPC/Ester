import streamlit as st
from engine.unit_engine import convert_area, convert_rate


def _get_rate(db: dict, element_id: str, location: str, quartile: str) -> float | None:
    """Return rate in £/m² for a given element/location/quartile, or None."""
    loc = (location or "").strip().lower()
    qrt = (quartile or "").strip().lower()

    for r in db["rates"]:
        if (
            r["element_id"] == element_id
            and r["location"].strip().lower() == loc
            and r["quartile"].strip().lower() == qrt
        ):
            return convert_rate(
                r["rate"],
                from_unit=r.get("rate_unit", "£/m2"),
                to_unit="£/m2",
            )
    return None


def render(db: dict):
    st.markdown(
        """
        ### Element Areas
        Enter the area for each element.

        - **Public areas** default to **% of GIA**
        - **Cat A fit out** defaults to **100% of NIA (ft²)**
        - Manual override is always available
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

    quartile = st.session_state.get("quartile", "Median")
    gia_m2 = st.session_state.get("gia_m2", 0.0)
    nia_m2 = st.session_state.get("nia_m2", 0.0)

    running_total = 0.0

    # ── Group elements by category ──────────────────
    categories: dict[str, list] = {}
    for el in db["elements"]:
        cat = el.get("category", "General")
        categories.setdefault(cat, []).append(el)

    for category, elements in categories.items():
        st.markdown(f"#### {category}", unsafe_allow_html=True)

        for element in elements:
            element_id = element["element_id"]
            name = element["element_name"]

            # ── Element classification ────────────────
            is_cat_a = element.get("area_basis") == "NIA"
            is_public_area = not is_cat_a  # public / welfare / circulation

            st.session_state.element_areas_m2.setdefault(element_id, 0.0)
            st.session_state.element_initialised.setdefault(element_id, False)

            rate = _get_rate(db, element_id, location, quartile)

            # ── ONE‑TIME Cat A DEFAULT (100% NIA) ──────
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

                    # ── Default input mode ─────────────────
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

                    # ── Cat A: NIA default ────────────────
                    if mode == "NIA default":
                        if nia_m2 <= 0:
                            st.warning("Enter NIA on the Project Setup page.")
                        else:
                            st.caption(
                                f"→ {convert_area(nia_m2, 'm2', 'ft2'):,.0f} ft² (100% of NIA)"
                            )

                    # ── Public areas: % of GIA ────────────
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
                            st.session_state.element_areas_m2[element_id] = (
                                gia_m2 * (pct / 100)
                            )

                    # ── Manual override ───────────────────
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

                # ── Cost preview ───────────────────────
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

    # ── Footer ──────────────────────────────────────
    st.markdown("---")
    col_a, col_b, col_c = st.columns(3)

    with col_a:
        st.metric("Subtotal", f"£{running_total:,.0f}")

    with col_b:
        if gia_m2 > 0 and running_total > 0:
            st.metric("Rate / m² GIA", f"£{running_total / gia_m2:,.0f}")

    with col_c:
        n_entered = sum(
            v > 0 for v in st.session_state.element_areas_m2.values()
        )
        st.metric("Elements entered", f"{n_entered} of {len(db['elements'])}")

    # ── Navigation ──────────────────────────────────
    any_entered = any(
        v > 0 for v in st.session_state.element_areas_m2.values()
    )

    col_back, col_spacer, col_next = st.columns([1, 4, 1])

    with col_back:
        if st.button("← Project Setup", use_container_width=True):
            st.session_state.page_idx = 1
            st.rerun()

    with col_next:
        if st.button(
            "Next: Breakdown →",
            disabled=not any_entered,
            type="primary",
            use_container_width=True,
        ):
            st.session_state.page_idx = 3
            st.rerun()

    if not any_entered:
        st.caption("Enter at least one area to proceed to the cost breakdown.")