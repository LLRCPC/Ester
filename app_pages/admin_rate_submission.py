"""
admin_rate_submission.py
------------------------
Page: Admin — Rate Submission

Admins input total cost (£) per element. The backend calculates
the rate (£/m²) by dividing total cost by the relevant area:
  - NIA  → Fit-Out category elements
  - GIA  → everything else
  - %    → On Costs (no area calculation)

GIA and NIA are entered once in Step 1 and reused throughout.
Area can be toggled between m² and ft² at input — backend always
stores and calculates in m².

Flow:
  Step 1 — Project Details (name, date, location, GIA, NIA, storeys, spec)
  Step 2 — Cost Entry (total cost per element → auto-calculates £/m²)
  Step 3 — Review & Submit
"""

import streamlit as st
import pandas as pd
from datetime import date
import os
import httpx

FT2_PER_M2 = 10.76391041671

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
        "is_active=eq.true&order=sort_order.asc"
        "&select=element_id,element_name,category,default_rate_unit,area_basis"
    )
    return pd.DataFrame(rows)


# ── Constants ─────────────────────────────────────────────────────────────────

LOCATIONS      = ["London", "Birmingham", "Manchester"]
PROJECT_TYPES  = ["Office", "Residential", "Retail", "Mixed Use",
                  "Industrial", "Education", "Healthcare", "Hospitality", "Other"]
CONTRACT_TYPES = ["Shell & Core", "Cat A Fit-Out",
                  "Shell & Core + Cat A Fit-Out", "Refurbishment", "New Build"]
SPEC_LEVELS    = ["Budget", "Standard", "High Spec", "Bespoke"]
PACKAGES       = ["Shell & Core", "Cat A Fit-Out"]

# Categories that use NIA as the denominator for rate calculation
NIA_CATEGORIES = {"Fit-Out"}

# Categories that use % — no area division
PCT_CATEGORIES = {"On Costs"}


# ── Area basis helper ─────────────────────────────────────────────────────────

def _area_basis(category: str) -> str:
    """Return 'NIA', 'GIA', or '%' for a given category."""
    if category in PCT_CATEGORIES:
        return "%"
    if category in NIA_CATEGORIES:
        return "NIA"
    return "GIA"


def _area_basis_label(category: str, gia_m2: float, nia_m2: float, unit: str) -> str:
    """Human-readable area basis label shown next to each element."""
    basis = _area_basis(category)
    if basis == "%":
        return "% of build cost"
    area_m2 = nia_m2 if basis == "NIA" else gia_m2
    if area_m2 <= 0:
        return f"{basis} — enter area in Step 1"
    if unit == "ft²":
        return f"{basis}: {area_m2 * FT2_PER_M2:,.0f} ft²"
    return f"{basis}: {area_m2:,.0f} m²"


# ── Session state helpers ─────────────────────────────────────────────────────

def _init_session():
    st.session_state.setdefault("ars_step",          1)
    st.session_state.setdefault("ars_project_saved", False)
    st.session_state.setdefault("ars_submission_id", None)
    # {element_id: {total_cost, rate_m2, rate_unit, pct, package, notes}}
    st.session_state.setdefault("ars_rates",         {})
    st.session_state.setdefault("ars_unit",          "m²")
    # Project fields
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
    steps  = ["1  Project Details", "2  Cost Entry", "3  Review & Submit"]
    cols   = st.columns(3)
    for i, (col, label) in enumerate(zip(cols, steps), 1):
        with col:
            if i < current:
                colour, prefix, weight = "#c8a84b", "✓ ", "500"
            elif i == current:
                colour, prefix, weight = "#0f1f3d", "", "700"
            else:
                colour, prefix, weight = "#b8c0cc", "", "400"
            st.markdown(
                f"""<div style="text-align:center;padding:0.6rem 0.5rem;
                    border-bottom:3px solid {colour};
                    font-size:0.78rem;font-weight:{weight};
                    letter-spacing:0.06em;text-transform:uppercase;
                    color:{colour};">{prefix}{label}</div>""",
                unsafe_allow_html=True,
            )
    st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)


# ── Step 1: Project Details ───────────────────────────────────────────────────

