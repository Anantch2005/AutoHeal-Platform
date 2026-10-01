class NetworkRemediator:
    """
    Build a Jenkins-side network recovery plan.

    The shared library performs a connectivity check on the Jenkins
    agent, while AutoHeal applies the controlled retry backoff before
    triggering the new Jenkins build.
    """

    BACKOFF_SECONDS = 10

    async def remediate(self, job_name: str) -> dict:
        return {
            "action": "CONNECTIVITY_CHECK_BACKOFF_AND_RETRY",
            "success": True,
            "remediation_performed": True,
            "parameters": {
                "AUTOHEAL_ACTION": "CONNECTIVITY_CHECK_BACKOFF",
            },
            "backoff_seconds": self.BACKOFF_SECONDS,
            "message": (
                "Network failure detected. AutoHeal will apply a "
                "short backoff, then the shared library will perform "
                "a connectivity check before continuing the retry."
            ),
        }