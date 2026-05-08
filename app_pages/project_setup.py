import streamlit as st
from engine.unit_engine import convert_area
from engine.postcode_engine import resolve_postcode, format_postcode

QUARTILE_LABELS = {
    "Min": "Minimum",
    "Low quart": "Lower Quartile",
    "Median": "Median",
    "Upper quart": "Upper Quartile",
    "Max": "Maximum",
}


def render():

    # ── Header ─────────────────────────────────────────────
    st.markdown(
        """
        <div style="margin-bottom:0.25rem;">
            <span style="font-family:'DM Serif Display',serif;
                         font-size:2rem;color:#0f1f3d;">
                Project Setup
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Ensure canonical keys exist ───────────────────────
    st.session_state.setdefault("gia_m2", 0.0)
    st.session_state.setdefault("nia_m2", 0.0)
    st.session_state.setdefault("location", "")
    st.session_state.setdefault("postcode", "")
    st.session_state.setdefault("quartile", "Median")
    st.session_state.setdefault("area_unit", "m²")

    col1, col2 = st.columns(2, gap="large")

    # ── LEFT COLUMN — Project Details ─────────────────────
    with col1:
        st.subheader("Project Details")

        st.text_input(
            "Project Name",
            key="project_name",
            placeholder="e.g. 22 Bishopsgate — Floor 14",
        )

        raw_postcode = st.text_input(
            "Project Postcode",
            value=st.session_state.postcode,
            placeholder="e.g. EC1A 1BB",
            help=(
                "Enter any full or partial UK postcode. "
                "We will detect whether the project is in "
                "London, Birmingham, or Manchester."
            ),
            max_chars=8,
        )

        if raw_postcode.strip():
            city, err = resolve_postcode(raw_postcode)

            if city:
                st.session_state.postcode = format_postcode(raw_postcode)
                st.session_state.location = city
                st.success(
                    f"📍 **{st.session_state.postcode}** → detected as **{city}**"
                )
            else:
                st.session_state.postcode = raw_postcode.strip().upper()
                st.session_state.location = ""
                st.error(f"⚠️ {err}")
        else:
            st.session_state.postcode = ""
            st.session_state.location = ""

        quartile_labels = list(QUARTILE_LABELS.values())
        label_to_key    = {v: k for k, v in QUARTILE_LABELS.items()}
        key_to_label    = QUARTILE_LABELS

        selected_label = st.selectbox(
            "Confidence Level",
            quartile_labels,
            index=quartile_labels.index(
                key_to_label.get(st.session_state.quartile, "Median")
            ),
        )
        st.session_state.quartile = label_to_key[selected_label]

    # ── RIGHT COLUMN — Building Areas ─────────────────────
    with col2:
        st.subheader("Building Areas")

        area_unit = st.radio(
            "Display unit",
            ["m²", "ft²"],
            horizontal=True,
            key="area_unit",
        )

        if area_unit == "m²":
            gia_display = st.session_state.gia_m2
        else:
            gia_display = convert_area(st.session_state.gia_m2, "m2", "ft2")

        gia_entered = st.number_input(
            f"Gross Internal Area ({area_unit})",
            min_value=0.0,
            step=10.0 if area_unit == "m²" else 100.0,
            format="%.1f",
            value=float(gia_display),
            key=f"gia_input_{area_unit}",
        )

        st.session_state.gia_m2 = (
            gia_entered if area_unit == "m²"
            else convert_area(gia_entered, "ft2", "m2")
        )

        if st.session_state.gia_m2 > 0:
            if area_unit == "m²":
                st.caption(f"≈ {convert_area(st.session_state.gia_m2, 'm2', 'ft2'):,.0f} ft²")
            else:
                st.caption(f"≈ {st.session_state.gia_m2:,.1f} m²")

        if area_unit == "m²":
            nia_display = st.session_state.nia_m2
        else:
            nia_display = convert_area(st.session_state.nia_m2, "m2", "ft2")

        nia_entered = st.number_input(
            f"Net Internal Area ({area_unit})",
            min_value=0.0,
            step=10.0 if area_unit == "m²" else 100.0,
            format="%.1f",
            value=float(nia_display),
            key=f"nia_input_{area_unit}",
        )

        st.session_state.nia_m2 = (
            nia_entered if area_unit == "m²"
            else convert_area(nia_entered, "ft2", "m2")
        )

        if st.session_state.nia_m2 > 0:
            if area_unit == "m²":
                st.caption(f"≈ {convert_area(st.session_state.nia_m2, 'm2', 'ft2'):,.0f} ft²")
            else:
                st.caption(f"≈ {st.session_state.nia_m2:,.1f} m²")

    # ── Footer ─────────────────────────────────────────────
    st.markdown("---")

    location_resolved = bool(st.session_state.location)

    if location_resolved:
        st.success(
            f"✅ Ready — **{st.session_state.location}** rates will be used. "
            "Continue to Element Areas."
        )
    else:
        st.warning("⚠️ Enter a valid postcode above to continue.")

    # ✅ ADDED DISCLAIMER
    st.caption("⚠️ This price is an estimate, not a formal quote.")

    col_back, _, col_next = st.columns([1, 4, 1])

    with col_back:
        if st.button("← Dashboard"):
            st.session_state.page_idx = 0
            st.rerun()

    with col_next:
        if st.button(
            "Next: Elements →",
            type="primary",
            disabled=not location_resolved,
        ):
            st.session_state.page_idx = 2
            st.rerun()