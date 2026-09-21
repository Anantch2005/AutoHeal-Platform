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

        # =========================================
        # CODE FAILURE
        # NEVER AUTO-HEAL
        # =========================================

        if action == "DO_NOT_HEAL":
            return {
                "action": "DO_NOT_HEAL",
                "success": False,
                "message": (
                    "Code/application failure is not safe "
                    "for automatic remediation."
                ),
            }

        # =========================================
        # FLAKY TEST
        # CONTROLLED RETRY + VERIFY
        # =========================================

        if category == "FLAKY_TEST" and action == "RETRY":

            preparation = await self._prepare_flaky_test(
                job_name
            )

            if not preparation["success"]:
                return preparation

            return await self._retry_and_verify(
                job_name=job_name,
                reason="flaky test",
                action="RETRY",
                parameters=preparation["parameters"],
            )

        # =========================================
        # WORKSPACE FAILURE
        # CLEAN WORKSPACE + FRESH CHECKOUT + RETRY
        # =========================================

        if category == "WORKSPACE_FAILURE":

            preparation = await self.workspace.remediate(
                job_name
            )

            if not preparation["success"]:
                return preparation

            return await self._retry_and_verify(
                job_name=job_name,
                reason=(
                    "workspace cleanup and fresh checkout"
                ),
                action=preparation["action"],
                parameters=preparation["parameters"],
            )

        # =========================================
        # DEPENDENCY FAILURE
        # CLEAN ENV + CLEAN INSTALL + RETRY
        # =========================================

        if category == "DEPENDENCY_FAILURE":

            preparation = await self.dependency.remediate(
                job_name
            )

            if not preparation["success"]:
                return preparation

            return await self._retry_and_verify(
                job_name=job_name,
                reason=(
                    "dependency environment reset "
                    "and clean install"
                ),
                action=preparation["action"],
                parameters=preparation["parameters"],
            )

        # =========================================
        # DOCKER FAILURE
        # INVALIDATE CACHE + REBUILD + VERIFY
        # =========================================

        if category == "DOCKER_FAILURE" and action in {
            "RETRY",
            "INVALIDATE_DOCKER_CACHE_AND_RETRY",
        }:

            preparation = await self.docker.remediate(
                job_name
            )

            if not preparation["success"]:
                return preparation

            return await self._retry_and_verify(
                job_name=job_name,
                reason=(
                    "Docker cache invalidation "
                    "and clean rebuild"
                ),
                action=preparation["action"],
                parameters=preparation["parameters"],
            )

        # =========================================
        # NETWORK FAILURE
        # CONNECTIVITY CHECK + BACKOFF + RETRY
        # =========================================

        if category == "NETWORK_FAILURE" and action in {
            "RETRY",
            "CONNECTIVITY_CHECK_BACKOFF_AND_RETRY",
        }:

            preparation = await self.network.remediate(
                job_name
            )

            if not preparation["success"]:
                return preparation

            return await self._retry_and_verify(
                job_name=job_name,
                reason=(
                    "connectivity check "
                    "and network backoff"
                ),
                action=preparation["action"],
                parameters=preparation["parameters"],
                backoff_seconds=preparation.get(
                    "backoff_seconds",
                    0,
                ),
            )

        # =========================================
        # REGISTRY FAILURE
        # CONTROLLED RETRY + VERIFY
        # =========================================

        if (
            category == "REGISTRY_FAILURE"
            and action == "RETRY"
        ):

            return await self._retry_and_verify(
                job_name=job_name,
                reason="registry failure",
                action="RETRY",
                parameters={
                    "AUTOHEAL_RETRY": "true",
                    "AUTOHEAL_ACTION": "RETRY_REGISTRY",
                },
            )

        # =========================================
        # EVERYTHING ELSE
        # =========================================

        return {
            "action": "ESCALATE",
            "success": False,
            "message": (
                f"No safe remediation exists for "
                f"{category}."
            ),
        }

    async def _prepare_flaky_test(
        self,
        job_name: str,
    ) -> dict:

        return {
            "action": "RETRY",
            "success": True,
            "parameters": {
                "AUTOHEAL_RETRY": "true",
                "AUTOHEAL_ACTION": "RETRY_FLAKY_TEST",
            },
            "message": (
                "Known flaky test detected. "
                "A controlled Jenkins retry will be attempted."
            ),
        }

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

        print(
            "Triggering Jenkins remediation build..."
        )

        try:

            trigger = await self.jenkins.trigger_build(
                job_name,
                parameters=parameters,
            )

        except Exception as exc:

            return {
                "action": "ESCALATE",
                "success": False,
                "message": (
                    "Failed to trigger Jenkins "
                    f"remediation build: {exc}"
                ),
            }

        if not isinstance(trigger, dict):

            return {
                "action": "ESCALATE",
                "success": False,
                "message": (
                    "Unexpected response from Jenkins trigger."
                ),
            }

        if not trigger.get("success", False):

            return {
                "action": "ESCALATE",
                "success": False,
                "message": trigger.get(
                    "message",
                    "Failed to trigger Jenkins "
                    "remediation build.",
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
                    "request, but no build number "
                    "was returned."
                ),
                "queue_url": queue_url,
            }

        print(
            f"New Jenkins build: #{new_build}"
        )

        try:

            result = await self.jenkins.get_build_result(
                job_name,
                new_build,
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
                    f"Remediation completed successfully "
                    f"after {reason}. "
                    "Pipeline automatically healed."
                ),
                "new_build_number": new_build,
                "verification_result": "SUCCESS",
                "queue_url": queue_url,
            }

        return {
            "action": "ESCALATE",
            "success": False,
            "message": (
                "Remediation completed but the pipeline "
                f"still failed after {reason}."
            ),
            "new_build_number": new_build,
            "verification_result": (
                result or "UNKNOWN"
            ),
            "queue_url": queue_url,
        }