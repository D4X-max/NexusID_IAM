"""
app.py  –  NexusID Portal  (Streamlit)
Three role-based views: Employee | Manager | IT Admin
Run: streamlit run app.py
"""

import streamlit as st
import requests
from datetime import datetime

API = "http://127.0.0.1:8000"

# ── Global constants — defined here so ALL views can access them ──
BIRTHRIGHT = {
    "Engineering": ["GitHub_Repo_Access", "Slack_Engineering_Channel", "AWS_Sandbox"],
    "Sales":       ["Salesforce_Read_Only", "Slack_Sales_Channel"],
    "HR":          ["Workday_Basic", "Slack_General"],
}

ALL_USERS = [
    {"id":1,"username":"dhruv","department":"Engineering","status":"Active","job_title":"Backend Engineer",  "email":"dhruv@company.com"},
    {"id":2,"username":"priya","department":"Sales",      "status":"Active","job_title":"Account Executive","email":"priya@company.com"},
    {"id":3,"username":"amit", "department":"HR",         "status":"Active","job_title":"HR Generalist",    "email":"amit@company.com"},
]

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
    border-radius:6px; padding:16px; text-align:center;
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
.nx-table th { background:#0f0f1a;color:#8b949e;font-family:'IBM Plex Mono',monospace;
               font-size:11px;letter-spacing:0.08em;text-transform:uppercase;
               padding:10px 14px;text-align:left;border-bottom:1px solid #21213a; }
.nx-table td { padding:10px 14px;border-bottom:1px solid #1a1a28;color:#c9d1d9; }
.nx-table tr:hover td { background:#1a1a28; }
div.stButton > button {
    background:#161622; color:#00d4aa; border:1px solid #00d4aa44;
    border-radius:6px; font-family:'IBM Plex Mono',monospace;
    font-size:12px; letter-spacing:0.05em; padding:8px 20px;
}
div.stButton > button:hover { background:#00d4aa15; border-color:#00d4aa; }
div.stButton > button[kind="primary"] { background:#00d4aa20;border-color:#00d4aa;color:#00d4aa; }
div[data-baseweb="input"] input,
div[data-baseweb="select"] div,
div[data-baseweb="textarea"] textarea {
    background:#0f0f1a !important; border-color:#21213a !important;
    color:#e6edf3 !important;
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
.chat-label { font-family:'IBM Plex Mono',monospace;font-size:10px;color:#8b949e;margin-bottom:4px;letter-spacing:0.1em; }
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
        r = requests.post(f"{API}{path}", json=data, params=params, timeout=5)
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
    cls = {"Active":"badge-active","Inactive":"badge-inactive"}.get(status,"badge-pending")
    return f'<span class="{cls}">{status}</span>'


# ── Session state init ────────────────────────────────────────
if "offboarded" not in st.session_state:
    st.session_state.offboarded = set()
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "hired_users" not in st.session_state:
    st.session_state.hired_users = []


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

    view = st.radio("view", ["👤  Employee", "✅  Manager", "🛡️  IT Admin"],
                    label_visibility="collapsed")
    st.markdown("---")
    st.markdown("""
    <div style='font-size:11px;color:#8b949e;font-family:IBM Plex Mono,monospace;line-height:1.8'>
        v0.6.0 — Sprint 3<br>SQLite · IsolationForest<br>SHA-256 Audit Integrity
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
#  VIEW 1 — EMPLOYEE
# ══════════════════════════════════════════════════════════════
if "Employee" in view:
    st.markdown('<div class="nx-title">My Access Portal</div>', unsafe_allow_html=True)
    st.markdown('<div class="nx-sub">View your current access and request new resources</div>', unsafe_allow_html=True)

    user_id  = st.selectbox("Select your profile", [1, 2, 3],
                             format_func=lambda x: {1:"dhruv (Engineering)",2:"priya (Sales)",3:"amit (HR)"}.get(x))
    user_map = {u["id"]: u for u in ALL_USERS}
    user     = user_map[user_id]

    # Check offboard status from session
    is_offboarded = user_id in st.session_state.offboarded

    if is_offboarded:
        st.error("⚠️ Your account has been deactivated. Please contact your IT Admin.")
        st.stop()

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
            {status_badge("Active")}
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="nx-header" style="margin-top:16px">Current Access</div>', unsafe_allow_html=True)
        for res in BIRTHRIGHT.get(user["department"], []):
            st.markdown(f"""
            <div class="nx-card-accent">
                <div style='font-size:13px;color:#e6edf3;font-family:IBM Plex Mono,monospace'>{res}</div>
                <div style='font-size:11px;color:#8b949e;margin-top:2px'>Active · Birthright</div>
            </div>
            """, unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="nx-header">Access Request Assistant</div>', unsafe_allow_html=True)

        if not st.session_state.chat_history:
            st.session_state.chat_history = [
                {"role":"bot","text":f"Hi {user['username']}! I can help you request access to resources. What do you need?"}
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
            submitted  = col_b.form_submit_button("Send")

        if submitted and user_input:
            st.session_state.chat_history.append({"role":"user","text":user_input})
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
                    bot_reply = f"✅ Access to <b>{matched_resource}</b> approved. Risk score: {risk} ({level})."
                elif status == "FLAGGED":
                    bot_reply = f"⚠️ <b>{matched_resource}</b> flagged for manager review. Risk: {risk} ({level})."
                elif status == "BLOCKED":
                    bot_reply = f"🚫 <b>{matched_resource}</b> blocked. Risk: {risk} ({level}). Contact IT Admin if needed."
                else:
                    bot_reply = f"Something went wrong: {resp.get('detail', str(resp))}"
            else:
                bot_reply = ("I can help with: GitHub, Salesforce, AWS, Slack, or Workday. "
                             "Try: <i>'I need access to GitHub'</i>")
            st.session_state.chat_history.append({"role":"bot","text":bot_reply})
            st.rerun()


# ══════════════════════════════════════════════════════════════
#  VIEW 2 — MANAGER
# ══════════════════════════════════════════════════════════════
elif "Manager" in view:
    st.markdown('<div class="nx-title">Manager Portal</div>', unsafe_allow_html=True)
    st.markdown('<div class="nx-sub">Approve access requests · View your team</div>', unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["✅  Pending Approvals", "👥  My Team", "🔄  Request Transfer"])

    # ── Tab 1: Approvals ──────────────────────────────────────
    with tab1:
        st.markdown('<div class="nx-header">Transfer requests awaiting approval</div>', unsafe_allow_html=True)

        if st.button("Refresh"):
            st.rerun()

        transfers = api_get("/transfers/pending")

        if isinstance(transfers, dict) and "error" in transfers:
            st.error(f"Could not reach API: {transfers['error']}")
        elif not isinstance(transfers, list) or len(transfers) == 0:
            st.markdown("""
            <div class="nx-card" style="text-align:center;padding:40px">
                <div style='font-size:32px;margin-bottom:8px'>✓</div>
                <div style='color:#8b949e;font-size:14px'>No pending approvals</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            pending = [t for t in transfers if isinstance(t, dict) and t.get("status") == "PENDING_APPROVAL"]
            if not pending:
                st.info("No pending approvals.")
            else:
                for t in pending:
                    st.markdown(f"""
                    <div class="nx-card">
                        <div style='font-size:14px;font-weight:600;color:#e6edf3'>
                            User ID {t['user_id']} — Transfer Request
                        </div>
                        <div style='font-size:12px;color:#8b949e;margin-top:4px;font-family:IBM Plex Mono,monospace'>
                            {t['old_department']} → {t['new_department']}
                        </div>
                        <div style='font-size:11px;color:#8b949e;margin-top:6px'>
                            Token: {t['token'][:16]}... · Requested: {t['created_at'][:10]}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    col_a, col_r, col_s = st.columns([1, 1, 4])
                    with col_a:
                        if st.button("Approve", key=f"approve_{t['token']}"):
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
                        if st.button("Reject", key=f"reject_{t['token']}"):
                            st.warning("Rejection endpoint coming in Sprint 4.")

    # ── Tab 2: My team ────────────────────────────────────────
    with tab2:
        st.markdown('<div class="nx-header">Direct reports</div>', unsafe_allow_html=True)
        team = [u for u in ALL_USERS if u["id"] in (2, 3)]
        for member in team:
            is_off    = member["id"] in st.session_state.offboarded
            cur_status = "Inactive" if is_off else member["status"]
            entitlements = [] if is_off else BIRTHRIGHT.get(member["department"], [])
            with st.expander(f"{member['username']}  ·  {member['department']}  ·  {member['job_title']}"):
                col1, col2 = st.columns(2)
                col1.markdown(f"**Status:** {cur_status}")
                col1.markdown(f"**User ID:** {member['id']}")
                col2.markdown("**Current Access:**")
                if entitlements:
                    for e in entitlements:
                        col2.markdown(f"- `{e}`")
                else:
                    col2.markdown("_No active entitlements_")

    # ── Tab 3: Request transfer ───────────────────────────────
    with tab3:
        st.markdown('<div class="nx-header">Request a department transfer</div>', unsafe_allow_html=True)
        with st.form("transfer_form"):
            t_user_id  = st.selectbox("Employee", [1, 2, 3],
                format_func=lambda x: {1:"dhruv (Engineering)",2:"priya (Sales)",3:"amit (HR)"}.get(x))
            t_new_dept = st.selectbox("Transfer to", ["Engineering", "Sales", "HR", "Marketing"])
            t_submit   = st.form_submit_button("Request Transfer")

        if t_submit:
            code, resp = api_patch(f"/users/{t_user_id}/transfer",
                                   params={"new_department": t_new_dept})
            if code == 200:
                st.success("Transfer request created and persisted to SQLite!")
                st.markdown(f"""
                <div class="nx-card-accent" style="margin-top:12px">
                    <div style='font-family:IBM Plex Mono,monospace;font-size:12px;color:#00d4aa'>APPROVAL TOKEN</div>
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


# ══════════════════════════════════════════════════════════════
#  VIEW 3 — IT ADMIN
# ══════════════════════════════════════════════════════════════
elif "IT Admin" in view:
    st.markdown('<div class="nx-title">IT Admin Console</div>', unsafe_allow_html=True)
    st.markdown('<div class="nx-sub">User lifecycle · Audit logs · System integrity</div>', unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs(["📊  Dashboard", "➕  Onboard", "📋  Audit Log", "🔍  Integrity"])

    # ── Tab 1: Dashboard ──────────────────────────────────────
    with tab1:
        st.markdown('<div class="nx-header">System overview</div>', unsafe_allow_html=True)

        verify    = api_get("/audit-log/verify")
        transfers = api_get("/transfers/pending")

        total_logs   = verify.get("total", 0) if isinstance(verify, dict) else 0
        tampered_ct  = len(verify.get("tampered", [])) if isinstance(verify, dict) else 0
        pending_ct   = len([t for t in transfers
                            if isinstance(transfers, list) and isinstance(t, dict)
                            and t.get("status") == "PENDING_APPROVAL"])

        # Build live user list — apply session-state offboards
        live_users = []
        for u in ALL_USERS + st.session_state.hired_users:
            u_copy = dict(u)
            if u_copy["id"] in st.session_state.offboarded:
                u_copy["status"] = "Inactive"
            live_users.append(u_copy)

        active_ct   = sum(1 for u in live_users if u["status"] == "Active")
        inactive_ct = sum(1 for u in live_users if u["status"] == "Inactive")

        c1, c2, c3, c4, c5 = st.columns(5)
        for col, val, lbl, color in [
            (c1, len(live_users), "Total Users",       "#00d4aa"),
            (c2, active_ct,       "Active",            "#00d4aa"),
            (c3, inactive_ct,     "Inactive",          "#f85149" if inactive_ct else "#00d4aa"),
            (c4, total_logs,      "Audit Entries",     "#00d4aa"),
            (c5, tampered_ct,     "Tampered Logs",     "#f85149" if tampered_ct else "#00d4aa"),
        ]:
            col.markdown(f"""
            <div class="nx-metric">
                <div class="val" style="color:{color}">{val}</div>
                <div class="lbl">{lbl}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='margin-top:24px'></div>", unsafe_allow_html=True)
        st.markdown('<div class="nx-header">All users</div>', unsafe_allow_html=True)

        for u in live_users:
            is_inactive  = u["status"] == "Inactive"
            ent_list     = [] if is_inactive else BIRTHRIGHT.get(u["department"], [])
            ent_html     = " ".join([
                f"<code style='background:#0f0f1a;border:1px solid #21213a;padding:2px 8px;"
                f"border-radius:4px;font-size:11px;color:#8b949e'>{e}</code>"
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
                    ID: {u['id']} · {u['department']} · {u['job_title']}
                </div>
                <div>{ent_html if ent_html else "<span style='font-size:12px;color:#8b949e'>No active entitlements</span>"}</div>
            </div>
            """, unsafe_allow_html=True)

            if not is_inactive:
                if col2.button("🔴 Offboard", key=f"offboard_{u['id']}"):
                    with st.spinner(f"Revoking all access for {u['username']}..."):
                        code, resp = api_patch(f"/users/{u['id']}/offboard")
                    if code == 200:
                        st.session_state.offboarded.add(u["id"])
                        st.success(f"Kill switch executed. Revoked: {resp.get('revoked')}")
                        st.rerun()
                    else:
                        st.error(resp.get("detail", "Error"))
            else:
                col2.markdown("<br>", unsafe_allow_html=True)
                col2.markdown('<span class="badge-inactive">Offboarded</span>', unsafe_allow_html=True)

    # ── Tab 2: Onboard ────────────────────────────────────────
    with tab2:
        st.markdown('<div class="nx-header">One-click new hire onboarding</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="nx-card" style="margin-bottom:24px">
            <div style='font-size:13px;color:#8b949e;line-height:1.6'>
                Hiring automatically provisions the full birthright access bundle
                based on department ABAC policy. All actions logged to immutable audit trail.
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

            preview = BIRTHRIGHT.get(h_dept, ["Slack_General (unknown dept — manual review)"])
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
                    # Add to session so dashboard reflects the new hire immediately
                    st.session_state.hired_users.append({
                        "id"        : int(h_id),
                        "username"  : h_username,
                        "department": h_dept,
                        "status"    : "Active",
                        "job_title" : h_title,
                        "email"     : h_email,
                    })
                    st.success(f"✅ {h_username} hired and activated!")
                    st.markdown(f"""
                    <div class="nx-card-accent">
                        <div style='color:#00d4aa;font-family:IBM Plex Mono,monospace;font-size:12px;margin-bottom:8px'>
                            ONBOARDING COMPLETE
                        </div>
                        <div style='font-size:13px;color:#8b949e'>
                            Status: <span style='color:#00d4aa'>{resp.get('status')}</span>
                            &nbsp;·&nbsp; Audit entries: <span style='color:#00d4aa'>{resp.get('audit_entries_written')}</span>
                        </div>
                        <div style='font-size:13px;color:#8b949e;margin-top:4px'>
                            Provisioned: <span style='color:#e6edf3'>{", ".join(resp.get("entitlements_provisioned", []))}</span>
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

        if st.button("Refresh", key="refresh_audit"):
            st.rerun()

        logs = api_get("/audit-log")

        if isinstance(logs, dict) and "error" in logs:
            st.error(f"API error: {logs['error']}")
        elif not logs:
            st.info("No audit entries yet.")
        else:
            actions = ["ALL"] + sorted(list({l.get("action","") for l in logs if isinstance(l, dict)}))
            action_filter = st.selectbox("Filter by action", actions)
            filtered = logs if action_filter == "ALL" else [l for l in logs if l.get("action") == action_filter]

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
                action    = log.get("action","")
                color     = ACTION_COLORS.get(action.split(" →")[0].strip(), "#8b949e")
                ts        = log.get("timestamp","")[:19].replace("T"," ")
                actor     = "SYSTEM" if log.get("actor_id") == 0 else f"user:{log.get('actor_id')}"
                outcome   = log.get("outcome","")
                out_color = "#00d4aa" if outcome == "Success" else "#f85149" if outcome in ("Failed","Blocked") else "#e3b341"
                rows_html += (
                    f"<tr>"
                    f"<td><code style='font-size:11px;color:#8b949e'>{log.get('id')}</code></td>"
                    f"<td style='font-size:12px;color:#8b949e;font-family:IBM Plex Mono,monospace'>{ts}</td>"
                    f"<td style='font-family:IBM Plex Mono,monospace;font-size:12px;color:{color}'>{action}</td>"
                    f"<td style='font-size:12px;color:#8b949e'>{actor}</td>"
                    f"<td style='font-size:12px'>user:{log.get('target_user_id')}</td>"
                    f"<td style='font-size:12px;color:{out_color}'>{outcome}</td>"
                    f"<td style='font-family:IBM Plex Mono,monospace;font-size:10px;color:#8b949e'>{log.get('integrity_hash','')}</td>"
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

    # ── Tab 4: Integrity ──────────────────────────────────────
    with tab4:
        st.markdown('<div class="nx-header">SHA-256 log integrity verification</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="nx-card" style="margin-bottom:24px">
            <div style='font-size:13px;color:#8b949e;line-height:1.6'>
                Every audit entry is hashed at write time using SHA-256 across all immutable fields.
                This check re-computes every hash and flags rows where the stored value no longer
                matches — detecting any post-write tampering.
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
                for col, val, lbl in [(c1,total,"Total Rows"),(c2,ok,"Clean"),(c3,len(tampered),"Tampered")]:
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