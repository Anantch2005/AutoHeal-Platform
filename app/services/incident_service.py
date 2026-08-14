import uuid

from app.classifier.classifier import FailureClassifier
from app.collectors.jenkins import JenkinsCollector
from app.database.repository import IncidentRepository
from app.models import (
    Incident,
    FailureClassification,
    RemediationResult,
)
from app.remediation.executor import RemediationExecutor
from app.safety.circuit_breaker import CircuitBreaker


class IncidentService:

    def __init__(self):
        self.jenkins = JenkinsCollector()
        self.classifier = FailureClassifier()
        self.remediation = RemediationExecutor()

        self.circuit_breaker = CircuitBreaker(
            max_attempts=3,
            window_minutes=30,
        )

        # PostgreSQL persistence
        self.repository = IncidentRepository()

    async def process_failure(
        self,
        job_name: str,
        build_number: int,
    ) -> Incident | None:

        # =========================================
        # 0. PERSISTENT DUPLICATE PROTECTION
        # =========================================

        if self.repository.exists(
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

        log = build.console_log or ""

        # =========================================
        # 2. CLASSIFY
        # =========================================

        classification_data = self.classifier.classify(
            log
        )

        classification = FailureClassification(
            **classification_data
        )

        # =========================================
        # 3. CREATE INCIDENT OBJECT
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
        # 4. PERSIST INCIDENT
        # =========================================

        database_incident_id = (
            self.repository.create_incident(
                incident_id=incident.incident_id,
                source=incident.source,
                job_name=incident.job_name,
                build_number=incident.build_number,
                status=incident.status,
                build_url=incident.build_url,
                failure_category=classification.category,
                failure_action=classification.action,
                reason=classification.reason,
                matched_pattern=(
                    classification.matched_pattern
                ),
                confidence=classification.confidence,
                console_log=incident.console_log,
            )
        )

        self.repository.add_audit_event(
            incident_id=database_incident_id,
            event_type="INCIDENT_CREATED",
            message=(
                f"Incident created for Jenkins "
                f"{job_name} #{build_number}"
            ),
        )

        # =========================================
        # LOG
        # =========================================

        print()
        print("=" * 60)
        print("AUTOHEAL INCIDENT")
        print("=" * 60)

        print(
            f"Incident ID : {incident.incident_id}"
        )

        print(
            f"Job         : {job_name}"
        )

        print(
            f"Build       : #{build_number}"
        )

        print(
            f"Status      : {incident.status}"
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
        # 5. UNSAFE FAILURE
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

            self.repository.add_audit_event(
                incident_id=database_incident_id,
                event_type="REMEDIATION_BLOCKED",
                message=remediation_message,
            )

            self.repository.create_attempt(
                incident_id=database_incident_id,
                attempt_number=1,
                action=classification.action,
                success=False,
                message=remediation_message,
                original_build_number=build_number,
                retry_build_number=None,
                queue_url=None,
                verification_result=None,
            )

            print("-" * 60)
            print("SAFETY DECISION")
            print("-" * 60)

            print(
                f"Decision    : {classification.action}"
            )

            print("=" * 60)

            return incident

        # =========================================
        # 6. CIRCUIT BREAKER
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

            self.repository.create_attempt(
                incident_id=database_incident_id,
                attempt_number=attempt,
                action="ESCALATE",
                success=False,
                message=remediation_message,
                original_build_number=build_number,
                retry_build_number=None,
                queue_url=None,
                verification_result=None,
            )

            self.repository.add_audit_event(
                incident_id=database_incident_id,
                event_type="CIRCUIT_BREAKER_OPEN",
                message=remediation_message,
            )

            print(
                "Decision    : ESCALATE"
            )

            print("=" * 60)

            return incident

        # =========================================
        # 7. REMEDIATION
        # =========================================

        print("-" * 60)
        print("PHASE 3 REMEDIATION")
        print("-" * 60)

        self.repository.add_audit_event(
            incident_id=database_incident_id,
            event_type="REMEDIATION_STARTED",
            message=(
                f"Attempt {attempt}: "
                f"{classification.action}"
            ),
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
                    f"Remediation exception: {exc}"
                ),
            }

        # =========================================
        # 8. PERSIST REMEDIATION
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

        self.repository.create_attempt(
            incident_id=database_incident_id,
            attempt_number=attempt,
            action=result["action"],
            success=result["success"],
            message=result["message"],
            original_build_number=build_number,
            retry_build_number=result.get(
                "new_build_number"
            ),
            queue_url=result.get(
                "queue_url"
            ),
            verification_result=result.get(
                "verification_result"
            ),
        )

        # =========================================
        # 9. AUDIT RESULT
        # =========================================

        event_type = (
            "REMEDIATION_SUCCEEDED"
            if result["success"]
            else "REMEDIATION_ESCALATED"
        )

        self.repository.add_audit_event(
            incident_id=database_incident_id,
            event_type=event_type,
            message=result["message"],
        )

        # =========================================
        # LOG RESULT
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
        # 10. RESET CIRCUIT AFTER SUCCESS
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