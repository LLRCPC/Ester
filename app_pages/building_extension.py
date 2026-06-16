"""
building_extension.py
---------------------
Page 2: Building Configuration — captures what the building WILL BECOME after works.

Captures:
- Overview panel: existing vs proposed at a glance
- Optional vertical extension (new floors + floor plate)
- Lifts, stairs, roof works, structural strengthening
- SVG of the PROPOSED building (existing in blue, new in red)
- Before vs after summary table
- Pushes proposed GIA/NIA into proposed_gia_m2 / proposed_nia_m2 (NOT gia_m2/nia_m2)
  so Project Setup existing values are never overwritten.

Key session state contract:
  gia_m2 / nia_m2                    — EXISTING building (owned by Project Setup, read-only here)
  proposed_gia_m2 / proposed_nia_m2  — PROPOSED building (owned by this page)

render() takes no arguments — called as render() from app.py.
"""

import streamlit as st
from engine.unit_engine import convert_area


def _init_defaults():
    """
    Initialise building config session state fresh from Project Setup values.
    Called every render so changes on Project Setup are always reflected here.
    """
    total_gia = st.session_state.get("gia_m2", 0.0)
    total_nia = st.session_state.get("nia_m2", 0.0)
    storeys   = st.session_state.get("storeys_above", 1)

    per_floor_gia = round(total_gia / storeys, 0) if total_gia > 0 and storeys > 0 else 0.0
    per_floor_nia = round(total_nia / storeys, 0) if total_nia > 0 and storeys > 0 else 0.0

    # Always keep per-floor defaults in sync with Project Setup
    st.session_state["ext_gia_per_floor_m2"] = per_floor_gia
    st.session_state["ext_nia_per_floor_m2"] = per_floor_nia

    # New floor areas default to the existing per-floor average.
    # Only reset if the user hasn't already overridden them.
    if st.session_state.get("ext_new_gia_m2", 0.0) == 0.0:
        st.session_state["ext_new_gia_m2"] = per_floor_gia
    if st.session_state.get("ext_new_nia_m2", 0.0) == 0.0:
        st.session_state["ext_new_nia_m2"] = per_floor_nia

    st.session_state.setdefault("ext_new_storeys",        0)
    st.session_state.setdefault("ext_lifts",              0)
    st.session_state.setdefault("ext_stairs",             0)
    st.session_state.setdefault("ext_roof_works",         False)
    st.session_state.setdefault("ext_structural_storeys", 0)
    st.session_state.setdefault("has_extension",          False)


def _calculate(unit: str) -> dict:
    """Return all derived before/after values from current session state."""
    above     = st.session_state.get("storeys_above", 0)
    below     = st.session_state.get("storeys_below", 0)
    exist_gia = st.session_state.get("gia_m2", 0.0)
    exist_nia = st.session_state.get("nia_m2", 0.0)

    ns = st.session_state.ext_new_storeys if st.session_state.has_extension else 0
    ng = st.session_state.ext_new_gia_m2
    ni = st.session_state.ext_new_nia_m2

    added_gia = ns * ng
    added_nia = ns * ni
    total_gia = exist_gia + added_gia
    total_nia = exist_nia + added_nia
    net_gross_exist   = (exist_nia / exist_gia * 100)   if exist_gia > 0 else 0
    net_gross_proposed = (total_nia / total_gia * 100)  if total_gia > 0 else 0

    def a(m2):
        return convert_area(m2, "m2", "ft2") if unit == "ft²" else m2

    return {
        "existing_storeys":    above,
        "below_storeys":       below,
        "new_storeys":         ns,
        "total_storeys":       above + below + ns,
        "exist_gia":           a(exist_gia),
        "exist_nia":           a(exist_nia),
        "added_gia":           a(added_gia),
        "added_nia":           a(added_nia),
        "total_gia":           a(total_gia),
        "total_nia":           a(total_nia),
        "total_gia_m2":        total_gia,
        "total_nia_m2":        total_nia,
        "net_gross_exist":     net_gross_exist,
        "net_gross_proposed":  net_gross_proposed,
        "gia_increase_pct":    ((total_gia - exist_gia) / exist_gia * 100) if exist_gia > 0 else 0,
        "nia_increase_pct":    ((total_nia - exist_nia) / exist_nia * 100) if exist_nia > 0 else 0,
    }


