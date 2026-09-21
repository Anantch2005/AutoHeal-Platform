class DependencyRemediator:
    """
    Build a safe Jenkins-side dependency recovery plan.

    AutoHeal does not modify dependency versions or lockfiles.
    Jenkins recreates the dependency environment and installs
    using the repository's existing dependency definition.
    """

    async def remediate(
        self,
        job_name: str,
    ) -> dict:

        return {
            "action": "CLEAN_DEPENDENCY_ENV_AND_RETRY",
            "success": True,
            "remediation_performed": True,
            "parameters": {
                "AUTOHEAL_RETRY": "true",
                "AUTOHEAL_ACTION": "CLEAN_DEPENDENCY_ENV",
                "AUTOHEAL_CLEAN_DEPENDENCY_ENV": "true",
                "AUTOHEAL_INSTALL_FROM_LOCKFILE": "true",
            },
            "message": (
                "Dependency failure detected. Jenkins will "
                "recreate the dependency environment and install "
                "from the existing lockfile/requirements definition "
                "before rerunning the pipeline."
            ),
        }