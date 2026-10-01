class WorkspaceRemediator:
    """
    Build a Jenkins-side workspace recovery plan.

    AutoHeal does not manipulate the Jenkins agent remotely.
    The shared library consumes AUTOHEAL_ACTION and performs the
    workspace cleanup immediately before the normal checkout.
    """

    async def remediate(self, job_name: str) -> dict:
        return {
            "action": "CLEAN_WORKSPACE_AND_RETRY",
            "success": True,
            "remediation_performed": True,
            "parameters": {
                "AUTOHEAL_ACTION": "CLEAN_WORKSPACE",
            },
            "message": (
                "Workspace failure detected. Jenkins will clean "
                "the current workspace and perform a fresh checkout "
                "before rerunning the pipeline."
            ),
        }