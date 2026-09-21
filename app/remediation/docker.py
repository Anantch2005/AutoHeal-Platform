class DockerRemediator:
    """
    Build a Jenkins-side Docker cache invalidation recovery plan.

    AutoHeal does not directly manipulate the Jenkins agent's
    Docker daemon. Jenkins receives the explicit instruction to
    rebuild without using the Docker build cache.
    """

    async def remediate(
        self,
        job_name: str,
    ) -> dict:

        return {
            "action": "INVALIDATE_DOCKER_CACHE_AND_RETRY",
            "success": True,
            "remediation_performed": True,
            "parameters": {
                "AUTOHEAL_RETRY": "true",
                "AUTOHEAL_ACTION": (
                    "INVALIDATE_DOCKER_CACHE"
                ),
                "AUTOHEAL_DOCKER_NO_CACHE": "true",
            },
            "message": (
                "Docker failure detected. Jenkins will rebuild "
                "the affected image without the Docker build cache "
                "and then verify the result."
            ),
        }