import json
import re

from openai import AsyncOpenAI

from app.ai.models import AIClassification
from app.ai.prompt import SYSTEM_PROMPT
from app.config import settings


class AIClassifier:

    ALLOWED_CATEGORIES = {
        "FLAKY_TEST",
        "WORKSPACE_FAILURE",
        "DEPENDENCY_FAILURE",
        "NETWORK_FAILURE",
        "DOCKER_FAILURE",
        "REGISTRY_FAILURE",
        "CODE_FAILURE",
        "UNKNOWN",
    }

    def __init__(self):
        self.enabled = (
            settings.ai_enabled
            and bool(settings.openai_api_key)
        )

        self.client = (
            AsyncOpenAI(
                api_key=settings.openai_api_key
            )
            if self.enabled
            else None
        )

    def _redact(self, log: str) -> str:
        """
        Redact common credential/token patterns before
        sending logs to the external AI provider.
        """

        redacted = log

        patterns = [
            (
                r"(?i)(authorization:\s*bearer\s+)[^\s]+",
                r"\1[REDACTED]",
            ),
            (
                r"(?i)(token[\"'=:\s]+)[A-Za-z0-9._-]+",
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
        ]

        for pattern, replacement in patterns:
            redacted = re.sub(
                pattern,
                replacement,
                redacted,
            )

        return redacted

    def _build_log(self, log: str) -> str:
        redacted = self._redact(log)

        return redacted[
            -settings.ai_max_log_chars:
        ]

    async def classify(
        self,
        log: str,
    ) -> AIClassification:

        if not self.enabled or self.client is None:
            return AIClassification(
                category="UNKNOWN",
                root_cause=(
                    "AI classification is disabled "
                    "or no API key is configured."
                ),
                reasoning=(
                    "No AI provider was available."
                ),
                confidence=0.0,
                matched_evidence=[],
            )

        payload = {
            "jenkins_log": self._build_log(log),
        }

        response = await self.client.responses.create(
            model=settings.ai_model,
            instructions=SYSTEM_PROMPT,
            input=json.dumps(payload),
            text={
                "format": {
                    "type": "json_schema",
                    "name": "autoheal_failure_diagnosis",
                    "description": (
                        "Structured diagnosis of an ambiguous "
                        "Jenkins CI/CD failure."
                    ),
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "enum": [
                                    "FLAKY_TEST",
                                    "WORKSPACE_FAILURE",
                                    "DEPENDENCY_FAILURE",
                                    "NETWORK_FAILURE",
                                    "DOCKER_FAILURE",
                                    "REGISTRY_FAILURE",
                                    "CODE_FAILURE",
                                    "UNKNOWN",
                                ],
                            },
                            "root_cause": {
                                "type": "string"
                            },
                            "reasoning": {
                                "type": "string"
                            },
                            "confidence": {
                                "type": "number",
                                "minimum": 0,
                                "maximum": 1,
                            },
                            "matched_evidence": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                },
                            },
                        },
                        "required": [
                            "category",
                            "root_cause",
                            "reasoning",
                            "confidence",
                            "matched_evidence",
                        ],
                        "additionalProperties": False,
                    },
                }
            },
        )

        parsed = json.loads(
            response.output_text
        )

        result = AIClassification(**parsed)

        if result.category not in self.ALLOWED_CATEGORIES:
            return AIClassification(
                category="UNKNOWN",
                root_cause=(
                    "AI returned an unsupported category."
                ),
                reasoning=(
                    "The AI classification was rejected "
                    "because the category was invalid."
                ),
                confidence=0.0,
                matched_evidence=[],
            )

        return result