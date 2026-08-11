import uuid

from app.collectors.jenkins import JenkinsCollector
from app.classifier.classifier import FailureClassifier
from app.models import Incident, FailureClassification


class IncidentService:

    def __init__(self):
        self.jenkins = JenkinsCollector()
        self.classifier = FailureClassifier()

    async def process_failure(
        self,
        job_name: str,
        build_number: int,
    ) -> Incident:

        # 1. Collect evidence from Jenkins
        build = await self.jenkins.get_build_info(
            job_name,
            build_number,
        )

        # 2. Classify the failure
        classification_data = self.classifier.classify(
            build.console_log or ""
        )

        classification = FailureClassification(
            **classification_data
        )

        # 3. Create incident
        incident = Incident(
            incident_id=f"AH-{uuid.uuid4().hex[:8].upper()}",
            source="jenkins",
            job_name=job_name,
            build_number=build_number,
            status=build.result or "UNKNOWN",
            build_url=build.url,
            console_log=build.console_log,
            classification=classification,
        )

        # 4. Print incident
        print("\n" + "=" * 60)
        print("AUTOHEAL INCIDENT")
        print("=" * 60)

        print(f"Incident ID : {incident.incident_id}")
        print(f"Job         : {incident.job_name}")
        print(f"Build       : #{incident.build_number}")
        print(f"Status      : {incident.status}")
        print(f"Build URL   : {incident.build_url}")

        print("-" * 60)
        print("CLASSIFICATION")
        print("-" * 60)

        print(f"Category    : {classification.category}")
        print(f"Action      : {classification.action}")
        print(f"Confidence  : {classification.confidence}")
        print(f"Reason      : {classification.reason}")

        if classification.matched_pattern:
            print(f"Pattern     : {classification.matched_pattern}")

        print("=" * 60)

        return incident