"""
app.py  –  NexusID Portal  (Streamlit)
Three role-based views: Employee | Manager | IT Admin
Run: streamlit run app.py
"""

import streamlit as st
import requests

API = "http://127.0.0.1:8000"

# ── Global constants ──────────────────────────────────────────
BIRTHRIGHT = {
    "Engineering": ["GitHub_Repo_Access", "Slack_Engineering_Channel", "AWS_Sandbox"],
    "Sales":       ["Salesforce_Read_Only", "Slack_Sales_Channel"],
    "HR":          ["Workday_Basic", "Slack_General"],
}

RESOURCE_MAP = {
    "salesforce": "Salesforce_Read_Only",
    "github":     "GitHub_Repo_Access",
    "aws root":   "AWS_Root",
    "aws":        "AWS_Sandbox",
    "slack":      "Slack_General",
    "workday":    "Workday_Basic",
}

# ── Page config ───────────────────────────────────────────────
st.set_page_config(
    page_title="NexusID Portal",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styling ───────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }

[data-testid="stSidebar"] { background:#0a0a0f; border-right:1px solid #1e1e2e; }
[data-testid="stSidebar"] * { color:#c9d1d9 !important; }

.stApp { background:#0d0d14; color:#e6edf3; }

.nx-card {
    background:#161622; border:1px solid #21213a;
    border-radius:8px; padding:20px 24px; margin-bottom:16px;
}
.nx-card-accent {
    background:#161622; border-left:3px solid #00d4aa;
    border-radius:0 8px 8px 0; padding:16px 20px; margin-bottom:12px;
}
.nx-metric {
    background:#0f0f1a; border:1px solid #1e1e30;
    border-radius:6px; padding:16px; text-align:center; margin-bottom:8px;
}
.nx-metric .val {
    font-family:'IBM Plex Mono',monospace; font-size:32px;
    font-weight:600; color:#00d4aa;
}
.nx-metric .lbl {
    font-size:11px; color:#8b949e; text-transform:uppercase;
    letter-spacing:0.1em; margin-top:4px;
}
.badge-active   { background:#0d3a2e;color:#00d4aa;border:1px solid #00d4aa33;padding:2px 10px;border-radius:12px;font-size:12px;font-family:monospace; }
.badge-inactive { background:#3a0d0d;color:#f85149;border:1px solid #f8514933;padding:2px 10px;border-radius:12px;font-size:12px;font-family:monospace; }
.badge-pending  { background:#3a2d0d;color:#e3b341;border:1px solid #e3b34133;padding:2px 10px;border-radius:12px;font-size:12px;font-family:monospace; }
.nx-header {
    font-family:'IBM Plex Mono',monospace; font-size:11px;
    letter-spacing:0.15em; text-transform:uppercase; color:#8b949e;
    margin-bottom:16px; padding-bottom:8px; border-bottom:1px solid #21213a;
}
.nx-title { font-size:24px; font-weight:600; color:#e6edf3; margin-bottom:4px; }
.nx-sub   { font-size:13px; color:#8b949e; margin-bottom:24px; }
.nx-table { width:100%; border-collapse:collapse; font-size:13px; }
.nx-table th {
    background:#0f0f1a; color:#8b949e; font-family:'IBM Plex Mono',monospace;
    font-size:11px; letter-spacing:0.08em; text-transform:uppercase;
    padding:10px 14px; text-align:left; border-bottom:1px solid #21213a;
}
.nx-table td { padding:10px 14px; border-bottom:1px solid #1a1a28; color:#c9d1d9; }
.nx-table tr:hover td { background:#1a1a28; }
div.stButton > button {
    background:#161622; color:#00d4aa; border:1px solid #00d4aa44;
    border-radius:6px; font-family:'IBM Plex Mono',monospace;
    font-size:12px; letter-spacing:0.05em; padding:8px 20px;
}
div.stButton > button:hover { background:#00d4aa15; border-color:#00d4aa; }
div.stButton > button[kind="primary"] { background:#00d4aa20; border-color:#00d4aa; color:#00d4aa; }
div[data-baseweb="input"] input,
div[data-baseweb="select"] div,
div[data-baseweb="textarea"] textarea {
    background:#0f0f1a !important; border-color:#21213a !important; color:#e6edf3 !important;
}
hr { border-color:#21213a; }
.chat-msg-user {
    background:#161d2b; border:1px solid #1e2d45;
    border-radius:12px 12px 2px 12px; padding:12px 16px;
    margin:8px 0; margin-left:20%; color:#79c0ff; font-size:14px;
}
.chat-msg-bot {
    background:#161622; border:1px solid #21213a;
    border-radius:12px 12px 12px 2px; padding:12px 16px;
    margin:8px 0; margin-right:20%; color:#c9d1d9; font-size:14px;
}
.chat-label {
    font-family:'IBM Plex Mono',monospace; font-size:10px;
    color:#8b949e; margin-bottom:4px; letter-spacing:0.1em;
}
</style>
""", unsafe_allow_html=True)


# ── API helpers ───────────────────────────────────────────────
def api_get(path):
    try:
        r = requests.get(f"{API}{path}", timeout=5)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def api_post(path, data=None, params=None):
    try:
        if data is not None:
            r = requests.post(f"{API}{path}", json=data, params=params, timeout=5)
        else:
            r = requests.post(f"{API}{path}", params=params, timeout=5)
        return r.status_code, r.json()
    except Exception as e:
        return 500, {"error": str(e)}

def api_patch(path, params=None):
    try:
        r = requests.patch(f"{API}{path}", params=params, timeout=5)
        return r.status_code, r.json()
    except Exception as e:
        return 500, {"error": str(e)}

def status_badge(status):
    cls = {"Active": "badge-active", "Inactive": "badge-inactive"}.get(status, "badge-pending")
    return f'<span class="{cls}">{status}</span>'


def _build_provision_html(items):
    """Build provisioned resources list — no backslash in f-string needed."""
    return "".join(
        "<div style='margin-top:4px;font-family:IBM Plex Mono,monospace;"
        "font-size:12px;color:#e6edf3'>&#10003; &nbsp;" + r + "</div>"
        for r in items
    )


# ── Live user fetch — source of truth is the API ──────────────
def get_live_users():
    """
    Always fetch from GET /users so hired users persist across
    page refreshes and appear in all three views immediately.
    Falls back to seed list if API is unreachable.
    """
    data = api_get("/users")
    if isinstance(data, list) and len(data) > 0:
        return data
    # Fallback if API is down
    return [
        {"id":1,"username":"dhruv","department":"Engineering","status":"Active",
         "job_title":"Backend Engineer","email":"dhruv@company.com","manager_id":None},
        {"id":2,"username":"priya","department":"Sales","status":"Active",
         "job_title":"Account Executive","email":"priya@company.com","manager_id":1},
        {"id":3,"username":"amit","department":"HR","status":"Active",
         "job_title":"HR Generalist","email":"amit@company.com","manager_id":1},
    ]


# ── Session state init ────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "selected_role" not in st.session_state:
    st.session_state.selected_role = None


# ══════════════════════════════════════════════════════════════
#  LANDING PAGE — shown until a role is selected
# ══════════════════════════════════════════════════════════════
if st.session_state.selected_role is None:
    st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style='text-align:center;padding:60px 0 40px'>
        <div style='font-family:IBM Plex Mono,monospace;font-size:42px;
                    font-weight:600;letter-spacing:0.04em;margin-bottom:8px'>
            <span style='color:#00d4aa'>NEXUS</span><span style='color:#e6edf3'>ID</span>
        </div>
        <div style='font-size:15px;color:#8b949e;letter-spacing:0.12em;
                    font-family:IBM Plex Mono,monospace;text-transform:uppercase;
                    margin-bottom:8px'>
            Identity Access Management
        </div>
        <div style='font-size:13px;color:#8b949e;max-width:520px;
                    margin:0 auto;line-height:1.7'>
            Automates the full Joiner–Mover–Leaver lifecycle with simulated IAM integrations,
            approval workflows, JIT access, and SHA-256 audit integrity.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Role cards ────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)

    ROLES = [
        {
            "col"   : col1,
            "key"   : "👤  Employee",
            "icon"  : "👤",
            "title" : "Employee",
            "desc"  : "View your access, request resources, and request JIT elevated access for sensitive tasks.",
            "tags"  : ["Access requests", "JIT access", "Chatbot"],
            "color" : "#00d4aa",
            "bg"    : "#0d3a2e",
            "border": "#00d4aa44",
        },
        {
            "col"   : col2,
            "key"   : "✅  Manager",
            "icon"  : "✅",
            "title" : "Manager",
            "desc"  : "Approve transfer requests, review team access, and initiate offboarding for your direct reports.",
            "tags"  : ["Approvals", "Access review", "Leaver requests"],
            "color" : "#79c0ff",
            "bg"    : "#0d1e3a",
            "border": "#79c0ff44",
        },
        {
            "col"   : col3,
            "key"   : "🛡️  IT Admin",
            "icon"  : "🛡️",
            "title" : "IT Admin",
            "desc"  : "Full lifecycle management — onboard, audit, integrity checks, JIT monitor, and orphan scanning.",
            "tags"  : ["Onboarding", "Audit trail", "Orphan scanner"],
            "color" : "#e3b341",
            "bg"    : "#3a2d0d",
            "border": "#e3b34144",
        },
    ]

    for role in ROLES:
        tags_html = "".join([
            f"<span style='background:{role['bg']};color:{role['color']};border:1px solid {role['border']};"
            f"padding:2px 10px;border-radius:12px;font-size:11px;font-family:IBM Plex Mono,monospace;"
            f"margin-right:6px'>{t}</span>"
            for t in role["tags"]
        ])
        role["col"].markdown(f"""
        <div style='background:#161622;border:1px solid {role["border"]};border-radius:12px;
                    padding:28px 24px;text-align:center;min-height:240px;
                    transition:border-color 0.2s'>
            <div style='font-size:32px;margin-bottom:12px'>{role["icon"]}</div>
            <div style='font-size:18px;font-weight:600;color:#e6edf3;margin-bottom:10px'>
                {role["title"]}
            </div>
            <div style='font-size:13px;color:#8b949e;line-height:1.6;margin-bottom:16px'>
                {role["desc"]}
            </div>
            <div style='margin-bottom:4px'>{tags_html}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)
        if role["col"].button(
            f"Enter as {role['title']}",
            key=f"role_{role['key']}",
            use_container_width=True,
        ):
            st.session_state.selected_role = role["key"]
            st.rerun()

    # ── Stats bar ─────────────────────────────────────────────
    st.markdown("<div style='margin-top:48px'></div>", unsafe_allow_html=True)
    stats_data = api_get("/audit-log/verify")
    users_data = api_get("/users")
    total_users = len(users_data) if isinstance(users_data, list) else 0
    total_logs  = stats_data.get("total", 0) if isinstance(stats_data, dict) else 0
    jit_data    = api_get("/jit/grants")
    total_jit   = len(jit_data) if isinstance(jit_data, list) else 0

    s1, s2, s3, s4 = st.columns(4)
    for col, val, lbl in [
        (s1, total_users, "Users managed"),
        (s2, total_logs,  "Audit entries"),
        (s3, total_jit,   "JIT grants issued"),
        (s4, "SHA-256",   "Audit integrity"),
    ]:
        col.markdown(f"""
        <div style='text-align:center;padding:16px;background:#161622;
                    border:1px solid #21213a;border-radius:8px'>
            <div style='font-family:IBM Plex Mono,monospace;font-size:24px;
                        font-weight:600;color:#00d4aa'>{val}</div>
            <div style='font-size:11px;color:#8b949e;text-transform:uppercase;
                        letter-spacing:0.1em;margin-top:4px'>{lbl}</div>
        </div>
        """, unsafe_allow_html=True)

    st.stop()  # Don't render the rest of the page

# ── Role is selected — show sidebar and portal ────────────────
with st.sidebar:
    st.markdown("""
    <div style='padding:20px 0 24px'>
        <div style='font-family:IBM Plex Mono,monospace;font-size:18px;
                    font-weight:600;color:#00d4aa;letter-spacing:0.05em'>
            NEXUS<span style='color:#e6edf3'>ID</span>
        </div>
        <div style='font-size:11px;color:#8b949e;margin-top:4px;
                    font-family:IBM Plex Mono,monospace;letter-spacing:0.1em'>
            IDENTITY ACCESS MANAGEMENT
        </div>
    </div>
    """, unsafe_allow_html=True)

    view = st.radio("view", ["👤  Employee", "✅  Manager", "🛡️  IT Admin"],
                    index=["👤  Employee", "✅  Manager", "🛡️  IT Admin"].index(
                        st.session_state.selected_role
                    ),
                    label_visibility="collapsed")
    st.session_state.selected_role = view
    st.markdown("---")
    st.markdown("""
    <div style='font-size:11px;color:#8b949e;font-family:IBM Plex Mono,monospace;line-height:1.8'>
        v0.8.0 — NexusID<br>SQLite · IsolationForest<br>SHA-256 Audit Integrity
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<div style='margin-top:16px'></div>", unsafe_allow_html=True)
    if st.button("Back to home", use_container_width=True):
        st.session_state.selected_role = None
        st.rerun()


# ── Fetch users fresh on every render ────────────────────────
ALL_USERS = get_live_users()
user_map  = {u["id"]: u for u in ALL_USERS}

# ── System health check ───────────────────────────────────────
_health = api_get("/")
if isinstance(_health, dict) and "error" in _health:
    st.markdown("""
    <div style='background:#3a0d0d;border:1px solid #f8514933;border-radius:8px;
                padding:12px 20px;margin-bottom:16px;display:flex;align-items:center;gap:12px'>
        <div style='width:10px;height:10px;background:#f85149;border-radius:50%;flex-shrink:0'></div>
        <div style='font-size:13px;color:#f85149;font-family:IBM Plex Mono,monospace'>
            API OFFLINE — uvicorn is not running.
            Start it with: <code style='background:#0f0f1a;padding:2px 8px;border-radius:4px'>
            uvicorn main:app --reload</code>
        </div>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown(f"""
    <div style='background:#0d3a2e;border:1px solid #00d4aa33;border-radius:8px;
                padding:10px 20px;margin-bottom:16px;display:flex;align-items:center;gap:12px'>
        <div style='width:10px;height:10px;background:#00d4aa;border-radius:50%;
                    flex-shrink:0;animation:pulse 2s infinite'></div>
        <div style='font-size:12px;color:#00d4aa;font-family:IBM Plex Mono,monospace'>
            API ONLINE &nbsp;·&nbsp; NexusID {_health.get("version","")}&nbsp;·&nbsp;
            {_health.get("storage","")}
        </div>
    </div>
    <style>@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.4}}}}</style>
    """, unsafe_allow_html=True)



# ══════════════════════════════════════════════════════════════
#  VIEW 1 — EMPLOYEE
# ══════════════════════════════════════════════════════════════
if "Employee" in view:
    st.markdown('<div class="nx-title">My Access Portal</div>', unsafe_allow_html=True)
    st.markdown('<div class="nx-sub">View your current access and request new resources</div>', unsafe_allow_html=True)
    
    def clear_chat_history():
        st.session_state.chat_history = []

    user_options = {u["id"]: f"{u['username']} ({u['department']})" for u in ALL_USERS}
    user_id = st.selectbox("Select your profile", list(user_options.keys()),
                            format_func=lambda x: user_options[x],
                            on_change=clear_chat_history)
    user = user_map[user_id]

    if user["status"] == "Inactive":
        st.error("Your account has been deactivated. Please contact your IT Admin.")
        st.stop()

    tab1, tab2, tab3 = st.tabs(["My Access", "Request Access", "JIT Access"])

    # ── Tab 1: My Access ──────────────────────────────────────
    with tab1:
        col1, col2 = st.columns([1, 2])

        with col1:
            st.markdown('<div class="nx-header">Profile</div>', unsafe_allow_html=True)
            st.markdown(f"""
            <div class="nx-card">
                <div style='font-size:20px;font-weight:600;color:#e6edf3;margin-bottom:4px'>{user['username']}</div>
                <div style='font-size:13px;color:#8b949e;margin-bottom:12px'>{user['job_title']}</div>
                <div style='font-size:12px;color:#8b949e;margin-bottom:6px'>
                    <span style='color:#00d4aa'>dept &nbsp;</span>{user['department']}
                </div>
                <div style='font-size:12px;color:#8b949e;margin-bottom:12px'>
                    <span style='color:#00d4aa'>email</span> {user['email']}
                </div>
                {status_badge(user['status'])}
            </div>
            """, unsafe_allow_html=True)

            st.markdown('<div class="nx-header" style="margin-top:16px">Current Access</div>', unsafe_allow_html=True)
            entitlements = BIRTHRIGHT.get(user["department"], [])
            if entitlements:
                for res in entitlements:
                    st.markdown(f"""
                    <div class="nx-card-accent">
                        <div style='font-size:13px;color:#e6edf3;font-family:IBM Plex Mono,monospace'>{res}</div>
                        <div style='font-size:11px;color:#8b949e;margin-top:2px'>Active · Birthright</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown('<div class="nx-card"><div style="color:#8b949e;font-size:13px">No defined policy.</div></div>', unsafe_allow_html=True)

        with col2:
            st.markdown('<div class="nx-header">Access Request Assistant</div>', unsafe_allow_html=True)
            if not st.session_state.chat_history:
                st.session_state.chat_history = [
                    {"role": "bot", "text": f"Hi {user['username']}! I can help you request access to resources. What do you need?"}
                ]
            for msg in st.session_state.chat_history:
                if msg["role"] == "user":
                    st.markdown(f'<div class="chat-label" style="text-align:right">YOU</div>'
                                f'<div class="chat-msg-user">{msg["text"]}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="chat-label">NEXUS</div>'
                                f'<div class="chat-msg-bot">{msg["text"]}</div>', unsafe_allow_html=True)

            st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)
            with st.form("chat_form", clear_on_submit=True):
                col_i, col_b = st.columns([4, 1])
                user_input = col_i.text_input("message", placeholder="e.g. I need access to Salesforce...",
                                               label_visibility="collapsed")
                submitted = col_b.form_submit_button("Send")

            if submitted and user_input:
                st.session_state.chat_history.append({"role": "user", "text": user_input})
                text_lower       = user_input.lower()
                matched_resource = next((v for k, v in RESOURCE_MAP.items() if k in text_lower), None)
                if matched_resource:
                    code, resp = api_post("/request-access", {
                        "user_id"      : user_id,
                        "resource_name": matched_resource,
                        "justification": user_input,
                        "request_type" : "Grant",
                    })
                    status = resp.get("status", "ERROR")
                    risk   = resp.get("risk_score", "N/A")
                    level  = resp.get("risk_level", "")
                    if status == "APPROVED":
                        bot_reply = f"Access to <b>{matched_resource}</b> approved. Risk score: {risk} ({level})."
                    elif status == "FLAGGED":
                        bot_reply = f"<b>{matched_resource}</b> flagged for manager review. Risk: {risk} ({level})."
                    elif status == "BLOCKED":
                        bot_reply = f"<b>{matched_resource}</b> blocked. Risk: {risk} ({level}). Contact IT Admin if needed."
                    else:
                        bot_reply = f"Something went wrong: {resp.get('detail', str(resp))}"
                else:
                    bot_reply = "I can help with: GitHub, Salesforce, AWS, Slack, or Workday. Try: <i>'I need access to GitHub'</i>"
                st.session_state.chat_history.append({"role": "bot", "text": bot_reply})
                st.rerun()

    # ── Tab 2: Request Access (standalone form) ───────────────
    with tab2:
        st.markdown('<div class="nx-header">Request access to a resource</div>', unsafe_allow_html=True)
        with st.form("access_form"):
            req_resource = st.selectbox("Resource", list(RESOURCE_MAP.values()) + ["AWS_Root"])
            req_just     = st.text_input("Justification", placeholder="e.g. Need for Q3 project")
            req_submit   = st.form_submit_button("Submit Request")
        if req_submit:
            code, resp = api_post("/request-access", {
                "user_id"      : user_id,
                "resource_name": req_resource,
                "justification": req_just,
                "request_type" : "Grant",
            })
            status = resp.get("status", "ERROR")
            risk   = resp.get("risk_score", "N/A")
            level  = resp.get("risk_level", "")
            if status == "APPROVED":
                st.success(f"Approved. Risk score: {risk} ({level})")
            elif status == "BLOCKED":
                st.error(f"Blocked — anomaly detected. Risk: {risk} ({level})")
            elif status == "FLAGGED":
                st.warning(f"Flagged for manager review. Risk: {risk} ({level})")
            else:
                st.error(resp.get("detail", str(resp)))

    # ── Tab 3: JIT Access ─────────────────────────────────────
    with tab3:
        st.markdown('<div class="nx-header">Just-in-time elevated access</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="nx-card" style="margin-bottom:20px">
            <div style='font-size:13px;color:#8b949e;line-height:1.6'>
                Request temporary access to sensitive resources. Access
                <span style='color:#f85149;font-weight:600'>auto-revokes</span>
                when the timer expires. Follows Zero Trust: no standing privileges.
            </div>
        </div>
        """, unsafe_allow_html=True)

        with st.form("jit_form"):
            jit_resource = st.selectbox("Resource", [
                "AWS_Root", "GitHub_Repo_Access", "Salesforce_Read_Only",
                "Workday_Basic", "AWS_Sandbox",
            ])
            jit_duration = st.slider("Duration (minutes)", min_value=1, max_value=120, value=30, step=1)
            jit_just     = st.text_input("Justification", placeholder="e.g. Hotfix deploy to production")
            jit_submit   = st.form_submit_button("Request JIT Access")

        if jit_submit:
            if not jit_just:
                st.warning("Please provide a justification.")
            else:
                code, resp = api_post("/jit/request", params={
                    "user_id"         : user_id,
                    "resource_name"   : jit_resource,
                    "justification"   : jit_just,
                    "duration_minutes": jit_duration,
                })
                if code == 200:
                    st.success(f"JIT access granted to {jit_resource}!")
                    st.markdown(f"""
                    <div class="nx-card-accent">
                        <div style='font-family:IBM Plex Mono,monospace;font-size:12px;
                                    color:#00d4aa;margin-bottom:8px'>JIT GRANT ACTIVE</div>
                        <div style='font-size:13px;color:#8b949e'>
                            Resource: <span style='color:#e6edf3'>{resp.get('resource')}</span>
                            &nbsp;·&nbsp; Expires in:
                            <span style='color:#e3b341'>{resp.get('duration_minutes')} min</span>
                        </div>
                        <div style='font-size:12px;color:#8b949e;margin-top:4px'>
                            Risk: <span style='color:#e6edf3'>{resp.get('risk_score')}</span>
                            ({resp.get('risk_level')})
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    st.rerun()
                else:
                    st.error(resp.get("detail", "Error"))

        st.markdown('<div class="nx-header" style="margin-top:24px">Active JIT grants</div>', unsafe_allow_html=True)
        if st.button("Refresh", key="refresh_jit"):
            st.rerun()

        grants = api_get("/jit/grants")
        if isinstance(grants, list):
            my_grants = [g for g in grants if g["user_id"] == user_id]
            active    = [g for g in my_grants if g["status"] == "ACTIVE"]
            past      = [g for g in my_grants if g["status"] != "ACTIVE"]

            if not active:
                st.markdown('<div class="nx-card" style="text-align:center;padding:30px"><div style="color:#8b949e;font-size:13px">No active JIT grants</div></div>', unsafe_allow_html=True)
            else:
                for g in active:
                    secs      = g.get("seconds_remaining", 0)
                    mins      = secs // 60
                    secs_rem  = secs % 60
                    pct       = max(0, min(100, int(secs / (g["duration_minutes"] * 60) * 100))) if g["duration_minutes"] > 0 else 0
                    bar_color = "#00d4aa" if pct > 50 else "#e3b341" if pct > 20 else "#f85149"
                    col1, col2 = st.columns([4, 1])
                    col1.markdown(f"""
                    <div class="nx-card" style="border-left:3px solid {bar_color}">
                        <div style='display:flex;justify-content:space-between;align-items:center'>
                            <div>
                                <div style='font-size:14px;font-weight:600;color:#e6edf3'>{g['resource_name']}</div>
                                <div style='font-size:12px;color:#8b949e;margin-top:4px'>{g['justification']}</div>
                            </div>
                            <div style='text-align:right'>
                                <div style='font-family:IBM Plex Mono,monospace;font-size:20px;font-weight:600;color:{bar_color}'>{mins:02d}:{secs_rem:02d}</div>
                                <div style='font-size:11px;color:#8b949e'>remaining</div>
                            </div>
                        </div>
                        <div style='margin-top:12px;background:#0f0f1a;border-radius:4px;height:4px;overflow:hidden'>
                            <div style='width:{pct}%;height:100%;background:{bar_color};border-radius:4px'></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    if col2.button("Revoke", key=f"revoke_jit_{g['id']}"):
                        code, resp = api_post(f"/jit/{g['id']}/revoke")
                        if code == 200:
                            st.success("JIT grant revoked.")
                            st.rerun()
                        else:
                            st.error(resp.get("detail", "Error"))

            if past:
                st.markdown('<div class="nx-header" style="margin-top:16px">Past grants</div>', unsafe_allow_html=True)
                for g in past:
                    sc = "#f85149" if g["status"] == "EXPIRED" else "#e3b341"
                    st.markdown(f'<div class="nx-card" style="opacity:0.6;border-left:3px solid {sc}"><div style="font-size:13px;color:#8b949e;font-family:IBM Plex Mono,monospace">{g["resource_name"]} &nbsp;·&nbsp; <span style="color:{sc}">{g["status"]}</span> &nbsp;·&nbsp; {g["granted_at"][:16].replace("T"," ")}</div></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
#  VIEW 2 — MANAGER
# ══════════════════════════════════════════════════════════════
elif "Manager" in view:
    st.markdown('<div class="nx-title">Manager Portal</div>', unsafe_allow_html=True)
    st.markdown('<div class="nx-sub">Approve access requests · View your team</div>', unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["✅  Pending Approvals", "👥  My Team", "🔄  Request Transfer", "🚪  Initiate Leaver", "📋  Access Review"])

    # ── Tab 1: Approvals ──────────────────────────────────────
    with tab1:
        st.markdown('<div class="nx-header">Transfer requests awaiting approval</div>', unsafe_allow_html=True)

        col_ref, col_info = st.columns([1, 5])
        if col_ref.button("Refresh", key="refresh_approvals"):
            st.rerun()

        transfers = api_get("/transfers/pending")

        if isinstance(transfers, dict) and "error" in transfers:
            st.error(f"Could not reach API — is uvicorn running? {transfers['error']}")
        elif not isinstance(transfers, list):
            st.error("Unexpected response from API.")
        else:
            pending = [t for t in transfers
                       if isinstance(t, dict) and t.get("status") == "PENDING_APPROVAL"]

            col_info.markdown(
                f"<span style='font-size:12px;color:#8b949e'>{len(pending)} pending · "
                f"{len(transfers)} total requests</span>",
                unsafe_allow_html=True
            )

            if not pending:
                st.markdown("""
                <div class="nx-card" style="text-align:center;padding:40px">
                    <div style='font-size:32px;margin-bottom:8px'>✓</div>
                    <div style='color:#8b949e;font-size:14px'>No pending approvals</div>
                    <div style='color:#8b949e;font-size:12px;margin-top:8px'>
                        Use Manager → Request Transfer to create one
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                for t in pending:
                    requester = user_map.get(t["user_id"], {})
                    name      = requester.get("username", f"User {t['user_id']}")
                    st.markdown(f"""
                    <div class="nx-card">
                        <div style='font-size:14px;font-weight:600;color:#e6edf3'>
                            {name} — Transfer Request
                        </div>
                        <div style='font-size:12px;color:#8b949e;margin-top:4px;
                                    font-family:IBM Plex Mono,monospace'>
                            {t['old_department']} → {t['new_department']}
                        </div>
                        <div style='font-size:11px;color:#8b949e;margin-top:6px'>
                            Token: {t['token'][:16]}... · Requested: {t['created_at'][:10]}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    col_a, col_r, _ = st.columns([1, 1, 4])
                    with col_a:
                        if st.button("✅ Approve", key=f"approve_{t['token']}"):
                            code, resp = api_post(
                                f"/transfer/{t['token']}/approve",
                                params={"manager_id": 1}
                            )
                            if code == 200:
                                st.success(f"Approved! Granted: {resp.get('granted')} | Revoked: {resp.get('revoked')}")
                                st.rerun()
                            else:
                                st.error(str(resp.get("detail", resp)))
                    with col_r:
                        if st.button("❌ Reject", key=f"reject_{t['token']}"):
                            code, resp = api_post(
                                f"/transfer/{t['token']}/reject",
                                params={"manager_id": 1, "reason": "Rejected by manager"}
                            )
                            if code == 200:
                                st.warning(f"Rejected. {resp.get('note')}")
                                st.rerun()
                            else:
                                st.error(str(resp.get("detail", resp)))

    # ── Tab 2: My team ────────────────────────────────────────
    with tab2:
        st.markdown('<div class="nx-header">Direct reports</div>', unsafe_allow_html=True)

        # Pull from live API — includes newly hired users under this manager
        team = [u for u in ALL_USERS if u.get("manager_id") == 1]

        if not team:
            st.info("No direct reports found.")
        else:
            for member in team:
                entitlements = [] if member["status"] == "Inactive" else BIRTHRIGHT.get(member["department"], [])
                with st.expander(f"{member['username']}  ·  {member['department']}  ·  {member['job_title']}"):
                    col1, col2 = st.columns(2)
                    col1.markdown(f"**Status:** {member['status']}")
                    col1.markdown(f"**User ID:** {member['id']}")
                    col1.markdown(f"**Email:** {member['email']}")
                    col2.markdown("**Current Access:**")
                    if entitlements:
                        for e in entitlements:
                            col2.markdown(f"- `{e}`")
                    else:
                        col2.markdown("_No active entitlements_")

    # ── Tab 3: Request transfer ───────────────────────────────
    with tab3:
        st.markdown('<div class="nx-header">Request a department transfer</div>', unsafe_allow_html=True)

        # Active users only, pulled from live API
        active_users  = [u for u in ALL_USERS if u["status"] == "Active"]
        transfer_opts = {u["id"]: f"{u['username']} ({u['department']})" for u in active_users}

        with st.form("transfer_form"):
            t_user_id  = st.selectbox("Employee", list(transfer_opts.keys()),
                                       format_func=lambda x: transfer_opts[x])
            t_new_dept = st.selectbox("Transfer to", ["Engineering", "Sales", "HR", "Marketing"])
            t_submit   = st.form_submit_button("Request Transfer")

        if t_submit:
            code, resp = api_patch(f"/users/{t_user_id}/transfer",
                                   params={"new_department": t_new_dept})
            if code == 200:
                st.success("Transfer request created and persisted to SQLite!")
                st.markdown(f"""
                <div class="nx-card-accent" style="margin-top:12px">
                    <div style='font-family:IBM Plex Mono,monospace;font-size:12px;color:#00d4aa'>
                        APPROVAL TOKEN
                    </div>
                    <div style='font-family:IBM Plex Mono,monospace;font-size:13px;
                                color:#e6edf3;margin-top:6px;word-break:break-all'>
                        {resp.get('approval_token')}
                    </div>
                    <div style='font-size:12px;color:#8b949e;margin-top:8px'>
                        Survives server restarts — stored in SQLite
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.error(str(resp.get("detail", resp)))


    # ── Tab 4: Initiate Leaver ────────────────────────────────
    with tab4:
        st.markdown('<div class="nx-header">Initiate leaver request for direct report</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="nx-card" style="margin-bottom:20px">
            <div style='font-size:13px;color:#8b949e;line-height:1.6'>
                When a team member resigns or is terminated, submit a leaver request here.
                This immediately revokes all their access and logs the termination
                with you as the initiating actor — no need to contact IT Admin separately.
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Only show active direct reports
        my_team_active = [u for u in ALL_USERS
                          if u.get("manager_id") == 1 and u["status"] == "Active"]

        if not my_team_active:
            st.markdown("""
            <div class="nx-card" style="text-align:center;padding:30px">
                <div style='color:#8b949e;font-size:13px'>No active direct reports to offboard.</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            with st.form("leaver_form"):
                team_opts  = {u["id"]: f"{u['username']} ({u['department']})"
                              for u in my_team_active}
                leaver_uid = st.selectbox("Select team member",
                                           list(team_opts.keys()),
                                           format_func=lambda x: team_opts[x])
                leaver_reason = st.selectbox("Reason", [
                    "Employee resignation",
                    "End of contract",
                    "Mutual termination",
                    "Performance-based termination",
                    "Redundancy",
                ])
                st.markdown("""
                <div style='background:#3a0d0d;border:1px solid #f8514933;
                             border-radius:6px;padding:12px 16px;margin-top:8px'>
                    <div style='font-size:12px;color:#f85149;font-family:IBM Plex Mono,monospace'>
                        WARNING — This action immediately revokes all access.
                        It cannot be undone without re-hiring the user.
                    </div>
                </div>
                """, unsafe_allow_html=True)
                leaver_submit = st.form_submit_button("Confirm Leaver Request", type="primary")

            if leaver_submit:
                selected_user = next(u for u in my_team_active if u["id"] == leaver_uid)
                with st.spinner(f"Revoking all access for {selected_user['username']}..."):
                    code, resp = api_post(
                        f"/users/{leaver_uid}/terminate-request",
                        params={"manager_id": 1, "reason": leaver_reason}
                    )
                if code == 200:
                    st.success(f"{selected_user['username']} has been offboarded.")
                    st.markdown(f"""
                    <div class="nx-card" style="border-left:3px solid #f85149;margin-top:12px">
                        <div style='font-family:IBM Plex Mono,monospace;font-size:12px;
                                    color:#f85149;margin-bottom:8px'>LEAVER EVENT COMPLETE</div>
                        <div style='font-size:13px;color:#8b949e'>
                            User &nbsp;<span style='color:#e6edf3'>{resp.get("username")}</span>
                            &nbsp;·&nbsp; Status &nbsp;
                            <span style='color:#f85149'>{resp.get("status")}</span>
                            &nbsp;·&nbsp; Triggered by &nbsp;
                            <span style='color:#e6edf3'>Manager</span>
                        </div>
                        <div style='font-size:13px;color:#8b949e;margin-top:4px'>
                            Revoked: <span style='color:#e6edf3'>
                                {", ".join(resp.get("revoked", []))}
                            </span>
                        </div>
                        <div style='font-size:12px;color:#8b949e;margin-top:4px'>
                            Reason: {resp.get("reason")}
                            &nbsp;·&nbsp; Audit entries: {resp.get("audit_entries")}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.error(resp.get("detail", str(resp)))


    # ── Tab 5: Access Review ──────────────────────────────────
    with tab5:
        st.markdown('<div class="nx-header">Periodic access review — certify your team</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="nx-card" style="margin-bottom:20px">
            <div style='font-size:13px;color:#8b949e;line-height:1.6'>
                Review and certify that each team member still needs their current access.
                Prevents <span style='color:#e3b341;font-weight:600'>access creep</span>
                — permissions that accumulate silently over time.
                Uncertified access is flagged for IT Admin review.
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_days2, col_run2, col_clear2, _ = st.columns([1, 1, 1, 3])
        review_days = col_days2.number_input("Review window (days)", min_value=1, max_value=365, value=90)

        if col_run2.button("Load Review", type="primary"):
            with st.spinner("Loading access review..."):
                st.session_state.access_review_result = api_get(f"/access-review?review_days={review_days}")

        if col_clear2.button("Clear"):
            st.session_state.pop("access_review_result", None)
            st.rerun()

        result = st.session_state.get("access_review_result")

        if result is not None:
            if isinstance(result, dict) and "error" in result:
                st.error(f"API error: {result['error']}")
            else:
                due        = result.get("due", [])
                up_to_date = result.get("up_to_date", [])

                c1, c2 = st.columns(2)
                due_color = "#f85149" if due else "#00d4aa"
                c1.markdown(f"""<div class="nx-metric">
                    <div class="val" style="color:{due_color}">{len(due)}</div>
                    <div class="lbl">Require review</div></div>""", unsafe_allow_html=True)
                c2.markdown(f"""<div class="nx-metric">
                    <div class="val">{len(up_to_date)}</div>
                    <div class="lbl">Up to date</div></div>""", unsafe_allow_html=True)

                if not due:
                    st.markdown("""
                    <div class="nx-card" style="text-align:center;padding:30px;border-left:3px solid #00d4aa">
                        <div style='color:#00d4aa;font-size:15px;font-weight:600'>All access is certified</div>
                        <div style='color:#8b949e;font-size:13px;margin-top:6px'>No reviews overdue.</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="nx-header" style="margin-top:20px;color:#e3b341">{len(due)} user(s) require access certification</div>', unsafe_allow_html=True)

                    for u in due:
                        ent_list  = u.get("entitlements", [])
                        last_rev  = u.get("last_review", "Never")[:10] if u.get("last_review") else "Never"
                        days_info = f"{u['days_since']} days ago" if u.get("days_since") else "Never reviewed"

                        col1, col2, col3 = st.columns([4, 1, 1])
                        col1.markdown(f"""
                        <div class="nx-card" style="border-left:3px solid #e3b341">
                            <div style='font-size:14px;font-weight:600;color:#e6edf3'>{u['username']}</div>
                            <div style='font-size:12px;color:#8b949e;margin-top:4px;font-family:IBM Plex Mono,monospace'>
                                {u['department']} · {u['job_title']} · Last review: {last_rev} ({days_info})
                            </div>
                            <div style='font-size:12px;color:#8b949e;margin-top:6px'>
                                Access: <span style='color:#e6edf3'>{", ".join(ent_list) if ent_list else "None"}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        if col2.button("Certify", key=f"certify_{u['id']}"):
                            code, resp = api_post(
                                f"/access-review/{u['id']}/certify",
                                params={"manager_id": 1, "action": "CERTIFY"}
                            )
                            if code == 200:
                                st.success(f"Certified {u['username']}.")
                                # Refresh stored result so list updates without clearing
                                st.session_state.access_review_result = api_get(
                                    f"/access-review?review_days={review_days}"
                                )
                                st.rerun()
                            else:
                                st.error(resp.get("detail", "Error"))

                        if col3.button("Flag", key=f"flag_{u['id']}"):
                            code, resp = api_post(
                                f"/access-review/{u['id']}/certify",
                                params={"manager_id": 1, "action": "FLAG_FOR_REDUCTION"}
                            )
                            if code == 200:
                                st.warning(f"Flagged {u['username']} for access reduction.")
                                st.session_state.access_review_result = api_get(
                                    f"/access-review?review_days={review_days}"
                                )
                                st.rerun()
                            else:
                                st.error(resp.get("detail", "Error"))


# ══════════════════════════════════════════════════════════════
#  VIEW 3 — IT ADMIN
# ══════════════════════════════════════════════════════════════
elif "IT Admin" in view:
    st.markdown('<div class="nx-title">IT Admin Console</div>', unsafe_allow_html=True)
    st.markdown('<div class="nx-sub">User lifecycle · Audit logs · System integrity</div>', unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["📊  Dashboard", "➕  Onboard", "📋  Audit Log", "🔍  Integrity", "⚡  JIT Monitor", "🔎  Orphan Scanner", "📈  Timeline"])

    # ── Tab 1: Dashboard ──────────────────────────────────────
    with tab1:
        st.markdown('<div class="nx-header">System overview</div>', unsafe_allow_html=True)

        verify    = api_get("/audit-log/verify")
        transfers = api_get("/transfers/pending")

        total_logs  = verify.get("total", 0) if isinstance(verify, dict) else 0
        tampered_ct = len(verify.get("tampered", [])) if isinstance(verify, dict) else 0
        pending_ct  = len([t for t in transfers
                           if isinstance(transfers, list) and isinstance(t, dict)
                           and t.get("status") == "PENDING_APPROVAL"])

        # ALL_USERS is already fetched fresh from API — statuses are live
        active_ct   = sum(1 for u in ALL_USERS if u["status"] == "Active")
        inactive_ct = sum(1 for u in ALL_USERS if u["status"] == "Inactive")

        c1, c2, c3, c4, c5 = st.columns(5)
        for col, val, lbl, color in [
            (c1, len(ALL_USERS), "Total Users",    "#00d4aa"),
            (c2, active_ct,      "Active",         "#00d4aa"),
            (c3, inactive_ct,    "Inactive",       "#f85149" if inactive_ct else "#00d4aa"),
            (c4, total_logs,     "Audit Entries",  "#00d4aa"),
            (c5, tampered_ct,    "Tampered Logs",  "#f85149" if tampered_ct else "#00d4aa"),
        ]:
            col.markdown(f"""
            <div class="nx-metric">
                <div class="val" style="color:{color}">{val}</div>
                <div class="lbl">{lbl}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='margin-top:24px'></div>", unsafe_allow_html=True)

        # ── Search + filter bar ───────────────────────────────
        src_col1, src_col2, src_col3 = st.columns([3, 2, 1])
        search_query  = src_col1.text_input(
            "search", placeholder="Search by name, email, department, job title...",
            label_visibility="collapsed"
        )
        status_filter = src_col2.selectbox(
            "status", ["All statuses", "Active", "Inactive", "Pending"],
            label_visibility="collapsed"
        )
        dept_options  = ["All departments"] + sorted({u["department"] for u in ALL_USERS})
        dept_filter   = src_col3.selectbox(
            "dept", dept_options, label_visibility="collapsed"
        )

        # Apply filters
        filtered_users = ALL_USERS
        if search_query:
            q = search_query.lower()
            filtered_users = [
                u for u in filtered_users
                if q in u["username"].lower()
                or q in u.get("email","").lower()
                or q in u["department"].lower()
                or q in u.get("job_title","").lower()
            ]
        if status_filter != "All statuses":
            filtered_users = [u for u in filtered_users if u["status"] == status_filter]
        if dept_filter != "All departments":
            filtered_users = [u for u in filtered_users if u["department"] == dept_filter]

        # Result count
        st.markdown(
            f'<div class="nx-header">All users &nbsp;'
            f'<span style="color:#8b949e;font-weight:400;font-size:11px">'
            f'showing {len(filtered_users)} of {len(ALL_USERS)}</span></div>',
            unsafe_allow_html=True
        )

        if not filtered_users:
            st.markdown("""
            <div class="nx-card" style="text-align:center;padding:30px">
                <div style='color:#8b949e;font-size:13px'>No users match your search.</div>
            </div>
            """, unsafe_allow_html=True)

        for u in filtered_users:
            is_inactive  = u["status"] == "Inactive"
            ent_list     = [] if is_inactive else BIRTHRIGHT.get(u["department"], [])
            ent_html     = " ".join([
                f"<code style='background:#0f0f1a;border:1px solid #21213a;"
                f"padding:2px 8px;border-radius:4px;font-size:11px;color:#8b949e'>{e}</code>"
                for e in ent_list
            ])

            col1, col2 = st.columns([5, 1])
            col1.markdown(f"""
            <div class="nx-card" style="margin-bottom:10px">
                <div style='display:flex;align-items:center;gap:12px;margin-bottom:6px'>
                    <span style='font-size:15px;font-weight:600;color:#e6edf3'>{u['username']}</span>
                    {status_badge(u['status'])}
                </div>
                <div style='font-size:12px;color:#8b949e;font-family:IBM Plex Mono,monospace;margin-bottom:8px'>
                    ID: {u['id']} · {u['department']} · {u['job_title']} · {u.get('email','')}
                </div>
                <div>{ent_html if ent_html else "<span style='font-size:12px;color:#8b949e'>No active entitlements</span>"}</div>
            </div>
            """, unsafe_allow_html=True)

            if not is_inactive:
                if col2.button("🔴 Offboard", key=f"offboard_{u['id']}"):
                    with st.spinner(f"Revoking all access for {u['username']}..."):
                        code, resp = api_patch(f"/users/{u['id']}/offboard")
                    if code == 200:
                        st.success(f"Kill switch executed. Revoked: {resp.get('revoked')}")
                        st.rerun()
                    else:
                        st.error(resp.get("detail", "Error"))
            else:
                col2.markdown("<br><br>", unsafe_allow_html=True)
                col2.markdown('<span class="badge-inactive">Offboarded</span>', unsafe_allow_html=True)

    # ── Tab 2: Onboard ────────────────────────────────────────
    with tab2:
        st.markdown('<div class="nx-header">One-click new hire onboarding</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="nx-card" style="margin-bottom:24px">
            <div style='font-size:13px;color:#8b949e;line-height:1.6'>
                Hiring automatically provisions the full birthright access bundle
                based on department ABAC policy. All actions logged to the immutable audit trail.
                New users appear immediately in all views after hiring.
            </div>
        </div>
        """, unsafe_allow_html=True)

        with st.form("hire_form"):
            h_col1, h_col2 = st.columns(2)
            h_id      = h_col1.number_input("User ID",    min_value=10, value=100)
            h_username= h_col1.text_input("Username")
            h_email   = h_col1.text_input("Email")
            h_manager = h_col1.number_input("Manager ID", min_value=1, value=1)
            h_dept    = h_col2.selectbox("Department", ["Engineering","Sales","HR","Marketing","Finance"])
            h_title   = h_col2.text_input("Job Title")

            preview = BIRTHRIGHT.get(h_dept, ["Slack_General — unknown dept, manual review required"])
            h_col2.markdown("**Will provision:**")
            for p in preview:
                h_col2.markdown(f"- `{p}`")

            h_submit = st.form_submit_button("🚀 Hire & Provision", type="primary")

        if h_submit:
            if not h_username or not h_email:
                st.warning("Please fill in username and email.")
            else:
                code, resp = api_post("/users/hire", {
                    "id"        : int(h_id),
                    "username"  : h_username,
                    "email"     : h_email,
                    "department": h_dept,
                    "job_title" : h_title,
                    "manager_id": int(h_manager),
                    "status"    : "Pending",
                })
                if code == 201:
                    st.success(f"✅ {h_username} hired and activated!")
                    st.markdown(f"""
                    <div class="nx-card-accent">
                        <div style='color:#00d4aa;font-family:IBM Plex Mono,monospace;
                                    font-size:12px;margin-bottom:8px'>ONBOARDING COMPLETE</div>
                        <div style='font-size:13px;color:#8b949e'>
                            Status: <span style='color:#00d4aa'>{resp.get('status')}</span>
                            &nbsp;·&nbsp;
                            Audit entries: <span style='color:#00d4aa'>{resp.get('audit_entries_written')}</span>
                        </div>
                        <div style='font-size:13px;color:#8b949e;margin-top:4px'>
                            Provisioned: <span style='color:#e6edf3'>
                                {", ".join(resp.get("entitlements_provisioned", []))}
                            </span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    if "warning" in resp:
                        st.warning(resp["warning"])
                    _prov_html = _build_provision_html(resp.get("entitlements_provisioned", []))
                    st.markdown(f"""
                    <div class="nx-card" style="margin-top:12px;border-left:3px solid #00d4aa">
                        <div style='font-family:IBM Plex Mono,monospace;font-size:11px;
                                    color:#00d4aa;margin-bottom:6px;letter-spacing:0.1em'>
                            PROVISIONING SUMMARY
                        </div>
                        <div style='font-size:13px;color:#8b949e'>
                            User ID &nbsp;<span style='color:#e6edf3'>{resp.get("user_id")}</span>
                            &nbsp;·&nbsp;
                            Username &nbsp;<span style='color:#e6edf3'>{resp.get("username")}</span>
                            &nbsp;·&nbsp;
                            Department &nbsp;<span style='color:#e6edf3'>{resp.get("department")}</span>
                        </div>
                        <div style='font-size:13px;color:#8b949e;margin-top:6px'>
                            Status &nbsp;<span style='color:#00d4aa;font-weight:600'>{resp.get("status")}</span>
                            &nbsp;·&nbsp;
                            Audit entries written &nbsp;<span style='color:#00d4aa'>{resp.get("audit_entries_written")}</span>
                        </div>
                        <div style='margin-top:10px;font-size:12px;color:#8b949e'>
                            Resources provisioned:
                        </div>
                        {_prov_html}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.error(str(resp.get("detail", resp)))

    # ── Tab 3: Audit log ──────────────────────────────────────
    with tab3:
        st.markdown('<div class="nx-header">Immutable audit trail — read only</div>', unsafe_allow_html=True)

        if st.button("Refresh", key="refresh_audit"):
            st.rerun()

        logs = api_get("/audit-log")

        if isinstance(logs, dict) and "error" in logs:
            st.error(f"API error: {logs['error']}")
        elif not logs:
            st.info("No audit entries yet.")
        else:
            actions = ["ALL"] + sorted({l.get("action", "") for l in logs if isinstance(l, dict)})
            action_filter = st.selectbox("Filter by action", actions)
            filtered = logs if action_filter == "ALL" else [
                l for l in logs if l.get("action") == action_filter
            ]

            ACTION_COLORS = {
                "AUTO_PROVISION"    : "#00d4aa",
                "AUTO_REVOKE"       : "#e3b341",
                "EMERGENCY_REVOKE"  : "#f85149",
                "TRANSFER_REQUESTED": "#79c0ff",
                "TRANSFER_APPROVED" : "#00d4aa",
                "BLOCKED"           : "#f85149",
                "FLAGGED"           : "#e3b341",
                "PENDING_APPROVAL"  : "#e3b341",
            }

            rows_html = ""
            for log in reversed(filtered):
                action    = log.get("action", "")
                color     = ACTION_COLORS.get(action.split(" →")[0].strip(), "#8b949e")
                ts        = log.get("timestamp", "")[:19].replace("T", " ")
                actor     = "SYSTEM" if log.get("actor_id") == 0 else f"user:{log.get('actor_id')}"
                outcome   = log.get("outcome", "")
                out_color = ("#00d4aa" if outcome == "Success"
                             else "#f85149" if outcome in ("Failed", "Blocked")
                             else "#e3b341")
                rows_html += (
                    f"<tr>"
                    f"<td><code style='font-size:11px;color:#8b949e'>{log.get('id')}</code></td>"
                    f"<td style='font-size:12px;color:#8b949e;font-family:IBM Plex Mono,monospace'>{ts}</td>"
                    f"<td style='font-family:IBM Plex Mono,monospace;font-size:12px;color:{color}'>{action}</td>"
                    f"<td style='font-size:12px;color:#8b949e'>{actor}</td>"
                    f"<td style='font-size:12px'>user:{log.get('target_user_id')}</td>"
                    f"<td style='font-size:12px;color:{out_color}'>{outcome}</td>"
                    f"<td style='font-family:IBM Plex Mono,monospace;font-size:10px;color:#8b949e'>"
                    f"{log.get('integrity_hash', '')}</td>"
                    f"</tr>"
                )

            st.markdown(f"""
            <div style='overflow-x:auto'>
            <table class="nx-table">
                <thead><tr>
                    <th>#</th><th>Timestamp</th><th>Action</th>
                    <th>Actor</th><th>Target</th><th>Outcome</th><th>Hash</th>
                </tr></thead>
                <tbody>{rows_html}</tbody>
            </table>
            </div>
            """, unsafe_allow_html=True)

            # ── Download button ───────────────────────────────
            import csv, io
            def build_csv(log_entries):
                buf = io.StringIO()
                writer = csv.writer(buf)
                writer.writerow(["id","timestamp","action","actor","target_user_id",
                                 "outcome","integrity_hash","details"])
                for log in log_entries:
                    actor = "SYSTEM" if log.get("actor_id") == 0 else f"user:{log.get('actor_id')}"
                    writer.writerow([
                        log.get("id",""),
                        log.get("timestamp","")[:19].replace("T"," "),
                        log.get("action",""),
                        actor,
                        log.get("target_user_id",""),
                        log.get("outcome",""),
                        log.get("integrity_hash",""),
                        str(log.get("details",{})),
                    ])
                return buf.getvalue()

            from datetime import datetime as _dt
            filename    = f"nexusid_audit_{_dt.now().strftime('%Y%m%d_%H%M%S')}.csv"
            export_logs = filtered  # export whatever is currently filtered

            st.markdown("<div style='margin-top:16px'></div>", unsafe_allow_html=True)
            col_dl, col_info = st.columns([1, 4])
            import json as _json
            json_filename = f"nexusid_audit_{_dt.now().strftime('%Y%m%d_%H%M%S')}.json"
            json_data     = _json.dumps(export_logs, indent=2, default=str)

            col_dl, col_dl2, col_info = st.columns([1, 1, 4])
            col_dl.download_button(
                label     = "Download CSV",
                data      = build_csv(export_logs),
                file_name = filename,
                mime      = "text/csv",
                key       = "download_audit_csv",
            )
            col_dl2.download_button(
                label     = "Download JSON",
                data      = json_data,
                file_name = json_filename,
                mime      = "application/json",
                key       = "download_audit_json",
            )
            col_info.markdown(
                f"<span style='font-size:12px;color:#8b949e;line-height:2.5'>"
                f"Exporting {len(export_logs)} entries"
                f"{f' (filtered: {action_filter})' if action_filter != 'ALL' else ''}"
                f"</span>",
                unsafe_allow_html=True,
            )

    # ── Tab 4: Integrity ──────────────────────────────────────
    with tab4:
        st.markdown('<div class="nx-header">SHA-256 log integrity verification</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="nx-card" style="margin-bottom:24px">
            <div style='font-size:13px;color:#8b949e;line-height:1.6'>
                Every audit entry is hashed at write time using SHA-256 across all immutable
                fields. This check re-computes every hash and flags rows where the stored value
                no longer matches — detecting any post-write tampering.
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Run Integrity Check", type="primary"):
            result = api_get("/audit-log/verify")
            if isinstance(result, dict) and "error" in result:
                st.error(f"API error: {result['error']}")
            else:
                total    = result.get("total", 0)
                ok       = result.get("ok", 0)
                tampered = result.get("tampered", [])

                c1, c2, c3 = st.columns(3)
                for col, val, lbl in [(c1, total, "Total Rows"), (c2, ok, "Clean"), (c3, len(tampered), "Tampered")]:
                    color = "#f85149" if lbl == "Tampered" and val > 0 else "#00d4aa"
                    col.markdown(f"""
                    <div class="nx-metric">
                        <div class="val" style="color:{color}">{val}</div>
                        <div class="lbl">{lbl}</div>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown("<div style='margin-top:16px'></div>", unsafe_allow_html=True)
                if not tampered:
                    st.markdown("""
                    <div class="nx-card-accent">
                        <div style='color:#00d4aa;font-weight:600'>All hashes verified clean</div>
                        <div style='font-size:12px;color:#8b949e;margin-top:4px'>
                            No tampering detected. Audit log integrity confirmed.
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="nx-card" style="border-left:3px solid #f85149">
                        <div style='color:#f85149;font-weight:600'>Tampered rows detected</div>
                        <div style='font-size:13px;color:#8b949e;margin-top:8px'>
                            Row IDs: <code>{tampered}</code>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

    # ── Tab 5: JIT Monitor ───────────────────────────────────
    with tab5:
        st.markdown('<div class="nx-header">JIT access monitor — all users</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="nx-card" style="margin-bottom:20px">
            <div style='font-size:13px;color:#8b949e;line-height:1.6'>
                Real-time view of all Just-In-Time access grants across the organisation.
                Active grants auto-revoke when their timer expires.
                Use early revoke if a session needs to be terminated immediately.
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Refresh", key="refresh_jit_admin"):
            st.rerun()

        grants = api_get("/jit/grants")
        user_map_jit = {u["id"]: u["username"] for u in ALL_USERS}

        if isinstance(grants, list):
            active_grants  = [g for g in grants if g["status"] == "ACTIVE"]
            expired_grants = [g for g in grants if g["status"] != "ACTIVE"]

            # Metrics
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"""<div class="nx-metric">
                <div class="val">{len(active_grants)}</div>
                <div class="lbl">Active JIT grants</div></div>""", unsafe_allow_html=True)
            c2.markdown(f"""<div class="nx-metric">
                <div class="val">{len(expired_grants)}</div>
                <div class="lbl">Expired / revoked</div></div>""", unsafe_allow_html=True)
            c3.markdown(f"""<div class="nx-metric">
                <div class="val">{len(grants)}</div>
                <div class="lbl">Total grants</div></div>""", unsafe_allow_html=True)

            st.markdown('<div class="nx-header" style="margin-top:24px">Active grants</div>',
                        unsafe_allow_html=True)

            if not active_grants:
                st.markdown("""
                <div class="nx-card" style="text-align:center;padding:30px">
                    <div style='color:#8b949e;font-size:13px'>No active JIT grants</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                for g in active_grants:
                    secs      = g.get("seconds_remaining", 0)
                    mins      = secs // 60
                    secs_rem  = secs % 60
                    pct       = max(0, min(100, int(secs / (g["duration_minutes"] * 60) * 100)))
                    bar_color = "#00d4aa" if pct > 50 else "#e3b341" if pct > 20 else "#f85149"
                    username  = user_map_jit.get(g["user_id"], f"user:{g['user_id']}")

                    col1, col2 = st.columns([5, 1])
                    col1.markdown(f"""
                    <div class="nx-card" style="border-left:3px solid {bar_color}">
                        <div style='display:flex;justify-content:space-between;align-items:center'>
                            <div>
                                <div style='font-size:14px;font-weight:600;color:#e6edf3'>
                                    {username} → {g['resource_name']}
                                </div>
                                <div style='font-size:12px;color:#8b949e;margin-top:4px'>
                                    {g['justification']}
                                </div>
                                <div style='font-size:11px;color:#8b949e;margin-top:4px;
                                            font-family:IBM Plex Mono,monospace'>
                                    Granted: {g['granted_at'][:16].replace('T',' ')}
                                    &nbsp;·&nbsp;
                                    Expires: {g['expires_at'][:16].replace('T',' ')}
                                </div>
                            </div>
                            <div style='text-align:right;min-width:80px'>
                                <div style='font-family:IBM Plex Mono,monospace;font-size:22px;
                                            font-weight:600;color:{bar_color}'>
                                    {mins:02d}:{secs_rem:02d}
                                </div>
                                <div style='font-size:11px;color:#8b949e'>remaining</div>
                            </div>
                        </div>
                        <div style='margin-top:10px;background:#0f0f1a;
                                    border-radius:4px;height:4px;overflow:hidden'>
                            <div style='width:{pct}%;height:100%;
                                        background:{bar_color};border-radius:4px'></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    if col2.button("Force Revoke", key=f"admin_revoke_jit_{g['id']}"):
                        code, resp = api_post(f"/jit/{g['id']}/revoke")
                        if code == 200:
                            st.success("JIT grant force-revoked.")
                            st.rerun()
                        else:
                            st.error(resp.get("detail", "Error"))

            if expired_grants:
                st.markdown('<div class="nx-header" style="margin-top:24px">Grant history</div>',
                            unsafe_allow_html=True)
                rows_html = ""
                for g in expired_grants[:20]:
                    username  = user_map_jit.get(g["user_id"], f"user:{g['user_id']}")
                    sc = "#f85149" if g["status"] == "EXPIRED" else "#e3b341"
                    rows_html += (
                        f"<tr>"
                        f"<td><code style='font-size:11px;color:#8b949e'>{g['id']}</code></td>"
                        f"<td style='font-size:12px;color:#e6edf3'>{username}</td>"
                        f"<td style='font-family:IBM Plex Mono,monospace;font-size:12px;color:#8b949e'>"
                        f"{g['resource_name']}</td>"
                        f"<td style='font-size:12px;color:#8b949e'>{g['duration_minutes']}m</td>"
                        f"<td style='font-family:IBM Plex Mono,monospace;font-size:12px;color:{sc}'>"
                        f"{g['status']}</td>"
                        f"<td style='font-size:12px;color:#8b949e'>"
                        f"{g['granted_at'][:16].replace('T',' ')}</td>"
                        f"</tr>"
                    )
                st.markdown(f"""
                <div style='overflow-x:auto'>
                <table class="nx-table">
                    <thead><tr>
                        <th>#</th><th>User</th><th>Resource</th>
                        <th>Duration</th><th>Status</th><th>Granted at</th>
                    </tr></thead>
                    <tbody>{rows_html}</tbody>
                </table>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.error("Could not reach API.")

    # ── Tab 6: Orphaned Account Scanner ──────────────────────
    with tab6:
        st.markdown('<div class="nx-header">Orphaned account detection</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="nx-card" style="margin-bottom:20px">
            <div style='font-size:13px;color:#8b949e;line-height:1.6'>
                Scans for <span style='color:#f85149;font-weight:600'>Active</span>
                users with no recent audit activity — accounts that were never properly
                offboarded. These are a leading cause of data breaches and compliance failures.
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_days, col_scan, col_clear, _ = st.columns([1, 1, 1, 3])
        inactive_days = col_days.number_input(
            "Flag if inactive for (days)", min_value=1, max_value=365, value=30
        )

        if col_scan.button("Run Scan", type="primary"):
            with st.spinner("Scanning all active accounts..."):
                st.session_state.orphan_result       = api_get(f"/users/orphaned-check?inactive_days={inactive_days}")
                st.session_state.orphan_inactive_days = inactive_days

        if col_clear.button("Clear", key="clear_orphan"):
            st.session_state.pop("orphan_result", None)
            st.rerun()

        result = st.session_state.get("orphan_result")

        if result is not None:
            if isinstance(result, dict) and "error" in result:
                st.error(f"API error: {result['error']}")
            else:
                orphaned = result.get("orphaned", [])
                clean    = result.get("clean", [])

                # Metrics
                c1, c2, c3 = st.columns(3)
                orph_color = "#f85149" if orphaned else "#00d4aa"
                c1.markdown(f"""<div class="nx-metric">
                    <div class="val" style="color:{orph_color}">{len(orphaned)}</div>
                    <div class="lbl">Orphaned accounts</div></div>""", unsafe_allow_html=True)
                c2.markdown(f"""<div class="nx-metric">
                    <div class="val">{len(clean)}</div>
                    <div class="lbl">Clean accounts</div></div>""", unsafe_allow_html=True)
                c3.markdown(f"""<div class="nx-metric">
                    <div class="val">{result.get("total_active", 0)}</div>
                    <div class="lbl">Total scanned</div></div>""", unsafe_allow_html=True)

                st.markdown("<div style='margin-top:24px'></div>", unsafe_allow_html=True)

                if not orphaned:
                    st.markdown("""
                    <div class="nx-card" style="text-align:center;padding:40px;border-left:3px solid #00d4aa">
                        <div style='font-size:28px;margin-bottom:8px'>✓</div>
                        <div style='color:#00d4aa;font-size:15px;font-weight:600'>No orphaned accounts detected</div>
                        <div style='color:#8b949e;font-size:13px;margin-top:6px'>
                            All active users have recent audit activity.
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(
                        f'<div class="nx-header" style="color:#f85149">'
                        f'{len(orphaned)} orphaned account{"s" if len(orphaned) > 1 else ""} found</div>',
                        unsafe_allow_html=True
                    )

                    for u in orphaned:
                        risk_color = "#f85149" if u["risk"] == "HIGH" else "#e3b341"
                        last_act   = u["last_activity"][:10] if u["last_activity"] else "Never"
                        days_str   = f"{u['days_inactive']} days" if u["days_inactive"] is not None else "Never active"

                        col1, col2 = st.columns([5, 1])
                        col1.markdown(f"""
                        <div class="nx-card" style="border-left:3px solid {risk_color}">
                            <div style='display:flex;justify-content:space-between;align-items:center'>
                                <div>
                                    <div style='font-size:15px;font-weight:600;color:#e6edf3'>
                                        {u["username"]}
                                        <span style='font-size:12px;font-weight:400;
                                               background:{risk_color}22;color:{risk_color};
                                               padding:2px 10px;border-radius:12px;
                                               margin-left:8px'>{u["risk"]} RISK</span>
                                    </div>
                                    <div style='font-size:12px;color:#8b949e;margin-top:4px;
                                                font-family:IBM Plex Mono,monospace'>
                                        {u["department"]} · {u["job_title"]} · {u["email"]}
                                    </div>
                                    <div style='font-size:12px;color:#8b949e;margin-top:6px'>
                                        Last activity:
                                        <span style='color:{risk_color}'>{last_act}</span>
                                        &nbsp;·&nbsp; {days_str}
                                        &nbsp;·&nbsp; {u["reason"]}
                                    </div>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        if col2.button("Offboard", key=f"orphan_offboard_{u['id']}"):
                            with st.spinner(f"Revoking access for {u['username']}..."):
                                code, resp = api_patch(f"/users/{u['id']}/offboard")
                            if code == 200:
                                st.success(f"{u['username']} offboarded. Revoked: {resp.get('revoked')}")
                                # Re-fetch so offboarded user disappears from the list
                                threshold = st.session_state.get("orphan_inactive_days", 30)
                                st.session_state.orphan_result = api_get(
                                    f"/users/orphaned-check?inactive_days={threshold}"
                                )
                                st.rerun()
                            else:
                                st.error(resp.get("detail", "Error"))

                        if u.get("manager_id") and st.button("Notify Mgr", key=f"notify_{u['id']}"):
                            code, resp = api_post(
                                f"/users/{u['id']}/notify-manager",
                                params={"reason": "Orphaned account detected by scanner"}
                            )
                            if code == 200:
                                st.info(f"Manager notified: {resp.get('notified_manager')}")
                            else:
                                st.error(resp.get("detail", "Error"))

                if clean:
                    with st.expander(f"View {len(clean)} clean accounts"):
                        for u in clean:
                            st.markdown(
                                f'<div style="font-size:12px;color:#8b949e;font-family:'
                                f'IBM Plex Mono,monospace;padding:4px 0">'
                                f'{u["username"]} · {u["department"]} · '
                                f'last active {u["days_inactive"]}d ago</div>',
                                unsafe_allow_html=True
                            )

    # ── Tab 7: User Access Timeline ──────────────────────────
    with tab7:
        st.markdown('<div class="nx-header">User access timeline — full lifecycle history</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="nx-card" style="margin-bottom:20px">
            <div style='font-size:13px;color:#8b949e;line-height:1.6'>
                Every action taken on a user — from hire to offboard — in chronological order.
                Shows the complete before/after access state for any user.
            </div>
        </div>
        """, unsafe_allow_html=True)

        tl_options = {u["id"]: f"{u['username']} ({u['department']} · {u['status']})"
                      for u in ALL_USERS}
        tl_col1, tl_col2 = st.columns([3, 1])
        tl_user_id = tl_col1.selectbox("Select user", list(tl_options.keys()),
                                        format_func=lambda x: tl_options[x],
                                        key="timeline_user")
        load_tl = tl_col2.button("Load Timeline", type="primary", key="load_timeline")

        if load_tl or "timeline_data" in st.session_state:
            if load_tl:
                with st.spinner("Loading timeline..."):
                    st.session_state.timeline_data = api_get(f"/users/{tl_user_id}/timeline")
                    st.session_state.timeline_uid  = tl_user_id

            tl = st.session_state.get("timeline_data", {})

            if isinstance(tl, dict) and "error" in tl:
                st.error(f"API error: {tl['error']}")
            elif isinstance(tl, dict) and "username" in tl:

                # ── User header ───────────────────────────────
                status_col = "#00d4aa" if tl["status"] == "Active" else "#f85149"
                st.markdown(f"""
                <div class="nx-card" style="margin-bottom:20px;border-left:3px solid {status_col}">
                    <div style='display:flex;justify-content:space-between;align-items:center'>
                        <div>
                            <div style='font-size:20px;font-weight:600;color:#e6edf3'>
                                {tl["username"]}
                            </div>
                            <div style='font-size:12px;color:#8b949e;margin-top:4px;
                                        font-family:IBM Plex Mono,monospace'>
                                {tl["department"]} · {tl["job_title"]} · {tl["email"]}
                            </div>
                        </div>
                        <div style='text-align:right'>
                            <span style='background:{"#0d3a2e" if tl["status"]=="Active" else "#3a0d0d"};
                                         color:{status_col};border:1px solid {status_col}33;
                                         padding:4px 14px;border-radius:12px;
                                         font-family:IBM Plex Mono,monospace;font-size:13px'>
                                {tl["status"]}
                            </span>
                        </div>
                    </div>
                    <div style='margin-top:12px'>
                        <div style='font-size:12px;color:#8b949e;margin-bottom:6px'>Current access:</div>
                        <div>{"".join([
                            f"<code style='background:#0f0f1a;border:1px solid #21213a;padding:2px 10px;"
                            f"border-radius:4px;font-size:12px;color:#00d4aa;margin-right:6px'>{r}</code>"
                            for r in tl["current_access"]
                        ]) if tl["current_access"] else
                        "<span style='font-size:12px;color:#8b949e'>No active entitlements</span>"
                        }</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # ── Timeline events ───────────────────────────
                st.markdown(
                    f'<div class="nx-header">{tl["total_events"]} events</div>',
                    unsafe_allow_html=True
                )

                CATEGORY_COLORS = {
                    "joiner"  : ("#00d4aa", "#0d3a2e"),
                    "mover"   : ("#79c0ff", "#0d1e3a"),
                    "leaver"  : ("#f85149", "#3a0d0d"),
                    "jit"     : ("#e3b341", "#3a2d0d"),
                    "review"  : ("#b39ddb", "#1a1a2e"),
                    "security": ("#f85149", "#3a0d0d"),
                    "admin"   : ("#8b949e", "#161622"),
                }

                events = tl.get("events", [])
                if not events:
                    st.markdown("""
                    <div class="nx-card" style="text-align:center;padding:30px">
                        <div style='color:#8b949e;font-size:13px'>No events recorded yet.</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    for i, ev in enumerate(events):
                        cat    = ev.get("category", "admin")
                        color, bg = CATEGORY_COLORS.get(cat, ("#8b949e", "#161622"))
                        ts     = ev.get("timestamp","")[:19].replace("T"," ")
                        res    = ev.get("resource","")
                        actor  = ev.get("actor","System")
                        outcome = ev.get("outcome","")
                        out_color = "#00d4aa" if outcome in ("Success","Certified")                                     else "#f85149" if outcome in ("Failed","Blocked","Rejected")                                     else "#e3b341"

                        # Connector line except last
                        if i < len(events) - 1:
                            st.markdown(f"""
                            <div style='display:flex;align-items:flex-start;gap:16px;margin-bottom:0'>
                                <div style='display:flex;flex-direction:column;align-items:center;flex-shrink:0'>
                                    <div style='width:12px;height:12px;border-radius:50%;
                                                background:{color};margin-top:14px;flex-shrink:0'></div>
                                    <div style='width:1px;height:100%;min-height:40px;
                                                background:{color}44;margin-top:4px'></div>
                                </div>
                                <div class="nx-card" style="flex:1;margin-bottom:4px;
                                                            border-left:3px solid {color};
                                                            background:{bg}">
                                    <div style='display:flex;justify-content:space-between;
                                                align-items:center;margin-bottom:4px'>
                                        <div style='font-size:13px;font-weight:600;color:#e6edf3'>
                                            {ev["description"]}
                                            {f"<span style='font-family:IBM Plex Mono,monospace;font-size:11px;color:{color};margin-left:8px'>{res}</span>" if res else ""}
                                        </div>
                                        <span style='font-size:11px;color:{out_color};
                                                     font-family:IBM Plex Mono,monospace'>
                                            {outcome}
                                        </span>
                                    </div>
                                    <div style='font-size:11px;color:#8b949e;
                                                font-family:IBM Plex Mono,monospace'>
                                        {ts} &nbsp;·&nbsp; {actor}
                                    </div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                            <div style='display:flex;align-items:flex-start;gap:16px'>
                                <div style='width:12px;height:12px;border-radius:50%;
                                            background:{color};margin-top:14px;flex-shrink:0'></div>
                                <div class="nx-card" style="flex:1;margin-bottom:4px;
                                                            border-left:3px solid {color};
                                                            background:{bg}">
                                    <div style='display:flex;justify-content:space-between;
                                                align-items:center;margin-bottom:4px'>
                                        <div style='font-size:13px;font-weight:600;color:#e6edf3'>
                                            {ev["description"]}
                                            {f"<span style='font-family:IBM Plex Mono,monospace;font-size:11px;color:{color};margin-left:8px'>{res}</span>" if res else ""}
                                        </div>
                                        <span style='font-size:11px;color:{out_color};
                                                     font-family:IBM Plex Mono,monospace'>
                                            {outcome}
                                        </span>
                                    </div>
                                    <div style='font-size:11px;color:#8b949e;
                                                font-family:IBM Plex Mono,monospace'>
                                        {ts} &nbsp;·&nbsp; {actor}
                                    </div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)