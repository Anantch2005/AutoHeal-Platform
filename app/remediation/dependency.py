class DependencyRemediator:
    """Request dependency recovery through the Jenkins runtime.

    The backend never executes commands on a Jenkins agent.
    The Shared Library detects supported project manifests and
    reinstalls dependencies without changing lockfiles.
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
                "Dependency failure detected. The AutoHeal Jenkins runtime "
                "will recreate a supported dependency environment from the "
                "existing manifest or lockfile before retrying."
            ),
        }