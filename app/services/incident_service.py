import uuid

from app.collectors.jenkins import JenkinsCollector
from app.classifier.classifier import FailureClassifier
from app.models import (
    Incident,
    FailureClassification,
    RemediationResult,
)
from app.remediation.jenkins import JenkinsRemediator


class IncidentService:

    def __init__(self):
        self.jenkins = JenkinsCollector()
        self.classifier = FailureClassifier()
        self.remediator = JenkinsRemediator()

    async def process_failure(
        self,
        job_name: str,
        build_number: int,
    ) -> Incident:

        # -----------------------------------------
        # 1. Collect evidence
        # -----------------------------------------

        build = await self.jenkins.get_build_info(
            job_name,
            build_number,
        )

        # -----------------------------------------
        # 2. Classify
        # -----------------------------------------

        classification_data = self.classifier.classify(
            build.console_log or ""
        )

        classification = FailureClassification(
            **classification_data
        )

        # -----------------------------------------
        # 3. Create incident
        # -----------------------------------------

        incident = Incident(
            incident_id=f"AH-{uuid.uuid4().hex[:8].upper()}",
            source="jenkins",
            job_name=job_name,
            build_number=build_number,
            status=build.result or "UNKNOWN",
            build_url=build.url,
            console_log=build.console_log,
            classification=classification,
        )

        print("\n" + "=" * 60)
        print("AUTOHEAL INCIDENT")
        print("=" * 60)

        print(f"Incident ID : {incident.incident_id}")
        print(f"Job         : {incident.job_name}")
        print(f"Build       : #{incident.build_number}")
        print(f"Status      : {incident.status}")

        print("-" * 60)
        print("CLASSIFICATION")
        print("-" * 60)

        print(f"Category    : {classification.category}")
        print(f"Action      : {classification.action}")
        print(f"Confidence  : {classification.confidence}")
        print(f"Reason      : {classification.reason}")

        # -----------------------------------------
        # 4. Safety decision
        # -----------------------------------------

        if classification.action == "DO_NOT_HEAL":

            incident.remediation = RemediationResult(
                action="DO_NOT_HEAL",
                success=False,
                message=(
                    "Failure classified as a code failure. "
                    "Automatic remediation was intentionally blocked."
                ),
            )

            print("-" * 60)
            print("REMEDIATION")
            print("-" * 60)
            print("Action      : BLOCKED")
            print("Reason      : Code failure")
            print("=" * 60)

            return incident

        # -----------------------------------------
        # 5. Retry
        # -----------------------------------------

        if classification.action == "RETRY":

            print("-" * 60)
            print("REMEDIATION")
            print("-" * 60)
            print("Action      : RETRY")
            print("Status      : Starting new Jenkins build...")

            try:

                new_build = await self.remediator.trigger_build(
                    job_name
                )

                print(
                    f"New Build   : #{new_build}"
                )

                # ---------------------------------
                # 6. Verification
                # ---------------------------------

                result = await self.remediator.get_build_result(
                    job_name,
                    new_build,
                )

                if result == "SUCCESS":

                    incident.remediation = RemediationResult(
                        action="RETRY",
                        success=True,
                        message="Retry succeeded. Pipeline healed.",
                        new_build_number=new_build,
                        verification_result=result,
                    )

                    print("Verification: SUCCESS")
                    print("Result      : HEALED")

                else:

                    incident.remediation = RemediationResult(
                        action="RETRY",
                        success=False,
                        message=(
                            "Retry completed but the pipeline "
                            "still failed."
                        ),
                        new_build_number=new_build,
                        verification_result=result,
                    )

                    print(
                        f"Verification: {result}"
                    )
                    print("Result      : ESCALATE")

            except Exception as exc:

                incident.remediation = RemediationResult(
                    action="RETRY",
                    success=False,
                    message=f"Remediation failed: {exc}",
                )

                print(
                    f"Remediation error: {exc}"
                )

        return incident