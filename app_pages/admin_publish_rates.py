"""
admin_publish_rates.py
----------------------
Page: Admin — Publish Rates

Shows all pending rate submissions. Admin can review each one,
then publish it into the live rates table with auto-calculated
quartile spread (±% from the submitted median rate).

Phase 1 logic (1-4 projects):
    Published as Median. Min/Max/Quartiles calculated as % spread.

Phase 2 logic (5+ projects per element):
    True statistical quartiles calculated from the dataset.

The publish process:
    1. Creates a new rate_set (or adds to existing draft)
    2. Writes rates rows for all 5 quartiles per element per location
    3. Supersedes the previous published rate_set
    4. Marks the submission as 'approved'
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


def _patch(table: str, row_id: str, payload: dict, id_col: str = "id") -> dict:
    url, key = _creds()
    r = httpx.patch(
        f"{url}/rest/v1/{table}?{id_col}=eq.{row_id}",
        headers=_headers(key),
        json=payload,
        timeout=15,
    )
    r.raise_for_status()
    result = r.json()
    return result[0] if isinstance(result, list) else result


def _delete(table: str, params: str) -> None:
    url, key = _creds()
    r = httpx.delete(
        f"{url}/rest/v1/{table}?{params}",
        headers=_headers(key),
        timeout=15,
    )
    r.raise_for_status()


# ── Data loaders ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=30)
def load_submissions() -> pd.DataFrame:
    """Load all submitted projects with rate counts."""
    rows = _get(
        "submitted_projects",
        "order=submitted_at.desc&select=*"
    )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


@st.cache_data(ttl=30)
def load_submission_rates(submission_id: str) -> pd.DataFrame:
    """Load all rates for a specific submission."""
    rows = _get(
        "submitted_rates",
        f"submission_id=eq.{submission_id}&select=*,elements(element_name,category,sort_order)"
    )
    return pd.DataFrame(rows) if rows else pd.DataFrame()


@st.cache_data(ttl=30)
def load_all_approved_rates(location: str, element_id: str) -> list:
    """Load all approved rates for a given element+location to calculate quartiles."""
    # Get all approved submission IDs for this location
    submissions = _get(
        "submitted_projects",
        f"status=eq.approved&location=eq.{location}&select=id"
    )
    if not submissions:
        return []

    sub_ids = [s["id"] for s in submissions]

    # Get all rates for this element across those submissions
    all_rates = []
    for sub_id in sub_ids:
        rates = _get(
            "submitted_rates",
            f"submission_id=eq.{sub_id}&element_id=eq.{element_id}&select=rate,rate_unit"
        )
        all_rates.extend(rates)

    return all_rates


@st.cache_data(ttl=60)
def load_elements_lookup() -> dict:
    rows = _get("elements", "select=element_id,element_name,category,sort_order")
    return {r["element_id"]: r for r in rows}


# ── Quartile calculation ──────────────────────────────────────────────────────

QUARTILE_NAMES = ["Min", "Low quart", "Median", "Upper quart", "Max"]

# Phase 1 spread percentages applied around the median
# Min = -25%, Low quart = -12%, Median = 0%, Upper quart = +12%, Max = +25%
PHASE1_SPREADS = {
    "Min":         -0.25,
    "Low quart":   -0.12,
    "Median":       0.00,
    "Upper quart": +0.12,
    "Max":         +0.25,
}


def calculate_quartiles(median_rate: float, all_rates: list) -> dict:
    """
    Calculate 5 quartile values from available data.
    
    Phase 1 (fewer than 5 data points): apply fixed % spread around median.
    Phase 2 (5+ data points): calculate true statistical quartiles.
    """
    # Convert all rates to £/m2 for consistency
    numeric_rates = []
    for r in all_rates:
        rate = float(r["rate"])
        if r.get("rate_unit") == "£/ft2":
            rate = rate * 10.764  # convert to £/m2
        numeric_rates.append(rate)

    if len(numeric_rates) >= 5:
        # Phase 2 — true quartiles
        numeric_rates.sort()
        n = len(numeric_rates)
        return {
            "Min":         round(numeric_rates[0], 2),
            "Low quart":   round(numeric_rates[int(n * 0.25)], 2),
            "Median":      round(numeric_rates[int(n * 0.50)], 2),
            "Upper quart": round(numeric_rates[int(n * 0.75)], 2),
            "Max":         round(numeric_rates[-1], 2),
        }
    else:
        # Phase 1 — spread around submitted median
        return {
            q: round(median_rate * (1 + spread), 2)
            for q, spread in PHASE1_SPREADS.items()
        }


# ── Publish logic ─────────────────────────────────────────────────────────────

def publish_submission(submission_id: str, submission: dict, rates_df: pd.DataFrame, set_name: str):
    """
    Publish a submission into the live rates table.
    
    1. Supersede existing published rate set
    2. Create new rate set
    3. Write 5 quartile rows per element
    4. Mark submission as approved
    """
    location = submission["location"]
    elements_lookup = load_elements_lookup()

    with st.spinner("Publishing rates to estimating engine..."):

        # ── Step 1: Supersede existing published rate set ─────────────────────
        existing = _get(
            "rate_sets",
            "is_draft=eq.false&superseded_at=is.null&select=rate_set_id"
        )
        for old_set in existing:
            _patch(
                "rate_sets",
                old_set["rate_set_id"],
                {"superseded_at": "now()"},
                id_col="rate_set_id"
            )

        # ── Step 2: Create new rate set ───────────────────────────────────────
        new_set = _post("rate_sets", {
            "set_name":     set_name,
            "notes":        f"Published from submission: {submission['project_name']}",
            "is_draft":     False,
            "published_at": "now()",
            "published_by": submission.get("submitted_by") or "CPC Admin",
        })
        new_rate_set_id = new_set["rate_set_id"]

        # ── Step 3: Write 5 quartile rows per element ─────────────────────────
        published_count = 0
        skipped_pct     = 0

        for _, rate_row in rates_df.iterrows():
            element_id = rate_row["element_id"]
            rate_unit  = rate_row["rate_unit"]

            # Skip % rates — not published to the rates table
            if rate_unit == "%":
                skipped_pct += 1
                continue

            # Convert submitted rate to £/m2
            submitted_rate = float(rate_row["rate"])
            if rate_unit == "£/ft2":
                median_rate = submitted_rate * 10.764
                publish_unit = "£/m2"
            else:
                median_rate = submitted_rate
                publish_unit = "£/m2"

            # Load all historical rates for this element+location
            all_historical = load_all_approved_rates(location, element_id)

            # Calculate 5 quartile values
            quartiles = calculate_quartiles(median_rate, all_historical)

            # Write one row per quartile
            for quartile_name, quartile_rate in quartiles.items():
                _post("rates", {
                    "rate_set_id": new_rate_set_id,
                    "element_id":  element_id,
                    "location":    location,
                    "quartile":    quartile_name,
                    "rate":        quartile_rate,
                    "rate_unit":   publish_unit,
                })
                published_count += 1

        # ── Step 4: Mark submission as approved ───────────────────────────────
        _patch("submitted_projects", submission_id, {"status": "approved"})

    # Clear caches so estimating engine picks up new rates immediately
    st.cache_data.clear()

    return published_count, skipped_pct, new_rate_set_id


# ── Render helpers ────────────────────────────────────────────────────────────

def _status_badge(status: str) -> str:
    colours = {
        "pending":  ("#fff8e6", "#c8a84b", "Pending"),
        "approved": ("#e8f5e9", "#2e7d32", "Approved"),
        "rejected": ("#fce8e6", "#c62828", "Rejected"),
    }
    bg, fg, label = colours.get(status, ("#f0f0f0", "#888", status.title()))
    return (
        f'<span style="background:{bg};color:{fg};'
        f'font-size:0.7rem;font-weight:600;letter-spacing:0.06em;'
        f'text-transform:uppercase;padding:0.2rem 0.6rem;'
        f'border-radius:4px;">{label}</span>'
    )


def _render_submission_detail(submission_id: str, submission: dict):
    """Render the expandable detail view for a single submission."""

    rates_df = load_submission_rates(submission_id)

    if rates_df.empty:
        st.warning("No rates found for this submission.")
        return

    # Flatten nested element info
    if "elements" in rates_df.columns:
        rates_df["element_name"] = rates_df["elements"].apply(
            lambda x: x.get("element_name", "") if isinstance(x, dict) else ""
        )
        rates_df["category"] = rates_df["elements"].apply(
            lambda x: x.get("category", "") if isinstance(x, dict) else ""
        )
        rates_df["sort_order"] = rates_df["elements"].apply(
            lambda x: x.get("sort_order", 999) if isinstance(x, dict) else 999
        )
        rates_df = rates_df.sort_values("sort_order")

    # Summary metrics
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Rates submitted", len(rates_df))
    with c2:
        st.metric("Location", submission.get("location", "—"))
    with c3:
        st.metric("Package", submission.get("package", "—"))
    with c4:
        st.metric("Spec level", submission.get("spec_level", "—"))

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    # Rates table
    display_cols = ["element_name", "category", "rate", "rate_unit", "quantity", "total_cost", "notes"]
    available    = [c for c in display_cols if c in rates_df.columns]
    display_df   = rates_df[available].copy()
    display_df.columns = [c.replace("_", " ").title() for c in available]

    if "Rate" in display_df.columns:
        display_df["Rate"] = display_df["Rate"].apply(
            lambda x: f"£{float(x):,.2f}" if x else "—"
        )
    if "Total Cost" in display_df.columns:
        display_df["Total Cost"] = display_df["Total Cost"].apply(
            lambda x: f"£{float(x):,.0f}" if x else "—"
        )
    if "Quantity" in display_df.columns:
        display_df["Quantity"] = display_df["Quantity"].apply(
            lambda x: f"{float(x):,.0f}" if x else "—"
        )

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # Quartile preview
    st.markdown("---")
    st.markdown(
        "<div style='font-size:0.85rem;font-weight:600;color:#0f1f3d;"
        "margin-bottom:0.5rem;'>Quartile spread preview (Phase 1 — ±25% around median)</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='font-size:0.78rem;color:#8a96a8;margin-bottom:0.75rem;'>"
        "Once 5+ projects are submitted for this location, true statistical "
        "quartiles will be calculated automatically.</div>",
        unsafe_allow_html=True,
    )

    # Show preview for first 3 non-% elements
    preview_rows = []
    shown = 0
    for _, r in rates_df.iterrows():
        if r.get("rate_unit") == "%" or shown >= 3:
            continue
        rate   = float(r["rate"])
        unit   = r.get("rate_unit", "£/m2")
        m2rate = rate * 10.764 if unit == "£/ft2" else rate
        qs     = calculate_quartiles(m2rate, [])
        preview_rows.append({
            "Element":     r.get("element_name", r["element_id"]),
            "Min":         f"£{qs['Min']:,.2f}",
            "Low Quart":   f"£{qs['Low quart']:,.2f}",
            "Median":      f"£{qs['Median']:,.2f}",
            "Upper Quart": f"£{qs['Upper quart']:,.2f}",
            "Max":         f"£{qs['Max']:,.2f}",
        })
        shown += 1

    if preview_rows:
        st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)
        if len(rates_df) > 3:
            st.caption(f"Showing 3 of {len(rates_df)} elements. All will be published.")

    # Publish controls
    st.markdown("---")

    if submission.get("status") == "approved":
        st.success("✅ This submission has already been published.")
        return

    col_name, col_btn = st.columns([3, 1])
    with col_name:
        set_name = st.text_input(
            "Rate set name",
            value=f"CPC Rate Set — {date.today().strftime('%B %Y')}",
            key=f"setname_{submission_id}",
            help="This name will appear in the rate_sets table.",
        )
    with col_btn:
        st.write("")
        st.write("")
        if st.button(
            "🚀  Publish to Estimating Engine",
            type="primary",
            key=f"publish_{submission_id}",
            use_container_width=True,
        ):
            try:
                count, skipped, new_id = publish_submission(
                    submission_id, submission, rates_df, set_name
                )
                st.success(
                    f"✅ Published successfully! "
                    f"{count} rate rows written across 5 quartiles. "
                    f"{skipped} percentage-based items skipped. "
                    f"Rate set ID: `{new_id}`"
                )
                st.info(
                    "The estimating engine will use these rates immediately. "
                    "Reload the app if you don't see the update."
                )
                st.rerun()
            except Exception as e:
                st.error(f"❌ Publish failed: {e}")


# ── Main render ───────────────────────────────────────────────────────────────

def render():

    st.markdown("""
    <div style="margin-bottom:0.25rem;">
        <span style="font-family:'DM Serif Display',serif;font-size:2rem;color:#0f1f3d;">
            Publish Rates
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
        Review pending rate submissions and publish them into the live estimating engine.
    </p>
    """, unsafe_allow_html=True)

    # ── Load submissions ──────────────────────────────────────────────────────
    try:
        submissions_df = load_submissions()
    except Exception as e:
        st.error(f"Could not load submissions: {e}")
        return

    if submissions_df.empty:
        st.markdown("""
        <div style="text-align:center;padding:5rem 2rem;">
            <div style="font-size:3rem;margin-bottom:1rem;opacity:0.35;">📭</div>
            <div style="font-family:'DM Serif Display',serif;font-size:1.25rem;color:#0f1f3d;">
                No submissions yet
            </div>
            <div style="margin-top:0.5rem;font-size:0.9rem;color:#8a96a8;">
                Submit rates from the Rate Submission page first.
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    # ── Summary metrics ───────────────────────────────────────────────────────
    total     = len(submissions_df)
    pending   = len(submissions_df[submissions_df["status"] == "pending"])
    approved  = len(submissions_df[submissions_df["status"] == "approved"])

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total submissions", total)
    with c2:
        st.metric("Pending review", pending)
    with c3:
        st.metric("Published", approved)

    st.markdown("---")

    # ── Filter ────────────────────────────────────────────────────────────────
    col_f1, col_f2, _ = st.columns([1, 1, 3])
    with col_f1:
        status_filter = st.selectbox(
            "Filter by status",
            ["All", "Pending", "Approved"],
            key="apr_status_filter",
        )
    with col_f2:
        location_filter = st.selectbox(
            "Filter by location",
            ["All", "London", "Birmingham", "Manchester"],
            key="apr_location_filter",
        )

    filtered_df = submissions_df.copy()
    if status_filter != "All":
        filtered_df = filtered_df[
            filtered_df["status"].str.lower() == status_filter.lower()
        ]
    if location_filter != "All":
        filtered_df = filtered_df[filtered_df["location"] == location_filter]

    if filtered_df.empty:
        st.info("No submissions match these filters.")
        return

    st.markdown(
        f"<div style='font-size:0.82rem;color:#8a96a8;margin-bottom:1rem;'>"
        f"Showing {len(filtered_df)} of {total} submissions</div>",
        unsafe_allow_html=True,
    )

    # ── Submission list ───────────────────────────────────────────────────────
    for _, row in filtered_df.iterrows():
        submission_id = row["id"]
        status        = row.get("status", "pending")
        project_name  = row.get("project_name", "Untitled")
        location      = row.get("location", "—")
        cost_date     = str(row.get("cost_date", ""))[:10]
        submitted_by  = row.get("submitted_by") or "—"
        package       = row.get("package", "—")
        submitted_at  = str(row.get("submitted_at", ""))[:10]

        # Header row for this submission
        header = (
            f'<div style="display:flex;justify-content:space-between;'
            f'align-items:center;flex-wrap:wrap;gap:0.5rem;">'
            f'<div>'
            f'<span style="font-family:DM Serif Display,serif;font-size:1rem;'
            f'color:#0f1f3d;">{project_name}</span>'
            f'<span style="font-size:0.78rem;color:#8a96a8;margin-left:0.75rem;">'
            f'📍 {location} &nbsp;·&nbsp; 📦 {package} &nbsp;·&nbsp; '
            f'📅 {cost_date} &nbsp;·&nbsp; 👤 {submitted_by}</span>'
            f'</div>'
            f'{_status_badge(status)}'
            f'</div>'
        )

        with st.expander(f"{project_name}  ·  {location}  ·  {cost_date}", expanded=(status == "pending")):
            st.markdown(header, unsafe_allow_html=True)
            st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)
            _render_submission_detail(submission_id, row.to_dict())

    st.markdown("---")
    st.caption(
        "⚠️ Publishing a submission supersedes the previous rate set. "
        "The estimating engine will use the new rates immediately."
    )