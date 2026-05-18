from uuid import UUID
from io import BytesIO
from fastapi import APIRouter, Depends, File, Query, UploadFile, status, HTTPException
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.paper import (
    PaperDetailResponse,
    PaperListItemResponse,
    PaperUploadResponse,
)
from app.schemas.publish import (
    PublishMetadataPreviewResponse,
    PublishMetadataUpdateRequest,
    PublishVersionCreateResponse,
)
from app.services.paper_service import PaperService
from app.services.publish_service import PublishService
from app.services.storage_service import StorageService

router = APIRouter(prefix="/papers", tags=["papers"])


def _raise_publish_http_error(error: ValueError) -> None:
    detail = str(error)

    if detail == "Paper not found.":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

    if (
        "has not been linked" in detail
        or "No extraction result available" in detail
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


@router.post("/upload", response_model=PaperUploadResponse,
             status_code=status.HTTP_201_CREATED,
    summary="Upload file PDF bài báo",
    description="""
API dùng để upload một file PDF bài báo lên hệ thống.

### Chức năng
- Nhận file PDF từ client
- Lưu file vào storage
- Tạo bản ghi paper trong database
- Trả về thông tin cơ bản của paper vừa upload

### Lưu ý
- Chỉ chấp nhận file PDF
- Field upload phải có tên là `file`
""",
    response_description="Thông tin bài báo sau khi upload thành công",
    responses={
        201: {
            "description": "Upload PDF thành công",
            "content": {
                "application/json": {
                    "example": {
                        "id": "8d42b62d-2591-4d54-8efa-e9e3ab06a262",
                        "original_filename": "Week1DB_Schema.drawio.pdf",
                        "storage_path": "s3://papers/papers/8d42b62d-2591-4d54-8efa-e9e3ab06a262.pdf",
                        "mime_type": "application/pdf",
                        "file_size_bytes": 108810,
                        "file_hash_sha256": "d764f7be75379fc5cbd32a6f36db7b38ed4e33eb82978aab9b29742cd0ed6c06",
                        "status": "pending",
                        "upload_source": "portal",
                        "created_at": "2026-03-11T12:44:38.541317Z"
                    }
                }
            },
        },
        400: {
            "description": "File không hợp lệ hoặc không phải PDF",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Only PDF files are allowed"
                    }
                }
            },
        },
        500: {
            "description": "Lỗi hệ thống khi upload file",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Internal server error"
                    }
                }
            },
        },
    },
)
async def upload_paper(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PaperService(db)
    paper = await service.upload_pdf(
        file=file,
        uploader_id=current_user.email,   # giữ theo kiểu hiện tại của PaperRecord
        actor_user_id=current_user.id,    # dùng cho activity log
    )
    return paper


@router.get("", response_model=list[PaperListItemResponse],
            summary="Lấy danh sách bài báo",
    description="""
API dùng để lấy danh sách các bài báo đã được upload lên hệ thống.

### Chức năng
- Hỗ trợ phân trang qua `skip` và `limit`
- Trả về danh sách paper ngắn gọn để hiển thị ngoài màn hình list

### Dùng cho FE
FE gọi endpoint này để:
- Hiển thị danh sách paper
- Phân trang danh sách
- Render bảng / card danh sách bài báo
""",
    response_description="Danh sách bài báo",
    responses={
        200: {
            "description": "Lấy danh sách bài báo thành công",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": "8d42b62d-2591-4d54-8efa-e9e3ab06a262",
                            "original_filename": "Week1DB_Schema.drawio.pdf",
                            "status": "pending",
                            "mime_type": "application/pdf",
                            "file_size_bytes": 108810,
                            "created_at": "2026-03-11T12:44:38.541317Z",
                            "updated_at": "2026-03-11T12:44:38.541317Z"
                        },
                        {
                            "id": "7d36df8b-ceb7-4733-805b-2f6e020902dd",
                            "original_filename": "CO3043-4000.pdf",
                            "status": "pending",
                            "mime_type": "application/pdf",
                            "file_size_bytes": 430497,
                            "created_at": "2026-03-10T16:59:10.774180Z",
                            "updated_at": "2026-03-10T16:59:10.774180Z"
                        },
                    ]
                }
            },
        },
        500: {
            "description": "Lỗi hệ thống khi lấy danh sách bài báo",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Internal server error"
                    }
                }
            },
        },
    },
)
def list_papers(
    skip: int = Query(0, ge=0, description="Số lượng bản ghi bỏ qua, dùng cho phân trang"),
    limit: int = Query(20, ge=1, le=100, description="Số lượng bản ghi tối đa trả về trong một lần gọi"),
    db: Session = Depends(get_db),
):
    service = PaperService(db)
    return service.list_papers(skip=skip, limit=limit)


