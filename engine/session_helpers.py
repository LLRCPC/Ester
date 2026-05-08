"""
session_helpers.py
------------------
Shared session-state utilities used across app pages.
Kept in a standalone module to avoid circular imports between app.py and page modules.
"""

import streamlit as st

PAGES = ["Dashboard", "Project Setup", "Element Areas", "Cost Breakdown", "Save Project"]


def go_to(idx: int):
    """Navigate to a page by index."""
    st.session_state.page_idx = max(0, min(idx, len(PAGES) - 1))


def new_project():
    """
    Reset all project-specific session state and navigate to Project Setup.
    Preserves app-level state (unit_system, area_unit).
    """
    defaults = {
        "project_id":         None,
        "project_name":       "",
        "postcode":           "",
        "gia_m2":             0.0,
        "nia_m2":             0.0,
        "location":           "",
        "quartile":           "Median",
        "element_areas_m2":   {},
        "_last_total_cost":   0,
    }
    for k, v in defaults.items():
        st.session_state[k] = v

    # Clear per-element widget state
    for key in list(st.session_state.keys()):
        if key.endswith("_unit") and key not in ("breakdown_unit", "unit_system", "area_unit"):
            del st.session_state[key]
        elif key.endswith("_area_input"):
            del st.session_state[key]
        elif key == "_nia_ft2_input":
            del st.session_state[key]
        elif key == "save_project_name_input":
            del st.session_state[key]
        elif key == "element_initialised":
            del st.session_state[key]

    st.session_state.page_idx = 1