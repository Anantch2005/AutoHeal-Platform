"""
Local Ollama diagnostic classifier.

AutoHeal uses this component only for diagnosis.

IMPORTANT ARCHITECTURE:

AutoHeal still collects the complete Jenkins console log.

The complete log is used by:
    - deterministic failure classification
    - incident persistence
    - audit/debugging
    - AutoHeal safety decisions

However, the complete Jenkins console is NOT sent to Ollama.

Before calling Ollama this module:

    1. identifies the relevant failure evidence
    2. identifies the Jenkins Pipeline stage when possible
    3. extracts a small context window around the failure
    4. limits the amount of data sent to the model
    5. redacts common secrets

This keeps the AI focused on the actual failure and reduces noise
and hallucination risk on large production Jenkins pipelines.

The AI does NOT control:
    - policy
    - remediation
    - retries
    - source-code changes
    - dependency changes

The deterministic classifier and Policy Engine remain authoritative.
"""

import json
import os
import re
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

    The full Jenkins console is accepted by this class, but only a
    targeted failure-stage excerpt is sent to Ollama.
    """

    # =============================================================
    # FAILURE SIGNALS
    # =============================================================

    FAILURE_SIGNALS = (
        "AssertionError",
        "FAILED",
        "ERROR",
        "Traceback",
        "ModuleNotFoundError",
        "ImportError",
        "PermissionError",
        "FileNotFoundError",
        "TimeoutError",
        "Connection refused",
        "connection refused",
        "Connection reset",
        "connection reset",
        "Connection timed out",
        "connection timed out",
        "ConnectTimeout",
        "Temporary failure in name resolution",
        "Could not resolve host",
        "network is unreachable",
        "Could not find a version that satisfies",
        "No matching distribution found",
        "ResolutionImpossible",
        "dependency conflict",
        "failed to resolve dependencies",
        "failed to solve:",
        "failed to build",
        "command not found",
        "unauthorized",
        "Unauthorized",
        "authentication required",
        "requested access to the resource is denied",
        "manifest unknown",
        "denied:",
        "No such file",
        "permission denied",
        "agent is offline",
        "workspace",
        "script returned exit code",
    )

    # =============================================================
    # CATEGORY-SPECIFIC SIGNALS
    # =============================================================

    CATEGORY_SIGNALS = {
        "CODE_FAILURE": (
            "AssertionError",
            "FAILED",
            "Traceback",
            "SyntaxError",
            "TypeError",
            "NameError",
            "ModuleNotFoundError",
            "ImportError",
            "test_",
        ),
        "DEPENDENCY_FAILURE": (
            "Could not find a version that satisfies",
            "No matching distribution found",
            "ResolutionImpossible",
            "dependency conflict",
            "package conflict",
            "version conflict",
            "failed to resolve dependencies",
            "pip install",
            "ERROR:",
        ),
        "DOCKER_FAILURE": (
            "failed to solve:",
            "failed to build",
            "Cannot connect to the Docker daemon",
            "Docker daemon",
            "BuildKit",
            "failed to create",
            "docker build",
        ),
        "REGISTRY_FAILURE": (
            "requested access to the resource is denied",
            "unauthorized",
            "Unauthorized",
            "authentication required",
            "manifest unknown",
            "denied:",
            "failed to push",
            "failed to pull",
            "registry",
        ),
        "NETWORK_FAILURE": (
            "Connection timed out",
            "ConnectTimeout",
            "connection timeout",
            "Temporary failure in name resolution",
            "network is unreachable",
            "Connection refused",
            "Failed to connect",
            "Could not resolve host",
            "Name or service not known",
            "HTTP/1.1 5",
            "HTTP/2 5",
        ),
        "WORKSPACE_FAILURE": (
            "unable to create file",
            "workspace",
            "permission denied",
            "cannot create",
            "Could not checkout",
            "Maximum checkout retry attempts reached",
            "fatal: cannot create directory",
            "workspace",
        ),
        "FLAKY_TEST": (
            "AUTOHEAL_FLAKY_TEST",
        ),
    }

    # =============================================================
    # JENKINS STAGE MARKER
    # =============================================================

    # Declarative Jenkins Pipeline normally emits lines similar to:
    #
    # [Pipeline] { (Test)
    # [Pipeline] { (Docker Build)
    #
    # This lets us identify the stage containing the failure.
    STAGE_PATTERN = re.compile(
        r"^\[Pipeline\]\s+\{\s+\((?P<stage>.+?)\)\s*$"
    )

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

        # This is now the MAXIMUM amount of targeted failure
        # context sent to Ollama, NOT the full Jenkins console size.
        self.max_log_chars = int(
            os.getenv(
                "AI_MAX_LOG_CHARS",
                "10000",
            )
        )

        self.timeout_seconds = float(
            os.getenv(
                "AI_TIMEOUT_SECONDS",
                "180",
            )
        )

        # Number of lines before and after the selected failure.
        self.failure_context_lines = int(
            os.getenv(
                "AI_FAILURE_CONTEXT_LINES",
                "35",
            )
        )

        # Maximum size of a single extracted Jenkins stage.
        self.max_stage_chars = int(
            os.getenv(
                "AI_STAGE_MAX_CHARS",
                "8000",
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
        Analyze a Jenkins console with Ollama.

        IMPORTANT:

        The complete Jenkins console may be passed into this method,
        but the complete console is NOT sent to Ollama.

        A targeted failure-stage excerpt is generated first.
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
            original_log,
            rules_category=rules_category,
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
            f"Model                 : "
            f"{self.model}"
        )

        print(
            f"Ollama URL            : "
            f"{self.ollama_url}"
        )

        print(
            f"Original Jenkins log  : "
            f"{len(original_log)} characters"
        )

        print(
            f"Targeted AI context   : "
            f"{len(prepared_log)} characters"
        )

        print(
            f"Rules category        : "
            f"{rules_category or 'UNKNOWN'}"
        )

        print(
            "Failure evidence      : "
            f"{self._count_failure_lines(prepared_log)} "
            "candidate lines"
        )

        print("-" * 72)
        print("TARGETED LOG SENT TO OLLAMA")
        print("-" * 72)

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
                "num_ctx": 8192,
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

        return self._parse_response(
            raw_response
        )

    # =============================================================
    # TARGETED LOG EXTRACTION
    # =============================================================

    def _prepare_log(
        self,
        log: str,
        rules_category: str | None = None,
    ) -> str:
        """
        Extract a small failure-focused section from the Jenkins log.

        The complete Jenkins console stays inside AutoHeal.

        Ollama receives only:

            - the relevant Jenkins stage when identifiable
            - the failure line
            - surrounding context
            - a small amount of stage context

        This prevents large unrelated pipeline stages from being
        supplied to the local model.
        """

        log = log or ""

        lines = log.splitlines()

        if not lines:
            return (
                "No Jenkins log lines were available."
            )

        # ---------------------------------------------------------
        # 1. Locate failure candidates
        # ---------------------------------------------------------

        candidate_indexes = []

        for index, line in enumerate(lines):

            if self._is_failure_line(
                line,
                rules_category=rules_category,
            ):
                candidate_indexes.append(
                    index
                )

        # ---------------------------------------------------------
        # 2. Choose the best failure line
        # ---------------------------------------------------------

        failure_index = (
            self._select_failure_index(
                lines,
                candidate_indexes,
                rules_category,
            )
        )

        # ---------------------------------------------------------
        # 3. Identify Jenkins stage
        # ---------------------------------------------------------

        stage_name, stage_start, stage_end = (
            self._find_stage_for_failure(
                lines,
                failure_index,
            )
        )

        # ---------------------------------------------------------
        # 4. Extract stage/failure context
        # ---------------------------------------------------------

        if stage_start is not None:

            stage_lines = lines[
                stage_start:stage_end
            ]

            # A stage may still be huge.
            #
            # Keep only a bounded section around the failure.
            if (
                sum(
                    len(line) + 1
                    for line in stage_lines
                )
                > self.max_stage_chars
            ):

                stage_lines = (
                    self._trim_stage_around_failure(
                        stage_lines,
                        failure_index - stage_start,
                    )
                )

            extracted = "\n".join(
                stage_lines
            )

        else:

            # No Declarative Pipeline stage marker.
            #
            # Fall back to a narrow failure window.
            start = max(
                0,
                failure_index
                - self.failure_context_lines,
            )

            end = min(
                len(lines),
                failure_index
                + self.failure_context_lines
                + 1,
            )

            extracted = "\n".join(
                lines[start:end]
            )

        # ---------------------------------------------------------
        # 5. Add focused failure window
        # ---------------------------------------------------------

        focused_start = max(
            0,
            failure_index
            - self.failure_context_lines,
        )

        focused_end = min(
            len(lines),
            failure_index
            + self.failure_context_lines
            + 1,
        )

        focused = "\n".join(
            lines[
                focused_start:focused_end
            ]
        )

        # ---------------------------------------------------------
        # 6. Build AI evidence document
        # ---------------------------------------------------------

        output = [
            "===== AUTOHEAL TARGETED AI EVIDENCE =====",
            "",
            (
                "The complete Jenkins console was analyzed "
                "locally by AutoHeal."
            ),
            (
                "Only the following failure-focused evidence "
                "is being provided to Ollama."
            ),
            "",
            f"Rules category: "
            f"{rules_category or 'UNKNOWN'}",
            "",
        ]

        if stage_name:

            output.extend(
                [
                    f"Failed Jenkins stage: "
                    f"{stage_name}",
                    "",
                ]
            )

        output.extend(
            [
                "===== FAILURE-STAGE CONTEXT =====",
                extracted,
                "",
                "===== FAILURE-CENTERED CONTEXT =====",
                focused,
                "",
                "===== END TARGETED EVIDENCE =====",
            ]
        )

        prepared = "\n".join(
            output
        )

        # ---------------------------------------------------------
        # 7. Redact secrets
        # ---------------------------------------------------------

        prepared = self._redact_secrets(
            prepared
        )

        # ---------------------------------------------------------
        # 8. Final hard limit
        # ---------------------------------------------------------

        if len(prepared) > self.max_log_chars:

            prepared = (
                prepared[
                    :self.max_log_chars
                ]
                + "\n\n"
                "===== AI CONTEXT TRUNCATED =====\n"
                "Only the first portion of the targeted "
                "failure evidence was sent to Ollama."
            )

        return prepared

    # =============================================================
    # FAILURE INDEX SELECTION
    # =============================================================

    def _select_failure_index(
        self,
        lines: list[str],
        candidate_indexes: list[int],
        rules_category: str | None,
    ) -> int:
        """
        Choose the most useful failure line.

        Category-specific strong signals receive higher scores.

        This is deliberately deterministic.

        Ollama is not asked to decide which part of the console
        is relevant.
        """

        if not candidate_indexes:
            return max(
                0,
                len(lines) - 1,
            )

        signals = self.CATEGORY_SIGNALS.get(
            rules_category or "",
            self.FAILURE_SIGNALS,
        )

        best_index = candidate_indexes[-1]
        best_score = -1

        for index in candidate_indexes:

            text = lines[index].strip()

            score = 0

            for signal in signals:

                if signal.lower() in text.lower():
                    score += 10

            # Strong traceback/assertion indicators.
            if "AssertionError" in text:
                score += 30

            if "Traceback" in text:
                score += 25

            if (
                "No matching distribution"
                in text
            ):
                score += 30

            if (
                "Could not find a version"
                in text
            ):
                score += 30

            if "failed to solve:" in text.lower():
                score += 30

            if (
                "requested access to the resource"
                in text.lower()
            ):
                score += 30

            if "connection refused" in text.lower():
                score += 30

            if (
                "permission denied"
                in text.lower()
            ):
                score += 20

            # Generic Jenkins wrapper messages receive very low
            # priority. We want the actual failure, not:
            #
            # script returned exit code 1
            if (
                "script returned exit code"
                in text.lower()
            ):
                score -= 20

            if (
                "process apparently never started"
                in text.lower()
            ):
                score -= 10

            if score > best_score:
                best_score = score
                best_index = index

        return best_index

    # =============================================================
    # STAGE DETECTION
    # =============================================================

    def _find_stage_for_failure(
        self,
        lines: list[str],
        failure_index: int,
    ) -> tuple[str | None, int | None, int]:
        """
        Find the Jenkins Pipeline stage surrounding the failure.

        Example:

            [Pipeline] { (Test)

            ...

            AssertionError

            ...

            [Pipeline] }

        Returns:

            (
                stage_name,
                stage_start,
                stage_end,
            )
        """

        stage_markers = []

        for index, line in enumerate(lines):

            match = self.STAGE_PATTERN.match(
                line.strip()
            )

            if match:

                stage_markers.append(
                    (
                        index,
                        match.group(
                            "stage"
                        ).strip(),
                    )
                )

        if not stage_markers:
            return (
                None,
                None,
                len(lines),
            )

        previous_stage = None

        for marker_index, stage_name in stage_markers:

            if marker_index <= failure_index:
                previous_stage = (
                    marker_index,
                    stage_name,
                )
            else:
                break

        if previous_stage is None:

            return (
                None,
                None,
                len(lines),
            )

        stage_start = previous_stage[0]
        stage_name = previous_stage[1]

        stage_end = len(lines)

        for marker_index, _ in stage_markers:

            if marker_index > stage_start:

                stage_end = marker_index
                break

        return (
            stage_name,
            stage_start,
            stage_end,
        )

    # =============================================================
    # STAGE TRIMMING
    # =============================================================

    def _trim_stage_around_failure(
        self,
        stage_lines: list[str],
        failure_offset: int,
    ) -> list[str]:
        """
        Trim a large stage while preserving the failure context.
        """

        context = self.failure_context_lines

        start = max(
            0,
            failure_offset - context,
        )

        end = min(
            len(stage_lines),
            failure_offset + context + 1,
        )

        selected = stage_lines[
            start:end
        ]

        # If still too large, shrink progressively.
        while (
            len(
                "\n".join(selected)
            )
            > self.max_stage_chars
            and len(selected) > 20
        ):

            context = max(
                10,
                context // 2,
            )

            start = max(
                0,
                failure_offset - context,
            )

            end = min(
                len(stage_lines),
                failure_offset + context + 1,
            )

            selected = stage_lines[
                start:end
            ]

        return selected

    # =============================================================
    # FAILURE DETECTION
    # =============================================================

    def _is_failure_line(
        self,
        line: str,
        rules_category: str | None = None,
    ) -> bool:
        """
        Determine whether a Jenkins line is likely useful
        diagnostic evidence.
        """

        text = line.strip()

        if not text:
            return False

        signals = self.CATEGORY_SIGNALS.get(
            rules_category or "",
            self.FAILURE_SIGNALS,
        )

        return any(
            signal.lower()
            in text.lower()
            for signal in signals
        )

    def _count_failure_lines(
        self,
        log: str,
    ) -> int:
        """
        Count diagnostic candidate lines.
        """

        return sum(
            1
            for line in log.splitlines()
            if self._is_failure_line(line)
        )

    # =============================================================
    # SECRET REDACTION
    # =============================================================

    def _redact_secrets(
        self,
        text: str,
    ) -> str:
        """
        Redact common credentials/secrets before sending evidence
        to Ollama.

        This is not a replacement for Jenkins credential masking.

        It is an additional AI-input safety boundary.
        """

        patterns = [
            (
                r"(?i)(Authorization:\s*Bearer\s+)"
                r"[^\s]+",
                r"\1[REDACTED]",
            ),
            (
                r"(?i)(Authorization:\s*Basic\s+)"
                r"[^\s]+",
                r"\1[REDACTED]",
            ),
            (
                r"(?i)(api[_-]?key\s*[:=]\s*)"
                r"[^\s]+",
                r"\1[REDACTED]",
            ),
            (
                r"(?i)(token\s*[:=]\s*)"
                r"[^\s]+",
                r"\1[REDACTED]",
            ),
            (
                r"(?i)(password\s*[:=]\s*)"
                r"[^\s]+",
                r"\1[REDACTED]",
            ),
            (
                r"(?i)(secret\s*[:=]\s*)"
                r"[^\s]+",
                r"\1[REDACTED]",
            ),
            (
                r"(?i)(access[_-]?key\s*[:=]\s*)"
                r"[^\s]+",
                r"\1[REDACTED]",
            ),
            (
                r"(?i)(private[_-]?key\s*[:=]\s*)"
                r"[^\s]+",
                r"\1[REDACTED]",
            ),
        ]

        result = text

        for pattern, replacement in patterns:

            result = re.sub(
                pattern,
                replacement,
                result,
            )

        return result

    # =============================================================
    # RESPONSE PARSING
    # =============================================================

    def _parse_response(
        self,
        raw_response: str,
    ) -> AIClassification:
        """
        Parse Ollama JSON safely.
        """

        try:

            data = json.loads(
                raw_response
            )

        except json.JSONDecodeError as exc:

            recovered = (
                self._extract_json_object(
                    raw_response
                )
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

        confidence = (
            self._normalize_confidence(
                data.get(
                    "confidence",
                    0.0,
                )
            )
        )

        matched_evidence = (
            self._normalize_list(
                data.get(
                    "matched_evidence",
                    [],
                )
            )
        )

        recommendations = (
            self._normalize_list(
                data.get(
                    "recommendations",
                    [],
                )
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
        Recover a JSON object from a response containing
        additional text or Markdown fences.
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

        return result[:10]

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

            confidence = (
                confidence / 100.0
            )

        return max(
            0.0,
            min(
                1.0,
                confidence,
            ),
        )