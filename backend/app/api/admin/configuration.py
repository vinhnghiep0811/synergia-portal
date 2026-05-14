from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_admin
from app.models.user import User
from app.schemas.admin import (
    AdminConfigResponse,
    AdminConfigUpdateRequest,
    AdminEvaluationReportResponse,
    ConfigValidateRequest,
    ConfigValidateResponse,
)
from app.services.admin_config_service import AdminConfigService
from app.services.admin_reporting_service import AdminReportingService

router = APIRouter()


@router.get("/configuration", response_model=AdminConfigResponse)
def get_admin_configuration(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = AdminConfigService(db)
    return service.get_configuration()


@router.patch("/configuration", response_model=AdminConfigResponse)
def update_admin_configuration(
    payload: AdminConfigUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = AdminConfigService(db)
    return service.update_configuration(payload=payload, actor_user=current_user)


@router.post("/configuration/validate", response_model=ConfigValidateResponse)
def validate_admin_configuration(
    payload: ConfigValidateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Test service connections without saving. Validates LLM, Semantic Scholar,
    Telegram, or Embedding individually or all at once."""
    service = AdminConfigService(db)
    return service.validate_services(payload)


@router.get("/evaluation-report", response_model=AdminEvaluationReportResponse)
def get_admin_evaluation_report(
    window_days: int = Query(7, ge=1, le=365),
    search_sample_limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = AdminReportingService(db)
    return service.build_evaluation_report(
        window_days=window_days,
        search_sample_limit=search_sample_limit,
    )

