"""
admin_rate_submission.py
------------------------
Page: Admin - Rate Submission

Admins input total cost per element. The backend calculates the rate:
  - NIA  -> Cat A Fit-Out elements (rate = cost / NIA)
  - GIA  -> most elements (rate = cost / GIA)
  - nr   -> Count elements (rate = cost / number of items)
  - %    -> On Costs (entered directly as a percentage)

Flow:
  Step 1 - Project Details
  Step 2 - Cost Entry (total cost per element -> auto-calculates rate)
  Step 3 - Review & Submit
"""

import streamlit as st
import pandas as pd
from datetime import date
import os
import httpx

FT2_PER_M2 = 10.76391041671

# -- Supabase helpers --

def _creds():
    url = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", "")
    return url, key

def _headers(key):
    return {
        "apikey":        key,
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
        "Prefer":        "return=representation",
    }

def _get(table: str, params: str = "") -> list:
    url, key = _creds()
    r = httpx.get(f"{url}/rest/v1/{table}?{params}", headers=_headers(key), timeout=15)
    r.raise_for_status()
    return r.json()

def _post(table: str, payload: dict) -> dict:
    url, key = _creds()
    r = httpx.post(f"{url}/rest/v1/{table}", headers=_headers(key), json=payload, timeout=15)
    r.raise_for_status()
    result = r.json()
    return result[0] if isinstance(result, list) else result

# -- Data loaders --

@st.cache_data(ttl=300)
def load_elements() -> pd.DataFrame:
    rows = _get("elements",
        "is_active=eq.true&order=sort_order.asc"
        "&select=element_id,element_name,category,default_rate_unit,area_basis")
    return pd.DataFrame(rows)

# -- Constants --

LOCATIONS      = ["London", "Birmingham", "Manchester"]
PROJECT_TYPES  = ["Office", "Residential", "Retail", "Mixed Use",
                  "Industrial", "Education", "Healthcare", "Hospitality", "Other"]
CONTRACT_TYPES = ["Shell & Core", "Cat A Fit-Out",
                  "Shell & Core + Cat A Fit-Out", "Refurbishment", "New Build"]
SPEC_LEVELS    = ["Budget", "Standard", "High Spec", "Bespoke"]
PACKAGES       = ["Shell & Core", "Cat A Fit-Out"]

PCT_CATEGORIES = {"On Costs"}

# Only used as a fallback when an element's area_basis column is blank.
NIA_CATEGORIES = {"Fit-Out", "Cat A Fit-Out"}

# -- Element type helpers --

def _element_type(row) -> str:
    rate_unit = str(row.get("default_rate_unit") or "").strip()
    category  = str(row.get("category") or "").strip()
    if rate_unit == "%" or category in PCT_CATEGORIES:
        return "pct"
    if rate_unit == "£/nr" or str(row.get("area_basis") or "").strip().lower() == "nr":
        return "count"
    return "area"

def _area_basis(row) -> str:
    """
    Decide GIA / NIA / % for an element.

    The element's `area_basis` column is the single source of truth — the
    very same column the user-facing Element Areas page uses to default Cat A
    elements to NIA. This guarantees the rate that gets SUBMITTED (cost ÷ area)
    sits on the same basis as the rate later APPLIED in the estimate, so the
    two can never silently disagree. Category names are only a last-resort
    fallback when the column is blank.
    """
    rate_unit = str(row.get("default_rate_unit") or "").strip()
    category  = str(row.get("category") or "").strip()
    basis_col = str(row.get("area_basis") or "").strip().upper()

    if rate_unit == "%" or category in PCT_CATEGORIES:
        return "%"
    if basis_col == "NIA":
        return "NIA"
    if basis_col == "GIA":
        return "GIA"
    return "NIA" if category in NIA_CATEGORIES else "GIA"

def _area_basis_label(basis: str, gia_m2: float, nia_m2: float, unit: str) -> str:
    if basis == "%":
        return "% of build cost"
    area_m2 = nia_m2 if basis == "NIA" else gia_m2
    if area_m2 <= 0:
        return f"{basis} - enter area in Step 1"
    if unit == "ft²":
        return f"{basis}: {area_m2 * FT2_PER_M2:,.0f} ft²"
    return f"{basis}: {area_m2:,.0f} m²"

# -- Session state helpers --

def _init_session():
    st.session_state.setdefault("ars_step", 1)
    st.session_state.setdefault("ars_project_saved", False)
    st.session_state.setdefault("ars_submission_id", None)
    st.session_state.setdefault("ars_rates", {})
    st.session_state.setdefault("ars_unit", "m²")
    st.session_state.setdefault("ars_project_name", "")
    st.session_state.setdefault("ars_location", "London")
    st.session_state.setdefault("ars_project_type", "Office")
    st.session_state.setdefault("ars_package", "Shell & Core")
    st.session_state.setdefault("ars_gia_m2", 0.0)
    st.session_state.setdefault("ars_nia_m2", 0.0)
    st.session_state.setdefault("ars_storeys_above", 0)
    st.session_state.setdefault("ars_storeys_below", 0)
    st.session_state.setdefault("ars_spec_level", "Standard")
    st.session_state.setdefault("ars_cost_date", date.today())
    st.session_state.setdefault("ars_notes", "")
    st.session_state.setdefault("ars_submitted_by", "")
    # -- Quick rate entry mode --
    st.session_state.setdefault("ars_quick_rates", {})

def _reset_form():
    keys = [k for k in st.session_state.keys() if k.startswith("ars_")]
    for k in keys:
        del st.session_state[k]
    st.cache_data.clear()

# -- Step indicator --

