# Citation Graph — Thiết kế & Công thức Tính Điểm

## Mục tiêu của bước Citation Graph

1. Tạo quan hệ có hướng A → B giữa các tài liệu trong kho nội bộ.
2. Tính một điểm `citation_score` trong khoảng [0, 1] cho mỗi cạnh.
3. Giải thích được điểm bằng evidence cụ thể (đoạn văn ngữ cảnh).
4. Cho phép tái tính điểm khi đổi công thức mà vẫn truy vết được lịch sử.

---

## Cập nhật trạng thái triển khai hiện tại (27-04-2026)

1. API citation graph đã chạy với các endpoint chính:
   1. `POST /citation-graph/runs/score`
   2. `POST /citation-graph/runs/score/by-paper/{paper_id}`
   3. `GET /citation-graph/network`
   4. `GET /citation-graph/edges/{edge_id}/mentions`
2. Worker có đủ 3 chế độ chấm điểm:
   1. global
   2. theo 1 canonical
   3. theo danh sách source canonical ids
3. UI `/citation-graph` hiện dùng refresh thủ công (nút "Làm mới mạng"), đã bỏ auto-refresh.
4. Graph hiện hiển thị cả tài liệu không có cạnh (isolated node), nên người dùng vẫn thấy đầy đủ node trong phạm vi run.
5. Danh sách cạnh ở panel "Thông tin mạng" được đặt trong khung cuộn, không xổ tràn chiều dài trang.

---

## Trả lời nhanh: Upload 1 tài liệu thì chuyện gì xảy ra?

1. API upload tạo `paper_records` với trạng thái ban đầu `pending/uploaded`, sau đó enqueue parse job và đổi sang `pending/queued`.
2. Worker `pdf_parse` đọc PDF, trích text, nhận diện DOI/title/fingerprint, tạo hoặc map `canonical_documents`, rồi đổi trạng thái paper sang `processing/parsed`.
3. Sau parse, hệ thống enqueue `semantic_scholar_enrich`.
4. Khi enrich xong, hệ thống thử enqueue `llm_extract` nếu đủ điều kiện.
5. `llm_extract` chạy xong sẽ enqueue `score_citation_graph_for_canonical`.
6. Worker citation đổi paper sang `processing/citation_scoring`, chạy scoring, rồi đổi sang `completed/citation_scored` nếu thành công.

### Vậy upload 1 tài liệu thì "chưa trích dẫn gì" đúng không?

1. Đúng trong trường hợp kho chỉ có đúng tài liệu đó: không có đích nội bộ để link, nên thường không sinh cạnh nội bộ (`citation_edges` rỗng cho tài liệu này).
2. Chưa hẳn đúng nếu kho đã có tài liệu khác: tài liệu mới có thể trích dẫn tài liệu cũ, khi link được thì sẽ có cạnh outgoing ngay trong lần scoring đó.
3. Dù không link được nội bộ, hệ thống vẫn có thể lưu mention unresolved ở `citation_mentions` với `target_canonical_id = null`, `is_internal = false` để audit.
4. Tài liệu mới gần như luôn chưa có incoming edge ở thời điểm vừa upload, vì chưa có tài liệu khác trích nó trong kho nội bộ.
5. Dù chưa có cạnh, node của tài liệu vẫn được hiển thị trên graph để người dùng có cái nhìn đầy đủ về tập tài liệu trong run.

---

## Điều kiện để có điểm citation nội bộ

1. Tài liệu nguồn phải có chunk retrievable và detect được anchor citation.
2. Entity linking phải map được mention tới canonical đích nội bộ (`target_canonical_id` khác null).
3. Mention phải là nội bộ (`is_internal = true`) thì mới được aggregate thành `citation_edges`.

---

## Cập nhật heuristic linking gần đây (27-04-2026)

1. Parser references đã xử lý được prefix markdown list (`- ...`, `* ...`), kể cả format `- [N]`.
2. Logic trích title reference đã tránh lỗi cắt rỗng khi năm nằm cuối theo format ACL/APA.
3. Ngưỡng author-year match được nới để tăng recall khi map reference:
   1. Ngưỡng map chính: 0.45
   2. Ngưỡng fallback mention: 0.55

---

## Phạm vi dữ liệu

1. Chỉ tính khi cả nguồn và đích đều map được vào canonical document nội bộ.
2. Trích dẫn ra ngoài kho có thể lưu riêng dạng unresolved, nhưng không vào điểm graph chính.

---

## Công việc triển khai (work packages)

1. Thiết kế schema và migration cho 3 bảng mới.
2. Viết job phát hiện citation mention từ chunk.
3. Viết bước entity linking mention → canonical document đích.
4. Tính feature cấp mention: similarity, section weight, intent, quality, link confidence.
5. Tính mention score và lưu citation_mentions.
6. Tổng hợp mention thành cạnh A → B, tính edge score và lưu citation_edges.
7. Lưu phiên chạy và trọng số vào citation_score_runs để audit.
8. Viết API đọc graph và top evidence cho UI.
9. Đánh giá định lượng và tinh chỉnh trọng số.

