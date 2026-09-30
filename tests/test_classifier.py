from app.classifier.classifier import FailureClassifier


classifier = FailureClassifier()


def test_flaky_test_signature():

    result = classifier.classify(
        "Assertion marker: AUTOHEAL_FLAKY_TEST"
    )

    assert result["category"] == "FLAKY_TEST"
    assert result["action"] == "RETRY"


def test_code_failure_wins_over_connection_refused():

    log = """
    Traceback (most recent call last):
      File "test_app.py", line 12, in test_db
        connect()
    Connection refused
    AssertionError: database test failed
    """

    result = classifier.classify(log)

    assert result["category"] == "CODE_FAILURE"
    assert result["action"] == "DO_NOT_HEAL"


def test_docker_daemon_permission_is_docker_failure():

    log = """
    permission denied while trying to connect to the Docker daemon socket
    """

    result = classifier.classify(log)

    assert result["category"] == "DOCKER_FAILURE"
    assert (
        result["action"]
        == "INVALIDATE_DOCKER_CACHE_AND_RETRY"
    )


def test_registry_failure_is_not_docker_failure():

    log = """
    docker push failed
    denied: requested access to the resource is denied
    """

    result = classifier.classify(log)

    assert result["category"] == "REGISTRY_FAILURE"
    assert result["action"] == "RETRY"


def test_generic_pull_step_failure_is_not_registry_failure():

    log = """
    Pull step failed because the deployment script returned exit code 1.
    """

    result = classifier.classify(log)

    assert result["category"] == "UNKNOWN"
    assert result["action"] == "ESCALATE"


def test_network_connection_failure():

    log = """
    curl: (7) Failed to connect to 127.0.0.1 port 9
    """

    result = classifier.classify(log)

    assert result["category"] == "NETWORK_FAILURE"

    assert (
        result["action"]
        == "CONNECTIVITY_CHECK_BACKOFF_AND_RETRY"
    )


def test_dependency_failure():

    log = """
    No matching distribution found for AUTOHEAL_DEPENDENCY_FAILURE
    """

    result = classifier.classify(log)

    assert result["category"] == "DEPENDENCY_FAILURE"

    assert (
        result["action"]
        == "CLEAN_DEPENDENCY_ENV_AND_RETRY"
    )


def test_workspace_failure():

    log = """
    ERROR: unable to create file in workspace
    """

    result = classifier.classify(log)

    assert result["category"] == "WORKSPACE_FAILURE"

    assert (
        result["action"]
        == "CLEAN_WORKSPACE_AND_RETRY"
    )


def test_ssh_permission_denied_fails_closed():

    log = """
    Permission denied (publickey).
    """

    result = classifier.classify(log)

    assert result["category"] == "UNKNOWN"
    assert result["action"] == "ESCALATE"


def test_unknown_failure_escalates():

    result = classifier.classify(
        "Something unexpected happened in the pipeline."
    )

    assert result["category"] == "UNKNOWN"
    assert result["action"] == "ESCALATE"