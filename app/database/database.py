
import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    if "incidents" not in inspector.get_table_names():
        return

    # create_all creates new tables but does not alter existing installations.
    # This small compatibility migration preserves existing incident history.
    columns = {column["name"] for column in inspector.get_columns("incidents")}
    if "final_status" not in columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE incidents ADD COLUMN final_status "
                    "VARCHAR(20) NOT NULL DEFAULT 'PROCESSING'"
                )
            )

    # The pre-check in the service is not race-safe. A database unique index
    # is the final authority. Do not delete duplicate historical rows silently.
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_incident_job_build "
                    "ON incidents (job_name, build_number)"
                )
            )
    except Exception:
        logger.exception(
            "Could not create the unique incident key. Inspect and manually "
            "reconcile duplicate (job_name, build_number) rows."
        )


    # Backfill terminal state for older rows when a result audit event exists.
    # This is idempotent and leaves genuinely in-progress incidents untouched.
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE incidents SET final_status = 'HEALED' "
                    "WHERE EXISTS (SELECT 1 FROM audit_events a "
                    "WHERE a.incident_id = incidents.id "
                    "AND a.event_type = 'AUTOHEAL_RESULT' "
                    "AND a.message LIKE '%final_result=HEALED%')"
                )
            )
            connection.execute(
                text(
                    "UPDATE incidents SET final_status = 'ESCALATED' "
                    "WHERE EXISTS (SELECT 1 FROM audit_events a "
                    "WHERE a.incident_id = incidents.id "
                    "AND a.event_type = 'AUTOHEAL_RESULT' "
                    "AND a.message LIKE '%final_result=ESCALATED%')"
                )
            )
    except Exception:
        logger.exception("Could not backfill historical incident final_status values")