import json
import os
import re

import httpx

from app.ai.models import AIClassification
from app.ai.prompt import SYSTEM_PROMPT, build_prompt


class AIClassifier:
    """
    Local Ollama-powered CI/CD diagnostic assistant.

    AI is advisory only.

    It analyzes Jenkins logs and returns:
        - diagnostic category
        - root cause
        - reasoning
        - confidence
        - evidence
        - recommendations

    It does NOT decide AutoHeal remediation.
    """

    def __init__(self):
        self.enabled = (
            os.getenv("AI_ENABLED", "false").lower()
            in {"true", "1", "yes", "on"}
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
                "12000",
            )
        )

        self.timeout = float(
            os.getenv(
                "AI_TIMEOUT_SECONDS",
                "120",
            )
        )

    @staticmethod
    def _extract_json(text: str) -> dict:
        """
        Extract JSON from the Ollama response.

        Handles:
        - pure JSON
        - Markdown JSON fences
        - accidental surrounding text
        """

        text = text.strip()

        # Remove Markdown code fences if the model ignored
        # the instruction not to use them.
        text = re.sub(
            r"^```(?:json)?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"\s*```$",
            "",
            text,
        )

        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to locate the first JSON object.
        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1 or end <= start:
            raise ValueError(
                "Ollama did not return a JSON object."
            )

        candidate = text[start : end + 1]

        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Ollama returned invalid JSON."
            ) from exc

    @staticmethod
    def _normalise_string(
        value,
        default: str,
    ) -> str:
        if value is None:
            return default

        value = str(value).strip()

        if not value:
            return default

        return value

    @staticmethod
    def _normalise_list(value) -> list[str]:
        if value is None:
            return []

        if isinstance(value, str):
            value = [value]

        if not isinstance(value, list):
            return []

        result = []

        for item in value:
            item = str(item).strip()

            if item:
                result.append(item)

        return result[:10]

    @staticmethod
    def _normalise_confidence(value) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.0

        # Some local models occasionally return percentages.
        if confidence > 1.0 and confidence <= 100.0:
            confidence = confidence / 100.0

        return max(
            0.0,
            min(1.0, confidence),
        )

    async def classify(
        self,
        log: str,
    ) -> AIClassification:
        """
        Analyze a Jenkins failure log with Ollama.
        """

        if not self.enabled:
            raise RuntimeError(
                "AI analysis is disabled."
            )

        if not log:
            raise ValueError(
                "Cannot perform AI analysis because "
                "the Jenkins console log is empty."
            )

        # Keep the prompt bounded so a huge Jenkins log does not
        # overwhelm the local model.
        trimmed_log = log[-self.max_log_chars :]

        payload = {
            "model": self.model,
            "system": SYSTEM_PROMPT,
            "prompt": build_prompt(trimmed_log),
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
            },
        }

        url = (
            f"{self.ollama_url}"
            "/api/generate"
        )

        async with httpx.AsyncClient(
            timeout=self.timeout
        ) as client:

            response = await client.post(
                url,
                json=payload,
            )

            response.raise_for_status()

        data = response.json()

        raw_output = data.get(
            "response",
            "",
        )

        if not raw_output:
            raise ValueError(
                "Ollama returned an empty response."
            )

        parsed = self._extract_json(
            raw_output
        )

        category = self._normalise_string(
            parsed.get("category"),
            "unknown",
        )

        root_cause = self._normalise_string(
            parsed.get("root_cause"),
            "The root cause could not be determined from the available log.",
        )

        reasoning = self._normalise_string(
            parsed.get("reasoning"),
            "The available Jenkins log did not provide enough diagnostic evidence.",
        )

        confidence = self._normalise_confidence(
            parsed.get("confidence")
        )

        evidence = self._normalise_list(
            parsed.get("matched_evidence")
        )

        recommendations = self._normalise_list(
            parsed.get("recommendations")
        )

        return AIClassification(
            category=category,
            root_cause=root_cause,
            reasoning=reasoning,
            confidence=confidence,
            matched_evidence=evidence,
            recommendations=recommendations,
        )