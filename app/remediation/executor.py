from app.remediation.jenkins import JenkinsRemediator
from app.remediation.workspace import WorkspaceRemediator
from app.remediation.dependency import DependencyRemediator


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
        # =========================================

        if category == "CODE_FAILURE":

            return {
                "action": "DO_NOT_HEAL",
                "success": False,
                "message": (
                    "Code failure detected. "
                    "Automatic modification is prohibited."
                ),
            }

        # =========================================
        # FLAKY TEST
        # =========================================

        if category == "FLAKY_TEST":

            return await self._retry(
                job_name,
                "FLAKY_TEST",
                parameters={
                    "AUTOHEAL_RETRY": "true",
                },
            )

        # =========================================
        # NETWORK FAILURE
        # =========================================

        if category == "NETWORK_FAILURE":

            return await self._retry(
                job_name,
                "NETWORK_FAILURE",
            )

        # =========================================
        # DOCKER FAILURE
        # =========================================

        if category == "DOCKER_FAILURE":

            return await self._retry(
                job_name,
                "DOCKER_FAILURE",
            )

        # =========================================
        # REGISTRY FAILURE
        # =========================================

        if category == "REGISTRY_FAILURE":

            return await self._retry(
                job_name,
                "REGISTRY_FAILURE",
            )

        # =========================================
        # WORKSPACE FAILURE
        # =========================================

        if category == "WORKSPACE_FAILURE":

            preparation = await self.workspace.remediate(
                job_name
            )

            if not preparation["success"]:
                return preparation

            return await self._retry(
                job_name,
                "WORKSPACE_FAILURE",
            )

        # =========================================
        # DEPENDENCY FAILURE
        # =========================================

        if category == "DEPENDENCY_FAILURE":

            preparation = await self.dependency.remediate(
                job_name
            )

            if not preparation["success"]:
                return preparation

            return await self._retry(
                job_name,
                "DEPENDENCY_FAILURE",
            )

        # =========================================
        # UNKNOWN
        # =========================================

        return {
            "action": "ESCALATE",
            "success": False,
            "message": (
                f"No safe remediation exists for "
                f"category '{category}'."
            ),
        }

    async def _retry(
        self,
        job_name: str,
        reason: str,
        parameters: dict | None = None,
    ) -> dict:

        try:

            # =====================================
            # TRIGGER REMEDIATION BUILD
            # =====================================

            new_build = await self.jenkins.trigger_build(
                job_name,
                parameters=parameters,
            )

            # =====================================
            # VERIFY BUILD
            # =====================================

            result = await self.jenkins.get_build_result(
                job_name,
                new_build,
            )

            # =====================================
            # HEALED
            # =====================================

            if result == "SUCCESS":

                return {
                    "action": "RETRY",
                    "success": True,
                    "message": (
                        f"AutoHeal successfully recovered "
                        f"the pipeline after {reason}."
                    ),
                    "new_build_number": new_build,
                    "verification_result": result,
                }

            # =====================================
            # RETRY FAILED
            # =====================================

            return {
                "action": "ESCALATE",
                "success": False,
                "message": (
                    f"Remediation retry failed after "
                    f"{reason}. Human investigation required."
                ),
                "new_build_number": new_build,
                "verification_result": result,
            }

        except Exception as exc:

            return {
                "action": "ESCALATE",
                "success": False,
                "message": (
                    f"Remediation execution failed: {exc}"
                ),
            }