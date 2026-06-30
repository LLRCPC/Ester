import streamlit as st
from engine.project_store import save_project
from engine.unit_engine import convert_area


def render(db: dict):
    st.markdown("""
    <div style="margin-bottom:0.25rem;">
        <span style="font-family:'DM Serif Display',serif;font-size:2rem;color:#0f1f3d;">
            Save Project
        </span>
    </div>
    <p style="color:#8a96a8;margin-top:0;font-size:0.95rem;">
        Save this estimate to your project library. You can reload and edit it at any time.
    </p>
    """, unsafe_allow_html=True)

    st.markdown("---")

    total_cost = st.session_state.get("_last_total_cost", 0)
    gia        = st.session_state.gia_m2
    location   = st.session_state.location
    quartile   = st.session_state.quartile
    postcode   = st.session_state.get("postcode", "")

    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.subheader("Project Details")

        # IMPORTANT: do NOT use key="project_name" here.
        # That key is owned by the text_input widget on project_setup.py.
        current_name = st.session_state.get("project_name", "")

        edited_name = st.text_input(
            "Project Name",
            value=current_name,
            help="Pre-filled from Project Setup. Rename here if needed before saving.",
            key="save_project_name_input",
        )

        if edited_name != current_name:
            st.session_state["project_name"] = edited_name

        if postcode and location:
            st.caption(f"📍 {postcode}  ({location})  ·  {quartile}")
        elif location:
            st.caption(f"📍 {location}  ·  {quartile}")

        # Areas — always shown in both units
        if gia > 0:
            gia_ft2 = convert_area(gia, "m2", "ft2")
            st.caption(f"GIA: {gia:,.0f} m²  ·  {gia_ft2:,.0f} ft²")
        if st.session_state.nia_m2 > 0:
            nia_m2  = st.session_state.nia_m2
            nia_ft2 = convert_area(nia_m2, "m2", "ft2")
            st.caption(f"NIA: {nia_m2:,.0f} m²  ·  {nia_ft2:,.0f} ft²")

    with col2:
        st.subheader("Cost Summary")
        st.metric("Total Fit-Out Cost", f"£{total_cost:,.0f}")
        if gia > 0 and total_cost > 0:
            m_a, m_b = st.columns(2)
            with m_a:
                st.metric("£ / m² GIA", f"£{total_cost / gia:,.0f}")
            with m_b:
                gia_ft2 = convert_area(gia, "m2", "ft2")
                st.metric("£ / ft² GIA", f"£{total_cost / gia_ft2:,.2f}")
        n = sum(1 for v in st.session_state.element_areas_m2.values() if v > 0)
        st.caption(f"{n} element(s) costed")

    st.markdown("---")

    save_name = st.session_state.get("project_name", "")
    can_save  = bool(save_name and location)

    if not can_save:
        st.warning("⚠️ A project name and a valid postcode are required before saving.")

    col_save, col_spacer = st.columns([1, 3])
    with col_save:
        if st.button(
            "💾  Save to Library",
            disabled=not can_save,
            type="primary",
            use_container_width=True,
        ):
            # Everything the cost engine doesn't strictly need, but which we
            # want restored when the project is reopened. Without this, a
            # project built with a vertical extension would lose its proposed
            # areas on reload and the £/m² figures would no longer match.
            project_meta = {
                "proposed_gia_m2":        st.session_state.get("proposed_gia_m2", 0.0),
                "proposed_nia_m2":        st.session_state.get("proposed_nia_m2", 0.0),
                "proposed_net_gross_pct": st.session_state.get("proposed_net_gross_pct", 0.0),
                "has_extension":          st.session_state.get("has_extension", False),
                "ext_new_storeys":        st.session_state.get("ext_new_storeys", 0),
                "ext_new_gia_m2":         st.session_state.get("ext_new_gia_m2", 0.0),
                "ext_new_nia_m2":         st.session_state.get("ext_new_nia_m2", 0.0),
                "ext_lifts":              st.session_state.get("ext_lifts", 0),
                "ext_stairs":             st.session_state.get("ext_stairs", 0),
                "ext_roof_works":         st.session_state.get("ext_roof_works", False),
                "ext_structural_storeys": st.session_state.get("ext_structural_storeys", 0),
                "storeys_above":          st.session_state.get("storeys_above", 0),
                "storeys_below":          st.session_state.get("storeys_below", 0),
                "spec_level":             st.session_state.get("spec_level", "Standard"),
                "building_type":          st.session_state.get("building_type", "Office"),
                "refurb_scope":           st.session_state.get("refurb_scope", "Full Strip Out"),
            }

            project_data = {
                "project_id":       st.session_state.project_id,
                "project_name":     st.session_state.project_name,
                "postcode":         postcode,
                "gia_m2":           st.session_state.gia_m2,
                "nia_m2":           st.session_state.nia_m2,
                "location":         st.session_state.location,
                "quartile":         st.session_state.quartile,
                "element_areas_m2": st.session_state.element_areas_m2,
                "total_cost":       total_cost,
                "project_meta":     project_meta,
            }
            project_id = save_project(project_data)
            st.session_state.project_id = project_id

            st.success(f"✅ **{st.session_state.project_name}** saved to library.")
            st.session_state.page_idx = 0
            st.rerun()

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    col_back, col_spacer2, col_dash = st.columns([1, 4, 1])
    with col_back:
        if st.button("← Breakdown", use_container_width=True):
            st.session_state.page_idx = 5  # back to Cost Breakdown
            st.rerun()
    with col_dash:
        if st.button("🏠 Dashboard", use_container_width=True):
            st.session_state.page_idx = 0
            st.rerun()