"""
database.py  –  SQLite + SQLAlchemy setup for NexusID  v2
Tables:
  audit_logs       – append-only, SHA-256 hashed
  pending_transfers – persisted approval queue (survives restarts)
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


# ── Table 1: Append-only audit log ───────────────────────────
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


# ── Table 2: Pending transfers (survives restarts) ────────────
class PendingTransferDB(Base):
    """
    Stores transfer requests that are awaiting manager approval.
    Replaces the in-memory PENDING_TRANSFERS dict.
    Status values: PENDING_APPROVAL | APPROVED | REJECTED | EXPIRED
    """
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


# ── Hashing ───────────────────────────────────────────────────
def _compute_hash(actor_id, action, target_user_id, outcome, details, timestamp):
    payload = json.dumps({
        "actor_id"       : actor_id,
        "action"         : action,
        "target_user_id" : target_user_id,
        "outcome"        : outcome,
        "details"        : details,
        "timestamp"      : timestamp.isoformat(),
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


# ── Public helpers ────────────────────────────────────────────
def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
        ts = row["timestamp"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        expected = _compute_hash(
            row["actor_id"], row["action"], row["target_user_id"],
            row["outcome"], row["details"], ts,
        )
        if expected != row["integrity_hash"]:
            tampered.append(row["id"])
    return {"total": len(rows), "ok": len(rows) - len(tampered), "tampered": tampered}


# ── Pending transfer helpers ──────────────────────────────────
def create_transfer(db, token, user_id, old_department, new_department,
                    requested_by, approver_id) -> PendingTransferDB:
    row = PendingTransferDB(
        token          = token,
        user_id        = user_id,
        old_department = old_department,
        new_department = new_department,
        requested_by   = requested_by,
        approver_id    = approver_id,
        status         = "PENDING_APPROVAL",
        created_at     = datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_transfer(db, token) -> PendingTransferDB | None:
    return db.query(PendingTransferDB).filter(PendingTransferDB.token == token).first()


def resolve_transfer(db, token, status) -> PendingTransferDB:
    row = db.query(PendingTransferDB).filter(PendingTransferDB.token == token).first()
    row.status      = status
    row.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row