---

## Các bảng DB liên quan tới Citation (thực tế đang chạy)

### 1) citation_score_runs (bảng phiên chạy)

| Cột | Kiểu | Null | Ghi bởi | Tác dụng |
|---|---|---|---|---|
| id | UUID (PK) | Không | Service khi tạo run | Định danh phiên chấm điểm để audit/replay |
| algorithm_version | varchar(50), index | Không | API/worker truyền vào, default `citation-v1` | Tách kết quả theo phiên bản công thức |
| weights_json | JSONB | Không | Service ghi snapshot trọng số | Lưu đúng bộ trọng số đã dùng trong run |
| status | varchar(30), default `running`, index | Không | Service/worker | Vòng đời run: running, completed, failed |
| processed_mentions | int, default 0 | Không | Service | Tổng số mention đã xử lý trong run |
| processed_edges | int, default 0 | Không | Service | Tổng số edge nội bộ sinh ra trong run |
| started_at | timestamptz, default now() | Không | DB | Thời điểm bắt đầu |
| ended_at | timestamptz | Có | Service khi kết thúc/thất bại | Thời điểm kết thúc |
| error_log | text | Có | Service khi failed | Lưu lỗi tóm tắt để truy vết |

Ghi chú index: Index riêng cho `algorithm_version` và `status`.

### 2) citation_mentions (bảng mức mention)

| Cột | Kiểu | Null | Ghi bởi | Tác dụng |
|---|---|---|---|---|
| id | UUID (PK) | Không | Service | Định danh mention |
| run_id | UUID FK → citation_score_runs.id (CASCADE), index | Không | Service | Mention thuộc phiên chạy nào |
| source_canonical_id | UUID FK → canonical_documents.id (CASCADE), index | Không | Service | Tài liệu nguồn A chứa citation |
| target_canonical_id | UUID FK → canonical_documents.id (SET NULL), index | Có | Service | Tài liệu đích B nếu link được |
| source_chunk_id | UUID FK → document_chunks.id (SET NULL), index | Có | Service | Chunk gốc dùng làm evidence |
| source_section_id | UUID FK → document_sections.id (SET NULL), index | Có | Service | Section gốc dùng cho section weighting/diversity |
| anchor_text | varchar(255) | Có | Service | Mẫu anchor như `[12]`, `(Author, 2020)`, DOI |
| context_snippet | text | Không | Service | 1-3 câu quanh anchor, dùng làm evidence chính |
| page_from | int | Có | Service từ chunk | Trang bắt đầu evidence |
| page_to | int | Có | Service từ chunk | Trang kết thúc evidence |
| section_type | varchar(50) | Có | Service từ chunk/section | Loại section để map trọng số |
| section_weight | numeric(5,4) | Không | Service tính | Điểm trọng số vị trí section |
| link_method | varchar(50) | Có | Service tính | Cách link: doi_exact/title_fuzzy/author_year/... |
| link_confidence | numeric(5,4) | Không | Service tính | Độ tin cậy link mention → target |
| semantic_similarity | numeric(5,4) | Không | Service tính | Độ tương đồng snippet với tài liệu đích |
| intent_label | varchar(50) | Không | Service suy luận | Nhãn mục đích citation |
| intent_score | numeric(5,4) | Không | Service map theo label | Điểm intent |
| chunk_quality | numeric(5,4) | Không | Service tính | Độ tốt của snippet/chunk |
| mention_score | numeric(5,4), index | Không | Service tính | Điểm cuối cùng ở cấp mention |
| is_internal | bool, default false | Không | Service gán | Có map được vào tài liệu nội bộ hay không |
| created_at | timestamptz, default now() | Không | DB | Audit thời gian tạo mention |

Ghi chú quan trọng:
1. Mention unresolved vẫn được lưu: `target_canonical_id = null`, `is_internal = false`.
2. Mention unresolved chỉ phục vụ audit/debug, không tham gia edge score nội bộ.

### 3) citation_edges (bảng mức cạnh A → B)

