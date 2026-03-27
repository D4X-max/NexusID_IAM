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

from models import User, AuditLog, AccessRequest, UserCreate
from risk_engine import assess_request
from database import (
    init_db, get_db, SessionLocal,
    append_log, verify_log_integrity, AuditLogDB,
    create_transfer, get_transfer, resolve_transfer, PendingTransferDB,
    get_all_users, get_user, upsert_user,
    update_user_status, update_user_department, UserDB,
    create_jit_grant, get_active_jit_grants, get_all_jit_grants,
    expire_jit_grant, revoke_jit_grant_early, JITAccessDB,create_user,
)
from simulated_connectors.mock_engine import mock_api_call

# ── App ───────────────────────────────────────────────────────
app = FastAPI(
    title="NexusID API",
    description="Unified IAM — Joiner / Mover / Leaver. All state persisted to SQLite.",
    version="0.8.0",
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
    "Marketing":   ["Salesforce_Marketing", "Slack_Marketing_Channel", "AWS_Analytics"],
    "Finance":     ["Workday_Finance", "Slack_Finance_Channel", "AWS_Billing"],
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
    return {"message": "NexusID API is live", "version": "0.8.0",
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
    if new_user.status != "Pending":
        raise HTTPException(status_code=422, detail="New hires must arrive with status 'Pending'.")

    existing = get_user(db, new_user.id)
    if existing and existing.status in ("Active", "Pending"):
        raise HTTPException(status_code=409,
            detail=f"User ID {new_user.id} already exists and is '{existing.status}'. "
                   f"Offboard them first before re-hiring.")

    # Re-hire path: user exists but is Inactive (e.g. contractor returning)
    is_rehire = existing is not None and existing.status == "Inactive"

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
        "event"                   : "REHIRE" if is_rehire else "HIRE",
        "user_id"                 : db_user.id,
        "username"                : db_user.username,
        "department"              : db_user.department,
        "status"                  : final_st,
        "entitlements_provisioned": [row.details.get("resource_name") for row in logs],
        "audit_entries_written"   : len(logs),
        "timestamp"               : datetime.now(timezone.utc).isoformat(),
    }
    if is_rehire:
        resp["note"] = "User was previously offboarded and has been re-hired. Full audit trail preserved."
    if new_user.department not in BIRTHRIGHT_POLICIES:
        resp["warning"] = (f"No policy for '{new_user.department}'. "
                           f"PENDING_APPROVAL logged. IT admin action required.")
    return resp


# ── Transfer request ──────────────────────────────────────────
@app.patch("/users/{user_id}/transfer", tags=["Lifecycle"])
async def transfer_user(user_id: int, new_department: str, new_job_title: str,
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
                    old_job_title=user.job_title, new_job_title=new_job_title, # <--- NEW
                    requested_by=user_id, approver_id=user.manager_id)
    
    append_log(db, actor_id=user_id, action="TRANSFER_REQUESTED",
               target_user_id=user_id, outcome="Pending",
               details={"token": token, "old": user.department, "new": new_department,
                        "old_title": user.job_title, "new_title": new_job_title}) # <--- NEW

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

    user.department = new_dep
    if request.new_job_title:
        user.job_title = request.new_job_title
    db.commit() 
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

# ── Transfer rejection ────────────────────────────────────────
@app.post("/transfer/{token}/reject", tags=["Lifecycle"])
async def reject_transfer(
    token      : str,
    manager_id : int,
    reason     : str = "Rejected by manager",
    db         : Session = Depends(get_db),
) -> dict:
    """
    Manager rejects a pending transfer request.
    User keeps their current department and access. Audit logged.
    """
    request = get_transfer(db, token)
    if not request:
        raise HTTPException(status_code=404, detail="Token not found.")
    if request.status != "PENDING_APPROVAL":
        raise HTTPException(status_code=409,
            detail=f"Transfer is already '{request.status}' — cannot reject.")
    if manager_id != request.approver_id:
        raise HTTPException(status_code=403,
            detail=f"Manager ID {manager_id} is not the designated approver.")

    user = get_user(db, request.user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User {request.user_id} not found.")

    # Mark token as rejected in SQLite
    resolve_transfer(db, token, "REJECTED")

    # Audit log — user keeps old department, no access changes
    append_log(
        db             = db,
        actor_id       = manager_id,
        action         = "TRANSFER_REJECTED",
        target_user_id = request.user_id,
        outcome        = "Rejected",
        details        = {
            "token"          : token,
            "old_department" : request.old_department,
            "new_department" : request.new_department,
            "approver"       : manager_id,
            "reason"         : reason,
        },
    )

    return {
        "event"          : "TRANSFER_REJECTED",
        "username"       : user.username,
        "old_department" : request.old_department,
        "new_department" : request.new_department,
        "rejected_by"    : manager_id,
        "reason"         : reason,
        "note"           : f"{user.username} keeps their current access in {user.department}.",
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
            "new_job_title": r.new_job_title,
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




# ── Manager-initiated leaver request ─────────────────────────
@app.post("/users/{user_id}/terminate-request", tags=["Lifecycle"])
async def terminate_request(
    user_id    : int,
    manager_id : int,
    reason     : str = "Employee resignation",
    db         : Session = Depends(get_db),
) -> dict:
    """
    Manager initiates a leaver request for one of their direct reports.
    Immediately triggers the kill switch — offboards the user, revokes
    all access, and logs the termination with the manager as actor.

    This closes the JML loop: Joiner (IT Admin) → Mover (Manager approval)
    → Leaver (Manager initiated OR IT Admin kill switch).

    Example:
        POST /users/1/terminate-request?manager_id=2&reason=Resignation
    """
    user = get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found.")
    if user.status == "Inactive":
        raise HTTPException(status_code=409,
            detail=f"User '{user.username}' is already Inactive.")

    # Validate manager relationship
    if user.manager_id != manager_id:
        raise HTTPException(status_code=403,
            detail=f"Manager {manager_id} is not the direct manager of '{user.username}'. "
                   f"Only the direct manager can initiate a termination request.")

    # Log the termination request before killing access
    append_log(
        db             = db,
        actor_id       = manager_id,
        action         = "TERMINATION_REQUESTED",
        target_user_id = user_id,
        outcome        = "Initiated",
        details        = {
            "reason"        : reason,
            "initiated_by"  : f"manager:{manager_id}",
            "department"    : user.department,
        },
    )

    # Trigger the kill switch immediately — same as IT Admin offboard
    entitlements = BIRTHRIGHT_POLICIES.get(user.department, ["Slack_General"])
    logs = await trigger_leaver_kill_switch(user, entitlements, db)

    # Override the audit log actor to show manager initiated this
    append_log(
        db             = db,
        actor_id       = manager_id,
        action         = "TERMINATION_COMPLETED",
        target_user_id = user_id,
        outcome        = "Success",
        details        = {
            "reason"         : reason,
            "initiated_by"   : f"manager:{manager_id}",
            "resources_revoked": [r.details.get("resource_name") for r in logs],
        },
    )

    return {
        "event"        : "LEAVER",
        "triggered_by" : "MANAGER",
        "manager_id"   : manager_id,
        "user_id"      : user_id,
        "username"     : user.username,
        "department"   : user.department,
        "reason"       : reason,
        "status"       : "Inactive",
        "revoked"      : [r.details.get("resource_name") for r in logs],
        "all_revoked"  : all(r.outcome == "Success" for r in logs),
        "audit_entries": len(logs) + 2,
        "timestamp"    : datetime.now(timezone.utc).isoformat(),
    }


# ── Access review workflow ────────────────────────────────────
@app.get("/access-review", tags=["Access"])
def get_access_review(
    review_days: int = 90,
    db: Session = Depends(get_db),
) -> dict:
    """
    Returns users whose access has not been reviewed in the last N days.
    Managers use this to certify their team still needs current access.
    Prevents access creep — permissions that accumulate silently over time.
    """
    from datetime import timedelta
    cutoff    = datetime.now(timezone.utc) - timedelta(days=review_days)
    all_users = get_all_users(db)
    due       = []
    up_to_date = []

    for user in all_users:
        if user.status != "Active":
            continue
        last_review = (
            db.query(AuditLogDB)
            .filter(
                AuditLogDB.target_user_id == user.id,
                AuditLogDB.action == "ACCESS_REVIEW_CERTIFIED"
            )
            .order_by(AuditLogDB.id.desc())
            .first()
        )
        entitlements = BIRTHRIGHT_POLICIES.get(user.department, [])
        if last_review is None:
            days_since = None
            due.append({
                "id"          : user.id,
                "username"    : user.username,
                "email"       : user.email,
                "department"  : user.department,
                "job_title"   : user.job_title,
                "manager_id"  : user.manager_id,
                "entitlements": entitlements,
                "last_review" : None,
                "days_since"  : None,
                "reason"      : "Never reviewed",
            })
        else:
            ts = last_review.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            days_since = (datetime.now(timezone.utc) - ts).days
            entry = {
                "id"          : user.id,
                "username"    : user.username,
                "email"       : user.email,
                "department"  : user.department,
                "job_title"   : user.job_title,
                "manager_id"  : user.manager_id,
                "entitlements": entitlements,
                "last_review" : ts.isoformat(),
                "days_since"  : days_since,
            }
            if ts < cutoff:
                entry["reason"] = f"Last reviewed {days_since} days ago"
                due.append(entry)
            else:
                up_to_date.append(entry)

    return {
        "scanned_at"   : datetime.now(timezone.utc).isoformat(),
        "review_days"  : review_days,
        "due_count"    : len(due),
        "clean_count"  : len(up_to_date),
        "due"          : due,
        "up_to_date"   : up_to_date,
    }


@app.post("/access-review/{user_id}/certify", tags=["Access"])
def certify_access(
    user_id    : int,
    manager_id : int,
    action     : str = "CERTIFY",
    db         : Session = Depends(get_db),
) -> dict:
    """
    Manager certifies a user's current access is appropriate (CERTIFY)
    or flags it for reduction (FLAG_FOR_REDUCTION).

    action options: "CERTIFY" | "FLAG_FOR_REDUCTION"
    """
    user = get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found.")
    if action not in ("CERTIFY", "FLAG_FOR_REDUCTION"):
        raise HTTPException(status_code=422,
            detail="action must be 'CERTIFY' or 'FLAG_FOR_REDUCTION'.")

    entitlements = BIRTHRIGHT_POLICIES.get(user.department, [])
    outcome      = "Certified" if action == "CERTIFY" else "Flagged"

    append_log(
        db             = db,
        actor_id       = manager_id,
        action         = "ACCESS_REVIEW_CERTIFIED" if action == "CERTIFY" else "ACCESS_REVIEW_FLAGGED",
        target_user_id = user_id,
        outcome        = outcome,
        details        = {
            "action"      : action,
            "entitlements": entitlements,
            "manager_id"  : manager_id,
            "reviewed_at" : datetime.now(timezone.utc).isoformat(),
        },
    )

    return {
        "event"       : "ACCESS_REVIEW",
        "action"      : action,
        "user_id"     : user_id,
        "username"    : user.username,
        "department"  : user.department,
        "entitlements": entitlements,
        "reviewed_by" : manager_id,
        "outcome"     : outcome,
        "timestamp"   : datetime.now(timezone.utc).isoformat(),
    }


# ── Manager notification on orphan detection ──────────────────
@app.post("/users/{user_id}/notify-manager", tags=["Users"])
def notify_manager(
    user_id : int,
    reason  : str = "Orphaned account detected",
    db      : Session = Depends(get_db),
) -> dict:
    """
    Sends a simulated notification to the user's manager when an
    orphaned account is detected. Logged in the audit trail.
    In production this would trigger a real Slack/email webhook.
    """
    user = get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found.")
    if user.manager_id is None:
        raise HTTPException(status_code=422,
            detail=f"User '{user.username}' has no manager assigned.")

    manager = get_user(db, user.manager_id)
    manager_name = manager.username if manager else f"manager:{user.manager_id}"

    append_log(
        db             = db,
        actor_id       = 0,
        action         = "MANAGER_NOTIFIED",
        target_user_id = user_id,
        outcome        = "Success",
        details        = {
            "reason"          : reason,
            "notified_manager": manager_name,
            "manager_id"      : user.manager_id,
            "channel"         : "simulated_slack",
            "message"         : f"Action required: {user.username} flagged — {reason}",
        },
    )

    return {
        "event"            : "MANAGER_NOTIFIED",
        "user_id"          : user_id,
        "username"         : user.username,
        "notified_manager" : manager_name,
        "manager_id"       : user.manager_id,
        "reason"           : reason,
        "channel"          : "simulated_slack",
        "note"             : "In production this fires a real Slack/email webhook.",
    }


# ── User access timeline ──────────────────────────────────────
@app.get("/users/{user_id}/timeline", tags=["Users"])
def get_user_timeline(user_id: int, db: Session = Depends(get_db)) -> dict:
    """
    Returns a full chronological access history for a user.
    Shows every JML event, access grant/revoke, and audit entry
    in one place — the before/after access state in narrative form.
    """
    user = get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found.")

    logs = (
        db.query(AuditLogDB)
        .filter(AuditLogDB.target_user_id == user_id)
        .order_by(AuditLogDB.timestamp.asc())
        .all()
    )

    ACTION_DESCRIPTIONS = {
        "AUTO_PROVISION"         : "Access granted",
        "AUTO_REVOKE"            : "Access revoked",
        "EMERGENCY_REVOKE"       : "Emergency revoke",
        "TRANSFER_REQUESTED"     : "Transfer requested",
        "TRANSFER_APPROVED"      : "Transfer approved",
        "TRANSFER_REJECTED"      : "Transfer rejected",
        "TERMINATION_REQUESTED"  : "Termination initiated",
        "TERMINATION_COMPLETED"  : "Offboarding complete",
        "JIT_GRANTED"            : "JIT access granted",
        "JIT_EXPIRED"            : "JIT access expired (auto)",
        "JIT_REVOKED_EARLY"      : "JIT access revoked early",
        "PENDING_APPROVAL"       : "Pending admin review",
        "MOVER_REVIEW_REQUIRED"  : "Manual review required",
        "ACCESS_REVIEW_CERTIFIED": "Access certified by manager",
        "ACCESS_REVIEW_FLAGGED"  : "Access flagged for reduction",
        "MANAGER_NOTIFIED"       : "Manager notified",
        "BLOCKED"                : "Request blocked (high risk)",
        "FLAGGED"                : "Request flagged (medium risk)",
    }

    EVENT_CATEGORY = {
        "AUTO_PROVISION"         : "joiner",
        "AUTO_REVOKE"            : "mover",
        "EMERGENCY_REVOKE"       : "leaver",
        "TRANSFER_REQUESTED"     : "mover",
        "TRANSFER_APPROVED"      : "mover",
        "TRANSFER_REJECTED"      : "mover",
        "TERMINATION_REQUESTED"  : "leaver",
        "TERMINATION_COMPLETED"  : "leaver",
        "JIT_GRANTED"            : "jit",
        "JIT_EXPIRED"            : "jit",
        "JIT_REVOKED_EARLY"      : "jit",
        "PENDING_APPROVAL"       : "joiner",
        "MOVER_REVIEW_REQUIRED"  : "mover",
        "ACCESS_REVIEW_CERTIFIED": "review",
        "ACCESS_REVIEW_FLAGGED"  : "review",
        "MANAGER_NOTIFIED"       : "admin",
        "BLOCKED"                : "security",
        "FLAGGED"                : "security",
    }

    events = []
    for log in logs:
        action_key = log.action.split(" →")[0].strip()
        details    = log.details if isinstance(log.details, dict) else {}
        resource   = details.get("resource_name") or details.get("resource") or ""
        
        # --- NEW ACTOR RESOLUTION ---
        if log.actor_id == 0:
            actor = "System"
        else:
            actor_record = get_user(db, log.actor_id)
            actor = actor_record.username if actor_record else f"User {log.actor_id}"
        # ----------------------------
        
        ts         = log.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        events.append({
            "id"         : log.id,
            "timestamp"  : ts.isoformat(),
            "action"     : log.action,
            "description": ACTION_DESCRIPTIONS.get(action_key, log.action),
            "category"   : EVENT_CATEGORY.get(action_key, "admin"),
            "resource"   : resource,
            "actor"      : actor,
            "outcome"    : log.outcome,
            "details"    : details,
        })

    # Current access state
    current_access = [] if user.status == "Inactive" else                      BIRTHRIGHT_POLICIES.get(user.department, [])

    return {
        "user_id"       : user_id,
        "username"      : user.username,
        "email"         : user.email,
        "department"    : user.department,
        "job_title"     : user.job_title,
        "status"        : user.status,
        "current_access": current_access,
        "total_events"  : len(events),
        "events"        : events,
    }

# ── Orphaned account scanner ──────────────────────────────────
@app.get("/users/orphaned-check", tags=["Users"])
def orphaned_check(
    inactive_days: int = 30,
    db: Session = Depends(get_db),
) -> dict:
    """
    Scans for potentially orphaned accounts — Active users with
    no audit activity in the last N days.

    An orphaned account is one that was never properly offboarded:
    the person left but their access was never revoked.
    This is one of the top causes of data breaches.

    Returns:
      - orphaned: users with no recent audit activity
      - clean:    users with recent activity
      - inactive_days: the threshold used
    """
    from datetime import timedelta
    from sqlalchemy import func

    cutoff     = datetime.now(timezone.utc) - timedelta(days=inactive_days)
    all_users  = get_all_users(db)
    orphaned   = []
    clean      = []

    for user in all_users:
        if user.status != "Active":
            continue  # only scan Active users

        # Find most recent audit entry for this user
        last_log = (
            db.query(AuditLogDB)
            .filter(AuditLogDB.target_user_id == user.id)
            .order_by(AuditLogDB.id.desc())
            .first()
        )

        if last_log is None:
            # Never had any audit activity — definitely orphaned
            orphaned.append({
                "id"              : user.id,
                "username"        : user.username,
                "email"           : user.email,
                "department"      : user.department,
                "job_title"       : user.job_title,
                "status"          : user.status,
                "last_activity"   : None,
                "days_inactive"   : None,
                "risk"            : "HIGH",
                "reason"          : "No audit record — account may predate NexusID",
            })
        else:
            ts = last_log.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            days_inactive = (datetime.now(timezone.utc) - ts).days

            if ts < cutoff:
                orphaned.append({
                    "id"            : user.id,
                    "username"      : user.username,
                    "email"         : user.email,
                    "department"    : user.department,
                    "job_title"     : user.job_title,
                    "status"        : user.status,
                    "last_activity" : ts.isoformat(),
                    "days_inactive" : days_inactive,
                    "risk"          : "HIGH" if days_inactive > 60 else "MEDIUM",
                    "reason"        : f"No activity for {days_inactive} days",
                })
            else:
                clean.append({
                    "id"            : user.id,
                    "username"      : user.username,
                    "department"    : user.department,
                    "last_activity" : ts.isoformat(),
                    "days_inactive" : days_inactive,
                })
    actual_active_count = len(orphaned) + len(clean)

    return {
        "scanned_at"    : datetime.now(timezone.utc).isoformat(),
        "inactive_days" : inactive_days,
        "total_active"  : actual_active_count, # Changed from len(all_users)
        "orphaned_count": len(orphaned),
        "clean_count"   : len(clean),
        "orphaned"      : orphaned,
        "clean"         : clean,
    }

# ── JIT background expiry task ────────────────────────────────
async def jit_expiry_worker():
    """
    Runs every 30 seconds. Checks for expired JIT grants and
    auto-revokes them via the kill switch. This is the
    'self-destructing' mechanism — no human needed.
    """
    while True:
        await asyncio.sleep(30)
        db = SessionLocal()
        try:
            now    = datetime.now(timezone.utc)
            active = get_active_jit_grants(db)
            for grant in active:
                expires = grant.expires_at
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
                if now >= expires:
                    user = get_user(db, grant.user_id)
                    if user:
                        # Revoke the specific resource
                        response = await simulate_provisioning(
                            user.email, grant.resource_name, "revoke"
                        )
                        response["action_taken"] = "JIT_AUTO_REVOKE"
                        response["jit_grant_id"] = grant.id

                        append_log(
                            db             = db,
                            actor_id       = 0,
                            action         = "JIT_EXPIRED",
                            target_user_id = grant.user_id,
                            outcome        = "Success",
                            details        = {
                                "resource_name"   : grant.resource_name,
                                "duration_minutes": grant.duration_minutes,
                                "granted_at"      : grant.granted_at.isoformat(),
                                "expires_at"      : grant.expires_at.isoformat(),
                                "jit_grant_id"    : grant.id,
                            },
                        )
                        expire_jit_grant(db, grant.id)
        except Exception as e:
            pass  # Never crash the background worker
        finally:
            db.close()


@app.on_event("startup")
async def start_jit_worker():
    asyncio.create_task(jit_expiry_worker())


# ── JIT: request elevated access ─────────────────────────────
@app.post("/jit/request", tags=["JIT"])
async def request_jit_access(
    user_id          : int,
    resource_name    : str,
    justification    : str,
    duration_minutes : int = 60,
    db               : Session = Depends(get_db),
) -> dict:
    """
    Request Just-In-Time elevated access for a limited time window.
    Access automatically revokes when the timer expires.

    Example:
        POST /jit/request?user_id=1&resource_name=AWS_Root&justification=Hotfix+deploy&duration_minutes=30
    """
    user = get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found.")
    if user.status != "Active":
        raise HTTPException(status_code=403, detail="Only Active users can request JIT access.")
    if duration_minutes < 1 or duration_minutes > 480:
        raise HTTPException(status_code=422, detail="Duration must be between 1 and 480 minutes.")

    # Run risk assessment — JIT is always for elevated/sensitive resources
    risk = assess_request(department=user.department, resource_name=resource_name)

    # Provision access
    response = await simulate_provisioning(user.email, resource_name, "grant")

    # Create JIT grant record in SQLite
    grant = create_jit_grant(
        db               = db,
        user_id          = user_id,
        resource_name    = resource_name,
        justification    = justification,
        duration_minutes = duration_minutes,
    )

    # Audit log
    append_log(
        db             = db,
        actor_id       = user_id,
        action         = "JIT_GRANTED",
        target_user_id = user_id,
        outcome        = "Success",
        details        = {
            "resource_name"   : resource_name,
            "duration_minutes": duration_minutes,
            "expires_at"      : grant.expires_at.isoformat(),
            "risk_score"      : risk["score"],
            "risk_level"      : risk["level"],
            "jit_grant_id"    : grant.id,
            "justification"   : justification,
        },
    )

    return {
        "event"            : "JIT_GRANTED",
        "grant_id"         : grant.id,
        "user"             : user.username,
        "resource"         : resource_name,
        "duration_minutes" : duration_minutes,
        "granted_at"       : grant.granted_at.isoformat(),
        "expires_at"       : grant.expires_at.isoformat(),
        "risk_score"       : risk["score"],
        "risk_level"       : risk["level"],
        "note"             : f"Access will auto-revoke in {duration_minutes} minutes.",
    }


# ── JIT: early revoke ─────────────────────────────────────────
@app.post("/jit/{grant_id}/revoke", tags=["JIT"])
async def revoke_jit_early(
    grant_id : int,
    db       : Session = Depends(get_db),
) -> dict:
    """Manually revoke a JIT grant before it expires."""
    grant = db.query(JITAccessDB).filter(JITAccessDB.id == grant_id).first()
    if not grant:
        raise HTTPException(status_code=404, detail=f"JIT grant {grant_id} not found.")
    if grant.status != "ACTIVE":
        raise HTTPException(status_code=409, detail=f"Grant is already '{grant.status}'.")

    user     = get_user(db, grant.user_id)
    response = await simulate_provisioning(user.email, grant.resource_name, "revoke")

    revoke_jit_grant_early(db, grant_id)
    append_log(
        db             = db,
        actor_id       = grant.user_id,
        action         = "JIT_REVOKED_EARLY",
        target_user_id = grant.user_id,
        outcome        = "Success",
        details        = {
            "resource_name": grant.resource_name,
            "jit_grant_id" : grant_id,
            "reason"       : "Manually revoked before expiry",
        },
    )

    return {
        "event"    : "JIT_REVOKED_EARLY",
        "grant_id" : grant_id,
        "resource" : grant.resource_name,
        "user"     : user.username,
    }


# ── JIT: list all grants ──────────────────────────────────────
@app.get("/jit/grants", tags=["JIT"])
def get_jit_grants(db: Session = Depends(get_db)) -> list:
    """Returns all JIT grants — active, expired, and early-revoked."""
    grants = get_all_jit_grants(db)
    now    = datetime.now(timezone.utc)
    return [
        {
            "id"              : g.id,
            "user_id"         : g.user_id,
            "resource_name"   : g.resource_name,
            "justification"   : g.justification,
            "duration_minutes": g.duration_minutes,
            "granted_at"      : g.granted_at.isoformat(),
            "expires_at"      : g.expires_at.isoformat(),
            "status"          : g.status,
            "revoked_at"      : g.revoked_at.isoformat() if g.revoked_at else None,
            "seconds_remaining": max(0, int(
                (g.expires_at.replace(tzinfo=timezone.utc) - now).total_seconds()
            )) if g.status == "ACTIVE" else 0,
        }
        for g in grants
    ]
    
#----- BULK HIRING ENDPOINT  -----
@app.post("/users/bulk-hire", tags=["Lifecycle"])
async def bulk_hire_users(users: list[UserCreate], db: Session = Depends(get_db)):
    results = []
    errors = []
    
    for user_item in users:
        try:
            # Reusing your core onboarding logic
            res = await onboard_single_user(user_item, db)
            results.append(res)
        except Exception as e:
            # Capture individual failures so one bad row doesn't kill the whole batch
            errors.append({"id": user_item.id, "username": user_item.username, "error": str(e)})
            
    return {
        "success_count": len(results),
        "failed_count": len(errors),
        "details": results,
        "errors": errors
    }
    
#--- Helper function for onboarding
async def onboard_single_user(user_data: UserCreate, db: Session):
    # Check if user exists
    existing = get_user(db, user_data.id)
    if existing:
        raise Exception(f"User ID {user_data.id} already exists")

    # 1. Create User in DB
    user = create_user(db, user_data)
    
    # 2. Trigger Birthright Provisioning
    dept = user.department
    entitlements = BIRTHRIGHT_POLICIES.get(dept, ["Slack_General"])
    
    # 3. Write Audit Logs
    for ent in entitlements:
        append_log(db, actor_id=0, action="AUTO_PROVISION", 
                   target_user_id=user.id, outcome="Success",
                   details={"resource": ent, "trigger": "Onboarding"})
        
    from database import update_user_status
    user = update_user_status(db, user.id, "Active")
        
    return {
        "user_id": user.id,
        "username": user.username,
        "status": user.status,
        "provisioned": entitlements
    }