def _render_steps(current: int):
    steps = ["1  Project Details", "2  Cost Entry", "3  Review & Submit"]
    cols = st.columns(3)
    for i, (col, label) in enumerate(zip(cols, steps), 1):
        with col:
            if i < current:
                colour, prefix, weight = "#c8a84b", "✓ ", "500"
            elif i == current:
                colour, prefix, weight = "#0f1f3d", "", "700"
            else:
                colour, prefix, weight = "#b8c0cc", "", "400"
            st.markdown(
                f'<div style="text-align:center;padding:0.6rem 0.5rem;'
                f'border-bottom:3px solid {colour};font-size:0.78rem;'
                f'font-weight:{weight};letter-spacing:0.06em;'
                f'text-transform:uppercase;color:{colour};">'
                f'{prefix}{label}</div>',
                unsafe_allow_html=True)
    st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

# -- Step 1: Project Details --

def _render_project_details():
    st.markdown("#### Project Details")
    st.markdown(
        "<p style='color:#8a96a8;font-size:0.9rem;margin-top:-0.5rem;'>"
        "Enter the key details for the cost plan you are logging rates from. "
        "GIA and NIA are used to calculate £/m² rates automatically.</p>",
        unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.session_state.ars_project_name = st.text_input(
            "Project Name *", value=st.session_state.ars_project_name,
            placeholder="e.g. York Way - Stage 3", key="ars_name_input")
        st.session_state.ars_location = st.selectbox(
            "Location *", LOCATIONS,
            index=LOCATIONS.index(st.session_state.ars_location), key="ars_location_input")
        st.session_state.ars_project_type = st.selectbox(
            "Project Type", PROJECT_TYPES,
            index=PROJECT_TYPES.index(st.session_state.ars_project_type), key="ars_ptype_input")
        st.session_state.ars_package = st.selectbox(
            "Package *", CONTRACT_TYPES,
            index=CONTRACT_TYPES.index(st.session_state.ars_package), key="ars_package_input")
        st.session_state.ars_spec_level = st.selectbox(
            "Spec Level", SPEC_LEVELS,
            index=SPEC_LEVELS.index(st.session_state.ars_spec_level), key="ars_spec_input")
        st.session_state.ars_submitted_by = st.text_input(
            "Your name", value=st.session_state.ars_submitted_by,
            placeholder="e.g. J. Smith", key="ars_submitter_input")

    with c2:
        st.session_state.ars_cost_date = st.date_input(
            "Cost Plan Date *", value=st.session_state.ars_cost_date, key="ars_date_input")

        area_unit = st.radio("Area input unit", ["m²", "ft²"],
                             horizontal=True, key="ars_area_unit_step1")

        if area_unit == "ft²":
            gia_display = st.session_state.ars_gia_m2 * FT2_PER_M2
            gia_entered = st.number_input("GIA (ft²) *", min_value=0.0, step=1000.0,
                format="%.0f", value=float(gia_display), key="ars_gia_input")
            st.session_state.ars_gia_m2 = gia_entered / FT2_PER_M2
            if gia_entered > 0: st.caption(f"≈ {st.session_state.ars_gia_m2:,.0f} m²")
        else:
            gia_entered = st.number_input("GIA (m²) *", min_value=0.0, step=100.0,
                format="%.0f", value=float(st.session_state.ars_gia_m2), key="ars_gia_input")
            st.session_state.ars_gia_m2 = gia_entered
            if gia_entered > 0: st.caption(f"≈ {gia_entered * FT2_PER_M2:,.0f} ft²")

        if area_unit == "ft²":
            nia_display = st.session_state.ars_nia_m2 * FT2_PER_M2
            nia_entered = st.number_input("NIA (ft²)", min_value=0.0, step=1000.0,
                format="%.0f", value=float(nia_display), key="ars_nia_input")
            st.session_state.ars_nia_m2 = nia_entered / FT2_PER_M2
            if nia_entered > 0: st.caption(f"≈ {st.session_state.ars_nia_m2:,.0f} m²")
        else:
            nia_entered = st.number_input("NIA (m²)", min_value=0.0, step=100.0,
                format="%.0f", value=float(st.session_state.ars_nia_m2), key="ars_nia_input")
            st.session_state.ars_nia_m2 = nia_entered
            if nia_entered > 0: st.caption(f"≈ {nia_entered * FT2_PER_M2:,.0f} ft²")

        gia_m2 = st.session_state.ars_gia_m2
        nia_m2 = st.session_state.ars_nia_m2
        if gia_m2 > 0 and nia_m2 > 0:
            if nia_m2 > gia_m2:
                st.warning("⚠️ NIA cannot exceed GIA.")
            else:
                st.metric("Net:Gross ratio", f"{(nia_m2/gia_m2)*100:.1f}%")

        col_ab, col_bg = st.columns(2)
        with col_ab:
            st.session_state.ars_storeys_above = st.number_input(
                "Storeys above ground", min_value=0, max_value=100, step=1,
                value=st.session_state.ars_storeys_above, key="ars_above_input")
        with col_bg:
            st.session_state.ars_storeys_below = st.number_input(
                "Storeys below ground", min_value=0, max_value=20, step=1,
                value=st.session_state.ars_storeys_below, key="ars_below_input")

    st.session_state.ars_notes = st.text_area(
        "Notes (optional)", value=st.session_state.ars_notes,
        placeholder="Any context about this project or the rates...",
        height=80, key="ars_notes_input")

    gia_m2 = st.session_state.ars_gia_m2
    nia_m2 = st.session_state.ars_nia_m2
    if gia_m2 > 0:
        st.info(
            f"📐 **Rate calculation basis:** "
            f"Most elements use GIA ({gia_m2:,.0f} m²). "
            f"Cat A Fit-Out uses NIA ({nia_m2:,.0f} m²"
            f"{' — ⚠️ enter NIA above' if nia_m2 == 0 else ''}). "
            f"Count items (lifts, WCs, stairs) use number × rate. "
            f"On Costs are entered as a percentage.")

    st.markdown("---")
    can_proceed = bool(st.session_state.ars_project_name
        and st.session_state.ars_location and st.session_state.ars_package
        and st.session_state.ars_cost_date and st.session_state.ars_gia_m2 > 0)

    if not can_proceed:
        st.warning("⚠️ Project name, location, package, cost date and GIA are required.")

    col_next, _ = st.columns([1, 4])
    with col_next:
        if st.button("Next: Enter Costs →", type="primary",
                     disabled=not can_proceed, use_container_width=True):
            st.session_state.ars_step = 2
            st.rerun()

# -- Step 2: Cost Entry --

def _render_cost_entry(elements_df: pd.DataFrame):
    gia_m2 = st.session_state.ars_gia_m2
    nia_m2 = st.session_state.ars_nia_m2

    col_toggle, col_progress, _ = st.columns([1, 2, 3])
    with col_toggle:
        unit = st.radio("Area display unit", ["m²", "ft²"], horizontal=True,
                        key="ars_unit_toggle", label_visibility="collapsed")
        st.session_state.ars_unit = unit

    logged = len([v for v in st.session_state.ars_rates.values()
                  if (v.get("total_cost") or 0) > 0
                  or (v.get("pct") or 0) > 0
                  or (v.get("count") or 0) > 0
                  or v.get("na")])
    total = len(elements_df)

    with col_progress:
        st.markdown(
            f"<div style='padding-top:0.4rem;font-size:0.82rem;color:#8a96a8;'>"
            f"<b style='color:#0f1f3d;'>{logged}</b> of {total} elements entered</div>",
            unsafe_allow_html=True)
        st.progress(logged / total if total > 0 else 0)

    st.markdown(
        "<p style='color:#8a96a8;font-size:0.88rem;margin-bottom:0.5rem;'>"
        "Enter costs from your cost plan. For <b>area elements</b>, enter the "
        "total cost and the £/m² rate is calculated automatically. "
        "For <b>count items</b> enter cost + number of items. "
        "For <b>On Costs</b> enter the percentage directly.</p>",
        unsafe_allow_html=True)

    gia_d = gia_m2 * FT2_PER_M2 if unit == "ft²" else gia_m2
    nia_d = nia_m2 * FT2_PER_M2 if unit == "ft²" else nia_m2
    st.markdown(
        f'<div style="background:#f5f4f0;border:1px solid #e4e0d8;'
        f'border-radius:6px;padding:0.6rem 1rem;margin-bottom:1rem;'
        f'font-size:0.82rem;color:#0f1f3d;display:flex;gap:2rem;flex-wrap:wrap;">'
        f'<span>📐 <b>GIA:</b> {gia_d:,.0f} {unit}</span>'
        f'<span>📐 <b>NIA:</b> {nia_d:,.0f} {unit} (Cat A)</span>'
        f'<span>🔢 <b>Count:</b> number × rate</span>'
        f'<span>📊 <b>On Costs:</b> % entry</span></div>',
        unsafe_allow_html=True)

    for category, cat_df in elements_df.groupby("category", sort=False):
        # Representative basis for the category header badge only. The real,
        # per-element basis is worked out inside the element loop below.
        basis = _area_basis(cat_df.iloc[0]) if len(cat_df) > 0 else "GIA"

        cat_logged = sum(1 for _, row in cat_df.iterrows()
            if (st.session_state.ars_rates.get(row["element_id"], {}).get("total_cost") or 0) > 0
            or (st.session_state.ars_rates.get(row["element_id"], {}).get("pct") or 0) > 0
            or (st.session_state.ars_rates.get(row["element_id"], {}).get("count") or 0) > 0
            or st.session_state.ars_rates.get(row["element_id"], {}).get("na"))
        cat_total = len(cat_df)

        sample_type = _element_type(cat_df.iloc[0]) if len(cat_df) > 0 else "area"
        badge_map = {
            "area":  ("GIA" if basis == "GIA" else "NIA",
                      {"GIA":"#e8f0fe","NIA":"#e8f5e9"}.get(basis,"#f0f0f0"),
                      {"GIA":"#1a4a9e","NIA":"#2e7d32"}.get(basis,"#555")),
            "count": ("£/nr", "#fce8e6", "#c62828"),
            "pct":   ("%", "#fff8e6", "#c8a84b"),
        }
        badge_label, bc, bt = badge_map.get(sample_type, ("GIA", "#e8f0fe", "#1a4a9e"))

        st.markdown(
            f'<div style="display:flex;justify-content:space-between;'
            f'align-items:center;margin:1.4rem 0 0.5rem;">'
            f'<span style="font-family:\'DM Serif Display\',serif;'
            f'font-size:1.1rem;color:#0f1f3d;">{category}</span>'
            f'<div style="display:flex;gap:0.5rem;align-items:center;">'
            f'<span style="background:{bc};color:{bt};font-size:0.68rem;'
            f'font-weight:700;letter-spacing:0.06em;text-transform:uppercase;'
            f'padding:0.15rem 0.5rem;border-radius:4px;">÷ {badge_label}</span>'
            f'<span style="font-size:0.75rem;color:#8a96a8;">'
            f'{cat_logged}/{cat_total} entered</span></div></div>',
            unsafe_allow_html=True)

        for _, row in cat_df.iterrows():
            element_id = row["element_id"]
            element_name = row["element_name"]
            existing = st.session_state.ars_rates.get(element_id, {})
            el_type = _element_type(row)
            # Per-element basis (from the area_basis column) and the matching
            # area to divide by. This is what keeps each element's rate on the
            # correct GIA/NIA basis.
            el_basis   = _area_basis(row)
            el_area_m2 = nia_m2 if el_basis == "NIA" else gia_m2

            # == ON COSTS (%) ==
            if el_type == "pct":
                existing_pct = existing.get("pct", 0.0) or 0.0
                is_na = existing.get("na", False)
                badge = "✓ " if existing_pct > 0 else ("－ " if is_na else "")
                hint = " — N/A" if is_na else (f" — {existing_pct:.2f}%" if existing_pct > 0 else "")

                with st.expander(f"{badge}{element_id}  {element_name}{hint}"):
                    na_val = st.checkbox("N/A — not applicable", value=is_na, key=f"ars_na_{element_id}")
                    if na_val:
                        notes_val = st.text_input("Notes", value=existing.get("notes",""),
                            placeholder="Optional...", key=f"ars_notes_{element_id}")
                        st.session_state.ars_rates[element_id] = {
                            "na":True,"pct":None,"rate_m2":None,"rate_unit":"N/A",
                            "total_cost":None,"count":None,
                            "package":existing.get("package",PACKAGES[0]),"notes":notes_val or None}
                    else:
                        c1, c2, c3 = st.columns([2,2,3])
                        with c1:
                            pct_val = st.number_input("Percentage (%)", min_value=0.0,
                                max_value=100.0, step=0.1, format="%.2f",
                                value=float(existing_pct), key=f"ars_pct_{element_id}")
                        with c2:
                            pkg_val = st.selectbox("Package", PACKAGES+["Both"],
                                index=(PACKAGES+["Both"]).index(existing.get("package",PACKAGES[0]))
                                if existing.get("package") in PACKAGES+["Both"] else 0,
                                key=f"ars_pkg_{element_id}")
                        with c3:
                            notes_val = st.text_input("Notes", value=existing.get("notes",""),
                                placeholder="Optional...", key=f"ars_notes_{element_id}",
                                label_visibility="collapsed")
                        if pct_val > 0:
                            st.session_state.ars_rates[element_id] = {
                                "na":False,"pct":pct_val,"rate_m2":None,"rate_unit":"%",
                                "total_cost":None,"count":None,"package":pkg_val,
                                "notes":notes_val or None}
                        elif element_id in st.session_state.ars_rates:
                            del st.session_state.ars_rates[element_id]

            # == COUNT ELEMENTS (£/nr) ==
            elif el_type == "count":
                existing_cost = existing.get("total_cost", 0.0) or 0.0
                existing_count = existing.get("count", 0) or 0
                is_na = existing.get("na", False)
                badge = "✓ " if existing_cost > 0 else ("－ " if is_na else "")
                rate_hint = ""
                if is_na: rate_hint = " — N/A"
                elif existing_cost > 0 and existing_count > 0:
                    rate_hint = f" — £{existing_cost/existing_count:,.0f}/nr"
                elif existing_cost > 0:
                    rate_hint = f" — £{existing_cost:,.0f} total"

                with st.expander(f"{badge}{element_id}  {element_name}{rate_hint}"):
                    na_val = st.checkbox("N/A — not applicable", value=is_na, key=f"ars_na_{element_id}")
                    if na_val:
                        notes_val = st.text_input("Notes", value=existing.get("notes",""),
                            placeholder="Optional...", key=f"ars_notes_{element_id}")
                        st.session_state.ars_rates[element_id] = {
                            "na":True,"total_cost":None,"rate_m2":None,"rate_unit":"N/A",
                            "pct":None,"count":None,
                            "package":existing.get("package",PACKAGES[0]),"notes":notes_val or None}
                    else:
                        c1, c2, c3 = st.columns([2,1,3])
                        with c1:
                            cost_val = st.number_input("Total cost (£)", min_value=0.0,
                                step=1000.0, format="%.0f", value=float(existing_cost),
                                key=f"ars_cost_{element_id}")
                        with c2:
                            count_val = st.number_input("Number of items", min_value=0,
                                step=1, format="%d", value=int(existing_count),
                                key=f"ars_count_{element_id}")
                        with c3:
                            notes_val = st.text_input("Notes", value=existing.get("notes",""),
                                placeholder="Optional...", key=f"ars_notes_{element_id}",
                                label_visibility="collapsed")

                        if cost_val > 0 and count_val > 0:
                            rate_nr = cost_val / count_val
                            st.markdown(
                                f'<div style="background:#f5f4f0;border:1px solid #e4e0d8;'
                                f'border-radius:6px;padding:0.6rem 0.9rem;margin-top:0.25rem;'
                                f'display:inline-block;">'
                                f'<div style="font-size:0.7rem;color:#8a96a8;'
                                f'text-transform:uppercase;letter-spacing:0.06em;">Calculated rate</div>'
                                f'<div style="font-family:\'DM Serif Display\',serif;'
                                f'font-size:1.2rem;color:#0f1f3d;">£{rate_nr:,.0f} / nr</div>'
                                f'<div style="font-size:0.72rem;color:#8a96a8;">'
                                f'£{cost_val:,.0f} ÷ {count_val} items</div></div>',
                                unsafe_allow_html=True)
                            st.session_state.ars_rates[element_id] = {
                                "na":False,"total_cost":cost_val,"rate_m2":rate_nr,
                                "rate_unit":"£/nr","pct":None,"count":count_val,
                                "package":PACKAGES[0],"notes":notes_val or None}
                        elif cost_val > 0 and count_val == 0:
                            st.warning("⚠️ Enter the number of items to calculate the rate.")
                        elif element_id in st.session_state.ars_rates:
                            del st.session_state.ars_rates[element_id]

            # == AREA ELEMENTS (£/m²) ==
            else:
                existing_cost = existing.get("total_cost", 0.0) or 0.0
                existing_override_m2 = existing.get("override_area_m2") or 0.0
                is_na = existing.get("na", False)
                badge = "✓ " if existing_cost > 0 else ("－ " if is_na else "")
                rate_hint = ""
                if is_na: rate_hint = " — N/A"
                elif existing_cost > 0:
                    _eff = existing_override_m2 if existing_override_m2 > 0 else el_area_m2
                    rate_hint = f" — £{existing_cost/_eff:,.2f}/m²" if _eff > 0 else f" — £{existing_cost:,.0f} total"

                basis_label = _area_basis_label(el_basis, gia_m2, nia_m2, unit)

                with st.expander(f"{badge}{element_id}  {element_name}{rate_hint}"):
                    st.markdown(
                        f"<div style='font-size:0.75rem;color:#8a96a8;margin-bottom:0.5rem;'>"
                        f"Default rate basis: {basis_label}</div>", unsafe_allow_html=True)

                    na_val = st.checkbox("N/A — not applicable", value=is_na, key=f"ars_na_{element_id}")
                    if na_val:
                        notes_val = st.text_input("Notes", value=existing.get("notes",""),
                            placeholder="Optional...", key=f"ars_notes_{element_id}")
                        st.session_state.ars_rates[element_id] = {
                            "na":True,"total_cost":None,"rate_m2":None,"rate_unit":"N/A",
                            "pct":None,"count":None,
                            "package":existing.get("package",PACKAGES[0]),
                            "notes":notes_val or None,"override_area_m2":None}
                    else:
                        c1, c2, c3 = st.columns([2,2,3])
                        with c1:
                            cost_val = st.number_input("Total cost (£)", min_value=0.0,
                                step=1000.0, format="%.0f", value=float(existing_cost),
                                key=f"ars_cost_{element_id}")
                        with c2:
                            pkg_val = st.selectbox("Package", PACKAGES,
                                index=PACKAGES.index(existing.get("package",PACKAGES[0]))
                                if existing.get("package") in PACKAGES else 0,
                                key=f"ars_pkg_{element_id}")
                        with c3:
                            notes_val = st.text_input("Notes", value=existing.get("notes",""),
                                placeholder="Optional...", key=f"ars_notes_{element_id}",
                                label_visibility="collapsed")

                        use_override = st.checkbox(
                            "📐 Override area — I know the exact size from drawings",
                            value=existing_override_m2 > 0, key=f"ars_override_chk_{element_id}")

                        override_area_m2 = 0.0
                        if use_override:
                            st.markdown(
                                "<div style='background:#fff8e6;border-left:3px solid #c8a84b;"
                                "padding:0.5rem 0.8rem;border-radius:0 4px 4px 0;"
                                "font-size:0.82rem;color:#7a5c00;margin:0.4rem 0;'>"
                                "⚠️ Override active — rate uses element area, not GIA/NIA.</div>",
                                unsafe_allow_html=True)
                            ov_col1, _ = st.columns([2,3])
                            with ov_col1:
                                ov_unit = st.radio("Area unit", ["m²","ft²"], horizontal=True,
                                    key=f"ars_ov_unit_{element_id}")
                                if ov_unit == "ft²":
                                    ov_display = existing_override_m2*FT2_PER_M2 if existing_override_m2>0 else 0.0
                                    ov_entered = st.number_input("Element area (ft²)", min_value=0.0,
                                        step=10.0, format="%.0f", value=float(ov_display),
                                        key=f"ars_ov_area_{element_id}")
                                    override_area_m2 = ov_entered / FT2_PER_M2
                                    if ov_entered > 0: st.caption(f"≈ {override_area_m2:,.1f} m²")
                                else:
                                    ov_entered = st.number_input("Element area (m²)", min_value=0.0,
                                        step=10.0, format="%.1f", value=float(existing_override_m2),
                                        key=f"ars_ov_area_{element_id}")
                                    override_area_m2 = ov_entered
                                    if ov_entered > 0: st.caption(f"≈ {ov_entered*FT2_PER_M2:,.0f} ft²")

                        eff_area_m2 = override_area_m2 if (use_override and override_area_m2 > 0) else el_area_m2
                        eff_lbl = f"element override ({override_area_m2:,.1f} m²)" if (use_override and override_area_m2 > 0) else el_basis

                        if cost_val > 0:
                            if eff_area_m2 > 0:
                                rate_m2 = cost_val / eff_area_m2
                                col_calc, _ = st.columns([2,2])
                                with col_calc:
                                    ov_badge = ("<span style='background:#fff8e6;color:#c8a84b;"
                                        "font-size:0.65rem;font-weight:700;padding:0.1rem 0.4rem;"
                                        "border-radius:3px;margin-left:0.4rem;'>OVERRIDE</span>"
                                        if (use_override and override_area_m2 > 0) else "")
                                    st.markdown(
                                        f'<div style="background:#f5f4f0;border:1px solid #e4e0d8;'
                                        f'border-radius:6px;padding:0.6rem 0.9rem;margin-top:0.25rem;">'
                                        f'<div style="font-size:0.7rem;color:#8a96a8;'
                                        f'text-transform:uppercase;letter-spacing:0.06em;">'
                                        f'Calculated rate{ov_badge}</div>'
                                        f'<div style="font-family:\'DM Serif Display\',serif;'
                                        f'font-size:1.2rem;color:#0f1f3d;">£{rate_m2:,.2f} / m²</div>'
                                        f'<div style="font-size:0.72rem;color:#8a96a8;">'
                                        f'£{cost_val:,.0f} ÷ {eff_area_m2:,.1f} m² ({eff_lbl})</div></div>',
                                        unsafe_allow_html=True)
                            else:
                                rate_m2 = None
                                if use_override:
                                    st.warning("⚠️ Enter the element area above to calculate the rate.")
                                else:
                                    st.warning(f"⚠️ {el_basis} is 0 — go back to Step 1 or use override.")

                            st.session_state.ars_rates[element_id] = {
                                "na":False,"total_cost":cost_val,"rate_m2":rate_m2,
                                "rate_unit":"£/m2","pct":None,"count":None,
                                "package":pkg_val,"notes":notes_val or None,
                                "override_area_m2":override_area_m2 if (use_override and override_area_m2>0) else None}
                        elif element_id in st.session_state.ars_rates:
                            del st.session_state.ars_rates[element_id]

    st.markdown("---")
    col_back, _, col_next = st.columns([1,4,1])
    with col_back:
        if st.button("← Project Details", use_container_width=True):
            st.session_state.ars_step = 1; st.rerun()
    with col_next:
        entered_count = len([v for v in st.session_state.ars_rates.values()
            if (v.get("total_cost") or 0)>0 or (v.get("pct") or 0)>0
            or (v.get("count") or 0)>0 or v.get("na")])
        if st.button("Review & Submit →", type="primary",
                     disabled=entered_count==0, use_container_width=True):
            st.session_state.ars_step = 3; st.rerun()
    if entered_count == 0:
        st.caption("Enter at least one cost to proceed.")

# -- Step 3: Review --

def _render_review(elements_df: pd.DataFrame):
    gia_m2 = st.session_state.ars_gia_m2
    nia_m2 = st.session_state.ars_nia_m2

    st.markdown("#### Review Before Submitting")
    st.markdown(
        "<p style='color:#8a96a8;font-size:0.9rem;margin-top:-0.5rem;'>"
        "Check everything below. Once submitted, rates are held for review.</p>",
        unsafe_allow_html=True)

    st.markdown(
        f'<div style="background:#fff;border:1px solid #ddd8d0;border-radius:8px;'
        f'padding:1.25rem 1.5rem;margin-bottom:1.5rem;font-size:0.875rem;'
        f'line-height:2;color:#0f1f3d;">'
        f'<div style="font-family:\'DM Serif Display\',serif;font-size:1.1rem;'
        f'margin-bottom:0.5rem;">{st.session_state.ars_project_name}</div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:0 2rem;">'
        f'<div>📍 <b>Location:</b> {st.session_state.ars_location}</div>'
        f'<div>📦 <b>Package:</b> {st.session_state.ars_package}</div>'
        f'<div>🏢 <b>Type:</b> {st.session_state.ars_project_type}</div>'
        f'<div>⭐ <b>Spec:</b> {st.session_state.ars_spec_level}</div>'
        f'<div>📐 <b>GIA:</b> {gia_m2:,.0f} m² ({gia_m2*FT2_PER_M2:,.0f} ft²)</div>'
        f'<div>📐 <b>NIA:</b> {nia_m2:,.0f} m² ({nia_m2*FT2_PER_M2:,.0f} ft²)</div>'
        f'<div>🏗️ <b>Storeys:</b> {st.session_state.ars_storeys_above} above · '
        f'{st.session_state.ars_storeys_below} below</div>'
        f'<div>📅 <b>Cost date:</b> {st.session_state.ars_cost_date}</div>'
        f'</div></div>', unsafe_allow_html=True)

    rates_data = st.session_state.ars_rates
    if not rates_data:
        st.warning("No costs entered."); return

    el_lookup = {r["element_id"]: r for _, r in elements_df.iterrows()}
    rows = []
    total_cost = 0.0

    for element_id, data in rates_data.items():
        el = el_lookup.get(element_id)
        if el is not None:
            category = el.get("category", "—")
            name     = el.get("element_name", element_id)
            basis    = _area_basis(el)
        else:
            category, name, basis = "—", element_id, "GIA"

        if data.get("na"):
            rows.append({"ID":element_id,"Element":name,"Total Cost":"—",
                "Basis":"—","Rate":"N/A","Notes":data.get("notes") or "—"})
        elif data.get("rate_unit") == "%":
            rows.append({"ID":element_id,"Element":name,"Total Cost":"—",
                "Basis":"%","Rate":f"{data['pct']:.2f}%","Notes":data.get("notes") or "—"})
        elif data.get("rate_unit") == "£/nr":
            cost = data.get("total_cost",0) or 0
            count = data.get("count",0) or 0
            total_cost += cost
            rate_nr = cost/count if count > 0 else 0
            rows.append({"ID":element_id,"Element":name,
                "Total Cost":f"£{cost:,.0f}","Basis":f"{count} nr",
                "Rate":f"£{rate_nr:,.0f}/nr" if rate_nr>0 else "—",
                "Notes":data.get("notes") or "—"})
        else:
            cost = data.get("total_cost",0) or 0
            rate_m2 = data.get("rate_m2")
            total_cost += cost
            rows.append({"ID":element_id,"Element":name,
                "Total Cost":f"£{cost:,.0f}","Basis":basis,
                "Rate":f"£{rate_m2:,.2f}/m²" if rate_m2 else "⚠️ No area",
                "Notes":data.get("notes") or "—"})

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Elements entered", len(rows))
    with c2: st.metric("Total cost logged", f"£{total_cost:,.0f}")
    with c3:
        if gia_m2 > 0 and total_cost > 0:
            st.metric("Overall £/m² GIA", f"£{total_cost/gia_m2:,.0f}")
    with c4: st.metric("Status after submit", "Pending review")

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    missing = [r for r in rows if r["Rate"] == "⚠️ No area"]
    if missing:
        st.warning(f"⚠️ {len(missing)} element(s) have no calculable rate (area is 0).")

    st.markdown("---")
    col_back, _, col_submit = st.columns([1,3,1])
    with col_back:
        if st.button("← Edit Costs", use_container_width=True):
            st.session_state.ars_step = 2; st.rerun()
    with col_submit:
        if st.button("✅  Submit to Supabase", type="primary", use_container_width=True):
            _submit_to_supabase(elements_df)

# -- Submit to Supabase --

def _submit_to_supabase(elements_df: pd.DataFrame):
    try:
        with st.spinner("Submitting to Supabase..."):
            project_row = _post("submitted_projects", {
                "project_name":  st.session_state.ars_project_name,
                "location":      st.session_state.ars_location,
                "project_type":  st.session_state.ars_project_type,
                "package":       st.session_state.ars_package,
                "gia_m2":        st.session_state.ars_gia_m2 or None,
                "nia_m2":        st.session_state.ars_nia_m2 or None,
                "storeys_above": st.session_state.ars_storeys_above or None,
                "storeys_below": st.session_state.ars_storeys_below or None,
                "spec_level":    st.session_state.ars_spec_level,
                "cost_date":     str(st.session_state.ars_cost_date),
                "notes":         st.session_state.ars_notes or None,
                "submitted_by":  st.session_state.ars_submitted_by or None,
                "status":        "pending",
            })
            submission_id = project_row["id"]

            for element_id, data in st.session_state.ars_rates.items():
                has_cost = data.get("total_cost",0) or 0
                has_pct = data.get("pct",0) or 0
                is_na = bool(data.get("na"))
                if not has_cost and not has_pct and not is_na:
                    continue

                if is_na:
                    rate_value = 0; rate_unit = "N/A"
                elif data.get("rate_unit") == "%":
                    rate_value = data["pct"]; rate_unit = "%"
                elif data.get("rate_unit") == "£/nr":
                    rate_value = data.get("rate_m2") or 0; rate_unit = "£/nr"
                else:
                    rate_value = data.get("rate_m2") or 0
                    rate_unit = data.get("rate_unit", "£/m2")

                notes_str = data.get("notes")
                if data.get("override_area_m2"):
                    notes_str = f"[Area override: {data['override_area_m2']:,.1f} m²] {notes_str or ''}".strip()
                elif data.get("count"):
                    notes_str = f"[Count: {data['count']}] {notes_str or ''}".strip()

                _post("submitted_rates", {
                    "submission_id": submission_id,
                    "element_id":    element_id,
                    "package":       data.get("package", "Shell & Core"),
                    "rate":          rate_value,
                    "rate_unit":     rate_unit,
                    "quantity":      data.get("override_area_m2") or data.get("count"),
                    "total_cost":    data.get("total_cost"),
                    "notes":         notes_str,
                })

        st.session_state.ars_submission_id = submission_id
        st.session_state.ars_project_saved = True
        st.rerun()
    except Exception as e:
        st.error(f"❌ Submission failed: {e}")
        st.caption("Check your Supabase credentials and try again.")

# -- Success screen --

def _render_success():
    st.markdown(
        '<div style="text-align:center;padding:3rem 2rem;">'
        '<div style="font-size:3rem;margin-bottom:1rem;">✅</div>'
        '<div style="font-family:\'DM Serif Display\',serif;font-size:1.6rem;'
        'color:#0f1f3d;margin-bottom:0.5rem;">Rates Submitted Successfully</div>'
        '<div style="color:#8a96a8;font-size:0.9rem;max-width:480px;'
        'margin:0 auto 2rem;">Your rates are now in Supabase with status '
        '<b>pending</b>. Go to <b>Publish Rates</b> to push them live.</div></div>',
        unsafe_allow_html=True)

    if st.session_state.ars_submission_id:
        st.markdown(
            f"<div style='text-align:center;font-size:0.78rem;color:#b8c0cc;"
            f"margin-bottom:2rem;'>Submission ID: "
            f"<code>{st.session_state.ars_submission_id}</code></div>",
            unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        if st.button("＋  Submit Another", type="primary", use_container_width=True):
            _reset_form(); st.rerun()
    with col3:
        if st.button("📤  Publish Rates →", use_container_width=True):
            st.session_state.page_idx = 8; st.rerun()

# =====================================================================
# QUICK RATE ENTRY MODE
# Enter a known rate directly (no cost/area maths). The rate is always
# anchored as the MEDIAN (Standard) so Publish Rates fans out the four
# spec bands around it via its factor ladder. Saves to the SAME
# submitted_projects / submitted_rates tables as the detailed flow.
# =====================================================================

def _render_quick_entry(elements_df: pd.DataFrame):
    st.markdown("#### Quick Rate Entry")
    st.markdown(
        "<p style='color:#8a96a8;font-size:0.9rem;margin-top:-0.5rem;'>"
        "Type rates you already know straight in \u2014 no cost plan needed. "
        "Most elements take a <b>\u00a3/m\u00b2</b> rate, count items take "
        "<b>\u00a3/nr</b>, and On Costs take a <b>%</b>. Each rate is treated "
        "as the <b>median</b>; the spec bands are generated around it when you "
        "publish. Leave anything you don't have blank.</p>",
        unsafe_allow_html=True)

    # ---- Compact header (one set of details for the whole batch) ----
    c1, c2 = st.columns(2)
    with c1:
        st.session_state.ars_project_name = st.text_input(
            "Source / Project Name *", value=st.session_state.ars_project_name,
            placeholder="e.g. Benchmark set - Office", key="arq_name_input")
        st.session_state.ars_location = st.selectbox(
            "Location *", LOCATIONS,
            index=LOCATIONS.index(st.session_state.ars_location),
            key="arq_location_input")
        st.session_state.ars_project_type = st.selectbox(
            "Project Type", PROJECT_TYPES,
            index=PROJECT_TYPES.index(st.session_state.ars_project_type),
            key="arq_ptype_input")
    with c2:
        st.session_state.ars_package = st.selectbox(
            "Package (applies to all rates below) *", PACKAGES,
            index=PACKAGES.index(st.session_state.ars_package)
            if st.session_state.ars_package in PACKAGES else 0,
            key="arq_package_input")
        st.session_state.ars_submitted_by = st.text_input(
            "Your name", value=st.session_state.ars_submitted_by,
            placeholder="e.g. J. Smith", key="arq_submitter_input")

    st.session_state.ars_notes = st.text_area(
        "Notes (optional)", value=st.session_state.ars_notes,
        placeholder="Where these rates came from, date, assumptions...",
        height=70, key="arq_notes_input")

    st.info("\u2139\ufe0f Each rate is logged as the **median (Standard)**. "
            "The Budget / High Spec / Bespoke bands are created automatically "
            "around it on the Publish Rates page.")

    # ---- Progress ----
    quick = st.session_state.ars_quick_rates
    entered = len([v for v in quick.values() if (v.get("rate") or 0) > 0])
    total = len(elements_df)
    st.markdown(
        f"<div style='font-size:0.82rem;color:#8a96a8;margin:0.5rem 0 0.25rem;'>"
        f"<b style='color:#0f1f3d;'>{entered}</b> of {total} rates entered</div>",
        unsafe_allow_html=True)
    st.progress(entered / total if total > 0 else 0)
    st.markdown("---")

    # ---- One input per element, grouped by category ----
    for category, cat_df in elements_df.groupby("category", sort=False):
        cat_entered = sum(
            1 for _, row in cat_df.iterrows()
            if (quick.get(row["element_id"], {}).get("rate") or 0) > 0)
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;'
            f'align-items:center;margin:1.2rem 0 0.4rem;">'
            f'<span style="font-family:\'DM Serif Display\',serif;'
            f'font-size:1.05rem;color:#0f1f3d;">{category}</span>'
            f'<span style="font-size:0.75rem;color:#8a96a8;">'
            f'{cat_entered}/{len(cat_df)} entered</span></div>',
            unsafe_allow_html=True)

        for _, row in cat_df.iterrows():
            element_id = row["element_id"]
            element_name = row["element_name"]
            el_type = _element_type(row)
            existing = quick.get(element_id, {})
            existing_rate = float(existing.get("rate", 0.0) or 0.0)

            if el_type == "pct":
                unit_label, rate_unit, step, fmt, maxv = "%", "%", 0.1, "%.2f", 100.0
            elif el_type == "count":
                unit_label, rate_unit, step, fmt, maxv = "\u00a3/nr", "\u00a3/nr", 100.0, "%.0f", None
            else:
                unit_label, rate_unit, step, fmt, maxv = "\u00a3/m\u00b2", "\u00a3/m2", 5.0, "%.2f", None

            col_lbl, col_in = st.columns([3, 2])
            with col_lbl:
                st.markdown(
                    f"<div style='padding-top:0.55rem;font-size:0.88rem;color:#0f1f3d;'>"
                    f"<span style='color:#b8c0cc;'>{element_id}</span>&nbsp;&nbsp;"
                    f"{element_name}</div>", unsafe_allow_html=True)
            with col_in:
                kwargs = dict(min_value=0.0, step=step, format=fmt,
                              value=existing_rate, key=f"arq_rate_{element_id}")
                if maxv is not None:
                    kwargs["max_value"] = maxv
                rate_val = st.number_input(f"Rate ({unit_label})", **kwargs)

            if rate_val > 0:
                pkg = "Both" if el_type == "pct" else st.session_state.ars_package
                quick[element_id] = {"rate": rate_val, "rate_unit": rate_unit,
                                     "package": pkg}
            elif element_id in quick:
                del quick[element_id]

    st.session_state.ars_quick_rates = quick

    # ---- Submit ----
    st.markdown("---")
    can_submit = bool(
        st.session_state.ars_project_name
        and st.session_state.ars_location
        and st.session_state.ars_package
        and entered > 0)
    if not can_submit:
        st.warning("\u26a0\ufe0f Enter a source name, location, package and at least one rate.")

    col_submit, _ = st.columns([1, 3])
    with col_submit:
        if st.button("\u2705  Submit Rates to Supabase", type="primary",
                     disabled=not can_submit, use_container_width=True):
            _submit_quick_to_supabase()


def _submit_quick_to_supabase():
    try:
        with st.spinner("Submitting to Supabase..."):
            project_row = _post("submitted_projects", {
                "project_name":  st.session_state.ars_project_name,
                "location":      st.session_state.ars_location,
                "project_type":  st.session_state.ars_project_type,
                "package":       st.session_state.ars_package,
                "gia_m2":        None,
                "nia_m2":        None,
                "storeys_above": None,
                "storeys_below": None,
                "spec_level":    "Standard",  # anchor rate as the median
                "cost_date":     str(st.session_state.ars_cost_date),
                "notes":         (st.session_state.ars_notes
                                  or "Quick rate entry") + " [quick entry]",
                "submitted_by":  st.session_state.ars_submitted_by or None,
                "status":        "pending",
            })
            submission_id = project_row["id"]

            for element_id, data in st.session_state.ars_quick_rates.items():
                rate_value = data.get("rate", 0) or 0
                if rate_value <= 0:
                    continue
                _post("submitted_rates", {
                    "submission_id": submission_id,
                    "element_id":    element_id,
                    "package":       data.get("package", "Shell & Core"),
                    "rate":          rate_value,
                    "rate_unit":     data.get("rate_unit", "\u00a3/m2"),
                    "quantity":      None,
                    "total_cost":    None,
                    "notes":         "Entered as known median rate (quick entry)",
                })

        st.session_state.ars_submission_id = submission_id
        st.session_state.ars_project_saved = True
        st.rerun()
    except Exception as e:
        st.error(f"\u274c Submission failed: {e}")
        st.caption("Check your Supabase credentials and try again.")


# -- Main render --

def render():
    _init_session()

    st.markdown(
        '<div style="margin-bottom:0.25rem;">'
        '<span style="font-family:\'DM Serif Display\',serif;font-size:2rem;'
        'color:#0f1f3d;">Rate Submission</span>'
        '<span style="display:inline-block;margin-left:0.75rem;'
        'background:#0f1f3d;color:#c8a84b;font-size:0.65rem;font-weight:700;'
        'letter-spacing:0.1em;text-transform:uppercase;padding:0.2rem 0.6rem;'
        'border-radius:4px;vertical-align:middle;">Admin</span></div>'
        '<p style="color:#8a96a8;margin-top:0;font-size:0.95rem;">'
        'Log total costs from a completed cost plan. Rates are calculated '
        'automatically and held for review before going live.</p>',
        unsafe_allow_html=True)

    if st.session_state.ars_project_saved:
        _render_success(); return

    try:
        elements_df = load_elements()
    except Exception as e:
        st.error(f"Could not load elements from Supabase: {e}"); return

    if elements_df.empty:
        st.error("No elements found in Supabase."); return

    mode = st.radio(
        "Entry mode",
        ["\U0001F4CB Detailed (cost \u2192 rate)", "\u26a1 Quick (rate per m\u00b2)"],
        horizontal=True, key="ars_mode_toggle")
    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    if "Quick" in mode:
        _render_quick_entry(elements_df)
    else:
        _render_steps(st.session_state.ars_step)
        if st.session_state.ars_step == 1: _render_project_details()
        elif st.session_state.ars_step == 2: _render_cost_entry(elements_df)
        elif st.session_state.ars_step == 3: _render_review(elements_df)

    st.markdown("---")
    st.caption("⚠️ Submitted rates are pending review and will not affect "
               "live estimates until published by an admin.")