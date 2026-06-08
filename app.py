import streamlit as st
from engine.data_loader import load_cost_database, get_json_mtime
from engine.session_helpers import new_project, PAGES
import os
import httpx

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
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,400&display=swap');

/* ── Design tokens ─────────────────────────────────────────────────────── */
:root {
    --navy:       #0d1b36;
    --navy-soft:  #162242;
    --slate:      #1e3358;
    --gold:       #c8a84b;
    --gold-lt:    #e8cc7a;
    --gold-dim:   rgba(200,168,75,0.15);
    --offwhite:   #f5f4f0;
    --surface:    #ffffff;
    --surface-2:  #faf9f7;
    --mid:        #8a96a8;
    --mid-lt:     #b8c0cc;
    --border:     #e4e0d8;
    --border-lt:  #edeae4;
    --shadow-sm:  0 1px 4px rgba(13,27,54,0.06);
    --shadow-md:  0 4px 16px rgba(13,27,54,0.10);
    --shadow-lg:  0 8px 32px rgba(13,27,54,0.14);
    --radius-sm:  4px;
    --radius:     8px;
    --radius-lg:  12px;
}

/* ── Base ──────────────────────────────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif !important;
    background-color: var(--offwhite) !important;
    color: var(--navy) !important;
    -webkit-font-smoothing: antialiased;
}
h1, h2, h3 {
    font-family: 'DM Serif Display', serif !important;
    font-weight: 400 !important;
    color: var(--navy) !important;
    letter-spacing: -0.01em;
}
p { line-height: 1.65; }

/* ── Main content area ─────────────────────────────────────────────────── */
.main .block-container {
    padding-top: 2rem !important;
    padding-bottom: 3rem !important;
    max-width: 1200px !important;
}

/* ── Sidebar ───────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: var(--navy) !important;
    border-right: 1px solid rgba(200,168,75,0.2) !important;
}
[data-testid="stSidebar"] * { color: #bcc6d8 !important; }
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.08) !important; }

/* Sidebar radio nav — active item */
[data-testid="stSidebar"] label:has(input[type="radio"]:checked) > div:last-child {
    color: var(--gold) !important;
    font-weight: 600 !important;
}
/* Sidebar radio — hover */
[data-testid="stSidebar"] label:hover > div:last-child {
    color: #ffffff !important;
}
/* Tighten sidebar radio spacing */
[data-testid="stSidebar"] [data-testid="stRadio"] > div {
    gap: 0.1rem !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label {
    padding: 0.45rem 0.75rem !important;
    border-radius: var(--radius-sm) !important;
    transition: background 0.15s ease;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
    background: rgba(255,255,255,0.06) !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
    background: rgba(200,168,75,0.12) !important;
}

/* ── Step progress bar ─────────────────────────────────────────────────── */
.step-bar {
    display: flex;
    align-items: stretch;
    gap: 0;
    margin-bottom: 2.5rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
    box-shadow: var(--shadow-sm);
}
.step {
    flex: 1;
    padding: 11px 6px;
    text-align: center;
    font-size: 0.7rem;
    font-weight: 500;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--mid-lt);
    border-right: 1px solid var(--border-lt);
    background: var(--surface);
    transition: background 0.2s;
    position: relative;
}
.step:last-child { border-right: none; }
.step.done {
    background: var(--surface-2);
    color: var(--mid);
}
.step.done::before {
    content: "✓ ";
    color: var(--gold);
    font-size: 0.65rem;
}
.step.active {
    background: var(--navy);
    color: #ffffff;
    font-weight: 600;
    letter-spacing: 0.04em;
}
.step.active::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: var(--gold);
}

/* ── Metrics ───────────────────────────────────────────────────────────── */
[data-testid="metric-container"] {
    background: var(--surface) !important;
    border: 1px solid var(--border-lt) !important;
    border-radius: var(--radius) !important;
    padding: 1.1rem 1.35rem 1rem !important;
    box-shadow: var(--shadow-sm) !important;
    transition: box-shadow 0.2s, border-color 0.2s;
}
[data-testid="metric-container"]:hover {
    box-shadow: var(--shadow-md) !important;
    border-color: var(--border) !important;
}
[data-testid="stMetricValue"] {
    font-family: 'DM Serif Display', serif !important;
    font-size: 1.75rem !important;
    color: var(--navy) !important;
    letter-spacing: -0.02em !important;
    line-height: 1.1 !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.7rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.07em !important;
    text-transform: uppercase !important;
    color: var(--mid) !important;
    margin-bottom: 0.3rem !important;
}
[data-testid="stMetricDelta"] { font-size: 0.8rem !important; }