@router.get("/{paper_id}", response_model=PaperDetailResponse,
            summary="Lấy chi tiết một bài báo",
    description="""
API dùng để lấy thông tin chi tiết của một bài báo theo `paper_id`.

### Chức năng
- Lấy metadata chi tiết của paper
- Phục vụ màn hình detail bên FE

### Dùng cho FE
FE gọi endpoint này khi:
- Người dùng click vào một paper trong danh sách
- Cần hiển thị trang chi tiết bài báo
""",
    response_description="Thông tin chi tiết bài báo",
    responses={
        200: {
            "description": "Lấy chi tiết bài báo thành công",
            "content": {
                "application/json": {
                    "example": {
                        "id": "907c3e6a-cf17-4dfe-b030-fe1914218e28",
                        "canonical_document_id": None,
                        "uploader_id": None,
                        "original_filename": "Week1DB_Schema.drawio.pdf",
                        "storage_path": "s3://papers/papers/907c3e6a-cf17-4dfe-b030-fe1914218e28.pdf",
                        "mime_type": "application/pdf",
                        "file_size_bytes": 108810,
                        "file_hash_sha256": "d764f7be75379fc5cbd32a6f36db7b38ed4e33eb82978aab9b29742cd0ed6c06",
                        "upload_source": "portal",
                        "status": "pending",
                        "parse_status": None,
                        "parse_error": None,
                        "extracted_text_preview": None,
                        "detected_doi": None,
                        "detected_fingerprint": None,
                        "detected_title": None,
                        "created_at": "2026-03-10T16:44:51.886708Z",
                        "updated_at": "2026-03-10T16:44:51.886708Z"
                    }
                }
            },
        },
        404: {
            "description": "Không tìm thấy bài báo với paper_id tương ứng",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Paper not found"
                    }
                }
            },
        },
        422: {
            "description": "paper_id không đúng định dạng UUID",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["path", "paper_id"],
                                "msg": "value is not a valid uuid",
                                "type": "type_error.uuid"
                            }
                        ]
                    }
                }
            },
        },
        500: {
            "description": "Lỗi hệ thống khi lấy chi tiết bài báo",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Internal server error"
                    }
                }
            },
        },
    },
)
def get_paper_detail(
    paper_id: UUID,
    db: Session = Depends(get_db),
):
    service = PaperService(db)
    return service.get_paper_detail(paper_id)


@router.get(
    "/{paper_id}/publish-metadata",
    response_model=PublishMetadataPreviewResponse,
    summary="Lay metadata review truoc publish",
)
def get_publish_metadata_preview(
    paper_id: UUID,
    db: Session = Depends(get_db),
):
    service = PublishService(db)

    try:
        return service.get_publish_preview(paper_id)
    except ValueError as error:
        _raise_publish_http_error(error)


@router.patch(
    "/{paper_id}/publish-metadata",
    response_model=PublishMetadataPreviewResponse,
    summary="Luu metadata da chinh sua cho publish",
)
def update_publish_metadata_draft(
    paper_id: UUID,
    payload: PublishMetadataUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PublishService(db)

    try:
        return service.update_publish_draft(
            paper_id,
            payload,
            actor_user_id=current_user.id,
            actor_email=current_user.email,
        )
    except ValueError as error:
        _raise_publish_http_error(error)


@router.post(
    "/{paper_id}/publish",
    response_model=PublishVersionCreateResponse,
    summary="Publish paper va tao snapshot version",
)
def publish_paper(
    paper_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = PublishService(db)

    try:
        return service.publish(
            paper_id,
            published_by=current_user.email,
            actor_user_id=current_user.id,
        )
    except ValueError as error:
        _raise_publish_http_error(error)

@router.get("/{paper_id}/file-url",
    summary="Lấy URL truy cập file PDF",
    description="""
        API trả về presigned URL để client có thể mở hoặc tải file PDF.

        ### Chức năng
        - Lấy storage_path từ database
        - Generate presigned URL từ MinIO
        - Trả về URL để FE mở file

        ### Lưu ý
        - URL có thời hạn (mặc định 10 phút)
        """,
        )
def get_paper_file_url(
    paper_id: UUID,
    db: Session = Depends(get_db),
):
    service = PaperService(db)
    paper = service.get_paper_detail(paper_id)

    storage_service = StorageService()
    file_url = storage_service.generate_presigned_get_url(
        paper.storage_path
    )

    return {
        "file_url": file_url
    }

@router.get(
    "/{paper_id}/file",
    response_class=StreamingResponse,
    summary="Xem file PDF của bài báo",
    description="""
API trả trực tiếp file PDF để client có thể mở lại trong browser.

### Chức năng
- Lấy storage_path từ database
- Đọc file từ MinIO
- Trả file PDF về cho client

### Dùng cho FE
FE có thể mở endpoint này bằng tab mới để xem PDF.
""",
    responses={
        200: {
            "description": "Trả file PDF thành công",
        },
        404: {
            "description": "Không tìm thấy bài báo với paper_id tương ứng",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Paper not found"
                    }
                }
            },
        },
        500: {
            "description": "Không thể đọc file từ storage",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Cannot load file from storage"
                    }
                }
            },
        },
    },
)
def get_paper_file(
    paper_id: UUID,
    db: Session = Depends(get_db),
):
    service = PaperService(db)
    paper = service.get_paper_detail(paper_id)

    storage_service = StorageService()

    try:
        file_bytes = storage_service.download_by_storage_path(paper.storage_path)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Cannot load file from storage: {str(e)}",
        )

    return StreamingResponse(
        BytesIO(file_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{paper.original_filename}"'
        },
    )
