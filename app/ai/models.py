from pydantic import BaseModel, Field


class AIClassification(BaseModel):
    """
    Diagnostic output produced by the local Ollama model.

    Important:
    This model is diagnostic only.

    The AI does NOT control:
        - AutoHeal failure classification
        - policy decisions
        - remediation actions
        - Jenkins retries

    Those responsibilities remain with the deterministic
    classifier and Policy Engine.
    """

    category: str = Field(
        description=(
            "A human-readable description of the failure type. "
            "This is informational only and does not control remediation."
        )
    )

    root_cause: str = Field(
        description=(
            "The most likely technical root cause of the Jenkins failure."
        )
    )

    reasoning: str = Field(
        description=(
            "A concise explanation connecting the Jenkins log evidence "
            "to the suspected root cause."
        )
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Confidence in the diagnosis from 0.0 to 1.0."
        ),
    )

    matched_evidence: list[str] = Field(
        default_factory=list,
        description=(
            "Important log messages, errors, stack traces, commands, "
            "or other evidence supporting the diagnosis."
        ),
    )

    recommendations: list[str] = Field(
        default_factory=list,
        description=(
            "Practical checks or next steps the developer/operator "
            "should perform."
        ),
    )