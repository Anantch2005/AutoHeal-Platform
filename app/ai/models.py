from pydantic import BaseModel, Field


class AIClassification(BaseModel):
    category: str = Field(
        description=(
            "One of the supported AutoHeal categories."
        )
    )

    root_cause: str = Field(
        description=(
            "Concise explanation of the most likely cause."
        )
    )

    reasoning: str = Field(
        description=(
            "Evidence-based reasoning from the Jenkins log."
        )
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Heuristic confidence from 0 to 1. "
            "Not a calibrated probability."
        )
    )

    matched_evidence: list[str] = Field(
        description=(
            "Important log snippets or signals supporting "
            "the classification."
        )
    )