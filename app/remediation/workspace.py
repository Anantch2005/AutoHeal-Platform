class WorkspaceRemediator:

    async def remediate(
        self,
        job_name: str,
    ) -> dict:
        """
        Safe workspace remediation.

        Phase 2 does not manipulate the Jenkins host
        filesystem directly.

        The next build receives a fresh execution attempt.
        """

        return {
            "action": "RETRY_AFTER_WORKSPACE_FAILURE",
            "success": True,
            "message": (
                "Workspace failure detected. "
                "A fresh Jenkins build will be attempted. "
                "Direct Jenkins host filesystem modification "
                "is disabled."
            ),
        }