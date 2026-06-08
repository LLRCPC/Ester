"""
admin_rate_submission.py
------------------------
Page: Admin — Rate Submission

Allows CPC admins to log rates from completed cost plans directly into Supabase.
Submitted rates land in submitted_projects + submitted_rates with status='pending'
and are reviewed/published manually before feeding into the estimating engine.

Structure:
  Section 1 — Project Details (name, date, location, package, GIA, NIA, storeys, spec)
  Section 2 — Rate Entry (all 64 elements grouped by category, toggle ft²/m²)
  Section 3 — Review & Submit
"""

import streamlit as st
import pandas as pd
from datetime import date
import os
import httpx


# ── Supabase helpers ──────────────────────────────────────────────────────────

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
    r = httpx.get(
        f"{url}/rest/v1/{table}?{params}",
        headers=_headers(key),
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def _post(table: str, payload: dict) -> dict:
    url, key = _creds()
    r = httpx.post(
        f"{url}/rest/v1/{table}",
        headers=_headers(key),
        json=payload,
        timeout=15,
    )
    r.raise_for_status()
    result = r.json()
    return result[0] if isinstance(result, list) else result


# ── Data loaders ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_elements() -> pd.DataFrame:
    rows = _get(
        "elements",
        "is_active=eq.true&order=sort_order.asc&select=element_id,element_name,category,default_rate_unit"
    )
    return pd.DataFrame(rows)


# ── Constants ─────────────────────────────────────────────────────────────────

LOCATIONS      = ["London", "Birmingham", "Manchester"]
PROJECT_TYPES  = ["Office", "Residential", "Retail", "Mixed Use", "Industrial", "Education", "Healthcare", "Hospitality", "Other"]
CONTRACT_TYPES = ["Shell & Core", "Cat A Fit-Out", "Shell & Core + Cat A Fit-Out", "Refurbishment", "New Build"]
SPEC_LEVELS    = ["Budget", "Standard", "High Spec", "Bespoke"]
RATE_UNITS_M2  = ["£/m2", "%"]
RATE_UNITS_FT2 = ["£/ft2", "%"]
PACKAGES       = ["Shell & Core", "Cat A Fit-Out"]

# Categories where % is the expected rate unit
PCT_CATEGORIES = {"On Costs"}


# ── Session state helpers ─────────────────────────────────────────────────────

def _init_session():
    st.session_state.setdefault("ars_step",          1)       # 1=details, 2=rates, 3=review
    st.session_state.setdefault("ars_project_saved", False)
    st.session_state.setdefault("ars_submission_id", None)
    st.session_state.setdefault("ars_rates",         {})      # {element_id: {rate, unit, qty, total, package, notes}}
    st.session_state.setdefault("ars_unit",          "m²")
    # Project detail fields
    st.session_state.setdefault("ars_project_name",  "")
    st.session_state.setdefault("ars_location",      "London")
    st.session_state.setdefault("ars_project_type",  "Office")
    st.session_state.setdefault("ars_package",       "Shell & Core")
    st.session_state.setdefault("ars_gia_m2",        0.0)
    st.session_state.setdefault("ars_nia_m2",        0.0)
    st.session_state.setdefault("ars_storeys_above", 0)
    st.session_state.setdefault("ars_storeys_below", 0)
    st.session_state.setdefault("ars_spec_level",    "Standard")
    st.session_state.setdefault("ars_cost_date",     date.today())
    st.session_state.setdefault("ars_notes",         "")
    st.session_state.setdefault("ars_submitted_by",  "")


def _reset_form():
    keys = [k for k in st.session_state.keys() if k.startswith("ars_")]
    for k in keys:
        del st.session_state[k]
    st.cache_data.clear()


# ── Step indicator ────────────────────────────────────────────────────────────

def _render_steps(current: int):
    steps = ["1  Project Details", "2  Rate Entry", "3  Review & Submit"]
    cols  = st.columns(3)
    for i, (col, label) in enumerate(zip(cols, steps), 1):
        with col:
            if i < current:
                colour = "#c8a84b"
                prefix = "✓ "
                weight = "500"
            elif i == current:
                colour = "#0f1f3d"
                prefix = ""
                weight = "700"
            else:
                colour = "#b8c0cc"
                prefix = ""
                weight = "400"

            st.markdown(
                f"""<div style="text-align:center;padding:0.6rem 0.5rem;
                    border-bottom: 3px solid {colour};
                    font-size:0.78rem;font-weight:{weight};
                    letter-spacing:0.06em;text-transform:uppercase;
                    color:{colour};">
                    {prefix}{label}
                </div>""",
                unsafe_allow_html=True,
            )
    st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)


