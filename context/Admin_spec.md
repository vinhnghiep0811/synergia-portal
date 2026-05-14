# 3.1.3 Các tác nhân và thành phần liên quan

Việc xác định các tác nhân và thành phần liên quan giúp làm rõ ai là người sử dụng hệ thống, ai chịu trách nhiệm vận hành, và những dịch vụ bên ngoài nào ảnh hưởng đến yêu cầu thiết kế. Trong phạm vi single workspace, đề tài không xây dựng mô hình phân quyền phức tạp. Tuy nhiên, vẫn cần phân biệt các nhóm vai trò dựa trên mục đích sử dụng, trách nhiệm và mối quan tâm chính của từng nhóm.

## Bảng 3.1.2: Các bên liên quan của hệ thống

| Nhóm | Bên liên quan | Vai trò trong hệ thống | Nhu cầu chính |
|---|---|---|---|
| Người dùng chính | Thành viên nhóm nghiên cứu | Người dùng trực tiếp tương tác với web portal để upload, tìm kiếm, kiểm tra và khai thác tài liệu trong kho chung. | • Upload tài liệu PDF nhanh chóng  <br> • Xem danh sách và chi tiết tài liệu  <br> • Tìm kiếm theo từ khóa và ngữ nghĩa  <br> • Kiểm tra metadata, evidence và trạng thái xử lý  <br> • Khám phá quan hệ trích dẫn cơ bản giữa các paper |
| Vận hành hệ thống | Admin | Người phụ trách cấu hình, giám sát và vận hành kỹ thuật của hệ thống trong phạm vi single workspace. | • Xem tổng quan danh sách tài liệu trong hệ thống  <br> • Cấu hình API key, mô hình LLM và tham số pipeline  <br> • Theo dõi activity log và trạng thái xử lý  <br> • Kiểm tra lỗi xử lý và hỗ trợ vận hành hệ thống |
| Sở hữu hệ thống | Nhóm nghiên cứu / Giảng viên hướng dẫn / Đơn vị sử dụng | Đối tượng sử dụng hệ thống như một kho tri thức nội bộ phục vụ nghiên cứu và kế thừa tài liệu giữa các thế hệ thành viên. | • Dữ liệu được tổ chức nhất quán  <br> • Tài liệu có thể được tìm lại và tái sử dụng  <br> • Quy trình tiếp nhận tài liệu minh bạch  <br> • Hệ thống vận hành ổn định trên hạ tầng nội bộ |
| Dịch vụ bên ngoài | Semantic Scholar API | Nguồn dữ liệu học thuật bên ngoài được sử dụng để chuẩn hóa metadata nền tảng của tài liệu. | • Cung cấp metadata như title, authors, year, venue và abstract  <br> • Hỗ trợ đối sánh theo DOI hoặc title candidate  <br> • Giúp giảm phụ thuộc vào LLM đối với metadata nền tảng |
| Dịch vụ bên ngoài | LLM service | Thành phần hỗ trợ trích xuất metadata nghiên cứu từ nội dung tài liệu đã được parse. | • Trả về output có cấu trúc  <br> • Mỗi trường thông tin cần đi kèm evidence snippet  <br> • Yêu cầu output có evidence để hỗ trợ kiểm chứng |
| Dịch vụ bên ngoài | Google OAuth 2.0 | Thành phần xác thực người dùng, giúp nhận diện người thực hiện các thao tác trong hệ thống. | • Đăng nhập đơn giản bằng tài khoản Google  <br> • Gắn thao tác upload, chỉnh sửa và publish với người dùng cụ thể  <br> • Hỗ trợ ghi nhận activity log |
| Tích hợp phụ trợ | Telegram Bot | Kênh tích hợp phụ trợ, chủ yếu phục vụ thông báo hoặc tương tác nhanh, không phải luồng nhập liệu chính của hệ thống. | • Gửi thông báo sau khi tài liệu được publish  <br> • Hỗ trợ tương tác nhanh nếu được bật  <br> • Không làm thay đổi luồng xử lý cốt lõi của web portal |

Cách phân loại trên phản ánh phạm vi single workspace của đề tài. Thành viên nhóm nghiên cứu là người dùng chính của portal; admin phụ trách cấu hình và vận hành kỹ thuật; các dịch vụ bên ngoài đóng vai trò hỗ trợ pipeline xử lý tài liệu. Dù có sử dụng các dịch vụ ngoài, dữ liệu cuối cùng vẫn được lưu trữ, kiểm soát và xác nhận trong hệ thống nội bộ của nhóm.

---

# 3.3 Đặc tả yêu cầu hệ thống

## 3.3.1 Quy tắc nghiệp vụ cốt lõi

Các quy tắc nghiệp vụ được sử dụng để ràng buộc cách hệ thống xử lý tài liệu, metadata và trạng thái kiểm chứng. Các quy tắc này không mô tả một chức năng riêng lẻ, mà xác định những nguyên tắc bắt buộc mà các chức năng của hệ thống phải tuân thủ. Việc tách riêng các quy tắc nghiệp vụ giúp đảm bảo rằng các yêu cầu chức năng ở phần sau được hiểu nhất quán và tránh các cách hiện thực có thể làm sai lệch mục tiêu của MVP.

## Bảng 3.3.1: Các quy tắc nghiệp vụ cốt lõi của hệ thống

