# Định vị lại đề tài

## 2. Định vị lại đề tài

### 2.1. Không nên trình bày như

Sinh viên không nên trình bày đề tài theo hướng:

- Chỉ là một website upload, lưu trữ và tìm kiếm PDF
- Bản sao của Zotero, Mendeley, Google Drive
- Hệ thống “có dùng LLM” để tóm tắt

→ Hội đồng sẽ đánh giá:
- thiếu chiều sâu
- chỉ tích hợp công cụ

---

### 2.2. Nên trình bày như

Một giải pháp:

- quản lý tri thức học thuật
- chuẩn hóa metadata
- hỗ trợ truy hồi tri thức

### Bottleneck thực tế

- Paper rải rác
- Chia sẻ thủ công
- Metadata không đồng nhất
- Khó tìm lại
- Tri thức không kế thừa

### Giá trị

- Biến tài liệu → tri thức có cấu trúc
- Truy hồi nhanh hơn
- Giảm chi phí phối hợp

---

## 3. Định hướng trình bày

### 3.1. Vấn đề

Tri thức phân tán ở:
- máy cá nhân
- Google Drive
- Telegram
- email
- Zotero

Hệ quả:
- khó tìm lại
- khó chia sẻ
- khó theo dõi liên hệ
- khó tích lũy tri thức

---

### 3.2. Đóng góp

1. Chuẩn hóa pipeline ingestion
2. Tổ chức tri thức nhiều lớp:
   - file
   - metadata
   - semantic
   - citation
3. Semantic search + Q&A
4. Nền tảng cho AI reasoning

---

### 3.3. Thesis Statement

Đề tài giải quyết:

- bottleneck quản lý tri thức
- bottleneck truy hồi tri thức

Vấn đề:
- tài liệu phân tán
- chia sẻ thủ công
- khó tái sử dụng

Giải pháp:
- chuẩn hóa pipeline
- semantic search
- Q&A có grounding
- citation graph

---

## 4. Liên hệ CAI

### 4.1. Knowledge ingestion
- pipeline tiếp nhận tài liệu

### 4.2. Structured memory
- metadata
- embedding
- citation graph
- log

### 4.3. Grounded retrieval
- retrieve + LLM
- có nguồn

### 4.4. Human-in-the-loop
- user xác nhận metadata

### 4.5. Experimental platform
- testbed cho:
  - metadata extraction
  - relatedness
  - Q&A
  - recommendation

---

## 5. Scope

### 5.1. Core

A. Flow tiếp nhận:
- upload web hoặc Telegram

B. Chuẩn hóa:
- validate
- chống trùng
- metadata

C. Search:
- keyword
- semantic

D. Detail:
- metadata
- abstract
- related papers

E. AI feature:
- chọn 1:
  - semantic search
  - Q&A
  - recommendation

---

### 5.2. Extended

- Chrome extension
- multi-space
- cloud backup
- fine-tuning
- graph lớn

---

### 5.3. Ưu tiên

1. Upload
2. Metadata
3. Search
4. Detail
5. AI feature
6. Citation graph nhỏ

---

## 6. Mô hình hóa

### 6.1. Business

- Input:
  - document
  - query

- Process:
  - parse
  - extract
  - store
  - retrieve

- Output:
  - knowledge

---

### 6.2. Data

- User
- Document
- Metadata
- Embedding
- Citation
- Query
- Feedback

---

### 6.3. AI Pipeline

- parsing
- extraction
- embedding
- indexing
- retrieval
- LLM

---

### 6.4. Evaluation

- input
- ground truth
- metric
- baseline

---

## 7. Công việc cần làm

- chốt bài toán
- chốt scope
- thiết kế kiến trúc
- thiết kế data
- dataset
- evaluation
- demo

---

## 8. Đánh giá

### Metadata
- title
- authors
- year
- venue

### Search
- Precision@K
- Recall@K
- NDCG

### Q&A
- correctness
- usefulness
- grounding

### System
- latency
- success rate

---

## 9. Dataset

### Metadata
- 50–100 papers
- ground truth sạch

### Search
- query + label

### Q&A
- question + answer + source

### Citation
- 20–30 papers cluster

---

## 10. Demo

### Nguyên tắc
- ngắn
- ổn định
- đúng pain point

---

### Demo 1: Upload
- upload → extract → save

### Demo 2: Search
- query → retrieve → open

### Demo 3: Q&A
- question → answer + source

### Demo 4: Citation graph
- paper → related

---

### Ưu tiên

- Upload → Metadata → Search
- hoặc
- Search → Q&A