def _render_project_details():
    st.markdown("#### Project Details")
    st.markdown(
        "<p style='color:#8a96a8;font-size:0.9rem;margin-top:-0.5rem;'>"
        "Enter the key details for the cost plan you are logging rates from. "
        "GIA and NIA are used to calculate £/m² rates automatically.</p>",
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
        st.session_state.ars_submitted_by = st.text_input(
            "Your name",
            value=st.session_state.ars_submitted_by,
            placeholder="e.g. J. Smith",
            key="ars_submitter_input",
        )

    with c2:
        st.session_state.ars_cost_date = st.date_input(
            "Cost Plan Date *",
            value=st.session_state.ars_cost_date,
            key="ars_date_input",
        )

        # Area unit toggle — affects display only, storage always m²
        area_unit = st.radio(
            "Area input unit",
            ["m²", "ft²"],
            horizontal=True,
            key="ars_area_unit_step1",
        )

        # GIA input
        if area_unit == "ft²":
            gia_display = st.session_state.ars_gia_m2 * FT2_PER_M2
            gia_entered = st.number_input(
                "GIA (ft²) *",
                min_value=0.0, step=1000.0, format="%.0f",
                value=float(gia_display),
                key="ars_gia_input",
            )
            st.session_state.ars_gia_m2 = gia_entered / FT2_PER_M2
            if gia_entered > 0:
                st.caption(f"≈ {st.session_state.ars_gia_m2:,.0f} m²")
        else:
            gia_entered = st.number_input(
                "GIA (m²) *",
                min_value=0.0, step=100.0, format="%.0f",
                value=float(st.session_state.ars_gia_m2),
                key="ars_gia_input",
            )
            st.session_state.ars_gia_m2 = gia_entered
            if gia_entered > 0:
                st.caption(f"≈ {gia_entered * FT2_PER_M2:,.0f} ft²")

        # NIA input
        if area_unit == "ft²":
            nia_display = st.session_state.ars_nia_m2 * FT2_PER_M2
            nia_entered = st.number_input(
                "NIA (ft²)",
                min_value=0.0, step=1000.0, format="%.0f",
                value=float(nia_display),
                key="ars_nia_input",
            )
            st.session_state.ars_nia_m2 = nia_entered / FT2_PER_M2
            if nia_entered > 0:
                st.caption(f"≈ {st.session_state.ars_nia_m2:,.0f} m²")
        else:
            nia_entered = st.number_input(
                "NIA (m²)",
                min_value=0.0, step=100.0, format="%.0f",
                value=float(st.session_state.ars_nia_m2),
                key="ars_nia_input",
            )
            st.session_state.ars_nia_m2 = nia_entered
            if nia_entered > 0:
                st.caption(f"≈ {nia_entered * FT2_PER_M2:,.0f} ft²")

        # Net:Gross ratio
        gia_m2 = st.session_state.ars_gia_m2
        nia_m2 = st.session_state.ars_nia_m2
        if gia_m2 > 0 and nia_m2 > 0:
            if nia_m2 > gia_m2:
                st.warning("⚠️ NIA cannot exceed GIA.")
            else:
                ratio = (nia_m2 / gia_m2) * 100
                st.metric("Net:Gross ratio", f"{ratio:.1f}%")

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

    st.session_state.ars_notes = st.text_area(
        "Notes (optional)",
        value=st.session_state.ars_notes,
        placeholder="Any context about this project or the rates...",
        height=80,
        key="ars_notes_input",
    )

    # Area basis info box
    gia_m2 = st.session_state.ars_gia_m2
    nia_m2 = st.session_state.ars_nia_m2
    if gia_m2 > 0:
        st.info(
            f"📐 **Rate calculation basis:** "
            f"Most elements will use GIA ({gia_m2:,.0f} m²). "
            f"Fit-Out elements will use NIA "
            f"({nia_m2:,.0f} m²{' — ⚠️ enter NIA above' if nia_m2 == 0 else ''}). "
            f"On Costs are entered as a percentage."
        )

    st.markdown("---")

    can_proceed = bool(
        st.session_state.ars_project_name
        and st.session_state.ars_location
        and st.session_state.ars_package
        and st.session_state.ars_cost_date
        and st.session_state.ars_gia_m2 > 0
    )

    if not can_proceed:
        st.warning("⚠️ Project name, location, package, cost date and GIA are required to continue.")

    col_next, _ = st.columns([1, 4])
    with col_next:
        if st.button(
            "Next: Enter Costs →",
            type="primary",
            disabled=not can_proceed,
            use_container_width=True,
        ):
            st.session_state.ars_step = 2
            st.rerun()


# ── Step 2: Cost Entry ────────────────────────────────────────────────────────

def _render_cost_entry(elements_df: pd.DataFrame):

    gia_m2 = st.session_state.ars_gia_m2
    nia_m2 = st.session_state.ars_nia_m2

    # ── Controls row ─────────────────────────────────────────────────────────
    col_toggle, col_progress, _ = st.columns([1, 2, 3])
    with col_toggle:
        unit = st.radio(
            "Area display unit",
            ["m²", "ft²"],
            horizontal=True,
            key="ars_unit_toggle",
            label_visibility="collapsed",
        )
        st.session_state.ars_unit = unit

    logged = len([v for v in st.session_state.ars_rates.values()
                  if (v.get("total_cost") or 0) > 0
                  or (v.get("pct") or 0) > 0
                  or v.get("na")])
    total  = len(elements_df)

    with col_progress:
        st.markdown(
            f"<div style='padding-top:0.4rem;font-size:0.82rem;color:#8a96a8;'>"
            f"<b style='color:#0f1f3d;'>{logged}</b> of {total} elements entered</div>",
            unsafe_allow_html=True,
        )
        st.progress(logged / total if total > 0 else 0)

    st.markdown(
        "<p style='color:#8a96a8;font-size:0.88rem;margin-bottom:0.5rem;'>"
        "Enter the <b>total cost (£)</b> for each element from your cost plan. "
        "The £/m² rate is calculated automatically using "
        "GIA or NIA as appropriate. Leave blank to skip, or tick "
        "<b>N/A</b> if the element doesn't exist on this project — "
        "N/A is recorded so we learn how often each element occurs.</p>",
        unsafe_allow_html=True,
    )

    # Area summary bar
    gia_display = gia_m2 * FT2_PER_M2 if unit == "ft²" else gia_m2
    nia_display = nia_m2 * FT2_PER_M2 if unit == "ft²" else nia_m2
    unit_label  = unit
    st.markdown(
        f"""<div style="background:#f5f4f0;border:1px solid #e4e0d8;
            border-radius:6px;padding:0.6rem 1rem;margin-bottom:1rem;
            font-size:0.82rem;color:#0f1f3d;display:flex;gap:2rem;">
            <span>📐 <b>GIA:</b> {gia_display:,.0f} {unit_label}
            (used for most elements)</span>
            <span>📐 <b>NIA:</b> {nia_display:,.0f} {unit_label}
            (used for Fit-Out)</span>
            <span>📊 <b>On Costs:</b> % entry</span>
        </div>""",
        unsafe_allow_html=True,
    )

    # ── Group by category ─────────────────────────────────────────────────────
    for category, cat_df in elements_df.groupby("category", sort=False):

        basis = _area_basis(category)
        is_pct = (basis == "%")

        # Area to use for this category
        area_m2 = nia_m2 if basis == "NIA" else gia_m2

        cat_logged = sum(
            1 for _, row in cat_df.iterrows()
            if (st.session_state.ars_rates.get(row["element_id"], {}).get("total_cost") or 0) > 0
            or (st.session_state.ars_rates.get(row["element_id"], {}).get("pct") or 0) > 0
            or st.session_state.ars_rates.get(row["element_id"], {}).get("na")
        )
        cat_total = len(cat_df)

        # Category header with basis badge
        basis_colour = {"GIA": "#e8f0fe", "NIA": "#e8f5e9", "%": "#fff8e6"}
        basis_text   = {"GIA": "#1a4a9e", "NIA": "#2e7d32", "%": "#c8a84b"}
        bc = basis_colour.get(basis, "#f0f0f0")
        bt = basis_text.get(basis, "#555")

        st.markdown(
            f"""<div style="display:flex;justify-content:space-between;
                align-items:center;margin:1.4rem 0 0.5rem;">
                <span style="font-family:'DM Serif Display',serif;
                font-size:1.1rem;color:#0f1f3d;">{category}</span>
                <div style="display:flex;gap:0.5rem;align-items:center;">
                    <span style="background:{bc};color:{bt};font-size:0.68rem;
                    font-weight:700;letter-spacing:0.06em;text-transform:uppercase;
                    padding:0.15rem 0.5rem;border-radius:4px;">÷ {basis}</span>
                    <span style="font-size:0.75rem;color:#8a96a8;">
                    {cat_logged}/{cat_total} entered</span>
                </div>
            </div>""",
            unsafe_allow_html=True,
        )

        for _, row in cat_df.iterrows():
            element_id   = row["element_id"]
            element_name = row["element_name"]
            existing     = st.session_state.ars_rates.get(element_id, {})

            if is_pct:
                # ── On Costs — percentage entry ───────────────────────────────
                existing_pct = existing.get("pct", 0.0) or 0.0
                is_na        = existing.get("na", False)
                is_entered   = existing_pct > 0 or is_na
                badge        = "✓ " if existing_pct > 0 else ("－ " if is_na else "")
                hint         = (" — N/A" if is_na
                                else f" — {existing_pct:.2f}%" if existing_pct > 0
                                else "")

                with st.expander(f"{badge}{element_id}  {element_name}{hint}"):
                    na_val = st.checkbox(
                        "N/A — this element is not applicable to this project",
                        value=is_na,
                        key=f"ars_na_{element_id}",
                        help="Marks the element as not applicable. No rate is "
                             "published, and the N/A is recorded so we can track "
                             "how often each element actually occurs.",
                    )

                    if na_val:
                        notes_val = st.text_input(
                            "Notes (optional — e.g. why it doesn't apply)",
                            value=existing.get("notes", ""),
                            placeholder="Optional...",
                            key=f"ars_notes_{element_id}",
                        )
                        st.session_state.ars_rates[element_id] = {
                            "na":         True,
                            "pct":        None,
                            "rate_m2":    None,
                            "rate_unit":  "N/A",
                            "total_cost": None,
                            "package":    existing.get("package", PACKAGES[0]),
                            "notes":      notes_val or None,
                        }
                    else:
                        c1, c2, c3 = st.columns([2, 2, 3])
                        with c1:
                            pct_val = st.number_input(
                                "Percentage (%)",
                                min_value=0.0, max_value=100.0,
                                step=0.1, format="%.2f",
                                value=float(existing_pct),
                                key=f"ars_pct_{element_id}",
                            )
                        with c2:
                            pkg_val = st.selectbox(
                                "Package",
                                PACKAGES + ["Both"],
                                index=(PACKAGES + ["Both"]).index(
                                    existing.get("package", PACKAGES[0])
                                ) if existing.get("package") in PACKAGES + ["Both"] else 0,
                                key=f"ars_pkg_{element_id}",
                            )
                        with c3:
                            notes_val = st.text_input(
                                "Notes",
                                value=existing.get("notes", ""),
                                placeholder="Optional...",
                                key=f"ars_notes_{element_id}",
                                label_visibility="collapsed",
                            )

                        if pct_val > 0:
                            st.session_state.ars_rates[element_id] = {
                                "na":         False,
                                "pct":        pct_val,
                                "rate_m2":    None,
                                "rate_unit":  "%",
                                "total_cost": None,
                                "package":    pkg_val,
                                "notes":      notes_val or None,
                            }
                        elif element_id in st.session_state.ars_rates:
                            del st.session_state.ars_rates[element_id]

            else:
                # ── Standard elements — total cost entry ──────────────────────
                existing_cost = existing.get("total_cost", 0.0) or 0.0
                is_na         = existing.get("na", False)
                is_entered    = existing_cost > 0 or is_na
                badge         = "✓ " if existing_cost > 0 else ("－ " if is_na else "")

                # Show calculated rate in expander header if entered
                rate_hint = ""
                if is_na:
                    rate_hint = " — N/A"
                elif existing_cost > 0 and area_m2 > 0:
                    rate_m2   = existing_cost / area_m2
                    rate_hint = f" — £{rate_m2:,.2f}/m²"
                elif existing_cost > 0:
                    rate_hint = f" — £{existing_cost:,.0f} total"

                basis_label = _area_basis_label(
                    category, gia_m2, nia_m2, unit
                )

                with st.expander(
                    f"{badge}{element_id}  {element_name}{rate_hint}"
                ):
                    # Show which area is being used
                    st.markdown(
                        f"<div style='font-size:0.75rem;color:#8a96a8;"
                        f"margin-bottom:0.5rem;'>Rate basis: {basis_label}</div>",
                        unsafe_allow_html=True,
                    )

                    na_val = st.checkbox(
                        "N/A — this element is not applicable to this project",
                        value=is_na,
                        key=f"ars_na_{element_id}",
                        help="Marks the element as not applicable (e.g. no basement, "
                             "no lifts). No rate is published, and the N/A is recorded "
                             "so we can track how often each element actually occurs.",
                    )

                    if na_val:
                        notes_val = st.text_input(
                            "Notes (optional — e.g. why it doesn't apply)",
                            value=existing.get("notes", ""),
                            placeholder="Optional...",
                            key=f"ars_notes_{element_id}",
                        )
                        st.session_state.ars_rates[element_id] = {
                            "na":         True,
                            "total_cost": None,
                            "rate_m2":    None,
                            "rate_unit":  "N/A",
                            "pct":        None,
                            "package":    existing.get("package", PACKAGES[0]),
                            "notes":      notes_val or None,
                        }
                    else:
                        c1, c2, c3 = st.columns([2, 2, 3])

                        with c1:
                            cost_val = st.number_input(
                                "Total cost (£)",
                                min_value=0.0,
                                step=1000.0,
                                format="%.0f",
                                value=float(existing_cost),
                                key=f"ars_cost_{element_id}",
                            )

                        with c2:
                            pkg_val = st.selectbox(
                                "Package",
                                PACKAGES,
                                index=PACKAGES.index(
                                    existing.get("package", PACKAGES[0])
                                ) if existing.get("package") in PACKAGES else 0,
                                key=f"ars_pkg_{element_id}",
                            )

                        with c3:
                            notes_val = st.text_input(
                                "Notes",
                                value=existing.get("notes", ""),
                                placeholder="Optional...",
                                key=f"ars_notes_{element_id}",
                                label_visibility="collapsed",
                            )

                        # Calculate and display rate
                        if cost_val > 0:
                            if area_m2 > 0:
                                rate_m2 = cost_val / area_m2
                                col_calc, _ = st.columns([2, 2])
                                with col_calc:
                                    st.markdown(
                                        f"""<div style="background:#f5f4f0;
                                            border:1px solid #e4e0d8;border-radius:6px;
                                            padding:0.6rem 0.9rem;margin-top:0.25rem;">
                                            <div style="font-size:0.7rem;color:#8a96a8;
                                            text-transform:uppercase;letter-spacing:0.06em;">
                                            Calculated rate</div>
                                            <div style="font-family:'DM Serif Display',serif;
                                            font-size:1.2rem;color:#0f1f3d;">
                                            £{rate_m2:,.2f} / m²</div>
                                            <div style="font-size:0.72rem;color:#8a96a8;">
                                            £{cost_val:,.0f} ÷ {area_m2:,.0f} m² {basis}</div>
                                        </div>""",
                                        unsafe_allow_html=True,
                                    )
                            else:
                                rate_m2 = None
                                st.warning(
                                    f"⚠️ {basis} is 0 — rate cannot be calculated. "
                                    f"Go back to Step 1 and enter the {basis}."
                                )

                            st.session_state.ars_rates[element_id] = {
                                "na":         False,
                                "total_cost": cost_val,
                                "rate_m2":    rate_m2,
                                "rate_unit":  "£/m2",
                                "pct":        None,
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
        entered_count = len([
            v for v in st.session_state.ars_rates.values()
            if (v.get("total_cost") or 0) > 0
            or (v.get("pct") or 0) > 0
            or v.get("na")
        ])
        if st.button(
            "Review & Submit →",
            type="primary",
            disabled=entered_count == 0,
            use_container_width=True,
        ):
            st.session_state.ars_step = 3
            st.rerun()

    if entered_count == 0:
        st.caption("Enter at least one cost to proceed.")


# ── Step 3: Review & Submit ───────────────────────────────────────────────────

def _render_review(elements_df: pd.DataFrame):

    gia_m2 = st.session_state.ars_gia_m2
    nia_m2 = st.session_state.ars_nia_m2

    st.markdown("#### Review Before Submitting")
    st.markdown(
        "<p style='color:#8a96a8;font-size:0.9rem;margin-top:-0.5rem;'>"
        "Check everything below. Once submitted, rates will be held for "
        "review before being published into the estimating engine.</p>",
        unsafe_allow_html=True,
    )

    # ── Project summary card ──────────────────────────────────────────────────
    st.markdown(
        f"""
        <div style="background:#fff;border:1px solid #ddd8d0;border-radius:8px;
                    padding:1.25rem 1.5rem;margin-bottom:1.5rem;
                    font-size:0.875rem;line-height:2;color:#0f1f3d;">
            <div style="font-family:'DM Serif Display',serif;font-size:1.1rem;
                        margin-bottom:0.5rem;">
                {st.session_state.ars_project_name}
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0 2rem;">
                <div>📍 <b>Location:</b> {st.session_state.ars_location}</div>
                <div>📦 <b>Package:</b> {st.session_state.ars_package}</div>
                <div>🏢 <b>Type:</b> {st.session_state.ars_project_type}</div>
                <div>⭐ <b>Spec:</b> {st.session_state.ars_spec_level}</div>
                <div>📐 <b>GIA:</b> {gia_m2:,.0f} m²
                     ({gia_m2 * FT2_PER_M2:,.0f} ft²)</div>
                <div>📐 <b>NIA:</b> {nia_m2:,.0f} m²
                     ({nia_m2 * FT2_PER_M2:,.0f} ft²)</div>
                <div>🏗️ <b>Storeys:</b>
                     {st.session_state.ars_storeys_above} above ·
                     {st.session_state.ars_storeys_below} below</div>
                <div>📅 <b>Cost date:</b> {st.session_state.ars_cost_date}</div>
                {"<div>👤 <b>Submitted by:</b> " + st.session_state.ars_submitted_by + "</div>"
                 if st.session_state.ars_submitted_by else ""}
            </div>
            {f'<div style="margin-top:0.5rem;color:#8a96a8;">📝 {st.session_state.ars_notes}</div>'
             if st.session_state.ars_notes else ""}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Rates review table ────────────────────────────────────────────────────
    rates_data = st.session_state.ars_rates
    if not rates_data:
        st.warning("No costs entered — go back and enter at least one.")
        return

    el_lookup  = {r["element_id"]: r for _, r in elements_df.iterrows()}
    rows       = []
    total_cost = 0.0

    for element_id, data in rates_data.items():
        el       = el_lookup.get(element_id, {})
        category = el.get("category", "—") if isinstance(el, dict) else "—"
        name     = el.get("element_name", element_id) if isinstance(el, dict) else element_id
        basis    = _area_basis(category)

        if data.get("na"):
            rows.append({
                "ID":            element_id,
                "Element":       name,
                "Package":       data.get("package", "—"),
                "Total Cost":    "—",
                "Basis":         "—",
                "Rate (£/m²)":   "N/A",
                "Entry":         "Not applicable",
                "Notes":         data.get("notes") or "—",
            })
        elif data.get("rate_unit") == "%":
            rows.append({
                "ID":            element_id,
                "Element":       name,
                "Package":       data.get("package", "—"),
                "Total Cost":    "—",
                "Basis":         "%",
                "Rate (£/m²)":   "—",
                "Entry":         f"{data['pct']:.2f}%",
                "Notes":         data.get("notes") or "—",
            })
        else:
            cost    = data.get("total_cost", 0) or 0
            rate_m2 = data.get("rate_m2")
            total_cost += cost
            rows.append({
                "ID":            element_id,
                "Element":       name,
                "Package":       data.get("package", "—"),
                "Total Cost":    f"£{cost:,.0f}",
                "Basis":         basis,
                "Rate (£/m²)":   f"£{rate_m2:,.2f}" if rate_m2 else "⚠️ No area",
                "Entry":         f"£{cost:,.0f} ÷ {basis}",
                "Notes":         data.get("notes") or "—",
            })

    # Headline metrics
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Elements entered", len(rows))
    with c2:
        st.metric("Total cost logged", f"£{total_cost:,.0f}")
    with c3:
        if gia_m2 > 0 and total_cost > 0:
            st.metric("Overall £/m² GIA", f"£{total_cost / gia_m2:,.0f}")
    with c4:
        st.metric("Status after submit", "Pending review")

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Warn if any rates couldn't be calculated
    missing = [r for r in rows if r["Rate (£/m²)"] == "⚠️ No area"]
    if missing:
        st.warning(
            f"⚠️ {len(missing)} element(s) have no calculable rate because "
            f"the relevant area is 0. Go back to Step 1 to fix this."
        )

    st.markdown("---")

    col_back, _, col_submit = st.columns([1, 3, 1])
    with col_back:
        if st.button("← Edit Costs", use_container_width=True):
            st.session_state.ars_step = 2
            st.rerun()
    with col_submit:
        if st.button(
            "✅  Submit to Supabase",
            type="primary",
            use_container_width=True,
        ):
            _submit_to_supabase(elements_df)


# ── Submit to Supabase ────────────────────────────────────────────────────────

def _submit_to_supabase(elements_df: pd.DataFrame):
    try:
        with st.spinner("Submitting to Supabase..."):

            # 1. Insert project header
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

            # 2. Insert individual rates
            for element_id, data in st.session_state.ars_rates.items():
                has_cost = data.get("total_cost", 0) or 0
                has_pct  = data.get("pct", 0) or 0
                is_na    = bool(data.get("na"))
                if not has_cost and not has_pct and not is_na:
                    continue

                if is_na:
                    # N/A: recorded for applicability tracking; rate 0 with
                    # unit "N/A" — never published, skipped explicitly.
                    rate_value = 0
                    rate_unit  = "N/A"
                elif data.get("rate_unit") == "%":
                    rate_value = data["pct"]
                    rate_unit  = "%"
                else:
                    rate_value = data.get("rate_m2") or 0
                    rate_unit  = data.get("rate_unit", "£/m2")

                _post("submitted_rates", {
                    "submission_id": submission_id,
                    "element_id":    element_id,
                    "package":       data.get("package", "Shell & Core"),
                    "rate":          rate_value,
                    "rate_unit":     rate_unit,
                    "quantity":      None,
                    "total_cost":    data.get("total_cost"),
                    "notes":         data.get("notes"),
                })

        st.session_state.ars_submission_id = submission_id
        st.session_state.ars_project_saved = True
        st.rerun()

    except Exception as e:
        st.error(f"❌ Submission failed: {e}")
        st.caption("Check your Supabase credentials and try again.")


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
                Your rates are now in Supabase with status <b>pending</b>.
                Go to the <b>Publish Rates</b> page to review and push them
                live into the estimating engine.
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
    with col1:
        if st.button("＋  Submit Another", type="primary", use_container_width=True):
            _reset_form()
            st.rerun()
    with col3:
        if st.button("📤  Publish Rates →", use_container_width=True):
            st.session_state.page_idx = 8
            st.rerun()


# ── Main render ───────────────────────────────────────────────────────────────

def render():
    _init_session()

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
        Log total costs from a completed cost plan. Rates are calculated
        automatically and held for review before going live.
    </p>
    """, unsafe_allow_html=True)

    if st.session_state.ars_project_saved:
        _render_success()
        return

    try:
        elements_df = load_elements()
    except Exception as e:
        st.error(f"Could not load elements from Supabase: {e}")
        return

    if elements_df.empty:
        st.error("No elements found in Supabase. Check the elements table.")
        return

    _render_steps(st.session_state.ars_step)

    if st.session_state.ars_step == 1:
        _render_project_details()
    elif st.session_state.ars_step == 2:
        _render_cost_entry(elements_df)
    elif st.session_state.ars_step == 3:
        _render_review(elements_df)

    st.markdown("---")
    st.caption(
        "⚠️ Submitted rates are pending review and will not affect "
        "live estimates until published by an admin."
    )