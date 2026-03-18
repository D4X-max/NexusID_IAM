import random

async def simulate_provisioning(user_email: str, resource: str):
    """
    Simulates a 201 Created response from an external service.
    """
    # Logic: 95% success rate to simulate occasional network blips for the Audit Log
    success = random.random() < 0.95
    
    if success:
        return {
            "status_code": 201,
            "body": {
                "message": f"Access to {resource} granted for {user_email}",
                "transaction_id": f"TXN-{random.randint(1000, 9999)}"
            }
        }
    return {"status_code": 500, "body": {"error": "Connection timed out"}}