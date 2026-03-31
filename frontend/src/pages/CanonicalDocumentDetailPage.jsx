import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getCanonicalDocumentDetail } from "../services/paperApi.js";
import { AppHeader } from "../components/AppHeader.jsx";

export function CanonicalDocumentDetailPage() {
  const { canonicalId } = useParams();
  const navigate = useNavigate();
  const [document, setDocument] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadDocument() {
      try {
        setLoading(true);
        setError("");
        const data = await getCanonicalDocumentDetail(canonicalId);
        setDocument(data);
      } catch (error) {
        setError(error.message || "Không thể tải thông tin canonical document");
        setDocument(null);
      } finally {
        setLoading(false);
      }
    }

    if (canonicalId) {
      loadDocument();
    }
  }, [canonicalId]);

  function formatDate(dateString) {
    if (!dateString) return "-";
    const date = new Date(dateString);
    return date.toLocaleDateString("vi-VN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function formatAuthors(authorsJson) {
    if (!authorsJson) return "-";
    try {
      const authors = typeof authorsJson === 'string' ? JSON.parse(authorsJson) : authorsJson;
      if (Array.isArray(authors)) {
        // Extract name from each author object
        return authors.map(author => author.name || author).join(", ");
      }
      return authors;
    } catch (error) {
      return authorsJson;
    }
  }

  function formatMetadataSource(source) {
    if (!source) return "-";
    if (source === "semantic_scholar") return "Semantic Scholar";
    return source;
  }

  function getBadgeColor(status) {
    switch (status) {
      case "matched":
        return "#22c55e";
      case "unmatched":
        return "#f59e0b";
      case "error":
        return "#ef4444";
      default:
        return "#22c55e"; // Default to green for enriched/matched
    }
  }

  if (loading) {
    return (
      <div className="app-shell">
        <AppHeader 
          title="Canonical Document Detail"
          subtitle="Chi tiết tài liệu canonical"
        />

        <main className="app-main app-main--papers">
          <div className="app-main__full">
            <div className="card" style={{ padding: "2rem", textAlign: "center" }}>
              Đang tải thông tin canonical document...
            </div>
          </div>
        </main>
      </div>
    );
  }

  if (error) {
    return (
      <div className="app-shell">
        <AppHeader 
          title="Canonical Document Detail"
          subtitle="Chi tiết tài liệu canonical"
        />

        <main className="app-main app-main--papers">
          <div className="app-main__full">
            <div className="card" style={{ padding: "2rem", textAlign: "center", color: "#dc2626" }}>
              {error}
              <div style={{ marginTop: "1rem" }}>
                <button
                  className="btn btn--secondary"
                  onClick={() => navigate("/canonical")}
                >
                  Quay lại danh sách
                </button>
              </div>
            </div>
          </div>
        </main>
      </div>
    );
  }

  if (!document) {
    return (
      <div className="app-shell">
        <AppHeader 
          title="Canonical Document Detail"
          subtitle="Chi tiết tài liệu canonical"
        />

        <main className="app-main app-main--papers">
          <div className="app-main__full">
            <div className="card" style={{ padding: "2rem", textAlign: "center" }}>
              Không tìm thấy canonical document
              <div style={{ marginTop: "1rem" }}>
                <button
                  className="btn btn--secondary"
                  onClick={() => navigate("/canonical")}
                >
                  Quay lại danh sách
                </button>
              </div>
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <AppHeader 
        title="Canonical Document Detail"
        subtitle="Chi tiết tài liệu canonical"
      />

      <main className="app-main app-main--papers">
        <div className="app-main__full">
          <section className="card">
            <header className="card__header">
              <div>
                <h2 className="card__title">Chi tiết Canonical Document</h2>
                <p className="card__subtitle">
                  ID: {document.id}
                </p>
              </div>
              <button
                className="btn btn--secondary"
                onClick={() => navigate("/canonical")}
              >
                Quay lại danh sách
              </button>
            </header>

            <div className="detail-grid">
              {/* Basic Information */}
              <div className="detail-section">
                <h3 className="detail-section__title">Thông tin cơ bản</h3>
                <dl className="detail-list">
                  <div className="detail-list__item">
                    <dt>ID:</dt>
                    <dd>{document.id}</dd>
                  </div>
                  <div className="detail-list__item">
                    <dt>Canonical Key:</dt>
                    <dd style={{ fontFamily: "monospace", fontSize: "0.9rem" }}>
                      {document.canonical_key || "-"}
                    </dd>
                  </div>
                  <div className="detail-list__item">
                    <dt>Canonical Type:</dt>
                    <dd>
                      <span
                        style={{
                          backgroundColor: "#f3f4f6",
                          padding: "0.25rem 0.5rem",
                          borderRadius: "4px",
                          fontSize: "0.8rem",
                          textTransform: "uppercase"
                        }}
                      >
                        {document.canonical_type || "-"}
                      </span>
                    </dd>
                  </div>
                  <div className="detail-list__item">
                    <dt>Fingerprint:</dt>
                    <dd style={{ fontFamily: "monospace", fontSize: "0.9rem" }}>
                      {document.fingerprint || "-"}
                    </dd>
                  </div>
                </dl>
              </div>

              {/* Title Information */}
              <div className="detail-section">
                <h3 className="detail-section__title">Thông tin tiêu đề</h3>
                <dl className="detail-list">
                  <div className="detail-list__item">
                    <dt>Title Candidate:</dt>
                    <dd>{document.title_candidate || "-"}</dd>
                  </div>
                  <div className="detail-list__item">
                    <dt>Title:</dt>
                    <dd>{document.title || "-"}</dd>
                  </div>
                  <div className="detail-list__item">
                    <dt>Abstract:</dt>
                    <dd style={{ maxWidth: "600px", whiteSpace: "pre-wrap" }}>
                      {document.abstract || "-"}
                    </dd>
                  </div>
                </dl>
              </div>

              {/* Publication Information */}
              <div className="detail-section">
                <h3 className="detail-section__title">Thông tin xuất bản</h3>
                <dl className="detail-list">
                  <div className="detail-list__item">
                    <dt>DOI:</dt>
                    <dd>
                      {document.doi ? (
                        <a
                          href={`https://doi.org/${document.doi}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ color: "#4f46e5", textDecoration: "none" }}
                        >
                          {document.doi}
                        </a>
                      ) : "-"}
                    </dd>
                  </div>
                  <div className="detail-list__item">
                    <dt>Venue:</dt>
                    <dd>{document.venue || "-"}</dd>
                  </div>
                  <div className="detail-list__item">
                    <dt>Publication Year:</dt>
                    <dd>{document.publication_year || "-"}</dd>
                  </div>
                  <div className="detail-list__item">
                    <dt>Authors:</dt>
                    <dd style={{ maxWidth: "600px" }}>
                      {formatAuthors(document.authors_json)}
                    </dd>
                  </div>
                </dl>
              </div>

              {/* Status Information */}
              <div className="detail-section">
                <h3 className="detail-section__title">Trạng thái</h3>
                <dl className="detail-list">
                  <div className="detail-list__item">
                    <dt>Enrichment Status:</dt>
                    <dd>
                      <span
                        style={{
                          backgroundColor: getBadgeColor(document.enrichment_status),
                          color: "white",
                          padding: "0.25rem 0.5rem",
                          borderRadius: "4px",
                          fontSize: "0.8rem",
                          textTransform: "uppercase"
                        }}
                      >
                        {document.enrichment_status || "-"}
                      </span>
                    </dd>
                  </div>
                  <div className="detail-list__item">
                    <dt>Match Status:</dt>
                    <dd>
                      <span
                        style={{
                          backgroundColor: getBadgeColor(document.match_status),
                          color: "white",
                          padding: "0.25rem 0.5rem",
                          borderRadius: "4px",
                          fontSize: "0.8rem",
                          textTransform: "uppercase"
                        }}
                      >
                        {document.match_status || "-"}
                      </span>
                    </dd>
                  </div>
                  <div className="detail-list__item">
                    <dt>Metadata Source:</dt>
                    <dd>{formatMetadataSource(document.metadata_source)}</dd>
                  </div>
                  <div className="detail-list__item">
                    <dt>Sematic Scholar Paper ID:</dt>
                    <dd>{document.ss_paper_id || "-"}</dd>
                  </div>
                  <div className="detail-list__item">
                    <dt>Sematic Scholar Match Confidence:</dt>
                    <dd>{document.ss_match_confidence || "-"}</dd>
                  </div>
                </dl>
              </div>

              {/* Timestamp Information */}
              <div className="detail-section">
                <h3 className="detail-section__title">Thời gian</h3>
                <dl className="detail-list">
                  <div className="detail-list__item">
                    <dt>Ngày tạo:</dt>
                    <dd>{formatDate(document.created_at)}</dd>
                  </div>
                  <div className="detail-list__item">
                    <dt>Ngày cập nhật:</dt>
                    <dd>{formatDate(document.updated_at)}</dd>
                  </div>
                </dl>
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
