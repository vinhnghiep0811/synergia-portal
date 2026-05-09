from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.search import SearchRequest, SearchResponse
from app.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["search"])

@router.post("/semantic", response_model=SearchResponse)
def semantic_search(
    request: SearchRequest,
    db: Session = Depends(get_db)
):
    """
    Tìm kiếm ngữ nghĩa (Semantic Search) trên kho dữ liệu tài liệu.
    Truyền vào câu hỏi `query` và số lượng kết quả `top_k`.
    """
    search_service = SearchService(db)
    results = search_service.semantic_search(query=request.query, top_k=request.top_k)
    return SearchResponse(results=results)


@router.get("/keyword", response_model=SearchResponse)
def keyword_search(
    query: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
):
    search_service = SearchService(db)
    results = search_service.keyword_search(
        query=query,
        limit=limit,
    )
    return SearchResponse(results=results)