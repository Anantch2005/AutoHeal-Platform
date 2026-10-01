class DockerRemediator:
    """
    Build a Jenkins-side Docker cache invalidation recovery plan.

    AutoHeal does not directly manipulate the Jenkins agent's Docker
    daemon. The shared docker_build step consumes AUTOHEAL_ACTION and
    performs the rebuild without the build cache.
    """

    async def remediate(self, job_name: str) -> dict:
        return {
            "action": "INVALIDATE_DOCKER_CACHE_AND_RETRY",
            "success": True,
            "remediation_performed": True,
            "parameters": {
                "AUTOHEAL_ACTION": "INVALIDATE_DOCKER_CACHE",
            },
            "message": (
                "Docker failure detected. The shared Docker build step "
                "will rebuild the affected image without cache."
            ),
        }