| Mã | Tên quy tắc | Nội dung quy tắc | Mục đích / tác động | Liên quan |
|---|---|---|---|---|
| BR-01 | Single workspace | Trong phạm vi MVP, hệ thống chỉ phục vụ một kho tài liệu chung cho một nhóm nghiên cứu. Hệ thống không triển khai nhiều workspace độc lập hoặc phân quyền phức tạp theo từng workspace. | Giảm độ phức tạp triển khai và tập trung vào pipeline xử lý tài liệu, chất lượng metadata và truy hồi tri thức. | FR-01, FR-02, NFR-07 |
| BR-02 | Web portal là kênh nhập liệu chính | Tài liệu học thuật trong MVP được tiếp nhận chủ yếu thông qua upload PDF trên web portal. Telegram Bot, nếu được bật, chỉ đóng vai trò phụ trợ cho thông báo hoặc tương tác nhanh. | Giữ luồng ingestion ổn định, dễ kiểm thử và tránh mở rộng phạm vi sang nhiều kênh nhập liệu. | FR-02, FR-21 |
| BR-03 | Không dùng LLM để sinh metadata nền tảng | Các trường metadata nền tảng như title, authors, year, venue, DOI và abstract không được sinh tự do bởi LLM. Các trường này phải được lấy từ parse PDF, DOI hoặc nguồn học thuật đáng tin cậy như Semantic Scholar. | Giảm rủi ro hallucination đối với các trường định danh quan trọng của tài liệu. | FR-07, NFR-05 |
| BR-04 | Metadata nghiên cứu phải có evidence | Các trường metadata nghiên cứu do LLM hỗ trợ trích xuất, như bài toán nghiên cứu, phương pháp chính, đóng góp, hạn chế và thiết lập đánh giá, phải đi kèm evidence snippet từ nội dung PDF đã parse. | Giúp người dùng kiểm chứng nguồn gốc của thông tin do hệ thống hỗ trợ trích xuất. | FR-08, FR-11, NFR-05 |
| BR-05 | Không suy đoán khi thiếu evidence | Nếu LLM không cung cấp được evidence rõ ràng cho một trường metadata chuyên biệt, hệ thống không được tự suy đoán. Trường đó phải được để trống hoặc đánh dấu unknown/not mentioned. | Bảo vệ độ tin cậy của dữ liệu học thuật và tránh tạo cảm giác hệ thống đã hiểu nội dung khi không có bằng chứng. | FR-08, FR-11, NFR-05 |
| BR-06 | Tài liệu phải qua Draft trước khi Published | Sau khi pipeline xử lý tự động hoàn tất, tài liệu phải được đưa về trạng thái Draft. Tài liệu chỉ được chuyển sang Published khi người dùng xác nhận. | Bảo đảm cơ chế human-in-the-loop và tránh đưa dữ liệu chưa kiểm chứng vào kho chính thức. | FR-11, FR-12 |
| BR-07 | Published là dữ liệu chính thức | Chỉ tài liệu ở trạng thái Published mới được xem là dữ liệu chính thức của kho tài liệu nhóm và được ưu tiên hiển thị trong các luồng khai thác như tìm kiếm, trang chi tiết hoặc citation graph. | Phân biệt rõ dữ liệu đã kiểm chứng với dữ liệu đang chờ người dùng rà soát. | FR-12, FR-13, FR-14, FR-15 |
| BR-08 | Canonical Document là đơn vị chống trùng lặp | Mỗi lần upload tạo ra một PaperRecord, nhưng các PaperRecord trùng nội dung phải được ánh xạ về cùng một Canonical Document dựa trên DOI hoặc fingerprint. | Tránh lưu trùng dữ liệu ở mức nội dung học thuật và tạo nền tảng cho canonical caching. | FR-05, FR-06 |
| BR-09 | Tái sử dụng ExtractionRun khi có cache hit | Nếu một Canonical Document đã có ExtractionRun hợp lệ, các lần upload trùng về sau phải tái sử dụng kết quả này thay vì gọi lại LLM. | Giảm thời gian xử lý, chi phí LLM và giúp hệ thống vận hành hiệu quả hơn. | FR-09, FR-10, NFR-06 |
| BR-10 | File gốc phải được giữ lại | File PDF gốc phải được lưu lại trong hệ thống ngay cả khi một bước xử lý như parse, enrichment, LLM extraction hoặc embedding thất bại. | Đảm bảo tài liệu có thể được kiểm tra lại, xử lý lại hoặc phục hồi khi pipeline gặp lỗi. | FR-02, FR-04, NFR-04 |
| BR-11 | Lỗi pipeline phải được ghi nhận | Các lỗi quan trọng trong pipeline như parse failed, Semantic Scholar no match, LLM timeout, embedding failed, cache hit hoặc cache miss phải được ghi vào processing log. | Hỗ trợ quan sát lỗi, kiểm thử, phân tích vận hành và đánh giá PoC. | FR-20, FR-22, NFR-09 |
| BR-12 | Thông báo chỉ gửi sau khi Published | Nếu Telegram Bot được bật, thông báo tài liệu mới chỉ được gửi sau khi tài liệu đã chuyển sang trạng thái Published. | Tránh thông báo dữ liệu chưa được người dùng xác nhận và giảm nhiễu cho nhóm nghiên cứu. | FR-12, FR-21 |

Các quy tắc nghiệp vụ trên là cơ sở để đặc tả các yêu cầu chức năng và phi chức năng ở các phần tiếp theo. Một yêu cầu chức năng chỉ được xem là phù hợp với MVP nếu không vi phạm các quy tắc này, đặc biệt là các quy tắc liên quan đến evidence-backed extraction, Draft -> Published và canonical caching.

## 3.3.2.1 Danh sách yêu cầu chức năng

Dựa trên bối cảnh vận hành, các bên liên quan và các pain point ưu tiên đã được xác định, phần này đặc tả các yêu cầu chức năng của hệ thống. Các yêu cầu này mô tả những chức năng nghiệp vụ mà hệ thống cần cung cấp để hỗ trợ quá trình tiếp nhận, xử lý, chuẩn hóa, kiểm chứng và khai thác tài liệu học thuật trong phạm vi một nhóm nghiên cứu nhỏ.

Trong phạm vi Đồ án tốt nghiệp, hệ thống được thiết kế theo mô hình single workspace. Do đó, các yêu cầu chức năng không tập trung vào quản lý nhiều không gian làm việc hoặc phân quyền phức tạp, mà ưu tiên pipeline xử lý tài liệu, chất lượng metadata, khả năng kiểm chứng kết quả LLM, canonical caching và truy hồi tri thức.

### Bảng 3.3.2: Danh sách các yêu cầu chức năng của hệ thống

