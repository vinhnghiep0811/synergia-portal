import { PaperStatusBadge } from "./PaperStatusBadge.jsx";
import { formatDate } from "../utils/formatDate.js";

export function PaperDetail({ paper }) {
  if (!paper) {
    return (
      <section className="card detail-card">
        <header className="card__header">
          <h2 className="card__title">Paper detail</h2>
          <p className="card__subtitle">
            Chọn một paper ở bảng bên trái để xem chi tiết.
          </p>
        </header>
      </section>
    );
  }

  return (
    <section className="card detail-card">
      <header className="card__header">
        <div>
          <h2 className="card__title">
            {paper.status === "pending" 
              ? paper.originalFilename || paper.filename || "Unknown file"
              : paper.title || "Đang xử lý..."
            }
          </h2>
          <p className="card__subtitle">
            {paper.status === "pending" 
              ? "File đang chờ xử lý"
              : `${(paper.authors || []).join(", ")} · ${paper.year} · ${paper.venue || "Unknown venue"}`
            }
          </p>
        </div>
        <PaperStatusBadge status={paper.status} />
      </header>

      <div className="detail-grid">
        <div className="detail-section">
          <h3 className="detail-section__title">
            {paper.status === "pending" ? "Thông tin file" : "Upload & lưu trữ"}
          </h3>
          <dl className="detail-list">
            <div className="detail-list__item">
              <dt>ID</dt>
              <dd>{paper.id}</dd>
            </div>
            <div className="detail-list__item">
              <dt>Tên file</dt>
              <dd>{paper.originalFilename || paper.filename || "Unknown file"}</dd>
            </div>
            <div className="detail-list__item">
              <dt>Trạng thái</dt>
              <dd><PaperStatusBadge status={paper.status} /></dd>
            </div>
            <div className="detail-list__item">
              <dt>Kích thước</dt>
              <dd>{paper.sizeMB?.toFixed(1)} MB</dd>
            </div>
            <div className="detail-list__item">
              <dt>Upload lúc</dt>
              <dd>{formatDate(paper.uploadedAt)}</dd>
            </div>
            {paper.status !== "pending" && (
              <>
                <div className="detail-list__item">
                  <dt>Uploaded by</dt>
                  <dd>{paper.uploadedBy || "-"}</dd>
                </div>
                <div className="detail-list__item">
                  <dt>Storage path</dt>
                  <dd>/papers/{paper.id}.pdf</dd>
                </div>
              </>
            )}
          </dl>
        </div>

        {paper.status !== "pending" && (
          <>
            <div className="detail-section">
              <h3 className="detail-section__title">Thông tin tài liệu</h3>
              <dl className="detail-list">
                <div className="detail-list__item">
                  <dt>Tiêu đề</dt>
                  <dd>{paper.title || "-"}</dd>
                </div>
                <div className="detail-list__item">
                  <dt>Tác giả</dt>
                  <dd>{(paper.authors || []).join(", ") || "-"}</dd>
                </div>
                <div className="detail-list__item">
                  <dt>Năm</dt>
                  <dd>{paper.year || "-"}</dd>
                </div>
                <div className="detail-list__item">
                  <dt>Kênh xuất bản</dt>
                  <dd>{paper.venue || "-"}</dd>
                </div>
              </dl>
            </div>

            <div className="detail-section">
              <h3 className="detail-section__title">Canonical document & metadata</h3>
              <dl className="detail-list">
                <div className="detail-list__item">
                  <dt>Canonical key</dt>
                  <dd>{paper.canonicalKey || "-"}</dd>
                </div>
                <div className="detail-list__item">
                  <dt>Deterministic parse</dt>
                  <dd>{paper.hasDeterministicParse ? "Đã parse" : "Chưa parse"}</dd>
                </div>
                <div className="detail-list__item">
                  <dt>Semantic Scholar metadata</dt>
                  <dd>{paper.hasCanonicalMetadata ? "Đã đồng bộ" : "Chưa có"}</dd>
                </div>
                <div className="detail-list__item">
                  <dt>LLM extraction</dt>
                  <dd>{paper.hasLLMExtraction ? "Đã trích xuất & cache" : "Chưa có"}</dd>
                </div>
              </dl>
            </div>
          </>
        )}
      </div>

      <div className="detail-section">
        <h3 className="detail-section__title">Luồng xử lý tài liệu</h3>
        <ol className="timeline">
          <li className="timeline__item timeline__item--done">
            <div className="timeline__dot" />
            <div className="timeline__content">
              <div className="timeline__title">Uploaded</div>
              <div className="timeline__description">
                File đã được nhận và lưu vào storage.
              </div>
            </div>
          </li>
          <li
            className={
              paper.hasDeterministicParse
                ? "timeline__item timeline__item--done"
                : paper.status === "failed"
                ? "timeline__item timeline__item--failed"
                : "timeline__item timeline__item--pending"
            }
          >
            <div className="timeline__dot" />
            <div className="timeline__content">
              <div className="timeline__title">PDF parsing (deterministic)</div>
              <div className="timeline__description">
                Trích xuất text, DOI, title candidate và fingerprint từ PDF.
              </div>
            </div>
          </li>
          <li
            className={
              paper.hasCanonicalMetadata
                ? "timeline__item timeline__item--done"
                : "timeline__item timeline__item--pending"
            }
          >
            <div className="timeline__dot" />
            <div className="timeline__content">
              <div className="timeline__title">
                Semantic Scholar canonical metadata
              </div>
              <div className="timeline__description">
                Lấy metadata nền tảng đáng tin cậy từ Semantic Scholar.
              </div>
            </div>
          </li>
          <li
            className={
              paper.hasLLMExtraction
                ? "timeline__item timeline__item--done"
                : "timeline__item timeline__item--pending"
            }
          >
            <div className="timeline__dot" />
            <div className="timeline__content">
              <div className="timeline__title">
                LLM metadata chuyên biệt + evidence
              </div>
              <div className="timeline__description">
                Trích xuất Problem / Method / Contribution / Limitation / Evaluation kèm evidence.
              </div>
            </div>
          </li>
        </ol>
      </div>
    </section>
  );
}

