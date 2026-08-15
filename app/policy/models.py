from pydantic import BaseModel


class PolicyDecision(BaseModel):
    category: str
    risk_level: str
    allowed: bool
    action: str
    max_attempts: int
    requires_approval: bool
    reason: str