"""
database.py  –  NexusID SQLite + SQLAlchemy  v4
Tables:
  users             – persisted user store (survives restarts)
  audit_logs        – append-only, SHA-256 hashed
  pending_transfers – approval queue (survives restarts)
"""

from sqlalchemy import (
    create_engine, Column, Integer, String,
    DateTime, JSON, event, text
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.engine import Engine
from datetime import datetime, timezone
import hashlib, json

DATABASE_URL = "sqlite:///./nexusid.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

@event.listens_for(Engine, "connect")
def set_sqlite_pragmas(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ── Table 1: Users ────────────────────────────────────────────
class UserDB(Base):
    """
    Persistent user store — replaces the in-memory USER_DB dict.
    Survives server restarts. Status updated in-place on hire/move/offboard.
    """
    __tablename__ = "users"

    id          = Column(Integer, primary_key=True, index=True)
    username    = Column(String,  nullable=False)
    email       = Column(String,  nullable=False)
    department  = Column(String,  nullable=False)
    job_title   = Column(String,  nullable=False)
    manager_id  = Column(Integer, nullable=True)
    status      = Column(String,  nullable=False, default="Pending")


# ── Table 2: Audit log ────────────────────────────────────────
class AuditLogDB(Base):
    __tablename__ = "audit_logs"

    id             = Column(Integer,  primary_key=True, index=True)
    timestamp      = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    actor_id       = Column(Integer,  nullable=False)
    action         = Column(String,   nullable=False)
    target_user_id = Column(Integer,  nullable=False)
    outcome        = Column(String,   nullable=False)
    details        = Column(JSON,     nullable=False)
    integrity_hash = Column(String,   nullable=False)


# ── Table 3: Pending transfers ────────────────────────────────
class PendingTransferDB(Base):
    __tablename__ = "pending_transfers"

    token          = Column(String,   primary_key=True, index=True)
    user_id        = Column(Integer,  nullable=False)
    old_department = Column(String,   nullable=False)
    new_department = Column(String,   nullable=False)
    requested_by   = Column(Integer,  nullable=False)
    approver_id    = Column(Integer,  nullable=False)
    status         = Column(String,   nullable=False, default="PENDING_APPROVAL")
    created_at     = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    resolved_at    = Column(DateTime, nullable=True)


# ── Hash helpers ──────────────────────────────────────────────
def _normalize_ts(ts) -> str:
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts)
    return ts.replace(tzinfo=None).isoformat()

def _normalize_details(details) -> dict:
    if isinstance(details, str):
        return json.loads(details)
    return details

def _compute_hash(actor_id, action, target_user_id, outcome, details, timestamp) -> str:
    payload = json.dumps({
        "actor_id"       : actor_id,
        "action"         : action,
        "target_user_id" : target_user_id,
        "outcome"        : outcome,
        "details"        : _normalize_details(details),
        "timestamp"      : _normalize_ts(timestamp),
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


# ── DB lifecycle ──────────────────────────────────────────────
def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── User helpers ──────────────────────────────────────────────
def get_all_users(db) -> list:
    return db.query(UserDB).order_by(UserDB.id).all()

def get_user(db, user_id: int):
    return db.query(UserDB).filter(UserDB.id == user_id).first()

def upsert_user(db, id, username, email, department,
                job_title, manager_id, status) -> UserDB:
    existing = db.query(UserDB).filter(UserDB.id == id).first()
    if existing:
        existing.username   = username
        existing.email      = email
        existing.department = department
        existing.job_title  = job_title
        existing.manager_id = manager_id
        existing.status     = status
    else:
        existing = UserDB(
            id=id, username=username, email=email,
            department=department, job_title=job_title,
            manager_id=manager_id, status=status,
        )
        db.add(existing)
    db.commit()
    db.refresh(existing)
    return existing

def update_user_status(db, user_id: int, status: str) -> UserDB:
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if user:
        user.status = status
        db.commit()
        db.refresh(user)
    return user

def update_user_department(db, user_id: int, department: str) -> UserDB:
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if user:
        user.department = department
        db.commit()
        db.refresh(user)
    return user


# ── Audit log helpers ─────────────────────────────────────────
def append_log(db, actor_id, action, target_user_id, outcome, details,
               timestamp=None) -> AuditLogDB:
    ts = timestamp or datetime.now(timezone.utc)
    row = AuditLogDB(
        timestamp      = ts,
        actor_id       = actor_id,
        action         = action,
        target_user_id = target_user_id,
        outcome        = outcome,
        details        = details,
        integrity_hash = _compute_hash(actor_id, action, target_user_id, outcome, details, ts),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

def verify_log_integrity(db) -> dict:
    rows     = db.execute(text("SELECT * FROM audit_logs")).mappings().all()
    tampered = []
    for row in rows:
        expected = _compute_hash(
            row["actor_id"], row["action"], row["target_user_id"],
            row["outcome"], row["details"], row["timestamp"],
        )
        if expected != row["integrity_hash"]:
            tampered.append(row["id"])
    return {"total": len(rows), "ok": len(rows) - len(tampered), "tampered": tampered}


# ── Transfer helpers ──────────────────────────────────────────
def create_transfer(db, token, user_id, old_department, new_department,
                    requested_by, approver_id) -> PendingTransferDB:
    row = PendingTransferDB(
        token=token, user_id=user_id,
        old_department=old_department, new_department=new_department,
        requested_by=requested_by, approver_id=approver_id,
        status="PENDING_APPROVAL", created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

def get_transfer(db, token):
    return db.query(PendingTransferDB).filter(PendingTransferDB.token == token).first()

def resolve_transfer(db, token, status) -> PendingTransferDB:
    row = db.query(PendingTransferDB).filter(PendingTransferDB.token == token).first()
    row.status      = status
    row.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row