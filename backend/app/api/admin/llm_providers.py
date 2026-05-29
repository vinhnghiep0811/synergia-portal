from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_admin
from app.models.user import User
from app.schemas.admin import LLMProviderCreateRequest, LLMProviderListResponse
from app.services.llm_provider_registry_service import LLMProviderRegistryService

router = APIRouter()


@router.get("/llm-providers", response_model=LLMProviderListResponse)
def get_llm_providers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = LLMProviderRegistryService(db)
    return {"providers": service.list_providers()}


@router.post("/llm-providers", response_model=LLMProviderListResponse)
def add_llm_provider(
    payload: LLMProviderCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = LLMProviderRegistryService(db)
    return {"providers": service.add_provider(payload.name, actor_user=current_user)}


@router.delete("/llm-providers/{provider_name}", response_model=LLMProviderListResponse)
def delete_llm_provider(
    provider_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = LLMProviderRegistryService(db)
    return {"providers": service.remove_provider(provider_name)}
