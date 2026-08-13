from app.remediation.jenkins import JenkinsRemediator


class RemediationExecutor:

    def __init__(self):
        self.jenkins = JenkinsRemediator()

    async def execute(
        self,
        job_name: str,
        category: str,
        action: str,
    ) -> dict:

        # =========================================
        # CODE FAILURE
        # NEVER AUTO-HEAL
        # =========================================

        if action == "DO_NOT_HEAL":

            return {
                "action": "DO_NOT_HEAL",
                "success": False,
                "message": (
                    "Code/application failure is not "
                    "safe for automatic remediation."
                ),
            }

        # =========================================
        # FLAKY TEST
        # RETRY + VERIFY
        # =========================================

        if (
            category == "FLAKY_TEST"
            and action == "RETRY"
        ):

            print(
                "Triggering Jenkins remediation build..."
            )

            parameters = {
                "AUTOHEAL_RETRY": "true",
            }

            try:

                trigger = await self.jenkins.trigger_build(
                    job_name,
                    parameters=parameters,
                )

            except Exception as exc:

                return {
                    "action": "ESCALATE",
                    "success": False,
                    "message": (
                        "Failed to trigger Jenkins retry: "
                        f"{exc}"
                    ),
                }

            # =====================================
            # CHECK TRIGGER RESPONSE
            # =====================================

            if not isinstance(trigger, dict):

                return {
                    "action": "ESCALATE",
                    "success": False,
                    "message": (
                        "Unexpected response from "
                        "Jenkins trigger."
                    ),
                }

            if not trigger.get("success", False):

                return {
                    "action": "ESCALATE",
                    "success": False,
                    "message": trigger.get(
                        "message",
                        "Failed to trigger Jenkins retry.",
                    ),
                }

            # =====================================
            # NEW BUILD NUMBER
            # =====================================

            new_build = trigger.get(
                "build_number"
            )

            queue_url = trigger.get(
                "queue_url"
            )

            if new_build is None:

                return {
                    "action": "ESCALATE",
                    "success": False,
                    "message": (
                        "Jenkins accepted the retry, "
                        "but no build number was returned."
                    ),
                    "queue_url": queue_url,
                }

            print(
                f"New Jenkins build: #{new_build}"
            )

            # =====================================
            # WAIT FOR COMPLETION / VERIFY
            # =====================================

            try:

                result = (
                    await self.jenkins.get_build_result(
                        job_name,
                        new_build,
                    )
                )

            except Exception as exc:

                return {
                    "action": "ESCALATE",
                    "success": False,
                    "message": (
                        "Failed while verifying "
                        f"Jenkins build #{new_build}: "
                        f"{exc}"
                    ),
                    "new_build_number": new_build,
                    "queue_url": queue_url,
                }

            # =====================================
            # SUCCESS → HEALED
            # =====================================

            if result == "SUCCESS":

                return {
                    "action": "RETRY",
                    "success": True,
                    "message": (
                        "Retry completed successfully. "
                        "Pipeline automatically healed."
                    ),
                    "new_build_number": new_build,
                    "verification_result": "SUCCESS",
                    "queue_url": queue_url,
                }

            # =====================================
            # FAILURE → ESCALATE
            # =====================================

            return {
                "action": "ESCALATE",
                "success": False,
                "message": (
                    "Retry completed but the pipeline "
                    "still failed."
                ),
                "new_build_number": new_build,
                "verification_result": (
                    result or "UNKNOWN"
                ),
                "queue_url": queue_url,
            }

        # =========================================
        # WORKSPACE FAILURE
        # =========================================

        if category == "WORKSPACE_FAILURE":

            return {
                "action": "ESCALATE",
                "success": False,
                "message": (
                    "Workspace remediation is not "
                    "enabled yet."
                ),
            }

        # =========================================
        # DEPENDENCY FAILURE
        # =========================================

        if category == "DEPENDENCY_FAILURE":

            return {
                "action": "ESCALATE",
                "success": False,
                "message": (
                    "Dependency remediation is not "
                    "enabled yet."
                ),
            }

        # =========================================
        # EVERYTHING ELSE
        # =========================================

        return {
            "action": "ESCALATE",
            "success": False,
            "message": (
                f"No safe remediation exists for "
                f"{category}."
            ),
        }