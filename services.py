from models import AccessRequest, ProvisioningResult
from datetime import datetime

def simulate_provisioning(req: AccessRequest) -> ProvisioningResult:
    # Mock logic
    return ProvisioningResult(
        status="Success",
        message=f"{req.request_type} successful for {req.resource_name}",
        resource_name=req.resource_name,
        action=req.request_type,
        timestamp=datetime.utcnow(),
        details={
            "system": "MockIAM",
            "processed": True
        }
    )