class NetworkRemediator:
    """
    Build a Jenkins-side network recovery plan.

    The connectivity check must run on the Jenkins agent because
    the failure may only exist in that agent's network namespace.
    """

    BACKOFF_SECONDS = 10

    async def remediate(
        self,
        job_name: str,
    ) -> dict:

        return {
            "action": (
                "CONNECTIVITY_CHECK_BACKOFF_AND_RETRY"
            ),
            "success": True,
            "remediation_performed": True,
            "parameters": {
                "AUTOHEAL_RETRY": "true",
                "AUTOHEAL_ACTION": (
                    "CONNECTIVITY_CHECK_BACKOFF"
                ),
                "AUTOHEAL_CONNECTIVITY_CHECK": "true",
                "AUTOHEAL_BACKOFF_SECONDS": str(
                    self.BACKOFF_SECONDS
                ),
            },
            "backoff_seconds": (
                self.BACKOFF_SECONDS
            ),
            "message": (
                "Network failure detected. Jenkins will "
                "perform a connectivity check, wait for a "
                "short backoff, and rerun the pipeline."
            ),
        }