| Mã | Actor | Tên yêu cầu | Mô tả chi tiết | Tham chiếu PP | Ưu tiên |
|---|---|---|---|---|---|
| FR-01 | Member, Admin | Đăng nhập và xác thực người dùng | Hệ thống cho phép người dùng đăng nhập thông qua một cơ chế xác thực phù hợp. Sau khi xác thực, hệ thống lưu thông tin người dùng cơ bản để gắn với các thao tác như upload, chỉnh sửa, publish và ghi nhận activity log. Trong phạm vi single workspace, hệ thống không triển khai phân quyền phức tạp theo nhiều workspace. | PP-07 | Cao |
| FR-02 | Member | Upload tài liệu qua Web Portal | Người dùng có thể upload tài liệu học thuật dạng PDF thông qua giao diện web. Hệ thống kiểm tra định dạng file, kích thước file, lưu file gốc vào lớp lưu trữ tài liệu và tạo một PaperRecord với trạng thái xử lý ban đầu. | PP-01 | Rất cao |
| FR-03 | Member, Admin | Theo dõi danh sách và trạng thái tài liệu | Hệ thống hiển thị danh sách tài liệu đã upload cùng các trạng thái xử lý như pending, parsing, enriching, extracting, draft, published hoặc failed. Người dùng có thể theo dõi tiến trình xử lý và mở trang chi tiết của từng tài liệu. | PP-01, PP-07 | Rất cao |
| FR-04 | System | Parse PDF và trích xuất văn bản | Sau khi tài liệu được upload, worker xử lý bất đồng bộ thực hiện parse PDF để trích xuất text. Hệ thống ưu tiên xử lý PDF dạng text-based. Nếu không trích xuất được nội dung, hệ thống đánh dấu trạng thái lỗi phù hợp thay vì suy đoán dữ liệu. | PP-01, PP-02 | Rất cao |
| FR-05 | System | Nhận diện DOI, title candidate và fingerprint | Từ nội dung đã parse, hệ thống nhận diện DOI bằng regex. Nếu không tìm thấy DOI, hệ thống trích xuất title candidate bằng heuristic và tạo fingerprint từ nội dung văn bản đã chuẩn hóa. Các thông tin này được sử dụng làm cơ sở cho canonical key. | PP-01, PP-04 | Rất cao |
| FR-06 | System | Xây dựng Canonical Document và phát hiện trùng lặp | Hệ thống tạo hoặc ánh xạ tài liệu vào Canonical Document dựa trên DOI hoặc fingerprint. Nếu tài liệu đã tồn tại, PaperRecord mới được ánh xạ về cùng Canonical Document để tránh tạo dữ liệu trùng lặp ở mức nội dung. | PP-01, PP-04 | Rất cao |
| FR-07 | System | Chuẩn hóa metadata nền tảng bằng Semantic Scholar | Hệ thống gọi Semantic Scholar API theo DOI hoặc title candidate để lấy metadata nền tảng như title, authors, year, venue và abstract. Các trường metadata nền tảng không được sinh bởi LLM. Nếu không match đủ tin cậy, hệ thống lưu trạng thái chưa match để người dùng kiểm tra. | PP-02, PP-03 | Rất cao |
| FR-08 | System | Trích xuất metadata chuyên biệt bằng LLM có evidence | Hệ thống sử dụng LLM để trích xuất metadata chuyên biệt, bao gồm bài toán nghiên cứu, phương pháp chính, đóng góp, hạn chế và thiết lập đánh giá. Mỗi trường do LLM sinh ra phải đi kèm evidence snippet từ nội dung tài liệu đã parse. Nếu không có evidence rõ ràng, trường tương ứng được để trống hoặc đánh dấu unknown. | PP-02, PP-03 | Rất cao |
| FR-09 | System | Lưu ExtractionRun theo Canonical Document | Kết quả trích xuất của LLM được lưu thành ExtractionRun gắn với Canonical Document. Kết quả này bao gồm output có cấu trúc, evidence snippet, trạng thái xử lý và log liên quan. | PP-03, PP-04 | Rất cao |
| FR-10 | System | Canonical caching cho kết quả LLM | Khi một tài liệu trùng được upload lại và Canonical Document đã có ExtractionRun đạt chuẩn, hệ thống tái sử dụng kết quả đã có thay vì gọi lại LLM. Hệ thống ghi nhận cache hit trong processing log để phục vụ kiểm thử và đánh giá vận hành. | PP-04 | Rất cao |
| FR-11 | Member | Kiểm tra và chỉnh sửa metadata ở trạng thái Draft | Sau khi pipeline xử lý hoàn tất, tài liệu được đưa vào trạng thái Draft. Người dùng có thể kiểm tra metadata nền tảng, metadata chuyên biệt, evidence snippet, tags và ghi chú trước khi quyết định publish. | PP-02, PP-03, PP-07 | Rất cao |
| FR-12 | Member | Publish tài liệu sau khi xác nhận | Người dùng có thể publish tài liệu sau khi đã kiểm tra thông tin. Chỉ các tài liệu ở trạng thái Published mới được xem là dữ liệu chính thức của nhóm. Hệ thống ghi nhận người thực hiện publish và thời điểm publish. | PP-03, PP-07 | Rất cao |
| FR-13 | Member | Xem chi tiết tài liệu | Hệ thống cung cấp trang chi tiết tài liệu, bao gồm file PDF, metadata nền tảng, metadata chuyên biệt, evidence snippet, trạng thái xử lý, canonical information và các quan hệ trích dẫn liên quan nếu có. | PP-02, PP-03, PP-06 | Rất cao |
| FR-14 | Member | Tìm kiếm tài liệu theo từ khóa | Người dùng có thể tìm kiếm tài liệu theo các trường như title, authors, year, venue, DOI, tags hoặc nội dung metadata. Chức năng này phục vụ các truy vấn chính xác và các trường hợp người dùng đã biết một phần thông tin tài liệu. | PP-05 | Cao |
| FR-15 | Member | Tìm kiếm ngữ nghĩa | Hệ thống hỗ trợ semantic search bằng cách sinh embedding cho tài liệu và truy vấn, sau đó tìm kiếm các tài liệu hoặc đoạn nội dung có độ tương đồng cao. Chức năng này giúp người dùng tìm tài liệu theo bài toán, phương pháp hoặc mô tả ngữ cảnh nghiên cứu. | PP-05 | Cao |
| FR-16 | System | Sinh và lưu embedding phục vụ semantic search | Sau khi tài liệu có nội dung hoặc metadata phù hợp, hệ thống sinh embedding và lưu vào PostgreSQL thông qua pgvector. Embedding được dùng cho semantic search và có thể được cập nhật khi metadata chính thức thay đổi. | PP-05 | Cao |
| FR-17 | Member | Hiển thị citation graph ở mức MVP | Hệ thống hiển thị mối quan hệ trích dẫn giữa các tài liệu trong kho nội bộ. Các node biểu diễn tài liệu, các edge biểu diễn quan hệ trích dẫn. Chức năng này tập trung vào hỗ trợ khám phá tri thức, không triển khai phân tích graph quy mô lớn. | PP-06 | Trung bình - cao |
| FR-18 | Member | Xem chi tiết cạnh trong citation graph | Khi người dùng chọn một quan hệ trích dẫn, hệ thống hiển thị các thông tin liên quan nếu có, chẳng hạn tài liệu nguồn, tài liệu được trích dẫn, đoạn ngữ cảnh trích dẫn hoặc ghi chú mô tả quan hệ. Chức năng này chỉ phục vụ khám phá quan hệ tài liệu ở mức MVP, không nhằm đánh giá độ ảnh hưởng học thuật của paper. | PP-06 | Trung bình - cao |
| FR-19 | Admin | Cấu hình hệ thống | Admin có thể cấu hình các tham số vận hành như Semantic Scholar API key, LLM provider hoặc model, embedding model, ngưỡng match metadata và các tham số pipeline cần thiết. | PP-07 | Cao |
| FR-20 | Admin | Theo dõi activity log và processing log | Hệ thống ghi nhận các hoạt động chính như upload tài liệu, chỉnh sửa metadata, publish, lỗi pipeline, cache hit và các thao tác cấu hình. Admin có thể xem log để theo dõi vận hành và phân tích lỗi. | PP-04, PP-07 | Cao |
| FR-21 | System, Telegram Bot | Gửi thông báo sau khi publish nếu Telegram Bot được bật | Nếu Telegram Bot được cấu hình, hệ thống gửi thông báo ngắn gọn sau khi tài liệu được publish. Nội dung thông báo có thể gồm title, authors/year, tags, summary ngắn và link về portal. Telegram Bot không phải là kênh ingestion chính trong MVP. | PP-07 | Tùy chọn |
| FR-22 | Admin, System | Thu thập dữ liệu phục vụ đánh giá | Hệ thống lưu các dữ liệu cần thiết cho kiểm thử và đánh giá, bao gồm trạng thái pipeline, thời gian xử lý, cache hit, lỗi parse, kết quả search và các log liên quan. Các dữ liệu này phục vụ đánh giá PoC và phân tích lỗi. | PP-04, PP-05, PP-07 | Cao |

