"""
building_extension.py
---------------------
Page 2: Building Configuration (sits between Project Setup and Element Areas)

Allows user to define existing building and any proposed vertical extension.
Existing storeys default from Project Setup inputs.
Outputs feed directly into session state GIA / NIA used by Element Areas.
"""

import streamlit as st
from engine.unit_engine import convert_area


def _init_defaults():
    """
    Initialise building extension session state.
    Existing storeys default to what was entered on Project Setup.
    Per-floor areas default to GIA/NIA divided by storeys if available.
    """
    # ext_existing_storeys defaults to storeys_above from project setup
    if "ext_existing_storeys" not in st.session_state:
        above = st.session_state.get("storeys_above", 0)
        below = st.session_state.get("storeys_below", 0)
        st.session_state["ext_existing_storeys"] = above + below

    # Per-floor GIA defaults to total GIA / storeys if available
    if "ext_gia_per_floor_m2" not in st.session_state:
        total_gia = st.session_state.get("gia_m2", 0.0)
        storeys   = st.session_state.get("ext_existing_storeys", 1)
        st.session_state["ext_gia_per_floor_m2"] = (
            round(total_gia / storeys, 0) if total_gia > 0 and storeys > 0 else 0.0
        )

    # Per-floor NIA defaults to total NIA / storeys if available
    if "ext_nia_per_floor_m2" not in st.session_state:
        total_nia = st.session_state.get("nia_m2", 0.0)
        storeys   = st.session_state.get("ext_existing_storeys", 1)
        st.session_state["ext_nia_per_floor_m2"] = (
            round(total_nia / storeys, 0) if total_nia > 0 and storeys > 0 else 0.0
        )

    st.session_state.setdefault("ext_new_storeys",        0)
    st.session_state.setdefault("ext_new_gia_m2",         st.session_state.get("ext_gia_per_floor_m2", 0.0))
    st.session_state.setdefault("ext_new_nia_m2",         st.session_state.get("ext_nia_per_floor_m2", 0.0))
    st.session_state.setdefault("ext_lifts",              0)
    st.session_state.setdefault("ext_stairs",             0)
    st.session_state.setdefault("ext_roof_works",         False)
    st.session_state.setdefault("ext_structural_storeys", 0)


def _calculate(unit: str) -> dict:
    """Return all derived values from current session state."""
    ex  = st.session_state.ext_existing_storeys
    ngf = st.session_state.ext_gia_per_floor_m2
    nif = st.session_state.ext_nia_per_floor_m2
    ns  = st.session_state.ext_new_storeys
    ng  = st.session_state.ext_new_gia_m2
    ni  = st.session_state.ext_new_nia_m2

    existing_gia = ex  * ngf
    existing_nia = ex  * nif
    added_gia    = ns  * ng
    added_nia    = ns  * ni
    total_gia    = existing_gia + added_gia
    total_nia    = existing_nia + added_nia
    net_gross    = (total_nia / total_gia * 100) if total_gia > 0 else 0

    def a(m2):
        return convert_area(m2, "m2", "ft2") if unit == "ft²" else m2

    return {
        "total_storeys":  ex + ns,
        "existing_gia":   a(existing_gia),
        "existing_nia":   a(existing_nia),
        "added_gia":      a(added_gia),
        "added_nia":      a(added_nia),
        "total_gia":      a(total_gia),
        "total_nia":      a(total_nia),
        "total_gia_m2":   total_gia,
        "total_nia_m2":   total_nia,
        "net_gross":      net_gross,
    }


