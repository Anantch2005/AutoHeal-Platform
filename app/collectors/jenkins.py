
import asyncio
import logging
from urllib.parse import quote

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class JenkinsBuild:
    """
    Normalized Jenkins build information used by AutoHeal.
    """

    def __init__(
        self,
        number: int,
        result: str,
        url: str,
        console_log: str,
    ):
        self.number = number
        self.result = result
        self.url = url
        self.console_log = console_log


class JenkinsCollector:
    """
    Collect build metadata and the complete Jenkins console log.

    The consoleText endpoint is intentionally fetched separately from
    the Jenkins build metadata API so AutoHeal receives the actual
    pipeline output, including pytest failures, Docker errors,
    dependency errors, shell errors, network errors, etc.
    """

    def __init__(self):
        self.base_url = settings.jenkins_url.rstrip("/")

        self.auth = (
            settings.jenkins_username,
            settings.jenkins_api_token,
        )

        self.timeout = 30

    def _job_base_url(self, job_name: str) -> str:
        parts = [
            part.strip()
            for part in job_name.strip("/").split("/")
            if part.strip()
        ]
        if not parts:
            raise ValueError("Jenkins job name cannot be empty.")
        encoded_path = "/".join(
            f"job/{quote(part, safe='')}" for part in parts
        )
        return f"{self.base_url}/{encoded_path}"

    async def get_build_info(
        self,
        job_name: str,
        build_number: int,
    ) -> JenkinsBuild:
        """
        Fetch Jenkins build metadata and the complete console log.

        Metadata:
            /job/<job>/<build>/api/json

        Console:
            /job/<job>/<build>/consoleText
        """

        job_base_url = self._job_base_url(job_name)
        metadata_url = f"{job_base_url}/{build_number}/api/json"
        console_url = f"{job_base_url}/{build_number}/consoleText"

        async with httpx.AsyncClient(
            auth=self.auth,
            timeout=self.timeout,
            follow_redirects=True,
        ) as client:

            # =====================================================
            # 1. BUILD METADATA
            # =====================================================

            metadata_response = await client.get(
                metadata_url,
            )

            metadata_response.raise_for_status()

            data = metadata_response.json()

            result = data.get(
                "result",
                "UNKNOWN",
            )

            url = data.get(
                "url",
                f"{job_base_url}/{build_number}/",
            )

            # =====================================================
            # 2. COMPLETE JENKINS CONSOLE LOG
            # =====================================================

            console_response = await client.get(
                console_url,
            )

            console_response.raise_for_status()

            console_log = console_response.text or ""

        # =========================================================
        # 3. BASIC LOG VALIDATION
        # =========================================================

        if not console_log.strip():
            console_log = (
                "Jenkins console log was empty. "
                "No console output was returned by Jenkins."
            )

        # Log only metadata. Raw Jenkins output can contain secrets and is
        # persisted for controlled diagnosis; it must not be dumped to stdout.
        logger.info(
            "Collected Jenkins evidence: job=%s build=%s result=%s "
            "console_chars=%d",
            job_name,
            build_number,
            result,
            len(console_log),
        )

        return JenkinsBuild(
            number=build_number,
            result=result,
            url=url,
            console_log=console_log,
        )

    async def get_console_log(
        self,
        job_name: str,
        build_number: int,
    ) -> str:
        """
        Explicitly fetch the complete Jenkins console log.

        This method is useful when another AutoHeal component needs
        the raw Jenkins console without fetching build metadata.
        """

        url = f"{self._job_base_url(job_name)}/{build_number}/consoleText"

        async with httpx.AsyncClient(
            auth=self.auth,
            timeout=self.timeout,
            follow_redirects=True,
        ) as client:

            response = await client.get(url)

            response.raise_for_status()

            log = response.text or ""

        if not log.strip():
            return (
                "Jenkins console log was empty. "
                "No console output was returned by Jenkins."
            )

        return log

    async def get_build_result(
        self,
        job_name: str,
        build_number: int,
        timeout: int = 300,
    ) -> str:
        """
        Wait for a Jenkins build to finish and return its final result.
        """

        url = f"{self._job_base_url(job_name)}/{build_number}/api/json"

        elapsed = 0

        async with httpx.AsyncClient(
            auth=self.auth,
            timeout=15,
            follow_redirects=True,
        ) as client:

            while elapsed < timeout:

                response = await client.get(url)

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
            f"Build #{build_number} did not finish "
            "in time."
        )

    async def wait_for_result(
        self,
        job_name: str,
        build_number: int,
        timeout: int = 300,
    ) -> str:
        """
        Compatibility wrapper used by remediation code.
        """

        return await self.get_build_result(
            job_name,
            build_number,
            timeout,
        )

    async def trigger_build(
        self,
        job_name: str,
    ) -> int:
        """
        Trigger a Jenkins build and wait until Jenkins
        assigns a build number.
        """

        url = f"{self._job_base_url(job_name)}/build"

        async with httpx.AsyncClient(
            auth=self.auth,
            timeout=30,
            follow_redirects=True,
        ) as client:

            response = await client.post(url)

            response.raise_for_status()

            queue_url = response.headers.get(
                "Location"
            )

            if not queue_url:
                raise RuntimeError(
                    "Jenkins did not return a queue URL."
                )

            elapsed = 0

            while elapsed < 60:

                queue_api_url = (
                    queue_url.rstrip("/")
                    + "/api/json"
                )

                queue_response = await client.get(
                    queue_api_url,
                )

                queue_response.raise_for_status()

                data = queue_response.json()

                executable = data.get(
                    "executable"
                )

                if executable:
                    return int(
                        executable["number"]
                    )

                if data.get("cancelled"):
                    raise RuntimeError(
                        "Jenkins queue item was cancelled."
                    )

                await asyncio.sleep(2)

                elapsed += 2

        raise TimeoutError(
            "Timed out waiting for Jenkins "
            "to assign a build number."
        )

