from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_admin
from app.models.user import User
from app.schemas.admin import LLMPromptTemplatesResponse, LLMPromptTemplatesUpdateRequest
from app.services.llm_prompt_template_service import LLMPromptTemplateService

router = APIRouter()


@router.get("/llm-prompts", response_model=LLMPromptTemplatesResponse)
def get_llm_prompts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = LLMPromptTemplateService(db)
    return {"templates": service.list_templates()}


@router.patch("/llm-prompts", response_model=LLMPromptTemplatesResponse)
def update_llm_prompts(
    payload: LLMPromptTemplatesUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = LLMPromptTemplateService(db)
    templates = service.update_templates(payload.templates, actor_user=current_user)
    return {"templates": templates}