| Cột | Kiểu | Null | Ghi bởi | Tác dụng |
|---|---|---|---|---|
| id | UUID (PK) | Không | Service | Định danh cạnh |
| run_id | UUID FK → citation_score_runs.id (CASCADE), index | Không | Service | Cạnh thuộc phiên chạy nào |
| algorithm_version | varchar(50), index | Không | Service | Version công thức tại thời điểm tính cạnh |
| source_canonical_id | UUID FK → canonical_documents.id (CASCADE), index | Không | Service | Nút nguồn A |
| target_canonical_id | UUID FK → canonical_documents.id (CASCADE), index | Không | Service | Nút đích B |
| mention_count | int | Không | Service aggregate | Tổng mention nội bộ A nhắc B |
| top3_mean_score | numeric(5,4) | Không | Service aggregate | Trung bình 3 mention mạnh nhất |
| frequency_score | numeric(5,4) | Không | Service aggregate | Điểm theo tần suất mention |
| diversity_score | numeric(5,4) | Không | Service aggregate | Điểm đa dạng section |
| intent_edge_score | numeric(5,4) | Không | Service aggregate | Điểm intent tổng hợp cấp cạnh |
| citation_score | numeric(5,4), index | Không | Service aggregate | Điểm cạnh cuối cùng trong [0,1] |
| score_band | varchar(20) | Có | Service | Nhãn low/medium/high |
| evidence_json | JSONB | Có | Service | Top evidence (anchor/snippet/page/section/score) để giải thích |
| updated_at | timestamptz, default now() | Không | DB/onupdate | Audit lần cập nhật cuối |

Ràng buộc thực tế trong DB:
1. Unique theo bộ `run_id + source_canonical_id + target_canonical_id`.
2. Không unique theo `algorithm_version` vì mỗi run đã gắn một `algorithm_version` riêng.

### 4) Các bảng đầu vào/đầu ra liên quan trực tiếp

1. `canonical_documents`:
   - `id`: khóa để làm node citation graph.
   - `title`, `abstract`, `doi`, `publication_year`, `authors_json`: đầu vào chính cho linking và similarity.
   - Quan hệ `citation_mentions_source`, `citation_mentions_target`, `citation_edges_outgoing`, `citation_edges_incoming`: phục vụ truy vấn graph theo node.
2. `document_chunks`:
   - `id`, `canonical_document_id`, `section_id`: truy vết mention về đúng tài liệu/chunk/section.
   - `content`: nơi detect anchor citation và trích context snippet.
   - `page_from`, `page_to`: nguồn dữ liệu trang cho evidence.
   - `section_type`, `is_retrievable`: dùng để lọc chunk và tính section weight.
3. `document_sections`:
   - `id`, `canonical_document_id`, `section_type`, `section_name`, `content`: dùng nhận diện reference section và diversity theo section.
   - `page_from`, `page_to`: hỗ trợ truy vết evidence.
4. `paper_records`:
   - `canonical_document_id`: map file upload → canonical node.
   - `processing_status`, `processing_stage`, `processing_error`: hiển thị tiến trình upload → parse → enrich → llm_extract → citation_scoring → citation_scored.

**Lưu ý vận hành bắt buộc:** Phải chạy migration tới head để có đủ 3 bảng citation, nếu không các endpoint đọc canonical có thể lỗi do ORM relationship eager-load vào bảng citation chưa tồn tại.

---

## Giải thích chi tiết từng dữ kiện đầu vào

| Dữ kiện | Có sẵn trong DB? | Ở đâu ra | Dùng để làm gì |
|---|---|---|---|
| context_snippet | Không có sẵn trực tiếp | Tính từ nội dung chunk bằng cách lấy câu quanh anchor citation | Là evidence chính, đầu vào cho semantic_similarity và intent |
| section_type | Có sẵn | Lấy từ document_chunks hoặc join document_sections | Xác định độ quan trọng vị trí citation |
| page | Có sẵn một phần | page_from, page_to của chunk/section | Truy vết evidence, phục vụ UI và audit |
| chunk quality | Không có sẵn trực tiếp | Tính từ độ dài, nhiễu OCR, độ rõ anchor, độ mạch lạc snippet | Giảm ảnh hưởng snippet kém chất lượng |
| loại section và ưu tiên cấu trúc | section có sẵn, ưu tiên phải tính | document_sections + bảng trọng số section | Tạo section_weight và diversity_score |
| title, abstract, doi | Có sẵn | canonical_documents | Linking mention → target và tính semantic similarity |
| problem, method, contributions | Có sẵn khi đã extraction | extraction_runs | Tăng chất lượng nhận diện intent (optional) |
| feature mention chi tiết | Không có sẵn | Tính và lưu vào citation_mentions | Dữ liệu trung gian để aggregate và debug |
| điểm graph tổng hợp | Không có sẵn | Aggregate từ citation_mentions | Kết quả cuối cùng lưu citation_edges |

---

## Context snippet là gì, có sẵn hay phải tính, và tác dụng

1. Context snippet là 1-3 câu bao quanh citation trong chunk nguồn.
2. Nó không phải cột có sẵn; phải tính từ `content` của chunk.
3. Cách lấy phổ biến:
   1. Detect anchor citation trong chunk.
   2. Sentence split.
   3. Lấy câu chứa anchor + câu trước/sau.
4. Nó là evidence trực tiếp để:
   1. Tính semantic similarity.
   2. Tính intent.
   3. Giải thích vì sao mention score cao hay thấp.

---

## Bộ công thức đề xuất

