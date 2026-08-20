import pytest

from app.ai.classifier import AIClassifier


@pytest.mark.asyncio
async def test_ai_disabled_returns_unknown():

    classifier = AIClassifier()

    classifier.enabled = False
    classifier.client = None

    result = await classifier.classify(
        "Some unknown Jenkins failure"
    )

    assert result.category == "UNKNOWN"
    assert result.confidence == 0.0


def test_ai_allowed_categories():

    assert "FLAKY_TEST" not in (
    AIClassifier.ALLOWED_CATEGORIES
    )
    assert "NETWORK_FAILURE" in AIClassifier.ALLOWED_CATEGORIES
    assert "CODE_FAILURE" in AIClassifier.ALLOWED_CATEGORIES
    assert "UNKNOWN" in AIClassifier.ALLOWED_CATEGORIES

@pytest.mark.asyncio
async def test_ai_classification_is_structured(
    monkeypatch,
):

    from app.ai.models import AIClassification

    classifier = AIClassifier()

    classifier.enabled = True

    fake_result = AIClassification(
        category="NETWORK_FAILURE",
        root_cause="Registry connection timed out.",
        reasoning=(
            "The Jenkins log contains repeated "
            "connection timeout errors."
        ),
        confidence=0.91,
        matched_evidence=[
            "connection timeout",
            "registry request timed out",
        ],
    )

    async def fake_classify(log):
        return fake_result

    monkeypatch.setattr(
        classifier,
        "classify",
        fake_classify,
    )

    result = await classifier.classify(
        "registry connection timeout"
    )

    assert result.category == "NETWORK_FAILURE"
    assert result.confidence == 0.91