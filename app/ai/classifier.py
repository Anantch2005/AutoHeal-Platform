"""
Local Ollama diagnostic classifier.

AutoHeal uses this component only for diagnosis.

The AI does NOT control:
- policy
- remediation
- retries
- source-code changes
- dependency changes

The deterministic classifier and policy engine remain authoritative.
"""

import json
import os
from typing import Any

import httpx

from app.ai.models import AIClassification
from app.ai.prompt import (
    SYSTEM_PROMPT,
    build_user_prompt,
)


class AIClassifier:
    """
    Local Ollama-powered Jenkins failure diagnostic assistant.
    """

    def __init__(self):
        self.enabled = (
            os.getenv(
                "AI_ENABLED",
                "false",
            ).strip().lower()
            in {
                "1",
                "true",
                "yes",
                "on",
            }
        )

        self.ollama_url = os.getenv(
            "OLLAMA_URL",
            "http://ollama:11434",
        ).rstrip("/")

        self.model = os.getenv(
            "OLLAMA_MODEL",
            "llama3.2:3b",
        )

        self.max_log_chars = int(
            os.getenv(
                "AI_MAX_LOG_CHARS",
                "40000",
            )
        )

        self.timeout_seconds = float(
            os.getenv(
                "AI_TIMEOUT_SECONDS",
                "180",
            )
        )

    # =============================================================
    # PUBLIC API
    # =============================================================

    async def classify(
        self,
        log: str,
        rules_category: str | None = None,
    ) -> AIClassification:
        """
        Analyze a Jenkins console log with Ollama.
        """

        if not self.enabled:
            raise RuntimeError(
                "AI analysis is disabled."
            )

        original_log = log or ""

        if not original_log.strip():
            raise RuntimeError(
                "Jenkins console log is empty."
            )

        prepared_log = self._prepare_log(
            original_log
        )

        user_prompt = build_user_prompt(
            log=prepared_log,
            rules_category=rules_category,
        )

        print()
        print("=" * 72)
        print("OLLAMA AI DIAGNOSTIC REQUEST")
        print("=" * 72)

        print(
            f"Model              : {self.model}"
        )

        print(
            f"Ollama URL         : {self.ollama_url}"
        )

        print(
            f"Original log chars : "
            f"{len(original_log)}"
        )

        print(
            f"AI log chars       : "
            f"{len(prepared_log)}"
        )

        print(
            f"Rules category     : "
            f"{rules_category or 'UNKNOWN'}"
        )

        print(
            "Failure evidence   : "
            f"{self._count_failure_lines(prepared_log)} "
            "candidate lines"
        )

        print("-" * 72)
        print("LOG SENT TO OLLAMA")
        print("-" * 72)

        # Print the exact text being supplied to the model.
        #
        # This is deliberately visible while we debug the integration.
        # It lets us verify that the actual pytest/Docker/dependency
        # failure is reaching Ollama.
        print(prepared_log)

        print("-" * 72)
        print()

        payload = {
            "model": self.model,
            "system": SYSTEM_PROMPT,
            "prompt": user_prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
                "num_ctx": 16384,
            },
        }

        endpoint = (
            f"{self.ollama_url}/api/generate"
        )

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(
                    self.timeout_seconds,
                    connect=10.0,
                )
            ) as client:

                response = await client.post(
                    endpoint,
                    json=payload,
                )

                response.raise_for_status()

                data = response.json()

        except httpx.HTTPError as exc:
            raise RuntimeError(
                f"Ollama request failed: {exc}"
            ) from exc

        except Exception as exc:
            raise RuntimeError(
                f"Ollama communication error: {exc}"
            ) from exc

        raw_response = data.get(
            "response",
            "",
        )

        if not isinstance(
            raw_response,
            str,
        ):
            raw_response = str(
                raw_response
            )

        raw_response = raw_response.strip()

        print()
        print("=" * 72)
        print("OLLAMA RAW RESPONSE")
        print("=" * 72)
        print(raw_response)
        print("=" * 72)
        print()

        if not raw_response:
            raise RuntimeError(
                "Ollama returned an empty response."
            )

        result = self._parse_response(
            raw_response
        )

        return result

    # =============================================================
    # LOG PREPARATION
    # =============================================================

    def _prepare_log(
        self,
        log: str,
    ) -> str:
        """
        Prepare the Jenkins console for the model.

        Strategy:

        1. If the complete log fits within the configured limit,
           send everything.

        2. If it is larger:
           - keep the beginning
           - keep failure-focused lines
           - keep context around failure lines
           - keep the end of the log

        This prevents the important pytest/Docker/etc. failure from
        being lost merely because Jenkins produced a long console.
        """

        log = log or ""

        if len(log) <= self.max_log_chars:
            return log

        lines = log.splitlines()

        selected: list[str] = []

        # ---------------------------------------------------------
        # Beginning
        # ---------------------------------------------------------

        beginning_chars = 5000

        beginning = log[
            :beginning_chars
        ]

        selected.append(
            "===== BEGINNING OF JENKINS CONSOLE ====="
        )

        selected.append(
            beginning
        )

        # ---------------------------------------------------------
        # Failure-focused regions
        # ---------------------------------------------------------

        failure_indexes = []

        for index, line in enumerate(lines):

            if self._is_failure_line(line):
                failure_indexes.append(
                    index
                )

        selected.append(
            "===== FAILURE-FOCUSED JENKINS EVIDENCE ====="
        )

        # Keep context around each failure marker.
        #
        # Limit the number of regions so a noisy Jenkins log does not
        # consume the entire model context.
        used_ranges: list[tuple[int, int]] = []

        for index in failure_indexes[-80:]:

            start = max(
                0,
                index - 4,
            )

            end = min(
                len(lines),
                index + 5,
            )

            current_range = (
                start,
                end,
            )

            overlaps = False

            for existing_start, existing_end in used_ranges:
                if (
                    start <= existing_end
                    and end >= existing_start
                ):
                    overlaps = True
                    break

            if overlaps:
                continue

            used_ranges.append(
                current_range
            )

            selected.extend(
                lines[start:end]
            )

        # ---------------------------------------------------------
        # End
        # ---------------------------------------------------------

        selected.append(
            "===== END OF JENKINS CONSOLE ====="
        )

        selected.append(
            log[-10000:]
        )

        prepared = "\n".join(
            selected
        )

        # Final hard limit.

        if len(prepared) > self.max_log_chars:

            # Preserve the end because Jenkins normally prints the
            # final failure summary there.
            prepared = (
                prepared[
                    :self.max_log_chars - 10000
                ]
                + "\n\n"
                + "===== FINAL JENKINS LOG SECTION =====\n"
                + log[-10000:]
            )

        return prepared

    # =============================================================
    # FAILURE DETECTION
    # =============================================================

    def _is_failure_line(
        self,
        line: str,
    ) -> bool:
        """
        Identify lines likely to contain useful failure evidence.
        """

        text = line.strip()

        if not text:
            return False

        tokens = (
            "ERROR",
            "Error",
            "error",
            "FAILED",
            "Failed",
            "failed",
            "FAIL",
            "Traceback",
            "AssertionError",
            "Exception",
            "ModuleNotFoundError",
            "ImportError",
            "PermissionError",
            "FileNotFoundError",
            "TimeoutError",
            "timeout",
            "timed out",
            "connection refused",
            "Connection refused",
            "connection reset",
            "Connection reset",
            "DNS",
            "Could not find",
            "No matching distribution",
            "ResolutionImpossible",
            "failed to solve",
            "command not found",
            "exit code",
            "unauthorized",
            "Unauthorized",
            "authentication required",
            "denied",
            "manifest unknown",
            "No such file",
            "permission denied",
            "agent is offline",
            "workspace",
        )

        return any(
            token in text
            for token in tokens
        )

    def _count_failure_lines(
        self,
        log: str,
    ) -> int:
        """
        Count likely diagnostic lines for observability/debugging.
        """

        return sum(
            1
            for line in log.splitlines()
            if self._is_failure_line(line)
        )

    # =============================================================
    # RESPONSE PARSING
    # =============================================================

    def _parse_response(
        self,
        raw_response: str,
    ) -> AIClassification:
        """
        Parse Ollama's JSON response safely.
        """

        try:
            data = json.loads(
                raw_response
            )

        except json.JSONDecodeError as exc:

            # Some local models occasionally wrap JSON in markdown.
            # Try to recover the first JSON object.
            recovered = self._extract_json_object(
                raw_response
            )

            if recovered is None:
                raise RuntimeError(
                    "Ollama returned invalid JSON: "
                    f"{exc}"
                ) from exc

            data = recovered

        if not isinstance(
            data,
            dict,
        ):
            raise RuntimeError(
                "Ollama JSON response was not an object."
            )

        category = self._clean_string(
            data.get(
                "category",
                "unknown",
            )
        )

        root_cause = self._clean_string(
            data.get(
                "root_cause",
                "",
            )
        )

        reasoning = self._clean_string(
            data.get(
                "reasoning",
                "",
            )
        )

        confidence = self._normalize_confidence(
            data.get(
                "confidence",
                0.0,
            )
        )

        matched_evidence = self._normalize_list(
            data.get(
                "matched_evidence",
                [],
            )
        )

        recommendations = self._normalize_list(
            data.get(
                "recommendations",
                [],
            )
        )

        if not category:
            category = "unknown"

        if not root_cause:
            root_cause = (
                "The AI did not provide a root cause."
            )

        if not reasoning:
            reasoning = (
                "The AI did not provide additional reasoning."
            )

        return AIClassification(
            category=category,
            root_cause=root_cause,
            reasoning=reasoning,
            confidence=confidence,
            matched_evidence=matched_evidence,
            recommendations=recommendations,
        )

    # =============================================================
    # JSON HELPERS
    # =============================================================

    def _extract_json_object(
        self,
        text: str,
    ) -> dict[str, Any] | None:
        """
        Recover a JSON object from a response that contains
        additional text or markdown fences.
        """

        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1:
            return None

        if end <= start:
            return None

        candidate = text[
            start:end + 1
        ]

        try:
            parsed = json.loads(
                candidate
            )

        except json.JSONDecodeError:
            return None

        if isinstance(
            parsed,
            dict,
        ):
            return parsed

        return None

    def _clean_string(
        self,
        value: Any,
    ) -> str:
        """
        Normalize model string output.
        """

        if value is None:
            return ""

        if isinstance(
            value,
            str,
        ):
            return value.strip()

        return str(
            value
        ).strip()

    def _normalize_list(
        self,
        value: Any,
    ) -> list[str]:
        """
        Normalize model list output.
        """

        if value is None:
            return []

        if isinstance(
            value,
            str,
        ):
            value = [
                value
            ]

        if not isinstance(
            value,
            list,
        ):
            return [
                str(value)
            ]

        result = []

        for item in value:

            if item is None:
                continue

            text = str(
                item
            ).strip()

            if text:
                result.append(
                    text
                )

        return result

    def _normalize_confidence(
        self,
        value: Any,
    ) -> float:
        """
        Normalize confidence into [0.0, 1.0].
        """

        try:
            confidence = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):
            return 0.0

        # Handle models returning percentages.
        if confidence > 1.0:
            confidence = confidence / 100.0

        return max(
            0.0,
            min(
                1.0,
                confidence,
            ),
        )