from app.classifier.classifier import FailureClassifier


classifier = FailureClassifier()


def test_flaky_test_signature():
    result = classifier.classify("AUTOHEAL_FLAKY_TEST")
    assert result["category"] == "FLAKY_TEST"
    assert result["action"] == "RETRY"


def test_code_assertion_is_not_healed():
    result = classifier.classify(
        "AssertionError: expected 5 but got -1"
    )
    assert result["category"] == "CODE_FAILURE"
    assert result["action"] == "DO_NOT_HEAL"


def test_docker_daemon_failure_escalates():
    result = classifier.classify(
        "Cannot connect to the Docker daemon"
    )
    assert result["category"] == "DOCKER_DAEMON_FAILURE"
    assert result["action"] == "ESCALATE"


def test_registry_auth_failure_escalates():
    result = classifier.classify(
        "denied: requested access to the resource is denied"
    )
    assert result["category"] == "REGISTRY_AUTH_FAILURE"
    assert result["action"] == "ESCALATE"


def test_disk_full_escalates():
    result = classifier.classify(
        "OSError: [Errno 28] No space left on device"
    )
    assert result["category"] == "DISK_FULL"
    assert result["action"] == "ESCALATE"


def test_oom_escalates():
    result = classifier.classify("script returned exit code 137")
    assert result["category"] == "OOM"
    assert result["action"] == "ESCALATE"


def test_agent_offline_escalates():
    result = classifier.classify(
        "Agent linux-builder-3 went offline during the build"
    )
    assert result["category"] == "AGENT_FAILURE"
    assert result["action"] == "ESCALATE"


def test_network_failure_uses_bounded_recovery():
    result = classifier.classify(
        "curl: (7) Failed to connect to 127.0.0.1 port 9"
    )
    assert result["category"] == "NETWORK_FAILURE"
    assert result["action"] == "CONNECTIVITY_CHECK_BACKOFF_AND_RETRY"


def test_dependency_failure_uses_dependency_recovery():
    result = classifier.classify(
        "/usr/local/bin/python: No module named pytest"
    )
    assert result["category"] == "DEPENDENCY_FAILURE"
    assert result["action"] == "CLEAN_DEPENDENCY_ENV_AND_RETRY"


def test_workspace_failure():
    result = classifier.classify(
        "ERROR: unable to create file in workspace"
    )
    assert result["category"] == "WORKSPACE_FAILURE"
    assert result["action"] == "CLEAN_WORKSPACE_AND_RETRY"


def test_ssh_auth_failure_fails_closed():
    result = classifier.classify("Permission denied (publickey).")
    assert result["category"] == "UNKNOWN"
    assert result["action"] == "ESCALATE"


def test_unknown_failure_escalates():
    result = classifier.classify(
        "Something unexpected happened in the pipeline."
    )
    assert result["category"] == "UNKNOWN"
    assert result["action"] == "ESCALATE"