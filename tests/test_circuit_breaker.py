from app.safety.circuit_breaker import CircuitBreaker


def test_circuit_breaker_opens_after_three_attempts():
    breaker = CircuitBreaker(max_attempts=3, window_minutes=30)

    assert breaker.allow("prac", "NETWORK_FAILURE") is True
    assert breaker.allow("prac", "NETWORK_FAILURE") is True
    assert breaker.allow("prac", "NETWORK_FAILURE") is True
    assert breaker.count("prac", "NETWORK_FAILURE") == 3
    assert breaker.allow("prac", "NETWORK_FAILURE") is False


def test_circuit_breaker_is_scoped_by_job_and_category():
    breaker = CircuitBreaker(max_attempts=1, window_minutes=30)

    assert breaker.allow("prac", "NETWORK_FAILURE") is True
    assert breaker.allow("prac", "NETWORK_FAILURE") is False
    assert breaker.allow("prac", "REGISTRY_FAILURE") is True
    assert breaker.allow("other-job", "NETWORK_FAILURE") is True