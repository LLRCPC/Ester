"""
feedback.py
-----------
Two things in one file:

1. render_feedback_widget()  — call this at the bottom of app.py to show a
   small collapsible panel on every page where testers can submit bugs or
   suggestions.  Submissions are saved to the `feedback_submissions` table
   in Supabase.

2. render_admin_feedback()   — a full admin page (page index 9) that shows
   all submissions as cards, colour-coded by status (yellow = open,
   green = resolved), with a toggle button to mark each one as fixed.
"""

import os
from datetime import datetime, timezone

import httpx
import pandas as pd
import streamlit as st


# ── Supabase helpers ───────────────────────────────────────────────────────────

def _creds():
    url = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", "")
    return url, key


def _headers(key: str) -> dict:
    return {
        "apikey":        key,
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
    }


def _submit_feedback(payload: dict) -> None:
    url, key = _creds()
    r = httpx.post(
        f"{url}/rest/v1/feedback_submissions",
        headers=_headers(key),
        json=payload,
        timeout=10,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Supabase error [{r.status_code}]: {r.text}")


def _set_resolved(row_id: str, resolved: bool) -> None:
    """Toggle the resolved flag on a single feedback row."""
    url, key = _creds()
    r = httpx.patch(
        f"{url}/rest/v1/feedback_submissions?id=eq.{row_id}",
        headers=_headers(key),
        json={"resolved": resolved},
        timeout=10,
    )
    if r.status_code not in (200, 201, 204):
        raise RuntimeError(f"Supabase error [{r.status_code}]: {r.text}")


@st.cache_data(ttl=30)
def _load_all_feedback() -> pd.DataFrame:
    url, key = _creds()
    r = httpx.get(
        f"{url}/rest/v1/feedback_submissions?order=submitted_at.desc&select=*",
        headers=_headers(key),
        timeout=10,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Supabase error [{r.status_code}]: {r.text}")
    data = r.json()
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data)


# ── Page names (used to label which page the tester was on) ───────────────────

PAGE_NAMES = [
    "Dashboard", "Project Setup", "Building Extension", "Building Overview",
    "Elements", "Breakdown", "Save Project", "Rate Submission",
    "Publish Rates", "Feedback Admin",
]


# ── Floating feedback widget ───────────────────────────────────────────────────

def render_feedback_widget():
    """
    Renders a small, always-visible feedback bar at the bottom of every page.
    Call this once near the end of app.py, after the page routing block.
    """

    st.markdown("""
    <style>
    .main .block-container { padding-bottom: 6rem !important; }

    .feedback-bar {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        z-index: 9999;
        background: #0d1b36;
        border-top: 2px solid #c8a84b;
        padding: 0.45rem 1.5rem;
        display: flex;
        align-items: center;
        gap: 1rem;
        font-family: 'DM Sans', sans-serif;
        font-size: 0.8rem;
        color: #bcc6d8;
        box-shadow: 0 -4px 16px rgba(13,27,54,0.18);
    }
    .feedback-bar-label {
        color: #c8a84b;
        font-weight: 600;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        white-space: nowrap;
        font-size: 0.75rem;
    }
    .feedback-bar-hint {
        color: #8a96a8;
        font-size: 0.75rem;
    }
    </style>

    <div class="feedback-bar">
        <span class="feedback-bar-label">🐛 Beta Feedback</span>
        <span class="feedback-bar-hint">Found a bug or have a suggestion? Use the panel below ↓</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)

    with st.expander("🐛  Report a Bug or Suggestion", expanded=False):
        st.markdown(
            "<p style='color:#8a96a8;font-size:0.85rem;margin-top:0;'>"
            "Help us improve Ester — report anything that looks wrong or "
            "suggest something that would make it easier to use.</p>",
            unsafe_allow_html=True,
        )

        col1, col2 = st.columns(2)

        with col1:
            fb_type = st.selectbox(
                "Type",
                ["🐛 Bug", "💡 Suggestion", "🎨 UI / Design", "❓ Confusing", "Other"],
                key="fb_type",
            )

        with col2:
            if "Bug" in fb_type:
                fb_severity = st.selectbox(
                    "How bad?",
                    ["🟡 Minor", "🟠 Moderate", "🔴 Blocks me completely"],
                    key="fb_severity",
                )
            else:
                fb_severity = "N/A"
                st.selectbox("How bad?", ["N/A"], key="fb_severity", disabled=True)

        current_page_idx = st.session_state.get("page_idx", 0)
        current_page = PAGE_NAMES[current_page_idx] if current_page_idx < len(PAGE_NAMES) else "Unknown"

        # If a reset was requested (from a previous submission), clear the key
        # BEFORE the text area widget is drawn — Streamlit requires this ordering.
        if st.session_state.pop("fb_reset_message", False):
            st.session_state.pop("fb_message", None)

        fb_message = st.text_area(
            "Tell us what happened (or what you'd like to see)",
            placeholder="e.g. 'The GIA field reset when I clicked Next' or 'Would be great to see a cost/m² on the summary card'",
            height=100,
            key="fb_message",
        )

        col_submit, col_info = st.columns([1, 3])
        with col_submit:
            submit_clicked = st.button("Submit Feedback", type="primary", use_container_width=True, key="fb_submit")
        with col_info:
            st.markdown(
                f"<div style='color:#8a96a8;font-size:0.78rem;padding-top:0.6rem;'>"
                f"Submitting from: <b>{current_page}</b> · "
                f"Logged in as: <b>{st.session_state.get('current_user_email', 'unknown')}</b>"
                f"</div>",
                unsafe_allow_html=True,
            )

        # Show a persistent success banner if feedback was just submitted
        if st.session_state.get("fb_just_submitted"):
            st.markdown(
                """
                <div style="
                    background:#e6f9f0;
                    border:1.5px solid #2d6a4f;
                    border-radius:8px;
                    padding:0.75rem 1.1rem;
                    margin-top:0.5rem;
                    display:flex;
                    align-items:center;
                    gap:0.6rem;
                    font-size:0.9rem;
                    color:#1a4731;
                    font-weight:500;
                ">
                    ✅ &nbsp;<strong>Feedback submitted — thanks!</strong>&nbsp;
                    Your report has been sent to the team.
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.session_state["fb_just_submitted"] = False

        if submit_clicked:
            if not fb_message.strip():
                st.warning("Please write something before submitting.")
            else:
                try:
                    _submit_feedback({
                        "submitted_at":  datetime.now(timezone.utc).isoformat(),
                        "submitted_by":  st.session_state.get("current_user_email", "unknown"),
                        "page":          current_page,
                        "type":          fb_type,
                        "severity":      fb_severity,
                        "message":       fb_message.strip(),
                        "resolved":      False,
                    })
                    # Signal that the next render should show the banner and reset the form
                    st.session_state["fb_just_submitted"] = True
                    st.session_state["fb_reset_message"] = True
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Could not submit: {e}")


# ── Admin feedback page (page index 9) ────────────────────────────────────────

def render_admin_feedback():
    """Full-page admin view — colour-coded cards with resolve toggles."""

    st.markdown(
        '<div style="margin-bottom:0.25rem;">'
        '<span style="font-family:\'DM Serif Display\',serif;font-size:2rem;'
        'color:#0f1f3d;">Feedback & Bug Reports</span>'
        '<span style="display:inline-block;margin-left:0.75rem;'
        'background:#0f1f3d;color:#c8a84b;font-size:0.65rem;font-weight:700;'
        'letter-spacing:0.1em;text-transform:uppercase;padding:0.2rem 0.6rem;'
        'border-radius:4px;vertical-align:middle;">Admin</span></div>'
        '<p style="color:#8a96a8;margin-top:0;font-size:0.95rem;">'
        'All feedback submitted by beta testers. Yellow = open, Green = resolved.</p>',
        unsafe_allow_html=True,
    )

    col_refresh, col_export, _ = st.columns([1, 1, 4])
    with col_refresh:
        if st.button("🔄  Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    try:
        df = _load_all_feedback()
    except Exception as e:
        st.error(f"Could not load feedback: {e}")
        return

    if df.empty:
        st.info("No feedback submitted yet. Share the app with your team!")
        return

    # Ensure resolved column exists (in case older rows pre-date the column)
    if "resolved" not in df.columns:
        df["resolved"] = False
    df["resolved"] = df["resolved"].fillna(False)

    # ── Summary metrics ────────────────────────────────────────────────────────
    total       = len(df)
    bugs        = len(df[df["type"].str.contains("Bug", na=False)])
    suggestions = len(df[df["type"].str.contains("Suggestion", na=False)])
    open_count  = len(df[df["resolved"] == False])
    resolved_count = len(df[df["resolved"] == True])

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total", total)
    m2.metric("Bugs", bugs)
    m3.metric("Suggestions", suggestions)
    m4.metric("🟡 Open", open_count)
    m5.metric("✅ Resolved", resolved_count)

    st.markdown("---")

    # ── Filters ────────────────────────────────────────────────────────────────
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)

    with col_f1:
        type_opts = ["All types"] + sorted(df["type"].dropna().unique().tolist())
        filter_type = st.selectbox("Filter by type", type_opts, key="fb_admin_type")

    with col_f2:
        page_opts = ["All pages"] + sorted(df["page"].dropna().unique().tolist())
        filter_page = st.selectbox("Filter by page", page_opts, key="fb_admin_page")

    with col_f3:
        user_opts = ["All users"] + sorted(df["submitted_by"].dropna().unique().tolist())
        filter_user = st.selectbox("Filter by user", user_opts, key="fb_admin_user")

    with col_f4:
        filter_status = st.selectbox(
            "Filter by status",
            ["All", "🟡 Open only", "✅ Resolved only"],
            key="fb_admin_status",
        )

    # Apply filters
    view = df.copy()
    if filter_type != "All types":
        view = view[view["type"] == filter_type]
    if filter_page != "All pages":
        view = view[view["page"] == filter_page]
    if filter_user != "All users":
        view = view[view["submitted_by"] == filter_user]
    if filter_status == "🟡 Open only":
        view = view[view["resolved"] == False]
    elif filter_status == "✅ Resolved only":
        view = view[view["resolved"] == True]

    st.markdown(f"**{len(view)} entries shown**")
    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    # ── Cards ──────────────────────────────────────────────────────────────────
    for _, row in view.iterrows():
        resolved    = bool(row.get("resolved", False))
        row_id      = str(row.get("id", ""))
        fb_type     = str(row.get("type", ""))
        severity    = str(row.get("severity", "N/A"))
        message     = str(row.get("message", ""))
        submitted_by = str(row.get("submitted_by", ""))
        page        = str(row.get("page", ""))
        submitted_at = str(row.get("submitted_at", ""))[:16].replace("T", " ")

        # Colour scheme: green border/bg if resolved, yellow if open
        if resolved:
            border_color = "#2d6a4f"
            bg_color     = "#f0faf5"
            badge_bg     = "#2d6a4f"
            badge_color  = "#ffffff"
            badge_text   = "✅ Resolved"
            btn_label    = "↩️  Mark as Open"
            btn_new_state = False
        else:
            border_color = "#b8860b"
            bg_color     = "#fffbea"
            badge_bg     = "#f0a500"
            badge_color  = "#ffffff"
            badge_text   = "🟡 Open"
            btn_label    = "✅  Mark as Resolved"
            btn_new_state = True

        # Card HTML
        st.markdown(
            f"""
            <div style="
                background:{bg_color};
                border:1.5px solid {border_color};
                border-radius:8px;
                padding:1rem 1.25rem 0.75rem;
                margin-bottom:0.75rem;
            ">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;flex-wrap:wrap;gap:0.5rem;">
                    <div style="display:flex;gap:0.5rem;align-items:center;flex-wrap:wrap;">
                        <span style="background:{badge_bg};color:{badge_color};font-size:0.7rem;font-weight:700;
                            letter-spacing:0.06em;text-transform:uppercase;padding:0.2rem 0.55rem;
                            border-radius:4px;">{badge_text}</span>
                        <span style="background:#0d1b36;color:#e8cc7a;font-size:0.7rem;font-weight:600;
                            padding:0.2rem 0.55rem;border-radius:4px;">{fb_type}</span>
                        {"<span style='background:#c0392b;color:#fff;font-size:0.7rem;font-weight:600;padding:0.2rem 0.55rem;border-radius:4px;'>" + severity + "</span>" if severity not in ("N/A", "nan") else ""}
                    </div>
                    <div style="font-size:0.75rem;color:#8a96a8;">
                        {submitted_by} &nbsp;·&nbsp; {page} &nbsp;·&nbsp; {submitted_at}
                    </div>
                </div>
                <div style="font-size:0.9rem;color:#0d1b36;line-height:1.6;">{message}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Resolve / re-open button sits just below each card
        btn_key = f"fb_resolve_{row_id}"
        if st.button(btn_label, key=btn_key):
            try:
                _set_resolved(row_id, btn_new_state)
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Could not update: {e}")

        st.markdown("<div style='height:0.25rem'></div>", unsafe_allow_html=True)

    # ── CSV export ─────────────────────────────────────────────────────────────
    export_cols = [c for c in ["submitted_at", "submitted_by", "page", "type", "severity", "message", "resolved"] if c in view.columns]
    csv_bytes = view[export_cols].to_csv(index=False).encode("utf-8")
    with col_export:
        st.download_button(
            label="⬇️  Export to CSV",
            data=csv_bytes,
            file_name=f"ester_feedback_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True,
        )