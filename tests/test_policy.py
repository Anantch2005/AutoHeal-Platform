
from app.policy.engine import PolicyEngine


def test_flaky_test_allows_one_retry():
    decision = PolicyEngine().evaluate(
        category="FLAKY_TEST",
        classifier_action="RETRY",
    )
    assert decision.allowed is True
    assert decision.action == "RETRY"
    assert decision.max_attempts == 1
    assert decision.requires_approval is False


def test_code_failure_is_never_auto_healed():
    decision = PolicyEngine().evaluate(
        category="CODE_FAILURE",
        classifier_action="DO_NOT_HEAL",
    )
    assert decision.allowed is False
    assert decision.action == "DO_NOT_HEAL"
    assert decision.max_attempts == 0


def test_unknown_failure_escalates():
    decision = PolicyEngine().evaluate(
        category="UNKNOWN",
        classifier_action="ESCALATE",
    )
    assert decision.allowed is False
    assert decision.action == "ESCALATE"
    assert decision.max_attempts == 0
    assert decision.requires_approval is True


def test_classifier_cannot_make_flaky_retry_unsafe():
    decision = PolicyEngine().evaluate(
        category="FLAKY_TEST",
        classifier_action="DO_NOT_HEAL",
    )
    assert decision.allowed is False
    assert decision.action == "DO_NOT_HEAL"


def test_ai_cannot_approve_flaky_test_from_one_failure():
    decision = PolicyEngine().evaluate(
        category="FLAKY_TEST",
        classifier_action="RETRY",
        source="ai",
        confidence=0.99,
    )
    assert decision.allowed is False
    assert decision.action == "ESCALATE"
    assert decision.requires_approval is True


def test_low_confidence_ai_escalates():
    decision = PolicyEngine().evaluate(
        category="NETWORK_FAILURE",
        classifier_action="ESCALATE",
        source="ai",
        confidence=0.80,
    )
    assert decision.allowed is False
    assert decision.action == "ESCALATE"


def test_high_confidence_ai_cannot_override_policy():
    decision = PolicyEngine().evaluate(
        category="REGISTRY_AUTH_FAILURE",
        classifier_action="ESCALATE",
        source="ai",
        confidence=0.99,
    )
    assert decision.allowed is False
    assert decision.action == "ESCALATE"


def test_network_recovery_has_bounded_attempts():
    decision = PolicyEngine().evaluate(
        category="NETWORK_FAILURE",
        classifier_action="CONNECTIVITY_CHECK_BACKOFF_AND_RETRY",
    )
    assert decision.allowed is True
    assert decision.action == "CONNECTIVITY_CHECK_BACKOFF_AND_RETRY"
    assert decision.max_attempts == 2


def test_workspace_recovery_allows_one_attempt():
    decision = PolicyEngine().evaluate(
        category="WORKSPACE_FAILURE",
        classifier_action="CLEAN_WORKSPACE_AND_RETRY",
    )
    assert decision.allowed is True
    assert decision.action == "CLEAN_WORKSPACE_AND_RETRY"
    assert decision.max_attempts == 1


def test_dependency_recovery_allows_one_attempt():
    decision = PolicyEngine().evaluate(
        category="DEPENDENCY_FAILURE",
        classifier_action="CLEAN_DEPENDENCY_ENV_AND_RETRY",
    )
    assert decision.allowed is True
    assert decision.action == "CLEAN_DEPENDENCY_ENV_AND_RETRY"
    assert decision.max_attempts == 1


def test_docker_cache_recovery_allows_one_attempt():
    decision = PolicyEngine().evaluate(
        category="DOCKER_FAILURE",
        classifier_action="INVALIDATE_DOCKER_CACHE_AND_RETRY",
    )
    assert decision.allowed is True
    assert decision.action == "INVALIDATE_DOCKER_CACHE_AND_RETRY"
    assert decision.max_attempts == 1


def test_registry_authentication_is_never_auto_healed():
    decision = PolicyEngine().evaluate(
        category="REGISTRY_AUTH_FAILURE",
        classifier_action="ESCALATE",
    )
    assert decision.allowed is False
    assert decision.action == "ESCALATE"
    assert decision.max_attempts == 0


def test_docker_daemon_failure_is_never_auto_healed():
    decision = PolicyEngine().evaluate(
        category="DOCKER_DAEMON_FAILURE",
        classifier_action="ESCALATE",
    )
    assert decision.allowed is False
    assert decision.action == "ESCALATE"
    assert decision.max_attempts == 0
