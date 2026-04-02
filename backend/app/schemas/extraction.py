from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.extraction_result import (
    ScalarFieldWithEvidence,
    ListFieldWithEvidence,
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
    contributions: ListFieldWithEvidence | None = None
    limitations: ListFieldWithEvidence | None = None
    evaluation_setup: EvaluationSetupField | None = None

    raw_llm_response: str | None = None
    token_input: int | None = None
    token_output: int | None = None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)