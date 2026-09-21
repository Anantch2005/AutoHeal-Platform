import pytest

from app.remediation.executor import RemediationExecutor


class FakeJenkins:

    def __init__(self, result="SUCCESS"):
        self.triggered = False
        self.parameters = None
        self.result = result

    async def trigger_build(
        self,
        job_name,
        parameters=None,
    ):

        self.triggered = True
        self.parameters = parameters

        return {
            "success": True,
            "build_number": 200,
            "queue_url": "fake-queue",
        }

    async def get_build_result(
        self,
        job_name,
        build_number,
    ):

        return self.result


@pytest.mark.asyncio
async def test_flaky_test_is_healed():

    executor = RemediationExecutor()

    fake = FakeJenkins(
        result="SUCCESS"
    )

    executor.jenkins = fake

    result = await executor.execute(
        job_name="prac",
        category="FLAKY_TEST",
        action="RETRY",
    )

    assert fake.triggered is True

    assert fake.parameters == {
        "AUTOHEAL_RETRY": "true",
        "AUTOHEAL_ACTION": "RETRY_FLAKY_TEST",
    }

    assert result["success"] is True
    assert result["action"] == "RETRY"
    assert result["new_build_number"] == 200
    assert (
        result["verification_result"]
        == "SUCCESS"
    )


@pytest.mark.asyncio
async def test_failed_retry_escalates():

    executor = RemediationExecutor()

    fake = FakeJenkins(
        result="FAILURE"
    )

    executor.jenkins = fake

    result = await executor.execute(
        job_name="prac",
        category="FLAKY_TEST",
        action="RETRY",
    )

    assert fake.triggered is True

    assert result["success"] is False
    assert result["action"] == "ESCALATE"
    assert result["new_build_number"] == 200
    assert (
        result["verification_result"]
        == "FAILURE"
    )


@pytest.mark.asyncio
async def test_workspace_failure_cleans_workspace_and_fresh_checkout():

    executor = RemediationExecutor()

    fake = FakeJenkins(
        result="SUCCESS"
    )

    executor.jenkins = fake

    result = await executor.execute(
        job_name="prac",
        category="WORKSPACE_FAILURE",
        action="CLEAN_WORKSPACE_AND_RETRY",
    )

    assert fake.triggered is True

    assert fake.parameters == {
        "AUTOHEAL_RETRY": "true",
        "AUTOHEAL_ACTION": "CLEAN_WORKSPACE",
        "AUTOHEAL_CLEAN_WORKSPACE": "true",
        "AUTOHEAL_FRESH_CHECKOUT": "true",
    }

    assert result["success"] is True
    assert (
        result["action"]
        == "CLEAN_WORKSPACE_AND_RETRY"
    )
    assert (
        result["verification_result"]
        == "SUCCESS"
    )


@pytest.mark.asyncio
async def test_dependency_failure_rebuilds_dependency_environment():

    executor = RemediationExecutor()

    fake = FakeJenkins(
        result="SUCCESS"
    )

    executor.jenkins = fake

    result = await executor.execute(
        job_name="prac",
        category="DEPENDENCY_FAILURE",
        action=(
            "CLEAN_DEPENDENCY_ENV_AND_RETRY"
        ),
    )

    assert fake.triggered is True

    assert fake.parameters == {
        "AUTOHEAL_RETRY": "true",
        "AUTOHEAL_ACTION": (
            "CLEAN_DEPENDENCY_ENV"
        ),
        "AUTOHEAL_CLEAN_DEPENDENCY_ENV": "true",
        "AUTOHEAL_INSTALL_FROM_LOCKFILE": "true",
    }

    assert result["success"] is True

    assert (
        result["action"]
        == "CLEAN_DEPENDENCY_ENV_AND_RETRY"
    )

    assert (
        result["verification_result"]
        == "SUCCESS"
    )


@pytest.mark.asyncio
async def test_docker_failure_invalidates_cache_before_retry():

    executor = RemediationExecutor()

    fake = FakeJenkins(
        result="SUCCESS"
    )

    executor.jenkins = fake

    result = await executor.execute(
        job_name="prac",
        category="DOCKER_FAILURE",
        action=(
            "INVALIDATE_DOCKER_CACHE_AND_RETRY"
        ),
    )

    assert fake.triggered is True

    assert fake.parameters == {
        "AUTOHEAL_RETRY": "true",
        "AUTOHEAL_ACTION": (
            "INVALIDATE_DOCKER_CACHE"
        ),
        "AUTOHEAL_DOCKER_NO_CACHE": "true",
    }

    assert result["success"] is True

    assert (
        result["action"]
        == "INVALIDATE_DOCKER_CACHE_AND_RETRY"
    )

    assert (
        result["verification_result"]
        == "SUCCESS"
    )


@pytest.mark.asyncio
async def test_network_failure_checks_connectivity_and_backoff(
    monkeypatch,
):

    executor = RemediationExecutor()

    fake = FakeJenkins(
        result="SUCCESS"
    )

    executor.jenkins = fake

    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(
        "app.remediation.executor.asyncio.sleep",
        fake_sleep,
    )

    result = await executor.execute(
        job_name="prac",
        category="NETWORK_FAILURE",
        action=(
            "CONNECTIVITY_CHECK_BACKOFF_AND_RETRY"
        ),
    )

    assert slept == [10]

    assert fake.triggered is True

    assert fake.parameters == {
        "AUTOHEAL_RETRY": "true",
        "AUTOHEAL_ACTION": (
            "CONNECTIVITY_CHECK_BACKOFF"
        ),
        "AUTOHEAL_CONNECTIVITY_CHECK": "true",
        "AUTOHEAL_BACKOFF_SECONDS": "10",
    }

    assert result["success"] is True

    assert (
        result["action"]
        == "CONNECTIVITY_CHECK_BACKOFF_AND_RETRY"
    )

    assert (
        result["verification_result"]
        == "SUCCESS"
    )


@pytest.mark.asyncio
async def test_code_failure_is_never_retried():

    executor = RemediationExecutor()

    fake = FakeJenkins()

    executor.jenkins = fake

    result = await executor.execute(
        job_name="prac",
        category="CODE_FAILURE",
        action="DO_NOT_HEAL",
    )

    assert fake.triggered is False

    assert result["success"] is False
    assert result["action"] == "DO_NOT_HEAL"