"""
project_setup.py
----------------
Page 1: Project Setup — captures the EXISTING building state.

Captures:
- Project name, postcode → location
- Existing building type
- Refurb scope / condition
- GIA, NIA, storeys above + below ground
- Floor-to-floor height + building perimeter → auto-calculated facade area
- Roof area
- Number of WC cores and lifts
- Spec level
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


def _calc_facade_m2(perimeter_m: float, floor_to_floor_m: float, storeys_above: int) -> float:
    """
    Calculate total facade area in m².
    Formula: perimeter × floor-to-floor height × number of above-ground storeys.
    Returns 0.0 if any input is missing.
    """
    if perimeter_m > 0 and floor_to_floor_m > 0 and storeys_above > 0:
        return round(perimeter_m * floor_to_floor_m * storeys_above, 0)
    return 0.0


def _building_svg(storeys_above: int, storeys_below: int, floor_to_floor_m: float) -> str:
    """
    Render the EXISTING building as it stands today.
    Above ground = slate blue, below ground = grey.
    Floor height is proportional when floor-to-floor height is entered.
    Max 24 floors shown visually.
    """
    max_vis    = 24
    vis_above  = min(storeys_above, max_vis)
    vis_below  = min(storeys_below, max(0, max_vis - vis_above))
    total_vis  = vis_above + vis_below

    W, H      = 220, 400
    bw        = 110

    # If we have a real floor height, scale floors proportionally
    # (cap so extreme heights don't overflow the canvas)
    if floor_to_floor_m > 0 and total_vis > 0:
        # Scale: treat 4m as a "standard" floor height → 24px
        raw_floor_h = int((floor_to_floor_m / 4.0) * 24)
        floor_h = min(40, max(10, raw_floor_h))
        # If the total scaled height would overflow, fall back to auto-fit
        if floor_h * total_vis > (H - 80):
            floor_h = min(28, max(10, (H - 80) // max(total_vis, 1)))
    else:
        floor_h = min(28, max(10, (H - 80) // max(total_vis, 1)))

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

    # Floor-to-floor height annotation on the right side of the building
    # Shows a small dimension line for one floor if height is known
    height_annotation = ""
    if floor_to_floor_m > 0 and vis_above > 0:
        ann_x  = sx + bw + 6
        ann_y1 = ground_y - floor_h          # bottom of L1
        ann_y2 = ground_y - (floor_h * 2)    # top of L1 (= bottom of L2)
        mid_y  = (ann_y1 + ann_y2) // 2
        height_annotation = (
            # vertical line
            f'<line x1="{ann_x + 4}" y1="{ann_y1}" x2="{ann_x + 4}" y2="{ann_y2}" '
            f'stroke="#888" stroke-width="0.8"/>'
            # top tick
            f'<line x1="{ann_x + 1}" y1="{ann_y2}" x2="{ann_x + 7}" y2="{ann_y2}" '
            f'stroke="#888" stroke-width="0.8"/>'
            # bottom tick
            f'<line x1="{ann_x + 1}" y1="{ann_y1}" x2="{ann_x + 7}" y2="{ann_y1}" '
            f'stroke="#888" stroke-width="0.8"/>'
            # label
            f'<text x="{ann_x + 10}" y="{mid_y + 3}" font-size="8" fill="#555" '
            f'font-family="sans-serif">{floor_to_floor_m:.1f}m</text>'
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
        f'{title}{overflow}{floors_svg}{ground_line}{height_annotation}{legend}'
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
    st.session_state.setdefault("gia_m2",              0.0)
    st.session_state.setdefault("nia_m2",              0.0)
    st.session_state.setdefault("location",            "")
    st.session_state.setdefault("postcode",            "")
    st.session_state.setdefault("spec_level",          "Standard")
    st.session_state.setdefault("area_unit",           "m²")
    st.session_state.setdefault("postcode_touched",    False)
    st.session_state.setdefault("_postcode_error",     "")
    st.session_state.setdefault("storeys_above",       0)
    st.session_state.setdefault("storeys_below",       0)
    st.session_state.setdefault("building_type",       "Office")
    st.session_state.setdefault("refurb_scope",        "Full Strip Out")
    st.session_state.setdefault("net_gross_pct",       0.0)
    # New geometry fields
    st.session_state.setdefault("floor_to_floor_m",   0.0)
    st.session_state.setdefault("perimeter_m",         0.0)
    st.session_state.setdefault("facade_area_m2",      0.0)
    st.session_state.setdefault("roof_area_m2",        0.0)
    # New building features
    st.session_state.setdefault("num_wc_cores",        0)
    st.session_state.setdefault("num_lifts",           0)

    # ── Layout: left inputs / right visual ───────────────────────────────────
    col_inputs, col_vis = st.columns([1.5, 1], gap="large")

    with col_inputs:

        # ── Section 1: Project Details ────────────────────────────────────────
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

        # ── Section 2: Building Areas ─────────────────────────────────────────
        st.subheader("Building Areas")

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

        # ── Section 3: Building Geometry ──────────────────────────────────────
        st.subheader("Building Geometry")
        st.caption(
            "Used to calculate facade area automatically. "
            "Facade area = perimeter × floor-to-floor height × storeys above ground."
        )

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

        col_h, col_p = st.columns(2)
        with col_h:
            ftf = st.number_input(
                "Floor-to-floor height (m)",
                min_value=0.0,
                max_value=20.0,
                step=0.1,
                format="%.2f",
                value=float(st.session_state.floor_to_floor_m),
                key="floor_to_floor_input",
                help="The height from finished floor level to the floor above. "
                     "Typically 3.5m–4.5m for commercial offices.",
            )
            st.session_state.floor_to_floor_m = ftf

        with col_p:
            perim = st.number_input(
                "Building perimeter (m)",
                min_value=0.0,
                step=1.0,
                format="%.1f",
                value=float(st.session_state.perimeter_m),
                key="perimeter_input",
                help="The total distance around the outside of the building footprint.",
            )
            st.session_state.perimeter_m = perim

        # Auto-calculate and display facade area
        facade_m2 = _calc_facade_m2(
            st.session_state.perimeter_m,
            st.session_state.floor_to_floor_m,
            st.session_state.storeys_above,
        )
        st.session_state.facade_area_m2 = facade_m2

        if facade_m2 > 0:
            st.success(
                f"🏗️ **Calculated facade area: {facade_m2:,.0f} m²** "
                f"({st.session_state.perimeter_m:.1f}m × "
                f"{st.session_state.floor_to_floor_m:.2f}m × "
                f"{st.session_state.storeys_above} storeys)"
            )
        elif st.session_state.storeys_above > 0:
            st.info("💡 Enter floor-to-floor height and perimeter above to calculate facade area.")

        st.markdown("---")

        # ── Section 4: Building Features ──────────────────────────────────────
        st.subheader("Building Features")
        st.caption("Used to price WC cores, lift lobbies, and roof works.")

        col_wc, col_lift = st.columns(2)
        with col_wc:
            st.number_input(
                "Number of WC cores",
                min_value=0,
                max_value=50,
                step=1,
                key="num_wc_cores",
                help="A WC core typically contains male, female and accessible WCs on one floor. "
                     "Enter the total number of cores across all floors.",
            )
        with col_lift:
            st.number_input(
                "Number of lifts",
                min_value=0,
                max_value=50,
                step=1,
                key="num_lifts",
                help="Total number of lift cars in the building.",
            )

        # Roof area — defaults to GIA ÷ storeys (i.e. one floor plate) if not set
        roof_default = 0.0
        if st.session_state.gia_m2 > 0 and st.session_state.storeys_above > 0:
            roof_default = round(st.session_state.gia_m2 / st.session_state.storeys_above, 0)

        # Only apply the default if the user hasn't entered anything yet
        if st.session_state.roof_area_m2 == 0.0 and roof_default > 0:
            st.session_state.roof_area_m2 = roof_default

        roof_display = (
            st.session_state.roof_area_m2 if area_unit == "m²"
            else convert_area(st.session_state.roof_area_m2, "m2", "ft2")
        )
        roof_entered = st.number_input(
            f"Roof area ({area_unit})",
            min_value=0.0,
            step=10.0 if area_unit == "m²" else 100.0,
            format="%.0f",
            value=float(roof_display),
            key=f"roof_input_{area_unit}",
            help="The plan area of the roof. Defaults to GIA ÷ storeys (one floor plate) "
                 "— override if the roof footprint differs.",
        )
        st.session_state.roof_area_m2 = (
            roof_entered if area_unit == "m²"
            else convert_area(roof_entered, "ft2", "m2")
        )

        if st.session_state.roof_area_m2 > 0 and roof_default > 0:
            if abs(st.session_state.roof_area_m2 - roof_default) < 1:
                st.caption(f"💡 Defaulted to one floor plate ({roof_default:,.0f} m²). Override if needed.")

        st.markdown("---")

        # ── Section 5: Specification Level ───────────────────────────────────
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

        # Sync into the rate-band key used by the engines
        # (key is still named "quartile" for saved-project compatibility)
        st.session_state.quartile = spec

    # ── Right column: SVG visualisation ──────────────────────────────────────
    with col_vis:
        st.subheader("Existing Building")
        st.caption("Updates as you enter storeys and height.")

        above = st.session_state.storeys_above
        below = st.session_state.storeys_below
        ftf   = st.session_state.floor_to_floor_m

        if above + below == 0:
            st.markdown(
                "<div style='text-align:center;padding:4rem 1rem;"
                "color:#8a96a8;font-size:0.9rem;'>"
                "Enter storeys to see the building visualisation."
                "</div>",
                unsafe_allow_html=True,
            )
        else:
            svg = _building_svg(above, below, ftf)
            st.markdown(svg, unsafe_allow_html=True)

            # ── Summary card ──────────────────────────────────────────────────
            facade_str = (
                f"{st.session_state.facade_area_m2:,.0f} m²"
                if st.session_state.facade_area_m2 > 0
                else "Enter perimeter + height"
            )
            roof_str = (
                f"{st.session_state.roof_area_m2:,.0f} m²"
                if st.session_state.roof_area_m2 > 0
                else "—"
            )
            wc_str   = str(st.session_state.num_wc_cores) if st.session_state.num_wc_cores > 0 else "—"
            lift_str = str(st.session_state.num_lifts)    if st.session_state.num_lifts > 0    else "—"

            st.markdown(
                f"""
                <div style="background:#fff;border:1px solid #ddd8d0;border-radius:6px;
                            padding:1rem 1.25rem;margin-top:1rem;font-size:0.85rem;
                            line-height:1.9;color:#0f1f3d;">
                    <div style="font-family:'DM Serif Display',serif;font-size:1rem;
                                margin-bottom:0.4rem;">Existing Summary</div>
                    <div>🏢 {st.session_state.building_type} &nbsp;·&nbsp; {st.session_state.refurb_scope}</div>
                    <div>📐 GIA: {st.session_state.gia_m2:,.0f} m²</div>
                    <div>📐 NIA: {st.session_state.nia_m2:,.0f} m²</div>
                    <div>🏗️ {above} storeys above · {below} below</div>
                    <div>📏 Floor-to-floor: {ftf:.2f}m</div>
                    <div>🪟 Facade: {facade_str}</div>
                    <div>🏠 Roof: {roof_str}</div>
                    <div>🚻 WC cores: {wc_str}</div>
                    <div>🛗 Lifts: {lift_str}</div>
                    <div>⭐ {st.session_state.spec_level} spec</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ── Snapshot: write all existing building values to protected ex_ keys ───
    # These are read by Building Overview and Building Config.
    # Writing every render ensures they're always current regardless of
    # Streamlit widget re-render order when navigating between pages.
    st.session_state["ex_project_name"]   = st.session_state.get("project_name", "")
    st.session_state["ex_location"]       = st.session_state.get("location", "")
    st.session_state["ex_building_type"]  = st.session_state.get("building_type", "Office")
    st.session_state["ex_refurb_scope"]   = st.session_state.get("refurb_scope", "Full Strip Out")
    st.session_state["ex_spec_level"]     = st.session_state.get("spec_level", "Standard")
    st.session_state["ex_gia_m2"]         = st.session_state.get("gia_m2", 0.0)
    st.session_state["ex_nia_m2"]         = st.session_state.get("nia_m2", 0.0)
    st.session_state["ex_storeys_above"]  = st.session_state.get("storeys_above", 0)
    st.session_state["ex_storeys_below"]  = st.session_state.get("storeys_below", 0)
    st.session_state["ex_floor_to_floor"] = st.session_state.get("floor_to_floor_m", 0.0)
    st.session_state["ex_perimeter_m"]    = st.session_state.get("perimeter_m", 0.0)
    st.session_state["ex_facade_area_m2"] = st.session_state.get("facade_area_m2", 0.0)
    st.session_state["ex_roof_area_m2"]   = st.session_state.get("roof_area_m2", 0.0)
    st.session_state["ex_num_wc_cores"]   = st.session_state.get("num_wc_cores", 0)
    st.session_state["ex_num_lifts"]      = st.session_state.get("num_lifts", 0)

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