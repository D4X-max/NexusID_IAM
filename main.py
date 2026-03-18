"""
main.py  –  NexusID API  v0.5.0
Run:  uvicorn main:app --reload
Docs: http://127.0.0.1:8000/docs
"""

import sys, random
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
import asyncio
from risk_engine import assess_request
sys.path.insert(0, "../simulated_connectors")

from models   import AccessRequest, AuditLog, User
from database import (
    init_db, get_db, append_log, verify_log_integrity,
    create_transfer, get_transfer, resolve_transfer, AuditLogDB,
)
from simulated_connectors.mock_engine import mock_api_call

# ── App bootstrap ─────────────────────────────────────────────
app = FastAPI(
    title="NexusID API",
    description="Unified access provisioning with append-only SQLite audit trail.",
    version="0.5.0",
)

@app.on_event("startup")
def startup():
    init_db()   # creates nexusid.db + audit_logs table if absent


# ── In-memory user store (Phase 1 MVP) ───────────────────────
USER_DB: dict[int, User] = {
    1: User(id=1, username="dhruv", email="dhruv@company.com",
            department="Engineering", job_title="Backend Engineer",
            manager_id=None, status="Active"),
    2: User(id=2, username="priya", email="priya@company.com",
            department="Sales", job_title="Account Executive",
            manager_id=1, status="Active"),
    3: User(id=3, username="amit", email="amit@company.com",
            department="HR", job_title="HR Generalist",
            manager_id=1, status="Active"),
}

# ── Birthright policies (ABAC) ────────────────────────────────
BIRTHRIGHT_POLICIES = {
    "Engineering": ["GitHub_Repo_Access", "Slack_Engineering_Channel", "AWS_Sandbox"],
    "Sales":       ["Salesforce_Read_Only", "Slack_Sales_Channel"],
    "HR":          ["Workday_Basic", "Slack_General"],
}



# ── DEV ONLY: remove before production ───────────────────────
@app.patch("/dev/users/{user_id}/activate", tags=["Dev"])
def dev_activate(user_id: int):
    user = USER_DB.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    USER_DB[user_id] = user.model_copy(update={"status": "Active"})
    return {"user_id": user_id, "username": user.username, "status": "Active"}


# ── Helpers ───────────────────────────────────────────────────
def resolve_connector(resource_name: str, request_type: str) -> tuple[str, str]:
    name = resource_name.lower()
    service = "aws" if any(k in name for k in ("aws", "github", "workday", "salesforce")) else "slack"
    action  = "provision" if request_type.lower() == "grant" else "deprovision"
    return service, action


async def simulate_provisioning(email: str, resource_name: str, request_type: str = "grant") -> dict:
    service, action = resolve_connector(resource_name, request_type)
    username = email.split("@")[0]
    raw = mock_api_call(service=service, action=action, user=username)
    raw["status_code"]   = 201 if request_type == "grant" else 200
    raw["resource_name"] = resource_name
    return raw

async def process_joiner_event(new_user: User, db: Session) -> list:
    """
    Birthright provisioning for a new joiner.
    Every outcome — success or pending-approval — is written to SQLite.
    """
    results = []

    if new_user.department in BIRTHRIGHT_POLICIES:
        entitlements = BIRTHRIGHT_POLICIES[new_user.department]
        action_type  = "AUTO_PROVISION"
        status       = "Success"
    else:
        entitlements = ["MANUAL_REVIEW_REQUIRED"]
        action_type  = "PENDING_APPROVAL"
        status       = "Manual_Action"

    for resource in entitlements:
        if action_type == "AUTO_PROVISION":
            response = await simulate_provisioning(new_user.email, resource)
        else:
            response = {
                "status_code"  : 202,
                "resource_name": resource,
                "body"         : {"message": f"Admin alert sent — no policy for '{new_user.department}'"},
            }

        # ── Write to SQLite (append-only, hashed) ────────────
        row = append_log(
            db             = db,
            actor_id       = 0,          # 0 = System
            action         = action_type,
            target_user_id = new_user.id,
            outcome        = status,
            details        = response,
        )
        results.append(row)

    return results



