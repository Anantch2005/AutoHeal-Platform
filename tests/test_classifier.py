from app.classifier.classifier import FailureClassifier


classifier = FailureClassifier()


def test_flaky_test():

    log = """
    FAILED test_calculator.py::test_autoheal_flaky

    AssertionError: AUTOHEAL_FLAKY_TEST
    """

    result = classifier.classify(log)

    assert result["category"] == "FLAKY_TEST"
    assert result["action"] == "RETRY"


def test_code_failure():

    log = """
    FAILED test_calculator.py::test_add

    E       assert 5 == 999
    """

    result = classifier.classify(log)

    assert result["category"] == "CODE_FAILURE"
    assert result["action"] == "DO_NOT_HEAL"


def test_network_failure():

    log = """
    requests.exceptions.ConnectTimeout:
    Connection timed out
    """

    result = classifier.classify(log)

    assert result["category"] == "NETWORK_FAILURE"
    assert result["action"] == "RETRY"


def test_dependency_failure():

    log = """
    ERROR: Could not find a version that satisfies
    the requirement example-package
    """

    result = classifier.classify(log)

    assert result["category"] == "DEPENDENCY_FAILURE"
    assert result["action"] == "RETRY_WITH_CLEAN_INSTALL"


def test_unknown_failure():

    log = """
    Something completely unexpected happened.
    """

    result = classifier.classify(log)

    assert result["category"] == "UNKNOWN"
    assert result["action"] == "ESCALATE"