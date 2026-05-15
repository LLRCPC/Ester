import streamlit as st
from engine.unit_engine import convert_area
from engine.postcode_engine import resolve_postcode, format_postcode

QUARTILE_LABELS = {
    "Min":         "Minimum",
    "Low quart":   "Lower Quartile",
    "Median":      "Median",
    "Upper quart": "Upper Quartile",
    "Max":         "Maximum",
}


def _resolve_postcode_callback():
    """
    Called automatically when the postcode field changes.
    Resolves the postcode and writes location into session state
    without the user needing to press Enter.
    """
    raw = st.session_state.get("postcode_input", "").strip()
    st.session_state["postcode_touched"] = True

    if not raw:
        st.session_state.postcode = ""
        st.session_state.location = ""
        return

    city, err = resolve_postcode(raw)
    if city:
        st.session_state.postcode = format_postcode(raw)
        st.session_state.location = city
    else:
        st.session_state.postcode = raw.upper()
        st.session_state.location = ""
        st.session_state["_postcode_error"] = err


def render():

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown(
        """
        <div style="margin-bottom:0.25rem;">
            <span style="font-family:'DM Serif Display',serif;
                         font-size:2rem;color:#0f1f3d;">
                Project Setup
            </span>
        </div>
        <p style="color:#8a96a8;margin-top:0;font-size:0.95rem;">
            Define the project location, scope, and building areas.
        </p>
        """,
        unsafe_allow_html=True,
    )

    # ── Session defaults ──────────────────────────────────────────────────────
    st.session_state.setdefault("gia_m2", 0.0)
    st.session_state.setdefault("nia_m2", 0.0)
    st.session_state.setdefault("location", "")
    st.session_state.setdefault("postcode", "")
    st.session_state.setdefault("quartile", "Median")
    st.session_state.setdefault("area_unit", "m²")
    st.session_state.setdefault("postcode_touched", False)
    st.session_state.setdefault("_postcode_error", "")
    st.session_state.setdefault("net_gross_pct", 0.0)
    st.session_state.setdefault("storeys_above", 0)
    st.session_state.setdefault("storeys_below", 0)
    st.session_state.setdefault("fitout_scope", "Whole building")

    col1, col2 = st.columns(2, gap="large")

    # ── LEFT COLUMN — Project Details ─────────────────────────────────────────
    with col1:
        st.subheader("Project Details")

        st.text_input(
            "Project Name",
            key="project_name",
            placeholder="e.g. 22 Bishopsgate — Floors 10–14",
        )

        # Postcode — resolves on_change, no Enter needed
        st.text_input(
            "Project Postcode",
            value=st.session_state.postcode,
            placeholder="e.g. EC1A 1BB",
            help=(
                "Enter any full UK postcode. "
                "We will detect whether the project is in "
                "London, Birmingham, or Manchester."
            ),
            max_chars=8,
            key="postcode_input",
            on_change=_resolve_postcode_callback,
        )

        # Postcode status — only shown after user has typed something
        if st.session_state.postcode_touched:
            if st.session_state.location:
                st.success(
                    f"📍 **{st.session_state.postcode}** → **{st.session_state.location}**"
                )
            else:
                err = st.session_state.get("_postcode_error", "Invalid postcode.")
                st.error(f"⚠️ {err}")

        # Confidence level
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

        st.markdown("---")

        # ── Fitout scope ──────────────────────────────────────────────────────
        st.subheader("Fit-Out Scope")

        scope = st.radio(
            "What is being fitted out?",
            ["Whole building", "Specific floors only"],
            index=["Whole building", "Specific floors only"].index(
                st.session_state.fitout_scope
            ),
            horizontal=True,
            key="fitout_scope",
        )

        if scope == "Specific floors only":
            st.caption(
                "Enter the GIA and NIA for the floors being fitted out only, "
                "not the whole building."
            )
        else:
            st.caption(
                "GIA and NIA should reflect the total building area."
            )

    # ── RIGHT COLUMN — Building Areas ─────────────────────────────────────────
    with col2:
        st.subheader("Building Areas")

        area_unit = st.radio(
            "Display unit",
            ["m²", "ft²"],
            horizontal=True,
            key="area_unit",
        )

        # ── GIA ───────────────────────────────────────────────────────────────
        gia_display = (
            st.session_state.gia_m2 if area_unit == "m²"
            else convert_area(st.session_state.gia_m2, "m2", "ft2")
        )

        gia_entered = st.number_input(
            f"Gross Internal Area ({area_unit})",
            min_value=0.0,
            step=10.0 if area_unit == "m²" else 100.0,
            format="%.0f",
            value=float(gia_display),
            key=f"gia_input_{area_unit}",
        )

        st.session_state.gia_m2 = (
            gia_entered if area_unit == "m²"
            else convert_area(gia_entered, "ft2", "m2")
        )

        if st.session_state.gia_m2 > 0:
            alt = (
                f"{convert_area(st.session_state.gia_m2, 'm2', 'ft2'):,.0f} ft²"
                if area_unit == "m²"
                else f"{st.session_state.gia_m2:,.0f} m²"
            )
            st.caption(f"≈ {alt}")

        # ── NIA ───────────────────────────────────────────────────────────────
        nia_display = (
            st.session_state.nia_m2 if area_unit == "m²"
            else convert_area(st.session_state.nia_m2, "m2", "ft2")
        )

        nia_entered = st.number_input(
            f"Net Internal Area ({area_unit})",
            min_value=0.0,
            step=10.0 if area_unit == "m²" else 100.0,
            format="%.0f",
            value=float(nia_display),
            key=f"nia_input_{area_unit}",
        )

        st.session_state.nia_m2 = (
            nia_entered if area_unit == "m²"
            else convert_area(nia_entered, "ft2", "m2")
        )

        if st.session_state.nia_m2 > 0:
            alt = (
                f"{convert_area(st.session_state.nia_m2, 'm2', 'ft2'):,.0f} ft²"
                if area_unit == "m²"
                else f"{st.session_state.nia_m2:,.0f} m²"
            )
            st.caption(f"≈ {alt}")

        # ── NIA:GIA ratio ─────────────────────────────────────────────────────
        gia_m2 = st.session_state.gia_m2
        nia_m2 = st.session_state.nia_m2

        if gia_m2 > 0 and nia_m2 > 0:
            if nia_m2 > gia_m2:
                st.warning("⚠️ NIA cannot exceed GIA — please check your inputs.")
                st.session_state.net_gross_pct = 0.0
            else:
                ratio = (nia_m2 / gia_m2) * 100
                st.session_state.net_gross_pct = round(ratio, 1)
                st.metric(
                    "Net:Gross Ratio",
                    f"{ratio:.1f}%",
                    help=(
                        "NIA as a percentage of GIA. "
                        "Used as the Cat A fit-out area basis in Element Areas."
                    ),
                )
        else:
            st.session_state.net_gross_pct = 0.0

        st.markdown("---")

        # ── Storeys ───────────────────────────────────────────────────────────
        st.subheader("Building Storeys")
        st.caption("These feed into Building Configuration automatically.")

        col_ab, col_bg = st.columns(2)

        with col_ab:
            storeys_above = st.number_input(
                "Storeys above ground",
                min_value=0,
                max_value=100,
                step=1,
                key="storeys_above",
            )

        with col_bg:
            storeys_below = st.number_input(
                "Storeys below ground",
                min_value=0,
                max_value=20,
                step=1,
                key="storeys_below",
            )

        total_storeys = storeys_above + storeys_below
        if total_storeys > 0:
            st.caption(
                f"Total storeys: {total_storeys}  "
                f"({storeys_above} above + {storeys_below} below ground)"
            )

    # ── Footer ────────────────────────────────────────────────────────────────
    st.markdown("---")

    location_resolved = bool(st.session_state.location)

    if location_resolved:
        st.success(
            f"✅ Ready — **{st.session_state.location}** rates will be used. "
            "Continue to Building Configuration."
        )

    st.caption("⚠️ All figures are estimates only and should not be used as a basis for contract or commitment.")

    col_back, _, col_next = st.columns([1, 4, 1])

    with col_back:
        if st.button("← Dashboard"):
            st.session_state.page_idx = 0
            st.rerun()

    with col_next:
        if st.button(
            "Next: Building Config →",
            type="primary",
            disabled=not location_resolved,
        ):
            st.session_state.page_idx = 2
            st.rerun()