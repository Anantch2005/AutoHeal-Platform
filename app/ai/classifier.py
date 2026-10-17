
"""
Focused Jenkins failure-context extractor + Ollama diagnostic client.

Architecture:

    full Jenkins console
        ├── deterministic BuildSentry classifier
        ├── audit/persistence
        └── focused evidence extractor -> Ollama

Ollama is diagnostic only.

It never selects:
    - remediation
    - retry
    - policy decisions
    - source-code changes
    - dependency changes
    - infrastructure changes
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.ai.context import FailureContextExtractor
from app.ai.models import AIClassification
from app.ai.prompt import SYSTEM_PROMPT, build_user_prompt
from app.config import settings

logger = logging.getLogger(__name__)


class AIClassifier(FailureContextExtractor):
    """
    Local Ollama diagnostic assistant.

    The complete Jenkins console may be passed into this class,
    but only focused failure evidence is sent to Ollama.
    """

    def __init__(self) -> None:

        self.enabled = settings.ai_enabled
        self.ollama_url = settings.ollama_url.rstrip("/")
        self.model = settings.ollama_model
        self.max_log_chars = settings.ai_max_log_chars
        self.timeout_seconds = settings.ai_timeout_seconds
        self.failure_context_lines = settings.ai_failure_context_lines
        self.max_stage_chars = settings.ai_stage_max_chars
        self.max_failure_candidates = settings.ai_max_failure_candidates

    # =============================================================
    # PUBLIC API
    # =============================================================

    async def classify(
        self,
        log: str,
        rules_category: str | None = None,
    ) -> AIClassification:

        if not self.enabled:

            raise RuntimeError(
                "AI analysis is disabled."
            )

        original_log = log or ""

        if not original_log.strip():

            raise RuntimeError(
                "Jenkins console log is empty."
            )

        # IMPORTANT:
        #
        # The complete Jenkins console enters this method.
        #
        # The complete console is NEVER placed directly into
        # the Ollama prompt.
        prepared_log = self._prepare_log(
            original_log,
            rules_category=rules_category,
        )

        user_prompt = build_user_prompt(
            log=prepared_log,
            rules_category=rules_category,
        )

        logger.info(
            "Preparing Ollama diagnostic request: model=%s original_log_chars=%d "
            "focused_context_chars=%d rules_category=%s failure_candidates=%d",
            self.model,
            len(original_log),
            len(prepared_log),
            rules_category or "UNKNOWN",
            self._count_failure_lines(prepared_log),
        )
        # Never log the raw or redacted prompt: console output may still contain
        # proprietary code, tokens, URLs, usernames, or internal hostnames.

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

        except httpx.HTTPError as exc:

            raise RuntimeError(
                f"Ollama request failed: {exc}"
            ) from exc

        body = response.json()

        raw_response = (
            body.get("response")
            if isinstance(body, dict)
            else None
        )

        if not raw_response:

            raise RuntimeError(
                "Ollama returned an empty response."
            )

        return self._parse_response(
            raw_response
        )

    # =============================================================
    # OLLAMA RESPONSE PARSING
    # =============================================================

    def _parse_response(
        self,
        raw_response: str,
    ) -> AIClassification:

        try:

            data = json.loads(
                raw_response
            )

        except json.JSONDecodeError as exc:

            data = (
                self._extract_json_object(
                    raw_response
                )
            )

            if data is None:

                raise RuntimeError(
                    "Ollama returned invalid JSON: "
                    f"{exc}"
                ) from exc

        if not isinstance(
            data,
            dict,
        ):

            raise RuntimeError(
                "Ollama JSON response "
                "was not an object."
            )

        category = (
            self._clean_string(
                data.get(
                    "category",
                    "unknown",
                )
            )
            or "unknown"
        )

        root_cause = (
            self._clean_string(
                data.get(
                    "root_cause",
                    "",
                )
            )
        )

        reasoning = (
            self._clean_string(
                data.get(
                    "reasoning",
                    "",
                )
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

        return AIClassification(
            category=category,
            root_cause=(
                root_cause
                or
                "The AI did not provide "
                "a root cause."
            ),
            reasoning=(
                reasoning
                or
                "The AI did not provide "
                "additional reasoning."
            ),
            confidence=confidence,
            matched_evidence=matched_evidence,
            recommendations=recommendations,
        )

    # =============================================================
    # JSON EXTRACTION
    # =============================================================

    @staticmethod
    def _extract_json_object(
        text: str,
    ) -> dict[str, Any] | None:

        start = text.find(
            "{"
        )

        end = text.rfind(
            "}"
        )

        if (
            start < 0
            or end <= start
        ):

            return None

        try:

            value = json.loads(
                text[
                    start:end + 1
                ]
            )

        except json.JSONDecodeError:

            return None

        if isinstance(
            value,
            dict,
        ):

            return value

        return None

    # =============================================================
    # STRING NORMALIZATION
    # =============================================================

    @staticmethod
    def _clean_string(
        value: Any,
    ) -> str:

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

    # =============================================================
    # LIST NORMALIZATION
    # =============================================================

    @staticmethod
    def _normalize_list(
        value: Any,
    ) -> list[str]:

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

            value = [
                value
            ]

        result: list[str] = []

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

    # =============================================================
    # CONFIDENCE NORMALIZATION
    # =============================================================

    @staticmethod
    def _normalize_confidence(
        value: Any,
    ) -> float:

        try:

            confidence = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return 0.0

        # Models sometimes return:
        #
        # 90
        #
        # instead of:
        #
        # 0.90
        if confidence > 1.0:

            confidence /= 100.0

        return max(
            0.0,
            min(
                1.0,
                confidence,
            ),
        )