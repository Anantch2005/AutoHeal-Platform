import time
import uuid
from app.ai.classifier import AIClassifier
from app.classifier.classifier import FailureClassifier
from app.collectors.jenkins import JenkinsCollector
from app.database.repository import IncidentRepository
from app.models import (
    Incident,
    FailureClassification,
    RemediationResult,
)
from app.observability.telemetry import (
    ai_classifications_total,
    escalated_total,
    healed_total,
    incidents_total,
    policy_decisions_total,
    policy_denials_total,
    processing_duration,
    remediation_attempts_total,
    remediation_failure_total,
    remediation_success_total,
    tracer,
)
from app.policy.engine import PolicyEngine
from app.remediation.executor import RemediationExecutor
from app.safety.circuit_breaker import CircuitBreaker
class IncidentService:
    def __init__(self):
        self.jenkins = JenkinsCollector()
        self.classifier = FailureClassifier()
        # Local Ollama diagnostic assistant.
        self.ai_classifier = AIClassifier()
        # Policy Engine remains authoritative.
        self.policy = PolicyEngine()
        # Remediation engine.
        self.remediation = RemediationExecutor()
        # Safety protection.
        self.circuit_breaker = CircuitBreaker(
            max_attempts=3,
            window_minutes=30,
        )
        # PostgreSQL persistence.
        self.repository = IncidentRepository()
    def _record_processing_duration(
        self,
        start_time: float,
        job_name: str,
    ):
        processing_duration.record(
            time.perf_counter() - start_time,
            {
                "job_name": job_name,
            },
        )
    def _format_ai_reasoning(
        self,
        ai_result,
    ) -> str:
        """
        Combine Ollama's reasoning and recommendations into the
        existing ai_reasoning database field.
        No database migration is required.
        """
        parts = [
            ai_result.reasoning.strip()
        ]
        if ai_result.recommendations:
            parts.append(
                "Recommended checks:\n"
                + "\n".join(
                    f"- {item}"
                    for item in ai_result.recommendations
                )
            )
        return "\n\n".join(
            part
            for part in parts
            if part
        )
    def _print_result_summary(
        self,
        incident: Incident,
        classification: FailureClassification,
        policy,
        result: RemediationResult,
        database_incident_id: int,
    ) -> None:
        """
        Print and persist a complete AutoHeal result summary.
        """
        final_result = (
            "HEALED"
            if result.success
            else "ESCALATED"
        )
        retry_build = (
            f"#{result.new_build_number}"
            if result.new_build_number is not None
            else "None"
        )
        verification = (
            result.verification_result
            or "Not performed"
        )
        print()
        print("=" * 72)
        print("AUTOHEAL RESULT SUMMARY")
        print("=" * 72)
        print(
            f"Incident ID       : "
            f"{incident.incident_id}"
        )
        print(
            f"Job               : "
            f"{incident.job_name}"
        )
        print(
            f"Failed Build      : "
            f"#{incident.build_number}"
        )
        print(
            f"Failure Category  : "
            f"{classification.category}"
        )
        print(
            f"Classifier Source : "
            f"{classification.source}"
        )
        print(
            f"Classifier Conf.  : "
            f"{classification.confidence:.2f}"
        )
        print(
            f"Policy Allowed    : "
            f"{policy.allowed}"
        )
        print(
            f"Policy Risk       : "
            f"{policy.risk_level}"
        )
        print(
            f"Policy Action     : "
            f"{policy.action}"
        )
        print(
            f"Remediation       : "
            f"{result.action}"
        )
        print(
            f"Retry Build       : "
            f"{retry_build}"
        )
        print(
            f"Verification      : "
            f"{verification}"
        )
        # =========================================
        # AI OUTPUT
        # =========================================
        if (
            classification.ai_root_cause
            or classification.ai_reasoning
            or classification.ai_confidence is not None
        ):
            print("-" * 72)
            print("AI DIAGNOSTIC OUTPUT")
            print("-" * 72)
            print(
                f"AI Category       : "
                f"{getattr(classification, 'ai_category', None) or 'None'}"
            )
            print(
                f"AI Root Cause     : "
                f"{classification.ai_root_cause or 'None'}"
            )
            print(
                f"AI Confidence     : "
                f"{classification.ai_confidence}"
            )
            print(
                f"AI Reasoning      : "
                f"{classification.ai_reasoning or 'None'}"
            )
            if classification.ai_evidence:
                print(
                    "AI Evidence       : "
                    + "; ".join(
                        classification.ai_evidence
                    )
                )
        print("-" * 72)
        print(
            f"Final Result      : "
            f"{final_result}"
        )
        print("=" * 72)
        # =========================================
        # PERSIST FINAL RESULT
        # =========================================
        self.repository.add_audit_event(
            incident_id=database_incident_id,
            event_type="AUTOHEAL_RESULT",
            message=(
                f"category={classification.category}; "
                f"classifier_source={classification.source}; "
                f"classifier_confidence={classification.confidence}; "
                f"policy_allowed={policy.allowed}; "
                f"policy_risk={policy.risk_level}; "
                f"policy_action={policy.action}; "
                f"remediation={result.action}; "
                f"retry_build={result.new_build_number}; "
                f"verification={verification}; "
                f"final_result={final_result}; "
                f"ai_confidence={classification.ai_confidence}; "
                f"ai_root_cause="
                f"{classification.ai_root_cause or ''}"
            ),
        )
    async def process_failure(
        self,
        job_name: str,
        build_number: int,
    ) -> Incident | None:
        start_time = time.perf_counter()
        # =========================================
        # OBSERVABILITY — INCIDENT RECEIVED
        # =========================================
        incidents_total.add(
            1,
            {
                "source": "jenkins",
                "job_name": job_name,
            },
        )
        with tracer.start_as_current_span(
            "autoheal.process_failure"
        ) as root_span:
            root_span.set_attribute(
                "service.name",
                "autoheal",
            )
            root_span.set_attribute(
                "jenkins.job.name",
                job_name,
            )
            root_span.set_attribute(
                "jenkins.build.number",
                build_number,
            )
            # =========================================
            # 1. PERSISTENT DUPLICATE PROTECTION
            # =========================================
            with tracer.start_as_current_span(
                "autoheal.duplicate_check"
            ):
                if self.repository.exists(
                    job_name,
                    build_number,
                ):
                    root_span.set_attribute(
                        "incident.duplicate",
                        True,
                    )
                    print(
                        f"Duplicate incident ignored: "
                        f"{job_name} #{build_number}"
                    )
                    self._record_processing_duration(
                        start_time,
                        job_name,
                    )
                    return None
            # =========================================
            # 2. COLLECT EVIDENCE
            # =========================================
            with tracer.start_as_current_span(
                "autoheal.collect_evidence"
            ) as span:
                span.set_attribute(
                    "jenkins.job.name",
                    job_name,
                )
                span.set_attribute(
                    "jenkins.build.number",
                    build_number,
                )
                build = (
                    await self.jenkins.get_build_info(
                        job_name,
                        build_number,
                    )
                )
                log = build.console_log or ""
                span.set_attribute(
                    "jenkins.build.result",
                    build.result or "UNKNOWN",
                )
                span.set_attribute(
                    "jenkins.console_log_length",
                    len(log),
                )
            # =========================================
            # 3. RULE-BASED CLASSIFICATION
            # =========================================
            with tracer.start_as_current_span(
                "autoheal.classification.rules"
            ) as span:
                classification_data = (
                    self.classifier.classify(log)
                )
                classification = (
                    FailureClassification(
                        **classification_data
                    )
                )
                span.set_attribute(
                    "failure.category",
                    classification.category,
                )
                span.set_attribute(
                    "failure.action",
                    classification.action,
                )
                span.set_attribute(
                    "classifier.source",
                    "rules",
                )
                span.set_attribute(
                    "classifier.confidence",
                    classification.confidence,
                )
            # =========================================
            # 4. AI DIAGNOSTIC ANALYSIS
            # =========================================
            #
            # Ollama analyzes EVERY failure.
            #
            # AI is advisory.
            #
            # Rules remain authoritative for known failures.
            #
            # Policy remains authoritative for remediation.
            # =========================================
            ai_was_used = False
            ai_result = None
            rules_category = classification.category
            if self.ai_classifier.enabled:
                print("-" * 60)
                print("AI DIAGNOSTIC ANALYSIS")
                print("-" * 60)
                with tracer.start_as_current_span(
                    "autoheal.ai_diagnosis"
                ) as span:
                    try:
                        ai_result = (
                            await self.ai_classifier.classify(
                                log
                            )
                        )
                        ai_was_used = True
                        ai_classifications_total.add(
                            1,
                            {
                                "category": (
                                    rules_category
                                ),
                            },
                        )
                        span.set_attribute(
                            "ai.category",
                            ai_result.category,
                        )
                        span.set_attribute(
                            "ai.confidence",
                            ai_result.confidence,
                        )
                        span.set_attribute(
                            "ai.root_cause",
                            ai_result.root_cause,
                        )
                        span.set_attribute(
                            "ai.reasoning",
                            ai_result.reasoning,
                        )
                        span.set_attribute(
                            "ai.role",
                            "diagnostic",
                        )
                        span.set_attribute(
                            "rules.category",
                            rules_category,
                        )
                        print(
                            f"AI Category  : "
                            f"{ai_result.category}"
                        )
                        print(
                            f"AI Root Cause: "
                            f"{ai_result.root_cause}"
                        )
                        print(
                            f"AI Reasoning : "
                            f"{ai_result.reasoning}"
                        )
                        print(
                            f"AI Confidence: "
                            f"{ai_result.confidence}"
                        )
                        if ai_result.matched_evidence:
                            print(
                                "AI Evidence  : "
                                + "; ".join(
                                    ai_result.matched_evidence
                                )
                            )
                        if ai_result.recommendations:
                            print(
                                "AI Checks    :"
                            )
                            for recommendation in (
                                ai_result.recommendations
                            ):
                                print(
                                    f"  - {recommendation}"
                                )
                        # -----------------------------------------
                        # AI IS ADVISORY
                        # -----------------------------------------
                        #
                        # IMPORTANT:
                        # Keep the deterministic classification.
                        #
                        # Do not replace CODE_FAILURE with whatever
                        # category Ollama happens to return.
                        #
                        # Do not allow Ollama to change policy.
                        # -----------------------------------------
                        ai_reasoning = (
                            self._format_ai_reasoning(
                                ai_result
                            )
                        )
                        classification = (
                            classification.model_copy(
                                update={
                                    "ai_root_cause": (
                                        ai_result.root_cause
                                    ),
                                    "ai_reasoning": (
                                        ai_reasoning
                                    ),
                                    "ai_confidence": (
                                        ai_result.confidence
                                    ),
                                    "ai_evidence": (
                                        ai_result.matched_evidence
                                    ),
                                }
                            )
                        )
                        if (
                            ai_result.category
                            != rules_category
                        ):
                            print(
                                "AI/rules diagnostic difference: "
                                f"rules={rules_category}, "
                                f"ai={ai_result.category}"
                            )
                    except Exception as exc:
                        span.record_exception(
                            exc
                        )
                        print(
                            "AI diagnostic analysis failed: "
                            f"{exc}"
                        )
                        # AI failure must NEVER change the
                        # deterministic AutoHeal decision.
                        classification = (
                            classification.model_copy(
                                update={
                                    "ai_root_cause": None,
                                    "ai_reasoning": (
                                        "AI analysis unavailable: "
                                        f"{exc}"
                                    ),
                                    "ai_confidence": None,
                                    "ai_evidence": [],
                                }
                            )
                        )
                        # Safe rule-based remediation continues
                        # exactly as before.
            # =========================================
            # 5. CREATE INCIDENT
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
            root_span.set_attribute(
                "incident.id",
                incident.incident_id,
            )
            root_span.set_attribute(
                "failure.category",
                classification.category,
            )
            root_span.set_attribute(
                "classifier.source",
                classification.source,
            )
            # =========================================
            # 6. PERSIST INCIDENT
            # =========================================
            with tracer.start_as_current_span(
                "autoheal.persist_incident"
            ):
                database_incident_id = (
                    self.repository.create_incident(
                        incident_id=incident.incident_id,
                        source=incident.source,
                        job_name=incident.job_name,
                        build_number=incident.build_number,
                        status=incident.status,
                        build_url=incident.build_url,
                        failure_category=(
                            classification.category
                        ),
                        failure_action=(
                            classification.action
                        ),
                        reason=classification.reason,
                        matched_pattern=(
                            classification.matched_pattern
                        ),
                        confidence=(
                            classification.confidence
                        ),
                        console_log=incident.console_log,
                        classifier_source=(
                            classification.source
                        ),
                        ai_root_cause=(
                            classification.ai_root_cause
                        ),
                        ai_reasoning=(
                            classification.ai_reasoning
                        ),
                        ai_confidence=(
                            classification.ai_confidence
                        ),
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
            # 7. AI AUDIT
            # =========================================
            if ai_was_used and ai_result is not None:
                self.repository.add_audit_event(
                    incident_id=database_incident_id,
                    event_type="AI_ANALYSIS",
                    message=(
                        f"rules_category="
                        f"{rules_category}; "
                        f"ai_category="
                        f"{ai_result.category}; "
                        f"confidence="
                        f"{ai_result.confidence}; "
                        f"root_cause="
                        f"{ai_result.root_cause}; "
                        f"reasoning="
                        f"{ai_result.reasoning}; "
                        f"evidence="
                        f"{'; '.join(ai_result.matched_evidence)}; "
                        f"recommendations="
                        f"{'; '.join(ai_result.recommendations)}"
                    ),
                )
            # =========================================
            # LOG INCIDENT
            # =========================================
            print()
            print("=" * 60)
            print("AUTOHEAL INCIDENT")
            print("=" * 60)
            print(
                f"Incident ID : "
                f"{incident.incident_id}"
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
                f"Category    : "
                f"{classification.category}"
            )
            print(
                f"Action      : "
                f"{classification.action}"
            )
            print(
                f"Source      : "
                f"{classification.source}"
            )
            print(
                f"Confidence  : "
                f"{classification.confidence}"
            )
            print(
                f"Reason      : "
                f"{classification.reason}"
            )
            # =========================================
            # 8. POLICY ENGINE
            # =========================================
            with tracer.start_as_current_span(
                "autoheal.policy.evaluate"
            ) as span:
                policy = self.policy.evaluate(
                    category=classification.category,
                    classifier_action=(
                        classification.action
                    ),
                    source=classification.source,
                    confidence=(
                        classification.confidence
                    ),
                )
                policy_decisions_total.add(
                    1,
                    {
                        "category": policy.category,
                        "allowed": str(
                            policy.allowed
                        ),
                        "action": policy.action,
                        "risk": policy.risk_level,
                    },
                )
                span.set_attribute(
                    "policy.category",
                    policy.category,
                )
                span.set_attribute(
                    "policy.allowed",
                    policy.allowed,
                )
                span.set_attribute(
                    "policy.action",
                    policy.action,
                )
                span.set_attribute(
                    "policy.risk_level",
                    policy.risk_level,
                )
                span.set_attribute(
                    "policy.max_attempts",
                    policy.max_attempts,
                )
            print("-" * 60)
            print("POLICY DECISION")
            print("-" * 60)
            print(
                f"Risk Level      : "
                f"{policy.risk_level}"
            )
            print(
                f"Allowed         : "
                f"{policy.allowed}"
            )
            print(
                f"Policy Action   : "
                f"{policy.action}"
            )
            print(
                f"Max Attempts    : "
                f"{policy.max_attempts}"
            )
            print(
                f"Approval Needed : "
                f"{policy.requires_approval}"
            )
            print(
                f"Reason          : "
                f"{policy.reason}"
            )
            self.repository.add_audit_event(
                incident_id=database_incident_id,
                event_type="POLICY_EVALUATED",
                message=(
                    f"category={policy.category}; "
                    f"risk={policy.risk_level}; "
                    f"allowed={policy.allowed}; "
                    f"action={policy.action}; "
                    f"max_attempts="
                    f"{policy.max_attempts}; "
                    f"approval="
                    f"{policy.requires_approval}"
                ),
            )
            # =========================================
            # 9. POLICY DENIED
            # =========================================
            if not policy.allowed:
                policy_denials_total.add(
                    1,
                    {
                        "category": policy.category,
                        "reason": policy.action,
                    },
                )
                escalated_total.add(
                    1,
                    {
                        "category": policy.category,
                        "action": policy.action,
                    },
                )
                root_span.set_attribute(
                    "result",
                    "ESCALATED",
                )
                incident.remediation = (
                    RemediationResult(
                        action=policy.action,
                        success=False,
                        message=policy.reason,
                    )
                )
                self.repository.create_attempt(
                    incident_id=database_incident_id,
                    attempt_number=0,
                    action=policy.action,
                    success=False,
                    message=policy.reason,
                    original_build_number=build_number,
                    retry_build_number=None,
                    queue_url=None,
                    verification_result=None,
                )
                self.repository.add_audit_event(
                    incident_id=database_incident_id,
                    event_type="POLICY_DENIED",
                    message=policy.reason,
                )
                self._print_result_summary(
                    incident=incident,
                    classification=classification,
                    policy=policy,
                    result=incident.remediation,
                    database_incident_id=database_incident_id,
                )
                print("-" * 60)
                print("POLICY RESULT")
                print("-" * 60)
                print(
                    f"Decision    : "
                    f"{policy.action}"
                )
                print(
                    f"Message     : "
                    f"{policy.reason}"
                )
                print("=" * 60)
                self._record_processing_duration(
                    start_time,
                    job_name,
                )
                return incident
            # =========================================
            # 10. CIRCUIT BREAKER
            # =========================================
            with tracer.start_as_current_span(
                "autoheal.safety.circuit_breaker"
            ) as span:
                allowed = (
                    self.circuit_breaker.allow(
                        job_name,
                        policy.category,
                    )
                )
                attempt = (
                    self.circuit_breaker.count(
                        job_name,
                        policy.category,
                    )
                )
                span.set_attribute(
                    "circuit_breaker.allowed",
                    allowed,
                )
                span.set_attribute(
                    "circuit_breaker.attempt",
                    attempt,
                )
            print("-" * 60)
            print("SAFETY CHECK")
            print("-" * 60)
            print(
                f"Attempt : {attempt}/3"
            )
            print(
                f"Allowed : {allowed}"
            )
            # =========================================
            # 11. POLICY ATTEMPT LIMIT
            # =========================================
            if attempt > policy.max_attempts:
                message = (
                    f"Policy limit reached for "
                    f"{policy.category}. "
                    f"Maximum attempts: "
                    f"{policy.max_attempts}."
                )
                escalated_total.add(
                    1,
                    {
                        "category": policy.category,
                        "action": "ESCALATE",
                    },
                )
                root_span.set_attribute(
                    "result",
                    "ESCALATED",
                )
                incident.remediation = (
                    RemediationResult(
                        action="ESCALATE",
                        success=False,
                        message=message,
                    )
                )
                self.repository.create_attempt(
                    incident_id=database_incident_id,
                    attempt_number=attempt,
                    action="ESCALATE",
                    success=False,
                    message=message,
                    original_build_number=build_number,
                    retry_build_number=None,
                    queue_url=None,
                    verification_result=None,
                )
                self.repository.add_audit_event(
                    incident_id=database_incident_id,
                    event_type="POLICY_LIMIT_REACHED",
                    message=message,
                )
                self._print_result_summary(
                    incident=incident,
                    classification=classification,
                    policy=policy,
                    result=incident.remediation,
                    database_incident_id=database_incident_id,
                )
                print(
                    "Decision    : ESCALATE"
                )
                print(
                    f"Message     : {message}"
                )
                print("=" * 60)
                self._record_processing_duration(
                    start_time,
                    job_name,
                )
                return incident
            # =========================================
            # 12. CIRCUIT BREAKER DENIED
            # =========================================
            if not allowed:
                message = (
                    "Circuit breaker opened after "
                    "repeated remediation attempts."
                )
                escalated_total.add(
                    1,
                    {
                        "category": policy.category,
                        "action": "ESCALATE",
                    },
                )
                root_span.set_attribute(
                    "result",
                    "ESCALATED",
                )
                incident.remediation = (
                    RemediationResult(
                        action="ESCALATE",
                        success=False,
                        message=message,
                    )
                )
                self.repository.create_attempt(
                    incident_id=database_incident_id,
                    attempt_number=attempt,
                    action="ESCALATE",
                    success=False,
                    message=message,
                    original_build_number=build_number,
                    retry_build_number=None,
                    queue_url=None,
                    verification_result=None,
                )
                self.repository.add_audit_event(
                    incident_id=database_incident_id,
                    event_type="CIRCUIT_BREAKER_OPEN",
                    message=message,
                )
                self._print_result_summary(
                    incident=incident,
                    classification=classification,
                    policy=policy,
                    result=incident.remediation,
                    database_incident_id=database_incident_id,
                )
                print(
                    "Decision    : ESCALATE"
                )
                print("=" * 60)
                self._record_processing_duration(
                    start_time,
                    job_name,
                )
                return incident
            # =========================================
            # 13. POLICY-CONTROLLED REMEDIATION
            # =========================================
            print("-" * 60)
            print(
                "POLICY-CONTROLLED REMEDIATION"
            )
            print("-" * 60)
            print(
                f"Policy Action : "
                f"{policy.action}"
            )
            print(
                f"Risk Level    : "
                f"{policy.risk_level}"
            )
            print(
                f"Max Attempts  : "
                f"{policy.max_attempts}"
            )
            self.repository.add_audit_event(
                incident_id=database_incident_id,
                event_type="REMEDIATION_STARTED",
                message=(
                    f"Attempt {attempt}: "
                    f"{policy.action}"
                ),
            )
            remediation_attempts_total.add(
                1,
                {
                    "category": policy.category,
                    "action": policy.action,
                },
            )
            with tracer.start_as_current_span(
                "autoheal.remediation"
            ) as span:
                span.set_attribute(
                    "remediation.category",
                    policy.category,
                )
                span.set_attribute(
                    "remediation.action",
                    policy.action,
                )
                span.set_attribute(
                    "remediation.attempt",
                    attempt,
                )
                try:
                    result = (
                        await self.remediation.execute(
                            job_name=job_name,
                            category=policy.category,
                            action=policy.action,
                        )
                    )
                except Exception as exc:
                    span.record_exception(exc)
                    result = {
                        "action": "ESCALATE",
                        "success": False,
                        "message": (
                            f"Remediation exception: "
                            f"{exc}"
                        ),
                    }
            # =========================================
            # 14. STORE REMEDIATION RESULT
            # =========================================
            incident.remediation = (
                RemediationResult(
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
            # 15. AUDIT RESULT
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
            # 16. METRICS RESULT
            # =========================================
            if result["success"]:
                remediation_success_total.add(
                    1,
                    {
                        "category": policy.category,
                        "action": result["action"],
                    },
                )
                healed_total.add(
                    1,
                    {
                        "category": policy.category,
                    },
                )
                root_span.set_attribute(
                    "result",
                    "HEALED",
                )
                root_span.set_attribute(
                    "remediation.success",
                    True,
                )
            else:
                remediation_failure_total.add(
                    1,
                    {
                        "category": policy.category,
                        "action": result["action"],
                    },
                )
                escalated_total.add(
                    1,
                    {
                        "category": policy.category,
                        "action": result["action"],
                    },
                )
                root_span.set_attribute(
                    "result",
                    "ESCALATED",
                )
                root_span.set_attribute(
                    "remediation.success",
                    False,
                )
            # =========================================
            # 17. LOG RESULT
            # =========================================
            print("-" * 60)
            print("REMEDIATION RESULT")
            print("-" * 60)
            print(
                f"Action  : "
                f"{result['action']}"
            )
            print(
                f"Success : "
                f"{result['success']}"
            )
            print(
                f"Message : "
                f"{result['message']}"
            )
            if result.get("queue_url"):
                print(
                    f"Queue   : "
                    f"{result['queue_url']}"
                )
            if result.get(
                "new_build_number"
            ):
                print(
                    f"New Build : "
                    f"#{result['new_build_number']}"
                )
            if result.get(
                "verification_result"
            ):
                print(
                    f"Verified : "
                    f"{result['verification_result']}"
                )
            # =========================================
            # 18. AUTOHEAL RESULT SUMMARY
            # =========================================
            self._print_result_summary(
                incident=incident,
                classification=classification,
                policy=policy,
                result=incident.remediation,
                database_incident_id=database_incident_id,
            )
            # =========================================
            # 19. RESET CIRCUIT AFTER SUCCESS
            # =========================================
            if result["success"]:
                self.circuit_breaker.reset(
                    job_name,
                    policy.category,
                )
                print(
                    "Result : HEALED"
                )
            else:
                print(
                    "Result : ESCALATE"
                )
            print("=" * 60)
            self._record_processing_duration(
                start_time,
                job_name,
            )
            return incident
