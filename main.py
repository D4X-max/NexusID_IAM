"""
main.py  –  NexusID API  v0.7.0
Users + transfers + audit all persisted to SQLite.
Run:  uvicorn main:app --reload
Docs: http://127.0.0.1:8000/docs
"""

import sys, random, uuid, asyncio
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
sys.path.insert(0, "../simulated_connectors")

from models      import AccessRequest, User
from risk_engine import assess_request
from database import (
    init_db, get_db, SessionLocal,
    append_log, verify_log_integrity, AuditLogDB,
    create_transfer, get_transfer, resolve_transfer, PendingTransferDB,
    get_all_users, get_user, upsert_user,
    update_user_status, update_user_department, UserDB,
)
from simulated_connectors.mock_engine import mock_api_call

# ── App ───────────────────────────────────────────────────────
app = FastAPI(
    title="NexusID API",
    description="Unified IAM — Joiner / Mover / Leaver. All state persisted to SQLite.",
    version="0.7.0",
)


# ── Startup: create tables + seed default users ───────────────
@app.on_event("startup")
def startup():
    init_db()
    db = SessionLocal()
    try:
        if db.query(UserDB).count() == 0:
            for u in [
                dict(id=1, username="dhruv", email="dhruv@company.com",
                     department="Engineering", job_title="Backend Engineer",
                     manager_id=None, status="Active"),
                dict(id=2, username="priya", email="priya@company.com",
                     department="Sales", job_title="Account Executive",
                     manager_id=1, status="Active"),
                dict(id=3, username="amit", email="amit@company.com",
                     department="HR", job_title="HR Generalist",
                     manager_id=1, status="Active"),
            ]:
                upsert_user(db, **u)
    finally:
        db.close()


# ── Birthright policies (ABAC) ────────────────────────────────
BIRTHRIGHT_POLICIES = {
    "Engineering": ["GitHub_Repo_Access", "Slack_Engineering_Channel", "AWS_Sandbox"],
    "Sales":       ["Salesforce_Read_Only", "Slack_Sales_Channel"],
    "HR":          ["Workday_Basic", "Slack_General"],
}


# ── Helpers ───────────────────────────────────────────────────
def resolve_connector(resource_name: str, request_type: str) -> tuple[str, str]:
    name    = resource_name.lower()
    service = "aws" if any(k in name for k in ("aws","github","workday","salesforce")) else "slack"
    action  = "provision" if request_type.lower() == "grant" else "deprovision"
    return service, action


async def simulate_provisioning(email: str, resource_name: str,
                                 request_type: str = "grant") -> dict:
    service, action = resolve_connector(resource_name, request_type)
    username = email.split("@")[0]
    raw = mock_api_call(service=service, action=action, user=username)
    raw["status_code"]   = 201 if request_type == "grant" else 200
    raw["resource_name"] = resource_name
    return raw


def user_to_dict(u: UserDB) -> dict:
    return {
        "id"        : u.id,
        "username"  : u.username,
        "email"     : u.email,
        "department": u.department,
        "job_title" : u.job_title,
        "manager_id": u.manager_id,
        "status"    : u.status,
    }


# ── Joiner logic ──────────────────────────────────────────────
async def process_joiner_event(user: UserDB, db: Session) -> list:
    results      = []
    policy_found = user.department in BIRTHRIGHT_POLICIES

    if policy_found:
        entitlements = BIRTHRIGHT_POLICIES[user.department]
        action_type  = "AUTO_PROVISION"
        status       = "Success"
    else:
        entitlements = ["MANUAL_REVIEW_REQUIRED"]
        action_type  = "PENDING_APPROVAL"
        status       = "Manual_Action"

    for resource in entitlements:
        if action_type == "AUTO_PROVISION":
            response = await simulate_provisioning(user.email, resource)
        else:
            response = {
                "status_code"  : 202,
                "resource_name": resource,
                "body"         : {"message": f"Admin alert — no policy for '{user.department}'"},
            }
        row = append_log(db, actor_id=0, action=action_type,
                         target_user_id=user.id, outcome=status, details=response)
        results.append(row)

    return results


