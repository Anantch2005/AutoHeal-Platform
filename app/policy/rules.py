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
            "Up to three controlled remediation attempts are allowed "
            "within the safety window; the circuit breaker stops repeats."
        ),
    ),

    "NETWORK_FAILURE": PolicyRule(
        category="NETWORK_FAILURE",
        risk_level="LOW",
        allowed=True,
        action="RETRY",
        max_attempts=3,
        requires_approval=False,
        reason=(
            "Transient network failure may recover "
            "on a controlled retry."
        ),
    ),

    "WORKSPACE_FAILURE": PolicyRule(
        category="WORKSPACE_FAILURE",
        risk_level="MEDIUM",
        allowed=True,
        action="RETRY",
        max_attempts=3,
        requires_approval=False,
        reason=(
            "Fresh Jenkins execution can provide a "
            "clean workspace without modifying source code."
        ),
    ),

    "DEPENDENCY_FAILURE": PolicyRule(
        category="DEPENDENCY_FAILURE",
        risk_level="MEDIUM",
        allowed=True,
        action="RETRY_WITH_CLEAN_INSTALL",
        max_attempts=3,
        requires_approval=False,
        reason=(
            "Up to three fresh dependency-install attempts are allowed "
            "within the safety window; lockfiles are never modified."
        ),
    ),

    "DOCKER_FAILURE": PolicyRule(
        category="DOCKER_FAILURE",
        risk_level="MEDIUM",
        allowed=True,
        action="RETRY",
        max_attempts=3,
        requires_approval=False,
        reason=(
            "Transient Docker execution failures may recover on "
            "controlled retries within the safety window."
        ),
    ),

    "REGISTRY_FAILURE": PolicyRule(
        category="REGISTRY_FAILURE",
        risk_level="MEDIUM",
        allowed=True,
        action="RETRY",
        max_attempts=3,
        requires_approval=False,
        reason=(
            "Transient registry failures may recover on controlled "
            "retries within the safety window."
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