Bộ này gồm 6 công thức: 4 công thức chính và 2 công thức chuẩn hóa hỗ trợ.

---

### Công thức 1: Link Confidence `[R1, R2, R3]`

$$
linkConf = 0.70 \cdot doiMatch + 0.20 \cdot titleMatch + 0.10 \cdot authorYearMatch
$$

Giá trị:
1. `doiMatch`: 0 hoặc 1.
2. `titleMatch`: [0, 1].
3. `authorYearMatch`: [0, 1].
4. `linkConf`: [0, 1].

Lý do trọng số:
1. **DOI exact match** là tín hiệu tin cậy nhất nên `0.70` — DOI matching đạt F-score ~95.4% trong pipeline GROBID + biblio-glutton `[R3]`.
2. **Title fuzzy match** hữu ích nhưng dễ nhầm hơn DOI nên `0.20` — phương pháp này được Crossref dùng chính thức trong hệ thống Reference Matching `[R2]`.
3. **Author-Year** chỉ bổ trợ nên `0.10` — đây là fallback khi thiếu DOI và title, xử lý tốt khi author bị viết tắt hoặc đảo thứ tự `[R1]`.

> ⚠️ Các trọng số cụ thể `0.70 / 0.20 / 0.10` là heuristic thiết kế; chưa có paper nào publish bộ số này. Nên tune lại theo dữ liệu thực nghiệm.

---

### Công thức 2: Chunk Quality

$$
quality = 0.45 \cdot lenScore + 0.30 \cdot cleanScore + 0.15 \cdot anchorClarity + 0.10 \cdot coherenceScore
$$

Giá trị:
1. `lenScore`: độ đủ dài ngữ cảnh.
2. `cleanScore`: mức sạch văn bản.
3. `anchorClarity`: độ rõ ràng của anchor.
4. `coherenceScore`: độ mạch lạc cục bộ của snippet.
5. `quality`: [0, 1].

Lý do trọng số:
1. Đủ ngữ cảnh vẫn quan trọng nhất nên `0.45`.
2. Độ sạch văn bản ảnh hưởng mạnh thứ hai nên `0.30`.
3. Anchor clarity hỗ trợ nhưng không quyết định hoàn toàn nên `0.15`.
4. Bổ sung coherence `0.10` để phạt snippet bị cắt cụt hoặc thiếu cấu trúc câu.

> ⚠️ Công thức Chunk Quality là thiết kế nội bộ; các thành phần (length, cleanliness, anchor clarity) phổ biến trong information retrieval nhưng không có paper cụ thể nào định nghĩa chính xác công thức này.

---

### Công thức 3: Mention Score `[R4, R5, R6]`

$$
m = \mathrm{clip}_{[0,1]}\left(0.35 \cdot sim + 0.30 \cdot intent + 0.25 \cdot sec + 0.10 \cdot quality\right)\cdot linkConf
$$

Giá trị:
1. `sim`: semantic similarity [0,1].
2. `intent`: intent score [0,1].
3. `sec`: section weight [0,1].
4. `quality`: từ công thức 2.
5. `linkConf`: từ công thức 1.
6. `m`: mention score [0,1].

Lý do trọng số:
1. `sim = 0.35` để giảm bias lexical similarity thuần túy — semantic similarity giữa context snippet và tài liệu đích là tín hiệu nội dung cốt lõi `[R4]`.
2. `intent = 0.30` để tăng vai trò ngữ nghĩa citation — intent classification (use_method, compare, background...) được nghiên cứu trong SciCite và ACL-ARC `[R5]`.
3. `sec = 0.25` vì vị trí section là tín hiệu cấu trúc mạnh — citation trong Methods hay Results có giá trị khác với citation trong Introduction `[R6]`.
4. `quality = 0.10` là lớp vệ sinh dữ liệu.
5. Nhân `linkConf` để "phạt cứng" các link không chắc `[R1]`.

---

### Công thức 4: Frequency Score `[R7]`

$$
freq = \min\left(1,\frac{\ln(1+n)}{\ln(11)}\right)
$$

Giá trị:
1. `n`: số mention giữa A và B.
2. `freq`: [0, 1].

Lý do:
1. Dùng log để tránh trường hợp spam mention làm điểm tăng tuyến tính vô hạn — logarithm của citation count là kỹ thuật chuẩn trong bibliometrics để xử lý phân phối lệch `[R7]`.
2. Sau khoảng 10 mention thì lợi ích thêm giảm dần.

> ⚠️ Hằng số chuẩn hóa `ln(11)` (saturation tại n=10) là quyết định thiết kế. Nên căn chỉnh theo phân phối mention thực tế của kho tài liệu.

---

### Công thức 5: Diversity Score `[R8]`

$$
div = \min\left(1,\frac{k}{3}\right)
$$

Giá trị:
1. `k`: số section high-weight khác nhau có mention, chỉ tính trong tập `{method, evaluation, results, discussion, conclusion}`.
2. `div`: [0, 1].

