class DependencyRemediator:

    async def remediate(
        self,
        job_name: str,
    ) -> dict:
        """
        Phase 2 dependency remediation.

        The Jenkins test stage creates a fresh Python
        container and installs dependencies again.
        Therefore a remediation retry provides a clean
        dependency-install attempt without modifying
        source code or lockfiles.
        """

        return {
            "action": "RETRY_WITH_CLEAN_INSTALL",
            "success": True,
            "message": (
                "Dependency failure detected. "
                "A fresh Jenkins execution will perform "
                "a clean dependency installation attempt."
            ),
        }