from sqlalchemy import select

from app.database.database import SessionLocal
from app.database.models import (
    IncidentRecord,
    RemediationAttemptRecord,
    AuditEventRecord,
)


class IncidentRepository:

    def exists(
        self,
        job_name: str,
        build_number: int,
    ) -> bool:

        with SessionLocal() as session:

            statement = select(IncidentRecord).where(
                IncidentRecord.job_name == job_name,
                IncidentRecord.build_number == build_number,
            )

            return session.scalar(statement) is not None

    def create_incident(
        self,
        incident_id: str,
        source: str,
        job_name: str,
        build_number: int,
        status: str,
        build_url: str | None,
        failure_category: str | None,
        failure_action: str | None,
        reason: str | None,
        matched_pattern: str | None,
        confidence: float | None,
        console_log: str | None,

        # =========================================
        # PHASE 5 - AI
        # =========================================

        classifier_source: str | None = None,
        ai_root_cause: str | None = None,
        ai_reasoning: str | None = None,
        ai_confidence: float | None = None,
    ) -> int:

        with SessionLocal() as session:

            record = IncidentRecord(
                incident_id=incident_id,
                source=source,
                job_name=job_name,
                build_number=build_number,
                status=status,
                build_url=build_url,
                failure_category=failure_category,
                failure_action=failure_action,
                reason=reason,
                matched_pattern=matched_pattern,
                confidence=confidence,
                console_log=console_log,

                # Phase 5
                classifier_source=classifier_source,
                ai_root_cause=ai_root_cause,
                ai_reasoning=ai_reasoning,
                ai_confidence=ai_confidence,
            )

            session.add(record)
            session.commit()
            session.refresh(record)

            return record.id

    def create_attempt(
        self,
        incident_id: int,
        attempt_number: int,
        action: str,
        success: bool,
        message: str,
        original_build_number: int,
        retry_build_number: int | None,
        queue_url: str | None,
        verification_result: str | None,
    ) -> None:

        with SessionLocal() as session:

            record = RemediationAttemptRecord(
                incident_id=incident_id,
                attempt_number=attempt_number,
                action=action,
                success=success,
                message=message,
                original_build_number=original_build_number,
                retry_build_number=retry_build_number,
                queue_url=queue_url,
                verification_result=verification_result,
            )

            session.add(record)
            session.commit()

    def add_audit_event(
        self,
        incident_id: int,
        event_type: str,
        message: str,
    ) -> None:

        with SessionLocal() as session:

            record = AuditEventRecord(
                incident_id=incident_id,
                event_type=event_type,
                message=message,
            )

            session.add(record)
            session.commit()

    def count_attempts(
        self,
        incident_id: int,
    ) -> int:

        with SessionLocal() as session:

            statement = select(
                RemediationAttemptRecord
            ).where(
                RemediationAttemptRecord.incident_id
                == incident_id
            )

            return len(
                session.scalars(statement).all()
            )