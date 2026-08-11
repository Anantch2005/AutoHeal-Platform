import uuid

from app.classifier.classifier import FailureClassifier
from app.collectors.jenkins import JenkinsCollector
from app.models import (
    Incident,
    FailureClassification,
    RemediationResult,
)
from app.remediation.jenkins import JenkinsRemediator
from app.safety.circuit_breaker import CircuitBreaker


class IncidentService:

    def __init__(self):

        self.jenkins = JenkinsCollector()

        self.classifier = FailureClassifier()

        self.remediator = JenkinsRemediator()

        self.circuit_breaker = CircuitBreaker(
            max_attempts=3,
            window_minutes=30,
        )

    async def process_failure(
        self,
        job_name: str,
        build_number: int,
    ) -> Incident:

        # =========================================
        # 1. COLLECT EVIDENCE
        # =========================================

        build = await self.jenkins.get_build_info(
            job_name,
            build_number,
        )

        # =========================================
        # 2. CLASSIFY FAILURE
        # =========================================

        classification_data = self.classifier.classify(
            build.console_log or ""
        )

        classification = FailureClassification(
            **classification_data
        )

        # =========================================
        # 3. CREATE INCIDENT
        # =========================================

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

        print()
        print("=" * 60)
        print("AUTOHEAL INCIDENT")
        print("=" * 60)

        print(f"Incident ID : {incident.incident_id}")
        print(f"Job         : {job_name}")
        print(f"Build       : #{build_number}")
        print(f"Status      : {build.result}")

        print("-" * 60)
        print("CLASSIFICATION")
        print("-" * 60)

        print(f"Category    : {classification.category}")
        print(f"Action      : {classification.action}")
        print(f"Confidence  : {classification.confidence}")
        print(f"Reason      : {classification.reason}")

        # =========================================
        # 4. CODE FAILURE → NEVER AUTO-HEAL
        # =========================================

        if classification.action == "DO_NOT_HEAL":

            incident.remediation = RemediationResult(
                action="DO_NOT_HEAL",
                success=False,
                message=(
                    "Automatic remediation blocked because "
                    "this appears to be a code failure."
                ),
            )

            print("-" * 60)
            print("REMEDIATION")
            print("-" * 60)

            print("Decision    : BLOCK")
            print("Reason      : Code failure")

            return incident

        # =========================================
        # 5. ONLY RETRY SAFE CATEGORIES
        # =========================================

        if classification.action == "RETRY":

            allowed = self.circuit_breaker.allow(
                job_name,
                classification.category,
            )

            attempt = self.circuit_breaker.get_attempt_count(
                job_name,
                classification.category,
            )

            print("-" * 60)
            print("SAFETY CHECK")
            print("-" * 60)

            print(f"Attempt     : {attempt}/3")
            print(f"Allowed     : {allowed}")

            # =====================================
            # CIRCUIT BREAKER
            # =====================================

            if not allowed:

                incident.remediation = RemediationResult(
                    action="ESCALATE",
                    success=False,
                    message=(
                        "Circuit breaker opened after "
                        "repeated remediation attempts."
                    ),
                )

                print("Decision    : ESCALATE")

                return incident

            # =====================================
            # 6. TRIGGER JENKINS RETRY
            # =====================================

            try:

                print("-" * 60)
                print("REMEDIATION")
                print("-" * 60)

                print("Action      : RETRY")
                print("Status      : Triggering Jenkins...")

                new_build = await self.remediator.trigger_build(
                    job_name
                )

                print(
                    f"New Build   : #{new_build}"
                )

                # =================================
                # 7. VERIFY
                # =================================

                print("Status      : Waiting for result...")

                result = await self.remediator.get_build_result(
                    job_name,
                    new_build,
                )

                print(
                    f"Verification: {result}"
                )

                # =================================
                # 8. HEALED
                # =================================

                if result == "SUCCESS":

                    self.circuit_breaker.reset(
                        job_name,
                        classification.category,
                    )

                    incident.remediation = RemediationResult(
                        action="RETRY",
                        success=True,
                        message=(
                            "Retry succeeded. "
                            "Pipeline automatically healed."
                        ),
                        new_build_number=new_build,
                        verification_result=result,
                    )

                    print("Result      : HEALED")

                # =================================
                # 9. STILL BROKEN
                # =================================

                else:

                    incident.remediation = RemediationResult(
                        action="RETRY",
                        success=False,
                        message=(
                            "Retry completed but the "
                            "pipeline is still failing."
                        ),
                        new_build_number=new_build,
                        verification_result=result,
                    )

                    print("Result      : ESCALATE")

            except Exception as exc:

                incident.remediation = RemediationResult(
                    action="RETRY",
                    success=False,
                    message=f"Remediation error: {exc}",
                )

                print(
                    f"Result      : ERROR - {exc}"
                )

        return incident