# ── Mover logic ───────────────────────────────────────────────
async def process_mover_event(user: UserDB, old_department: str,
                               db: Session) -> list:
    old_access = BIRTHRIGHT_POLICIES.get(old_department)
    new_access = BIRTHRIGHT_POLICIES.get(user.department)

    if old_access is None or new_access is None:
        unknown = old_department if old_access is None else user.department
        row = append_log(db, actor_id=0, action="MOVER_REVIEW_REQUIRED",
                         target_user_id=user.id, outcome="Manual_Action",
                         details={"reason": f"No policy defined for '{unknown}'"})
        return [row]

    to_revoke = set(old_access) - set(new_access)
    to_grant  = set(new_access) - set(old_access)
    results   = []

    for resource in to_revoke:
        response = await simulate_provisioning(user.email, resource, "revoke")
        response["action_taken"] = "REVOKE"
        row = append_log(db, actor_id=0, action="AUTO_REVOKE",
                         target_user_id=user.id,
                         outcome="Success" if response["status_code"] == 200 else "Failed",
                         details=response)
        results.append(row)

    for resource in to_grant:
        response = await simulate_provisioning(user.email, resource, "grant")
        response["action_taken"] = "GRANT"
        row = append_log(db, actor_id=0, action="AUTO_PROVISION",
                         target_user_id=user.id,
                         outcome="Success" if response["status_code"] == 201 else "Failed",
                         details=response)
        results.append(row)

    return results


# ── Leaver logic (parallel kill switch) ──────────────────────
async def _revoke_one(user: UserDB, resource: str, db: Session) -> AuditLogDB:
    response = await simulate_provisioning(user.email, resource, "revoke")
    response["action_taken"] = "EMERGENCY_REVOKE"
    return append_log(db, actor_id=0, action="EMERGENCY_REVOKE",
                      target_user_id=user.id,
                      outcome="Success" if response["status_code"] == 200 else "Failed",
                      details=response)


async def trigger_leaver_kill_switch(user: UserDB, entitlements: list[str],
                                      db: Session) -> list:
    # Parallel API calls — sequential DB writes to avoid SQLite lock
    responses = await asyncio.gather(
        *[simulate_provisioning(user.email, r, "revoke") for r in entitlements]
    )
    results = []
    for response in responses:
        response["action_taken"] = "EMERGENCY_REVOKE"
        row = append_log(db, actor_id=0, action="EMERGENCY_REVOKE",
                         target_user_id=user.id,
                         outcome="Success" if response["status_code"] == 200 else "Failed",
                         details=response)
        results.append(row)

    update_user_status(db, user.id, "Inactive")
    return results


# ── Health ────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {"message": "NexusID API is live", "version": "0.7.0",
            "storage": "SQLite (users + transfers + audit)"}


# ── Users ─────────────────────────────────────────────────────
@app.get("/users", tags=["Users"])
def get_users(db: Session = Depends(get_db)) -> list:
    """All users from SQLite — live status, survives restarts."""
    return [user_to_dict(u) for u in get_all_users(db)]


# ── Hire ──────────────────────────────────────────────────────
@app.post("/users/hire", tags=["Lifecycle"], status_code=201)
async def hire_user(new_user: User, db: Session = Depends(get_db)) -> dict:
    """
    Hire a new user and trigger birthright provisioning.
    ```json
    {"id":10,"username":"riya","email":"riya@company.com",
     "department":"Engineering","job_title":"SRE","manager_id":1,"status":"Pending"}
    ```
    """
    if get_user(db, new_user.id):
        raise HTTPException(status_code=409, detail=f"User ID {new_user.id} already exists.")
    if new_user.status != "Pending":
        raise HTTPException(status_code=422, detail="New hires must arrive with status 'Pending'.")

    db_user = upsert_user(
        db, id=new_user.id, username=new_user.username, email=new_user.email,
        department=new_user.department, job_title=new_user.job_title,
        manager_id=new_user.manager_id, status="Pending",
    )
    logs     = await process_joiner_event(db_user, db)
    all_ok   = all(row.outcome in ("Success", "Manual_Action") for row in logs)
    final_st = "Active" if all_ok else "Provisioning_Failed"
    update_user_status(db, db_user.id, final_st)

    resp = {
        "event"                   : "HIRE",
        "user_id"                 : db_user.id,
        "username"                : db_user.username,
        "department"              : db_user.department,
        "status"                  : final_st,
        "entitlements_provisioned": [row.details.get("resource_name") for row in logs],
        "audit_entries_written"   : len(logs),
        "timestamp"               : datetime.now(timezone.utc).isoformat(),
    }
    if new_user.department not in BIRTHRIGHT_POLICIES:
        resp["warning"] = (f"No policy for '{new_user.department}'. "
                           f"PENDING_APPROVAL logged. IT admin action required.")
    return resp


