"""
building_overview.py
--------------------
Page 3: Building Overview — read-only confirmation page.

Shows a clean before vs after summary of the building.
Reads from protected ex_ snapshot keys written by project_setup.py,
so values are always stable regardless of widget re-render order.
"""

import streamlit as st
from engine.unit_engine import convert_area


def render():

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown("""
    <div style="margin-bottom:0.25rem;">
        <span style="font-family:'DM Serif Display',serif;font-size:2rem;color:#0f1f3d;">
            Building Overview
        </span>
    </div>
    <p style="color:#8a96a8;margin-top:0;font-size:0.95rem;">
        Confirm the existing and proposed building before moving into element costing.
        Go back to adjust any values.
    </p>
    """, unsafe_allow_html=True)

    # ── Unit toggle ───────────────────────────────────────────────────────────
    col_toggle, _ = st.columns([2, 6])
    with col_toggle:
        unit = st.radio(
            "Display unit", ["m²", "ft²"],
            horizontal=True, key="overview_unit",
            label_visibility="collapsed",
        )

    st.markdown("---")

    # ── Read from protected ex_ snapshot keys (written by project_setup.py) ──
    project_name  = st.session_state.get("ex_project_name",   "") or st.session_state.get("project_name", "Unnamed Project")
    location      = st.session_state.get("ex_location",       "") or st.session_state.get("location",     "—")
    spec          = st.session_state.get("ex_spec_level",     "") or st.session_state.get("spec_level",   "Standard")
    refurb_scope  = st.session_state.get("ex_refurb_scope",   "") or st.session_state.get("refurb_scope", "—")
    building_type = st.session_state.get("ex_building_type",  "") or st.session_state.get("building_type","—")

    exist_gia     = st.session_state.get("ex_gia_m2",         0.0)
    exist_nia     = st.session_state.get("ex_nia_m2",         0.0)
    storeys_above = st.session_state.get("ex_storeys_above",  0)
    storeys_below = st.session_state.get("ex_storeys_below",  0)
    ftf           = st.session_state.get("ex_floor_to_floor", 0.0)
    perimeter     = st.session_state.get("ex_perimeter_m",    0.0)
    facade_area   = st.session_state.get("ex_facade_area_m2", 0.0)
    roof_area     = st.session_state.get("ex_roof_area_m2",   0.0)
    num_wc        = st.session_state.get("ex_num_wc_cores",   0)
    num_lifts     = st.session_state.get("ex_num_lifts",      0)

    # Proposed values (written by building_extension.py)
    prop_gia    = st.session_state.get("proposed_gia_m2",  exist_gia)
    prop_nia    = st.session_state.get("proposed_nia_m2",  exist_nia)
    new_storeys = st.session_state.get("ext_new_storeys",  0) if st.session_state.get("has_extension") else 0
    ext_lifts   = st.session_state.get("ext_lifts",        0)
    ext_stairs  = st.session_state.get("ext_stairs",       0)
    roof_works  = st.session_state.get("ext_roof_works",   False)
    str_storeys = st.session_state.get("ext_structural_storeys", 0)

    # Proposed storeys and facade
    prop_storeys_above = storeys_above + new_storeys
    prop_facade = (
        round(perimeter * ftf * prop_storeys_above, 0)
        if perimeter > 0 and ftf > 0 and prop_storeys_above > 0
        else facade_area
    )

    # Net:Gross ratios
    ng_exist = (exist_nia / exist_gia * 100) if exist_gia > 0 else 0
    ng_prop  = (prop_nia  / prop_gia  * 100) if prop_gia  > 0 else 0

    # ── Guard ─────────────────────────────────────────────────────────────────
    if exist_gia == 0.0 and storeys_above == 0:
        st.warning("⚠️ No building data found — please complete Project Setup first.")
        col_a, _ = st.columns([1, 5])
        with col_a:
            if st.button("← Project Setup", use_container_width=True):
                st.session_state.page_idx = 1
                st.rerun()
        return

    # ── Helpers ───────────────────────────────────────────────────────────────
    def fmt(m2):
        if unit == "ft²":
            return f"{convert_area(m2, 'm2', 'ft2'):,.0f} ft²"
        return f"{m2:,.0f} m²"

    def delta(before, after, is_area=True):
        if before == 0 or after == before:
            return None
        diff = after - before
        pct  = diff / before * 100
        sign = "+" if diff >= 0 else ""
        if is_area:
            return f"{sign}{fmt(abs(diff))} ({sign}{pct:.0f}%)"
        return f"{sign}{diff:.0f} ({sign}{pct:.0f}%)"

    def metric_row(label, value, delta_val=None, border_color="#e8e4df"):
        delta_html = (
            f"<div style='font-size:0.75rem;color:#2e7d32;margin-top:0.1rem;'>{delta_val}</div>"
            if delta_val else ""
        )
        return (
            f"<div style='padding:0.5rem 0;border-bottom:1px solid {border_color};'>"
            f"<div style='font-size:0.75rem;color:#8a96a8;'>{label}</div>"
            f"<div style='font-size:0.9rem;font-weight:600;color:#0f1f3d;'>{value}</div>"
            f"{delta_html}"
            f"</div>"
        )

    # ── Project header card ───────────────────────────────────────────────────
    display_name = project_name if project_name else "Unnamed Project"
    st.markdown(
        f"""
        <div style="background:#0f1f3d;border-radius:8px;padding:1.1rem 1.5rem;
                    margin-bottom:1.5rem;color:#fff;">
            <div style="font-family:'DM Serif Display',serif;font-size:1.3rem;
                        margin-bottom:0.3rem;">{display_name}</div>
            <div style="font-size:0.83rem;color:#8a96a8;line-height:1.8;">
                📍 {location} &nbsp;·&nbsp;
                🏢 {building_type} &nbsp;·&nbsp;
                🔧 {refurb_scope} &nbsp;·&nbsp;
                ⭐ {spec} spec
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Two-column comparison ─────────────────────────────────────────────────
    col_ex, col_mid, col_pr = st.columns([5, 1, 5])

    # ── EXISTING column ───────────────────────────────────────────────────────
    with col_ex:
        st.markdown(
            "<div style='background:#f4f2ef;border-radius:8px;padding:1rem 1.25rem;"
            "border:1px solid #e0dbd3;'>"
            "<div style='font-family:\"DM Serif Display\",serif;font-size:1rem;"
            "color:#0f1f3d;margin-bottom:0.75rem;padding-bottom:0.5rem;"
            "border-bottom:2px solid #185FA5;'>🏢 Existing Building</div>",
            unsafe_allow_html=True,
        )
        rows_exist = [
            ("Storeys above ground",  f"{storeys_above}"),
            ("Storeys below ground",  f"{storeys_below}"),
            ("Total storeys",         f"{storeys_above + storeys_below}"),
            ("Gross Internal Area",   fmt(exist_gia)),
            ("Net Internal Area",     fmt(exist_nia)),
            ("Net:Gross ratio",       f"{ng_exist:.0f}%"),
            ("Floor-to-floor height", f"{ftf:.2f}m"      if ftf > 0       else "—"),
            ("Building perimeter",    f"{perimeter:.0f}m" if perimeter > 0 else "—"),
            ("Facade area",           fmt(facade_area)   if facade_area > 0 else "—"),
            ("Roof area",             fmt(roof_area)     if roof_area > 0   else "—"),
            ("WC cores",              f"{num_wc}"        if num_wc > 0      else "—"),
            ("Lifts",                 f"{num_lifts}"     if num_lifts > 0   else "—"),
        ]
        for label, val in rows_exist:
            st.markdown(metric_row(label, val), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Arrow ─────────────────────────────────────────────────────────────────
    with col_mid:
        st.markdown(
            "<div style='text-align:center;padding-top:8rem;"
            "font-size:2rem;color:#c8a84b;'>→</div>",
            unsafe_allow_html=True,
        )

    # ── PROPOSED column ───────────────────────────────────────────────────────
    with col_pr:
        st.markdown(
            "<div style='background:#eaf4e8;border-radius:8px;padding:1rem 1.25rem;"
            "border:1px solid #b8ddb3;'>"
            "<div style='font-family:\"DM Serif Display\",serif;font-size:1rem;"
            "color:#0f1f3d;margin-bottom:0.75rem;padding-bottom:0.5rem;"
            "border-bottom:2px solid #2e7d32;'>🏗️ Proposed Building</div>",
            unsafe_allow_html=True,
        )

        rows_prop = [
            ("Storeys above ground", f"{prop_storeys_above}",
             delta(storeys_above, prop_storeys_above, is_area=False)),
            ("Storeys below ground", f"{storeys_below}", None),
            ("Total storeys",        f"{prop_storeys_above + storeys_below}",
             delta(storeys_above + storeys_below, prop_storeys_above + storeys_below, is_area=False)),
            ("Gross Internal Area",  fmt(prop_gia),  delta(exist_gia, prop_gia)),
            ("Net Internal Area",    fmt(prop_nia),  delta(exist_nia, prop_nia)),
            ("Net:Gross ratio",      f"{ng_prop:.0f}%", None),
            ("Floor-to-floor height", f"{ftf:.2f}m"      if ftf > 0        else "—", None),
            ("Building perimeter",    f"{perimeter:.0f}m" if perimeter > 0  else "—", None),
            ("Facade area",           fmt(prop_facade)    if prop_facade > 0 else "—",
             delta(facade_area, prop_facade) if (facade_area > 0 and prop_facade != facade_area) else None),
            ("Roof area",             fmt(roof_area)      if roof_area > 0   else "—", None),
            ("WC cores",              f"{num_wc}"         if num_wc > 0      else "—", None),
            ("Lifts",                 f"{num_lifts}"      if num_lifts > 0   else "—", None),
        ]
        for label, val, d in rows_prop:
            st.markdown(metric_row(label, val, delta_val=d, border_color="#c8e6c4"), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Works scope summary bar ───────────────────────────────────────────────
    scope_items = []
    if new_storeys > 0:
        scope_items.append(f"<strong>+{new_storeys} new storeys</strong> (vertical extension)")
    if roof_works:
        scope_items.append("<strong>Roof works</strong>")
    if str_storeys > 0:
        scope_items.append(f"<strong>Structural strengthening</strong> ({str_storeys} storeys)")
    if ext_lifts > 0:
        scope_items.append(f"<strong>{ext_lifts} lifts</strong>")
    if ext_stairs > 0:
        scope_items.append(f"<strong>{ext_stairs} stairs</strong>")

    if scope_items:
        st.markdown(
            f"<div style='background:#fff8e8;border:1px solid #f0d080;border-radius:6px;"
            f"padding:0.8rem 1.1rem;margin-top:1rem;font-size:0.85rem;color:#6b4f00;'>"
            f"🔧 <strong>Works scope:</strong> &nbsp;"
            f"{' &nbsp;·&nbsp; '.join(scope_items)}"
            f"</div>",
            unsafe_allow_html=True,
        )

    # ── GIA / NIA delta bar ───────────────────────────────────────────────────
    if prop_gia != exist_gia or prop_nia != exist_nia:
        gia_pct = ((prop_gia - exist_gia) / exist_gia * 100) if exist_gia > 0 else 0
        nia_pct = ((prop_nia - exist_nia) / exist_nia * 100) if exist_nia > 0 else 0
        st.markdown(
            f"<div style='background:#e8f4fd;border:1px solid #90caf9;border-radius:6px;"
            f"padding:0.8rem 1.1rem;margin-top:0.6rem;font-size:0.85rem;color:#0d47a1;'>"
            f"📈 GIA {gia_pct:+.0f}% &nbsp;({fmt(exist_gia)} → {fmt(prop_gia)}) &nbsp;·&nbsp; "
            f"NIA {nia_pct:+.0f}% &nbsp;({fmt(exist_nia)} → {fmt(prop_nia)})"
            f"</div>",
            unsafe_allow_html=True,
        )

    # ── Navigation ────────────────────────────────────────────────────────────
    st.markdown("---")
    col_back, _, col_next = st.columns([1, 4, 1])
    with col_back:
        if st.button("← Building Config", use_container_width=True):
            st.session_state.page_idx = 2
            st.rerun()
    with col_next:
        if st.button("Next: Elements →", type="primary", use_container_width=True):
            st.session_state.page_idx = 4
            st.rerun()