def test_registry_failure_is_not_docker_failure():

    log = """
    docker push failed
    denied: requested access to the resource is denied
    """

    result = classifier.classify(log)

    assert result["category"] == "REGISTRY_FAILURE"
    assert result["action"] == "RETRY"


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