## 3.3.2.2 Các chức năng không thuộc phạm vi MVP

Để giữ phạm vi triển khai phù hợp với Đồ án tốt nghiệp, một số chức năng không được đưa vào MVP. Các chức năng này có thể được xem là hướng phát triển trong tương lai, nhưng không phải là yêu cầu bắt buộc của hệ thống ở giai đoạn hiện tại.

Thứ nhất, hệ thống không triển khai multi-workspace hoặc phân quyền phức tạp theo nhiều không gian làm việc. Hệ thống được thiết kế cho một single workspace phục vụ một nhóm nghiên cứu.

Thứ hai, hệ thống không triển khai Chrome Extension hoặc mobile app. Luồng nhập liệu chính là upload thông qua web portal. Telegram Bot, nếu được bật, chỉ đóng vai trò phụ trợ cho thông báo hoặc tương tác nhanh.

Thứ ba, hệ thống không triển khai recommendation nâng cao hoặc learning path. Các chức năng gợi ý tài liệu chỉ có thể được xem xét ở mức mở rộng sau khi semantic search và citation graph cơ bản đã ổn định.

Thứ tư, hệ thống không triển khai LLM-based Q&A như một chức năng cốt lõi của MVP. LLM được sử dụng chủ yếu cho trích xuất metadata chuyên biệt có evidence.

Thứ năm, hệ thống không fine-tune LLM. Việc sử dụng LLM trong đề tài tập trung vào inference có kiểm chứng thông qua evidence snippet và human verification.

Thứ sáu, các thành phần như paperless-ngx, n8n, vector database độc lập hoặc graph database độc lập không được đưa vào phạm vi triển khai MVP. Trong giai đoạn hiện tại, hệ thống ưu tiên kiến trúc gọn hơn để giảm rủi ro tích hợp, đồng thời tập trung vào pipeline xử lý tài liệu, evidence-backed extraction, canonical caching và truy hồi tri thức ở mức cơ bản.

## 3.3.2.3 Truy vết giữa pain point và yêu cầu chức năng

Tập yêu cầu chức năng trên được thiết kế để có thể truy vết ngược về các pain point ưu tiên. PP-01 được phản ánh trong các yêu cầu về upload, lưu trữ, parse PDF và canonical detection. PP-02 và PP-03 được phản ánh trong các yêu cầu về chuẩn hóa metadata, LLM extraction có evidence và quy trình Draft → Published. PP-04 được phản ánh trong Canonical Document, ExtractionRun và canonical caching. PP-05 được phản ánh trong keyword search, semantic search và embedding. PP-06 được phản ánh trong citation graph và chi tiết cạnh. PP-07 được phản ánh trong xác thực, giao diện theo dõi trạng thái, admin settings, activity log và triển khai theo hướng kiểm soát dữ liệu nội bộ.

Cách tổ chức này giúp bảo đảm rằng mỗi chức năng trong MVP đều xuất phát từ một vấn đề thực tế hoặc một ràng buộc thiết kế đã được xác định, đồng thời tránh mở rộng hệ thống sang các chức năng chưa cần thiết trong phạm vi hiện tại.

# 3.3.3 Yêu cầu phi chức năng

## 3.3.3.1 Danh sách yêu cầu phi chức năng

Bên cạnh các yêu cầu chức năng, hệ thống cần đáp ứng một tập hợp các yêu cầu phi chức năng nhằm đảm bảo khả năng vận hành ổn định, tính tin cậy của dữ liệu và khả năng kiểm chứng trong phạm vi triển khai thực tế. Các yêu cầu này không mô tả hệ thống thực hiện chức năng gì, mà mô tả hệ thống cần vận hành như thế nào để các chức năng đã đặc tả có thể được sử dụng một cách hiệu quả.

Trong phạm vi Đồ án tốt nghiệp, hệ thống được triển khai theo mô hình single workspace cho một nhóm nghiên cứu nhỏ. Do đó, các yêu cầu phi chức năng không tập trung vào khả năng mở rộng ở quy mô tổ chức lớn hoặc phân quyền phức tạp, mà ưu tiên các tiêu chí thiết thực hơn: kiểm soát dữ liệu nội bộ, độ tin cậy của pipeline xử lý, khả năng kiểm chứng kết quả LLM, hiệu quả tài nguyên thông qua canonical caching, khả năng quan sát lỗi và tính dễ sử dụng của web portal.

### Bảng 3.3.3: Danh sách các yêu cầu phi chức năng của hệ thống

