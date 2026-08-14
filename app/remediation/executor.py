from app.remediation.dependency import DependencyRemediator
from app.remediation.jenkins import JenkinsRemediator
from app.remediation.workspace import WorkspaceRemediator


class RemediationExecutor:

    def __init__(self):
        self.jenkins = JenkinsRemediator()
        self.workspace = WorkspaceRemediator()
        self.dependency = DependencyRemediator()

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
                    "Code/application failure is not "
                    "safe for automatic remediation."
                ),
            }

        # =========================================
        # FLAKY TEST
        # RETRY + VERIFY
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
            )

        # =========================================
        # WORKSPACE FAILURE
        # FRESH JENKINS EXECUTION
        # =========================================

        if category == "WORKSPACE_FAILURE":

            preparation = await self.workspace.remediate(
                job_name
            )

            if not preparation["success"]:
                return preparation

            return await self._retry_and_verify(
                job_name=job_name,
                reason="workspace failure",
            )

        # =========================================
        # DEPENDENCY FAILURE
        # FRESH DEPENDENCY INSTALL
        # =========================================

        if category == "DEPENDENCY_FAILURE":

            preparation = await self.dependency.remediate(
                job_name
            )

            if not preparation["success"]:
                return preparation

            return await self._retry_and_verify(
                job_name=job_name,
                reason="dependency failure",
            )

        # =========================================
        # NETWORK FAILURE
        # =========================================

        if category == "NETWORK_FAILURE" and action == "RETRY":

            return await self._retry_and_verify(
                job_name=job_name,
                reason="network failure",
            )

        # =========================================
        # DOCKER FAILURE
        # =========================================

        if category == "DOCKER_FAILURE" and action == "RETRY":

            return await self._retry_and_verify(
                job_name=job_name,
                reason="Docker failure",
            )

        # =========================================
        # REGISTRY FAILURE
        # =========================================

        if category == "REGISTRY_FAILURE" and action == "RETRY":

            return await self._retry_and_verify(
                job_name=job_name,
                reason="registry failure",
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
            "message": (
                "Known flaky test detected. "
                "A controlled Jenkins retry will be attempted."
            ),
        }

    async def _retry_and_verify(
        self,
        job_name: str,
        reason: str,
    ) -> dict:

        print(
            "Triggering Jenkins remediation build..."
        )

        parameters = {
            "AUTOHEAL_RETRY": "true",
        }

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
                    f"Failed to trigger Jenkins retry: {exc}"
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
                    "Failed to trigger Jenkins retry.",
                ),
                "queue_url": trigger.get("queue_url"),
            }

        new_build = trigger.get("build_number")
        queue_url = trigger.get("queue_url")

        if new_build is None:

            return {
                "action": "ESCALATE",
                "success": False,
                "message": (
                    "Jenkins accepted the retry, "
                    "but no build number was returned."
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
                    f"Failed while verifying Jenkins "
                    f"build #{new_build}: {exc}"
                ),
                "new_build_number": new_build,
                "queue_url": queue_url,
            }

        if result == "SUCCESS":

            return {
                "action": "RETRY",
                "success": True,
                "message": (
                    f"Retry completed successfully after "
                    f"{reason}. Pipeline automatically healed."
                ),
                "new_build_number": new_build,
                "verification_result": "SUCCESS",
                "queue_url": queue_url,
            }

        return {
            "action": "ESCALATE",
            "success": False,
            "message": (
                f"Retry completed but the pipeline still "
                f"failed after {reason}."
            ),
            "new_build_number": new_build,
            "verification_result": result or "UNKNOWN",
            "queue_url": queue_url,
        }