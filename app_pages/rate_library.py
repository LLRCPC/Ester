"""
rate_library.py
---------------
Page: Rate Library

Two tabs:
  1. Log Rates  — create a project and log line-item rates against it
  2. Benchmark  — pick any element, see min/max/median across all projects
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

def _patch(table: str, row_id: str, payload: dict) -> dict:
    url, key = _creds()
    r = httpx.patch(
        f"{url}/rest/v1/{table}?id=eq.{row_id}",
        headers=_headers(key),
        json=payload,
        timeout=15,
    )
    r.raise_for_status()
    result = r.json()
    return result[0] if isinstance(result, list) else result


# ── Cached data loaders ───────────────────────────────────────────────────────

@st.cache_data(ttl=120)
def load_elements() -> pd.DataFrame:
    rows = _get("rl_elements", "is_active=eq.true&order=section_ref.asc,subsection.asc,item_code.asc&select=*")
    return pd.DataFrame(rows)

@st.cache_data(ttl=60)
def load_projects() -> pd.DataFrame:
    rows = _get("rl_projects", "order=cost_date.desc&select=*")
    return pd.DataFrame(rows)

@st.cache_data(ttl=60)
def load_rates_for_project(project_id: str) -> pd.DataFrame:
    rows = _get(
        "rl_rates",
        f"project_id=eq.{project_id}&select=*,rl_elements(section_ref,section_name,subsection,item_code,description,typical_unit)"
    )
    return pd.DataFrame(rows)

@st.cache_data(ttl=60)
def load_benchmark(element_id: str) -> pd.DataFrame:
    rows = _get(
        "rl_rates",
        f"element_id=eq.{element_id}"
        f"&select=rate,unit,quantity,total_cost,notes,logged_at,"
        f"rl_projects(name,location,project_type,contract_type,cost_date,gia_m2)"
    )
    return pd.DataFrame(rows)


# ── Tab 1: Log Rates ──────────────────────────────────────────────────────────

def _render_log_rates():
    st.markdown("""
    <p style="color:#8a96a8;font-size:0.92rem;margin-top:0;">
        Create a project and log your line-item rates. Every project you add
        makes the benchmark data richer.
    </p>
    """, unsafe_allow_html=True)

    # ── Project selector / creator ────────────────────────────────────────────
    col_sel, col_new = st.columns([3, 1])

    projects_df = load_projects()

    with col_sel:
        if projects_df.empty:
            st.info("No projects yet — create one to get started.")
            project_options = {}
        else:
            project_options = {
                f"{r['name']}  ·  {r['location']}  ·  {r['cost_date'][:7]}": r['id']
                for _, r in projects_df.iterrows()
            }
            selected_label = st.selectbox(
                "Select project to log rates against",
                list(project_options.keys()),
                key="rl_project_select",
            )
            selected_project_id = project_options[selected_label]

    with col_new:
        st.write("")
        if st.button("＋ New Project", type="primary", use_container_width=True):
            st.session_state["rl_show_new_project"] = True

    # ── New project form ──────────────────────────────────────────────────────
    if st.session_state.get("rl_show_new_project"):
        with st.expander("New Project", expanded=True):
            c1, c2 = st.columns(2)
            with c1:
                np_name     = st.text_input("Project name", key="np_name")
                np_location = st.selectbox(
                    "Location",
                    ["London", "Birmingham", "Manchester", "Edinburgh",
                     "Bristol", "Leeds", "Other"],
                    key="np_location",
                )
                np_type = st.selectbox(
                    "Project type",
                    ["Office", "Residential", "Retail", "Mixed Use",
                     "Industrial", "Education", "Healthcare", "Other"],
                    key="np_type",
                )
            with c2:
                np_contract = st.selectbox(
                    "Contract type",
                    ["Shell & Core", "Fit Out", "Shell & Core + Fit Out",
                     "Refurbishment", "New Build", "Extension"],
                    key="np_contract",
                )
                np_gia = st.number_input("GIA (m²)", min_value=0.0, step=100.0, key="np_gia")
                np_date = st.date_input("Cost date", value=date.today(), key="np_date")
            np_notes = st.text_area("Notes (optional)", key="np_notes", height=68)

            col_save, col_cancel = st.columns([1, 3])
            with col_save:
                if st.button("Save Project", type="primary", use_container_width=True):
                    if not np_name:
                        st.error("Project name is required.")
                    else:
                        payload = {
                            "name":          np_name,
                            "location":      np_location,
                            "project_type":  np_type,
                            "contract_type": np_contract,
                            "gia_m2":        np_gia if np_gia > 0 else None,
                            "cost_date":     str(np_date),
                            "notes":         np_notes or None,
                        }
                        try:
                            _post("rl_projects", payload)
                            st.cache_data.clear()
                            st.session_state["rl_show_new_project"] = False
                            st.success(f"✅ '{np_name}' saved.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Save failed: {e}")
            with col_cancel:
                if st.button("Cancel", use_container_width=True):
                    st.session_state["rl_show_new_project"] = False
                    st.rerun()

    if project_options and "selected_project_id" in locals():
        st.markdown("---")
        _render_rate_entry(selected_project_id)


def _render_rate_entry(project_id: str):
    """Render the line-item rate entry form for a given project."""

    elements_df = load_elements()
    existing_df = load_rates_for_project(project_id)

    # Which element IDs already have rates logged?
    logged_ids = set()
    if not existing_df.empty and "element_id" in existing_df.columns:
        logged_ids = set(existing_df["element_id"].tolist())

    # Section filter
    sections = ["All sections"] + sorted(elements_df["section_name"].unique().tolist())
    col_f1, col_f2, col_f3 = st.columns([2, 2, 3])
    with col_f1:
        section_filter = st.selectbox("Filter by section", sections, key="rl_section_filter")
    with col_f2:
        show_logged = st.radio(
            "Show",
            ["All items", "Not yet logged", "Already logged"],
            horizontal=True,
            key="rl_show_logged",
            label_visibility="collapsed",
        )
    with col_f3:
        search = st.text_input("Search descriptions", placeholder="e.g. piling, curtain wall...", key="rl_search")

    # Apply filters
    df = elements_df.copy()
    if section_filter != "All sections":
        df = df[df["section_name"] == section_filter]
    if show_logged == "Not yet logged":
        df = df[~df["id"].isin(logged_ids)]
    elif show_logged == "Already logged":
        df = df[df["id"].isin(logged_ids)]
    if search:
        df = df[df["description"].str.contains(search, case=False, na=False)]

    if df.empty:
        st.info("No items match your filters.")
        return

    # Progress
    total = len(elements_df)
    done  = len(logged_ids)
    st.markdown(
        f"<div style='font-size:0.82rem;color:#8a96a8;margin-bottom:0.75rem;'>"
        f"<b style='color:#0f1f3d;'>{done}</b> of {total} items logged for this project"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.progress(done / total if total > 0 else 0)

    st.markdown("---")

    # Group by section → subsection
    for section, sec_df in df.groupby("section_name", sort=False):
        st.markdown(
            f"<div style='font-family:DM Serif Display,serif;font-size:1.15rem;"
            f"color:#0f1f3d;margin:1.2rem 0 0.5rem;'>{section}</div>",
            unsafe_allow_html=True,
        )

        for subsection, sub_df in sec_df.groupby("subsection", sort=False):
            st.markdown(
                f"<div style='font-size:0.78rem;letter-spacing:0.06em;text-transform:uppercase;"
                f"color:#8a96a8;margin:0.6rem 0 0.3rem;'>{subsection}</div>",
                unsafe_allow_html=True,
            )

            for _, row in sub_df.iterrows():
                element_id   = row["id"]
                is_logged    = element_id in logged_ids
                badge        = "✓ " if is_logged else ""
                cost_hint    = ""

                # Find existing rate if logged
                existing_rate = None
                if is_logged and not existing_df.empty:
                    match = existing_df[existing_df["element_id"] == element_id]
                    if not match.empty:
                        er = match.iloc[0]["rate"]
                        eu = match.iloc[0]["unit"]
                        existing_rate = er
                        cost_hint = f" — £{er:,.0f}/{eu}"

                with st.expander(f"{badge}{row['item_code']}  {row['description']}{cost_hint}"):
                    c1, c2, c3, c4 = st.columns([2, 1.5, 1.5, 1])

                    with c1:
                        rate_val = st.number_input(
                            "Rate (£)",
                            min_value=0.0,
                            step=1.0,
                            format="%.2f",
                            value=float(existing_rate) if existing_rate is not None else 0.0,
                            key=f"rate_{element_id}",
                        )
                    with c2:
                        unit_options = ["m2", "m3", "m", "nr", "t", "ft2", "item", "pct", "storeys"]
                        default_unit = row["typical_unit"]
                        if default_unit not in unit_options:
                            unit_options.insert(0, default_unit)
                        unit_val = st.selectbox(
                            "Unit",
                            unit_options,
                            index=unit_options.index(default_unit),
                            key=f"unit_{element_id}",
                        )
                    with c3:
                        qty_val = st.number_input(
                            "Quantity",
                            min_value=0.0,
                            step=1.0,
                            format="%.1f",
                            key=f"qty_{element_id}",
                        )
                    with c4:
                        notes_val = st.text_input("Notes", key=f"notes_{element_id}", label_visibility="collapsed", placeholder="Notes...")

                    col_btn, col_total = st.columns([1, 3])
                    with col_btn:
                        if st.button(
                            "Update" if is_logged else "Log Rate",
                            key=f"save_{element_id}",
                            type="primary" if not is_logged else "secondary",
                            use_container_width=True,
                            disabled=rate_val == 0,
                        ):
                            total_cost = rate_val * qty_val if qty_val > 0 else None
                            payload = {
                                "project_id": project_id,
                                "element_id": element_id,
                                "rate":       rate_val,
                                "unit":       unit_val,
                                "quantity":   qty_val if qty_val > 0 else None,
                                "total_cost": total_cost,
                                "notes":      notes_val or None,
                            }
                            try:
                                if is_logged:
                                    # Update existing
                                    existing_row = existing_df[existing_df["element_id"] == element_id].iloc[0]
                                    _patch("rl_rates", existing_row["id"], payload)
                                else:
                                    _post("rl_rates", payload)
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed: {e}")

                    with col_total:
                        if rate_val > 0 and qty_val > 0:
                            st.markdown(
                                f"<div style='padding-top:0.5rem;font-family:DM Serif Display,serif;"
                                f"font-size:1rem;color:#0f1f3d;'>= £{rate_val * qty_val:,.0f}</div>",
                                unsafe_allow_html=True,
                            )


# ── Tab 2: Benchmark ──────────────────────────────────────────────────────────

def _render_benchmark():
    st.markdown("""
    <p style="color:#8a96a8;font-size:0.92rem;margin-top:0;">
        Select any line item to see how rates compare across all logged projects.
    </p>
    """, unsafe_allow_html=True)

    elements_df = load_elements()
    projects_df = load_projects()

    if projects_df.empty:
        st.info("No projects logged yet. Add rates in the Log Rates tab first.")
        return

    # ── Filters ───────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        sections = sorted(elements_df["section_name"].unique().tolist())
        bm_section = st.selectbox("Section", sections, key="bm_section")

    section_els = elements_df[elements_df["section_name"] == bm_section]

    with col2:
        subsections = sorted(section_els["subsection"].unique().tolist())
        bm_sub = st.selectbox("Subsection", subsections, key="bm_sub")

    sub_els = section_els[section_els["subsection"] == bm_sub]

    with col3:
        item_options = {
            f"{r['item_code']}  {r['description']}": r['id']
            for _, r in sub_els.iterrows()
        }
        bm_item_label = st.selectbox("Line item", list(item_options.keys()), key="bm_item")
        bm_element_id = item_options[bm_item_label]

    # ── Fetch benchmark data ──────────────────────────────────────────────────
    bm_df = load_benchmark(bm_element_id)

    if bm_df.empty:
        st.info("No rates logged for this item yet. Add some in the Log Rates tab.")
        return

    # Flatten nested project fields
    bm_df["project_name"]     = bm_df["rl_projects"].apply(lambda x: x.get("name", "") if isinstance(x, dict) else "")
    bm_df["project_location"] = bm_df["rl_projects"].apply(lambda x: x.get("location", "") if isinstance(x, dict) else "")
    bm_df["project_type"]     = bm_df["rl_projects"].apply(lambda x: x.get("project_type", "") if isinstance(x, dict) else "")
    bm_df["contract_type"]    = bm_df["rl_projects"].apply(lambda x: x.get("contract_type", "") if isinstance(x, dict) else "")
    bm_df["cost_date"]        = bm_df["rl_projects"].apply(lambda x: x.get("cost_date", "")[:7] if isinstance(x, dict) else "")
    bm_df["gia_m2"]           = bm_df["rl_projects"].apply(lambda x: x.get("gia_m2") if isinstance(x, dict) else None)

    # ── Filter sidebar ────────────────────────────────────────────────────────
    cf1, cf2 = st.columns(2)
    with cf1:
        loc_options = ["All locations"] + sorted(bm_df["project_location"].unique().tolist())
        bm_location = st.selectbox("Filter by location", loc_options, key="bm_location")
    with cf2:
        type_options = ["All types"] + sorted(bm_df["project_type"].unique().tolist())
        bm_ptype = st.selectbox("Filter by project type", type_options, key="bm_ptype")

    filtered = bm_df.copy()
    if bm_location != "All locations":
        filtered = filtered[filtered["project_location"] == bm_location]
    if bm_ptype != "All types":
        filtered = filtered[filtered["project_type"] == bm_ptype]

    if filtered.empty:
        st.info("No data matches these filters.")
        return

    rates = filtered["rate"].astype(float)
    n     = len(rates)
    mn    = rates.min()
    mx    = rates.max()
    med   = rates.median()
    avg   = rates.mean()

    # ── Headline benchmark metrics ────────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        f"<div style='font-family:DM Serif Display,serif;font-size:1.1rem;"
        f"color:#0f1f3d;margin-bottom:1rem;'>"
        f"Benchmark: {bm_item_label.split('  ', 1)[-1]}</div>",
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Projects", n)
    with c2:
        st.metric("Minimum", f"£{mn:,.0f}")
    with c3:
        st.metric("Median", f"£{med:,.0f}")
    with c4:
        st.metric("Average", f"£{avg:,.0f}")
    with c5:
        st.metric("Maximum", f"£{mx:,.0f}")

    # ── Visual range bar ─────────────────────────────────────────────────────
    if n > 1:
        spread_pct = ((mx - mn) / mn * 100) if mn > 0 else 0
        st.markdown(
            f"<div style='font-size:0.82rem;color:#8a96a8;margin:0.5rem 0 1rem;'>"
            f"Spread: £{mn:,.0f} – £{mx:,.0f} &nbsp;({spread_pct:.0f}% range)</div>",
            unsafe_allow_html=True,
        )

        # Simple HTML range bar
        if mx > mn:
            med_pct = int((med - mn) / (mx - mn) * 100)
            avg_pct = int((avg - mn) / (mx - mn) * 100)
        else:
            med_pct = avg_pct = 50

        st.markdown(f"""
        <div style="position:relative;height:28px;background:#f0ede8;
                    border-radius:4px;margin-bottom:1.5rem;border:1px solid #ddd8d0;">
            <div style="position:absolute;top:50%;left:{med_pct}%;
                        transform:translate(-50%,-50%);
                        width:3px;height:22px;background:#0f1f3d;border-radius:2px;">
            </div>
            <div style="position:absolute;top:50%;left:{avg_pct}%;
                        transform:translate(-50%,-50%);
                        width:10px;height:10px;background:#c8a84b;
                        border-radius:50%;border:2px solid white;">
            </div>
        </div>
        <div style="display:flex;justify-content:space-between;
                    font-size:0.75rem;color:#8a96a8;margin-top:-1.2rem;margin-bottom:1rem;">
            <span>£{mn:,.0f} min</span>
            <span style="color:#0f1f3d;">▌ median &nbsp; ● avg</span>
            <span>£{mx:,.0f} max</span>
        </div>
        """, unsafe_allow_html=True)

    # ── Project-by-project table ──────────────────────────────────────────────
    st.markdown("#### All data points")

    display = filtered[[
        "project_name", "project_location", "project_type",
        "contract_type", "cost_date", "rate", "unit",
        "quantity", "total_cost", "notes"
    ]].copy()

    display.columns = [
        "Project", "Location", "Type", "Contract",
        "Date", "Rate (£)", "Unit", "Qty", "Total (£)", "Notes"
    ]

    # Format numbers
    display["Rate (£)"]  = display["Rate (£)"].apply(lambda x: f"£{float(x):,.0f}" if x else "—")
    display["Total (£)"] = display["Total (£)"].apply(lambda x: f"£{float(x):,.0f}" if x else "—")
    display["Qty"]       = display["Qty"].apply(lambda x: f"{float(x):,.0f}" if x else "—")

    st.dataframe(display, use_container_width=True, hide_index=True)

    # ── Export ────────────────────────────────────────────────────────────────
    col_dl, _ = st.columns([1, 4])
    with col_dl:
        csv = display.to_csv(index=False)
        item_slug = bm_item_label.split("  ", 1)[-1][:30].replace(" ", "_")
        st.download_button(
            "⬇️ Export CSV",
            data=csv,
            file_name=f"benchmark_{item_slug}.csv",
            mime="text/csv",
            use_container_width=True,
        )


# ── Main render ───────────────────────────────────────────────────────────────

def render():
    st.markdown("""
    <div style="margin-bottom:0.25rem;">
        <span style="font-family:'DM Serif Display',serif;font-size:2rem;color:#0f1f3d;">
            Rate Library
        </span>
    </div>
    <p style="color:#8a96a8;margin-top:0;font-size:0.95rem;">
        Log rates from every cost plan you complete. Build your own benchmark database over time.
    </p>
    """, unsafe_allow_html=True)

    tab_log, tab_bm = st.tabs(["📥  Log Rates", "📊  Benchmark"])

    with tab_log:
        _render_log_rates()

    with tab_bm:
        _render_benchmark()