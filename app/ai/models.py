from pydantic import BaseModel, Field


class AIClassification(BaseModel):

    category: str = Field(
        description="AutoHeal failure category."
    )

    root_cause: str

    reasoning: str

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    matched_evidence: list[str]