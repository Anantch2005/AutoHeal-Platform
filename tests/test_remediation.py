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

    fake = FakeJenkins(result="SUCCESS")

    executor.jenkins = fake

    result = await executor.execute(
        job_name="prac",
        category="FLAKY_TEST",
        action="RETRY",
    )

    assert fake.triggered is True

    assert fake.parameters == {
        "AUTOHEAL_RETRY": "true",
    }

    assert result["success"] is True
    assert result["action"] == "RETRY"
    assert result["new_build_number"] == 200
    assert result["verification_result"] == "SUCCESS"


@pytest.mark.asyncio
async def test_failed_retry_escalates():

    executor = RemediationExecutor()

    fake = FakeJenkins(result="FAILURE")

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
    assert result["verification_result"] == "FAILURE"


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