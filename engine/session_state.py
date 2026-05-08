import streamlit as st


DEFAULTS = {
    "page_idx": 0,
    "project_id": None,
    "project_name": "",
    "location": "London",   # ✅ safe default (no blank state ever)
    "quartile": "Median",
    "gia_m2": 0.0,
    "nia_m2": 0.0,
    "element_areas_m2": {},
    "breakdown_unit": "m²",
    "_last_total_cost": 0,
}


def init_session():
    """Initialise session safely once."""
    for key, value in DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value


def set_value(key, value):
    """Safe setter (centralised control)."""
    st.session_state[key] = value


def get_value(key, default=None):
    """Safe getter."""
    return st.session_state.get(key, default)


def reset_project():
    """Reset only project-related fields (not navigation)."""
    keys_to_reset = [
        "project_id",
        "project_name",
        "location",
        "quartile",
        "gia_m2",
        "nia_m2",
        "element_areas_m2",
        "_last_total_cost",
    ]

    for k in keys_to_reset:
        if k in DEFAULTS:
            st.session_state[k] = DEFAULTS[k]