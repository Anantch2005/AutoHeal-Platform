import asyncio

import httpx

from app.config import settings


class JenkinsRemediator:
    def __init__(self):
        self.base_url = settings.jenkins_url.rstrip("/")
        self.auth = (
            settings.jenkins_username,
            settings.jenkins_api_token,
        )

    async def trigger_build(self, job_name: str) -> int:
        """
        Trigger a new Jenkins build and return the new build number.
        """

        url = f"{self.base_url}/job/{job_name}/build"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                auth=self.auth,
                timeout=30,
            )

            response.raise_for_status()

            queue_url = response.headers.get("Location")

            if not queue_url:
                raise RuntimeError(
                    "Jenkins did not return a queue location."
                )

        return await self._wait_for_build(queue_url)

    async def _wait_for_build(
        self,
        queue_url: str,
        timeout: int = 120,
    ) -> int:

        queue_api = f"{queue_url.rstrip('/')}/api/json"

        elapsed = 0

        async with httpx.AsyncClient() as client:

            while elapsed < timeout:

                response = await client.get(
                    queue_api,
                    auth=self.auth,
                    timeout=15,
                )

                response.raise_for_status()

                data = response.json()

                if data.get("cancelled"):
                    raise RuntimeError(
                        "Jenkins build queue item was cancelled."
                    )

                executable = data.get("executable")

                if executable:
                    return executable["number"]

                await asyncio.sleep(2)
                elapsed += 2

        raise TimeoutError(
            "Timed out waiting for Jenkins build to start."
        )

    async def get_build_result(
        self,
        job_name: str,
        build_number: int,
        timeout: int = 300,
    ) -> str:

        url = (
            f"{self.base_url}/job/"
            f"{job_name}/{build_number}/api/json"
        )

        elapsed = 0

        async with httpx.AsyncClient() as client:

            while elapsed < timeout:

                response = await client.get(
                    url,
                    auth=self.auth,
                    timeout=15,
                )

                response.raise_for_status()

                data = response.json()

                if not data.get("building", False):
                    return data.get("result", "UNKNOWN")

                await asyncio.sleep(5)
                elapsed += 5

        raise TimeoutError(
            f"Build #{build_number} did not finish in time."
        )