# ── Step 1: Project Details ───────────────────────────────────────────────────

def _render_project_details():
    st.markdown("#### Project Details")
    st.markdown(
        "<p style='color:#8a96a8;font-size:0.9rem;margin-top:-0.5rem;'>"
        "Enter the key details for the cost plan you are logging rates from.</p>",
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)

    with c1:
        st.session_state.ars_project_name = st.text_input(
            "Project Name *",
            value=st.session_state.ars_project_name,
            placeholder="e.g. York Way — Stage 3",
            key="ars_name_input",
        )
        st.session_state.ars_location = st.selectbox(
            "Location *",
            LOCATIONS,
            index=LOCATIONS.index(st.session_state.ars_location),
            key="ars_location_input",
        )
        st.session_state.ars_project_type = st.selectbox(
            "Project Type",
            PROJECT_TYPES,
            index=PROJECT_TYPES.index(st.session_state.ars_project_type),
            key="ars_ptype_input",
        )
        st.session_state.ars_package = st.selectbox(
            "Package *",
            CONTRACT_TYPES,
            index=CONTRACT_TYPES.index(st.session_state.ars_package),
            key="ars_package_input",
        )
        st.session_state.ars_spec_level = st.selectbox(
            "Spec Level",
            SPEC_LEVELS,
            index=SPEC_LEVELS.index(st.session_state.ars_spec_level),
            key="ars_spec_input",
        )

    with c2:
        st.session_state.ars_cost_date = st.date_input(
            "Cost Plan Date *",
            value=st.session_state.ars_cost_date,
            key="ars_date_input",
        )

        # GIA
        gia_val = st.number_input(
            "GIA (m²)",
            min_value=0.0,
            step=100.0,
            format="%.0f",
            value=float(st.session_state.ars_gia_m2),
            key="ars_gia_input",
        )
        st.session_state.ars_gia_m2 = gia_val
        if gia_val > 0:
            st.caption(f"≈ {gia_val * 10.764:,.0f} ft²")

        # NIA
        nia_val = st.number_input(
            "NIA (m²)",
            min_value=0.0,
            step=100.0,
            format="%.0f",
            value=float(st.session_state.ars_nia_m2),
            key="ars_nia_input",
        )
        st.session_state.ars_nia_m2 = nia_val
        if nia_val > 0:
            st.caption(f"≈ {nia_val * 10.764:,.0f} ft²")

        col_ab, col_bg = st.columns(2)
        with col_ab:
            st.session_state.ars_storeys_above = st.number_input(
                "Storeys above ground",
                min_value=0, max_value=100, step=1,
                value=st.session_state.ars_storeys_above,
                key="ars_above_input",
            )
        with col_bg:
            st.session_state.ars_storeys_below = st.number_input(
                "Storeys below ground",
                min_value=0, max_value=20, step=1,
                value=st.session_state.ars_storeys_below,
                key="ars_below_input",
            )

        st.session_state.ars_submitted_by = st.text_input(
            "Your name",
            value=st.session_state.ars_submitted_by,
            placeholder="e.g. J. Smith",
            key="ars_submitter_input",
        )

    st.session_state.ars_notes = st.text_area(
        "Notes (optional)",
        value=st.session_state.ars_notes,
        placeholder="Any context about this project or the rates...",
        height=80,
        key="ars_notes_input",
    )

    st.markdown("---")

    # Validation
    can_proceed = bool(
        st.session_state.ars_project_name
        and st.session_state.ars_location
        and st.session_state.ars_package
        and st.session_state.ars_cost_date
    )

    if not can_proceed:
        st.warning("⚠️ Project name, location, package and cost date are required to continue.")

    col_next, _ = st.columns([1, 4])
    with col_next:
        if st.button(
            "Next: Enter Rates →",
            type="primary",
            disabled=not can_proceed,
            use_container_width=True,
        ):
            st.session_state.ars_step = 2
            st.rerun()