/* ── Buttons ───────────────────────────────────────────────────────────── */
.stButton > button {
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
    letter-spacing: 0.02em !important;
    border-radius: var(--radius) !important;
    padding: 0.55rem 1.25rem !important;
    transition: all 0.18s ease !important;
    cursor: pointer !important;
}
.stButton > button[kind="primary"] {
    background: var(--navy) !important;
    color: #ffffff !important;
    border: none !important;
    box-shadow: var(--shadow-sm) !important;
}
.stButton > button[kind="primary"]:hover {
    background: var(--navy-soft) !important;
    transform: translateY(-1px) !important;
    box-shadow: var(--shadow-md) !important;
}
.stButton > button[kind="primary"]:active {
    transform: translateY(0) !important;
}
.stButton > button:not([kind="primary"]) {
    background: var(--surface) !important;
    color: var(--navy) !important;
    border: 1px solid var(--border) !important;
}
.stButton > button:not([kind="primary"]):hover {
    border-color: var(--navy) !important;
    background: var(--surface-2) !important;
}

/* ── Inputs ────────────────────────────────────────────────────────────── */
[data-testid="stNumberInput"] input,
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {
    border-radius: var(--radius) !important;
    border-color: var(--border) !important;
    background: var(--surface) !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.9rem !important;
    transition: border-color 0.15s, box-shadow 0.15s !important;
}
[data-testid="stNumberInput"] input:focus,
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
    border-color: var(--navy) !important;
    box-shadow: 0 0 0 3px rgba(13,27,54,0.08) !important;
}
[data-testid="stSelectbox"] > div > div {
    border-radius: var(--radius) !important;
    border-color: var(--border) !important;
    background: var(--surface) !important;
}

/* ── Tables ────────────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border-radius: var(--radius) !important;
    overflow: hidden !important;
    border: 1px solid var(--border-lt) !important;
}

/* ── Expanders ─────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid var(--border-lt) !important;
    border-radius: var(--radius) !important;
    background: var(--surface) !important;
    margin-bottom: 0.35rem !important;
    box-shadow: none !important;
}
[data-testid="stExpander"]:hover {
    border-color: var(--border) !important;
    box-shadow: var(--shadow-sm) !important;
}

/* ── Tabs ──────────────────────────────────────────────────────────────── */
[data-testid="stTabs"] [role="tablist"] {
    border-bottom: 2px solid var(--border) !important;
    gap: 0.25rem !important;
}
[data-testid="stTabs"] [role="tab"] {
    font-size: 0.8rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.04em !important;
    padding: 0.5rem 1rem !important;
    border-radius: var(--radius-sm) var(--radius-sm) 0 0 !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: var(--navy) !important;
    border-bottom: 2px solid var(--navy) !important;
}

/* ── Info / warning / error boxes ──────────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: var(--radius) !important;
    font-size: 0.875rem !important;
}

/* ── Project cards ─────────────────────────────────────────────────────── */
.proj-card {
    background: var(--surface);
    border: 1px solid var(--border-lt);
    border-radius: var(--radius);
    padding: 1.1rem 1.3rem;
    margin-bottom: 0.6rem;
    transition: box-shadow 0.2s, border-color 0.2s;
}
.proj-card:hover {
    box-shadow: var(--shadow-md);
    border-color: var(--border);
}
.proj-name {
    font-family: 'DM Serif Display', serif;
    font-size: 1.05rem;
    color: var(--navy);
    letter-spacing: -0.01em;
}
.proj-meta {
    font-size: 0.78rem;
    color: var(--mid);
    margin-top: 4px;
    line-height: 1.5;
}

/* ── Page titles ───────────────────────────────────────────────────────── */
.page-title {
    font-family: 'DM Serif Display', serif;
    font-size: 2.1rem;
    color: var(--navy);
    margin-bottom: 0.1rem;
    letter-spacing: -0.02em;
    line-height: 1.15;
}
.page-subtitle {
    color: var(--mid);
    font-size: 0.9rem;
    margin-top: 0;
    margin-bottom: 1.75rem;
    line-height: 1.6;
}

/* ── Login card ────────────────────────────────────────────────────────── */
.login-card {
    max-width: 400px;
    margin: 6rem auto;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 2.5rem 2rem;
    box-shadow: var(--shadow-lg);
}

