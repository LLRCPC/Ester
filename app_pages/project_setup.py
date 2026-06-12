"""
project_setup.py
----------------
Page 1: Project Setup — captures the EXISTING building state.

Captures:
- Project name, postcode → location
- Existing building type
- Refurb scope / condition
- GIA, NIA, storeys above + below ground
- Spec level (replaces confidence level / quartile)
- SVG of the existing building as it stands today
"""

import streamlit as st
from engine.unit_engine import convert_area
from engine.postcode_engine import resolve_postcode, format_postcode

SPEC_LEVELS = ["Budget", "Standard", "High Spec", "Bespoke"]

BUILDING_TYPES = [
    "Office",
    "Retail",
    "Residential",
    "Mixed Use",
    "Industrial",
    "Education",
    "Healthcare",
    "Hospitality",
    "Other",
]

REFURB_SCOPES = [
    "Shell Only",
    "Partial Strip Out",
    "Full Strip Out",
    "New Build",
]

SPEC_DESCRIPTIONS = {
    "Budget":    "Cost-led. Functional specification, minimal feature finishes.",
    "Standard":  "Mid-market. Good quality finishes, standard MEP strategy.",
    "High Spec": "Grade A. Premium finishes, advanced MEP, enhanced sustainability.",
    "Bespoke":   "Landmark. Architect-designed, bespoke materials, no cost ceiling.",
}


def _resolve_postcode_callback():
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


