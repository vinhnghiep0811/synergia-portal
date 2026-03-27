import { PaperStatusBadge } from "./PaperStatusBadge.jsx";
import { ProcessingTimeline } from "./ProcessingTimeline.jsx";
import { formatDate } from "../utils/formatDate.js";

function formatSizeMB(sizeMB) {
  if (sizeMB == null || Number.isNaN(sizeMB)) return "-";
  return `${sizeMB.toFixed(1)} MB`;
}

function formatMatchConfidence(confidence) {
  if (confidence == null || confidence === "") return "-";
  const numeric = Number(confidence);
  if (Number.isNaN(numeric)) return String(confidence);
  return numeric.toFixed(3);
}

function getSemanticStatusLabel(status) {
  switch (status) {
    case "enriched":
      return "Matched";
    case "unmatched":
      return "Unmatched";
    case "rate_limited":
      return "Rate limited";
    case "pending":
    case "enriching":
      return "Dang enrich";
    case "not_linked":
      return "Chua link canonical";
    default:
      return "Khong ro";
  }
}

function getMatchTypeLabel(matchStatus) {
  switch (matchStatus) {
    case "matched_by_doi":
      return "Matched by DOI";
    case "matched_by_title":
      return "Matched by title";
    case "unmatched":
      return "Unmatched";
    case "rate_limited":
      return "Rate limited";
    default:
      return "-";
  }
}

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

  const displayTitle =
    paper.detectedTitle ||
    paper.title ||
    paper.originalFilename ||
    paper.filename ||
    "Unknown file";

  const subtitle =
    paper.status === "pending"
      ? "File đang chờ xử lý"
      : paper.detectedDoi
      ? `DOI: ${paper.detectedDoi}`
      : "Đã có thông tin chi tiết của tài liệu";

  const parseDisplay =
    paper.parseStatus === "done"
      ? "Đã parse thành công"
      : paper.parseStatus === "failed"
      ? "Parse thất bại"
      : "Chưa parse";

  const canonicalDisplay = paper.canonicalDocumentId ? "Đã liên kết" : "Chưa có";
  const semanticStatus = getSemanticStatusLabel(paper.semanticScholarStatus);
  const hasMatchedMetadata = paper.semanticScholarStatus === "enriched";
  const authorsDisplay = paper.canonicalAuthors?.length
    ? paper.canonicalAuthors.join(", ")
    : "-";

  return (
    <section className="card detail-card">
      <header className="card__header">
        <div>
          <h2 className="card__title">{displayTitle}</h2>
          <p className="card__subtitle">{subtitle}</p>
        </div>
        <PaperStatusBadge status={paper.status} />
      </header>

      <ProcessingTimeline paper={paper} />

      <div className="detail-grid">
        <div className="detail-section">
          <h3 className="detail-section__title">Thông tin file</h3>
          <dl className="detail-list">
            <div className="detail-list__item">
              <dt>ID</dt>
              <dd>{paper.id}</dd>
            </div>
            <div className="detail-list__item">
              <dt>Tên file</dt>
              <dd>{paper.originalFilename || paper.filename || "-"}</dd>
            </div>
            <div className="detail-list__item">
              <dt>Trạng thái</dt>
              <dd>
                <PaperStatusBadge status={paper.status} />
              </dd>
            </div>
            <div className="detail-list__item">
              <dt>Loại file</dt>
              <dd>{paper.mimeType || "-"}</dd>
            </div>
            <div className="detail-list__item">
              <dt>Kích thước</dt>
              <dd>{formatSizeMB(paper.sizeMB)}</dd>
            </div>
            <div className="detail-list__item">
              <dt>Upload lúc</dt>
              <dd>{paper.uploadedAt ? formatDate(paper.uploadedAt) : "-"}</dd>
            </div>
            <div className="detail-list__item">
              <dt>Cập nhật lúc</dt>
              <dd>{paper.updatedAt ? formatDate(paper.updatedAt) : "-"}</dd>
            </div>
            <div className="detail-list__item">
              <dt>Upload source</dt>
              <dd>{paper.uploadSource || "-"}</dd>
            </div>
          </dl>
        </div>

        <div className="detail-section">
          <h3 className="detail-section__title">Metadata trích xuất</h3>
          <dl className="detail-list">
            <div className="detail-list__item">
              <dt>Detected title</dt>
              <dd>{paper.detectedTitle || "-"}</dd>
            </div>
            <div className="detail-list__item">
              <dt>Detected DOI</dt>
              <dd>{paper.detectedDoi || "-"}</dd>
            </div>
            <div className="detail-list__item">
              <dt>Detected fingerprint</dt>
              <dd>{paper.detectedFingerprint || "-"}</dd>
            </div>
            <div className="detail-list__item">
              <dt>Parse status</dt>
              <dd>{parseDisplay}</dd>
            </div>
            <div className="detail-list__item">
              <dt>Parse error</dt>
              <dd>{paper.parseError || "-"}</dd>
            </div>
            <div className="detail-list__item">
              <dt>Canonical document</dt>
              <dd>{canonicalDisplay}</dd>
            </div>
            <div className="detail-list__item">
              <dt>Canonical document ID</dt>
              <dd>{paper.canonicalDocumentId || "-"}</dd>
            </div>
          </dl>
        </div>
      </div>

      <div className="detail-section semantic-section">
        <h3 className="detail-section__title">Semantic Scholar enrichment</h3>
        <div className="semantic-status-row">
          <span
            className={`semantic-status-badge semantic-status-badge--${paper.semanticScholarStatus || "unknown"}`}
          >
            {semanticStatus}
          </span>
          <span className="semantic-status-note">
            {paper.canonicalDocumentId
              ? "Trang thai enrich metadata cua canonical document"
              : "Can parse/canonicalize xong de bat dau enrich"}
          </span>
        </div>

        <dl className="detail-list semantic-detail-list">
          <div className="detail-list__item">
            <dt>Match type</dt>
            <dd>{getMatchTypeLabel(paper.matchStatus)}</dd>
          </div>
          <div className="detail-list__item">
            <dt>Match confidence</dt>
            <dd>{formatMatchConfidence(paper.ssMatchConfidence)}</dd>
          </div>
          <div className="detail-list__item">
            <dt>Metadata source</dt>
            <dd>{paper.semanticSource || "-"}</dd>
          </div>
          <div className="detail-list__item">
            <dt>Semantic Scholar paper ID</dt>
            <dd>{paper.ssPaperId || "-"}</dd>
          </div>
        </dl>

        {hasMatchedMetadata ? (
          <div className="semantic-metadata">
            <h4 className="semantic-metadata__title">Canonical metadata</h4>
            <dl className="detail-list semantic-detail-list">
              <div className="detail-list__item">
                <dt>Title</dt>
                <dd>{paper.canonicalTitle || paper.canonicalTitleCandidate || "-"}</dd>
              </div>
              <div className="detail-list__item">
                <dt>Publication year</dt>
                <dd>{paper.canonicalPublicationYear || "-"}</dd>
              </div>
              <div className="detail-list__item">
                <dt>Venue</dt>
                <dd>{paper.canonicalVenue || "-"}</dd>
              </div>
              <div className="detail-list__item">
                <dt>Authors</dt>
                <dd>{authorsDisplay}</dd>
              </div>
            </dl>

            {paper.canonicalAbstract && (
              <div className="semantic-abstract">
                <h5 className="semantic-abstract__title">Abstract</h5>
                <p className="semantic-abstract__content">{paper.canonicalAbstract}</p>
              </div>
            )}
          </div>
        ) : (
          <p className="semantic-empty-note">
            {paper.semanticScholarStatus === "rate_limited"
              ? "Semantic Scholar dang rate limit. Vui long thu lai sau 5 phut."
              : "Chua co metadata canonical de hien thi. Neu status la Unmatched thi he thong khong tim duoc ket qua phu hop."}
          </p>
        )}
      </div>

      {paper.extractedTextPreview && (
        <div className="detail-section">
          <h3 className="detail-section__title">Text preview</h3>
          <div
            style={{
              fontSize: "0.9rem",
              lineHeight: 1.6,
              color: "#374151",
              background: "#f9fafb",
              border: "1px solid #e5e7eb",
              borderRadius: "0.75rem",
              padding: "1rem",
              whiteSpace: "pre-wrap",
            }}
          >
            {paper.extractedTextPreview}
          </div>
        </div>
      )}
    </section>
  );
}
