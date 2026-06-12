"""
admin_publish_rates.py
----------------------
Page: Admin — Publish Rates

Shows all pending rate submissions. Admin can review each one,
then publish it into the live rates table with auto-calculated
spec bands (Budget / Standard / High Spec / Bespoke).

Phase 1 logic (1-4 projects):
    Submitted rate anchored at its spec band; other bands derived.

Phase 2 logic (5+ projects per element):
    Bands calculated from real submitted data.

The publish process:
    1. Creates a new rate_set (or adds to existing draft)
    2. Writes rates rows for all 4 spec bands per element per location
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


def _post_many(table: str, payloads: list, batch_size: int = 100) -> None:
    """Insert many rows in batches (much faster than one POST per row)."""
    url, key = _creds()
    for i in range(0, len(payloads), batch_size):
        batch = payloads[i:i + batch_size]
        r = httpx.post(
            f"{url}/rest/v1/{table}",
            headers=_headers(key),
            json=batch,
            timeout=30,
        )
        r.raise_for_status()


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
    """Load all approved rates for a given element+location to calculate spec bands."""
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
def load_applicability_stats() -> pd.DataFrame:
    """
    How often is each element applicable across ALL submissions?
    An element 'answered' = a rate was entered OR it was marked N/A.
    Applicability % = answered-with-rate / total answered.
    """
    rows = _get(
        "submitted_rates",
        "select=element_id,rate_unit,elements(element_name,category,sort_order)"
    )
    if not rows:
        return pd.DataFrame()

    stats: dict = {}
    for r in rows:
        eid = r["element_id"]
        el  = r.get("elements") or {}
        s = stats.setdefault(eid, {
            "Element":    el.get("element_name", eid),
            "Category":   el.get("category", "—"),
            "sort_order": el.get("sort_order", 999),
            "Answered":   0,
            "N/A":        0,
        })
        s["Answered"] += 1
        if r.get("rate_unit") == "N/A":
            s["N/A"] += 1

    out = []
    for s in stats.values():
        applicable = s["Answered"] - s["N/A"]
        pct = (applicable / s["Answered"] * 100) if s["Answered"] else 0
        out.append({
            "Element":         s["Element"],
            "Category":        s["Category"],
            "Times answered":  s["Answered"],
            "Times N/A":       s["N/A"],
            "Applicability":   f"{pct:.0f}%",
            "sort_order":      s["sort_order"],
            "_pct":            pct,
        })
    df = pd.DataFrame(out).sort_values(["_pct", "sort_order"])
    return df.drop(columns=["sort_order", "_pct"])


@st.cache_data(ttl=60)
def load_elements_lookup() -> dict:
    rows = _get("elements", "select=element_id,element_name,category,sort_order")
    return {r["element_id"]: r for r in rows}


# ── Spec band calculation ─────────────────────────────────────────────────────

# The four published rate bands. These are written to the `quartile`
# column of the rates table (the column keeps its old name to avoid a
# database migration — only the VALUES stored in it have changed).
SPEC_BANDS = ["Budget", "Standard", "High Spec", "Bespoke"]

# Phase 1 ladder: each band as a multiple of the Standard rate.
SPEC_FACTORS = {
    "Budget":    0.75,
    "Standard":  1.00,
    "High Spec": 1.12,
    "Bespoke":   1.25,
}

# Translation for legacy data published under the old quartile names.
# "Low quart" is retired (Standard is taken from the old Median).
LEGACY_TO_SPEC = {
    "Min":         "Budget",
    "Median":      "Standard",
    "Upper quart": "High Spec",
    "Max":         "Bespoke",
}


def calculate_spec_bands(submitted_rate: float, all_rates: list,
                         spec_level: str = "Standard") -> dict:
    """
    Calculate the 4 spec-band rates (Budget / Standard / High Spec / Bespoke).

    Phase 1 (fewer than 5 data points):
        The submitted rate is anchored at the band matching the project's
        spec level, and the other bands are derived from it using the
        fixed factor ladder. A Bespoke project's rate therefore becomes
        the Bespoke band exactly, with everything else built BELOW it —
        no fictional rates are ever created above it.

    Phase 2 (5+ data points): bands come from real submitted data:
        Budget = lowest observed, Standard = median,
        High Spec = 75th percentile, Bespoke = highest observed.
    """
    # Convert all rates to £/m2 for consistency
    numeric_rates = []
    for r in all_rates:
        rate = float(r["rate"])
        if r.get("rate_unit") == "£/ft2":
            rate = rate * 10.764  # convert to £/m2
        numeric_rates.append(rate)

    if len(numeric_rates) >= 5:
        # Phase 2 — bands from real data
        numeric_rates.sort()
        n = len(numeric_rates)
        return {
            "Budget":    round(numeric_rates[0], 2),
            "Standard":  round(numeric_rates[int(n * 0.50)], 2),
            "High Spec": round(numeric_rates[int(n * 0.75)], 2),
            "Bespoke":   round(numeric_rates[-1], 2),
        }
    else:
        # Phase 1 — anchor the submitted rate at its own spec band,
        # derive the implied Standard rate, then apply the ladder.
        anchor_factor = SPEC_FACTORS.get(spec_level, 1.00)
        implied_standard = submitted_rate / anchor_factor
        return {
            band: round(implied_standard * factor, 2)
            for band, factor in SPEC_FACTORS.items()
        }


# ── Publish logic ─────────────────────────────────────────────────────────────

def publish_submission(submission_id: str, submission: dict, rates_df: pd.DataFrame, set_name: str):
    """
    Publish a submission into the live rates table.

    1. Read all rates from the current live rate set (so nothing is lost)
    2. Supersede the existing published rate set
    3. Create a new rate set
    4. Carry forward all existing rates EXCEPT the element+location
       combinations being republished by this submission
    5. Write 4 fresh spec band rows per element from this submission
    6. Mark submission as approved

    This means each publish UPDATES the live rates rather than
    REPLACING them — rates for other locations and other elements
    are preserved.
    """
    location = submission["location"]
    spec_level = submission.get("spec_level") or "Standard"
    elements_lookup = load_elements_lookup()

    with st.spinner("Publishing rates to estimating engine..."):

        # ── Step 1: Read existing live rates BEFORE superseding ──────────────
        existing_sets = _get(
            "rate_sets",
            "is_draft=eq.false&superseded_at=is.null"
            "&order=published_at.desc&select=rate_set_id"
        )

        carried_rates = []
        if existing_sets:
            current_set_id = existing_sets[0]["rate_set_id"]
            carried_rates = _get(
                "rates",
                f"rate_set_id=eq.{current_set_id}"
                "&select=element_id,location,quartile,rate,rate_unit"
            )

        # ── Step 2: Supersede existing published rate set(s) ─────────────────
        for old_set in existing_sets:
            _patch(
                "rate_sets",
                old_set["rate_set_id"],
                {"superseded_at": "now()"},
                id_col="rate_set_id"
            )

        # ── Step 3: Create new rate set ───────────────────────────────────────
        new_set = _post("rate_sets", {
            "set_name":     set_name,
            "notes":        f"Published from submission: {submission['project_name']}",
            "is_draft":     False,
            "published_at": "now()",
            "published_by": submission.get("submitted_by") or "CPC Admin",
        })
        new_rate_set_id = new_set["rate_set_id"]

        # ── Step 4: Build the new rows for this submission ───────────────────
        new_rows        = []
        replaced_keys   = set()   # (element_id, location) pairs being updated
        skipped_pct     = 0
        skipped_zero    = 0
        skipped_na      = 0

        for _, rate_row in rates_df.iterrows():
            element_id = rate_row["element_id"]
            rate_unit  = rate_row["rate_unit"]

            # Skip % rates — not published to the rates table
            if rate_unit == "%":
                skipped_pct += 1
                continue

            # Skip N/A rows — element not applicable to this project.
            # Recorded in submitted_rates for applicability tracking only.
            if rate_unit == "N/A":
                skipped_na += 1
                continue

            # Convert submitted rate to £/m2
            submitted_rate = float(rate_row["rate"])

            # Skip rates of zero — these happen when an area (e.g. NIA)
            # was missing at submission time, so no rate was calculable.
            # Publishing them would push £0.00 into the live engine.
            if submitted_rate <= 0:
                skipped_zero += 1
                continue

            if rate_unit == "£/ft2":
                median_rate = submitted_rate * 10.764
            else:
                median_rate = submitted_rate
            publish_unit = "£/m2"

            # Load all historical rates for this element+location
            all_historical = load_all_approved_rates(location, element_id)

            # Calculate the 4 spec-band rates, anchored to the project's spec level
            bands = calculate_spec_bands(median_rate, all_historical, spec_level)

            replaced_keys.add((element_id, location))

            for band_name, band_rate in bands.items():
                new_rows.append({
                    "rate_set_id": new_rate_set_id,
                    "element_id":  element_id,
                    "location":    location,
                    "quartile":    band_name,   # column keeps legacy name; value is the spec band
                    "rate":        band_rate,
                    "rate_unit":   publish_unit,
                })

        # ── Step 5: Carry forward rates not replaced by this submission ──────
        # Legacy rows published under the old quartile names are translated
        # to the new spec bands here (Min→Budget, Median→Standard,
        # Upper quart→High Spec, Max→Bespoke). Old "Low quart" rows are
        # dropped — that band no longer exists.
        carried_rows = []
        for old in carried_rates:
            key = (old.get("element_id"), old.get("location"))
            if key in replaced_keys:
                continue  # being replaced by fresh rates above

            band = old.get("quartile")
            if band not in SPEC_BANDS:
                band = LEGACY_TO_SPEC.get(band)  # translate old names
                if band is None:
                    continue  # retired band (e.g. "Low quart") — drop it

            carried_rows.append({
                "rate_set_id": new_rate_set_id,
                "element_id":  old.get("element_id"),
                "location":    old.get("location"),
                "quartile":    band,
                "rate":        old.get("rate"),
                "rate_unit":   old.get("rate_unit"),
            })

        # ── Step 6: Write everything in batches ──────────────────────────────
        all_rows = new_rows + carried_rows
        if all_rows:
            _post_many("rates", all_rows)

        published_count = len(new_rows)
        carried_count   = len(carried_rows)

        # ── Step 7: Mark submission as approved ───────────────────────────────
        _patch("submitted_projects", submission_id, {"status": "approved"})

    # Clear caches so estimating engine picks up new rates immediately
    st.cache_data.clear()

    return published_count, skipped_pct, skipped_zero, skipped_na, carried_count, new_rate_set_id


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

    if "Rate" in display_df.columns and "Rate Unit" in display_df.columns:
        display_df["Rate"] = [
            "N/A" if u == "N/A" else (f"£{float(x):,.2f}" if x else "—")
            for x, u in zip(display_df["Rate"], display_df["Rate Unit"])
        ]
    elif "Rate" in display_df.columns:
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

    # Spec band preview
    spec_level = submission.get("spec_level") or "Standard"
    st.markdown("---")
    st.markdown(
        f"<div style='font-size:0.85rem;font-weight:600;color:#0f1f3d;"
        f"margin-bottom:0.5rem;'>Spec band preview "
        f"(Phase 1 — submitted rate anchored at "
        f"<span style='color:#c8a84b;'>{spec_level}</span>)</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='font-size:0.78rem;color:#8a96a8;margin-bottom:0.75rem;'>"
        "The submitted rate becomes the band matching this project's spec "
        "level, and the other bands are derived from it — e.g. a Bespoke "
        "project's rate becomes the Bespoke band, with the bands below built "
        "from it only. Once 5+ projects are submitted for this location, "
        "bands will be calculated from real data automatically.</div>",
        unsafe_allow_html=True,
    )

    # Show preview for first 3 non-% elements
    preview_rows = []
    shown = 0
    for _, r in rates_df.iterrows():
        if r.get("rate_unit") in ("%", "N/A") or shown >= 3:
            continue
        rate   = float(r["rate"])
        unit   = r.get("rate_unit", "£/m2")
        m2rate = rate * 10.764 if unit == "£/ft2" else rate
        qs     = calculate_spec_bands(m2rate, [], spec_level)
        preview_rows.append({
            "Element":   r.get("element_name", r["element_id"]),
            "Budget":    f"£{qs['Budget']:,.2f}",
            "Standard":  f"£{qs['Standard']:,.2f}",
            "High Spec": f"£{qs['High Spec']:,.2f}",
            "Bespoke":   f"£{qs['Bespoke']:,.2f}",
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
                count, skipped, skipped_zero, skipped_na, carried, new_id = publish_submission(
                    submission_id, submission, rates_df, set_name
                )
                st.success(
                    f"✅ Published successfully! "
                    f"{count} new rate rows written across 4 spec bands. "
                    f"{carried} existing rate rows carried forward. "
                    f"{skipped} percentage-based items skipped. "
                    f"{skipped_na} marked N/A (not applicable — recorded for "
                    f"applicability tracking). "
                    f"Rate set ID: `{new_id}`"
                )
                if skipped_zero:
                    st.warning(
                        f"⚠️ {skipped_zero} element(s) were skipped because their "
                        f"submitted rate was £0 (usually caused by a missing GIA/NIA "
                        f"at submission time). These were NOT published."
                    )
                st.info(
                    "The estimating engine will use these rates immediately. "
                    "Refresh or change page to see the updated status badge."
                )
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

    # ── Element applicability tracker ────────────────────────────────────────
    try:
        applicability_df = load_applicability_stats()
    except Exception:
        applicability_df = pd.DataFrame()

    if not applicability_df.empty:
        with st.expander("📈 Element applicability — how often does each element occur?"):
            st.markdown(
                "<div style='font-size:0.8rem;color:#8a96a8;margin-bottom:0.75rem;'>"
                "Based on all submissions to date. <b>Times N/A</b> counts projects "
                "where the element was explicitly marked not applicable. Elements "
                "are sorted with the least applicable first — these are your "
                "rarely-occurring elements. The picture sharpens as more projects "
                "are submitted.</div>",
                unsafe_allow_html=True,
            )
            st.dataframe(applicability_df, use_container_width=True, hide_index=True)

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