def _building_svg(storeys_above: int, storeys_below: int) -> str:
    """
    Render the EXISTING building as it stands today.
    Above ground = slate blue, below ground = grey.
    Max 24 floors shown visually.
    """
    max_vis    = 24
    vis_above  = min(storeys_above, max_vis)
    vis_below  = min(storeys_below, max(0, max_vis - vis_above))
    total_vis  = vis_above + vis_below

    W, H      = 220, 400
    bw        = 110
    floor_h   = min(28, max(10, (H - 80) // max(total_vis, 1)))
    ground_y  = H - 50 - (floor_h * vis_below)
    sy        = ground_y - (floor_h * vis_above)
    sx        = (W - bw) // 2

    floors_svg = ""

    # Above-ground floors
    for i in range(vis_above):
        y = sy + (vis_above - 1 - i) * floor_h
        floors_svg += (
            f'<rect x="{sx}" y="{y}" width="{bw}" height="{floor_h - 1}" '
            f'fill="#B5D4F4" stroke="#185FA5" stroke-width="0.5"/>'
        )
        if floor_h >= 16:
            floors_svg += (
                f'<text x="{sx + 5}" y="{y + floor_h - 5}" '
                f'font-size="9" fill="#0c2e5c" font-family="sans-serif">L{i + 1}</text>'
            )

    # Below-ground floors
    for i in range(vis_below):
        y = ground_y + i * floor_h
        floors_svg += (
            f'<rect x="{sx}" y="{y}" width="{bw}" height="{floor_h - 1}" '
            f'fill="#D0CEC8" stroke="#888780" stroke-width="0.5"/>'
        )
        if floor_h >= 16:
            floors_svg += (
                f'<text x="{sx + 5}" y="{y + floor_h - 5}" '
                f'font-size="9" fill="#555" font-family="sans-serif">B{i + 1}</text>'
            )

    # Overflow label
    overflow = ""
    actual_total = storeys_above + storeys_below
    if actual_total > max_vis:
        overflow = (
            f'<text x="{W // 2}" y="{sy - 10}" text-anchor="middle" '
            f'font-size="9" fill="#888" font-family="sans-serif">'
            f'{actual_total} storeys total — showing {max_vis}</text>'
        )

    # Ground line
    ground_line = (
        f'<rect x="{sx - 20}" y="{ground_y - 2}" width="{bw + 40}" height="3" fill="#555"/>'
        f'<text x="{sx - 22}" y="{ground_y + 10}" '
        f'font-size="9" fill="#555" font-family="sans-serif">GL</text>'
    )

    # Legend
    legend_y = H - 18
    legend = (
        f'<rect x="4" y="{legend_y}" width="9" height="9" fill="#B5D4F4" rx="2"/>'
        f'<text x="16" y="{legend_y + 8}" font-size="8" fill="#555" font-family="sans-serif">Above ground</text>'
        f'<rect x="110" y="{legend_y}" width="9" height="9" fill="#D0CEC8" rx="2"/>'
        f'<text x="122" y="{legend_y + 8}" font-size="8" fill="#555" font-family="sans-serif">Below ground</text>'
    )

    # Title
    title = (
        f'<text x="{W // 2}" y="14" text-anchor="middle" '
        f'font-size="10" fill="#0f1f3d" font-family="sans-serif" font-weight="600">'
        f'Existing Building</text>'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}">'
        f'{title}{overflow}{floors_svg}{ground_line}{legend}'
        f'</svg>'
    )


def render():

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown("""
    <div style="margin-bottom:0.25rem;">
        <span style="font-family:'DM Serif Display',serif;font-size:2rem;color:#0f1f3d;">
            Project Setup
        </span>
    </div>
    <p style="color:#8a96a8;margin-top:0;font-size:0.95rem;">
        Define the <strong>existing building</strong> — what's there today before any works.
    </p>
    """, unsafe_allow_html=True)

    # ── Session defaults ──────────────────────────────────────────────────────
    st.session_state.setdefault("gia_m2",           0.0)
    st.session_state.setdefault("nia_m2",           0.0)
    st.session_state.setdefault("location",         "")
    st.session_state.setdefault("postcode",         "")
    st.session_state.setdefault("spec_level",       "Standard")
    st.session_state.setdefault("area_unit",        "m²")
    st.session_state.setdefault("postcode_touched", False)
    st.session_state.setdefault("_postcode_error",  "")
    st.session_state.setdefault("storeys_above",    0)
    st.session_state.setdefault("storeys_below",    0)
    st.session_state.setdefault("building_type",    "Office")
    st.session_state.setdefault("refurb_scope",     "Full Strip Out")
    st.session_state.setdefault("net_gross_pct",    0.0)

    # ── Layout: left inputs / right visual ───────────────────────────────────
    col_inputs, col_vis = st.columns([1.5, 1], gap="large")

    with col_inputs:

        # ── Project details ───────────────────────────────────────────────────
        st.subheader("Project Details")

        st.text_input(
            "Project Name",
            key="project_name",
            placeholder="e.g. 22 Bishopsgate — Floors 10–14",
        )

        st.text_input(
            "Project Postcode",
            value=st.session_state.postcode,
            placeholder="e.g. EC1A 1BB",
            help="Enter any full UK postcode. We resolve to London, Birmingham, or Manchester.",
            max_chars=8,
            key="postcode_input",
            on_change=_resolve_postcode_callback,
        )

        if st.session_state.postcode_touched:
            if st.session_state.location:
                st.success(
                    f"📍 **{st.session_state.postcode}** → **{st.session_state.location}**"
                )
            else:
                err = st.session_state.get("_postcode_error", "Invalid postcode.")
                st.error(f"⚠️ {err}")

        col_type, col_scope = st.columns(2)
        with col_type:
            st.selectbox(
                "Existing Building Type",
                BUILDING_TYPES,
                index=BUILDING_TYPES.index(st.session_state.building_type),
                key="building_type",
            )
        with col_scope:
            st.selectbox(
                "Refurb Scope",
                REFURB_SCOPES,
                index=REFURB_SCOPES.index(st.session_state.refurb_scope),
                key="refurb_scope",
            )

        st.markdown("---")

        # ── Building areas ────────────────────────────────────────────────────
        st.subheader("Existing Building Areas")

        area_unit = st.radio(
            "Display unit",
            ["m²", "ft²"],
            horizontal=True,
            key="area_unit",
        )

        # GIA
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

        # NIA
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

        # Net:Gross ratio
        gia_m2 = st.session_state.gia_m2
        nia_m2 = st.session_state.nia_m2
        if gia_m2 > 0 and nia_m2 > 0:
            if nia_m2 > gia_m2:
                st.warning("⚠️ NIA cannot exceed GIA.")
                st.session_state.net_gross_pct = 0.0
            else:
                ratio = (nia_m2 / gia_m2) * 100
                st.session_state.net_gross_pct = round(ratio, 1)
                st.metric("Net:Gross Ratio", f"{ratio:.1f}%")

        st.markdown("---")

        # ── Storeys ───────────────────────────────────────────────────────────
        st.subheader("Existing Storeys")

        col_ab, col_bg = st.columns(2)
        with col_ab:
            st.number_input(
                "Storeys above ground",
                min_value=0, max_value=100, step=1,
                key="storeys_above",
            )
        with col_bg:
            st.number_input(
                "Storeys below ground",
                min_value=0, max_value=20, step=1,
                key="storeys_below",
            )

        total = st.session_state.storeys_above + st.session_state.storeys_below
        if total > 0:
            st.caption(
                f"Total: {total} storeys "
                f"({st.session_state.storeys_above} above · "
                f"{st.session_state.storeys_below} below)"
            )

        st.markdown("---")

        # ── Spec level ────────────────────────────────────────────────────────
        st.subheader("Specification Level")
        st.caption("Sets the rate tier used throughout the estimate. Can be overridden per element later.")

        spec = st.radio(
            "Spec level",
            SPEC_LEVELS,
            index=SPEC_LEVELS.index(st.session_state.spec_level),
            horizontal=True,
            key="spec_level",
            label_visibility="collapsed",
        )

        st.info(f"**{spec}** — {SPEC_DESCRIPTIONS[spec]}")

        # Sync the chosen spec level into the rate-band key used by the
        # engines (key is still named "quartile" for saved-project
        # compatibility — its value is now the spec level).
        st.session_state.quartile = spec

    # ── Right column: SVG visualisation ──────────────────────────────────────
    with col_vis:
        st.subheader("Existing Building")
        st.caption("Updates as you enter storeys.")

        above = st.session_state.storeys_above
        below = st.session_state.storeys_below

        if above + below == 0:
            st.markdown(
                "<div style='text-align:center;padding:4rem 1rem;"
                "color:#8a96a8;font-size:0.9rem;'>"
                "Enter storeys to see the building visualisation."
                "</div>",
                unsafe_allow_html=True,
            )
        else:
            svg = _building_svg(above, below)
            st.markdown(svg, unsafe_allow_html=True)

            # Summary card beneath the SVG
            st.markdown(
                f"""
                <div style="background:#fff;border:1px solid #ddd8d0;border-radius:6px;
                            padding:1rem 1.25rem;margin-top:1rem;font-size:0.85rem;
                            line-height:1.8;color:#0f1f3d;">
                    <div style="font-family:'DM Serif Display',serif;font-size:1rem;
                                margin-bottom:0.4rem;">Existing Summary</div>
                    <div>🏢 {st.session_state.building_type} &nbsp;·&nbsp; {st.session_state.refurb_scope}</div>
                    <div>📐 GIA: {st.session_state.gia_m2:,.0f} m²</div>
                    <div>📐 NIA: {st.session_state.nia_m2:,.0f} m²</div>
                    <div>🏗️ {above} storeys above · {below} below</div>
                    <div>⭐ {st.session_state.spec_level} spec</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ── Footer ────────────────────────────────────────────────────────────────
    st.markdown("---")

    location_resolved = bool(st.session_state.location)
    if location_resolved:
        st.success(
            f"✅ Ready — **{st.session_state.location}** rates at "
            f"**{st.session_state.spec_level}** spec will be used."
        )

    st.caption("⚠️ All figures are estimates only and should not be used as a basis for contract or commitment.")

    col_back, _, col_next = st.columns([1, 4, 1])
    with col_back:
        if st.button("← Dashboard", use_container_width=True):
            st.session_state.page_idx = 0
            st.rerun()
    with col_next:
        if st.button(
            "Next: Building Config →",
            type="primary",
            disabled=not location_resolved,
            use_container_width=True,
        ):
            st.session_state.page_idx = 2
            st.rerun()