async def process_mover_event(user: User, old_department: str, db: Session) -> list:
    """
    Calculates the delta between old and new department access,
    revokes first, then provisions, and writes everything to SQLite.
    """
    old_access = BIRTHRIGHT_POLICIES.get(old_department)
    new_access = BIRTHRIGHT_POLICIES.get(user.department)

    # Gap 3 fix: unknown department on either side → flag for manual review
    if old_access is None or new_access is None:
        unknown = old_department if old_access is None else user.department
        row = append_log(
            db             = db,
            actor_id       = 0,
            action         = "MOVER_REVIEW_REQUIRED",
            target_user_id = user.id,
            outcome        = "Manual_Action",
            details        = {"reason": f"No policy defined for '{unknown}'"},
        )
        return [row]

    to_revoke = set(old_access) - set(new_access)
    to_grant  = set(new_access) - set(old_access)
    # intersection = access kept silently — no churn, no log noise
    results = []

    # Gap 1 + security first: revoke via mock engine, not a hardcoded dict
    for resource in to_revoke:
        response = await simulate_provisioning(user.email, resource, "revoke")
        response["action_taken"] = "REVOKE"
        row = append_log(                                    # Gap 2 fix: persist to SQLite
            db             = db,
            actor_id       = 0,
            action         = "AUTO_REVOKE",
            target_user_id = user.id,
            outcome        = "Success" if response["status_code"] == 200 else "Failed",
            details        = response,
        )
        results.append(row)

    # Then provision new access
    for resource in to_grant:
        response = await simulate_provisioning(user.email, resource, "grant")
        response["action_taken"] = "GRANT"
        row = append_log(
            db             = db,
            actor_id       = 0,
            action         = "AUTO_PROVISION",
            target_user_id = user.id,
            outcome        = "Success" if response["status_code"] == 201 else "Failed",
            details        = response,
        )
        results.append(row)

    return results


async def _revoke_one(user, resource, db):
    response = await simulate_provisioning(user.email, resource, "revoke")
    response["action_taken"] = "EMERGENCY_REVOKE"

    row = append_log(
        db=db,
        actor_id=0,
        action="EMERGENCY_REVOKE",
        target_user_id=user.id,
        outcome="Success" if response["status_code"] == 200 else "Failed",
        details=response,
    )

    return row

async def trigger_leaver_kill_switch(
    user: User,
    current_entitlements: list[str],
    db: Session,
) -> list:

    # Run all revocations concurrently
    results = await asyncio.gather(
        *[_revoke_one(user, resource, db) for resource in current_entitlements]
    )

    # Mark user inactive AFTER all revokes
    USER_DB[user.id] = user.model_copy(update={"status": "Inactive"})

    return results


# ── Health ────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {"message": "NexusID API is live", "version": "0.5.0", "db": "SQLite (append-only)"}


# ── Hire endpoint ─────────────────────────────────────────────
@app.post("/users/hire", tags=["Lifecycle"], status_code=201)
async def hire_user(new_user: User, db: Session = Depends(get_db)) -> dict:
    """
    Creates a new user and triggers birthright provisioning.
    All outcomes are persisted to the SQLite audit log.

    Known dept example:
    ```json
    {"id":10,"username":"riya","email":"riya@company.com",
     "department":"Engineering","job_title":"SRE","manager_id":1,"status":"Pending"}
    ```
    Unknown dept example:
    ```json
    {"id":11,"username":"karan","email":"karan@company.com",
     "department":"Marketing","job_title":"Growth Lead","manager_id":1,"status":"Pending"}
    ```
    """
    if new_user.id in USER_DB:
        raise HTTPException(status_code=409, detail=f"User ID {new_user.id} already exists.")
    if new_user.status != "Pending":
        raise HTTPException(status_code=422, detail="New hires must arrive with status 'Pending'.")

    USER_DB[new_user.id] = new_user
    logs = await process_joiner_event(new_user, db)

    all_ok = all(row.outcome in ("Success", "Manual_Action") for row in logs)
    final_status = "Active" if all_ok else "Provisioning_Failed"
    USER_DB[new_user.id] = new_user.model_copy(update={"status": final_status})

    response = {
        "event"                   : "HIRE",
        "user_id"                 : new_user.id,
        "username"                : new_user.username,
        "department"              : new_user.department,
        "status"                  : final_status,
        "entitlements_provisioned": [row.details.get("resource_name") for row in logs],
        "audit_entries_written"   : len(logs),
        "db"                      : "SQLite",
        "timestamp"               : datetime.now(timezone.utc).isoformat(),
    }

    if new_user.department not in BIRTHRIGHT_POLICIES:
        response["warning"] = (
            f"No birthright policy for '{new_user.department}'. "
            f"PENDING_APPROVAL logged. IT admin action required."
        )

    return response


