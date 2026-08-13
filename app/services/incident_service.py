import uuid

from app.classifier.classifier import FailureClassifier
from app.collectors.jenkins import JenkinsCollector
from app.models import (
    Incident,
    FailureClassification,
    RemediationResult,
)
from app.remediation.executor import RemediationExecutor
from app.safety.circuit_breaker import CircuitBreaker
from app.state.processed_incidents import ProcessedIncidents


class IncidentService:

    def __init__(self):
        self.jenkins = JenkinsCollector()
        self.classifier = FailureClassifier()

        # Phase 2 remediation engine
        self.remediation = RemediationExecutor()

        # Safety protection
        self.circuit_breaker = CircuitBreaker(
            max_attempts=3,
            window_minutes=30,
        )

        # Prevent duplicate processing of the same
        # Jenkins job/build during the current process.
        self.processed_incidents = ProcessedIncidents()

    async def process_failure(
        self,
        job_name: str,
        build_number: int,
    ) -> Incident | None:

        # =========================================
        # 0. DUPLICATE INCIDENT PROTECTION
        # =========================================

        if self.processed_incidents.is_processed(
            job_name,
            build_number,
        ):
            print(
                f"Duplicate incident ignored: "
                f"{job_name} #{build_number}"
            )

            return None

        # =========================================
        # 1. COLLECT EVIDENCE
        # =========================================

        build = await self.jenkins.get_build_info(
            job_name,
            build_number,
        )

        # Only mark processed after Jenkins evidence
        # was successfully collected.
        self.processed_incidents.mark_processed(
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
        # LOG INCIDENT
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

        # =========================================
        # 4. BLOCK UNSAFE FAILURES
        # =========================================

        if classification.action in (
            "DO_NOT_HEAL",
            "ESCALATE",
        ):

            remediation_message = (
                classification.reason
            )

            incident.remediation = RemediationResult(
                action=classification.action,
                success=False,
                message=remediation_message,
            )

            print("-" * 60)
            print("SAFETY DECISION")
            print("-" * 60)

            print(
                f"Decision    : {classification.action}"
            )

            print(
                f"Message     : {remediation_message}"
            )

            print("=" * 60)

            return incident

        # =========================================
        # 5. CIRCUIT BREAKER
        # =========================================

        allowed = self.circuit_breaker.allow(
            job_name,
            classification.category,
        )

        attempt = self.circuit_breaker.count(
            job_name,
            classification.category,
        )

        print("-" * 60)
        print("SAFETY CHECK")
        print("-" * 60)

        print(
            f"Attempt     : {attempt}/3"
        )

        print(
            f"Allowed     : {allowed}"
        )

        if not allowed:

            remediation_message = (
                "Circuit breaker opened after "
                "repeated remediation attempts."
            )

            incident.remediation = RemediationResult(
                action="ESCALATE",
                success=False,
                message=remediation_message,
            )

            print(
                "Decision    : ESCALATE"
            )

            print(
                f"Message     : {remediation_message}"
            )

            print("=" * 60)

            return incident

        # =========================================
        # 6. PHASE 2 REMEDIATION
        # =========================================

        print("-" * 60)
        print("PHASE 2 REMEDIATION")
        print("-" * 60)

        print(
            f"Category    : {classification.category}"
        )

        print(
            f"Action      : {classification.action}"
        )

        try:

            result = await self.remediation.execute(
                job_name=job_name,
                category=classification.category,
                action=classification.action,
            )

        except Exception as exc:

            result = {
                "action": "ESCALATE",
                "success": False,
                "message": (
                    f"Unhandled remediation error: {exc}"
                ),
            }

        # =========================================
        # 7. STORE RESULT
        # =========================================

        incident.remediation = RemediationResult(
            action=result["action"],
            success=result["success"],
            message=result["message"],
            new_build_number=result.get(
                "new_build_number"
            ),
            verification_result=result.get(
                "verification_result"
            ),
            queue_url=result.get(
                "queue_url"
            ),
        )

        # =========================================
        # 8. LOG RESULT
        # =========================================

        print("-" * 60)
        print("REMEDIATION RESULT")
        print("-" * 60)

        print(
            f"Action      : {result['action']}"
        )

        print(
            f"Success     : {result['success']}"
        )

        print(
            f"Message     : {result['message']}"
        )

        if result.get("queue_url"):
            print(
                f"Queue       : {result['queue_url']}"
            )

        if result.get("new_build_number"):
            print(
                f"New Build   : "
                f"#{result['new_build_number']}"
            )

        if result.get("verification_result"):
            print(
                f"Verified    : "
                f"{result['verification_result']}"
            )

        # =========================================
        # 9. RESET CIRCUIT AFTER SUCCESS
        # =========================================

        if result["success"]:

            self.circuit_breaker.reset(
                job_name,
                classification.category,
            )

            print(
                "Result      : HEALED"
            )

        else:

            print(
                "Result      : ESCALATE"
            )

        print("=" * 60)

        return incident