| Mã | Nhóm chất lượng | Yêu cầu phi chức năng | Giải thích lựa chọn | Liên quan |
|---|---|---|---|---|
| NFR-01 | Security & Privacy | Hệ thống phải được thiết kế theo hướng kiểm soát dữ liệu nội bộ. Tài liệu gốc được lưu trên hạ tầng do nhóm quản lý, người dùng đăng nhập thông qua cơ chế xác thực người dùng, và các thao tác chính cần được ghi nhận. | Tài liệu nghiên cứu có thể bao gồm bản thảo chưa công bố hoặc nội dung nhạy cảm. Vì vậy, hệ thống cần hạn chế phụ thuộc vào kho lưu trữ công cộng và phải cho phép truy vết người thực hiện các thao tác quan trọng như upload, chỉnh sửa và publish. | PP-07, FR-01, FR-02, FR-20 |
| NFR-02 | Usability | Giao diện web phải dễ sử dụng đối với thành viên nhóm nghiên cứu, tập trung vào các luồng chính như upload, theo dõi trạng thái, kiểm tra metadata, publish, tìm kiếm và xem quan hệ trích dẫn ở mức MVP. | Một trong các rào cản khi đưa hệ thống mới vào sử dụng là người dùng lo ngại hệ thống quá phức tạp. Do đó, giao diện cần ưu tiên tính rõ ràng, hạn chế số bước không cần thiết và thể hiện trạng thái xử lý một cách minh bạch. | PP-07, FR-02, FR-03, FR-11, FR-13 |
| NFR-03 | Performance | Các thao tác tương tác trực tiếp với người dùng như xem danh sách, mở trang chi tiết và tìm kiếm cần có thời gian phản hồi ở mức chấp nhận được đối với kho tài liệu quy mô nhóm nghiên cứu. | Người dùng sử dụng hệ thống trong quá trình nghiên cứu nên các thao tác tra cứu không được gây gián đoạn. Các tác vụ nặng như parse PDF hoặc LLM extraction không chạy trực tiếp trong request-response mà được xử lý bất đồng bộ. | PP-01, PP-05, FR-03, FR-14, FR-15 |
| NFR-04 | Reliability | Pipeline xử lý tài liệu phải có trạng thái rõ ràng, có khả năng ghi nhận lỗi, hỗ trợ retry cho các tác vụ phù hợp và không làm mất file gốc khi một bước xử lý thất bại. | Pipeline gồm nhiều bước có thể thất bại như parse PDF, gọi Semantic Scholar, sinh embedding hoặc gọi LLM. Hệ thống cần đảm bảo lỗi ở một bước không làm mất dữ liệu và người dùng có thể biết tài liệu đang ở trạng thái nào. | PP-01, PP-07, FR-03, FR-04, FR-20 |
| NFR-05 | Data Quality & Verifiability | Metadata nền tảng phải được lấy từ parse PDF hoặc nguồn đáng tin cậy. Metadata nghiên cứu do LLM trích xuất phải có evidence snippet đi kèm. Trường không có evidence rõ ràng phải được để trống hoặc đánh dấu unknown. | Đây là yêu cầu quan trọng để hạn chế hallucination và bảo vệ độ tin cậy của dữ liệu học thuật. Hệ thống không để LLM tự sinh các trường nền tảng như title, authors, year hoặc venue. | PP-02, PP-03, FR-07, FR-08, FR-11 |
| NFR-06 | Resource Efficiency | Hệ thống phải tái sử dụng kết quả xử lý theo Canonical Document khi phát hiện tài liệu trùng lặp, đặc biệt là kết quả LLM extraction. | LLM extraction và sinh embedding là các bước tốn tài nguyên. Canonical caching giúp tránh gọi lại LLM cho cùng một paper, giảm thời gian xử lý và chi phí vận hành. | PP-04, FR-06, FR-09, FR-10 |
| NFR-07 | Maintainability | Hệ thống cần được tổ chức theo các module rõ ràng, tách biệt frontend, backend API, worker xử lý nền, lớp lưu trữ file, cơ sở dữ liệu và các tích hợp bên ngoài. | Cấu trúc module hóa giúp nhóm phát triển song song, dễ kiểm thử từng thành phần và thuận tiện khi thay đổi LLM provider, embedding model hoặc workflow xử lý. | FR-02, FR-04, FR-07, FR-08, FR-19 |
| NFR-08 | Deployability | Hệ thống cần có khả năng đóng gói và triển khai lại trên VM nội bộ bằng một quy trình cài đặt rõ ràng, ưu tiên Docker Compose hoặc cơ chế tương đương. | Đề tài hướng đến triển khai MVP trên hạ tầng nội bộ. Vì vậy, hệ thống cần giảm phụ thuộc môi trường cục bộ và có tài liệu triển khai đủ rõ để tái lập. | FR-19, FR-20, FR-22 |
| NFR-09 | Observability & Measurability | Hệ thống cần ghi nhận processing log, activity log và các chỉ số vận hành cần thiết để phục vụ kiểm thử, đánh giá pipeline và phân tích lỗi. | Đề tài cần chứng minh tính thực tế của pipeline, hiệu quả canonical caching, độ ổn định xử lý và hiệu quả tìm kiếm. Vì vậy, log và metrics là yêu cầu bắt buộc để đánh giá hệ thống một cách có căn cứ. | PP-04, PP-05, PP-07, FR-20, FR-22 |
| NFR-10 | Scalability | Kiến trúc hệ thống cần cho phép mở rộng ở mức phù hợp với nhóm nghiên cứu, bao gồm tăng số lượng tài liệu, tăng dung lượng lưu trữ và bổ sung worker xử lý nền khi cần. | Hệ thống không đặt mục tiêu phục vụ quy mô tổ chức lớn trong MVP. Tuy nhiên, việc tách file storage, database và worker giúp hệ thống có khả năng mở rộng từng phần mà không phải thay đổi thiết kế cốt lõi. | PP-01, PP-04, FR-02, FR-06, FR-10 |

## 3.3.3.2 Định lượng hóa yêu cầu và phương pháp kiểm thử

Để các yêu cầu phi chức năng có thể được kiểm chứng trong quá trình nghiệm thu, một số yêu cầu được chuyển hóa thành các chỉ số đo lường cụ thể. Các ngưỡng trong Bảng 3.3.4 dưới đây được lựa chọn theo phạm vi PoC của đề tài, hướng đến kho tài liệu quy mô nhóm nghiên cứu thay vì một hệ thống production quy mô lớn.

### Bảng 3.3.4: Định lượng hóa yêu cầu phi chức năng và phương pháp kiểm thử

| Mã NFR | Chỉ số đo lường / Ngưỡng nghiệm thu | Phương pháp kiểm thử | Ghi chú |
|---|---|---|---|
| NFR-01 | • 100% API yêu cầu đăng nhập phải từ chối request chưa xác thực. <br> • Các thao tác upload, chỉnh sửa và publish phải được gắn với user tương ứng. | • Thử gọi API khi chưa đăng nhập. <br> • Kiểm tra activity log sau các thao tác chính. | Không kiểm thử RBAC phức tạp vì hệ thống vận hành theo single workspace. |
| NFR-02 | Người dùng hoàn thành các tác vụ cơ bản như upload, xem trạng thái, kiểm tra metadata và publish mà không cần hướng dẫn dài. | • Tối thiểu 80% người dùng thử hoàn thành các tác vụ cơ bản như upload, xem trạng thái, kiểm tra metadata và publish theo kịch bản nhiệm vụ mà không cần hỗ trợ trực tiếp. <br> • Ghi nhận thời gian hoàn thành, lỗi thao tác và phản hồi định tính. | Có thể dùng khảo sát SUS nếu có đủ thời gian, nhưng không bắt buộc trong MVP. |
| NFR-03 | • Thời gian phản hồi tìm kiếm keyword hoặc semantic search <= 3 giây với kho thử nghiệm quy mô từ 100 đến 500 tài liệu. <br> • Trang danh sách và trang chi tiết phản hồi ở mức không gây gián đoạn sử dụng. | Chạy tập truy vấn mẫu và đo thời gian phản hồi trung bình, P95 nếu có thể. | Không tính thời gian xử lý nền như parse PDF hoặc LLM extraction vào thời gian phản hồi UI. |
| NFR-04 | Pipeline xử lý không làm mất file gốc khi một bước thất bại. Các trạng thái pending, parsing, enriching, extracting, draft, published và failed phải được cập nhật nhất quán. | Thử các trường hợp lỗi như PDF không parse được, Semantic Scholar không match, LLM timeout hoặc lỗi embedding. | Các lỗi phải được ghi nhận trong processing log. |
| NFR-05 | • 100% trường metadata chuyên biệt do LLM sinh ra phải có evidence snippet, hoặc được đánh dấu unknown/empty nếu thiếu evidence. <br> • 100% metadata nền tảng không được sinh tự do bởi LLM. | Kiểm tra output LLM trên tập paper mẫu. Đối chiếu schema lưu trữ và giao diện hiển thị evidence. | Đây là tiêu chí nghiệm thu quan trọng nhất cho phần AI-assisted extraction. |
| NFR-06 | Khi upload lại cùng một paper đã có ExtractionRun đạt chuẩn, hệ thống phải tái sử dụng kết quả cũ và không gọi lại LLM. | Upload cùng một paper nhiều lần, kiểm tra số lần gọi LLM và cache hit trong log. | Canonical key ưu tiên DOI; nếu không có DOI thì dùng fingerprint. |
| NFR-07 | Các thành phần chính gồm frontend, backend, worker, storage, database và external integrations phải được tách module rõ ràng. | Review cấu trúc mã nguồn, cấu hình service và dependency giữa các module. | Tiêu chí này phục vụ bảo trì và mở rộng sau MVP. |
| NFR-08 | Hệ thống có thể được triển khai lại trên VM mới theo tài liệu hướng dẫn và cấu hình môi trường đã chuẩn bị. Nếu có đủ Docker image, biến môi trường và dữ liệu cấu hình, quá trình triển khai nên hoàn tất trong thời gian chấp nhận được đối với MVP. | Thử triển khai fresh bằng Docker Compose hoặc kịch bản triển khai tương đương. | Không tính thời gian tải model LLM lớn nếu model được quản lý bên ngoài hệ thống. |
| NFR-09 | Hệ thống ghi nhận được các dữ liệu tối thiểu: thời gian xử lý pipeline, trạng thái job, lỗi parse, lỗi enrichment, cache hit, kết quả search và activity log. | Thực hiện các luồng chính và kiểm tra dữ liệu log/metrics được ghi nhận đầy đủ. | Dữ liệu này phục vụ chương đánh giá và phân tích lỗi. |
| NFR-10 | Hệ thống xử lý ổn định trên tập thử nghiệm tối thiểu 100 tài liệu PDF text-based và có thể mở rộng lưu trữ mà không thay đổi schema lõi. | Upload tập tài liệu thử nghiệm, theo dõi trạng thái pipeline, dung lượng lưu trữ và khả năng truy xuất lại file. | Mục tiêu là kiểm chứng khả năng vận hành ở quy mô nhóm nghiên cứu, không phải benchmark production. |

