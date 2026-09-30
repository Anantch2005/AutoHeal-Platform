import json

import pytest

from app.ai.classifier import AIClassifier


class FakeResponse:

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeAsyncClient:

    def __init__(self, response):
        self.response = response
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        tb,
    ):
        return False

    async def post(
        self,
        url,
        **kwargs,
    ):
        self.calls.append(
            (
                url,
                kwargs,
            )
        )

        return self.response


@pytest.mark.asyncio
async def test_ai_disabled_returns_unknown():

    classifier = AIClassifier()

    classifier.enabled = False

    result = await classifier.classify(
        "Some unknown Jenkins failure"
    )

    assert result.category == "UNKNOWN"
    assert result.confidence == 0.0


def test_ai_allowed_categories():

    assert (
        "FLAKY_TEST"
        not in AIClassifier.ALLOWED_CATEGORIES
    )

    assert (
        "NETWORK_FAILURE"
        in AIClassifier.ALLOWED_CATEGORIES
    )

    assert (
        "CODE_FAILURE"
        in AIClassifier.ALLOWED_CATEGORIES
    )

    assert (
        "UNKNOWN"
        in AIClassifier.ALLOWED_CATEGORIES
    )


def test_ai_log_redaction():

    classifier = AIClassifier()

    prepared = classifier._prepare_log(
        "Authorization: Bearer super-secret "
        "api_key=top-secret "
        "password=hidden "
        "token=abc123"
    )

    assert "super-secret" not in prepared
    assert "top-secret" not in prepared
    assert "hidden" not in prepared
    assert "abc123" not in prepared

    assert (
        prepared.count("[REDACTED]")
        >= 4
    )


@pytest.mark.asyncio
async def test_ai_classification_parses_real_ollama_response(
    monkeypatch,
):

    classifier = AIClassifier()

    classifier.enabled = True

    payload = {
        "response": json.dumps(
            {
                "category": "NETWORK_FAILURE",
                "root_cause": (
                    "Registry connection timed out."
                ),
                "reasoning": (
                    "The Jenkins log contains "
                    "repeated connection timeout errors."
                ),
                "confidence": 0.91,
                "matched_evidence": [
                    "connection timeout",
                    "registry request timed out",
                ],
            }
        )
    }

    fake_client = FakeAsyncClient(
        FakeResponse(payload)
    )

    def make_client():
        return fake_client

    monkeypatch.setattr(
        "app.ai.classifier.httpx.AsyncClient",
        make_client,
    )

    result = await classifier.classify(
        "registry connection timeout"
    )

    assert result.category == "NETWORK_FAILURE"

    assert result.confidence == 0.91

    assert (
        result.root_cause
        == "Registry connection timed out."
    )

    assert result.matched_evidence == [
        "connection timeout",
        "registry request timed out",
    ]

    assert len(fake_client.calls) == 1

    url, kwargs = fake_client.calls[0]

    assert url.endswith(
        "/api/generate"
    )

    assert kwargs["json"]["stream"] is False

    assert (
        kwargs["json"]["format"]
        == "json"
    )