# ── Step 2: Rate Entry ────────────────────────────────────────────────────────

def _render_rate_entry(elements_df: pd.DataFrame):

    # Unit toggle
    col_toggle, col_progress, _ = st.columns([1, 2, 3])
    with col_toggle:
        unit = st.radio(
            "Rate unit",
            ["m²", "ft²"],
            horizontal=True,
            key="ars_unit_toggle",
            label_visibility="collapsed",
        )
        st.session_state.ars_unit = unit

    # Progress indicator
    logged = len([v for v in st.session_state.ars_rates.values() if v.get("rate", 0) > 0])
    total  = len(elements_df)
    with col_progress:
        st.markdown(
            f"<div style='padding-top:0.4rem;font-size:0.82rem;color:#8a96a8;'>"
            f"<b style='color:#0f1f3d;'>{logged}</b> of {total} elements logged</div>",
            unsafe_allow_html=True,
        )
        st.progress(logged / total if total > 0 else 0)

    st.markdown(
        "<p style='color:#8a96a8;font-size:0.88rem;margin-bottom:1rem;'>"
        "Select the elements you have up-to-date rates for. "
        "Leave others blank — only filled rates will be submitted.</p>",
        unsafe_allow_html=True,
    )

    # Determine rate units based on toggle
    rate_units = RATE_UNITS_FT2 if unit == "ft²" else RATE_UNITS_M2

    # Group by category
    for category, cat_df in elements_df.groupby(
        elements_df["category"],
        sort=False
    ):
        # Count how many in this category have been logged
        cat_logged = sum(
            1 for _, row in cat_df.iterrows()
            if st.session_state.ars_rates.get(row["element_id"], {}).get("rate", 0) > 0
        )
        cat_total = len(cat_df)

        st.markdown(
            f"""<div style="display:flex;justify-content:space-between;
                align-items:baseline;margin:1.4rem 0 0.5rem;">
                <span style="font-family:'DM Serif Display',serif;
                font-size:1.1rem;color:#0f1f3d;">{category}</span>
                <span style="font-size:0.75rem;color:#8a96a8;">
                {cat_logged}/{cat_total} logged</span>
            </div>""",
            unsafe_allow_html=True,
        )

        for _, row in cat_df.iterrows():
            element_id   = row["element_id"]
            element_name = row["element_name"]
            is_pct       = (category in PCT_CATEGORIES)

            # Get existing values
            existing = st.session_state.ars_rates.get(element_id, {})
            existing_rate  = existing.get("rate", 0.0)
            existing_qty   = existing.get("quantity", 0.0)
            existing_notes = existing.get("notes", "")
            existing_pkg   = existing.get("package", PACKAGES[0])

            is_logged  = existing_rate > 0
            badge      = "✓ " if is_logged else ""
            rate_hint  = f" — {existing_rate:,.2f}" if is_logged else ""

            with st.expander(f"{badge}{element_id}  {element_name}{rate_hint}"):

                if is_pct:
                    # On costs — percentage input only
                    c1, c2, c3 = st.columns([2, 2, 2])
                    with c1:
                        pct_val = st.number_input(
                            "Rate (%)",
                            min_value=0.0,
                            max_value=100.0,
                            step=0.1,
                            format="%.2f",
                            value=float(existing_rate),
                            key=f"ars_rate_{element_id}",
                        )
                    with c2:
                        pkg_val = st.selectbox(
                            "Package",
                            PACKAGES + ["Both"],
                            index=(PACKAGES + ["Both"]).index(existing_pkg) if existing_pkg in PACKAGES + ["Both"] else 0,
                            key=f"ars_pkg_{element_id}",
                        )
                    with c3:
                        notes_val = st.text_input(
                            "Notes",
                            value=existing_notes,
                            placeholder="Optional...",
                            key=f"ars_notes_{element_id}",
                            label_visibility="collapsed",
                        )

                    if pct_val > 0:
                        st.session_state.ars_rates[element_id] = {
                            "rate":     pct_val,
                            "rate_unit": "%",
                            "quantity": None,
                            "total_cost": None,
                            "package":  pkg_val,
                            "notes":    notes_val or None,
                        }
                    elif element_id in st.session_state.ars_rates:
                        del st.session_state.ars_rates[element_id]

                else:
                    # Standard rate entry
                    c1, c2, c3, c4, c5 = st.columns([2, 1.5, 1.5, 1.5, 2])

                    with c1:
                        rate_val = st.number_input(
                            f"Rate (£/{unit})",
                            min_value=0.0,
                            step=1.0,
                            format="%.2f",
                            value=float(existing_rate),
                            key=f"ars_rate_{element_id}",
                        )
                    with c2:
                        # Default unit based on toggle, but allow % override
                        default_unit = "£/ft2" if unit == "ft²" else "£/m2"
                        unit_options = rate_units
                        unit_val = st.selectbox(
                            "Unit",
                            unit_options,
                            index=unit_options.index(default_unit) if default_unit in unit_options else 0,
                            key=f"ars_unit_{element_id}",
                        )
                    with c3:
                        qty_val = st.number_input(
                            f"Qty ({unit})",
                            min_value=0.0,
                            step=10.0,
                            format="%.0f",
                            value=float(existing_qty) if existing_qty else 0.0,
                            key=f"ars_qty_{element_id}",
                        )
                    with c4:
                        pkg_val = st.selectbox(
                            "Package",
                            PACKAGES,
                            index=PACKAGES.index(existing_pkg) if existing_pkg in PACKAGES else 0,
                            key=f"ars_pkg_{element_id}",
                        )
                    with c5:
                        notes_val = st.text_input(
                            "Notes",
                            value=existing_notes,
                            placeholder="Optional...",
                            key=f"ars_notes_{element_id}",
                            label_visibility="collapsed",
                        )

                    # Calculate total
                    total_cost = None
                    if rate_val > 0 and qty_val > 0:
                        total_cost = round(rate_val * qty_val, 0)
                        st.markdown(
                            f"<div style='font-family:DM Serif Display,serif;"
                            f"font-size:0.95rem;color:#0f1f3d;padding-top:0.25rem;'>"
                            f"= £{total_cost:,.0f}</div>",
                            unsafe_allow_html=True,
                        )

                    if rate_val > 0:
                        st.session_state.ars_rates[element_id] = {
                            "rate":       rate_val,
                            "rate_unit":  unit_val,
                            "quantity":   qty_val if qty_val > 0 else None,
                            "total_cost": total_cost,
                            "package":    pkg_val,
                            "notes":      notes_val or None,
                        }
                    elif element_id in st.session_state.ars_rates:
                        del st.session_state.ars_rates[element_id]

    st.markdown("---")

    col_back, _, col_next = st.columns([1, 4, 1])
    with col_back:
        if st.button("← Project Details", use_container_width=True):
            st.session_state.ars_step = 1
            st.rerun()
    with col_next:
        logged_count = len([
            v for v in st.session_state.ars_rates.values()
            if v.get("rate", 0) > 0
        ])
        if st.button(
            "Review & Submit →",
            type="primary",
            disabled=logged_count == 0,
            use_container_width=True,
        ):
            st.session_state.ars_step = 3
            st.rerun()

    if logged_count == 0:
        st.caption("Enter at least one rate to proceed.")


