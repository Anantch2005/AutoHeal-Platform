
from sqlalchemy import select

from app.database.database import SessionLocal, create_tables
from app.database.models import IncidentRecord
from app.database.repository import IncidentRepository


def test_incident_deduplication_and_final_status_persistence():
    create_tables()
    repository = IncidentRepository()
    job_name = "repository-test/job"
    build_number = 987654

    first_id = repository.create_incident(
        incident_id="AH-REPO-ONE",
        source="jenkins",
        job_name=job_name,
        build_number=build_number,
        status="FAILURE",
        build_url="http://jenkins/job/repository-test/job/987654/",
        failure_category="CODE_FAILURE",
        failure_action="DO_NOT_HEAL",
        reason="test fixture",
        matched_pattern="AssertionError",
        confidence=0.93,
        console_log="AssertionError",
    )
    assert first_id is not None

    duplicate_id = repository.create_incident(
        incident_id="AH-REPO-TWO",
        source="jenkins",
        job_name=job_name,
        build_number=build_number,
        status="FAILURE",
        build_url=None,
        failure_category="CODE_FAILURE",
        failure_action="DO_NOT_HEAL",
        reason="duplicate fixture",
        matched_pattern="AssertionError",
        confidence=0.93,
        console_log="AssertionError",
    )
    assert duplicate_id is None

    repository.update_final_status(first_id, "ESCALATED")
    with SessionLocal() as session:
        record = session.scalar(
            select(IncidentRecord).where(IncidentRecord.id == first_id)
        )
        assert record is not None
        assert record.status == "FAILURE"
        assert record.final_status == "ESCALATED"

