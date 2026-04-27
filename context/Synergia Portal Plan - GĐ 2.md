# Synergia Portal Plan - Giai đoạn 2

## Mục tiêu

Mục tiêu tổng quát của giai đoạn 2 là hiện thực hóa một hệ thống quản lý và chia sẻ tài liệu học thuật tập trung cho nhóm nghiên cứu nhỏ, vận hành được trên hạ tầng nội bộ (VM on-prem), trong đó mỗi tài liệu sau khi được đưa vào hệ thống sẽ được chuẩn hóa metadata đáng tin cậy, được trích xuất thêm các metadata chuyên biệt có ý nghĩa nghiên cứu bằng LLM nhưng theo cơ chế có kiểm chứng dựa trên bằng chứng trích trực tiếp từ PDF, và chỉ được công bố tới nhóm sau khi người dùng xác nhận.

Hệ thống đồng thời phải chứng minh được tính thực tế bằng cách tối ưu chi phí suy luận thông qua việc nhận diện “canonical document” để tránh gọi lại LLM cho tài liệu trùng.

### Các mục tiêu cụ thể

- Thứ nhất:
  - Hệ thống phải cung cấp luồng nhập liệu (ingestion) tối thiểu từ web portal
  - Có khả năng:
    - upload PDF
    - lưu trữ file
    - theo dõi trạng thái xử lý
    - trang danh sách và trang chi tiết
  - Telegram bot hoặc extension chỉ là phụ trợ

- Thứ hai:
  - Chuẩn hóa metadata nền tảng:
    - parse PDF để phát hiện DOI và title
    - gọi Semantic Scholar để lấy:
      - tác giả
      - năm
      - venue
      - abstract
  - Không dùng LLM để điền metadata nền tảng

- Thứ ba:
  - Trích xuất metadata chuyên biệt:
    - bài toán nghiên cứu
    - phương pháp
    - đóng góp
    - hạn chế / giả định
    - thiết lập đánh giá
  - Mỗi trường bắt buộc có evidence snippet
  - Không có evidence → để trống

- Thứ tư:
  - Human-in-the-loop:
    - Draft → Published
    - user xác nhận trước khi publish
    - Telegram chỉ gửi sau khi publish

- Thứ năm:
  - Canonical caching:
    - lưu kết quả LLM theo canonical key
    - tránh gọi lại LLM cho tài liệu trùng

- Thứ sáu:
  - Phần học thuật:
    - mô hình hóa “reference/citation importance”
    - có đánh giá định lượng + phân tích lỗi

---

## Phạm vi đề tài

- Chỉ triển khai:
  - single workspace
- Không triển khai:
  - multi-workspace
  - hệ thống phân quyền phức tạp

Lý do:
- giảm độ phức tạp UI
- tránh vấn đề đồng bộ dữ liệu

Tuy nhiên:
- vẫn thiết kế Canonical Document để mở rộng sau

Hạn chế:
- chỉ xử lý PDF text-based
- PDF scan:
  - có thể fail
  - đánh dấu “không trích xuất được”
- OCR là hướng tương lai

Không làm:
- recommendation nâng cao
- learning path
- citation graph lớn

Chỉ:
- hiển thị liên kết cơ bản

---

## Luồng xử lý nghiệp vụ

### Bước 1: Ingestion
- kiểm tra file:
  - định dạng
  - kích thước
- đánh giá sơ bộ
- lưu file
- tạo PaperRecord (pending)

### Bước 2: Parsing
- dùng pdfplumber:
  - extract text
- nhận diện DOI bằng regex
- heuristic title
- tạo fingerprint

### Bước 3: Canonical Document
- nếu có DOI → canonical key = DOI
- nếu không → fingerprint

### Bước 4: Duplicate detection
- nếu trùng:
  - đánh dấu duplicate
  - hoặc map cùng canonical

### Bước 5: Metadata chuẩn hóa
- gọi Semantic Scholar:
  - theo DOI hoặc title
- lấy:
  - authors
  - year
  - venue
  - abstract

### Bước 6: LLM extraction
- chỉ chạy khi:
  - chưa có kết quả
- bắt buộc:
  - có evidence
- extract:
  - problem
  - method
  - contributions
  - limitations
  - evaluation

- lưu:
  - ExtractionRun
  - kèm evidence

- nếu không có evidence:
  - để trống
  - không suy đoán

### Bước 7: Draft → Publish
- user:
  - chỉnh sửa
  - thêm tag
- publish:
  - mới coi là dữ liệu sạch
- Telegram:
  - chỉ notify sau publish

---

## Metadata chuyên biệt + đảm bảo đúng

### Các trường:
- bài toán nghiên cứu
- phương pháp
- đóng góp
- hạn chế
- evaluation

### Nguyên tắc:
- mỗi field phải có evidence snippet
- lưu vị trí:
  - trang
  - section
- UI:
  - hiển thị evidence

### Metadata nền tảng:
- không dùng LLM
- chỉ từ:
  - parse
  - Semantic Scholar

---

## Canonical caching

- canonical key:
  - DOI (ưu tiên)
  - fingerprint (fallback)

- lưu:
  - ExtractionRun

- reuse:
  - nếu đã có extraction đạt chuẩn
  - không gọi lại LLM

---

## Công nghệ

### Frontend
- React
- Next.js hoặc Vite

### Backend
- Python + FastAPI (khuyến nghị)
- hoặc Node/NestJS

### Database
- PostgreSQL
- pgvector (optional)

### Storage
- MinIO
- hoặc local + backup

### Queue
- Redis + Celery / RQ / BullMQ

### LLM
- API:
  - Ollama
  - Gemini

### Metadata
- Semantic Scholar API

### Parsing
- pdfplumber
- regex DOI

---

## Kế hoạch thực hiện

### Tuần 1
- setup VM
- Docker Compose
- schema DB

### Tuần 2
- upload PDF
- list + detail

### Tuần 3
- parsing
- DOI
- fingerprint
- duplicate detection

### Tuần 4
- Semantic Scholar
- mapping canonical

### Tuần 5
- LLM extraction
- evidence
- caching

### Tuần 6
- Draft → Publish
- Telegram

### Tuần 7
- citation importance

### Tuần 8
- UI + error analysis

### Tuần 9
- PoC + metrics

### Tuần 10
- report + demo