import asyncio
import httpx

from app.config import settings


class JenkinsQueue:

    def __init__(self):
        self.base_url = settings.jenkins_url.rstrip("/")
        self.auth = (
            settings.jenkins_username,
            settings.jenkins_api_token,
        )

    async def wait_for_executable(
        self,
        queue_url: str,
        timeout_seconds: int = 120,
    ) -> int | None:

        if not queue_url:
            return None

        if not queue_url.endswith("/"):
            queue_url += "/"

        api_url = queue_url + "api/json"

        elapsed = 0

        async with httpx.AsyncClient() as client:

            while elapsed < timeout_seconds:

                response = await client.get(
                    api_url,
                    auth=self.auth,
                    timeout=30,
                )

                response.raise_for_status()

                data = response.json()

                executable = data.get(
                    "executable"
                )

                if executable:
                    return executable.get(
                        "number"
                    )

                if data.get("cancelled"):
                    return None

                await asyncio.sleep(2)
                elapsed += 2

        return None