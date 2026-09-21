class WorkspaceRemediator:
    """
    Build a safe Jenkins-side workspace recovery plan.

    AutoHeal does not directly delete files from a Jenkins agent.
    It sends explicit parameters to Jenkins so the pipeline can:
    1. clean the workspace
    2. perform a fresh checkout
    3. run the normal pipeline
    """

    async def remediate(
        self,
        job_name: str,
    ) -> dict:

        return {
            "action": "CLEAN_WORKSPACE_AND_RETRY",
            "success": True,
            "remediation_performed": True,
            "parameters": {
                "AUTOHEAL_RETRY": "true",
                "AUTOHEAL_ACTION": "CLEAN_WORKSPACE",
                "AUTOHEAL_CLEAN_WORKSPACE": "true",
                "AUTOHEAL_FRESH_CHECKOUT": "true",
            },
            "message": (
                "Workspace failure detected. Jenkins will "
                "clean the workspace, perform a fresh checkout, "
                "and rerun the pipeline."
            ),
        }