Lý do:
1. Citation xuất hiện đa section trọng yếu đáng tin hơn xuất hiện một chỗ — dựa trên nguyên lý Rao-Stirling Diversity Index đo sự phân bố trích dẫn qua nhiều nhóm `[R8]`.
2. Dùng mẫu số 3 để phù hợp hơn với paper ngắn hoặc cấu trúc section không quá sâu.

> ⚠️ Công thức `min(1, k/3)` là rút gọn thực dụng so với Rao-Stirling đầy đủ.

---

### Công thức 6: Edge Score `[R4, R6, R7, R8]`

$$
S_{A \to B} = \mathrm{clip}_{[0,1]}\left(0.60 \cdot \overline{m}_{top3} + 0.20 \cdot freq + 0.15 \cdot div + 0.05 \cdot intentEdge\right)
$$

Giá trị:
1. $\overline{m}_{top3}$: trung bình top 3 mention score.
2. `freq`: từ công thức 4.
3. `div`: từ công thức 5.
4. `intentEdge`: trung bình intent của các mention mạnh.
5. `S`: citation score [0, 1].

Lý do trọng số:
1. `0.60` cho `top3_mean` để ưu tiên chất lượng evidence mạnh — pattern "top-k aggregation" phổ biến trong citation recommendation `[R4]`.
2. `0.20` cho frequency vì tần suất có ý nghĩa nhưng không nên lấn át chất lượng `[R7]`.
3. `0.15` cho diversity để thưởng citation có mặt ở nhiều



## Vì sao chọn các trọng số như 0.5, 0.2 kiểu này

1. Đây là bộ khởi tạo theo nguyên tắc cân bằng giữa tín hiệu nội dung và tín hiệu cấu trúc.
2. Nhóm tín hiệu độ tin cậy cao (doiMatch, top mention) vẫn được đặt trọng số lớn.
3. Semantic similarity được hạ nhẹ để giảm lệch theo từ vựng bề mặt.
4. Intent và section được tăng vai trò vì phản ánh mục đích và vị trí citation tốt hơn.
5. Dùng log và clip để giữ điểm ổn định, tránh bùng nổ do ngoại lệ.
6. Bộ trọng số này dễ giải thích với hội đồng và dễ tune theo dữ liệu thực nghiệm.

---

## Đầu ra cuối cùng bạn có được

1. Một citation graph nội bộ có trọng số rõ ràng.
2. Mỗi cạnh có evidence truy vết được.
3. Điểm có thể tái tính theo phiên bản thuật toán.
4. Có nền tảng tốt để làm semantic search mở rộng bằng graph hoặc ranking paper liên quan.

---






## Tài liệu tham khảo

> **Lưu ý về cách đọc phần này:** Mỗi nguồn cung cấp *động lực học thuật* (academic motivation) cho việc đưa một feature vào mô hình — tức là xác nhận feature đó có ý nghĩa trong bài toán citation analysis. Tuy nhiên, không nguồn nào đề xuất hay validate các *trọng số cụ thể*, *hằng số kỹ thuật*, hay *công thức aggregation* trong hệ thống. Toàn bộ phần đó là thiết kế heuristic nội bộ và cần được hiệu chỉnh bằng thực nghiệm.

---

### [R1] Wellner et al. 2004 — Citation Matching và Identity Uncertainty

| Trường | Nội dung |
|---|---|
| Tác giả | Wellner, B.; McCallum, A.; Peng, F.; Hay, M. |
| Tiêu đề | *An Integrated, Conditional Model of Information Extraction and Coreference with Application to Citation Graph Construction* |
| Nơi xuất bản | UAI 2004 (20th Conference on Uncertainty in Artificial Intelligence) |
| Năm | 2004 |
| URL | https://people.eecs.berkeley.edu/~russell/papers/nips02-citation.pdf |
| **Dùng ở đâu trong hệ thống** | Công thức 1 — động lực để đưa author/year vào như tín hiệu linking; Công thức 3 — nguyên lý xử lý uncertainty trong citation link |
| **Nội dung paper** | Paper trình bày mô hình xác suất có điều kiện tích hợp để giải quyết bài toán *identity uncertainty* trong citation matching: khi cùng một tài liệu được nhắc đến dưới nhiều dạng khác nhau do lỗi OCR, tên tác giả viết tắt, đảo thứ tự, thiếu metadata. Mô hình kết hợp nhiều feature metadata (author, title, year, venue) đồng thời thay vì xử lý riêng lẻ. |
| **Phần hỗ trợ hệ thống** | Cung cấp động lực học thuật cho việc sử dụng author và year như các tín hiệu liên kết citation. Hệ thống đơn giản hóa ý tưởng này thành tín hiệu `authorYearMatch` riêng biệt — đây là adaptation nội bộ, không phải pipeline của paper. |
| **Phần là heuristic nội bộ** | Trọng số 0.10 cho `authorYearMatch`; cấu trúc 3 tín hiệu riêng biệt (DOI → title → author-year); cơ chế nhân `linkConf` trực tiếp vào mention score. |

