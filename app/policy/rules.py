from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyRule:
    category: str
    risk_level: str
    allowed: bool
    action: str
    max_attempts: int
    requires_approval: bool
    reason: str


POLICY_RULES = {

    "FLAKY_TEST": PolicyRule(
        category="FLAKY_TEST",
        risk_level="LOW",
        allowed=True,
        action="RETRY",
        max_attempts=3,
        requires_approval=False,
        reason=(
            "Known transient test failure. "
            "Up to three controlled Jenkins retries "
            "are allowed within the safety window."
        ),
    ),

    "NETWORK_FAILURE": PolicyRule(
        category="NETWORK_FAILURE",
        risk_level="LOW",
        allowed=True,
        action="CONNECTIVITY_CHECK_BACKOFF_AND_RETRY",
        max_attempts=3,
        requires_approval=False,
        reason=(
            "Transient network failure may recover "
            "after a connectivity check and controlled backoff."
        ),
    ),

    "WORKSPACE_FAILURE": PolicyRule(
        category="WORKSPACE_FAILURE",
        risk_level="MEDIUM",
        allowed=True,
        action="CLEAN_WORKSPACE_AND_RETRY",
        max_attempts=3,
        requires_approval=False,
        reason=(
            "Workspace failures can be safely recovered "
            "by cleaning the workspace and performing "
            "a fresh checkout."
        ),
    ),

    "DEPENDENCY_FAILURE": PolicyRule(
        category="DEPENDENCY_FAILURE",
        risk_level="MEDIUM",
        allowed=True,
        action="CLEAN_DEPENDENCY_ENV_AND_RETRY",
        max_attempts=3,
        requires_approval=False,
        reason=(
            "A fresh dependency installation attempt "
            "is allowed without modifying lockfiles "
            "or dependency versions."
        ),
    ),

    "DOCKER_FAILURE": PolicyRule(
        category="DOCKER_FAILURE",
        risk_level="MEDIUM",
        allowed=True,
        action="INVALIDATE_DOCKER_CACHE_AND_RETRY",
        max_attempts=3,
        requires_approval=False,
        reason=(
            "Transient Docker execution failures may "
            "recover after invalidating the build cache."
        ),
    ),

    "REGISTRY_FAILURE": PolicyRule(
        category="REGISTRY_FAILURE",
        risk_level="MEDIUM",
        allowed=True,
        action="RETRY",
        max_attempts=1,
        requires_approval=False,
        reason=(
            "Transient registry failure may recover "
            "on one controlled retry."
        ),
    ),

    "CODE_FAILURE": PolicyRule(
        category="CODE_FAILURE",
        risk_level="HIGH",
        allowed=False,
        action="DO_NOT_HEAL",
        max_attempts=0,
        requires_approval=False,
        reason=(
            "Application or test code failure must not "
            "be automatically modified or retried as a fix."
        ),
    ),

    "UNKNOWN": PolicyRule(
        category="UNKNOWN",
        risk_level="HIGH",
        allowed=False,
        action="ESCALATE",
        max_attempts=0,
        requires_approval=True,
        reason=(
            "Unknown failure cannot be safely remediated "
            "without human review."
        ),
    ),
}