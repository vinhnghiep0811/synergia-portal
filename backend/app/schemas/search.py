from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID

class SearchRequest(BaseModel):
    query: str = Field(..., description="Câu hỏi hoặc từ khóa tìm kiếm")
    top_k: int = Field(5, ge=1, le=50, description="Số lượng kết quả tối đa trả về")

class SearchResultItem(BaseModel):
    chunk_id: UUID = Field(..., description="ID của đoạn text (chunk)")
    canonical_document_id: UUID = Field(..., description="ID của tài liệu chứa đoạn text này")
    title: Optional[str] = Field(None, description="Tiêu đề của tài liệu")
    content: str = Field(..., description="Nội dung của đoạn text")
    similarity_score: float = Field(..., description="Độ tương đồng (cosine similarity)")

class SearchResponse(BaseModel):
    results: List[SearchResultItem]
