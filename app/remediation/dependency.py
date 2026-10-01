class DependencyRemediator:
    """
    Build a Jenkins-side dependency recovery plan.

    The shared library decides how to recreate the project's
    dependency environment. For the included Python helper this
    means recreating .venv and reinstalling the existing dependency
    definition without changing versions or lockfiles.
    """

    async def remediate(self, job_name: str) -> dict:
        return {
            "action": "CLEAN_DEPENDENCY_ENV_AND_RETRY",
            "success": True,
            "remediation_performed": True,
            "parameters": {
                "AUTOHEAL_ACTION": "CLEAN_DEPENDENCY_ENV",
            },
            "message": (
                "Dependency failure detected. The shared library will "
                "recreate the dependency environment and reinstall "
                "from the repository's existing dependency definition."
            ),
        }