/* ── Download button ───────────────────────────────────────────────────── */
[data-testid="stDownloadButton"] button {
    border-radius: var(--radius) !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
}
</style>
""", unsafe_allow_html=True)

# ── Supabase Auth helpers ──────────────────────────────────────────────────────

def _supabase_creds():
    url = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", "")
    return url, key

def _sign_in(email: str, password: str):
    """Call Supabase Auth to sign in. Returns (user_dict, error_string)."""
    url, key = _supabase_creds()
    try:
        r = httpx.post(
            f"{url}/auth/v1/token?grant_type=password",
            headers={"apikey": key, "Content-Type": "application/json"},
            json={"email": email, "password": password},
            timeout=10,
        )
        data = r.json()
        if r.status_code == 200 and "access_token" in data:
            return data, None
        else:
            msg = data.get("error_description") or data.get("msg") or "Login failed"
            return None, msg
    except Exception as e:
        return None, str(e)

def _sign_up(email: str, password: str):
    """Register a new user. Returns (user_dict, error_string)."""
    url, key = _supabase_creds()
    try:
        r = httpx.post(
            f"{url}/auth/v1/signup",
            headers={"apikey": key, "Content-Type": "application/json"},
            json={"email": email, "password": password},
            timeout=10,
        )
        data = r.json()
        if r.status_code in (200, 201) and data.get("id"):
            return data, None
        else:
            msg = data.get("msg") or data.get("error_description") or "Sign up failed"
            return None, msg
    except Exception as e:
        return None, str(e)

def _get_user_role(user_id: str, access_token: str) -> str:
    """Look up whether this user is 'admin' or 'user'."""
    url, key = _supabase_creds()
    try:
        r = httpx.get(
            f"{url}/rest/v1/user_roles?user_id=eq.{user_id}&select=role",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {access_token}",
            },
            timeout=10,
        )
        rows = r.json()
        if rows:
            return rows[0].get("role", "user")
    except Exception:
        pass
    return "user"

def _reset_password(email: str):
    """Send a password reset email."""
    url, key = _supabase_creds()
    try:
        r = httpx.post(
            f"{url}/auth/v1/recover",
            headers={"apikey": key, "Content-Type": "application/json"},
            json={"email": email},
            timeout=10,
        )
        return r.status_code == 200
    except Exception:
        return False

# ── Session: initialise once ──────────────────────────────────────────────────
if "initialised" not in st.session_state:
    st.session_state.update({
        "authenticated":          False,
        "current_user_email":     "",
        "current_user_id":        "",
        "current_user_role":      "user",   # 'user' or 'admin'
        "access_token":           "",
        "page_idx":               0,
        "project_id":             None,
        "project_name":           "",
        "gia_m2":                 0.0,
        "nia_m2":                 0.0,
        "location":               "",
        "postcode":               "",
        "quartile":               "Median",
        "spec_level":             "Standard",
        "building_type":          "Office",
        "refurb_scope":           "Full Strip Out",
        "net_gross_pct":          0.0,
        "element_areas_m2":       {},
        "breakdown_unit":         "m²",
        "_last_total_cost":       0,
        "postcode_touched":       False,
        "_postcode_error":        "",
        "storeys_above":          0,
        "storeys_below":          0,
        "has_extension":          False,
        "ext_gia_per_floor_m2":   0.0,
        "ext_nia_per_floor_m2":   0.0,
        "ext_new_storeys":        0,
        "ext_new_gia_m2":         0.0,
        "ext_new_nia_m2":         0.0,
        "ext_lifts":              0,
        "ext_stairs":             0,
        "ext_roof_works":         False,
        "ext_structural_storeys": 0,
    })
    st.session_state.initialised = True

# ═════════════════════════════════════════════════════════════════════════════
# LOGIN GATE
# ═════════════════════════════════════════════════════════════════════════════

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
        # Tab between Sign In and Sign Up
        login_tab, signup_tab = st.tabs(["Sign In", "Create Account"])

        with login_tab:
            email_in = st.text_input("Email", key="login_email", placeholder="you@company.com")
            pwd_in   = st.text_input("Password", type="password", key="login_pwd", placeholder="Password")

            if st.button("Sign In", type="primary", use_container_width=True, key="btn_signin"):
                if not email_in or not pwd_in:
                    st.error("Please enter your email and password.")
                else:
                    with st.spinner("Signing in..."):
                        result, err = _sign_in(email_in.strip(), pwd_in)
                    if err:
                        st.error(f"❌ {err}")
                    else:
                        user = result.get("user", {})
                        user_id = user.get("id", "")
                        token   = result.get("access_token", "")
                        role    = _get_user_role(user_id, token)
                        st.session_state.authenticated      = True
                        st.session_state.current_user_email = email_in.strip()
                        st.session_state.current_user_id    = user_id
                        st.session_state.current_user_role  = role
                        st.session_state.access_token       = token
                        st.rerun()

            st.markdown("---")
            forgot_email = st.text_input("Email for password reset", key="forgot_email",
                                          placeholder="you@company.com")
            if st.button("Send Password Reset Email", key="btn_reset"):
                if forgot_email:
                    ok = _reset_password(forgot_email.strip())
                    if ok:
                        st.success("✅ Reset email sent — check your inbox.")
                    else:
                        st.error("Could not send reset email. Check the address.")
                else:
                    st.warning("Enter your email above first.")

        with signup_tab:
            new_email = st.text_input("Email", key="signup_email", placeholder="you@company.com")
            new_pwd   = st.text_input("Password (min 6 characters)", type="password",
                                       key="signup_pwd", placeholder="Choose a password")
            new_pwd2  = st.text_input("Confirm Password", type="password",
                                       key="signup_pwd2", placeholder="Repeat password")

            if st.button("Create Account", type="primary", use_container_width=True, key="btn_signup"):
                if not new_email or not new_pwd:
                    st.error("Please fill in all fields.")
                elif new_pwd != new_pwd2:
                    st.error("Passwords don't match.")
                elif len(new_pwd) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    with st.spinner("Creating account..."):
                        result, err = _sign_up(new_email.strip(), new_pwd)
                    if err:
                        st.error(f"❌ {err}")
                    else:
                        st.success("✅ Account created! You can now sign in.")

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
PAGE_ICONS = ["🏠", "📋", "🏗️", "⚙️", "📊", "💾", "📚", "📥", "🚀"]

# ── Admin pages (only visible to admins) ─────────────────────────────────────
is_admin = st.session_state.get("current_user_role") == "admin"

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

    # Show user email + role badge in sidebar
    role_colour = "#c8a84b" if is_admin else "#8a96a8"
    role_label  = "Admin" if is_admin else "User"
    st.markdown(
        f"<div style='font-size:0.75rem;color:#8a96a8;margin-bottom:4px;'>"
        f"Signed in as</div>"
        f"<div style='font-size:0.8rem;color:#bcc6d8;margin-bottom:4px;'>"
        f"{st.session_state.current_user_email}</div>"
        f"<span style='background:{role_colour};color:#0d1b36;"
        f"font-size:0.65rem;font-weight:700;letter-spacing:0.06em;"
        f"text-transform:uppercase;padding:0.15rem 0.5rem;"
        f"border-radius:4px;'>{role_label}</span>",
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # Build nav — filter admin pages for non-admin users
    if is_admin:
        nav_pages = list(PAGES)
        nav_icons = list(PAGE_ICONS)
    else:
        # Non-admins only see the first 6 workflow pages + Rate Library (idx 6)
        nav_pages = list(PAGES[:7])
        nav_icons = list(PAGE_ICONS[:7])
        
    plain_labels = [f"{nav_icons[i]}  {nav_pages[i]}" for i in range(len(nav_pages))]

    # Clamp page_idx to valid range for this user
    max_idx = len(nav_pages) - 1
    if st.session_state.page_idx > max_idx:
        st.session_state.page_idx = 0

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
        # Clear auth state but keep app initialised
        st.session_state.authenticated      = False
        st.session_state.current_user_email = ""
        st.session_state.current_user_id    = ""
        st.session_state.current_user_role  = "user"
        st.session_state.access_token       = ""
        st.session_state.page_idx           = 0
        st.rerun()

# ── Step progress bar ─────────────────────────────────────────────────────────
def render_step_bar(current: int):
    workflow_pages = PAGES[:6]
    workflow_icons = PAGE_ICONS[:6]
    html = '<div class="step-bar">'
    for i, name in enumerate(workflow_pages):
        cls = "done" if i < current else ("active" if i == current else "")
        html += f'<div class="step {cls}">{workflow_icons[i]} {name}</div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

if st.session_state.page_idx < 6:
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
elif idx == 6:
    from app_pages.rate_library import render; render()
elif idx == 7 and is_admin:
    from app_pages.admin_rate_submission import render; render()
elif idx == 8 and is_admin:
    from app_pages.admin_publish_rates import render; render()
else:
    st.warning("Page not found or access denied.")