@app.post("/request-access", tags=["Access"])
def request_access(payload: AccessRequest, db: Session = Depends(get_db)) -> dict:
    """
    Manual Grant / Revoke with ML risk scoring.
    HIGH risk → blocked + audit logged.
    MEDIUM risk → flagged for review + audit logged.
    LOW risk → provisioned immediately + audit logged.
    """
    # 1. Validate user
    user = USER_DB.get(payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User {payload.user_id} not found.")
    if user.status != "Active":
        raise HTTPException(status_code=403,
            detail=f"User '{user.username}' is '{user.status}'. Only Active users can request access.")
    if payload.request_type not in ("Grant", "Revoke"):
        raise HTTPException(status_code=422, detail="request_type must be 'Grant' or 'Revoke'.")

    # 2. Risk assessment — uses department from USER_DB, not AccessRequest
    risk = assess_request(
        department   = user.department,
        resource_name= payload.resource_name,
        access_level = 1,
    )

    # 3. Policy Decision Point (PDP)
    if risk["level"] == "HIGH":
        append_log(
            db             = db,
            actor_id       = payload.user_id,
            action         = f"BLOCKED → {payload.resource_name}",
            target_user_id = payload.user_id,
            outcome        = "Blocked",
            details        = {
                "reason"        : "Anomaly detected by risk engine",
                "risk_score"    : risk["score"],
                "risk_level"    : risk["level"],
                "resource_name" : payload.resource_name,
                "justification" : payload.justification,
            },
        )
        return {
            "status"         : "BLOCKED",
            "reason"         : "Anomaly detected — request exceeds risk threshold.",
            "risk_score"     : risk["score"],
            "risk_level"     : risk["level"],
            "recommendation" : risk["recommendation"],
            "audit_logged"   : True,
        }

    if risk["level"] == "MEDIUM":
        append_log(
            db             = db,
            actor_id       = payload.user_id,
            action         = f"FLAGGED → {payload.resource_name}",
            target_user_id = payload.user_id,
            outcome        = "Flagged",
            details        = {
                "reason"        : "Medium risk — pending manual review",
                "risk_score"    : risk["score"],
                "risk_level"    : risk["level"],
                "resource_name" : payload.resource_name,
                "justification" : payload.justification,
            },
        )
        return {
            "status"         : "FLAGGED",
            "reason"         : "Medium risk — flagged for manual review before provisioning.",
            "risk_score"     : risk["score"],
            "risk_level"     : risk["level"],
            "recommendation" : risk["recommendation"],
            "audit_logged"   : True,
        }

    # 4. LOW risk — proceed with provisioning
    service, action = resolve_connector(payload.resource_name, payload.request_type)
    mock_response   = mock_api_call(service=service, action=action, user=user.username)
    outcome         = "Success" if mock_response.get("status") != "error" else "Failed"
    nexus_id        = f"NXS-{service.upper()}-{random.randint(100000, 999999)}"

    append_log(
        db             = db,
        actor_id       = payload.user_id,
        action         = f"{payload.request_type} → {payload.resource_name}",
        target_user_id = payload.user_id,
        outcome        = outcome,
        details        = mock_response | {
            "risk_score" : risk["score"],
            "risk_level" : risk["level"],
        },
    )

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

# ── Leaver offboard endpoint ──────────────────────────────────
@app.patch("/users/{user_id}/offboard", tags=["Lifecycle"])
async def offboard_user(
    user_id: int,
    db     : Session = Depends(get_db),
) -> dict:
    """
    Kill switch — immediately revokes ALL current department entitlements
    and marks the user Inactive. No approval gate: speed is the priority.

    Example:
        PATCH /users/1/offboard
    """
    user = USER_DB.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found.")
    if user.status == "Inactive":
        raise HTTPException(status_code=409,
            detail=f"User '{user.username}' is already Inactive.")

    # Resolve their current entitlements from BIRTHRIGHT_POLICIES
    current_entitlements = BIRTHRIGHT_POLICIES.get(user.department, ["Slack_General"])

    logs = await trigger_leaver_kill_switch(user, current_entitlements, db)

    return {
        "event"    : "LEAVER",
        "user_id"  : user_id,
        "username" : user.username,
        "department": user.department,
        "status"   : "Inactive",
        "revoked"  : [r.details.get("resource_name") for r in logs],
        "all_revoked" : all(r.outcome == "Success" for r in logs),
        "audit_entries": len(logs),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }



# ── Mover event ───────────────────────────────────────────────
@app.post("/users/move", tags=["Lifecycle"])
async def move_user(
    user_id        : int,
    new_department : str,
    db             : Session = Depends(get_db),
) -> dict:
    """
    Transfers a user to a new department.
    Revokes old-dept access, provisions new-dept access — delta only.

    Example:
        POST /users/move?user_id=1&new_department=Sales
    """
    # 1. Validate user exists and is Active
    user = USER_DB.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found.")
    if user.status != "Active":
        raise HTTPException(status_code=403,
            detail=f"User '{user.username}' is '{user.status}'. Only Active users can be moved.")
    if user.department == new_department:
        raise HTTPException(status_code=409,
            detail=f"User '{user.username}' is already in '{new_department}'. No move needed.")

    # 2. Snapshot old department before mutating
    old_department = user.department

    # 3. Update user in DB
    USER_DB[user_id] = user.model_copy(update={"department": new_department})
    updated_user     = USER_DB[user_id]

    # 4. Run delta provisioning (revoke old → grant new)
    logs = await process_mover_event(updated_user, old_department, db)

    # 5. Detect if it landed in manual review
    needs_review = any(row.action == "MOVER_REVIEW_REQUIRED" for row in logs)

    return {
        "event"          : "MOVER",
        "user_id"        : user_id,
        "username"        : user.username,
        "old_department" : old_department,
        "new_department" : new_department,
        "revoked"        : [r.details.get("resource_name") for r in logs if r.action == "AUTO_REVOKE"],
        "granted"        : [r.details.get("resource_name") for r in logs if r.action == "AUTO_PROVISION"],
        "needs_review"   : needs_review,
        "audit_entries"  : len(logs),
        "db"             : "SQLite",
        "timestamp"      : datetime.now(timezone.utc).isoformat(),
    }


# ── Manual access request ─────────────────────────────────────
@app.post("/request-access", tags=["Access"])
def request_access(payload: AccessRequest, db: Session = Depends(get_db)) -> dict:
    """Manual Grant / Revoke for an existing Active user."""
    user = USER_DB.get(payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User {payload.user_id} not found.")
    if user.status != "Active":
        raise HTTPException(status_code=403,
            detail=f"User '{user.username}' is '{user.status}'. Only Active users can request access.")
    if payload.request_type not in ("Grant", "Revoke"):
        raise HTTPException(status_code=422, detail="request_type must be 'Grant' or 'Revoke'.")

    service, action = resolve_connector(payload.resource_name, payload.request_type)
    mock_response   = mock_api_call(service=service, action=action, user=user.username)
    outcome         = "Success" if mock_response.get("status") != "error" else "Failed"
    nexus_id        = f"NXS-{service.upper()}-{random.randint(100000, 999999)}"

    append_log(
        db             = db,
        actor_id       = payload.user_id,
        action         = f"{payload.request_type} → {payload.resource_name}",
        target_user_id = payload.user_id,
        outcome        = outcome,
        details        = mock_response,
    )

    return {
        "nexus_id"           : nexus_id,
        "outcome"            : outcome,
        "user"               : user.username,
        "department"         : user.department,
        "resource_name"      : payload.resource_name,
        "request_type"       : payload.request_type,
        "justification"      : payload.justification,
        "connector_response" : mock_response,
        "audit_logged"       : True,
        "db"                 : "SQLite",
    }


# ── Audit log viewer ──────────────────────────────────────────
@app.get("/audit-log", tags=["Audit"])
def get_audit_log(db: Session = Depends(get_db)) -> list:
    """Returns all audit entries from SQLite, oldest first."""
    from database import AuditLogDB
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
            "integrity_hash": r.integrity_hash[:16] + "…",  # truncated for display
        }
        for r in rows
    ]