# ── Transfer request ──────────────────────────────────────────
@app.patch("/users/{user_id}/transfer", tags=["Lifecycle"])
async def transfer_user(user_id: int, new_department: str,
                        db: Session = Depends(get_db)) -> dict:
    """Initiates a transfer — persisted to SQLite, requires manager approval."""
    user = get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found.")
    if user.status != "Active":
        raise HTTPException(status_code=403, detail=f"User '{user.username}' must be Active.")
    if user.department == new_department:
        raise HTTPException(status_code=409, detail="User is already in that department.")
    if user.manager_id is None:
        raise HTTPException(status_code=422, detail="User has no manager. Cannot route for approval.")

    token = str(uuid.uuid4())
    create_transfer(db, token=token, user_id=user_id,
                    old_department=user.department, new_department=new_department,
                    requested_by=user_id, approver_id=user.manager_id)
    append_log(db, actor_id=user_id, action="TRANSFER_REQUESTED",
               target_user_id=user_id, outcome="Pending",
               details={"token": token, "old": user.department, "new": new_department})

    return {
        "status"         : "PENDING_APPROVAL",
        "message"        : f"Persisted to SQLite. Awaiting manager (id={user.manager_id}) approval.",
        "approval_token" : token,
        "user"           : user.username,
        "old_department" : user.department,
        "new_department" : new_department,
    }


# ── Transfer approval ─────────────────────────────────────────
@app.post("/transfer/{token}/approve", tags=["Lifecycle"])
async def approve_transfer(token: str, manager_id: int,
                           db: Session = Depends(get_db)) -> dict:
    """Manager approves transfer. Reads from SQLite — survives restarts."""
    request = get_transfer(db, token)
    if not request:
        raise HTTPException(status_code=404, detail="Token not found.")
    if request.status != "PENDING_APPROVAL":
        raise HTTPException(status_code=409, detail=f"Transfer is already '{request.status}'.")
    if manager_id != request.approver_id:
        raise HTTPException(status_code=403,
            detail=f"Manager ID {manager_id} is not the designated approver.")

    user = get_user(db, request.user_id)
    if not user:
        raise HTTPException(status_code=404,
            detail=f"User {request.user_id} not found. Re-hire and create a new transfer request.")

    old_dep = request.old_department
    new_dep = request.new_department

    update_user_department(db, user.id, new_dep)
    updated_user = get_user(db, user.id)
    logs = await process_mover_event(updated_user, old_dep, db)

    resolve_transfer(db, token, "APPROVED")
    append_log(db, actor_id=manager_id, action="TRANSFER_APPROVED",
               target_user_id=user.id, outcome="Success",
               details={"token": token, "old": old_dep, "new": new_dep, "approver": manager_id})

    return {
        "event"          : "TRANSFER_APPROVED",
        "username"       : user.username,
        "old_department" : old_dep,
        "new_department" : new_dep,
        "approved_by"    : manager_id,
        "revoked"        : [r.details.get("resource_name") for r in logs if r.action == "AUTO_REVOKE"],
        "granted"        : [r.details.get("resource_name") for r in logs if r.action == "AUTO_PROVISION"],
        "audit_entries"  : len(logs),
    }


# ── Offboard ──────────────────────────────────────────────────
@app.patch("/users/{user_id}/offboard", tags=["Lifecycle"])
async def offboard_user(user_id: int, db: Session = Depends(get_db)) -> dict:
    """Kill switch — parallel revocation, status persisted to SQLite."""
    user = get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found.")
    if user.status == "Inactive":
        raise HTTPException(status_code=409, detail=f"User '{user.username}' is already Inactive.")

    entitlements = BIRTHRIGHT_POLICIES.get(user.department, ["Slack_General"])
    logs = await trigger_leaver_kill_switch(user, entitlements, db)

    return {
        "event"        : "LEAVER",
        "user_id"      : user_id,
        "username"     : user.username,
        "department"   : user.department,
        "status"       : "Inactive",
        "revoked"      : [r.details.get("resource_name") for r in logs],
        "all_revoked"  : all(r.outcome == "Success" for r in logs),
        "parallel"     : True,
        "audit_entries": len(logs),
        "timestamp"    : datetime.now(timezone.utc).isoformat(),
    }


