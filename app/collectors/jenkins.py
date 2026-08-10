import httpx

from app.config import settings
from app.models import JenkinsBuildInfo


class JenkinsCollector:
    def __init__(self):
        self.base_url = settings.jenkins_url.rstrip("/")
        self.auth = (
            settings.jenkins_username,
            settings.jenkins_api_token,
        )

    async def get_build_info(
        self,
        job_name: str,
        build_number: int,
    ) -> JenkinsBuildInfo:

        url = (
            f"{self.base_url}/job/"
            f"{job_name}/{build_number}/api/json"
        )

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                auth=self.auth,
                timeout=30,
            )

            response.raise_for_status()
            data = response.json()

        console_log = await self.get_console_log(
            job_name,
            build_number,
        )

        return JenkinsBuildInfo(
            job_name=job_name,
            build_number=build_number,
            result=data.get("result"),
            building=data.get("building", False),
            url=data.get("url"),
            duration=data.get("duration"),
            timestamp=data.get("timestamp"),
            console_log=console_log,
        )

    async def get_console_log(
        self,
        job_name: str,
        build_number: int,
    ) -> str:

        url = (
            f"{self.base_url}/job/"
            f"{job_name}/{build_number}/consoleText"
        )

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                auth=self.auth,
                timeout=30,
            )

            response.raise_for_status()

            return response.text