# ── Step 3: Review & Submit ───────────────────────────────────────────────────

def _render_review(elements_df: pd.DataFrame):

    st.markdown("#### Review Before Submitting")
    st.markdown(
        "<p style='color:#8a96a8;font-size:0.9rem;margin-top:-0.5rem;'>"
        "Check the details below. Once submitted, rates will be held for review "
        "before being published into the estimating engine.</p>",
        unsafe_allow_html=True,
    )

    # ── Project summary card ──────────────────────────────────────────────────
    st.markdown(
        f"""
        <div style="background:#fff;border:1px solid #ddd8d0;border-radius:8px;
                    padding:1.25rem 1.5rem;margin-bottom:1.5rem;
                    font-size:0.875rem;line-height:2;color:#0f1f3d;">
            <div style="font-family:'DM Serif Display',serif;font-size:1.1rem;
                        margin-bottom:0.5rem;color:#0f1f3d;">
                {st.session_state.ars_project_name}
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0 2rem;">
                <div>📍 <b>Location:</b> {st.session_state.ars_location}</div>
                <div>📦 <b>Package:</b> {st.session_state.ars_package}</div>
                <div>🏢 <b>Type:</b> {st.session_state.ars_project_type}</div>
                <div>⭐ <b>Spec:</b> {st.session_state.ars_spec_level}</div>
                <div>📐 <b>GIA:</b> {st.session_state.ars_gia_m2:,.0f} m²</div>
                <div>📐 <b>NIA:</b> {st.session_state.ars_nia_m2:,.0f} m²</div>
                <div>🏗️ <b>Storeys:</b> {st.session_state.ars_storeys_above} above · {st.session_state.ars_storeys_below} below</div>
                <div>📅 <b>Cost date:</b> {st.session_state.ars_cost_date}</div>
                {"<div>👤 <b>Submitted by:</b> " + st.session_state.ars_submitted_by + "</div>" if st.session_state.ars_submitted_by else ""}
            </div>
            {f'<div style="margin-top:0.5rem;color:#8a96a8;">📝 {st.session_state.ars_notes}</div>' if st.session_state.ars_notes else ""}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Rates table ───────────────────────────────────────────────────────────
    rates_data = st.session_state.ars_rates
    if not rates_data:
        st.warning("No rates logged — go back and enter at least one rate.")
        return

    # Build display dataframe
    el_lookup = {row["element_id"]: row["element_name"] for _, row in elements_df.iterrows()}
    rows = []
    for element_id, data in rates_data.items():
        if data.get("rate", 0) > 0:
            rows.append({
                "ID":         element_id,
                "Element":    el_lookup.get(element_id, element_id),
                "Package":    data.get("package", "—"),
                "Rate":       f"£{data['rate']:,.2f}" if data["rate_unit"] != "%" else f"{data['rate']:.2f}%",
                "Unit":       data.get("rate_unit", "—"),
                "Quantity":   f"{data['quantity']:,.0f}" if data.get("quantity") else "—",
                "Total (£)":  f"£{data['total_cost']:,.0f}" if data.get("total_cost") else "—",
                "Notes":      data.get("notes") or "—",
            })

    display_df = pd.DataFrame(rows)

    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.metric("Rates to submit", len(rows))
    with col_m2:
        total_logged = sum(
            d.get("total_cost", 0) or 0
            for d in rates_data.values()
            if d.get("rate_unit") != "%"
        )
        if total_logged > 0:
            st.metric("Total logged cost", f"£{total_logged:,.0f}")
    with col_m3:
        st.metric("Status after submit", "Pending review")

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # ── Submit button ─────────────────────────────────────────────────────────
    col_back, _, col_submit = st.columns([1, 3, 1])

    with col_back:
        if st.button("← Edit Rates", use_container_width=True):
            st.session_state.ars_step = 2
            st.rerun()

    with col_submit:
        if st.button(
            "✅  Submit to Supabase",
            type="primary",
            use_container_width=True,
        ):
            _submit_to_supabase(elements_df)


def _submit_to_supabase(elements_df: pd.DataFrame):
    """Write project + rates to Supabase submitted_projects and submitted_rates."""
    try:
        with st.spinner("Submitting to Supabase..."):

            # 1. Insert project header
            project_payload = {
                "project_name":   st.session_state.ars_project_name,
                "location":       st.session_state.ars_location,
                "project_type":   st.session_state.ars_project_type,
                "package":        st.session_state.ars_package,
                "gia_m2":         st.session_state.ars_gia_m2 or None,
                "nia_m2":         st.session_state.ars_nia_m2 or None,
                "storeys_above":  st.session_state.ars_storeys_above or None,
                "storeys_below":  st.session_state.ars_storeys_below or None,
                "spec_level":     st.session_state.ars_spec_level,
                "cost_date":      str(st.session_state.ars_cost_date),
                "notes":          st.session_state.ars_notes or None,
                "submitted_by":   st.session_state.ars_submitted_by or None,
                "status":         "pending",
            }
            project_row = _post("submitted_projects", project_payload)
            submission_id = project_row["id"]

            # 2. Insert individual rates
            rates_data = st.session_state.ars_rates
            for element_id, data in rates_data.items():
                if data.get("rate", 0) > 0:
                    rate_payload = {
                        "submission_id": submission_id,
                        "element_id":    element_id,
                        "package":       data.get("package", "Shell & Core"),
                        "rate":          data["rate"],
                        "rate_unit":     data.get("rate_unit", "£/m2"),
                        "quantity":      data.get("quantity"),
                        "total_cost":    data.get("total_cost"),
                        "notes":         data.get("notes"),
                    }
                    _post("submitted_rates", rate_payload)

        # ── Success ───────────────────────────────────────────────────────────
        st.session_state.ars_submission_id  = submission_id
        st.session_state.ars_project_saved  = True
        st.rerun()

    except Exception as e:
        st.error(f"❌ Submission failed: {e}")
        st.caption("Check your Supabase credentials and table permissions, then try again.")


# ── Success screen ────────────────────────────────────────────────────────────

def _render_success():
    st.markdown(
        """
        <div style="text-align:center;padding:3rem 2rem;">
            <div style="font-size:3rem;margin-bottom:1rem;">✅</div>
            <div style="font-family:'DM Serif Display',serif;font-size:1.6rem;
                        color:#0f1f3d;margin-bottom:0.5rem;">
                Rates Submitted Successfully
            </div>
            <div style="color:#8a96a8;font-size:0.9rem;max-width:480px;
                        margin:0 auto 2rem;">
                Your rates are now sitting in Supabase with status <b>pending</b>.
                A CPC admin will review and publish them into the estimating engine.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.ars_submission_id:
        st.markdown(
            f"<div style='text-align:center;font-size:0.78rem;color:#b8c0cc;"
            f"margin-bottom:2rem;'>Submission ID: "
            f"<code>{st.session_state.ars_submission_id}</code></div>",
            unsafe_allow_html=True,
        )

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button(
            "＋  Submit Another Project",
            type="primary",
            use_container_width=True,
        ):
            _reset_form()
            st.rerun()


# ── Main render ───────────────────────────────────────────────────────────────

def render():
    _init_session()

    # ── Page header ───────────────────────────────────────────────────────────
    st.markdown("""
    <div style="margin-bottom:0.25rem;">
        <span style="font-family:'DM Serif Display',serif;font-size:2rem;color:#0f1f3d;">
            Rate Submission
        </span>
        <span style="display:inline-block;margin-left:0.75rem;
                     background:#0f1f3d;color:#c8a84b;
                     font-size:0.65rem;font-weight:700;letter-spacing:0.1em;
                     text-transform:uppercase;padding:0.2rem 0.6rem;
                     border-radius:4px;vertical-align:middle;">
            Admin
        </span>
    </div>
    <p style="color:#8a96a8;margin-top:0;font-size:0.95rem;">
        Log rates from a completed cost plan. Submitted rates are held for review
        before being published into the estimating engine.
    </p>
    """, unsafe_allow_html=True)

    # ── Success state ─────────────────────────────────────────────────────────
    if st.session_state.ars_project_saved:
        _render_success()
        return

    # ── Load elements ─────────────────────────────────────────────────────────
    try:
        elements_df = load_elements()
    except Exception as e:
        st.error(f"Could not load elements from Supabase: {e}")
        return

    if elements_df.empty:
        st.error("No elements found in Supabase. Check the elements table.")
        return

    # ── Step indicator ────────────────────────────────────────────────────────
    _render_steps(st.session_state.ars_step)

    # ── Route to correct step ─────────────────────────────────────────────────
    if st.session_state.ars_step == 1:
        _render_project_details()
    elif st.session_state.ars_step == 2:
        _render_rate_entry(elements_df)
    elif st.session_state.ars_step == 3:
        _render_review(elements_df)

    st.markdown("---")
    st.caption("⚠️ Submitted rates are pending review and will not affect live estimates until published by an admin.")