# ── Access request with risk scoring ─────────────────────────
@app.post("/request-access", tags=["Access"])
def request_access(payload: AccessRequest, db: Session = Depends(get_db)) -> dict:
    """Manual Grant / Revoke with ML risk scoring (LOW/MEDIUM/HIGH)."""
    user = get_user(db, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User {payload.user_id} not found.")
    if user.status != "Active":
        raise HTTPException(status_code=403,
            detail=f"User '{user.username}' is '{user.status}'. Only Active users can request access.")
    if payload.request_type not in ("Grant", "Revoke"):
        raise HTTPException(status_code=422, detail="request_type must be 'Grant' or 'Revoke'.")

    risk = assess_request(department=user.department, resource_name=payload.resource_name)

    if risk["level"] == "HIGH":
        append_log(db, actor_id=payload.user_id,
                   action=f"BLOCKED → {payload.resource_name}",
                   target_user_id=payload.user_id, outcome="Blocked",
                   details={"reason": "Anomaly detected by risk engine",
                            "risk_score": risk["score"], "risk_level": risk["level"],
                            "resource_name": payload.resource_name,
                            "justification": payload.justification})
        return {"status": "BLOCKED", "reason": "Anomaly detected — request exceeds risk threshold.",
                "risk_score": risk["score"], "risk_level": risk["level"],
                "recommendation": risk["recommendation"], "audit_logged": True}

    if risk["level"] == "MEDIUM":
        append_log(db, actor_id=payload.user_id,
                   action=f"FLAGGED → {payload.resource_name}",
                   target_user_id=payload.user_id, outcome="Flagged",
                   details={"reason": "Medium risk — pending manual review",
                            "risk_score": risk["score"], "risk_level": risk["level"],
                            "resource_name": payload.resource_name,
                            "justification": payload.justification})
        return {"status": "FLAGGED", "reason": "Medium risk — flagged for manual review.",
                "risk_score": risk["score"], "risk_level": risk["level"],
                "recommendation": risk["recommendation"], "audit_logged": True}

    service, action = resolve_connector(payload.resource_name, payload.request_type)
    mock_response   = mock_api_call(service=service, action=action, user=user.username)
    outcome         = "Success" if mock_response.get("status") != "error" else "Failed"
    nexus_id        = f"NXS-{service.upper()}-{random.randint(100000, 999999)}"

    append_log(db, actor_id=payload.user_id,
               action=f"{payload.request_type} → {payload.resource_name}",
               target_user_id=payload.user_id, outcome=outcome,
               details=mock_response | {"risk_score": risk["score"], "risk_level": risk["level"]})

    return {
        "nexus_id"           : nexus_id,
        "status"             : "APPROVED",
        "outcome"            : outcome,
        "user"               : user.username,
        "department"         : user.department,
        "resource_name"      : payload.resource_name,
        "request_type"       : payload.request_type,
        "justification"      : payload.justification,
        "risk_score"         : risk["score"],
        "risk_level"         : risk["level"],
        "connector_response" : mock_response,
        "audit_logged"       : True,
    }


# ── Pending transfers ─────────────────────────────────────────
@app.get("/transfers/pending", tags=["Lifecycle"])
def get_pending_transfers(db: Session = Depends(get_db)) -> list:
    rows = db.query(PendingTransferDB).order_by(PendingTransferDB.created_at).all()
    return [
        {
            "token"          : r.token,
            "user_id"        : r.user_id,
            "old_department" : r.old_department,
            "new_department" : r.new_department,
            "approver_id"    : r.approver_id,
            "status"         : r.status,
            "created_at"     : r.created_at.isoformat(),
            "resolved_at"    : r.resolved_at.isoformat() if r.resolved_at else None,
        }
        for r in rows
    ]


# ── Audit log ─────────────────────────────────────────────────
@app.get("/audit-log", tags=["Audit"])
def get_audit_log(db: Session = Depends(get_db)) -> list:
    rows = db.query(AuditLogDB).order_by(AuditLogDB.id).all()
    return [
        {
            "id"            : r.id,
            "timestamp"     : r.timestamp.isoformat(),
            "actor_id"      : r.actor_id,
            "action"        : r.action,
            "target_user_id": r.target_user_id,
            "outcome"       : r.outcome,
            "details"       : r.details,
            "integrity_hash": r.integrity_hash[:16] + "…",
        }
        for r in rows
    ]


@app.get("/audit-log/verify", tags=["Audit"])
def verify_integrity(db: Session = Depends(get_db)) -> dict:
    """SHA-256 tamper detection across all audit rows."""
    return verify_log_integrity(db)