from pydantic import BaseModel
from typing import Optional


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
    matched_pattern: Optional[str] = None

class RemediationResult(BaseModel):
    action: str
    success: bool
    message: str
    new_build_number: Optional[int] = None
    verification_result: Optional[str] = None

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