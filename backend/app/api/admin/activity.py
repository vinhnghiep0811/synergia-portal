from uuid import UUID
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_admin
from app.models.user import User
from app.schemas.activity import ActivityLogListResponse
from app.services.activity_query_service import ActivityQueryService

router = APIRouter()


@router.get(
    "/activity",
    response_model=ActivityLogListResponse,
    summary="Lay activity feed cho admin",
    description="""
API dùng để lấy danh sách activity của hệ thống cho màn admin activity.

### Chức năng
- Trả về activity mới nhất trước
- Hỗ trợ filter theo event_type, status, paper_record_id, canonical_document_id
- Hỗ trợ phân trang với skip/limit
- Trả về tổng số bản ghi để FE render pagination

### Dùng cho FE
FE gọi endpoint này khi:
- mở trang admin activity
- bấm refresh
- đổi filter
- phân trang
""",
)
def list_admin_activity(
    skip: int = Query(0, ge=0, description="Số lượng bản ghi bỏ qua"),
    limit: int = Query(20, ge=1, le=100, description="Số lượng activity tối đa trả về"),
    event_type: str | None = Query(None, description="Lọc theo loại event"),
    status: str | None = Query(None, description="Lọc theo status"),
    actor_type: str | None = Query(None, description="Lọc theo actor_type"),
    paper_record_id: UUID | None = Query(None, description="Lọc theo paper_record_id"),
    canonical_document_id: UUID | None = Query(None, description="Lọc theo canonical_document_id"),
    days: int | None = Query(None, ge=1, le=365, description="Lấy log trong N ngày gần nhất"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    created_from = None
    if days:
        created_from = datetime.now(timezone.utc) - timedelta(days=days)

    service = ActivityQueryService(db)
    return service.list_activity_logs(
        skip=skip,
        limit=limit,
        event_type=event_type,
        status=status,
        actor_type=actor_type,
        paper_record_id=paper_record_id,
        canonical_document_id=canonical_document_id,
        created_from=created_from,
    )


@router.get(
    "/processing-logs",
    response_model=ActivityLogListResponse,
    summary="Lay processing log cho admin",
)
def list_admin_processing_logs(
    skip: int = Query(0, ge=0, description="Số lượng bản ghi bỏ qua"),
    limit: int = Query(20, ge=1, le=100, description="Số lượng log tối đa trả về"),
    event_family: str = Query(
        "all",
        description="all | parse | semantic_scholar | llm_extraction | duplicate | canonical",
    ),
    status: str | None = Query(None, description="Lọc theo status"),
    errors_only: bool = Query(False, description="Chỉ lấy log lỗi"),
    paper_record_id: UUID | None = Query(None, description="Lọc theo paper_record_id"),
    canonical_document_id: UUID | None = Query(None, description="Lọc theo canonical_document_id"),
    days: int = Query(7, ge=1, le=365, description="Lấy log trong N ngày gần nhất"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    prefix_by_family = {
        "parse": "parse_",
        "semantic_scholar": "semantic_scholar_",
        "llm_extraction": "llm_extraction_",
        "duplicate": "duplicate_",
        "canonical": "canonical_",
        "all": None,
    }
    if event_family not in prefix_by_family:
        event_family = "all"

    created_from = datetime.now(timezone.utc) - timedelta(days=days)
    effective_status = "error" if errors_only else status

    service = ActivityQueryService(db)
    return service.list_activity_logs(
        skip=skip,
        limit=limit,
        event_prefix=prefix_by_family[event_family],
        status=effective_status,
        actor_type="system",
        paper_record_id=paper_record_id,
        canonical_document_id=canonical_document_id,
        created_from=created_from,
    )