def _building_svg(existing_above: int, existing_below: int, new_storeys: int, roof: bool) -> str:
    """
    Proposed building SVG.
    Below-ground = grey, existing above = blue, new floors = red, roof works = green triangle.
    """
    max_vis            = 24
    vis_below          = min(existing_below, max_vis)
    vis_existing_above = min(existing_above, max_vis - vis_below)
    vis_new            = min(new_storeys, max_vis - vis_below - vis_existing_above)
    total_vis          = vis_below + vis_existing_above + vis_new

    W, H     = 220, 400
    bw       = 110
    floor_h  = min(28, max(10, (H - 80) // max(total_vis, 1)))
    ground_y = H - 50 - (floor_h * vis_below)
    sx       = (W - bw) // 2

    sy = ground_y - (floor_h * (vis_existing_above + vis_new))

    floors_svg = ""

    # Existing above-ground floors (blue)
    for i in range(vis_existing_above):
        y = ground_y - (i + 1) * floor_h
        floors_svg += (
            f'<rect x="{sx}" y="{y}" width="{bw}" height="{floor_h - 1}" '
            f'fill="#B5D4F4" stroke="#185FA5" stroke-width="0.5"/>'
        )
        if floor_h >= 16:
            floors_svg += (
                f'<text x="{sx + 5}" y="{y + floor_h - 5}" '
                f'font-size="9" fill="#0c2e5c" font-family="sans-serif">L{i + 1}</text>'
            )

    # New floors (red)
    for i in range(vis_new):
        y = ground_y - (vis_existing_above + i + 1) * floor_h
        floors_svg += (
            f'<rect x="{sx}" y="{y}" width="{bw}" height="{floor_h - 1}" '
            f'fill="#F09595" stroke="#A32D2D" stroke-width="0.5"/>'
        )
        if floor_h >= 16:
            floors_svg += (
                f'<text x="{sx + 5}" y="{y + floor_h - 5}" '
                f'font-size="9" fill="#7a1a1a" font-family="sans-serif">'
                f'L{vis_existing_above + i + 1} (new)</text>'
            )

    # Below-ground floors (grey)
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

    # Roof works triangle (green)
    roof_svg = ""
    if roof and (vis_existing_above + vis_new) > 0:
        ry = sy - 18
        roof_svg = (
            f'<polygon points="{sx - 8},{sy} {sx + bw // 2},{ry} {sx + bw + 8},{sy}" '
            f'fill="#97C459" stroke="#3B6D11" stroke-width="0.5"/>'
        )

    # Overflow label
    overflow = ""
    actual_total = existing_above + existing_below + new_storeys
    if actual_total > max_vis:
        overflow = (
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
        f'<rect x="64" y="{legend_y}" width="9" height="9" fill="#F09595" rx="2"/>'
        f'<text x="76" y="{legend_y + 8}" font-size="8" fill="#555" font-family="sans-serif">New</text>'
        f'<rect x="106" y="{legend_y}" width="9" height="9" fill="#D0CEC8" rx="2"/>'
        f'<text x="118" y="{legend_y + 8}" font-size="8" fill="#555" font-family="sans-serif">Below GL</text>'
        + (
            f'<rect x="172" y="{legend_y}" width="9" height="9" fill="#97C459" rx="2"/>'
            f'<text x="184" y="{legend_y + 8}" font-size="8" fill="#555" font-family="sans-serif">Roof</text>'
            if roof else ""
        )
    )

    title = (
        f'<text x="{W // 2}" y="14" text-anchor="middle" '
        f'font-size="10" fill="#0f1f3d" font-family="sans-serif" font-weight="600">'
        f'Proposed Building</text>'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}">'
        f'{title}{overflow}{roof_svg}{floors_svg}{ground_line}{legend}'
        f'</svg>'
    )


def render():
    _init_defaults()

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown("""
    <div style="margin-bottom:0.25rem;">
        <span style="font-family:'DM Serif Display',serif;font-size:2rem;color:#0f1f3d;">
            Building Configuration
        </span>
    </div>
    <p style="color:#8a96a8;margin-top:0;font-size:0.95rem;">
        Define what the building will <strong>become</strong> after works —
        extension scope, services and building systems.
    </p>
    """, unsafe_allow_html=True)

    col_toggle, _ = st.columns([2, 6])
    with col_toggle:
        unit = st.radio(
            "Display unit", ["m²", "ft²"],
            horizontal=True, key="building_unit",
            label_visibility="collapsed",
        )

    # ── Guard: must have Project Setup data ───────────────────────────────────
    exist_gia     = st.session_state.get("gia_m2", 0.0)
    storeys_above = st.session_state.get("storeys_above", 0)

    if exist_gia == 0.0 and storeys_above == 0:
        st.warning("⚠️ No building data found — please complete Project Setup first.")
        if st.button("← Project Setup"):
            st.session_state.page_idx = 1
            st.rerun()
        return

    # ── Calculate proposed values (needed for overview panel) ─────────────────
    calc = _calculate(unit)

    # Push proposed totals to separate keys immediately so overview is accurate
    st.session_state["proposed_gia_m2"] = calc["total_gia_m2"]
    st.session_state["proposed_nia_m2"] = calc["total_nia_m2"]
    if calc["total_gia_m2"] > 0:
        st.session_state["proposed_net_gross_pct"] = round(
            calc["total_nia_m2"] / calc["total_gia_m2"] * 100, 1
        )

    st.markdown("---")

    # ── Layout: inputs left, visual right ────────────────────────────────────
    col_inputs, col_vis = st.columns([1.4, 1], gap="large")

    exist_nia     = st.session_state.get("nia_m2", 0.0)
    storeys_below = st.session_state.get("storeys_below", 0)
    per_floor_gia = st.session_state.get("ext_gia_per_floor_m2", 0.0)
    per_floor_nia = st.session_state.get("ext_nia_per_floor_m2", 0.0)

    # ── LEFT: all inputs ──────────────────────────────────────────────────────
    with col_inputs:

        # ── Vertical Extension ────────────────────────────────────────────────
        st.markdown("#### Vertical Extension")
        st.checkbox(
            "This project includes a vertical extension (new floors)",
            key="has_extension",
        )

        if st.session_state.has_extension:
            st.number_input(
                "Number of new storeys",
                min_value=0, max_value=50, step=1,
                key="ext_new_storeys",
            )

            if st.session_state.ext_new_storeys > 0:

                # Assumption box
                if per_floor_gia > 0:
                    if unit == "m²":
                        st.info(
                            f"📐 **Assumption:** New floors match existing per-floor average — "
                            f"GIA {per_floor_gia:,.0f} m² · NIA {per_floor_nia:,.0f} m² per floor. "
                            f"Override below if new floors differ."
                        )
                    else:
                        st.info(
                            f"📐 **Assumption:** New floors match existing per-floor average — "
                            f"GIA {convert_area(per_floor_gia, 'm2', 'ft2'):,.0f} ft² · "
                            f"NIA {convert_area(per_floor_nia, 'm2', 'ft2'):,.0f} ft² per floor. "
                            f"Override below if new floors differ."
                        )

                if unit == "m²":
                    new_gia_display = st.session_state.ext_new_gia_m2
                    new_nia_display = st.session_state.ext_new_nia_m2
                else:
                    new_gia_display = convert_area(st.session_state.ext_new_gia_m2, "m2", "ft2")
                    new_nia_display = convert_area(st.session_state.ext_new_nia_m2, "m2", "ft2")

                col_g, col_n = st.columns(2)
                with col_g:
                    new_gia_entered = st.number_input(
                        f"GIA per new floor ({unit})",
                        min_value=0.0,
                        step=50.0 if unit == "m²" else 500.0,
                        format="%.0f",
                        value=float(new_gia_display),
                        key=f"ext_new_gia_input_{unit}",
                    )
                    st.session_state.ext_new_gia_m2 = (
                        new_gia_entered if unit == "m²"
                        else convert_area(new_gia_entered, "ft2", "m2")
                    )
                with col_n:
                    new_nia_entered = st.number_input(
                        f"NIA per new floor ({unit})",
                        min_value=0.0,
                        step=50.0 if unit == "m²" else 500.0,
                        format="%.0f",
                        value=float(new_nia_display),
                        key=f"ext_new_nia_input_{unit}",
                    )
                    st.session_state.ext_new_nia_m2 = (
                        new_nia_entered if unit == "m²"
                        else convert_area(new_nia_entered, "ft2", "m2")
                    )

                # Total added area caption
                added_gia = st.session_state.ext_new_storeys * st.session_state.ext_new_gia_m2
                added_nia = st.session_state.ext_new_storeys * st.session_state.ext_new_nia_m2
                if unit == "m²":
                    st.caption(
                        f"Total added: GIA +{added_gia:,.0f} m² · NIA +{added_nia:,.0f} m²"
                    )
                else:
                    st.caption(
                        f"Total added: "
                        f"GIA +{convert_area(added_gia, 'm2', 'ft2'):,.0f} ft² · "
                        f"NIA +{convert_area(added_nia, 'm2', 'ft2'):,.0f} ft²"
                    )
        else:
            st.session_state.ext_new_storeys = 0

        st.markdown("---")

        # ── Building Services ─────────────────────────────────────────────────
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

        st.markdown("---")

        # Update button
        if st.button("🔄  Update Building Visual", type="primary", use_container_width=True):
            st.session_state["_bc_svg"] = _building_svg(
                existing_above=st.session_state.storeys_above,
                existing_below=st.session_state.storeys_below,
                new_storeys=st.session_state.ext_new_storeys if st.session_state.has_extension else 0,
                roof=st.session_state.ext_roof_works,
            )
            st.session_state["_bc_unit"] = unit

    # ── RIGHT: visual ─────────────────────────────────────────────────────────
    with col_vis:
        st.markdown("#### Proposed Building")

        if "_bc_svg" not in st.session_state:
            st.session_state["_bc_svg"] = _building_svg(
                existing_above=st.session_state.storeys_above,
                existing_below=st.session_state.storeys_below,
                new_storeys=0,
                roof=False,
            )
            st.session_state["_bc_unit"] = unit

        st.markdown(st.session_state["_bc_svg"], unsafe_allow_html=True)
        st.caption("Press **Update Building Visual** after making changes.")

    # ── Navigation ────────────────────────────────────────────────────────────
    st.markdown("---")
    col_back, _, col_next = st.columns([1, 4, 1])
    with col_back:
        if st.button("← Project Setup", use_container_width=True):
            st.session_state.page_idx = 1
            st.rerun()
    with col_next:
        if st.button("Next: Overview →", type="primary", use_container_width=True):
            st.session_state.page_idx = 3
            st.rerun()