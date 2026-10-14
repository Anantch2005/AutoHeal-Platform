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
        max_attempts=1,
        requires_approval=False,
        reason="Allow one controlled retry for a known flaky-test signature.",
    ),
    "NETWORK_FAILURE": PolicyRule(
        category="NETWORK_FAILURE",
        risk_level="LOW",
        allowed=True,
        action="CONNECTIVITY_CHECK_BACKOFF_AND_RETRY",
        max_attempts=1,
        requires_approval=False,
        reason="Bounded connectivity checks and backoff are permitted.",
    ),
    "WORKSPACE_FAILURE": PolicyRule(
        category="WORKSPACE_FAILURE",
        risk_level="MEDIUM",
        allowed=True,
        action="CLEAN_WORKSPACE_AND_RETRY",
        max_attempts=1,
        requires_approval=False,
        reason="One scoped workspace recovery is permitted.",
    ),
    "DEPENDENCY_FAILURE": PolicyRule(
        category="DEPENDENCY_FAILURE",
        risk_level="MEDIUM",
        allowed=True,
        action="CLEAN_DEPENDENCY_ENV_AND_RETRY",
        max_attempts=1,
        requires_approval=False,
        reason=(
            "Recreate a supported dependency environment from existing "
            "manifests without changing dependency versions."
        ),
    ),
    "DOCKER_FAILURE": PolicyRule(
        category="DOCKER_FAILURE",
        risk_level="MEDIUM",
        allowed=True,
        action="INVALIDATE_DOCKER_CACHE_AND_RETRY",
        max_attempts=1,
        requires_approval=False,
        reason= (   
            "One cache-bypassing Docker rebuild is permitted."
            "Shared builder cache is not deleted."
        ),
    ),
    "REGISTRY_FAILURE": PolicyRule(
        category="REGISTRY_FAILURE",
        risk_level="MEDIUM",
        allowed=True,
        action="RETRY",
        max_attempts=1,
        requires_approval=False,
        reason="Allow one controlled retry for a potentially transient registry failure.",
    ),
    "DISK_FULL": PolicyRule(
        category="DISK_FULL",
        risk_level="HIGH",
        allowed=False,
        action="ESCALATE",
        max_attempts=0,
        requires_approval=True,
        reason="Agent-scoped disk cleanup is not implemented.",
    ),
    "OOM": PolicyRule(
        category="OOM",
        risk_level="HIGH",
        allowed=False,
        action="ESCALATE",
        max_attempts=0,
        requires_approval=True,
        reason="Resource resizing or agent replacement is not implemented.",
    ),
    "AGENT_FAILURE": PolicyRule(
        category="AGENT_FAILURE",
        risk_level="HIGH",
        allowed=False,
        action="ESCALATE",
        max_attempts=0,
        requires_approval=True,
        reason="Agent restart or replacement requires a privileged executor.",
    ),
    "REGISTRY_AUTH_FAILURE": PolicyRule(
        category="REGISTRY_AUTH_FAILURE",
        risk_level="HIGH",
        allowed=False,
        action="ESCALATE",
        max_attempts=0,
        requires_approval=True,
        reason="Authentication failures require credential or permission review.",
    ),
    "DOCKER_DAEMON_FAILURE": PolicyRule(
        category="DOCKER_DAEMON_FAILURE",
        risk_level="HIGH",
        allowed=False,
        action="ESCALATE",
        max_attempts=0,
        requires_approval=True,
        reason="Cache cleanup cannot repair an unavailable Docker daemon.",
    ),
    "CODE_FAILURE": PolicyRule(
        category="CODE_FAILURE",
        risk_level="HIGH",
        allowed=False,
        action="DO_NOT_HEAL",
        max_attempts=0,
        requires_approval=False,
        reason="Application and test code must not be modified automatically.",
    ),
    "UNKNOWN": PolicyRule(
        category="UNKNOWN",
        risk_level="HIGH",
        allowed=False,
        action="ESCALATE",
        max_attempts=0,
        requires_approval=True,
        reason="Unknown failures require human investigation.",
    ),
}