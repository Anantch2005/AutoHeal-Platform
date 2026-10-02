import pytest

from app.remediation.dependency import DependencyRemediator
from app.remediation.docker import DockerRemediator
from app.remediation.network import NetworkRemediator
from app.remediation.workspace import WorkspaceRemediator


async def _get(remediator):
    return await remediator.remediate("prac")


@pytest.mark.asyncio
async def test_workspace_plan_is_explicit():

    plan = await _get(
        WorkspaceRemediator()
    )

    assert (
        plan["action"]
        == "CLEAN_WORKSPACE_AND_RETRY"
    )

    assert plan["parameters"] == {
        "AUTOHEAL_ACTION": "CLEAN_WORKSPACE",
    }


@pytest.mark.asyncio
async def test_dependency_plan_is_explicit():

    plan = await _get(
        DependencyRemediator()
    )

    assert (
        plan["action"]
        == "CLEAN_DEPENDENCY_ENV_AND_RETRY"
    )

    assert plan["parameters"] == {
        "AUTOHEAL_ACTION": "CLEAN_DEPENDENCY_ENV",
    }


@pytest.mark.asyncio
async def test_docker_plan_is_explicit():

    plan = await _get(
        DockerRemediator()
    )

    assert (
        plan["action"]
        == "INVALIDATE_DOCKER_CACHE_AND_RETRY"
    )

    assert plan["parameters"] == {
        "AUTOHEAL_ACTION": "INVALIDATE_DOCKER_CACHE",
    }


@pytest.mark.asyncio
async def test_network_plan_is_explicit():

    plan = await _get(
        NetworkRemediator()
    )

    assert (
        plan["action"]
        == "CONNECTIVITY_CHECK_BACKOFF_AND_RETRY"
    )

    assert plan["parameters"] == {
        "AUTOHEAL_ACTION": "CONNECTIVITY_CHECK_BACKOFF",
    }