# 3.4 Mô hình hóa tương tác người dùng

## 3.4.1 Sơ đồ Use Case tổng quát (Overall Use Case Diagram)

Sơ đồ Use Case tổng quát được sử dụng để biểu diễn các nhóm chức năng chính của hệ thống ở mức mục tiêu người dùng. Trong phạm vi hệ thống, hai tác nhân chính được xác định là Member và Admin. Member là thành viên nhóm nghiên cứu, trực tiếp sử dụng portal để upload, kiểm tra, publish, tìm kiếm và khai thác tài liệu học thuật. Admin là người phụ trách cấu hình, giám sát và vận hành hệ thống.

Hình 3.4.1 minh họa mối quan hệ giữa hai tác nhân chính và các nhóm use case tương ứng trong hệ thống.

### Các nhóm use case chính của Member

Thành viên nhóm nghiên cứu tương tác với hệ thống thông qua các nhóm chức năng sau:

- Upload tài liệu PDF lên web portal.
- Theo dõi trạng thái pipeline xử lý tài liệu.
- Kiểm tra metadata nền tảng và metadata chuyên biệt.
- Xác nhận và publish tài liệu.
- Tìm kiếm tài liệu theo từ khóa hoặc semantic search.
- Xem citation graph và khai thác quan hệ trích dẫn.
- Xem chi tiết tài liệu và evidence snippet.

### Các nhóm use case chính của Admin

Admin chịu trách nhiệm cấu hình và vận hành hệ thống, bao gồm:

- Cấu hình Semantic Scholar API key.
- Cấu hình LLM provider và embedding model.
- Theo dõi processing log và activity log.
- Giám sát trạng thái pipeline.
- Thu thập dữ liệu phục vụ đánh giá PoC.
- Kiểm tra cache hit và lỗi pipeline.

## 3.4.2 Phân rã các Use Case chính

Để hỗ trợ việc đặc tả luồng xử lý và thiết kế hệ thống, các chức năng được gom thành bốn nhóm use case chính:

| Mã UC | Tên Use Case | Mục tiêu chính |
|---|---|---|
| UC-01 | Thu thập và chuẩn hóa tài liệu | Upload, parse PDF, chuẩn hóa metadata và canonical detection |
| UC-02 | Kiểm tra và khai thác tài liệu | Draft review, publish, tìm kiếm và semantic retrieval |
| UC-03 | Phân tích quan hệ trích dẫn | Hiển thị citation graph và khám phá citation edge |
| UC-04 | Vận hành và cấu hình hệ thống | Giám sát pipeline, cấu hình hệ thống và thu thập dữ liệu đánh giá |

# 3.4.3 Đặc tả Use Case chi tiết
## 3.4.3.4 UC-04: Vận hành và cấu hình hệ thống

### Bảng 3.4.5: Đặc tả chi tiết Use Case UC-04

| Mục | Nội dung chi tiết |
|---|---|
| Mã UC | UC-04 |
| Tên UC | Vận hành và cấu hình hệ thống |
| Tác nhân chính | Admin |
| Mục đích | Cho phép admin theo dõi tình trạng vận hành của hệ thống, cấu hình các tham số kỹ thuật cần thiết và thu thập dữ liệu phục vụ kiểm thử, đánh giá PoC. |
| Tiền điều kiện | • Admin đã đăng nhập thành công vào hệ thống. <br> • Admin có quyền truy cập khu vực cấu hình và giám sát. <br> • Các thành phần backend, worker, database và storage đang hoạt động hoặc có log trạng thái. |
| Kích hoạt | Admin mở trang quản trị hệ thống từ web portal. |
| Luồng chính | 1. Admin truy cập dashboard quản trị. <br> 2. Hệ thống hiển thị tổng quan số lượng tài liệu, trạng thái pipeline, số job đang xử lý, số job lỗi và các cache hit nếu có. <br> 3. Admin mở trang cấu hình hệ thống. <br> 4. Admin cấu hình hoặc cập nhật các tham số như Semantic Scholar API key, LLM provider/model, embedding model, ngưỡng match metadata và tham số pipeline. <br> 5. Hệ thống kiểm tra tính hợp lệ cơ bản của cấu hình và lưu cấu hình mới. <br> 6. Admin xem activity log để theo dõi các thao tác như upload, chỉnh sửa metadata, publish và thay đổi cấu hình. <br> 7. Admin xem processing log để phân tích các lỗi như parse failed, enrichment failed, LLM timeout hoặc cache miss. <br> 8. Admin xuất hoặc thu thập dữ liệu phục vụ đánh giá, bao gồm thời gian xử lý, cache hit, kết quả search mẫu và lỗi pipeline. |
| Luồng thay thế | Chỉ xem trạng thái hệ thống <br> 1A.1. Admin chỉ mở dashboard để kiểm tra nhanh tình trạng vận hành. <br> 1A.2. Hệ thống hiển thị số liệu tổng quan mà không thay đổi cấu hình. <br><br> Cập nhật một phần cấu hình <br> 4A.1. Admin chỉ thay đổi một tham số, ví dụ LLM model hoặc threshold match metadata. <br> 4A.2. Hệ thống lưu phần cấu hình được thay đổi và giữ nguyên các tham số còn lại. <br><br> Thu thập dữ liệu đánh giá <br> 8A.1. Admin chọn khoảng thời gian hoặc nhóm dữ liệu cần xuất. <br> 8A.2. Hệ thống tạo dữ liệu phục vụ đánh giá pipeline, canonical caching hoặc search. |
| Luồng ngoại lệ | Cấu hình không hợp lệ <br> 5E.1. API key, model name hoặc tham số pipeline không hợp lệ. <br> 5E.2. Hệ thống từ chối lưu cấu hình và hiển thị lý do lỗi. <br><br> Không truy cập được dịch vụ bên ngoài <br> 5E.3. Hệ thống không kiểm tra được Semantic Scholar API hoặc LLM Service. <br> 5E.4. Hệ thống cảnh báo admin và ghi nhận lỗi vào log. <br><br> Không có dữ liệu đánh giá <br> 8E.1. Chưa có đủ log hoặc metrics để xuất dữ liệu. <br> 8E.2. Hệ thống thông báo chưa đủ dữ liệu và gợi ý chạy các luồng kiểm thử chính. |
| Hậu điều kiện | • Cấu hình hệ thống được cập nhật nếu hợp lệ. <br> • Activity log và processing log được admin theo dõi. <br> • Dữ liệu phục vụ kiểm thử và đánh giá được thu thập khi có đủ điều kiện. |
| Yêu cầu liên quan | FR-01, FR-19, FR-20, FR-22 |

