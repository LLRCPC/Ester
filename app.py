import streamlit as st
from engine.data_loader import load_cost_database, get_json_mtime
from engine.session_helpers import new_project, PAGES

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Ester",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,400&display=swap');
:root {
    --navy:#0f1f3d; --slate:#1e3358; --gold:#c8a84b; --gold-lt:#e8cc7a;
    --offwhite:#f7f5f0; --white:#ffffff; --mid:#8a96a8; --border:#ddd8d0;
    --shadow:0 2px 12px rgba(15,31,61,0.09); --radius:6px;
}
html,body,[class*="css"]{font-family:'DM Sans',sans-serif!important;background-color:var(--offwhite)!important;color:var(--navy);}
h1,h2,h3{font-family:'DM Serif Display',serif!important;font-weight:400!important;color:var(--navy)!important;}

/* Sidebar */
[data-testid="stSidebar"]{background:var(--navy)!important;border-right:2px solid rgba(200,168,75,0.25);}
[data-testid="stSidebar"] *{color:#c8d0df!important;}
[data-testid="stSidebar"] hr{border-color:rgba(255,255,255,0.12)!important;}
[data-testid="stSidebar"] label:has(input[type="radio"]:checked)>div:last-child{color:var(--gold)!important;font-weight:600!important;}

/* Step progress bar */
.step-bar{display:flex;border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;margin-bottom:2rem;background:var(--white);}
.step{flex:1;padding:10px 4px;text-align:center;font-size:0.73rem;font-weight:500;letter-spacing:0.05em;text-transform:uppercase;color:var(--mid);border-right:1px solid var(--border);background:var(--white);}
.step:last-child{border-right:none;}
.step.done{background:var(--offwhite);color:var(--navy);}
.step.done::before{content:"✓  ";}
.step.active{background:var(--navy);color:var(--white);font-weight:600;}

/* Metrics */
[data-testid="metric-container"]{background:var(--white);border:1px solid var(--border);border-radius:var(--radius);padding:1rem 1.25rem;box-shadow:var(--shadow);}
[data-testid="stMetricValue"]{font-family:'DM Serif Display',serif!important;font-size:1.6rem!important;color:var(--navy)!important;}
[data-testid="stMetricLabel"]{font-size:0.78rem!important;letter-spacing:0.05em!important;text-transform:uppercase!important;color:var(--mid)!important;}

/* Buttons */
.stButton>button{font-family:'DM Sans',sans-serif!important;font-weight:500!important;letter-spacing:0.03em!important;border-radius:var(--radius)!important;transition:all 0.18s ease!important;}
.stButton>button[kind="primary"]{background:var(--navy)!important;color:var(--white)!important;border:none!important;}
.stButton>button[kind="primary"]:hover{background:var(--slate)!important;transform:translateY(-1px)!important;box-shadow:0 4px 16px rgba(15,31,61,0.22)!important;}
.stButton>button:not([kind="primary"]){background:var(--white)!important;color:var(--navy)!important;border:1px solid var(--border)!important;}
.stButton>button:not([kind="primary"]):hover{border-color:var(--navy)!important;}

/* Expanders */
[data-testid="stExpander"]{background:var(--white)!important;border:1px solid var(--border)!important;border-radius:var(--radius)!important;margin-bottom:0.5rem!important;}

/* DataFrames */
[data-testid="stDataFrame"]{border:1px solid var(--border)!important;border-radius:var(--radius)!important;}

/* Inputs */
[data-testid="stNumberInput"] input,[data-testid="stTextInput"] input{border-radius:var(--radius)!important;}
[data-testid="stAlert"]{border-radius:var(--radius)!important;}
hr{border-color:var(--border)!important;margin:1.5rem 0!important;}

/* Project cards */
.proj-card{background:var(--white);border:1px solid var(--border);border-radius:var(--radius);padding:1.1rem 1.4rem;margin-bottom:0.6rem;box-shadow:var(--shadow);transition:border-color 0.15s;}
.proj-card:hover{border-color:var(--navy);}
.proj-title{font-family:'DM Serif Display',serif;font-size:1.05rem;color:var(--navy);}
.proj-meta{font-size:0.8rem;color:var(--mid);margin-top:3px;}
.page-title{font-family:'DM Serif Display',serif;font-size:2rem;color:var(--navy);margin-bottom:0.1rem;}
.page-subtitle{color:var(--mid);font-size:0.92rem;margin-top:0;margin-bottom:1.5rem;}

/* Login card */
.login-card{max-width:420px;margin:6rem auto;background:var(--white);border:1px solid var(--border);border-radius:10px;padding:2.5rem 2rem;box-shadow:0 4px 24px rgba(15,31,61,0.12);}
</style>
""", unsafe_allow_html=True)

# ── Session: initialise once ──────────────────────────────────────────────────
if "initialised" not in st.session_state:
    st.session_state.update({
        "authenticated":          False,
        "page_idx":               0,
        "project_id":             None,
        "project_name":           "",
        "gia_m2":                 0.0,
        "nia_m2":                 0.0,
        "location":               "",
        "quartile":               "Median",
        "element_areas_m2":       {},
        "breakdown_unit":         "m²",
        "_last_total_cost":       0,
        # Building extension defaults
        "ext_existing_storeys":   8,
        "ext_gia_per_floor_m2":   900.0,
        "ext_nia_per_floor_m2":   720.0,
        "ext_new_storeys":        0,
        "ext_new_gia_m2":         900.0,
        "ext_new_nia_m2":         720.0,
        "ext_lifts":              4,
        "ext_stairs":             2,
        "ext_roof_works":         False,
        "ext_structural_storeys": 0,
    })
    st.session_state.initialised = True

# ═════════════════════════════════════════════════════════════════════════════
# LOGIN GATE
# ═════════════════════════════════════════════════════════════════════════════

APP_PASSWORD = "CPC2026"   # ← change this

if not st.session_state.authenticated:

    from pathlib import Path

    st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

    logo_path = Path("assets/CPC_logo.png")
    logo_col1, logo_col2, logo_col3 = st.columns([1, 1.2, 1])
    with logo_col2:
        if logo_path.exists():
            st.image(str(logo_path), use_container_width=True)

    st.markdown(
        "<h2 style='text-align:center;margin-bottom:0;'>Construction Project Configurator</h2>",
        unsafe_allow_html=True
    )
    st.markdown(
        "<p style='text-align:center;font-size:0.85rem;"
        "color:#8a96a8;letter-spacing:0.08em;text-transform:uppercase;'>"
        "Cost Estimating Tool</p>",
        unsafe_allow_html=True
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        pwd = st.text_input(
            "Password",
            type="password",
            label_visibility="collapsed",
            placeholder="Enter password"
        )
        if st.button("Sign In", type="primary", use_container_width=True):
            if pwd == APP_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password")

    st.stop()


# ── Load DB ───────────────────────────────────────────────────────────────────
@st.cache_data
def load_db(mtime: float):
    return load_cost_database()

try:
    db = load_db(get_json_mtime())
except FileNotFoundError as e:
    st.error(f"**Cost database not found.**\n\n{e}")
    st.stop()
except (KeyError, ValueError) as e:
    st.error(f"**Cost database is invalid:** {e}")
    st.stop()

# ── Page definitions ──────────────────────────────────────────────────────────
PAGE_ICONS = ["🏠", "📋", "🏗️", "⚙️", "📊", "💾"]

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:

    from pathlib import Path
    logo_path = Path("assets/CPC_logo.png")
    if logo_path.exists():
        st.image(str(logo_path), width=130)

    st.markdown(
        "<div style='font-family:DM Serif Display,serif;"
        "color:#e8cc7a;font-size:0.95rem;line-height:1.1;'>"
        "Construction<br>Project<br>Configurator</div>"
        "<div style='font-size:0.7rem;color:#8a96a8;"
        "letter-spacing:0.08em;text-transform:uppercase;'>"
        "CPC Estimating Tool</div>",
        unsafe_allow_html=True
    )

    st.markdown("---")

    plain_labels = [f"{PAGE_ICONS[i]}  {PAGES[i]}" for i in range(len(PAGES))]
    selected = st.radio("nav", plain_labels, index=st.session_state.page_idx,
                        label_visibility="collapsed")
    new_idx = plain_labels.index(selected)
    if new_idx != st.session_state.page_idx:
        st.session_state.page_idx = new_idx
        st.rerun()

    st.markdown("---")

    has_project = bool(st.session_state.project_name or st.session_state.location)
    if has_project:
        summary_parts = []
        if st.session_state.project_name:
            summary_parts.append(
                f'<div style="font-family:DM Serif Display,serif;font-size:0.95rem;'
                f'color:#e8cc7a;margin-bottom:4px;">{st.session_state.project_name}</div>'
            )
        if st.session_state.location:
            summary_parts.append(f'<div>📍 {st.session_state.location}</div>')
        if st.session_state.quartile:
            summary_parts.append(f'<div>📊 {st.session_state.quartile}</div>')
        if st.session_state.gia_m2 > 0:
            summary_parts.append(f'<div>GIA: {st.session_state.gia_m2:,.0f} m²</div>')
        if st.session_state.nia_m2 > 0:
            from engine.unit_engine import convert_area
            nia_ft2 = convert_area(st.session_state.nia_m2, "m2", "ft2")
            summary_parts.append(f'<div>NIA: {nia_ft2:,.0f} ft²</div>')

        st.markdown(
            f'<div style="font-size:0.8rem;line-height:1.9;color:#c8d0df;">{"".join(summary_parts)}</div>',
            unsafe_allow_html=True,
        )
        st.markdown("---")

    if st.button("Sign Out", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

# ── Step progress bar ─────────────────────────────────────────────────────────
def render_step_bar(current: int):
    html = '<div class="step-bar">'
    for i, name in enumerate(PAGES):
        cls = "done" if i < current else ("active" if i == current else "")
        html += f'<div class="step {cls}">{PAGE_ICONS[i]} {name}</div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

render_step_bar(st.session_state.page_idx)

# ── Page routing ──────────────────────────────────────────────────────────────
idx = st.session_state.page_idx

if idx == 0:
    from app_pages.dashboard import render; render(db)
elif idx == 1:
    from app_pages.project_setup import render; render()
elif idx == 2:
    from app_pages.building_extension import render; render()
elif idx == 3:
    from app_pages.elements import render; render(db)
elif idx == 4:
    from app_pages.breakdown import render; render(db)
elif idx == 5:
    from app_pages.save_project import render; render(db)