class DependencyRemediator:

    async def remediate(
        self,
        job_name: str,
    ) -> dict:
        """
        Safe dependency remediation.

        We do not modify source code or lockfiles.
        """

        return {
            "action": "RETRY_WITH_CLEAN_INSTALL",
            "success": True,
            "message": (
                "Dependency failure detected. "
                "A fresh dependency installation will be "
                "attempted by the Jenkins pipeline."
            ),
        }