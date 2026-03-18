"""
app.py  –  NexusID Portal  (Streamlit)
Run:  streamlit run app.py
Requires: pip install streamlit requests
"""

import streamlit as st
import requests
import json
from datetime import datetime

API = "http://127.0.0.1:8000"

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

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: #0a0a0f;
    border-right: 1px solid #1e1e2e;
}
[data-testid="stSidebar"] * { color: #c9d1d9 !important; }
[data-testid="stSidebar"] .stRadio label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 13px;
    letter-spacing: 0.05em;
}

/* Main bg */
.stApp { background: #0d0d14; color: #e6edf3; }

/* Cards */
.nx-card {
    background: #161622;
    border: 1px solid #21213a;
    border-radius: 8px;
    padding: 20px 24px;
    margin-bottom: 16px;
}
.nx-card-accent {
    background: #161622;
    border-left: 3px solid #00d4aa;
    border-radius: 0 8px 8px 0;
    padding: 16px 20px;
    margin-bottom: 12px;
}

/* Metric */
.nx-metric {
    background: #0f0f1a;
    border: 1px solid #1e1e30;
    border-radius: 6px;
    padding: 16px;
    text-align: center;
}
.nx-metric .val {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 32px;
    font-weight: 600;
    color: #00d4aa;
}
.nx-metric .lbl {
    font-size: 11px;
    color: #8b949e;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-top: 4px;
}

/* Status badges */
.badge-active   { background:#0d3a2e; color:#00d4aa; border:1px solid #00d4aa33;
                  padding:2px 10px; border-radius:12px; font-size:12px; font-family:monospace; }
.badge-inactive { background:#3a0d0d; color:#f85149; border:1px solid #f8514933;
                  padding:2px 10px; border-radius:12px; font-size:12px; font-family:monospace; }
.badge-pending  { background:#3a2d0d; color:#e3b341; border:1px solid #e3b34133;
                  padding:2px 10px; border-radius:12px; font-size:12px; font-family:monospace; }

/* Risk badges */
.risk-low    { background:#0d3a2e; color:#00d4aa; border:1px solid #00d4aa44;
               padding:3px 12px; border-radius:12px; font-size:13px; font-weight:600; }
.risk-medium { background:#3a2d0d; color:#e3b341; border:1px solid #e3b34144;
               padding:3px 12px; border-radius:12px; font-size:13px; font-weight:600; }
.risk-high   { background:#3a0d0d; color:#f85149; border:1px solid #f8514944;
               padding:3px 12px; border-radius:12px; font-size:13px; font-weight:600; }

/* Headers */
.nx-header {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: #8b949e;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid #21213a;
}
.nx-title {
    font-size: 24px;
    font-weight: 600;
    color: #e6edf3;
    margin-bottom: 4px;
}
.nx-sub {
    font-size: 13px;
    color: #8b949e;
    margin-bottom: 24px;
}

/* Tables */
.nx-table { width:100%; border-collapse:collapse; font-size:13px; }
.nx-table th { background:#0f0f1a; color:#8b949e; font-family:'IBM Plex Mono',monospace;
               font-size:11px; letter-spacing:0.08em; text-transform:uppercase;
               padding:10px 14px; text-align:left; border-bottom:1px solid #21213a; }
.nx-table td { padding:10px 14px; border-bottom:1px solid #1a1a28; color:#c9d1d9; }
.nx-table tr:hover td { background:#1a1a28; }

/* Buttons */
div.stButton > button {
    background: #161622;
    color: #00d4aa;
    border: 1px solid #00d4aa44;
    border-radius: 6px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    letter-spacing: 0.05em;
    padding: 8px 20px;
    transition: all 0.2s;
}
div.stButton > button:hover {
    background: #00d4aa15;
    border-color: #00d4aa;
}
div.stButton > button[kind="primary"] {
    background: #00d4aa20;
    border-color: #00d4aa;
    color: #00d4aa;
}

/* Inputs */
div[data-baseweb="input"] input,
div[data-baseweb="select"] div,
div[data-baseweb="textarea"] textarea {
    background: #0f0f1a !important;
    border-color: #21213a !important;
    color: #e6edf3 !important;
    font-family: 'IBM Plex Sans', sans-serif !important;
}

/* Divider */
hr { border-color: #21213a; }

/* Chat */
.chat-msg-user {
    background: #161d2b;
    border: 1px solid #1e2d45;
    border-radius: 12px 12px 2px 12px;
    padding: 12px 16px;
    margin: 8px 0;
    margin-left: 20%;
    color: #79c0ff;
    font-size: 14px;
}
.chat-msg-bot {
    background: #161622;
    border: 1px solid #21213a;
    border-radius: 12px 12px 12px 2px;
    padding: 12px 16px;
    margin: 8px 0;
    margin-right: 20%;
    color: #c9d1d9;
    font-size: 14px;
}
.chat-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    color: #8b949e;
    margin-bottom: 4px;
    letter-spacing: 0.1em;
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

def api_post(path, data):
    try:
        r = requests.post(f"{API}{path}", json=data, timeout=5)
        return r.status_code, r.json()
    except Exception as e:
        return 500, {"error": str(e)}

def api_patch(path):
    try:
        r = requests.patch(f"{API}{path}", timeout=5)
        return r.status_code, r.json()
    except Exception as e:
        return 500, {"error": str(e)}

def status_badge(status):
    cls = {"Active":"badge-active","Inactive":"badge-inactive"}.get(status,"badge-pending")
    return f'<span class="{cls}">{status}</span>'

def risk_badge(level):
    cls = {"LOW":"risk-low","MEDIUM":"risk-medium","HIGH":"risk-high"}.get(level,"risk-high")
    return f'<span class="{cls}">{level}</span>'


# ── Sidebar ───────────────────────────────────────────────────
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

    st.markdown("**Switch View**")
    view = st.radio(
        "view",
        ["👤  Employee", "✅  Manager", "🛡️  IT Admin"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown("""
    <div style='font-size:11px;color:#8b949e;font-family:IBM Plex Mono,monospace;
                line-height:1.8'>
        v0.6.0 — Sprint 3<br>
        SQLite · IsolationForest<br>
        SHA-256 Audit Integrity
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
#  VIEW 1 — EMPLOYEE
# ══════════════════════════════════════════════════════════════
if "Employee" in view:
    st.markdown('<div class="nx-title">My Access Portal</div>', unsafe_allow_html=True)
    st.markdown('<div class="nx-sub">View your current access and request new resources</div>', unsafe_allow_html=True)

    # User selector
    user_id = st.selectbox("Select your profile", [1, 2, 3],
                           format_func=lambda x: {1:"dhruv (Engineering)",2:"priya (Sales)",3:"amit (HR)"}.get(x))

    users = {
        1: {"username":"dhruv","department":"Engineering","email":"dhruv@company.com","status":"Active","job_title":"Backend Engineer"},
        2: {"username":"priya","department":"Sales","email":"priya@company.com","status":"Active","job_title":"Account Executive"},
        3: {"username":"amit","department":"HR","email":"amit@company.com","status":"Active","job_title":"HR Generalist"},
    }
    ENTITLEMENTS = {
        "Engineering": ["GitHub_Repo_Access","Slack_Engineering_Channel","AWS_Sandbox"],
        "Sales":       ["Salesforce_Read_Only","Slack_Sales_Channel"],
        "HR":          ["Workday_Basic","Slack_General"],
    }
    user = users[user_id]

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown('<div class="nx-header">Profile</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div class="nx-card">
            <div style='font-size:20px;font-weight:600;color:#e6edf3;margin-bottom:4px'>
                {user['username']}
            </div>
            <div style='font-size:13px;color:#8b949e;margin-bottom:12px'>{user['job_title']}</div>
            <div style='font-size:12px;color:#8b949e;margin-bottom:6px'>
                <span style='color:#00d4aa'>dept</span>&nbsp;&nbsp;{user['department']}
            </div>
            <div style='font-size:12px;color:#8b949e;margin-bottom:12px'>
                <span style='color:#00d4aa'>email</span>&nbsp;{user['email']}
            </div>
            {status_badge(user['status'])}
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="nx-header" style="margin-top:16px">Current Access</div>', unsafe_allow_html=True)
        for res in ENTITLEMENTS.get(user["department"], []):
            st.markdown(f"""
            <div class="nx-card-accent">
                <div style='font-size:13px;color:#e6edf3;font-family:IBM Plex Mono,monospace'>{res}</div>
                <div style='font-size:11px;color:#8b949e;margin-top:2px'>Active · Birthright</div>
            </div>
            """, unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="nx-header">Access Request Assistant</div>', unsafe_allow_html=True)

        # Chat history
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = [
                {"role": "bot", "text": f"Hi {user['username']}! I can help you request access to resources. What do you need?"}
            ]

        # Display chat
        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                st.markdown(f'<div class="chat-label" style="text-align:right">YOU</div>'
                           f'<div class="chat-msg-user">{msg["text"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="chat-label">NEXUS</div>'
                           f'<div class="chat-msg-bot">{msg["text"]}</div>', unsafe_allow_html=True)

        st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)

        # Input
        with st.form("chat_form", clear_on_submit=True):
            col_input, col_btn = st.columns([4, 1])
            with col_input:
                user_input = st.text_input("message", placeholder="e.g. I need access to Salesforce...",
                                          label_visibility="collapsed")
            with col_btn:
                submitted = st.form_submit_button("Send")

        if submitted and user_input:
            st.session_state.chat_history.append({"role":"user","text":user_input})

            # Parse intent
            text_lower = user_input.lower()
            resource_map = {
                "salesforce": "Salesforce_Read_Only",
                "github":     "GitHub_Repo_Access",
                "aws":        "AWS_Sandbox",
                "slack":      "Slack_General",
                "workday":    "Workday_Basic",
                "aws_root":   "AWS_Root",
            }
            matched_resource = next((v for k,v in resource_map.items() if k in text_lower), None)

            if matched_resource:
                code, resp = api_post("/request-access", {
                    "user_id"      : user_id,
                    "resource_name": matched_resource,
                    "justification": user_input,
                    "request_type" : "Grant",
                })
                status = resp.get("status","ERROR")
                risk   = resp.get("risk_score", "N/A")
                level  = resp.get("risk_level", "")

                if status == "APPROVED":
                    bot_reply = f"✅ Access to **{matched_resource}** approved! Risk score: {risk} ({level}). You're all set."
                elif status == "FLAGGED":
                    bot_reply = f"⚠️ Your request for **{matched_resource}** has been flagged for manager review. Risk score: {risk}. Your manager will be notified."
                elif status == "BLOCKED":
                    bot_reply = f"🚫 Request for **{matched_resource}** was blocked. Risk score: {risk} ({level}). This resource is outside your department's access policy. Contact IT Admin if you believe this is an error."
                else:
                    bot_reply = f"Something went wrong: {resp.get('detail', str(resp))}"
            else:
                bot_reply = ("I can help you request access to: GitHub, Salesforce, AWS, Slack, or Workday. "
                            "Just mention the tool you need — for example: 'I need access to Salesforce for a client demo'.")

            st.session_state.chat_history.append({"role":"bot","text":bot_reply})
            st.rerun()


# ══════════════════════════════════════════════════════════════
#  VIEW 2 — MANAGER
# ══════════════════════════════════════════════════════════════
elif "Manager" in view:
    st.markdown('<div class="nx-title">Manager Dashboard</div>', unsafe_allow_html=True)
    st.markdown('<div class="nx-sub">Approve transfer requests and view your team</div>', unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["📋  Pending Approvals", "👥  My Team", "🔀  Initiate Transfer"])

    # ── Tab 1: Pending approvals ──────────────────────────────
    with tab1:
        st.markdown('<div class="nx-header">Transfer requests awaiting approval</div>', unsafe_allow_html=True)

        transfers = api_get("/transfers/pending")

        if "error" in transfers:
            st.error(f"API error: {transfers['error']}")
        else:
            pending = [t for t in transfers if t["status"] == "PENDING_APPROVAL"]
            if not pending:
                st.markdown("""
                <div class="nx-card" style="text-align:center;padding:40px">
                    <div style='font-size:32px;margin-bottom:8px'>✓</div>
                    <div style='color:#8b949e;font-size:14px'>No pending approvals</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                for t in pending:
                    with st.container():
                        st.markdown(f"""
                        <div class="nx-card">
                            <div style='display:flex;justify-content:space-between;align-items:center'>
                                <div>
                                    <div style='font-size:14px;font-weight:600;color:#e6edf3'>
                                        User ID {t['user_id']} — Transfer Request
                                    </div>
                                    <div style='font-size:12px;color:#8b949e;margin-top:4px;
                                                font-family:IBM Plex Mono,monospace'>
                                        {t['old_department']} → {t['new_department']}
                                    </div>
                                    <div style='font-size:11px;color:#8b949e;margin-top:6px'>
                                        Token: {t['token'][:16]}...
                                        &nbsp;·&nbsp; Requested: {t['created_at'][:10]}
                                    </div>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        col_a, col_r, col_s = st.columns([1, 1, 4])
                        with col_a:
                            if st.button("Approve", key=f"approve_{t['token']}"):
                                code, resp = api_post(
                                    f"/transfer/{t['token']}/approve?manager_id=1", {}
                                )
                                if code == 200:
                                    st.success(f"Approved! Granted: {resp.get('granted')}")
                                    st.rerun()
                                else:
                                    st.error(str(resp))
                        with col_r:
                            if st.button("Reject", key=f"reject_{t['token']}"):
                                st.warning("Rejection endpoint coming in Sprint 4.")

    # ── Tab 2: My team ────────────────────────────────────────
    with tab2:
        st.markdown('<div class="nx-header">Direct reports</div>', unsafe_allow_html=True)

        team = [
            {"id":2,"name":"priya","dept":"Sales","title":"Account Executive","status":"Active"},
            {"id":3,"name":"amit","dept":"HR","title":"HR Generalist","status":"Active"},
        ]

        ENTITLEMENTS = {
            "Engineering": ["GitHub_Repo_Access","Slack_Engineering_Channel","AWS_Sandbox"],
            "Sales":       ["Salesforce_Read_Only","Slack_Sales_Channel"],
            "HR":          ["Workday_Basic","Slack_General"],
        }

        for member in team:
            with st.expander(f"{member['name']}  ·  {member['dept']}  ·  {member['title']}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Status:** {member['status']}")
                    st.markdown(f"**User ID:** {member['id']}")
                with col2:
                    entitlements = ENTITLEMENTS.get(member["dept"], [])
                    st.markdown("**Current Access:**")
                    for e in entitlements:
                        st.markdown(f"- `{e}`")

    # ── Tab 3: Initiate transfer ──────────────────────────────
    with tab3:
        st.markdown('<div class="nx-header">Request a department transfer for a team member</div>', unsafe_allow_html=True)

        with st.form("transfer_form"):
            t_user_id = st.selectbox("Employee", [2, 3],
                format_func=lambda x: {2:"priya (Sales)", 3:"amit (HR)"}.get(x))
            t_new_dept = st.selectbox("Transfer to", ["Engineering","Sales","HR","Marketing"])
            t_submit = st.form_submit_button("Request Transfer")

        if t_submit:
            code, resp = api_patch(f"/users/{t_user_id}/transfer?new_department={t_new_dept}")
            if code == 200:
                st.success(f"Transfer request created!")
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
                        Persisted to SQLite — survives server restarts
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.error(str(resp.get("detail", resp)))


# ══════════════════════════════════════════════════════════════
#  VIEW 3 — IT ADMIN
# ══════════════════════════════════════════════════════════════
elif "IT Admin" in view:
    st.markdown('<div class="nx-title">IT Admin Console</div>', unsafe_allow_html=True)
    st.markdown('<div class="nx-sub">User lifecycle management · Audit logs · System integrity</div>', unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["📊  Dashboard", "➕  Onboard", "📋  Audit Log", "🔍  Integrity"])

    # ── Tab 1: Dashboard ──────────────────────────────────────
    with tab1:
        st.markdown('<div class="nx-header">User overview</div>', unsafe_allow_html=True)

        users_data = [
            {"id":1,"username":"dhruv","department":"Engineering","status":"Active","job_title":"Backend Engineer"},
            {"id":2,"username":"priya","department":"Sales","status":"Active","job_title":"Account Executive"},
            {"id":3,"username":"amit","department":"HR","status":"Active","job_title":"HR Generalist"},
        ]

        active   = sum(1 for u in users_data if u["status"] == "Active")
        inactive = sum(1 for u in users_data if u["status"] == "Inactive")
        pending  = sum(1 for u in users_data if u["status"] == "Pending")

        c1, c2, c3, c4 = st.columns(4)
        for col, val, lbl in [
            (c1, len(users_data), "Total Users"),
            (c2, active,          "Active"),
            (c3, inactive,        "Inactive"),
            (c4, pending,         "Pending"),
        ]:
            with col:
                st.markdown(f"""
                <div class="nx-metric">
                    <div class="val">{val}</div>
                    <div class="lbl">{lbl}</div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("<div style='margin-top:24px'></div>", unsafe_allow_html=True)
        st.markdown('<div class="nx-header">All users</div>', unsafe_allow_html=True)

        rows = "".join([
            f"<tr><td><code>{u['id']}</code></td>"
            f"<td style='color:#e6edf3;font-weight:500'>{u['username']}</td>"
            f"<td>{u['department']}</td>"
            f"<td>{u['job_title']}</td>"
            f"<td>{status_badge(u['status'])}</td></tr>"
            for u in users_data
        ])
        st.markdown(f"""
        <table class="nx-table">
            <thead><tr>
                <th>ID</th><th>Username</th><th>Department</th>
                <th>Job Title</th><th>Status</th>
            </tr></thead>
            <tbody>{rows}</tbody>
        </table>
        """, unsafe_allow_html=True)

        st.markdown("<div style='margin-top:32px'></div>", unsafe_allow_html=True)
        st.markdown('<div class="nx-header">Kill switch — emergency offboard</div>', unsafe_allow_html=True)

        with st.form("offboard_form"):
            ob_col1, ob_col2 = st.columns([2, 1])
            with ob_col1:
                ob_user = st.selectbox("Select user to offboard", [1, 2, 3],
                    format_func=lambda x: {1:"dhruv (Engineering)",2:"priya (Sales)",3:"amit (HR)"}.get(x))
            with ob_col2:
                st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
                ob_submit = st.form_submit_button("⚡ Execute Kill Switch", type="primary")

        if ob_submit:
            code, resp = api_patch(f"/users/{ob_user}/offboard")
            if code == 200:
                st.success(f"Kill switch executed for user {ob_user}")
                st.markdown(f"""
                <div class="nx-card" style="margin-top:12px">
                    <div style='color:#f85149;font-family:IBM Plex Mono,monospace;
                                font-size:12px;margin-bottom:8px'>EMERGENCY REVOKE COMPLETE</div>
                    <div style='font-size:13px;color:#8b949e'>
                        Revoked: <span style='color:#e6edf3'>{", ".join(resp.get("revoked", []))}</span>
                    </div>
                    <div style='font-size:13px;color:#8b949e;margin-top:4px'>
                        Parallel: <span style='color:#00d4aa'>{resp.get("parallel")}</span>
                        &nbsp;·&nbsp;
                        Audit entries: <span style='color:#00d4aa'>{resp.get("audit_entries")}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.error(str(resp.get("detail", resp)))

    # ── Tab 2: Onboard ────────────────────────────────────────
    with tab2:
        st.markdown('<div class="nx-header">One-click new hire onboarding</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="nx-card" style="margin-bottom:24px">
            <div style='font-size:13px;color:#8b949e;line-height:1.6'>
                Hiring a new employee automatically provisions their full birthright access bundle
                based on department policy (ABAC). All actions are logged to the immutable audit trail.
            </div>
        </div>
        """, unsafe_allow_html=True)

        with st.form("hire_form"):
            h_col1, h_col2 = st.columns(2)
            with h_col1:
                h_id       = st.number_input("User ID", min_value=10, value=100)
                h_username = st.text_input("Username")
                h_email    = st.text_input("Email")
                h_manager  = st.number_input("Manager ID", min_value=1, value=1)
            with h_col2:
                h_dept  = st.selectbox("Department", ["Engineering","Sales","HR","Marketing","Finance"])
                h_title = st.text_input("Job Title")

                PREVIEW = {
                    "Engineering": ["GitHub_Repo_Access","Slack_Engineering_Channel","AWS_Sandbox"],
                    "Sales":       ["Salesforce_Read_Only","Slack_Sales_Channel"],
                    "HR":          ["Workday_Basic","Slack_General"],
                }
                preview = PREVIEW.get(h_dept, ["Slack_General — unknown dept, manual review required"])
                st.markdown("**Will provision:**")
                for p in preview:
                    st.markdown(f"- `{p}`")

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
                    st.success(f"Successfully hired {h_username}!")
                    st.markdown(f"""
                    <div class="nx-card" style="margin-top:12px">
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
                else:
                    st.error(str(resp.get("detail", resp)))

    # ── Tab 3: Audit log ──────────────────────────────────────
    with tab3:
        st.markdown('<div class="nx-header">Immutable audit trail — read only</div>', unsafe_allow_html=True)

        col_r, col_f = st.columns([1, 3])
        with col_r:
            if st.button("Refresh"):
                st.rerun()

        logs = api_get("/audit-log")

        if "error" in logs:
            st.error(f"API error: {logs['error']}")
        elif not logs:
            st.info("No audit entries yet.")
        else:
            ACTION_COLORS = {
                "AUTO_PROVISION"    : "#00d4aa",
                "AUTO_REVOKE"       : "#e3b341",
                "EMERGENCY_REVOKE"  : "#f85149",
                "TRANSFER_REQUESTED": "#79c0ff",
                "TRANSFER_APPROVED" : "#00d4aa",
                "BLOCKED"           : "#f85149",
                "FLAGGED"           : "#e3b341",
            }

            rows = ""
            for log in reversed(logs):
                action = log.get("action","")
                color  = ACTION_COLORS.get(action.split(" →")[0], "#8b949e")
                ts     = log.get("timestamp","")[:19].replace("T"," ")
                actor  = "SYSTEM" if log.get("actor_id") == 0 else f"user:{log.get('actor_id')}"
                outcome = log.get("outcome","")
                out_color = "#00d4aa" if outcome == "Success" else "#f85149" if outcome in ("Failed","Blocked") else "#e3b341"

                rows += (
                    f"<tr>"
                    f"<td><code style='font-size:11px;color:#8b949e'>{log.get('id')}</code></td>"
                    f"<td style='font-size:12px;color:#8b949e;font-family:IBM Plex Mono,monospace'>{ts}</td>"
                    f"<td style='font-family:IBM Plex Mono,monospace;font-size:12px;color:{color}'>{action}</td>"
                    f"<td style='font-size:12px;color:#8b949e'>{actor}</td>"
                    f"<td style='font-size:12px'>user:{log.get('target_user_id')}</td>"
                    f"<td style='font-size:12px;color:{out_color}'>{outcome}</td>"
                    f"<td style='font-family:IBM Plex Mono,monospace;font-size:10px;color:#8b949e'>"
                    f"{log.get('integrity_hash','')}</td>"
                    f"</tr>"
                )

            st.markdown(f"""
            <div style='overflow-x:auto'>
            <table class="nx-table">
                <thead><tr>
                    <th>#</th><th>Timestamp</th><th>Action</th>
                    <th>Actor</th><th>Target</th><th>Outcome</th><th>Hash</th>
                </tr></thead>
                <tbody>{rows}</tbody>
            </table>
            </div>
            """, unsafe_allow_html=True)

    # ── Tab 4: Integrity check ────────────────────────────────
    with tab4:
        st.markdown('<div class="nx-header">SHA-256 log integrity verification</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="nx-card" style="margin-bottom:24px">
            <div style='font-size:13px;color:#8b949e;line-height:1.6'>
                Every audit log entry is hashed at write time using SHA-256 across all
                immutable fields. This check re-computes every hash and flags any rows
                where the stored hash no longer matches — detecting post-write tampering.
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("Run Integrity Check", type="primary"):
            result = api_get("/audit-log/verify")
            if "error" in result:
                st.error(f"API error: {result['error']}")
            else:
                total    = result.get("total", 0)
                ok       = result.get("ok", 0)
                tampered = result.get("tampered", [])

                c1, c2, c3 = st.columns(3)
                for col, val, lbl in [(c1,total,"Total Rows"),(c2,ok,"Clean"),(c3,len(tampered),"Tampered")]:
                    with col:
                        color = "#f85149" if lbl == "Tampered" and val > 0 else "#00d4aa"
                        st.markdown(f"""
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