# 3.5 Tiêu chí nghiệm thu và truy vết yêu cầu

Sau khi xác định các yêu cầu chức năng, yêu cầu phi chức năng và các use case chính, cần có một bước tổng hợp nhằm làm rõ cách đánh giá mức độ hoàn thành của hệ thống. Phần này trình bày các tiêu chí nghiệm thu theo từng luồng nghiệp vụ trọng tâm, đồng thời xây dựng ma trận truy vết giữa pain point, yêu cầu, thành phần thiết kế và kiểm thử.

Mục tiêu của phần này là đảm bảo rằng các chức năng được triển khai không chỉ xuất phát từ nhu cầu thực tế, mà còn có thể được kiểm chứng thông qua các tiêu chí cụ thể. Cách tiếp cận này giúp giữ phạm vi MVP rõ ràng, hạn chế phát triển các chức năng ngoài trọng tâm, đồng thời tạo cơ sở cho phần thiết kế hệ thống và kiểm thử ở các chương sau.

## 3.5.1 Tiêu chí nghiệm thu theo luồng nghiệp vụ chính

Các tiêu chí nghiệm thu được tổ chức theo bốn luồng nghiệp vụ chính tương ứng với các use case tổng quát đã xác định. Mỗi luồng phản ánh một nhóm mục tiêu lớn của người dùng hoặc admin khi tương tác với hệ thống.

Bảng dưới đây tổng hợp các tiêu chí nghiệm thu chính cho từng luồng. Các tiêu chí này không đi sâu vào chi tiết cài đặt, mà tập trung vào việc hệ thống cần đạt trạng thái nào để được xem là đáp ứng yêu cầu.

### Bảng 3.5.1: Tiêu chí nghiệm thu theo luồng nghiệp vụ chính

| Mã flow | Luồng nghiệp vụ | Tiêu chí nghiệm thu | UC / FR liên quan | Phương pháp kiểm chứng |
|---|---|---|---|---|
| AF-01 | Thu thập và chuẩn hóa tài liệu | • Người dùng upload được file PDF hợp lệ qua web portal. <br> • File gốc được lưu vào storage. <br> • Hệ thống parse được nội dung text đối với PDF text-based. <br> • DOI hoặc title candidate được nhận diện nếu có. <br> • Canonical Document được tạo hoặc ánh xạ đúng khi upload trùng. <br> • Metadata nền tảng được enrich từ nguồn học thuật đáng tin cậy. <br> • Metadata chuyên biệt được sinh kèm evidence snippet. <br> • Pipeline cập nhật trạng thái rõ ràng từ pending đến draft hoặc failed. | UC-01 / FR-02, FR-03, FR-04, FR-05, FR-06, FR-07, FR-08, FR-09, FR-10 | • Upload tập PDF hợp lệ và không hợp lệ. <br> • Kiểm tra file được lưu trong storage. <br> • Kiểm tra nội dung parse text. <br> • Upload trùng tài liệu để kiểm tra canonical caching. <br> • Kiểm tra evidence snippet trên output extraction. <br> • Theo dõi processing log trong từng bước pipeline. |
| AF-02 | Kiểm tra và publish tài liệu | • Người dùng xem được metadata nền tảng và metadata chuyên biệt của tài liệu ở trạng thái Draft. <br> • Evidence snippet hiển thị tương ứng với từng trường extraction. <br> • Người dùng chỉnh sửa metadata hoặc tags trước khi publish. <br> • Tài liệu chỉ xuất hiện trong kho chính thức sau khi được publish. <br> • Activity log ghi nhận thao tác publish và chỉnh sửa metadata. | UC-02 / FR-11, FR-12, FR-13, FR-20 | • Mở trang chi tiết của tài liệu Draft. <br> • Kiểm tra evidence snippet hiển thị đúng. <br> • Chỉnh sửa metadata và tags. <br> • Publish tài liệu và kiểm tra trạng thái Published. <br> • Kiểm tra activity log sau thao tác publish. |
| AF-03 | Tìm kiếm và truy hồi tri thức | • Người dùng tìm kiếm được tài liệu bằng keyword search. <br> • Semantic search trả về các tài liệu có liên quan về ngữ nghĩa. <br> • Kết quả tìm kiếm hiển thị metadata cơ bản và trạng thái tài liệu. <br> • Trang chi tiết hiển thị file PDF, metadata nền tảng, metadata chuyên biệt và evidence snippet. <br> • Kiểm tra dữ liệu truy vấn được ghi nhận nếu logging được bật. | UC-02 / FR-13, FR-14, FR-15, FR-16, FR-22 | • Thực hiện tập truy vấn keyword mẫu. <br> • Thực hiện semantic search bằng mô tả bài toán nghiên cứu. <br> • Đánh giá độ liên quan của kết quả trả về. <br> • Kiểm tra trang chi tiết tài liệu. <br> • Kiểm tra query log hoặc metrics nếu có. |
| AF-04 | Phân tích đồ thị trích dẫn | • Hệ thống hiển thị được citation graph cho tài liệu hoặc tập tài liệu có quan hệ trích dẫn. <br> • Node trong graph biểu diễn tài liệu. <br> • Edge trong graph biểu diễn quan hệ trích dẫn giữa các tài liệu. <br> • Khi chọn node, người dùng xem được thông tin tóm lược của tài liệu. <br> • Khi chọn edge, hệ thống hiển thị thông tin mô tả quan hệ trích dẫn nếu dữ liệu có sẵn, chẳng hạn loại quan hệ hoặc ngữ cảnh trích dẫn. <br> • Nếu thiếu dữ liệu trích dẫn hoặc thiếu citation context, hệ thống hiển thị thông báo phù hợp thay vì lỗi giao diện. | UC-03 / FR-17, FR-18, FR-22 | • Chuẩn bị tập tài liệu có citation edge mẫu. <br> • Kiểm tra graph hiển thị đúng node và edge. <br> • Kiểm tra tương tác chọn node và chọn edge. <br> • Kiểm tra dữ liệu citation type, context và strength hiển thị đúng với dữ liệu lưu trong PostgreSQL. <br> • Kiểm tra fallback khi thiếu citation context. |
| AF-05 | Vận hành và cấu hình hệ thống | • Người dùng đăng nhập được thông qua cơ chế xác thực được cấu hình. <br> • Admin xem được tổng quan trạng thái hệ thống. <br> • Admin cấu hình được các tham số vận hành tối thiểu liên quan đến nguồn metadata, LLM, embedding và pipeline xử lý. <br> • Hệ thống ghi nhận activity log cho các thao tác chính như upload, chỉnh sửa metadata, publish và thay đổi cấu hình. <br> • Hệ thống ghi processing log cho các job xử lý nền. <br> • Admin thu thập được dữ liệu phục vụ kiểm thử và đánh giá PoC. | UC-04 / FR-01, FR-19, FR-20, FR-22 | • Kiểm thử đăng nhập bằng Google OAuth. <br> • Kiểm tra màn hình admin dashboard. <br> • Thử cập nhật cấu hình hệ thống. <br> • Thực hiện các thao tác chính và kiểm tra activity log. <br> • Gây lỗi pipeline có kiểm soát và kiểm tra processing log. <br> • Kiểm tra dữ liệu metrics phục vụ đánh giá. |

