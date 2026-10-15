
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class IncidentRecord(Base):

    __tablename__ = "incidents"
    __table_args__ = (
        UniqueConstraint("job_name", "build_number", name="uq_incident_job_build"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    incident_id: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        index=True,
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    job_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    build_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # Original Jenkins result (normally FAILURE) is preserved separately
    # from AutoHeal's terminal lifecycle outcome.
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    final_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PROCESSING",
    )

    build_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    failure_category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    failure_action: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    matched_pattern: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    confidence: Mapped[float | None] = mapped_column(
        nullable=True,
    )

    console_log: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # =========================================
    # PHASE 5 - AI CLASSIFICATION
    # =========================================

    classifier_source: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    ai_root_cause: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    ai_reasoning: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    ai_confidence: Mapped[float | None] = mapped_column(
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )

    remediation_attempts = relationship(
        "RemediationAttemptRecord",
        back_populates="incident",
        cascade="all, delete-orphan",
    )

    audit_events = relationship(
        "AuditEventRecord",
        back_populates="incident",
        cascade="all, delete-orphan",
    )


class RemediationAttemptRecord(Base):

    __tablename__ = "remediation_attempts"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id"),
        nullable=False,
        index=True,
    )

    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    success: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    original_build_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    retry_build_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    queue_url: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    verification_result: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    incident = relationship(
        "IncidentRecord",
        back_populates="remediation_attempts",
    )


class AuditEventRecord(Base):

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id"),
        nullable=False,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )

    incident = relationship(
        "IncidentRecord",
        back_populates="audit_events",
    )

