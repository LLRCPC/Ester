"""
session_helpers.py
------------------
Shared session-state utilities used across app pages.
Kept in a standalone module to avoid circular imports between app.py and page modules.

Page index map:
  0  Dashboard
  1  Project Setup
  2  Building Configuration
  3  Building Overview
  4  Element Areas
  5  Cost Breakdown
  6  Save Project
  --- Admin only ---
  7  Rate Submission
  8  Publish Rates
"""

import streamlit as st

# ── Spec levels (replace the old quartile bands) ──────────────────────────────
SPEC_LEVELS = ["Budget", "Standard", "High Spec", "Bespoke"]

# Old saved projects / old published rates may still use the legacy
# quartile names — translate them to the new spec bands.
LEGACY_TO_SPEC = {
    "min": "Budget",
    "low quart": "Standard",
    "median": "Standard",
    "upper quart": "High Spec",
    "max": "Bespoke",
}


def resolve_spec(value: str) -> str:
    """Return a valid spec band, translating legacy quartile names."""
    v = (value or "").strip()
    return LEGACY_TO_SPEC.get(v.lower(), v) or "Standard"


# Main workflow pages (shown in step bar)
WORKFLOW_PAGES = [
    "Dashboard",
    "Project Setup",
    "Building Configuration",
    "Building Overview",
    "Element Areas",
    "Cost Breakdown",
    "Save Project",
]

# Admin pages (grouped separately in sidebar)
ADMIN_PAGES = [
    "Rate Submission",
    "Publish Rates",
]

# Combined list — index matches page_idx
PAGES = WORKFLOW_PAGES + ADMIN_PAGES


def go_to(idx: int):
    """Navigate to a page by index."""
    st.session_state.page_idx = max(0, min(idx, len(PAGES) - 1))


def new_project():
    """
    Reset all project-specific session state and navigate to Project Setup.
    Preserves app-level state (unit_system, area_unit).
    """
    defaults = {
        # Project identity
        "project_id":             None,
        "project_name":           "",
        "postcode":               "",
        "location":               "",
        "quartile":               "Standard",   # holds the spec level (key name kept for saved-project compatibility)
        "fitout_scope":           "Whole building",

        # Areas — existing building (owned by Project Setup)
        "gia_m2":                 0.0,
        "nia_m2":                 0.0,
        "net_gross_pct":          0.0,

        # Areas — proposed building (owned by Building Config)
        "proposed_gia_m2":        0.0,
        "proposed_nia_m2":        0.0,
        "proposed_net_gross_pct": 0.0,

        # Existing building snapshot (written by project_setup, read by overview/config)
        'ex_project_name':   '',
        'ex_location':       '',
        'ex_building_type':  'Office',
        'ex_refurb_scope':   'Full Strip Out',
        'ex_spec_level':     'Standard',
        'ex_gia_m2':         0.0,
        'ex_nia_m2':         0.0,
        'ex_storeys_above':  0,
        'ex_storeys_below':  0,
        'ex_floor_to_floor': 0.0,
        'ex_perimeter_m':    0.0,
        'ex_facade_area_m2': 0.0,
        'ex_roof_area_m2':   0.0,
        'ex_num_wc_cores':   0,
        'ex_num_lifts':      0,


        # Storeys
        "storeys_above":          0,
        "storeys_below":          0,

        # Building geometry (new)
        "floor_to_floor_m":       0.0,
        "perimeter_m":            0.0,
        "facade_area_m2":         0.0,
        "roof_area_m2":           0.0,

        # Building features (new)
        "num_wc_cores":           0,
        "num_lifts":              0,

        # Building extension page
        "ext_existing_storeys":   0,
        "ext_gia_per_floor_m2":   0.0,
        "ext_nia_per_floor_m2":   0.0,
        "ext_new_storeys":        0,
        "ext_new_gia_m2":         0.0,
        "ext_new_nia_m2":         0.0,
        "ext_lifts":              0,
        "ext_stairs":             0,
        "ext_roof_works":         False,
        "ext_structural_storeys": 0,

        # Cost
        "element_areas_m2":       {},
        "_last_total_cost":       0,

        # Postcode UI state
        "postcode_touched":       False,
        "_postcode_error":        "",
    }
    for k, v in defaults.items():
        st.session_state[k] = v

    # Clear per-element widget state
    for key in list(st.session_state.keys()):
        if key.endswith("_unit") and key not in (
            "breakdown_unit", "unit_system", "area_unit", "building_unit"
        ):
            del st.session_state[key]
        elif key.endswith("_area_input"):
            del st.session_state[key]
        elif key in ("_nia_ft2_input", "save_project_name_input", "element_initialised"):
            del st.session_state[key]

    st.session_state.page_idx = 1