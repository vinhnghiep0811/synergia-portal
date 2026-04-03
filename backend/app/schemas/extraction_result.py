from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class EvidenceItem(BaseModel):
    snippet: str = Field(..., min_length=1)
    page: Optional[int] = None
    section: Optional[str] = None


class ScalarFieldWithEvidence(BaseModel):
    value: Optional[str] = None
    evidence: List[EvidenceItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_evidence_for_value(self):
        if self.value is not None and self.value.strip() != "" and len(self.evidence) == 0:
            raise ValueError("Non-null value must include at least one evidence item.")
        return self


class ListFieldWithEvidence(BaseModel):
    items: List[str] = Field(default_factory=list)
    evidence: List[EvidenceItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_evidence_for_items(self):
        if len(self.items) > 0 and len(self.evidence) == 0:
            raise ValueError("Non-empty items must include at least one evidence item.")
        return self


class EvaluationSetupValue(BaseModel):
    datasets: List[str] = Field(default_factory=list)
    metrics: List[str] = Field(default_factory=list)
    benchmarks: List[str] = Field(default_factory=list)


class EvaluationSetupField(BaseModel):
    value: Optional[EvaluationSetupValue] = None
    evidence: List[EvidenceItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_evidence_for_value(self):
        has_content = (
            self.value is not None
            and (
                len(self.value.datasets) > 0
                or len(self.value.metrics) > 0
                or len(self.value.benchmarks) > 0
            )
        )
        if has_content and len(self.evidence) == 0:
            raise ValueError("Non-empty evaluation_setup must include at least one evidence item.")
        return self


class ExtractionResultSchema(BaseModel):
    problem: ScalarFieldWithEvidence = Field(default_factory=ScalarFieldWithEvidence)
    method: ScalarFieldWithEvidence = Field(default_factory=ScalarFieldWithEvidence)
    contributions: ListFieldWithEvidence = Field(default_factory=ListFieldWithEvidence)
    limitations: ListFieldWithEvidence = Field(default_factory=ListFieldWithEvidence)
    evaluation_setup: EvaluationSetupField = Field(default_factory=EvaluationSetupField)