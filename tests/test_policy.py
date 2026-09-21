from app.policy.engine import PolicyEngine


def test_flaky_test_is_allowed():

    engine = PolicyEngine()

    decision = engine.evaluate(
        category="FLAKY_TEST",
        classifier_action="RETRY",
    )

    assert decision.allowed is True
    assert decision.risk_level == "LOW"
    assert decision.action == "RETRY"
    assert decision.max_attempts == 3
    assert decision.requires_approval is False


def test_code_failure_is_denied():

    engine = PolicyEngine()

    decision = engine.evaluate(
        category="CODE_FAILURE",
        classifier_action="DO_NOT_HEAL",
    )

    assert decision.allowed is False
    assert decision.risk_level == "HIGH"
    assert decision.action == "DO_NOT_HEAL"
    assert decision.max_attempts == 0


def test_unknown_failure_escalates():

    engine = PolicyEngine()

    decision = engine.evaluate(
        category="UNKNOWN",
        classifier_action="ESCALATE",
    )

    assert decision.allowed is False
    assert decision.risk_level == "HIGH"
    assert decision.action == "ESCALATE"
    assert decision.requires_approval is True


def test_policy_overrides_unsafe_classifier():

    engine = PolicyEngine()

    decision = engine.evaluate(
        category="FLAKY_TEST",
        classifier_action="DO_NOT_HEAL",
    )

    assert decision.allowed is False
    assert decision.action == "DO_NOT_HEAL"
    assert decision.risk_level == "HIGH"


def test_ai_flaky_test_is_never_auto_healed():

    engine = PolicyEngine()

    decision = engine.evaluate(
        category="FLAKY_TEST",
        classifier_action="ESCALATE",
        source="ai",
        confidence=0.99,
    )

    assert decision.allowed is False
    assert decision.action == "ESCALATE"
    assert decision.requires_approval is True


def test_low_confidence_ai_is_escalated():

    engine = PolicyEngine()

    decision = engine.evaluate(
        category="NETWORK_FAILURE",
        classifier_action="ESCALATE",
        source="ai",
        confidence=0.80,
    )

    assert decision.allowed is False
    assert decision.action == "ESCALATE"
    assert decision.requires_approval is True


def test_high_confidence_ai_network_failure_can_be_allowed():

    engine = PolicyEngine()

    decision = engine.evaluate(
        category="NETWORK_FAILURE",
        classifier_action="ESCALATE",
        source="ai",
        confidence=0.95,
    )

    assert decision.allowed is True
    assert (
        decision.action
        == "CONNECTIVITY_CHECK_BACKOFF_AND_RETRY"
    )


def test_workspace_policy_uses_targeted_remediation():

    decision = PolicyEngine().evaluate(
        category="WORKSPACE_FAILURE",
        classifier_action=(
            "CLEAN_WORKSPACE_AND_RETRY"
        ),
    )

    assert decision.allowed is True
    assert (
        decision.action
        == "CLEAN_WORKSPACE_AND_RETRY"
    )
    assert decision.max_attempts == 3


def test_dependency_policy_uses_targeted_remediation():

    decision = PolicyEngine().evaluate(
        category="DEPENDENCY_FAILURE",
        classifier_action=(
            "CLEAN_DEPENDENCY_ENV_AND_RETRY"
        ),
    )

    assert decision.allowed is True
    assert (
        decision.action
        == "CLEAN_DEPENDENCY_ENV_AND_RETRY"
    )
    assert decision.max_attempts == 3


def test_docker_policy_uses_targeted_remediation():

    decision = PolicyEngine().evaluate(
        category="DOCKER_FAILURE",
        classifier_action=(
            "INVALIDATE_DOCKER_CACHE_AND_RETRY"
        ),
    )

    assert decision.allowed is True
    assert (
        decision.action
        == "INVALIDATE_DOCKER_CACHE_AND_RETRY"
    )
    assert decision.max_attempts == 3