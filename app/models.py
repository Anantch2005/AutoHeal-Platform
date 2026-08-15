from typing import Optional

from pydantic import BaseModel


class JenkinsWebhookEvent(BaseModel):
    job_name: str
    build_number: int
    build_url: Optional[str] = None
    status: str = "FAILURE"


class JenkinsBuildInfo(BaseModel):
    job_name: str
    build_number: int
    result: Optional[str] = None
    building: bool = False
    url: Optional[str] = None
    duration: Optional[int] = None
    timestamp: Optional[int] = None
    console_log: Optional[str] = None


class FailureClassification(BaseModel):
    category: str
    action: str
    reason: str
    confidence: float
    matched_pattern: str | None = None

    source: str = "rules"

    ai_root_cause: str | None = None
    ai_reasoning: str | None = None
    ai_confidence: float | None = None
    ai_evidence: list[str] = []

class RemediationResult(BaseModel):
    action: str
    success: bool
    message: str

    new_build_number: int | None = None

    verification_result: str | None = None

    queue_url: str | None = None


class Incident(BaseModel):
    incident_id: str
    source: str
    job_name: str
    build_number: int
    status: str
    build_url: Optional[str] = None
    console_log: Optional[str] = None
    classification: Optional[FailureClassification] = None
    remediation: Optional[RemediationResult] = None