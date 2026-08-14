class WorkspaceRemediator:

    async def remediate(
        self,
        job_name: str,
    ) -> dict:
        """
        Phase 2 workspace remediation.

        The Jenkins pipeline starts with Clean Workspace,
        so a new remediation build provides a fresh
        workspace execution.

        AutoHeal does not directly modify the Jenkins
        host filesystem.
        """

        return {
            "action": "RETRY_AFTER_WORKSPACE_FAILURE",
            "success": True,
            "message": (
                "Workspace failure detected. "
                "A fresh Jenkins execution will be started. "
                "AutoHeal does not directly modify the "
                "Jenkins host filesystem."
            ),
        }