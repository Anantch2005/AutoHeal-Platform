
class DockerRemediator:
    """
    Build a Jenkins-side Docker cache-bypass recovery plan.

    BuildSentry performs a Docker daemon preflight. The Calculator Jenkinsfile
    detects AUTOHEAL_ACTION=DOCKER_CACHE_BYPASS and runs a scoped
    `docker build --no-cache`; the generic Shared library remains unchanged.
    """

    async def remediate(self, job_name: str) -> dict:
        return {
            "action": "DOCKER_CACHE_BYPASS_AND_RETRY",
            "success": True,
            "remediation_performed": True,
            "parameters": {
                "AUTOHEAL_ACTION": "DOCKER_CACHE_BYPASS",
            },
            "message": (
                "Docker daemon preflight and policy-approved cache-bypass "
                "build will run in the recovery pipeline."
            ),
        }