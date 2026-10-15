
"""Incident result reporting and terminal-status persistence."""

import logging

from app.models import Incident, FailureClassification, RemediationResult

logger = logging.getLogger(__name__)


class IncidentResultReporter:
    def __init__(self, repository):
        self.repository = repository

    @staticmethod
    def _log_lines(*parts) -> None:
        logger.info("%s", " ".join(str(part) for part in parts))

    def format_ai_reasoning(
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

    def record_result_summary(
        self,
        incident: Incident,
        classification: FailureClassification,
        policy,
        result: RemediationResult,
        database_incident_id: int,
    ) -> None:
        """
        Log and persist a complete AutoHeal result summary.
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

        self._log_lines()
        self._log_lines("=" * 72)
        self._log_lines("AUTOHEAL RESULT SUMMARY")
        self._log_lines("=" * 72)

        self._log_lines(
            f"Incident ID       : "
            f"{incident.incident_id}"
        )

        self._log_lines(
            f"Job               : "
            f"{incident.job_name}"
        )

        self._log_lines(
            f"Failed Build      : "
            f"#{incident.build_number}"
        )

        self._log_lines(
            f"Failure Category  : "
            f"{classification.category}"
        )

        self._log_lines(
            f"Classifier Source : "
            f"{classification.source}"
        )

        self._log_lines(
            f"Classifier Conf.  : "
            f"{classification.confidence:.2f}"
        )

        self._log_lines(
            f"Policy Allowed    : "
            f"{policy.allowed}"
        )

        self._log_lines(
            f"Policy Risk       : "
            f"{policy.risk_level}"
        )

        self._log_lines(
            f"Policy Action     : "
            f"{policy.action}"
        )

        self._log_lines(
            f"Remediation       : "
            f"{result.action}"
        )

        self._log_lines(
            f"Retry Build       : "
            f"{retry_build}"
        )

        self._log_lines(
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
            self._log_lines("-" * 72)
            self._log_lines("AI DIAGNOSTIC OUTPUT")
            self._log_lines("-" * 72)

            self._log_lines(
                f"AI Category       : "
                f"{'diagnostic-only (not an internal AutoHeal category)'}"
            )

            self._log_lines(
                f"AI Root Cause     : "
                f"{classification.ai_root_cause or 'None'}"
            )

            self._log_lines(
                f"AI Confidence     : "
                f"{classification.ai_confidence}"
            )

            self._log_lines(
                f"AI Reasoning      : "
                f"{classification.ai_reasoning or 'None'}"
            )

            if classification.ai_evidence:
                self._log_lines(
                    "AI Evidence       : "
                    + "; ".join(
                        classification.ai_evidence
                    )
                )

        self._log_lines("-" * 72)

        self._log_lines(
            f"Final Result      : "
            f"{final_result}"
        )

        self._log_lines("=" * 72)

        # =========================================
        # PERSIST FINAL RESULT
        # =========================================

        self.repository.update_final_status(
            incident_id=database_incident_id,
            final_status=final_result,
        )

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

