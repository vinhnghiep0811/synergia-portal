from fastapi import APIRouter, status
from app.api.papers import router as papers_router

router = APIRouter()

@router.get("/health",
            status_code=status.HTTP_200_OK,
    summary="Kiểm tra trạng thái hoạt động của API",
    description="""
API dùng để kiểm tra backend còn hoạt động hay không.

### Mục đích
- Kiểm tra service đã chạy chưa
- Dùng cho monitoring, load balancer, devops hoặc FE ping thử backend
- Thường dùng để test nhanh sau khi deploy

### Kết quả
Nếu hệ thống hoạt động bình thường, API trả về trạng thái `ok`.
""",
    response_description="Trạng thái hoạt động của hệ thống",
    responses={
        200: {
            "description": "Backend hoạt động bình thường",
            "content": {
                "application/json": {
                    "example": {
                        "status": "ok"
                    }
                }
            },
        }
    },
    tags=["system"],
)
def health():
    return {"status": "ok"}

router.include_router(papers_router)