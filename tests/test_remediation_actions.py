import pytest

from app.remediation.dependency import (
    DependencyRemediator,
)

from app.remediation.docker import (
    DockerRemediator,
)

from app.remediation.network import (
    NetworkRemediator,
)

from app.remediation.workspace import (
    WorkspaceRemediator,
)


@pytest.mark.asyncio
async def test_workspace_plan():

    result = await (
        WorkspaceRemediator()
        .remediate("prac")
    )

    assert result["success"] is True

    assert (
        result["action"]
        == "CLEAN_WORKSPACE_AND_RETRY"
    )

    assert result["parameters"] == {
        "AUTOHEAL_ACTION":
            "CLEAN_WORKSPACE",
    }


@pytest.mark.asyncio
async def test_dependency_plan():

    result = await (
        DependencyRemediator()
        .remediate("prac")
    )

    assert result["success"] is True

    assert (
        result["action"]
        == "CLEAN_DEPENDENCY_ENV_AND_RETRY"
    )

    assert result["parameters"] == {
        "AUTOHEAL_ACTION":
            "CLEAN_DEPENDENCY_ENV",
    }


@pytest.mark.asyncio
async def test_docker_plan():

    result = await (
        DockerRemediator()
        .remediate("prac")
    )

    assert result["success"] is True

    assert (
        result["action"]
        == "INVALIDATE_DOCKER_CACHE_AND_RETRY"
    )

    assert result["parameters"] == {
        "AUTOHEAL_ACTION":
            "INVALIDATE_DOCKER_CACHE",
    }


@pytest.mark.asyncio
async def test_network_plan():

    result = await (
        NetworkRemediator()
        .remediate("prac")
    )

    assert result["success"] is True

    assert (
        result["action"]
        == "CONNECTIVITY_CHECK_BACKOFF_AND_RETRY"
    )

    assert result["parameters"] == {
        "AUTOHEAL_ACTION":
            "CONNECTIVITY_CHECK_BACKOFF",
    }