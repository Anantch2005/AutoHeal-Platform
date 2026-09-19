class DependencyRemediator:

    async def remediate(
        self,
        job_name: str,
    ) -> dict:
        """
        Prepare the safe dependency recovery contract.

        AutoHeal never edits source code or lockfiles. The actual remediation
        is the Jenkins retry, which performs a fresh dependency installation.
        JenkinsRemediator performs that external operation.
        """

        return {
            "action": "RETRY_WITH_CLEAN_INSTALL",
            "success": True,
            "remediation_performed": False,
            "message": (
                "Dependency failure classified. AutoHeal does not modify "
                "source code or lockfiles; remediation is performed by the "
                "subsequent Jenkins retry with a fresh dependency install."
            ),
        }