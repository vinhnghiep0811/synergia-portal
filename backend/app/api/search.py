from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.constants.activity import (
    ActivityActorType,
    ActivityEventType,
    ActivityObjectType,
    ActivityStatus,
)
from app.models.user import User
from app.schemas.search import SearchRequest, SearchResponse
from app.services.activity_log_service import ActivityLogService
from app.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["search"])

@router.post("/semantic", response_model=SearchResponse)
def semantic_search(
    request: SearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Tìm kiếm ngữ nghĩa (Semantic Search) trên kho dữ liệu tài liệu.
    Truyền vào câu hỏi `query` và số lượng kết quả `top_k`.
    """
    search_service = SearchService(db)
    results = search_service.semantic_search(query=request.query, top_k=request.top_k)

    ActivityLogService(db).log(
        actor_type=ActivityActorType.USER,
        actor_user_id=current_user.id,
        event_type=ActivityEventType.SEARCH_SEMANTIC_EXECUTED,
        object_type=ActivityObjectType.SEARCH_QUERY,
        object_id=uuid4(),
        status=ActivityStatus.INFO,
        message=f'Semantic search executed: "{request.query[:80]}"',
        metadata_json={
            "query": request.query[:500],
            "top_k": request.top_k,
            "result_count": len(results),
        },
    )
    db.commit()
    return SearchResponse(results=results)


@router.get("/keyword", response_model=SearchResponse)
def keyword_search(
    query: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    search_service = SearchService(db)
    results = search_service.keyword_search(
        query=query,
        limit=limit,
    )

    ActivityLogService(db).log(
        actor_type=ActivityActorType.USER,
        actor_user_id=current_user.id,
        event_type=ActivityEventType.SEARCH_KEYWORD_EXECUTED,
        object_type=ActivityObjectType.SEARCH_QUERY,
        object_id=uuid4(),
        status=ActivityStatus.INFO,
        message=f'Keyword search executed: "{query[:80]}"',
        metadata_json={
            "query": query[:500],
            "limit": limit,
            "result_count": len(results),
        },
    )
    db.commit()
    return SearchResponse(results=results)
