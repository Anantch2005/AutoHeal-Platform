import asyncio

import httpx

from app.config import settings


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

        metadata_url = (
            f"{self.base_url}/job/"
            f"{job_name}/{build_number}/api/json"
        )

        console_url = (
            f"{self.base_url}/job/"
            f"{job_name}/{build_number}/consoleText"
        )

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
                f"{self.base_url}/job/"
                f"{job_name}/{build_number}/",
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

        print()
        print("=" * 72)
        print("JENKINS EVIDENCE COLLECTION")
        print("=" * 72)
        print(
            f"Job             : {job_name}"
        )
        print(
            f"Build           : #{build_number}"
        )
        print(
            f"Build Result    : {result}"
        )
        print(
            f"Console URL     : {console_url}"
        )
        print(
            f"Console Length  : {len(console_log)} characters"
        )
        print("=" * 72)

        # =========================================================
        # 4. SHOW THE END OF THE LOG
        # =========================================================
        #
        # The complete log is still returned.
        #
        # We only limit what is printed to the AutoHeal container
        # stdout so extremely large Jenkins logs do not flood
        # Docker logs.
        #
        # Ollama receives the complete console_log.
        # =========================================================

        preview_limit = 12000

        if len(console_log) > preview_limit:
            preview = console_log[-preview_limit:]

            print(
                "Console Preview  : "
                "showing final "
                f"{preview_limit} characters"
            )
            print("-" * 72)
            print(preview)
            print("-" * 72)
            print(
                "The complete console log remains available "
                "to the AutoHeal processing pipeline."
            )
        else:
            print("Console Preview:")
            print("-" * 72)
            print(console_log)
            print("-" * 72)

        print("=" * 72)
        print()

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

        url = (
            f"{self.base_url}/job/"
            f"{job_name}/{build_number}/consoleText"
        )

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

        url = (
            f"{self.base_url}/job/"
            f"{job_name}/{build_number}/api/json"
        )

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

        url = (
            f"{self.base_url}/job/"
            f"{job_name}/build"
        )

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