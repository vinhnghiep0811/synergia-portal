from pydantic import BaseModel, Field
from typing import List
from uuid import UUID


class SearchRequest(BaseModel):
    query: str = Field(..., description="Câu hỏi hoặc từ khóa tìm kiếm")
    top_k: int = Field(5, ge=1, le=50, description="Số lượng kết quả tối đa trả về")


class SearchResultItem(BaseModel):
    chunk_id: UUID | None = Field(None, description="ID của đoạn text nếu kết quả đến từ chunk")
    canonical_document_id: UUID | None = Field(None, description="ID của tài liệu chuẩn hóa")
    paper_id: UUID | None = Field(None, description="ID của paper record nếu kết quả đến từ paper")
    title: str | None = Field(None, description="Tiêu đề của tài liệu")
    content: str = Field(..., description="Snippet hoặc nội dung khớp")
    similarity_score: float = Field(..., description="Điểm khớp / tương đồng")
    source: str = Field("semantic", description="semantic | metadata | chunk")


class SearchResponse(BaseModel):
    results: List[SearchResultItem]