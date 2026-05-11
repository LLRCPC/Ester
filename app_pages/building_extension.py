"""
building_extension.py
---------------------
Page 2: Building Extension (sits between Project Setup and Element Areas)

Allows user to define existing building and any proposed vertical extension.
Outputs feed directly into session state GIA / NIA used by Element Areas.
"""

import streamlit as st
import streamlit.components.v1 as components
from engine.unit_engine import convert_area


# ── Constants ────────────────────────────────────────────────────────────────
M2_TO_FT2 = 10.76391041671


def _init_defaults():
    """Initialise all extension-related session state keys once."""
    defaults = {
        "ext_existing_storeys":  8,
        "ext_gia_per_floor_m2":  900.0,
        "ext_nia_per_floor_m2":  720.0,
        "ext_new_storeys":       0,
        "ext_new_gia_m2":        900.0,
        "ext_new_nia_m2":        720.0,
        "ext_lifts":             4,
        "ext_stairs":            2,
        "ext_roof_works":        False,
        "ext_structural_storeys": 0,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


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


def _building_svg(existing: int, new: int, roof: bool) -> str:
    """
    Generate an SVG of the building.
    Existing floors = blue, new floors = red, roof = green triangle.
    Max 24 floors shown visually; label shown if more.
    """
    total     = existing + new
    max_vis   = 24
    vis_total = min(total, max_vis)
    vis_ex    = min(existing, max_vis - min(new, max_vis))
    vis_new   = vis_total - vis_ex

    W, H      = 220, 420
    bw        = 110
    floor_h   = min(28, max(10, (H - 80) // max(vis_total, 1)))
    build_h   = floor_h * vis_total
    sx        = (W - bw) // 2
    sy        = H - 50 - build_h

    floors_svg = ""
    for i in range(vis_total):
        is_new = i >= vis_ex
        y      = sy + (vis_total - 1 - i) * floor_h
        fill   = "#F09595" if is_new else "#B5D4F4"
        stroke = "#A32D2D" if is_new else "#185FA5"
        label  = f"L{i + 1}"
        text   = ""
        if floor_h >= 16:
            text = (
                f'<text x="{sx + 5}" y="{y + floor_h - 5}" '
                f'font-size="9" fill="#444" font-family="sans-serif">'
                f'{label}</text>'
            )
        floors_svg += (
            f'<rect x="{sx}" y="{y}" width="{bw}" height="{floor_h - 1}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="0.5"/>{text}'
        )

    roof_svg = ""
    if roof and vis_total > 0:
        ry = sy - 18
        roof_svg = (
            f'<polygon points="{sx - 8},{sy} {sx + bw // 2},{ry} {sx + bw + 8},{sy}" '
            f'fill="#97C459" stroke="#3B6D11" stroke-width="0.5"/>'
        )

    overflow_label = ""
    if total > max_vis:
        overflow_label = (
            f'<text x="{W // 2}" y="{sy - 24}" text-anchor="middle" '
            f'font-size="9" fill="#888" font-family="sans-serif">'
            f'{total} storeys total — showing {max_vis}</text>'
        )

    ground = (
        f'<rect x="{sx - 20}" y="{H - 44}" width="{bw + 40}" height="8" fill="#888"/>'
        f'<text x="{W // 2}" y="{H - 28}" text-anchor="middle" '
        f'font-size="10" fill="#666" font-family="sans-serif">Ground</text>'
    )

    legend = (
        f'<rect x="10" y="{H - 18}" width="10" height="10" fill="#B5D4F4" rx="2"/>'
        f'<text x="24" y="{H - 9}" font-size="9" fill="#666" font-family="sans-serif">Existing</text>'
        f'<rect x="72" y="{H - 18}" width="10" height="10" fill="#F09595" rx="2"/>'
        f'<text x="86" y="{H - 9}" font-size="9" fill="#666" font-family="sans-serif">New</text>'
        f'<rect x="114" y="{H - 18}" width="10" height="10" fill="#97C459" rx="2"/>'
        f'<text x="128" y="{H - 9}" font-size="9" fill="#666" font-family="sans-serif">Roof</text>'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}">'
        f'{overflow_label}{roof_svg}{floors_svg}{ground}{legend}'
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
        Define the existing building and any proposed vertical extension.
        Total GIA and NIA will update automatically in Element Areas.
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

    # ── Two-column layout ─────────────────────────────────────────────────────
    col_inputs, col_vis = st.columns([1.4, 1], gap="large")

    with col_inputs:

        # ── Existing building ─────────────────────────────────────────────────
        st.markdown("#### Existing Building")

        ex_storeys = st.number_input(
            "Number of existing storeys",
            min_value=1, max_value=100, step=1,
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

    # ── Push totals into session state for downstream pages ──────────────────
    st.session_state.gia_m2 = calc["total_gia_m2"]
    st.session_state.nia_m2 = calc["total_nia_m2"]

    st.caption(
        f"⚠️ GIA and NIA have been updated to {calc['total_gia_m2']:,.0f} m² "
        f"and {calc['total_nia_m2']:,.0f} m² and will be used in Element Areas."
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