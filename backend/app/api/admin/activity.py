from uuid import UUID

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
    paper_record_id: UUID | None = Query(None, description="Lọc theo paper_record_id"),
    canonical_document_id: UUID | None = Query(None, description="Lọc theo canonical_document_id"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    service = ActivityQueryService(db)
    return service.list_activity_logs(
        skip=skip,
        limit=limit,
        event_type=event_type,
        status=status,
        paper_record_id=paper_record_id,
        canonical_document_id=canonical_document_id,
    )