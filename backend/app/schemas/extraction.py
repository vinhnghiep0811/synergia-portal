from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.extraction_result import (
    ScalarFieldWithEvidence,
    ListItemWithEvidence,
    EvaluationSetupField,
)


class ExtractionRunListItemResponse(BaseModel):
    id: UUID
    canonical_document_id: UUID
    model_name: str | None = None
    prompt_version: str | None = None
    status: str
    token_input: int | None = None
    token_output: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExtractionRunResponse(BaseModel):
    id: UUID
    canonical_document_id: UUID
    model_name: str | None = None
    prompt_version: str | None = None
    status: str

    problem_statement: ScalarFieldWithEvidence | None = None
    main_method: ScalarFieldWithEvidence | None = None
    contributions: list[ListItemWithEvidence] = Field(default_factory=list)
    limitations: list[ListItemWithEvidence] = Field(default_factory=list)
    evaluation_setup: EvaluationSetupField | None = None

    raw_llm_response: str | None = None
    token_input: int | None = None
    token_output: int | None = None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("contributions", "limitations", mode="before")
    @classmethod
    def none_to_empty_list(cls, v):
        return v or []