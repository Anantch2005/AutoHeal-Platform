import asyncio

from app.remediation.dependency import DependencyRemediator
from app.remediation.docker import DockerRemediator
from app.remediation.jenkins import JenkinsRemediator
from app.remediation.network import NetworkRemediator
from app.remediation.workspace import WorkspaceRemediator


class RemediationExecutor:

    def __init__(self):

        self.jenkins = JenkinsRemediator()

        self.workspace = WorkspaceRemediator()

        self.dependency = DependencyRemediator()

        self.docker = DockerRemediator()

        self.network = NetworkRemediator()


    async def execute(
        self,
        job_name: str,
        category: str,
        action: str,
    ) -> dict:

        # =====================================================
        # UNSAFE
        # =====================================================

        if action == "DO_NOT_HEAL":

            return {
                "action": "DO_NOT_HEAL",
                "success": False,
                "message": (
                    "Failure is not safe for "
                    "automatic remediation."
                ),
            }


        # =====================================================
        # FLAKY TEST
        # =====================================================

        if (
            category == "FLAKY_TEST"
            and action == "RETRY"
        ):

            return await self._retry_and_verify(
                job_name=job_name,
                reason="flaky test",
                action="RETRY",
                parameters={
                    "AUTOHEAL_ACTION": "RETRY",
                },
            )


        # =====================================================
        # WORKSPACE
        # =====================================================

        if (
            category == "WORKSPACE_FAILURE"
            and action
            == "CLEAN_WORKSPACE_AND_RETRY"
        ):

            plan = await (
                self.workspace.remediate(
                    job_name
                )
            )

            return await self._execute_plan(
                job_name,
                plan,
                reason="workspace cleanup and fresh checkout",
            )


        # =====================================================
        # DEPENDENCY
        # =====================================================

        if (
            category == "DEPENDENCY_FAILURE"
            and action
            == "CLEAN_DEPENDENCY_ENV_AND_RETRY"
        ):

            plan = await (
                self.dependency.remediate(
                    job_name
                )
            )

            return await self._execute_plan(
                job_name,
                plan,
                reason=(
                    "dependency environment reset "
                    "and clean install"
                ),
            )


        # =====================================================
        # DOCKER
        # =====================================================

        if (
            category == "DOCKER_FAILURE"
            and action
            == "INVALIDATE_DOCKER_CACHE_AND_RETRY"
        ):

            plan = await (
                self.docker.remediate(
                    job_name
                )
            )

            return await self._execute_plan(
                job_name,
                plan,
                reason=(
                    "Docker cache invalidation "
                    "and clean rebuild"
                ),
            )


        # =====================================================
        # NETWORK
        # =====================================================

        if (
            category == "NETWORK_FAILURE"
            and action
            == "CONNECTIVITY_CHECK_BACKOFF_AND_RETRY"
        ):

            plan = await (
                self.network.remediate(
                    job_name
                )
            )

            return await self._execute_plan(
                job_name,
                plan,
                reason=(
                    "connectivity check "
                    "and network backoff"
                ),
            )


        # =====================================================
        # REGISTRY
        # =====================================================

        if (
            category == "REGISTRY_FAILURE"
            and action == "RETRY"
        ):

            return await self._retry_and_verify(
                job_name=job_name,
                reason="registry failure",
                action="RETRY",
                parameters={
                    "AUTOHEAL_ACTION":
                        "RETRY_REGISTRY",
                },
            )


        # =====================================================
        # UNSUPPORTED
        # =====================================================

        return {
            "action": "ESCALATE",
            "success": False,
            "message": (
                f"No safe remediation exists for "
                f"{category}."
            ),
        }


    async def _execute_plan(
        self,
        job_name: str,
        plan: dict,
        reason: str,
    ) -> dict:

        if not plan.get(
            "success",
            False,
        ):

            return plan


        return await self._retry_and_verify(
            job_name=job_name,
            reason=reason,
            action=plan["action"],
            parameters=plan[
                "parameters"
            ],
            backoff_seconds=plan.get(
                "backoff_seconds",
                0,
            ),
        )


    async def _retry_and_verify(
        self,
        job_name: str,
        reason: str,
        action: str,
        parameters: dict[str, str],
        backoff_seconds: int = 0,
    ) -> dict:

        if backoff_seconds > 0:

            print(
                "Applying remediation backoff: "
                f"{backoff_seconds} seconds"
            )

            await asyncio.sleep(
                backoff_seconds
            )


        try:

            trigger = await (
                self.jenkins.trigger_build(
                    job_name,
                    parameters=parameters,
                )
            )

        except Exception as exc:

            return {
                "action": "ESCALATE",
                "success": False,
                "message": (
                    "Failed to trigger Jenkins "
                    "remediation build: "
                    f"{exc}"
                ),
            }


        if not isinstance(
            trigger,
            dict,
        ):

            return {
                "action": "ESCALATE",
                "success": False,
                "message": (
                    "Unexpected response from "
                    "Jenkins trigger."
                ),
            }


        if not trigger.get(
            "success",
            False,
        ):

            return {
                "action": "ESCALATE",
                "success": False,
                "message": trigger.get(
                    "message",
                    "Jenkins remediation failed.",
                ),
                "queue_url": trigger.get(
                    "queue_url"
                ),
            }


        new_build = trigger.get(
            "build_number"
        )

        queue_url = trigger.get(
            "queue_url"
        )


        if new_build is None:

            return {
                "action": "ESCALATE",
                "success": False,
                "message": (
                    "Jenkins accepted the remediation "
                    "request but no build number was returned."
                ),
                "queue_url": queue_url,
            }


        try:

            result = await (
                self.jenkins.get_build_result(
                    job_name,
                    new_build,
                )
            )

        except Exception as exc:

            return {
                "action": "ESCALATE",
                "success": False,
                "message": (
                    "Failed while verifying Jenkins "
                    f"build #{new_build}: {exc}"
                ),
                "new_build_number": new_build,
                "queue_url": queue_url,
            }


        if result == "SUCCESS":

            return {
                "action": action,
                "success": True,
                "message": (
                    "Remediation succeeded after "
                    f"{reason}."
                ),
                "new_build_number": new_build,
                "verification_result": "SUCCESS",
                "queue_url": queue_url,
            }


        return {
            "action": "ESCALATE",
            "success": False,
            "message": (
                "Pipeline still failed after "
                f"{reason}."
            ),
            "new_build_number": new_build,
            "verification_result": (
                result or "UNKNOWN"
            ),
            "queue_url": queue_url,
        }