# ── Integrity check ───────────────────────────────────────────



import uuid

# ── Pending transfer store ────────────────────────────────────



# ── Transfer endpoint (requires manager approval) ─────────────
@app.patch("/users/{user_id}/transfer", tags=["Lifecycle"])
async def transfer_user(
    user_id        : int,
    new_department : str,
    db             : Session = Depends(get_db),
) -> dict:
    """
    Initiates a department transfer — does NOT execute immediately.
    Creates a pending request in SQLite and returns an approval token.
    Token survives server restarts.
    """
    user = USER_DB.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found.")
    if user.status != "Active":
        raise HTTPException(status_code=403, detail=f"User '{user.username}' must be Active.")
    if user.department == new_department:
        raise HTTPException(status_code=409, detail="User is already in that department.")
    if user.manager_id is None:
        raise HTTPException(status_code=422, detail="User has no manager set. Cannot route for approval.")

    token = str(uuid.uuid4())

    # Sprint 3: persist to SQLite instead of in-memory dict
    create_transfer(
        db             = db,
        token          = token,
        user_id        = user_id,
        old_department = user.department,
        new_department = new_department,
        requested_by   = user_id,
        approver_id    = user.manager_id,
    )

    append_log(
        db             = db,
        actor_id       = user_id,
        action         = "TRANSFER_REQUESTED",
        target_user_id = user_id,
        outcome        = "Pending",
        details        = {"token": token, "old": user.department, "new": new_department},
    )

    return {
        "status"         : "PENDING_APPROVAL",
        "message"        : f"Persisted to DB. Awaiting manager (id={user.manager_id}) approval.",
        "approval_token" : token,
        "user"           : user.username,
        "old_department" : user.department,
        "new_department" : new_department,
        "note"           : "Token survives server restarts — stored in SQLite.",
    }


