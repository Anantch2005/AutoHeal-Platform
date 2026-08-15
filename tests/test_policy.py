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
    assert decision.max_attempts == 1
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