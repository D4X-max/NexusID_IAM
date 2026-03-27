from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, Dict, Any

# User Model: The "Source of Truth"
class User(BaseModel):
    id: int
    username: str
    email: EmailStr
    department: str        # Used for ABAC logic
    job_title: str
    manager_id: Optional[int]
    status: str = "Active" # Active, Inactive (Leaver), or Pending (Joiner)

# Access Request: For the Portal/Chatbot
class AccessRequest(BaseModel):
    user_id: int
    resource_name: str     # e.g., "AWS_S3_ReadOnly"
    justification: str
    request_type: str      # "Grant" or "Revoke"

# Audit Log: Read-only trail
class AuditLog(BaseModel):
    timestamp: datetime = datetime.now()
    actor_id: int
    action: str
    target_user_id: int
    outcome: str           # "Success" or "Failed"
    details: Dict[str, Any]  # Store the Mock JSON response here
    
class ProvisioningResult(BaseModel):
    status: str  # "Success" or "Failed"
    message: str
    resource_name: str
    action: str  # "Grant" or "Revoke"
    timestamp: datetime = datetime.now()
    details: Dict[str, Any]  # Raw response / debug info
    
class UserCreate(BaseModel):
    id: int
    username: str
    email: EmailStr
    department: str
    job_title: str
    manager_id: Optional[int]
    status: str = "Pending"