# ── Manager approval endpoint ─────────────────────────────────
@app.post("/transfer/{token}/approve", tags=["Lifecycle"])
async def approve_transfer(
    token      : str,
    manager_id : int,
    db         : Session = Depends(get_db),
) -> dict:
    """
    Manager approves a pending transfer using the token.
    Reads from SQLite — works even after a server restart.
    Triggers process_mover_event on approval.
    """
    # Sprint 3: read from SQLite, not in-memory dict
    request = get_transfer(db, token)
    if not request:
        raise HTTPException(status_code=404, detail="Approval token not found or already used.")
    if request.status != "PENDING_APPROVAL":
        raise HTTPException(status_code=409, detail=f"Transfer is already '{request.status}'.")
    if manager_id != request.approver_id:
        raise HTTPException(status_code=403,
            detail=f"Manager ID {manager_id} is not the designated approver for this request.")

    user    = USER_DB[request.user_id]
    old_dep = request.old_department
    new_dep = request.new_department

    USER_DB[user.id] = user.model_copy(update={"department": new_dep})
    logs = await process_mover_event(USER_DB[user.id], old_dep, db)

    # Mark token consumed in SQLite
    resolve_transfer(db, token, "APPROVED")

    append_log(
        db             = db,
        actor_id       = manager_id,
        action         = "TRANSFER_APPROVED",
        target_user_id = user.id,
        outcome        = "Success",
        details        = {"token": token, "old": old_dep, "new": new_dep, "approver": manager_id},
    )

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
    
@app.get("/audit-log/verify", tags=["Audit"])
def verify_integrity(db: Session = Depends(get_db)) -> dict:
    """
    Re-computes SHA-256 hashes for every row and compares to stored values.
    Any tampered rows will appear in the 'tampered' list.
    A clean DB returns: { "total": N, "ok": N, "tampered": [] }
    """
    return verify_log_integrity(db)