

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


def test_registry_auth_failure_escalates():
    result = classifier.classify(
        "docker pull example.invalid/private:latest: denied: requested access to the resource is denied"
    )
    assert result["category"] == "REGISTRY_AUTH_FAILURE"
    assert result["action"] == "ESCALATE"


def test_docker_daemon_failure_escalates():
    result = classifier.classify(
        "Cannot connect to the Docker daemon at unix:///var/run/docker.sock"
    )
    assert result["category"] == "DOCKER_DAEMON_FAILURE"
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


def test_pip_connection_failure_is_network_failure():
    result = classifier.classify(
        "pip install failed: Connection refused while connecting to package index"
    )
    assert result["category"] == "NETWORK_FAILURE"
    assert result["action"] == "CONNECTIVITY_CHECK_BACKOFF_AND_RETRY"


def test_missing_python_dependency_uses_dependency_recovery():
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


def test_peer_dependency_warning_is_not_a_failure():
    result = classifier.classify(
        "npm WARN peer dependency version conflict"
    )
    assert result["category"] == "UNKNOWN"
    assert result["action"] == "ESCALATE"


def test_unknown_failure_escalates():
    result = classifier.classify(
        "Something unexpected happened in the pipeline."
    )
    assert result["category"] == "UNKNOWN"
    assert result["action"] == "ESCALATE"


# Regression cases from the portfolio review: broad words in a test failure
# must not override stronger application/test evidence.
def test_assertion_with_connection_refused_is_code_failure():
    result = classifier.classify(
        "E AssertionError: expected response; message was Connection refused"
    )
    assert result["category"] == "CODE_FAILURE"
    assert result["action"] == "DO_NOT_HEAL"


def test_typo_in_local_import_is_not_dependency_recovery():
    result = classifier.classify(
        "Traceback (most recent call last):\n"
        "  File 'tests/test_app.py', line 2, in <module>\n"
        "    from app.calcluator import add\n"
        "ModuleNotFoundError: No module named 'app.calcluator'"
    )
    assert result["category"] == "CODE_FAILURE"
    assert result["action"] == "DO_NOT_HEAL"


def test_application_http_500_is_not_network_failure():
    result = classifier.classify(
        "FAILED tests/test_api.py::test_create_user - AssertionError: expected 200, got 500\n"
        "Application response: HTTP/1.1 500 Internal Server Error"
    )
    assert result["category"] == "CODE_FAILURE"


def test_generic_authentication_text_is_not_registry_auth_failure():
    result = classifier.classify(
        "FAILED tests/test_login.py::test_authentication_required - AssertionError"
    )
    assert result["category"] == "CODE_FAILURE"


def test_unrelated_authentication_phrase_is_not_registry_auth_failure():
    result = classifier.classify("The application says authentication required")
    assert result["category"] == "UNKNOWN"


def test_confidence_is_not_hardcoded_to_one():
    result = classifier.classify("curl: (7) Failed to connect to 127.0.0.1 port 9")
    assert result["category"] == "NETWORK_FAILURE"
    assert 0.0 < result["confidence"] < 1.0


def test_classifier_uses_tail_for_old_unrelated_log_noise():
    log = ("Connection refused\n" * 400) + "AssertionError: expected 2 but got 1"
    result = classifier.classify(log)
    assert result["category"] == "CODE_FAILURE"

