import uuid

from app.collectors.jenkins import JenkinsCollector
from app.models import Incident


class IncidentService:
    def __init__(self):
        self.jenkins = JenkinsCollector()

    async def process_failure(
        self,
        job_name: str,
        build_number: int,
    ) -> Incident:

        build = await self.jenkins.get_build_info(
            job_name,
            build_number,
        )

        incident = Incident(
            incident_id=f"AH-{uuid.uuid4().hex[:8].upper()}",
            source="jenkins",
            job_name=job_name,
            build_number=build_number,
            status=build.result or "UNKNOWN",
            build_url=build.url,
            console_log=build.console_log,
        )

        print("\n" + "=" * 60)
        print("AUTOHEAL INCIDENT")
        print("=" * 60)
        print(f"Incident ID : {incident.incident_id}")
        print(f"Job         : {incident.job_name}")
        print(f"Build       : #{incident.build_number}")
        print(f"Status      : {incident.status}")
        print(f"Build URL   : {incident.build_url}")
        print("=" * 60)

        return incident