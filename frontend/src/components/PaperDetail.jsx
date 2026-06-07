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

function getCrossrefStatusLabel(status) {
  switch (status) {
    case "verified": return "Verified";
    case "partial": return "Partial";
    case "weak": return "Weak";
    case "conflict": return "Conflict";
    case "not_found": return "Not found";
    case "rate_limited": return "Rate limited";
    case "error": return "Error";
    default: return "-";
  }
}

function formatCrossrefField(field) {
  if (!field) return "-";
  const score = field.score == null ? "" : ` (${Number(field.score).toFixed(3)})`;
  return `${field.status || "-"}${score}`;
}

function formatCrossrefValue(value) {
  if (value == null || value === "") return "-";
  if (Array.isArray(value)) {
    return value.length ? value.join(", ") : "-";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function CrossrefMetadataRow({ label, value, field }) {
  return (
    <div className="crossref-metadata__row">
      <dt>{label}</dt>
      <dd>
        <span className="crossref-metadata__value">{formatCrossrefValue(value)}</span>
        {field && (
          <span className={`crossref-metadata__status crossref-metadata__status--${field.status || "unknown"}`}>
            {formatCrossrefField(field)}
          </span>
        )}
      </dd>
    </div>
  );
}

function getSemanticStatusLabel(status) {
  switch (status) {
    case "enriched": return "Matched";
    case "unmatched": return "Unmatched";
    case "rate_limited": return "Rate limited";
    case "pending":
    case "enriching": return "Enriching";
    case "not_linked": return "Chua link canonical";
    default: return "Unclear";
  }
}

function getMatchTypeLabel(matchStatus) {
  switch (matchStatus) {
    case "matched_by_doi": return "Matched by DOI";
    case "matched_by_title": return "Matched by title";
    case "matched_by_crossref_doi": return "Matched by Crossref DOI";
    case "matched_by_crossref_title": return "Matched by Crossref title";
    case "matched_by_crossref": return "Matched by Crossref";
    case "unmatched": return "Unmatched";
    case "rate_limited": return "Rate limited";
    case "crossref_rate_limited": return "Crossref rate limited";
    default: return "-";
  }
}

function formatSemanticSource(source) {
  if (!source) return "-";
  if (source === "semantic_scholar") return "Semantic Scholar";
  if (source === "crossref") return "Crossref";
  return source;
}

function formatLLMProvider(provider, modelName) {
  const normalizedProvider = (provider || "").toLowerCase();
  const normalizedModel = (modelName || "").toLowerCase();

  if (normalizedProvider === "regex_parsing") return "Regex parsing";
  if (normalizedProvider === "gemini") return "Gemini";
  if (normalizedProvider === "ollama" && normalizedModel.includes("gemma")) {
    return "Gemma (Ollama)";
  }
  if (normalizedProvider === "ollama") return "Ollama";
  if (provider) return provider;
  if (normalizedModel.includes("gemini")) return "Gemini";
  if (normalizedModel.includes("gemma")) return "Gemma";
  return "-";
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
    paper.title ||
    paper.detectedTitle ||
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
  const crossrefMetadata =
    paper.crossrefMetadata || paper.crossrefVerification?.crossref_metadata || null;
  const crossrefFields = paper.crossrefVerification?.fields || {};

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
            <div className="detail-list__item">
              <dt>LLM provider</dt>
              <dd>{formatLLMProvider(paper.llmProvider, paper.llmModel)}</dd>
            </div>
            <div className="detail-list__item">
              <dt>LLM model</dt>
              <dd>{paper.llmModel || "-"}</dd>
            </div>
            <div className="detail-list__item">
              <dt>LLM run status</dt>
              <dd>{paper.llmRunStatus || "-"}</dd>
            </div>
            <div className="detail-list__item">
              <dt>Prompt version</dt>
              <dd>{paper.llmPromptVersion || "-"}</dd>
            </div>
            <div className="detail-list__item">
              <dt>Extraction run ID</dt>
              <dd>{paper.llmExtractionRunId || "-"}</dd>
            </div>
          </dl>
        </div>
      </div>

      <div className="detail-section semantic-section">
        <h3 className="detail-section__title">Metadata enrichment</h3>
        <div className="semantic-status-row">
          <span
            className={`semantic-status-badge semantic-status-badge--${paper.semanticScholarStatus || "unknown"}`}
          >
            {semanticStatus}
          </span>
          <span className="semantic-status-note">
            {paper.canonicalDocumentId
              ? "Canonical document enrich metadata status"
              : "Parsing and canonicalization completed. Ready to start enrichment."}
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
            <dd>{formatSemanticSource(paper.semanticSource)}</dd>
          </div>
          <div className="detail-list__item">
            <dt>Semantic Scholar paper ID</dt>
            <dd>{paper.ssPaperId || "-"}</dd>
          </div>
          <div className="detail-list__item">
            <dt>Crossref verification</dt>
            <dd>{getCrossrefStatusLabel(paper.crossrefMatchStatus)}</dd>
          </div>
          <div className="detail-list__item">
            <dt>Crossref confidence</dt>
            <dd>{formatMatchConfidence(paper.crossrefMatchConfidence)}</dd>
          </div>
        </dl>

        {paper.crossrefVerification?.fields && (
          <dl className="detail-list semantic-detail-list">
            <div className="detail-list__item">
              <dt>Crossref DOI</dt>
              <dd>{formatCrossrefField(paper.crossrefVerification.fields.doi)}</dd>
            </div>
            <div className="detail-list__item">
              <dt>Crossref title</dt>
              <dd>{formatCrossrefField(paper.crossrefVerification.fields.title)}</dd>
            </div>
            <div className="detail-list__item">
              <dt>Crossref authors</dt>
              <dd>{formatCrossrefField(paper.crossrefVerification.fields.authors)}</dd>
            </div>
            <div className="detail-list__item">
              <dt>Crossref year</dt>
              <dd>{formatCrossrefField(paper.crossrefVerification.fields.year)}</dd>
            </div>
            <div className="detail-list__item">
              <dt>Crossref venue</dt>
              <dd>{formatCrossrefField(paper.crossrefVerification.fields.venue)}</dd>
            </div>
            <div className="detail-list__item">
              <dt>Crossref abstract</dt>
              <dd>{formatCrossrefField(paper.crossrefVerification.fields.abstract)}</dd>
            </div>
          </dl>
        )}

        {crossrefMetadata && (
          <div className="crossref-metadata">
            <h4 className="semantic-metadata__title">Crossref returned metadata</h4>
            <dl className="crossref-metadata__list">
              <CrossrefMetadataRow
                label="DOI"
                value={crossrefMetadata.doi}
                field={crossrefFields.doi}
              />
              <CrossrefMetadataRow
                label="Title"
                value={crossrefMetadata.title}
                field={crossrefFields.title}
              />
              <CrossrefMetadataRow
                label="Authors"
                value={crossrefMetadata.authors}
                field={crossrefFields.authors}
              />
              <CrossrefMetadataRow
                label="Year"
                value={crossrefMetadata.year}
                field={crossrefFields.year}
              />
              <CrossrefMetadataRow
                label="Venue"
                value={crossrefMetadata.venue}
                field={crossrefFields.venue}
              />
              <CrossrefMetadataRow
                label="Abstract"
                value={crossrefMetadata.abstract}
                field={crossrefFields.abstract}
              />
              <CrossrefMetadataRow label="Type" value={crossrefMetadata.type} />
              <CrossrefMetadataRow label="URL" value={crossrefMetadata.url} />
            </dl>
          </div>
        )}

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
              ? "Semantic Scholar is rate limited. Please try again in a few minutes."
              : "There is no canonical metadata available to display. If the status is Unmatched, it means the system could not find a suitable matching result."}
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