## 3.5.2 Ma trận truy vết pain point - yêu cầu - thiết kế - kiểm thử

Bên cạnh tiêu chí nghiệm thu theo flow, cần xác định mối liên hệ giữa pain point, yêu cầu chức năng, use case, thành phần thiết kế và kiểm thử. Ma trận truy vết giúp chứng minh rằng mỗi thành phần trong hệ thống đều có lý do tồn tại rõ ràng và đều phục vụ việc giải quyết một vấn đề đã được xác định từ trước.

Bảng dưới đây trình bày ma trận truy vết ở mức nhóm. Cách trình bày này phù hợp với phạm vi báo cáo vì không làm bảng quá chi tiết, nhưng vẫn đủ để thể hiện mối liên kết giữa phân tích yêu cầu, thiết kế và kiểm thử.

### Bảng 3.5.2: Ma trận truy vết pain point - yêu cầu - thiết kế - kiểm thử

| Pain point | Yêu cầu liên quan | Use case liên quan | Thành phần thiết kế tương ứng | Hướng kiểm thử / đánh giá |
|---|---|---|---|---|
| PP-01 | FR-02, FR-03, FR-04, FR-05, FR-06 | UC-01: Thu thập và chuẩn hóa tài liệu | • Web portal upload PDF <br> • Backend API <br> • Lớp lưu trữ tài liệu <br> • Worker xử lý nền <br> • PDF parsing module <br> • Canonical Document <br> • Duplicate detection | • Kiểm thử upload PDF hợp lệ và không hợp lệ. <br> • Kiểm tra file được lưu vào RustFS. <br> • Kiểm tra PaperRecord được tạo. <br> • Kiểm tra trạng thái pipeline. <br> • Upload trùng tài liệu để kiểm tra canonical detection. |
| PP-02 | FR-07, FR-08, FR-11 | UC-01, UC-02 | • Semantic Scholar integration <br> • Metadata normalization module <br> • LLM extraction service <br> • Evidence extraction module <br> • Draft review UI | • Kiểm tra metadata nền tảng được enrich đúng. <br> • Kiểm tra evidence snippet cho từng trường extraction. <br> • Kiểm tra fallback unknown khi thiếu evidence. |
| PP-03 | FR-08, FR-11, FR-12 | UC-01, UC-02 | • Draft workflow <br> • Publish workflow <br> • Metadata review interface <br> • Activity logging | • Kiểm tra tài liệu phải qua Draft trước khi Published. <br> • Kiểm tra activity log khi publish. <br> • Kiểm tra người dùng có thể chỉnh sửa metadata trước publish. |
| PP-04 | FR-06, FR-09, FR-10, FR-20, FR-22 | UC-01, UC-04 | • Canonical Document <br> • ExtractionRun cache <br> • Processing log <br> • Metrics collection module | • Upload lặp lại cùng một paper để kiểm tra cache hit. <br> • Đo số lần gọi LLM trước và sau caching. <br> • Kiểm tra log cache hit/cache miss. |
| PP-05 | FR-14, FR-15, FR-16 | UC-02 | • Search API <br> • Embedding service <br> • pgvector <br> • Search UI | • Thực hiện keyword search và semantic search trên tập tài liệu mẫu. <br> • Đánh giá độ liên quan của kết quả trả về. |
| PP-06 | FR-17, FR-18 | UC-03 | • Citation graph UI <br> • Citation edge storage <br> • Graph rendering module | • Kiểm tra hiển thị node và edge. <br> • Kiểm tra fallback khi thiếu citation context. <br> • Kiểm tra thông tin citation type và strength. |
| PP-07 | FR-01, FR-03, FR-19, FR-20, FR-21, FR-22 | UC-02, UC-04 | • Google OAuth <br> • Admin dashboard <br> • Configuration module <br> • Activity log <br> • Telegram Bot integration | • Kiểm thử đăng nhập. <br> • Kiểm tra cấu hình hệ thống. <br> • Kiểm tra activity log và processing log. <br> • Kiểm tra gửi thông báo Telegram sau publish nếu được bật. |

## 3.5.3 Kết luận chương

Chương này đã trình bày đặc tả yêu cầu cho hệ thống quản lý và khai thác tài liệu nghiên cứu học thuật trong phạm vi một nhóm nghiên cứu nhỏ. Các yêu cầu được xây dựng dựa trên các pain point thực tế đã phân tích trước đó, đồng thời được giới hạn phù hợp với phạm vi MVP của Đồ án tốt nghiệp.

Phần đặc tả bao gồm các quy tắc nghiệp vụ cốt lõi, yêu cầu chức năng, yêu cầu phi chức năng, các use case chính, tiêu chí nghiệm thu và ma trận truy vết giữa pain point, thiết kế và kiểm thử. Cách tổ chức này giúp đảm bảo rằng mỗi chức năng được triển khai đều có mục tiêu rõ ràng, có thể kiểm chứng và phục vụ trực tiếp cho bài toán quản lý tri thức nghiên cứu.

Kết quả của chương này đóng vai trò làm cơ sở cho chương thiết kế hệ thống ở phần tiếp theo, bao gồm thiết kế kiến trúc tổng thể, thiết kế cơ sở dữ liệu, pipeline xử lý tài liệu, kiến trúc xử lý nền và các thành phần phục vụ semantic retrieval, canonical caching và citation graph.