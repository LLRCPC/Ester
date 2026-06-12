import streamlit as st
import pandas as pd
from engine.breakdown_engine import calculate_cost_breakdown
from engine.unit_engine import convert_area, convert_rate


def render(db: dict):
    st.markdown("""
    <div style="margin-bottom:0.25rem;">
        <span style="font-family:'DM Serif Display',serif;font-size:2rem;color:#0f1f3d;">
            Cost Breakdown
        </span>
    </div>
    <p style="color:#8a96a8;margin-top:0;font-size:0.95rem;">
        Itemised cost plan. Return to <b>Element Areas</b> to adjust inputs — your changes will recalculate instantly.
    </p>
    """, unsafe_allow_html=True)

    # ── Guards ───────────────────────────────────────
    if st.session_state.location == "":
        st.warning("⚠️ Please select a location on the Project Setup page.")
        if st.button("← Project Setup"):
            st.session_state.page_idx = 1
            st.rerun()
        return

    all_zero = not st.session_state.get("element_areas_m2") or all(
        v == 0.0 for v in st.session_state.element_areas_m2.values()
    )
    if all_zero:
        st.warning("⚠️ No element areas entered — go back to Element Areas.")
        if st.button("← Element Areas"):
            st.session_state.page_idx = 3  # Element Areas is now page 3
            st.rerun()
        return

    location = st.session_state.location
    quartile = st.session_state.quartile
    gia      = st.session_state.gia_m2

    # ── Calculate ────────────────────────────────────
    try:
        result = calculate_cost_breakdown(
            db=db,
            location=location,
            quartile=quartile,
            element_areas_m2=st.session_state.element_areas_m2,
        )
    except ValueError as e:
        st.error(f"Calculation error: {e}")
        return

    total_cost = result["total_cost"]
    elements   = result["elements"]

    st.session_state["_last_total_cost"] = total_cost

    # ── Unit toggle (controls the detail table below) ─
    col_toggle, col_spacer = st.columns([2, 6])
    with col_toggle:
        unit = st.radio(
            "Display unit",
            ["m²", "ft²"],
            horizontal=True,
            key="breakdown_unit",
            label_visibility="collapsed",
        )

    # ── Headline metrics — both units always shown ───
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Fit-Out Cost", f"£{total_cost:,.0f}")
    with col2:
        if gia > 0:
            st.metric("£ / m² GIA", f"£{total_cost / gia:,.0f}")
        else:
            st.metric("£ / m² GIA", "— enter GIA")
    with col3:
        if gia > 0:
            gia_ft2 = convert_area(gia, "m2", "ft2")
            st.metric("£ / ft² GIA", f"£{total_cost / gia_ft2:,.2f}")
        else:
            st.metric("£ / ft² GIA", "— enter GIA")
    with col4:
        n = sum(1 for v in st.session_state.element_areas_m2.values() if v > 0)
        st.metric("Elements costed", f"{n} of {len(elements)}")
    with col5:
        proj = st.session_state.project_name or "—"
        st.metric("Project", proj)

    st.caption(f"📍 {location}  ·  {quartile}  ·  table shown in {unit}")
    st.markdown("---")

    # ── Grouped table ────────────────────────────────
    category_map = {e["element_id"]: e.get("category", "General") for e in db["elements"]}
    grouped: dict[str, list] = {}
    for el in elements:
        cat = category_map.get(el["element_id"], "General")
        grouped.setdefault(cat, []).append(el)

    area_col = f"Area ({unit})"
    rate_col = f"Rate (£/{unit})"
    all_rows = []

    for category, cat_els in grouped.items():
        cat_total = sum(el["total_cost"] for el in cat_els)
        rows = []

        for el in cat_els:
            # Both-unit values calculated once per element
            area_m2  = el["area_m2"]
            area_ft2 = convert_area(area_m2, "m2", "ft2")
            rate_m2  = el["rate_gbp_m2"]
            rate_ft2 = convert_rate(rate_m2, "£/m2", "£/ft2")

            # On-screen table follows the toggle
            if unit == "m²":
                area_d = area_m2
                rate_d = rate_m2
            else:
                area_d = area_ft2
                rate_d = rate_ft2

            rows.append({
                "Element":    el["element_name"],
                area_col:     f"{area_d:,.0f}",
                rate_col:     f"£{rate_d:,.2f}",
                "Total Cost": f"£{el['total_cost']:,.0f}",
            })

            # CSV export always carries BOTH units
            all_rows.append({
                "Category":        category,
                "Element":         el["element_name"],
                "Area (m²)":       round(area_m2, 0),
                "Area (ft²)":      round(area_ft2, 0),
                "Rate (£/m²)":     round(rate_m2, 2),
                "Rate (£/ft²)":    round(rate_ft2, 2),
                "Total Cost (£)":  el["total_cost"],
            })

        pct = (cat_total / total_cost * 100) if total_cost > 0 else 0

        st.markdown(f"""
        <div style="display:flex;justify-content:space-between;align-items:baseline;
                    margin:1rem 0 0.4rem;">
            <span style="font-family:'DM Serif Display',serif;font-size:1.1rem;color:#0f1f3d;">
                {category}
            </span>
            <span style="font-size:0.85rem;color:#8a96a8;">
                £{cat_total:,.0f} &nbsp;({pct:.1f}%)
            </span>
        </div>
        """, unsafe_allow_html=True)

        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    st.markdown("---")

    # ── Export ───────────────────────────────────────
    col_dl, col_spacer2 = st.columns([1, 3])
    with col_dl:
        csv = pd.DataFrame(all_rows).to_csv(index=False)
        proj_slug = (st.session_state.project_name or "project").replace(" ", "_")
        st.download_button(
            "⬇️ Download CSV (m² + ft²)",
            data=csv,
            file_name=f"{proj_slug}_{location}_{quartile}.csv".replace(" ", "_"),
            mime="text/csv",
            use_container_width=True,
        )

    # ── Navigation ───────────────────────────────────
    col_back, col_spacer3, col_next = st.columns([1, 4, 1])
    with col_back:
        if st.button("← Element Areas", use_container_width=True):
            st.session_state.page_idx = 3  # back to Element Areas
            st.rerun()
    with col_next:
        if st.button("Save Project →", type="primary", use_container_width=True):
            st.session_state.page_idx = 5  # forward to Save Project
            st.rerun()