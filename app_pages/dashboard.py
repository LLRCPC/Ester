import streamlit as st
from engine.project_store import list_projects, load_project, delete_project
from engine.session_helpers import new_project


def _restore_project(project_id: str):
    """Load a saved project into session state and jump to Breakdown."""
    try:
        data = load_project(project_id)
    except FileNotFoundError:
        st.error(f"Project '{project_id}' could not be found.")
        return

    st.session_state.project_id       = data.get("project_id")
    st.session_state.project_name     = data.get("project_name", "")
    st.session_state.gia_m2           = data.get("gia_m2", 0.0)
    st.session_state.nia_m2           = data.get("nia_m2", 0.0)
    st.session_state.location         = data.get("location", "")
    st.session_state.quartile         = data.get("quartile", "Median")
    st.session_state.element_areas_m2 = data.get("element_areas_m2", {})
    st.session_state._last_total_cost  = data.get("total_cost", 0)
    st.session_state.page_idx = 3   # jump straight to Breakdown


def render(db: dict):
    st.markdown("""
    <div class="page-title">Dashboard</div>
    <p class="page-subtitle">Your saved cost plans. Open a project to review or edit it.</p>
    """, unsafe_allow_html=True)

    col_new, _ = st.columns([1, 4])
    with col_new:
        if st.button("＋  New Project", type="primary", use_container_width=True):
            new_project()
            st.rerun()

    st.markdown("---")

    projects = list_projects()

    if not projects:
        st.markdown("""
        <div style="text-align:center;padding:5rem 2rem;">
            <div style="font-size:3.5rem;margin-bottom:1rem;opacity:0.35;">📁</div>
            <div style="font-family:'DM Serif Display',serif;font-size:1.25rem;color:#0f1f3d;">
                No saved projects yet
            </div>
            <div style="margin-top:0.5rem;font-size:0.9rem;color:#8a96a8;">
                Start a new project to build your first cost plan.
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    # Header row
    col_h1, col_h2, col_h3, col_h4, col_h5 = st.columns([4, 2, 2, 1, 1])
    for col, label in zip(
        [col_h1, col_h2, col_h3, col_h4, col_h5],
        ["Project", "Location", "Total Cost", "", ""]
    ):
        col.markdown(f'<span style="font-size:0.75rem;letter-spacing:0.06em;text-transform:uppercase;color:#8a96a8;">{label}</span>', unsafe_allow_html=True)

    st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)

    for proj in projects:
        col1, col2, col3, col4, col5 = st.columns([4, 2, 2, 1, 1])

        with col1:
            gia_str  = f"{proj['gia_m2']:,.0f} m²" if proj.get("gia_m2") else "—"
            saved    = proj["saved_at"][:10] if proj.get("saved_at") else ""
            st.markdown(f"""
            <div class="proj-card">
                <div class="proj-title">{proj.get("project_name") or "Untitled"}</div>
                <div class="proj-meta">GIA: {gia_str} &nbsp;·&nbsp; Saved: {saved}</div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(
                f'<div style="padding-top:1rem;font-size:0.9rem;color:#0f1f3d;">'
                f'{proj.get("location", "—")}</div>',
                unsafe_allow_html=True
            )

        with col3:
            if proj.get("total_cost"):
                st.markdown(
                    f'<div style="padding-top:0.8rem;font-family:DM Serif Display,serif;'
                    f'font-size:1.1rem;color:#0f1f3d;">£{proj["total_cost"]:,.0f}</div>',
                    unsafe_allow_html=True
                )

        with col4:
            st.write("")
            if st.button("Open", key=f"open_{proj['project_id']}", use_container_width=True):
                _restore_project(proj["project_id"])
                st.rerun()

        with col5:
            st.write("")
            if st.button("🗑", key=f"del_{proj['project_id']}", help="Delete project"):
                delete_project(proj["project_id"])
                st.rerun()