---

### [R2] Crossref Reference Matching Documentation

| Trường | Nội dung |
|---|---|
| Tác giả | Crossref (tổ chức) |
| Tiêu đề | *Reference Matching — Official Crossref Documentation* |
| Nơi xuất bản | crossref.org |
| Năm | 2019 (cập nhật liên tục) |
| URL | https://www.crossref.org/categories/reference-matching/ |
| **Dùng ở đâu trong hệ thống** | Công thức 1 — động lực để đưa `titleMatch` vào như tín hiệu linking khi thiếu DOI |
| **Nội dung tài liệu** | Crossref mô tả hệ thống reference matching chính thức, trong đó title fuzzy matching được dùng như phương pháp chính khi không có DOI. Xác nhận đây là phương pháp production-proven ở quy mô hàng trăm triệu record, đồng thời thừa nhận tỷ lệ false positive cao hơn DOI matching. |
| **Phần hỗ trợ hệ thống** | Cung cấp động lực học thuật và thực tiễn cho việc dùng title matching như tín hiệu linking thứ hai. |
| **Phần là heuristic nội bộ** | Trọng số 0.20 cho `titleMatch`. |

---

### [R3] Nicholson et al. 2021 — scite: Smart Citation Index

| Trường | Nội dung |
|---|---|
| Tác giả | Nicholson, J.M.; Mordaunt, M.; Lopez, P.; Bhatt, S.; Lazarovici, M.; Mons, B.; Shankar, K. |
| Tiêu đề | *scite: A smart citation index that displays the context of citations and classifies their intent using deep learning* |
| Nơi xuất bản | Quantitative Science Studies (QSS), MIT Press |
| Năm | 2021 |
| URL | https://direct.mit.edu/qss/article/2/3/882/102990 |
| **Dùng ở đâu trong hệ thống** | Công thức 1 — động lực để đặt `doiMatch` là tín hiệu đáng tin cậy nhất |
| **Nội dung paper** | Paper mô tả kiến trúc của hệ thống scite — một citation index quy mô lớn xử lý hàng trăm triệu citation contexts. Hệ thống sử dụng GROBID để extract references từ PDF, kết hợp Crossref API và biblio-glutton để DOI matching, và deep learning để phân loại citation intent (supporting, contradicting, mentioning). |
| **Phần hỗ trợ hệ thống** | Xác nhận DOI matching là tín hiệu linking chính trong hệ thống production quy mô lớn, cung cấp động lực để đặt `doiMatch` ở vị trí ưu tiên cao nhất. |
| **Phần là heuristic nội bộ** | Trọng số 0.70 cho `doiMatch`. |
| ⚠️ **Lưu ý** | Các phiên bản tài liệu trước có trích dẫn "F-score ~95.4% cho DOI matching" — con số này **đã được xóa** vì chưa xác minh được xuất xứ chính xác từ bảng số liệu cụ thể nào trong paper. Không nên dùng con số này trong tài liệu chính thức cho đến khi kiểm chứng lại. |

---

### [R4] Valenzuela et al. 2015 — Identifying Meaningful Citations

| Trường | Nội dung |
|---|---|
| Tác giả | Valenzuela, M.; Ha, V.; Etzioni, O. |
| Tiêu đề | *Identifying Meaningful Citations* |
| Nơi xuất bản | AAAI Workshop on Scholarly Big Data |
| Năm | 2015 |
| URL | https://www.semanticscholar.org/paper/Identifying-Meaningful-Citations-Valenzuela-Ha/1c7d6c495f1c7dc7e63b89edcae75fe8a0bbeb6c |
| **Dùng ở đâu trong hệ thống** | Công thức 3 (Mention Score) — động lực cho bộ feature (similarity, section, frequency); Bảng section_weight — thứ tự ưu tiên section |
| **Nội dung paper** | Paper nghiên cứu bài toán phân biệt "meaningful citation" với "incidental citation". Tác giả huấn luyện binary classifier với các feature: **(1) semantic similarity** giữa context và tài liệu đích, **(2) citation count** của tài liệu đích, **(3) section location** (Methods/Results vs Introduction), **(4) position trong bài**. Đây là paper trực tiếp nhất với bài toán hệ thống đang giải quyết. |
| **Phần hỗ trợ hệ thống** | Cung cấp động lực học thuật cho việc đưa semantic similarity, section location, và frequency vào như các feature đánh giá mức độ quan trọng của citation. Xác nhận thứ tự ưu tiên section: Methods/Results quan trọng hơn Introduction. |
| **Phần là heuristic nội bộ** | Mọi trọng số (0.35, 0.25, v.v.); bảng section_weight với giá trị số cụ thể; cơ chế top-3 aggregation trong Công thức 6. |