def _building_svg(existing: int, new: int, below: int, roof: bool) -> str:
    """
    Generate an SVG of the building.
    Below-ground floors = grey, existing above = blue,
    new floors = red, roof = green triangle.
    Max 24 floors shown visually.
    """
    total_above = existing
    total_all   = existing + new
    max_vis     = 24

    # How many we can show
    vis_total = min(total_all + below, max_vis)
    vis_below = min(below, max_vis)
    vis_above_existing = min(existing, max_vis - vis_below)
    vis_new   = min(new, max_vis - vis_below - vis_above_existing)

    W, H    = 220, 460
    bw      = 110
    floor_h = min(28, max(10, (H - 80) // max(vis_total, 1)))
    build_h = floor_h * vis_total
    sx      = (W - bw) // 2

    # Ground line sits above below-ground floors
    ground_y = H - 50 - (floor_h * vis_below)
    sy       = ground_y - (floor_h * (vis_above_existing + vis_new))

    floors_svg = ""

    # New floors (top)
    for i in range(vis_new):
        floor_num = vis_above_existing + i
        y = sy + (vis_above_existing + vis_new - 1 - i) * floor_h
        floors_svg += (
            f'<rect x="{sx}" y="{y}" width="{bw}" height="{floor_h - 1}" '
            f'fill="#F09595" stroke="#A32D2D" stroke-width="0.5"/>'
        )
        if floor_h >= 16:
            floors_svg += (
                f'<text x="{sx + 5}" y="{y + floor_h - 5}" '
                f'font-size="9" fill="#7a1a1a" font-family="sans-serif">'
                f'L{floor_num + 1} (new)</text>'
            )

    # Existing above-ground floors
    for i in range(vis_above_existing):
        y = sy + (vis_above_existing - 1 - i) * floor_h
        floors_svg += (
            f'<rect x="{sx}" y="{y}" width="{bw}" height="{floor_h - 1}" '
            f'fill="#B5D4F4" stroke="#185FA5" stroke-width="0.5"/>'
        )
        if floor_h >= 16:
            floors_svg += (
                f'<text x="{sx + 5}" y="{y + floor_h - 5}" '
                f'font-size="9" fill="#0c2e5c" font-family="sans-serif">'
                f'L{i + 1}</text>'
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
                f'font-size="9" fill="#555" font-family="sans-serif">'
                f'B{i + 1}</text>'
            )

    # Roof
    roof_svg = ""
    if roof and (vis_above_existing + vis_new) > 0:
        ry = sy - 18
        roof_svg = (
            f'<polygon points="{sx - 8},{sy} {sx + bw // 2},{ry} {sx + bw + 8},{sy}" '
            f'fill="#97C459" stroke="#3B6D11" stroke-width="0.5"/>'
        )

    # Overflow label
    overflow_label = ""
    total_vis_count = vis_below + vis_above_existing + vis_new
    actual_total = below + total_all
    if actual_total > max_vis:
        overflow_label = (
            f'<text x="{W // 2}" y="{sy - 26}" text-anchor="middle" '
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
        f'<text x="16" y="{legend_y + 8}" font-size="8" fill="#555" font-family="sans-serif">Existing</text>'
        f'<rect x="60" y="{legend_y}" width="9" height="9" fill="#F09595" rx="2"/>'
        f'<text x="72" y="{legend_y + 8}" font-size="8" fill="#555" font-family="sans-serif">New</text>'
        f'<rect x="100" y="{legend_y}" width="9" height="9" fill="#D0CEC8" rx="2"/>'
        f'<text x="112" y="{legend_y + 8}" font-size="8" fill="#555" font-family="sans-serif">Below</text>'
        f'<rect x="150" y="{legend_y}" width="9" height="9" fill="#97C459" rx="2"/>'
        f'<text x="162" y="{legend_y + 8}" font-size="8" fill="#555" font-family="sans-serif">Roof</text>'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}">'
        f'{overflow_label}{roof_svg}{floors_svg}{ground_line}{legend}'
        f'</svg>'
    )


def render():
    _init_defaults()

    st.markdown("""
    <div style="margin-bottom:0.25rem;">
        <span style="font-family:'DM Serif Display',serif;font-size:2rem;color:#0f1f3d;">
            Building Configuration
        </span>
    </div>
    <p style="color:#8a96a8;margin-top:0;font-size:0.95rem;">
        Review the existing building and define any proposed vertical extension.
        Storeys and areas are pre-filled from Project Setup.
    </p>
    """, unsafe_allow_html=True)

    # ── Guard ─────────────────────────────────────────────────────────────────
    if not st.session_state.get("location"):
        st.warning("⚠️ Please complete Project Setup before configuring the building.")
        if st.button("← Project Setup"):
            st.session_state.page_idx = 1
            st.rerun()
        return

    # ── Unit toggle ───────────────────────────────────────────────────────────
    col_toggle, _ = st.columns([2, 6])
    with col_toggle:
        unit = st.radio(
            "Display unit",
            ["m²", "ft²"],
            horizontal=True,
            key="building_unit",
            label_visibility="collapsed",
        )

    st.markdown("---")

    col_inputs, col_vis = st.columns([1.4, 1], gap="large")

    with col_inputs:

        # ── Existing building ─────────────────────────────────────────────────
        st.markdown("#### Existing Building")

        # Show where storeys came from
        above = st.session_state.get("storeys_above", 0)
        below = st.session_state.get("storeys_below", 0)
        if above > 0 or below > 0:
            st.caption(
                f"Pre-filled from Project Setup: "
                f"{above} above ground + {below} below ground"
            )

        ex_storeys = st.number_input(
            "Total existing storeys (above ground)",
            min_value=0, max_value=100, step=1,
            value=st.session_state.ext_existing_storeys,
            key="ext_existing_storeys",
        )

        if unit == "m²":
            gia_floor_display = st.session_state.ext_gia_per_floor_m2
            nia_floor_display = st.session_state.ext_nia_per_floor_m2
        else:
            gia_floor_display = convert_area(st.session_state.ext_gia_per_floor_m2, "m2", "ft2")
            nia_floor_display = convert_area(st.session_state.ext_nia_per_floor_m2, "m2", "ft2")

        gia_floor_entered = st.number_input(
            f"GIA per existing floor ({unit})",
            min_value=0.0, step=50.0 if unit == "m²" else 500.0,
            format="%.0f", value=float(gia_floor_display),
            key=f"ext_gia_floor_input_{unit}",
        )
        st.session_state.ext_gia_per_floor_m2 = (
            gia_floor_entered if unit == "m²"
            else convert_area(gia_floor_entered, "ft2", "m2")
        )

        nia_floor_entered = st.number_input(
            f"NIA per existing floor ({unit})",
            min_value=0.0, step=50.0 if unit == "m²" else 500.0,
            format="%.0f", value=float(nia_floor_display),
            key=f"ext_nia_floor_input_{unit}",
        )
        st.session_state.ext_nia_per_floor_m2 = (
            nia_floor_entered if unit == "m²"
            else convert_area(nia_floor_entered, "ft2", "m2")
        )

        st.markdown("---")

        # ── Extension ─────────────────────────────────────────────────────────
        st.markdown("#### Proposed Extension")

        new_storeys = st.number_input(
            "Number of additional storeys",
            min_value=0, max_value=50, step=1,
            value=st.session_state.ext_new_storeys,
            key="ext_new_storeys",
        )

        if new_storeys > 0:
            if unit == "m²":
                new_gia_display = st.session_state.ext_new_gia_m2
                new_nia_display = st.session_state.ext_new_nia_m2
            else:
                new_gia_display = convert_area(st.session_state.ext_new_gia_m2, "m2", "ft2")
                new_nia_display = convert_area(st.session_state.ext_new_nia_m2, "m2", "ft2")

            new_gia_entered = st.number_input(
                f"GIA per new floor ({unit})",
                min_value=0.0, step=50.0 if unit == "m²" else 500.0,
                format="%.0f", value=float(new_gia_display),
                key=f"ext_new_gia_input_{unit}",
            )
            st.session_state.ext_new_gia_m2 = (
                new_gia_entered if unit == "m²"
                else convert_area(new_gia_entered, "ft2", "m2")
            )

            new_nia_entered = st.number_input(
                f"NIA per new floor ({unit})",
                min_value=0.0, step=50.0 if unit == "m²" else 500.0,
                format="%.0f", value=float(new_nia_display),
                key=f"ext_new_nia_input_{unit}",
            )
            st.session_state.ext_new_nia_m2 = (
                new_nia_entered if unit == "m²"
                else convert_area(new_nia_entered, "ft2", "m2")
            )

        st.markdown("---")

        # ── Building services ─────────────────────────────────────────────────
        st.markdown("#### Building Services")

        col_a, col_b = st.columns(2)
        with col_a:
            st.number_input(
                "Number of lifts",
                min_value=0, max_value=20, step=1,
                key="ext_lifts",
            )
        with col_b:
            st.number_input(
                "Number of stairs",
                min_value=0, max_value=20, step=1,
                key="ext_stairs",
            )

        col_c, col_d = st.columns(2)
        with col_c:
            st.checkbox("Roof works required", key="ext_roof_works")
        with col_d:
            st.number_input(
                "Structural strengthening (storeys)",
                min_value=0, max_value=50, step=1,
                key="ext_structural_storeys",
            )

    # ── Visualisation ─────────────────────────────────────────────────────────
    with col_vis:
        st.markdown("#### Building Visualisation")

        calc = _calculate(unit)

        svg = _building_svg(
            existing=st.session_state.ext_existing_storeys,
            new=st.session_state.ext_new_storeys,
            below=st.session_state.get("storeys_below", 0),
            roof=st.session_state.ext_roof_works,
        )
        st.markdown(svg, unsafe_allow_html=True)

    # ── Outputs ───────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Developed Building Summary")

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Total storeys", calc["total_storeys"])
    with c2:
        st.metric(f"Existing GIA ({unit})", f"{calc['existing_gia']:,.0f}")
    with c3:
        st.metric(f"Added GIA ({unit})", f"+{calc['added_gia']:,.0f}")
    with c4:
        st.metric(f"Total GIA ({unit})", f"{calc['total_gia']:,.0f}")
    with c5:
        st.metric("Net:Gross", f"{calc['net_gross']:.0f}%")

    c6, c7, c8, c9, c10 = st.columns(5)
    with c6:
        st.metric("Lifts", st.session_state.ext_lifts)
    with c7:
        st.metric(f"Existing NIA ({unit})", f"{calc['existing_nia']:,.0f}")
    with c8:
        st.metric(f"Added NIA ({unit})", f"+{calc['added_nia']:,.0f}")
    with c9:
        st.metric(f"Total NIA ({unit})", f"{calc['total_nia']:,.0f}")
    with c10:
        st.metric("Structural (storeys)", st.session_state.ext_structural_storeys)

    # ── Push totals into session state for downstream pages ───────────────────
    st.session_state.gia_m2 = calc["total_gia_m2"]
    st.session_state.nia_m2 = calc["total_nia_m2"]

    # Recalculate net:gross from developed totals
    if calc["total_gia_m2"] > 0:
        st.session_state.net_gross_pct = round(
            calc["total_nia_m2"] / calc["total_gia_m2"] * 100, 1
        )

    st.caption(
        f"⚠️ GIA updated to {calc['total_gia_m2']:,.0f} m² and "
        f"NIA to {calc['total_nia_m2']:,.0f} m² — these will be used in Element Areas."
    )

    # ── Navigation ────────────────────────────────────────────────────────────
    st.markdown("---")
    col_back, _, col_next = st.columns([1, 4, 1])
    with col_back:
        if st.button("← Project Setup", use_container_width=True):
            st.session_state.page_idx = 1
            st.rerun()
    with col_next:
        if st.button(
            "Next: Elements →",
            type="primary",
            use_container_width=True,
        ):
            st.session_state.page_idx = 3
            st.rerun()