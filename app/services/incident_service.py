import uuid

from app.classifier.classifier import FailureClassifier
from app.collectors.jenkins import JenkinsCollector
from app.models import (
    Incident,
    FailureClassification,
    RemediationResult,
)


class IncidentService:

    def __init__(self):
        self.jenkins = JenkinsCollector()
        self.classifier = FailureClassifier()

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

        log = build.console_log or ""

        # =========================================
        # 2. CLASSIFY FAILURE
        # =========================================

        classification_data = self.classifier.classify(
            log
        )

        classification = FailureClassification(
            **classification_data
        )

        # =========================================
        # 3. CREATE INCIDENT
        # =========================================

        incident = Incident(
            incident_id=(
                f"AH-{uuid.uuid4().hex[:8].upper()}"
            ),
            source="jenkins",
            job_name=job_name,
            build_number=build_number,
            status=build.result or "UNKNOWN",
            build_url=build.url,
            console_log=log,
            classification=classification,
        )

        # =========================================
        # 4. PHASE 1 DECISION
        # =========================================

        if classification.action == "RETRY":
            remediation_message = (
                "Failure is classified as recoverable. "
                "Automatic remediation is not enabled yet."
            )

        elif classification.action == "DO_NOT_HEAL":
            remediation_message = (
                "Failure is unsafe to automatically remediate."
            )

        else:
            remediation_message = (
                "Failure could not be safely classified. "
                "Escalation is required."
            )

        incident.remediation = RemediationResult(
            action=classification.action,
            success=False,
            message=remediation_message,
        )

        # =========================================
        # 5. LOG INCIDENT
        # =========================================

        print()
        print("=" * 60)
        print("AUTOHEAL INCIDENT")
        print("=" * 60)

        print(
            f"Incident ID : {incident.incident_id}"
        )

        print(
            f"Job         : {incident.job_name}"
        )

        print(
            f"Build       : #{incident.build_number}"
        )

        print(
            f"Status      : {incident.status}"
        )

        print(
            f"Build URL   : {incident.build_url}"
        )

        print("-" * 60)
        print("CLASSIFICATION")
        print("-" * 60)

        print(
            f"Category    : {classification.category}"
        )

        print(
            f"Action      : {classification.action}"
        )

        print(
            f"Confidence  : {classification.confidence}"
        )

        print(
            f"Reason      : {classification.reason}"
        )

        print("-" * 60)
        print("PHASE 1 DECISION")
        print("-" * 60)

        print(
            f"Decision    : {classification.action}"
        )

        print(
            f"Message     : {remediation_message}"
        )

        print("=" * 60)

        return incident