---

### [R5] Cohan et al. 2019 — SciCite: Citation Intent Classification

| Trường | Nội dung |
|---|---|
| Tác giả | Cohan, A.; Ammar, W.; van Zuylen, M.; Cady, F. |
| Tiêu đề | *Structural Scaffolds for Citation Intent Classification in Scientific Publications* |
| Nơi xuất bản | NAACL-HLT 2019 (ACL Anthology) |
| Năm | 2019 |
| URL | https://aclanthology.org/N19-1361/ |
| **Dùng ở đâu trong hệ thống** | Công thức 3 (Mention Score) — động lực cho feature `intent`; Công thức 6 (Edge Score) — động lực cho `intentEdge`; Bảng mapping `intent_score` — taxonomy nhãn gốc |
| **Nội dung paper** | Paper giới thiệu dataset SciCite (~11.000 citation instances) và mô hình phân loại citation intent với 3 nhãn: **Method**, **Result**, **Background**. Mô hình dùng structural scaffold từ section header để cải thiện phân loại, đạt F1 ~84%. Paper chứng minh intent classification mang thông tin phân biệt mạnh về vai trò của citation. |
| **Phần hỗ trợ hệ thống** | Cung cấp động lực học thuật cho việc dùng citation intent như feature; cung cấp taxonomy nhãn gốc (Method, Result, Background) mà hệ thống mở rộng thành 6 nhãn nội bộ. |
| **Phần là heuristic nội bộ** | Điểm số gán cho từng nhãn (use_method=1.00, background=0.40, v.v.) — SciCite chỉ phân loại nhãn, không gán điểm số; việc mở rộng thành 6 nhãn; trọng số 0.30 trong Công thức 3 và 0.05 trong Công thức 6. |

---

### [R6] Jurgens et al. 2018 — ACL-ARC Citation Intent

| Trường | Nội dung |
|---|---|
| Tác giả | Jurgens, D.; Kumar, S.; Hoover, R.; McFarland, D.; Jurafsky, D. |
| Tiêu đề | *Measuring the Evolution of a Scientific Field through Citation Frames* |
| Nơi xuất bản | Transactions of the Association for Computational Linguistics (TACL) |
| Năm | 2018 |
| URL | https://aclanthology.org/Q18-1028/ |
| **Dùng ở đâu trong hệ thống** | Bảng mapping `intent_score` — bổ sung taxonomy nhãn ngoài 3 nhãn SciCite |
| **Nội dung paper** | Paper giới thiệu dataset ACL-ARC với taxonomy citation intent chi tiết hơn SciCite, gồm các nhãn: Uses, Extends, Similarities, Differences, Motivation, Future work. Paper phân tích sự thay đổi của citation pattern trong ngành NLP theo thời gian. |
| **Phần hỗ trợ hệ thống** | Cung cấp động lực học thuật để mở rộng taxonomy từ 3 nhãn SciCite sang các nhãn phân biệt thêm như compare, baseline — lấy cảm hứng từ Similarities/Differences/Uses trong ACL-ARC. |
| **Phần là heuristic nội bộ** | Mapping cụ thể từ ACL-ARC sang 6 nhãn nội bộ; điểm số gán cho từng nhãn. |

---

### [R7] Aksnes et al. 2019 — Citation Count trong Bibliometrics

| Trường | Nội dung |
|---|---|
| Tác giả | Aksnes, D.W.; Langfeldt, L.; Wouters, P. |
| Tiêu đề | *Citations, Citation Indicators, and Research Quality: An Overview of Basic Concepts and Theories* |
| Nơi xuất bản | SAGE Open |
| Năm | 2019 |
| URL | https://journals.sagepub.com/doi/10.1177/2158244019829575 |
| **Dùng ở đâu trong hệ thống** | Công thức 4 (Frequency Score) — động lực cho log transformation; Công thức 6 (Edge Score) — động lực cho `freq` |
| **Nội dung paper** | Overview tổng hợp lý thuyết về citation count trong bibliometrics. Paper chỉ ra phân phối citation count là **highly skewed** và logarithmic transformation (`log(1+n)`) là kỹ thuật chuẩn để xử lý phân phối lệch khi tính chỉ số bibliometric, tránh outlier kéo méo điểm. |
| **Phần hỗ trợ hệ thống** | Cung cấp động lực học thuật cho việc dùng log transformation thay vì đếm tuyến tính. |
| **Phần là heuristic nội bộ** | Hằng số `ln(11)` — saturation tại n=10 là quyết định kỹ thuật nội bộ, không xuất phát từ paper; trọng số 0.20 cho `freq`. |

---

### [R8] Leydesdorff et al. 2019 — Rao-Stirling Diversity Index

