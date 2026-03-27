# NexusID — Self-Service Identity Lifecycle Automation

> Automates the full Joiner–Mover–Leaver (JML) lifecycle with simulated IAM integrations, ML-powered risk scoring, Just-In-Time access, and a SHA-256 tamper-proof audit trail.

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green?style=flat-square&logo=fastapi)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-red?style=flat-square&logo=streamlit)
![SQLite](https://img.shields.io/badge/Storage-SQLite-orange?style=flat-square&logo=sqlite)
![scikit-learn](https://img.shields.io/badge/ML-scikit--learn-F7931E?style=flat-square&logo=scikitlearn)

---

## The Problem

Manual Joiner–Mover–Leaver processes cause:

- **Delays** — average provisioning time of 2–3 days per new hire
- **Errors** — inconsistent access bundles, missing revocations
- **Orphaned accounts** — leavers whose access is never cleaned up
- **Security gaps** — standing privileges that should be time-limited

NexusID solves all four in a single portal.

---

## Demo

| Flow               | What happens                                                                                                                           |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| **Joiner**         | IT Admin hires a user → ABAC policy auto-provisions the full access bundle → audit logged                                              |
| **Mover**          | Manager requests a department transfer → approval token generated → manager approves → delta access applied (old revoked, new granted) |
| **Leaver**         | Manager or IT Admin initiates offboarding → parallel kill switch revokes all access simultaneously → user marked Inactive              |
| **JIT Access**     | Employee requests elevated access for N minutes → background worker auto-revokes on expiry                                             |
| **Orphan Scanner** | IT Admin scans for Active users with no recent activity → one-click offboard or notify manager                                         |
| **Access Review**  | Manager certifies team access is appropriate → audit logged → prevents access creep                                                    |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Streamlit Frontend  (app.py)                           │
│  ┌──────────────┐  ┌─────────────┐  ┌───────────────┐  │
│  │   Employee   │  │   Manager   │  │   IT Admin    │  │
│  │  JIT access  │  │  Approvals  │  │  Dashboard    │  │
│  │  Chatbot     │  │  Leaver req │  │  Audit log    │  │
│  │  Entitlement │  │  Access rev │  │  Orphan scan  │  │
│  └──────────────┘  └─────────────┘  └───────────────┘  │
└─────────────────────────┬───────────────────────────────┘
                          │ HTTP (REST)
┌─────────────────────────▼───────────────────────────────┐
│  FastAPI Backend  (main.py)                             │
│                                                         │
│  JML Lifecycle         Access Control                   │
│  ├── POST /users/hire  ├── POST /request-access         │
│  ├── PATCH /transfer   ├── POST /jit/request            │
│  ├── POST /approve     ├── POST /jit/{id}/revoke        │
│  ├── POST /reject      └── GET  /jit/grants             │
│  ├── PATCH /offboard                                    │
│  └── POST /terminate   Audit & Compliance               │
│                        ├── GET  /audit-log              │
│  Intelligence          ├── GET  /audit-log/verify       │
│  ├── Risk Engine       ├── GET  /users/orphaned-check   │
│  └── JIT Worker        ├── GET  /access-review          │
│                        ├── POST /access-review/certify  │
│                        └── GET  /users/{id}/timeline    │
└─────────────────────────┬───────────────────────────────┘
                          │ SQLAlchemy ORM
┌─────────────────────────▼───────────────────────────────┐
│  SQLite  (nexusid.db)                                   │
│  ├── users             (persisted user store)           │
│  ├── audit_logs        (append-only, SHA-256 hashed)    │
│  ├── pending_transfers (approval queue)                 │
│  └── jit_access        (JIT grants with expiry)         │
└─────────────────────────────────────────────────────────┘
```

---

## Features

### Core JML Lifecycle

- **Joiner** — one-click hire with ABAC birthright provisioning per department policy
- **Mover** — department transfer with manager approval gate; delta access only (revoke old, grant new)
- **Leaver** — IT Admin kill switch OR manager-initiated termination; `asyncio.gather` fires all revocations in parallel
- **Re-hire** — offboarded users can be re-hired; full audit trail preserved

### Approval Workflows

- Transfer requests generate a UUID token persisted to SQLite — survives server restarts
- Manager validates token to approve or reject
- Rejection preserves current access; approval triggers delta provisioning
- Token is marked consumed after use — cannot be replayed

### Just-In-Time (JIT) Zero Trust Access

- Employees request time-limited elevated access (1–120 minutes)
- Background `asyncio` worker auto-revokes on expiry — no human needed
- Live countdown timer in the Employee portal
- IT Admin monitor shows all active grants with force-revoke capability
- Every grant/expiry fully audit logged with `actor_id=0` (System) on auto-revoke

### ML Risk Engine

- Hybrid IsolationForest (300 estimators) + rule-based override
- Trained on department–resource–access_level triples
- Cross-department access requests get a floor score of 0.70 (HIGH)
- `AWS_Root` always scores HIGH regardless of department
- Three outcomes: `APPROVED` (LOW) → `FLAGGED` (MEDIUM) → `BLOCKED` (HIGH)

### Audit Trail

- Every action appended to `audit_logs` with SHA-256 hash over all immutable fields
- `GET /audit-log/verify` re-computes every hash and returns tampered row IDs
- Download as CSV or JSON from the IT Admin portal
- `actor_id=0` marks System-initiated events (JIT expiry, ABAC provisioning)

### Orphaned Account Scanner

- Scans all Active users for those with no audit activity in N days
- `HIGH RISK` for users with zero audit records (predated the system)
- `MEDIUM` for inactive 30–60 days, `HIGH` for >60 days
- One-click offboard or simulated Slack notification to manager

### Access Review

- `GET /access-review?review_days=90` finds users uncertified in N days
- Manager can `CERTIFY` (confirms access appropriate) or `FLAG_FOR_REDUCTION`
- Prevents access creep — permissions accumulating silently over time
- Results persist in session state; list updates in-place after each action

### Advanced Security & Bulk Lifecycle

- **Self-Service Secret Rotation** — employees can independently rotate developer API keys via the portal; reduces helpdesk overhead while maintaining a full SHA-256 audit trail
- **Risk Distribution Heatmap** — IT Admin console includes a visual risk analysis of orphaned accounts using a `pandas` background gradient; identifies high-risk departments (e.g., Engineering vs. Sales) at a glance
- **Bulk Onboarding** — support for CSV-based mass hiring; IT Admins can provision hundreds of users and their corresponding ABAC birthright access bundles in a single transaction
- **Enhanced Mover Workflow** — department transfers now support concurrent `new_job_title` updates; ensures identity records and access permissions remain synced during internal transitions

---

## Project Structure

```
NexusID_IAM/
├── main.py              # FastAPI app — all endpoints
├── app.py               # Streamlit portal — 3 role views
├── database.py          # SQLAlchemy models + helpers (4 tables)
├── models.py            # Pydantic schemas (User, AccessRequest, AuditLog)
├── risk_engine.py       # IsolationForest hybrid risk scorer
├── simulated_connectors/
│   └── mock_engine.py   # Simulated Slack + AWS IAM connectors
├── requirements.txt
├── README.md
└── nexusid.db           # SQLite database (auto-created on first run)
```

---

## Quick Start

### Prerequisites

- Python 3.10+
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/nexusid.git
cd nexusid

# Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Application

You need **two terminals** running simultaneously:

```bash
# Terminal 1 — FastAPI backend
uvicorn main:app --reload
# API runs at http://127.0.0.1:8000
# Interactive docs at http://127.0.0.1:8000/docs

# Terminal 2 — Streamlit frontend
streamlit run app.py
# Portal runs at http://localhost:8501
```

On first run, the database is created automatically and seeded with three default users:

| ID  | Username | Department  | Role              |
| --- | -------- | ----------- | ----------------- |
| 1   | dhruv    | Engineering | Backend Engineer  |
| 2   | priya    | Sales       | Account Executive |
| 3   | amit     | HR          | HR Generalist     |

---

## API Reference

### Lifecycle

| Method  | Endpoint                        | Description                                          |
| ------- | ------------------------------- | ---------------------------------------------------- |
| `POST`  | `/users/hire`                   | Hire a new user — triggers birthright provisioning   |
| `PATCH` | `/users/{id}/transfer`          | Request department transfer — returns approval token |
| `POST`  | `/transfer/{token}/approve`     | Manager approves transfer                            |
| `POST`  | `/transfer/{token}/reject`      | Manager rejects transfer                             |
| `PATCH` | `/users/{id}/offboard`          | IT Admin kill switch — parallel revocation           |
| `POST`  | `/users/{id}/terminate-request` | Manager-initiated leaver request                     |

### Access

| Method | Endpoint                      | Description                                     |
| ------ | ----------------------------- | ----------------------------------------------- |
| `POST` | `/request-access`             | Manual access grant/revoke with ML risk scoring |
| `POST` | `/jit/request`                | Request time-limited elevated access            |
| `POST` | `/jit/{id}/revoke`            | Early revoke a JIT grant                        |
| `GET`  | `/jit/grants`                 | List all JIT grants with `seconds_remaining`    |
| `GET`  | `/access-review`              | Users needing periodic access certification     |
| `POST` | `/access-review/{id}/certify` | Certify or flag a user's access                 |

### Audit & Compliance

| Method | Endpoint                     | Description                                   |
| ------ | ---------------------------- | --------------------------------------------- |
| `GET`  | `/audit-log`                 | Full audit trail                              |
| `GET`  | `/audit-log/verify`          | SHA-256 tamper detection                      |
| `GET`  | `/users`                     | All users — live status from SQLite           |
| `GET`  | `/users/{id}/timeline`       | Full chronological access history for a user  |
| `GET`  | `/users/orphaned-check`      | Scan for Active users with no recent activity |
| `POST` | `/users/{id}/notify-manager` | Simulated Slack notification to manager       |
| `GET`  | `/transfers/pending`         | All transfer requests                         |


### Administrative & Self-Service API

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/users/bulk-hire` | **Bulk Lifecycle:** Provision multiple users and their automated birthright access via a single CSV or JSON list. |
| `POST` | `/users/{id}/rotate-api-key` | **Self-Service:** Enables users to rotate their own secure developer tokens, reducing IT helpdesk overhead while maintaining audit integrity. |
| `POST` | `/demo/inject-heatmap` | **Demo Utility:** Injects a mathematical spread of HIGH and MEDIUM risk orphaned accounts to demonstrate the security heatmap. |
| `GET` | `/audit-log/verify` | **Compliance:** Triggers a comprehensive SHA-256 integrity check across all immutable logs to detect post-write tampering. |

### Example: Hire a new user

```bash
curl -X POST http://127.0.0.1:8000/users/hire \
  -H "Content-Type: application/json" \
  -d '{
    "id": 10,
    "username": "sara",
    "email": "sara@company.com",
    "department": "Engineering",
    "job_title": "SRE",
    "manager_id": 1,
    "status": "Pending"
  }'
```

### Example: Full Mover flow

```bash
# 1. Request transfer
curl -X PATCH "http://127.0.0.1:8000/users/10/transfer?new_department=Sales"
# Returns: { "approval_token": "abc-123-..." }

# 2. Approve (manager)
curl -X POST "http://127.0.0.1:8000/transfer/abc-123-.../approve?manager_id=1"

# 3. Check audit trail
curl http://127.0.0.1:8000/users/10/timeline
```

### Example: JIT access

```bash
# Grant 30-minute JIT access
curl -X POST "http://127.0.0.1:8000/jit/request?user_id=1&resource_name=AWS_Root&justification=Hotfix+deploy&duration_minutes=30"

# Check countdown
curl http://127.0.0.1:8000/jit/grants

# Access auto-revokes at expiry — check audit log
curl http://127.0.0.1:8000/audit-log
```

---

## ABAC Birthright Policies

```python
BIRTHRIGHT_POLICIES = {
    "Engineering": ["GitHub_Repo_Access", "Slack_Engineering_Channel", "AWS_Sandbox"],
    "Sales":       ["Salesforce_Read_Only", "Slack_Sales_Channel"],
    "HR":          ["Workday_Basic", "Slack_General"],
}
```

Unknown departments trigger `PENDING_APPROVAL` and require manual IT Admin action.

---

## Risk Engine

The hybrid IsolationForest scorer evaluates every access request:

```
Input:  (department, resource_name, access_level)
          ↓
     IsolationForest (300 estimators, contamination=0.40)
          ↓
     Normalize to 0.0 → 1.0
          ↓
     Rule override: cross-department? → floor at 0.70
          ↓
Output: score, level (LOW/MEDIUM/HIGH), recommendation
```

| Score range | Level  | Action                                |
| ----------- | ------ | ------------------------------------- |
| < 0.35      | LOW    | Auto-approve + provision              |
| 0.35 – 0.65 | MEDIUM | Flag for manager review               |
| ≥ 0.65      | HIGH   | Block — audit logged, no provisioning |
---

## Scalability Path

NexusID is built on production-grade patterns. Scaling is a configuration change, not an architectural rewrite:

| Component        | MVP              | Production                                                   |
| ---------------- | ---------------- | ------------------------------------------------------------ |
| Database         | SQLite           | PostgreSQL — change `DATABASE_URL` in `database.py`          |
| Frontend         | Streamlit        | React — same FastAPI endpoints, no backend changes           |
| Background tasks | asyncio loop     | Celery + Redis — drop-in for JIT expiry worker               |
| Connectors       | `mock_engine.py` | Real Slack SDK / AWS Boto3 — one function swap per connector |
| Auth             | Role selector    | OAuth2 / SAML — FastAPI middleware                           |

---

## Constraints Met

Per the hackathon brief:

- **Simulated IAM APIs only** — `mock_engine.py` returns realistic JSON, no real systems touched
- **No production systems** — entirely local, SQLite only
- **Simple roles and policies** — three departments, predefined ABAC bundles
- **Focus on logic and flow** — full JML automation with approval gates
- **Local storage** — SQLite with SQLAlchemy ORM

---

### `users`

| Column        | Type         | Description                                                                 |
|--------------|-------------|-----------------------------------------------------------------------------|
| id           | Integer (PK) | Unique User ID                                                              |
| username     | String       | Employee username                                                           |
| email        | String       | Employee contact email                                                      |
| department   | String       | Current department (Engineering, Sales, HR, Marketing, Finance)             |
| job_title    | String       | Current official role                                                       |
| manager_id   | Integer      | ID of the direct supervisor                                                 |
| status       | String       | Active, Inactive, or Pending                                                |
| created_at   | DateTime     | UTC timestamp of user creation for lifecycle reporting                      |


---

### `audit_logs` *(Append-only)*

| Column | Type | Description |
| :--- | :--- | :--- |
| **id** | Integer (PK) | Unique Log ID |
| **timestamp** | DateTime | UTC time of action |
| **actor_id** | Integer | User who performed the action (0 = System) |
| **action** | String | Action type (e.g., `JIT_GRANTED`, `AUTO_PROVISION`) |
| **target_user_id**| Integer | ID of the user affected by the action |
| **outcome** | String | Result of the action (e.g., `Success`, `Failed`, `Blocked`) |
| **details** | JSON | Raw simulated connector response or metadata |
| **integrity_hash**| String | SHA-256 cryptographic hash for tamper detection |

---

### `pending_transfers`

| Column | Type | Description |
| :--- | :--- | :--- |
| **token** | String (PK) | Unique UUID approval token |
| **user_id** | Integer | ID of the user being transferred |
| **old_department** | String | Original department before move |
| **new_department** | String | Target department after move |
| **old_job_title** | String | Original title (Preserves historical role context) |
| **new_job_title** | String | New proposed job title (Captures "Mover" phase role change) |
| **status** | String | `PENDING_APPROVAL`, `APPROVED`, or `REJECTED` |
| **created_at** | DateTime | UTC timestamp when the transfer was requested |
| **resolved_at** | DateTime | UTC timestamp when the manager took action |

---

### `jit_access`

| Column | Type | Description |
| :--- | :--- | :--- |
| **id** | Integer (PK) | Unique Grant ID |
| **user_id** | Integer | ID of the user receiving elevated access |
| **resource_name** | String | Sensitive resource (e.g., `AWS_Root`) |
| **justification** | String | Business reason for temporary access |
| **duration_minutes**| Integer | Requested window (Auto-revokes on expiry) |
| **status** | String | Current state: `ACTIVE`, `EXPIRED`, or `REVOKED_EARLY` |


## Tech Stack

| Layer           | Technology                   |
| --------------- | ---------------------------- |
| Backend API     | FastAPI + Uvicorn            |
| Frontend        | Streamlit                    |
| Database        | SQLite + SQLAlchemy          |
| ML Risk Engine  | scikit-learn IsolationForest |
| Data validation | Pydantic                     |
| Async           | Python asyncio               |
| Hashing         | hashlib SHA-256              |

---

## Requirements

```
fastapi
uvicorn[standard]
streamlit
sqlalchemy
pydantic[email]
scikit-learn
numpy
requests
```

Install with:

```bash
pip install -r requirements.txt
```

---
