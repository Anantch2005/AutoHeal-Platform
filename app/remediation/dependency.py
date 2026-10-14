
class DependencyRemediator:
    """Create a safe dependency-recovery plan for Jenkins.

    The Jenkins Shared Library executes the allowlisted operation
    on the Jenkins agent. The backend only requests and verifies a
    separate recovery build.
    """

    async def remediate(self, job_name: str) -> dict:
        return {
            "action": "CLEAN_DEPENDENCY_ENV_AND_RETRY",
            "success": True,
            "remediation_performed": False,
            "parameters": {
                "AUTOHEAL_ACTION": "CLEAN_DEPENDENCY_ENV",
            },
            "message": (
                "Dependency recovery was requested. The Jenkins "
                "Shared Library must rebuild the supported environment "
                "from the existing manifest before verification."
            ),
        }