| Trường | Nội dung |
|---|---|
| Tác giả | Leydesdorff, L.; Wagner, C.S.; Bornmann, L. |
| Tiêu đề | *Interdisciplinarity as diversity in citation patterns among journals: Rao-Stirling diversity, relative variety, and the Gini coefficient* |
| Nơi xuất bản | Journal of Informetrics |
| Năm | 2019 |
| URL | https://www.sciencedirect.com/science/article/pii/S1751157718303535 |
| **Dùng ở đâu trong hệ thống** | Công thức 5 (Diversity Score) — lấy cảm hứng từ nguyên lý diversity; Công thức 6 (Edge Score) — động lực cho `div` |
| **Nội dung paper** | Paper phân tích Rao-Stirling Diversity Index trong citation pattern giữa các journal và discipline. Công thức đầy đủ: $\Delta = \sum_{ij} d_{ij} \cdot p_i \cdot p_j$, đo mức độ phân bố trích dẫn qua nhiều nhóm/danh mục. Nguyên lý cốt lõi: citation phân bố đa dạng qua nhiều nhóm chứng tỏ mối quan hệ phong phú và sâu hơn. |
| **Phần hỗ trợ hệ thống** | Cung cấp *nguyên lý* học thuật: citation xuất hiện ở nhiều vùng quan trọng khác nhau là tín hiệu đáng tin hơn citation tập trung một chỗ. Paper nghiên cứu diversity giữa các *discipline/journal*, hệ thống **adapt nguyên lý này sang diversity giữa các section** — đây là adaptation nội bộ, không phải ứng dụng trực tiếp. |
| **Phần là heuristic nội bộ** | Công thức `min(1, k/3)` — không phải Rao-Stirling; mẫu số 3; tập section được chọn; trọng số 0.15 trong Công thức 6. |

---

## Bảng tóm tắt: Feature có động lực học thuật vs Heuristic nội bộ

| Thành phần | Loại | Nguồn động lực | Ghi chú |
|---|---|---|---|
| Dùng DOI làm tín hiệu linking chính | ✅ Research-motivated | [R3] Nicholson et al. 2021 | DOI matching dùng trong production pipeline quy mô lớn |
| Dùng title fuzzy matching khi thiếu DOI | ✅ Research-motivated | [R2] Crossref | Phương pháp chính thức của Crossref |
| Dùng author/year làm tín hiệu fallback | ✅ Research-motivated | [R1] Wellner et al. 2004 | Xử lý identity uncertainty trong citation matching |
| Dùng semantic similarity đánh giá mention | ✅ Research-motivated | [R4] Valenzuela et al. 2015 | Feature trong meaningful citation classifier |
| Dùng citation intent như feature | ✅ Research-motivated | [R5] Cohan et al. 2019 | Intent phân biệt vai trò citation mạnh |
| Dùng section location như feature cấu trúc | ✅ Research-motivated | [R4] Valenzuela et al. 2015 | Methods/Results quan trọng hơn Introduction |
| Dùng log transform cho frequency | ✅ Research-motivated | [R7] Aksnes et al. 2019 | Chuẩn trong bibliometrics cho skewed distribution |
| Dùng diversity qua nhiều nhóm | ✅ Research-motivated (nguyên lý) | [R8] Leydesdorff et al. 2019 | Nguyên lý Rao-Stirling; adaptation sang section là nội bộ |
| Trọng số 0.70 / 0.20 / 0.10 (Công thức 1) | ⚙️ Heuristic nội bộ | — | Cần tune theo dữ liệu |
| Trọng số 0.35 / 0.30 / 0.25 / 0.10 (Công thức 3) | ⚙️ Heuristic nội bộ | — | Cần tune theo dữ liệu |
| Trọng số 0.60 / 0.20 / 0.15 / 0.05 (Công thức 6) | ⚙️ Heuristic nội bộ | — | Cần tune theo dữ liệu |
| Hằng số saturation ln(11) (Công thức 4) | ⚙️ Heuristic nội bộ | — | Cần căn chỉnh theo phân phối mention thực tế |
| Công thức `min(1, k/3)` (Công thức 5) | ⚙️ Heuristic nội bộ (inspired by [R8]) | — | Adaptation từ nguyên lý Rao-Stirling, không phải công thức gốc |
| Top-3 aggregation (Công thức 6) | ⚙️ Heuristic nội bộ | — | Quyết định kỹ thuật giảm nhiễu, không có paper validate |
| Bảng section_weight (giá trị số) | ⚙️ Heuristic nội bộ (inspired by [R4]) | — | Paper xác nhận thứ tự ưu tiên section, không xác nhận giá trị số |
| Bảng intent_score (giá trị số) | ⚙️ Heuristic nội bộ (inspired by [R5][R6]) | — | Paper chỉ phân loại nhãn, không gán điểm số |
| Toàn bộ Công thức 2 (Chunk Quality) | ⚙️ Heuristic nội bộ | — | Không có paper validate |