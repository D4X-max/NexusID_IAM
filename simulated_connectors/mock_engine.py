"""
Mock Engine - Simulates AWS and Slack API responses
Usage:
    python mock_engine.py --service slack --action provision --user dhruv
    python mock_engine.py --service aws   --action provision --user dhruv
    python mock_engine.py --service slack --action status    --user dhruv
"""

import json
import argparse
import random
from datetime import datetime, timezone

# ─────────────────────────────────────────────
#  Simulated response templates
# ─────────────────────────────────────────────

SLACK_RESPONSES = {
    "provision": {
        "status": "provisioned",
        "resource": "slack_pro",
        "user": "{user}",
        "workspace": "mock-workspace.slack.com",
        "channel": "#general",
        "timestamp": "{ts}",
        "request_id": "{req_id}",
    },
    "status": {
        "status": "active",
        "resource": "slack_pro",
        "user": "{user}",
        "workspace": "mock-workspace.slack.com",
        "last_seen": "{ts}",
        "request_id": "{req_id}",
    },
    "deprovision": {
        "status": "deprovisioned",
        "resource": "slack_pro",
        "user": "{user}",
        "timestamp": "{ts}",
        "request_id": "{req_id}",
    },
}

AWS_RESPONSES = {
    "provision": {
        "status": "provisioned",
        "resource": "aws_ec2_instance",
        "user": "{user}",
        "instance_id": "i-{rand}",
        "region": "ap-south-1",
        "ami": "ami-0abcdef1234567890",
        "instance_type": "t3.micro",
        "timestamp": "{ts}",
        "request_id": "{req_id}",
    },
    "status": {
        "status": "running",
        "resource": "aws_ec2_instance",
        "user": "{user}",
        "instance_id": "i-{rand}",
        "region": "ap-south-1",
        "uptime_hours": 42,
        "timestamp": "{ts}",
        "request_id": "{req_id}",
    },
    "deprovision": {
        "status": "terminated",
        "resource": "aws_ec2_instance",
        "user": "{user}",
        "instance_id": "i-{rand}",
        "region": "ap-south-1",
        "timestamp": "{ts}",
        "request_id": "{req_id}",
    },
}

SERVICE_MAP = {
    "slack": SLACK_RESPONSES,
    "aws":   AWS_RESPONSES,
}

# ─────────────────────────────────────────────
#  Core mock call function
# ─────────────────────────────────────────────

def mock_api_call(service: str, action: str, user: str) -> dict:
    service = service.lower()
    action  = action.lower()

    if service not in SERVICE_MAP:
        return {"status": "error", "code": 400,
                "message": f"Unknown service '{service}'. Available: {list(SERVICE_MAP.keys())}"}

    actions = SERVICE_MAP[service]
    if action not in actions:
        return {"status": "error", "code": 400,
                "message": f"Unknown action '{action}' for {service}. Available: {list(actions.keys())}"}

    rand_hex = f"{random.randint(0x100000000000, 0xffffffffffff):012x}"
    ts       = datetime.now(timezone.utc).isoformat()
    req_id   = f"req-{random.randint(10000, 99999)}"

    def fill(val):
        if isinstance(val, str):
            return (val.replace("{user}", user)
                       .replace("{ts}", ts)
                       .replace("{req_id}", req_id)
                       .replace("{rand}", rand_hex))
        return val

    return {k: fill(v) for k, v in actions[action].items()}


# ─────────────────────────────────────────────
#  CLI entry point
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Mock Engine – simulates AWS / Slack API responses")
    parser.add_argument("--service", default="slack", choices=["slack", "aws"])
    parser.add_argument("--action",  default="provision", choices=["provision", "status", "deprovision"])
    parser.add_argument("--user",    default="dhruv")
    args = parser.parse_args()

    response = mock_api_call(service=args.service, action=args.action, user=args.user)
    print(json.dumps(response, indent=2))


if __name__ == "__main__":
    main()