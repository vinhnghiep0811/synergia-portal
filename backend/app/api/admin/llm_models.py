from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_admin
from app.models.user import User
from app.schemas.admin import (
    LLMModelOptionCreateRequest,
    LLMModelOptionItem,
    LLMModelOptionListResponse,
    LLMModelOptionUpdateRequest,
)
from app.services.llm_model_option_service import LLMModelOptionService

router = APIRouter()


@router.get("/llm-models", response_model=LLMModelOptionListResponse)
def list_llm_models(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    del current_user
    service = LLMModelOptionService(db)
    models = service.list_models()
    return LLMModelOptionListResponse(
        models=[
            LLMModelOptionItem(
                id=model.id,
                name=model.name,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            for model in models
        ]
    )


@router.post("/llm-models", response_model=LLMModelOptionItem, status_code=status.HTTP_201_CREATED)
def create_llm_model(
    payload: LLMModelOptionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = LLMModelOptionService(db)
    try:
        row = service.create_model(payload.name, actor_user_id=current_user.id)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return LLMModelOptionItem(
        id=row.id,
        name=row.name,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.patch("/llm-models/{model_id}", response_model=LLMModelOptionItem)
def update_llm_model(
    model_id: int,
    payload: LLMModelOptionUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    del current_user
    service = LLMModelOptionService(db)
    try:
        row = service.update_model(model_id, payload.name)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return LLMModelOptionItem(
        id=row.id,
        name=row.name,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.delete("/llm-models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_llm_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    del current_user
    service = LLMModelOptionService(db)
    try:
        service.delete_model(model_id)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return None
