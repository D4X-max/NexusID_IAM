"""
risk_engine.py  –  NexusID anomaly detection  v2
Hybrid approach:
  - IsolationForest scores requests against learned normal behaviour
  - Rule-based override catches obvious cross-department access attempts
  - Calibrated normalization using actual training score range
"""

import numpy as np
from sklearn.ensemble import IsolationForest

# ── ID mappings ───────────────────────────────────────────────
DEPARTMENT_IDS = {
    "Engineering" : 1,
    "Sales"       : 2,
    "HR"          : 3,
    "Marketing"   : 4,
    "Unknown"     : 99,
}

RESOURCE_IDS = {
    "GitHub_Repo_Access"       : 10,
    "Slack_Engineering_Channel": 11,
    "AWS_Sandbox"              : 12,
    "Salesforce_Read_Only"     : 20,
    "Slack_Sales_Channel"      : 21,
    "Workday_Basic"            : 30,
    "Slack_General"            : 31,
    "AWS_Root"                 : 99,
    "MANUAL_REVIEW_REQUIRED"   : 98,
}

# Which resource IDs each department legitimately owns
DEPARTMENT_RESOURCES = {
    1: {10, 11, 12},   # Engineering
    2: {20, 21},        # Sales
    3: {30, 31},        # HR
}

# ── Training data ─────────────────────────────────────────────
TRAINING_DATA = [
    # Engineering normal
    [1, 10, 1], [1, 10, 1], [1, 10, 1], [1, 10, 1], [1, 10, 2],
    [1, 11, 1], [1, 11, 1], [1, 11, 1], [1, 11, 1], [1, 11, 2],
    [1, 12, 1], [1, 12, 1], [1, 12, 1], [1, 12, 1], [1, 12, 2],
    # Sales normal
    [2, 20, 1], [2, 20, 1], [2, 20, 1], [2, 20, 1], [2, 20, 2],
    [2, 21, 1], [2, 21, 1], [2, 21, 1], [2, 21, 1], [2, 21, 2],
    # HR normal
    [3, 30, 1], [3, 30, 1], [3, 30, 1], [3, 30, 2],
    [3, 31, 1], [3, 31, 1], [3, 31, 1], [3, 31, 2],
    # Cross-dept anomalies at all access levels
    [1, 20, 1], [1, 20, 2], [1, 20, 3],
    [1, 21, 1], [1, 21, 2], [1, 21, 3],
    [2, 10, 1], [2, 10, 2], [2, 10, 3],
    [2, 12, 1], [2, 12, 2], [2, 12, 3],
    [3, 10, 1], [3, 10, 2], [3, 10, 3],
    [3, 12, 1], [3, 12, 2], [3, 12, 3],
    # AWS_Root — always anomalous regardless of dept
    [1, 99, 1], [1, 99, 2], [1, 99, 3],
    [2, 99, 1], [2, 99, 2], [2, 99, 3],
    [3, 99, 1], [3, 99, 2], [3, 99, 3],
]

# ── Train ─────────────────────────────────────────────────────
model = IsolationForest(n_estimators=300, contamination=0.40, random_state=42)
model.fit(TRAINING_DATA)

# Calibrate normalization to actual score range
_all_scores = model.decision_function(TRAINING_DATA)
_SCORE_MIN  = float(_all_scores.min())
_SCORE_MAX  = float(_all_scores.max())


# ── Helpers ───────────────────────────────────────────────────
def _normalize(raw: float) -> float:
    """Maps raw IsolationForest score → 0.0 (safe) to 1.0 (anomalous)."""
    return float(np.clip(
        (_SCORE_MAX - raw) / (_SCORE_MAX - _SCORE_MIN), 0.0, 1.0
    ))

def _is_cross_dept(dept_id: int, resource_id: int) -> bool:
    """Rule-based check: does this dept own this resource?"""
    if resource_id in (98, 99):
        return True                                   # always flagged
    owned = DEPARTMENT_RESOURCES.get(dept_id, set())
    if not owned:
        return True                                   # unknown dept
    return resource_id not in owned

def _get_risk_level(score: float) -> str:
    if score < 0.35:  return "LOW"
    if score < 0.65:  return "MEDIUM"
    return "HIGH"


# ── Public API ────────────────────────────────────────────────
def calculate_risk_score(dept_id: int, resource_id: int,
                         access_level: int = 1) -> dict:
    """
    Hybrid ML + rule-based risk scoring.
    Returns score 0.0 (safe) → 1.0 (high risk).
    """
    raw   = float(model.decision_function([[dept_id, resource_id, access_level]])[0])
    score = _normalize(raw)

    # Rule override: cross-dept access is always at least HIGH
    if _is_cross_dept(dept_id, resource_id):
        score = max(score, 0.70)

    level = _get_risk_level(score)

    return {
        "score"          : round(score, 3),
        "level"          : level,
        "recommendation" : "APPROVE" if level == "LOW" else "REVIEW" if level == "MEDIUM" else "BLOCK",
        "raw_score"      : round(raw, 4),
        "cross_dept"     : _is_cross_dept(dept_id, resource_id),
    }


def assess_request(department: str, resource_name: str,
                   access_level: int = 1) -> dict:
    """String-based wrapper — takes names from main.py directly."""
    dept_id     = DEPARTMENT_IDS.get(department, 99)
    resource_id = RESOURCE_IDS.get(resource_name, 98)
    result      = calculate_risk_score(dept_id, resource_id, access_level)
    result["department"]   = department
    result["resource"]     = resource_name
    result["access_level"] = access_level
    return result