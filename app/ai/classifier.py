import json
import re

import httpx

from app.ai.models import AIClassification
from app.ai.prompt import SYSTEM_PROMPT
from app.config import settings


class AIClassifier:

    ALLOWED_CATEGORIES = {
        "WORKSPACE_FAILURE",
        "DEPENDENCY_FAILURE",
        "NETWORK_FAILURE",
        "DOCKER_FAILURE",
        "REGISTRY_FAILURE",
        "CODE_FAILURE",
        "UNKNOWN",
    }

    def __init__(self):

        self.enabled = settings.ai_enabled

        self.base_url = (
            settings.ollama_url.rstrip("/")
        )

        self.model = settings.ollama_model

    def _redact(self, log: str) -> str:

        patterns = [
            (
                r"(?i)(authorization:\s*bearer\s+)[^\s]+",
                r"\1[REDACTED]",
            ),
            (
                r"(?i)(password[\"'=:\s]+)[^\s]+",
                r"\1[REDACTED]",
            ),
            (
                r"(?i)(api[_-]?key[\"'=:\s]+)[^\s]+",
                r"\1[REDACTED]",
            ),
            (
                r"(?i)(token[\"'=:\s]+)[^\s]+",
                r"\1[REDACTED]",
            ),
        ]

        redacted = log

        for pattern, replacement in patterns:
            redacted = re.sub(
                pattern,
                replacement,
                redacted,
            )

        return redacted

    def _prepare_log(self, log: str) -> str:

        redacted = self._redact(log)

        return redacted[
            -settings.ai_max_log_chars:
        ]

    async def classify(
        self,
        log: str,
    ) -> AIClassification:

        if not self.enabled:

            return AIClassification(
                category="UNKNOWN",
                root_cause=(
                    "Local AI classification is disabled."
                ),
                reasoning=(
                    "AI_ENABLED=false."
                ),
                confidence=0.0,
                matched_evidence=[],
            )

        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            "Jenkins failure log:\n"
            "--------------------\n"
            f"{self._prepare_log(log)}\n"
            "--------------------\n\n"
            "Return JSON with exactly these fields:\n"
            "{\n"
            '  "category": "...",\n'
            '  "root_cause": "...",\n'
            '  "reasoning": "...",\n'
            '  "confidence": 0.0,\n'
            '  "matched_evidence": ["..."]\n'
            "}"
        )

        async with httpx.AsyncClient() as client:

            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                },
                timeout=120,
            )

            response.raise_for_status()

            data = response.json()

        raw = data.get("response")

        if not raw:
            raise RuntimeError(
                "Ollama returned an empty response."
            )

        parsed = json.loads(raw)

        result = AIClassification(**parsed)

        if result.category not in self.ALLOWED_CATEGORIES:

            return AIClassification(
                category="UNKNOWN",
                root_cause=(
                    "Ollama returned an unsupported "
                    "failure category."
                ),
                reasoning=(
                    "AI output failed category validation."
                ),
                confidence=0.0,
                matched_evidence=[],
            )

        return result