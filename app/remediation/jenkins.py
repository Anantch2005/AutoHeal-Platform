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

    async def trigger_build(
        self,
        job_name: str,
        parameters: dict | None = None,
    ) -> dict:
        """
        Trigger a Jenkins build.

        If parameters are provided, use
        /buildWithParameters so AutoHeal can pass
        AUTOHEAL_RETRY=true.
        """

        if parameters:
            url = (
                f"{self.base_url}/job/"
                f"{job_name}/buildWithParameters"
            )
        else:
            url = (
                f"{self.base_url}/job/"
                f"{job_name}/build"
            )

        async with httpx.AsyncClient() as client:

            response = await client.post(
                url,
                auth=self.auth,
                data=parameters,
                timeout=30,
            )

            response.raise_for_status()

            queue_url = response.headers.get(
                "Location"
            )

            if not queue_url:
                raise RuntimeError(
                    "Jenkins did not return a queue URL."
                )

        # Wait until Jenkins assigns the real
        # build number.
        build_number = await self.wait_for_queue(
            queue_url
        )

        return {
            "success": True,
            "message": "Jenkins build triggered.",
            "build_number": build_number,
            "queue_url": queue_url,
        }

    async def wait_for_queue(
        self,
        queue_url: str,
        timeout: int = 120,
    ) -> int:

        api_url = (
            queue_url.rstrip("/")
            + "/api/json"
        )

        elapsed = 0

        async with httpx.AsyncClient() as client:

            while elapsed < timeout:

                response = await client.get(
                    api_url,
                    auth=self.auth,
                    timeout=20,
                )

                response.raise_for_status()

                data = response.json()

                if data.get("cancelled"):
                    raise RuntimeError(
                        "Jenkins queue item was cancelled."
                    )

                executable = data.get(
                    "executable"
                )

                if executable:
                    return executable["number"]

                await asyncio.sleep(2)
                elapsed += 2

        raise TimeoutError(
            "Timed out waiting for Jenkins "
            "queue item."
        )

    async def get_build_result(
        self,
        job_name: str,
        build_number: int,
        timeout: int = 600,
    ) -> str:
        """
        Wait for the Jenkins build to finish and
        return its final result.
        """

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
                    timeout=20,
                )

                response.raise_for_status()

                data = response.json()

                if not data.get(
                    "building",
                    False,
                ):
                    return data.get(
                        "result",
                        "UNKNOWN",
                    )

                await asyncio.sleep(5)
                elapsed += 5

        raise TimeoutError(
            f"Build #{build_number} did not "
            "finish within the timeout."
        )