class WorkspaceRemediator:

    async def remediate(
        self,
        job_name: str,
    ) -> dict:
        """
        Prepare the safe workspace recovery contract.

        AutoHeal does not mutate the Jenkins controller/agent filesystem.
        The actual remediation is the Jenkins retry, which executes the
        pipeline's clean-workspace path. JenkinsRemediator performs that retry.
        """

        return {
            "action": "RETRY_AFTER_WORKSPACE_FAILURE",
            "success": True,
            "remediation_performed": False,
            "message": (
                "Workspace failure classified. No Jenkins host filesystem "
                "is modified by AutoHeal; remediation is performed by the "
                "subsequent Jenkins retry using the clean-workspace path."
            ),
        }