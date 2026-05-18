import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { semanticSearch, keywordSearch } from "../services/searchApi.js";
import { AppHeader } from "../components/AppHeader.jsx";
import "../styles/SematicSearchPage.css";

export function SemanticSearchPage() {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [hasSearched, setHasSearched] = useState(false);
  const [expandedEvidence, setExpandedEvidence] = useState({});
  const [searchMode, setSearchMode] = useState("semantic"); // "semantic" or "keyword"
  const navigate = useNavigate();

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    try {
      setLoading(true);
      setError("");
      setHasSearched(true);
      
      let data;
      if (searchMode === "semantic") {
        data = await semanticSearch(query.trim(), topK);
      } else {
        data = await keywordSearch(query.trim(), topK);
      }
      
      // Sort by similarity_score descending
      const sortedResults = (data.results || []).sort((a, b) => (b.similarity_score || 0) - (a.similarity_score || 0));
      console.log(`🔍 ${searchMode} search results:`, sortedResults);
      setResults(sortedResults);
    } catch (err) {
      setError(err.message || "Tìm kiếm thất bại");
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setQuery("");
    setResults([]);
    setError("");
    setHasSearched(false);
    setExpandedEvidence({});
  };

  const toggleEvidence = (index) => {
    setExpandedEvidence(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };

  const getEvidenceContent = (content) => {
    if (!content) return "Không có evidence";
    const newlineIndex = content.indexOf('\n');
    if (newlineIndex === -1) return content;
    return content.slice(newlineIndex + 1).trim();
  };

  const getEvidenceSection = (content) => {
    if (!content) return null;
    const newlineIndex = content.indexOf('\n');
    if (newlineIndex === -1) return null;
    return content.slice(0, newlineIndex).trim();
  };

  return (
    <div className="app-shell">
      <AppHeader
        title={searchMode === "semantic" ? "Tìm kiếm ngữ nghĩa" : "Tìm kiếm từ khóa"}
        subtitle={searchMode === "semantic" ? "Tìm kiếm tài liệu dựa trên ý nghĩa ngữ cảnh." : "Tìm kiếm tài liệu dựa trên từ khóa chính xác."}
      />

      <main className="app-main app-main--papers">
        <div className="app-main__full">
          <section className="card list-card">
            <header className="card__header card__header--with-actions">
              <div>
                <h2 className="card__title">
                  {searchMode === "semantic" ? "Tìm kiếm ngữ nghĩa" : "Tìm kiếm từ khóa"}
                </h2>
                <p className="card__subtitle">
                  {searchMode === "semantic" 
                    ? "Nhập câu truy vấn để tìm các tài liệu liên quan theo ngữ nghĩa."
                    : "Nhập từ khóa để tìm các tài liệu chứa từ khóa chính xác."}
                </p>
              </div>
            </header>

            {/* Search Mode Toggle */}
            <div className="semantic-search-mode-group">
              <label className="semantic-search-label">
                Chế độ tìm kiếm
              </label>
              <div className="semantic-search-mode-toggle">
                <button
                  type="button"
                  className={`semantic-search-mode-button ${
                    searchMode === "semantic" ? "active" : ""
                  }`}
                  onClick={() => setSearchMode("semantic")}
                >
                  Tìm kiếm ngữ nghĩa
                </button>
                <button
                  type="button"
                  className={`semantic-search-mode-button ${
                    searchMode === "keyword" ? "active" : ""
                  }`}
                  onClick={() => setSearchMode("keyword")}
                >
                  Tìm kiếm từ khóa
                </button>
              </div>
            </div>

            {/* Search Form */}
            <form onSubmit={handleSearch} className="semantic-search-form">
              <div className="semantic-search-input-group">
                <label className="semantic-search-label">
                  {searchMode === "semantic" ? "Câu truy vấn" : "Từ khóa"}
                </label>
                <input
                  type="search"
                  placeholder={searchMode === "semantic" ? "Ví dụ: task planning in robotics..." : "Ví dụ: bio, machine learning..."}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="semantic-search-input"
                />
              </div>

              <div className="semantic-search-topk-group">
                <label className="semantic-search-label">
                  {searchMode === "semantic" ? "Top K" : "Số kết quả"}
                </label>
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={topK}
                  onChange={(e) => setTopK(parseInt(e.target.value) || 5)}
                  className="semantic-search-input"
                />
              </div>

              <div className="semantic-search-buttons">
                <button
                  type="submit"
                  className="semantic-search-button semantic-search-button--primary"
                  disabled={loading || !query.trim()}
                >
                  {loading ? "Đang tìm..." : "Tìm kiếm"}
                </button>

                {hasSearched && (
                  <button
                    type="button"
                    className="semantic-search-button semantic-search-button--secondary"
                    onClick={handleClear}
                  >
                    ✕ Xóa
                  </button>
                )}
              </div>
            </form>

            {/* Loading State */}
            {loading && (
              <div className="semantic-search-loading">
                <div className="semantic-search-spinner"></div>
                <span>Đang tìm kiếm tài liệu liên quan...</span>
              </div>
            )}

            {/* Error Message */}
            {error && (
              <div className="semantic-search-error">
                ⚠️ {error}
              </div>
            )}

            {/* Results */}
            {hasSearched && !loading && !error && (
              <div>
                {results.length === 0 ? (
                  <div className="semantic-search-empty">
                    <div className="semantic-search-empty-icon">
                      🔍
                    </div>
                    <h3 className="semantic-search-empty-title">
                      Không tìm thấy kết quả
                    </h3>
                    <p className="semantic-search-empty-text">
                      Thử thay đổi câu truy vấn hoặc tăng giá trị Top K.
                    </p>
                  </div>
                ) : (
                  <div>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "0.5rem",
                        marginBottom: "1rem",
                      }}
                    >
                      <div
                        style={{
                          width: "8px",
                          height: "8px",
                          borderRadius: "999px",
                          backgroundColor: "#22c55e",
                        }}
                      />
                      <h3
                        style={{
                          fontSize: "0.95rem",
                          fontWeight: "600",
                          margin: 0,
                          color: "#374151",
                        }}
                      >
                        Tìm thấy {results.length} kết quả
                      </h3>
                    </div>

                    <div className="table-wrapper">
                      <table className="paper-table">
                        <thead>
                          <tr>
                            <th style={{ width: "60px" }}>#</th>
                            <th>Tiêu đề</th>
                            <th style={{ width: "450px" }}>Bằng chứng</th>
                            <th>Độ tương đồng</th>
                            <th>Chi tiết</th>
                          </tr>
                        </thead>
                        <tbody>
                          {results.map((result, index) => (
                            <tr
                              key={result.document_id || index}
                              className="paper-row"
                            >
                              <td>
                                <span
                                  style={{
                                    display: "inline-flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    width: "28px",
                                    height: "28px",
                                    backgroundColor:
                                      index < 3 ? "#fbbf24" : "#e5e7eb",
                                    color: index < 3 ? "#92400e" : "#6b7280",
                                    borderRadius: "50%",
                                    fontSize: "0.75rem",
                                    fontWeight: "600",
                                  }}
                                >
                                  {index + 1}
                                </span>
                              </td>
                              <td className="paper-title-cell">
                                <div
                                  className="paper-title-main"
                                  style={{
                                    maxWidth: "400px",
                                    overflow: "hidden",
                                    textOverflow: "ellipsis",
                                    whiteSpace: "nowrap",
                                  }}
                                >
                                  {result.title || "Không có tiêu đề"}
                                </div>
                                {result.venue && (
                                  <div className="paper-title-sub">
                                    {result.venue}
                                  </div>
                                )}
                              </td>
                              <td>
                                <div className="semantic-search-evidence">
                                  {getEvidenceSection(result.content) && (
                                    <div className="semantic-search-evidence-section">
                                      {getEvidenceSection(result.content)}
                                    </div>
                                  )}
                                  <div
                                    className={`semantic-search-evidence-content ${
                                      expandedEvidence[index] ? 'expanded' : ''
                                    }`}
                                    title={getEvidenceContent(result.content)}
                                  >
                                    {getEvidenceContent(result.content)}
                                  </div>

                                  {getEvidenceContent(result.content).length > 180 && (
                                    <button
                                      onClick={() => toggleEvidence(index)}
                                      className={`semantic-search-evidence-toggle ${
                                        expandedEvidence[index] ? 'expanded' : ''
                                      }`}
                                    >
                                      {expandedEvidence[index] ? 'Thu gọn' : 'Xem thêm'}
                                    </button>
                                  )}
                                </div>
                              </td>
                              <td>
                                <span
                                  style={{
                                    display: "inline-flex",
                                    alignItems: "center",
                                    gap: "0.5rem",
                                    padding: "0.375rem 0.75rem",
                                    backgroundColor:
                                      result.similarity_score >= 0.8
                                        ? "#d1fae5"
                                        : result.similarity_score >= 0.6
                                        ? "#dbeafe"
                                        : "#f3f4f6",
                                    color:
                                      result.similarity_score >= 0.8
                                        ? "#065f46"
                                        : result.similarity_score >= 0.6
                                        ? "#1e40af"
                                        : "#4b5563",
                                    borderRadius: "999px",
                                    fontSize: "0.8rem",
                                    fontWeight: "600",
                                  }}
                                >
                                  <span
                                    style={{
                                      width: "6px",
                                      height: "6px",
                                      borderRadius: "50%",
                                      backgroundColor:
                                        result.similarity_score >= 0.8
                                          ? "#10b981"
                                          : result.similarity_score >= 0.6
                                          ? "#3b82f6"
                                          : "#9ca3af",
                                    }}
                                  />
                                  {(result.similarity_score * 100).toFixed(1)}%
                                </span>
                              </td>
                              <td>
                                <button
                                  style={{
                                    background: "none",
                                    border: "none",
                                    color: "#4f46e5",
                                    textDecoration: "underline",
                                    cursor: "pointer",
                                    fontSize: "0.9rem",
                                    padding: 0,
                                  }}
                                  onClick={() =>
                                    window.open(`/canonical/${result.canonical_document_id}`, '_blank', 'noopener,noreferrer')
                                  }
                                  disabled={!result.canonical_document_id}
                                >
                                  {result.canonical_document_id ? "Chi tiết" : "Không có ID"}
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {/* Score Legend */}
                    <div
                      style={{
                        display: "flex",
                        gap: "1rem",
                        marginTop: "1rem",
                        padding: "0.75rem",
                        backgroundColor: "#f9fafb",
                        borderRadius: "6px",
                        fontSize: "0.8rem",
                        color: "#6b7280",
                      }}
                    >
                      <span>Chú thích độ tương đồng:</span>
                      <span style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
                        <span
                          style={{
                            width: "8px",
                            height: "8px",
                            borderRadius: "50%",
                            backgroundColor: "#10b981",
                          }}
                        />
                        Cao (≥80%)
                      </span>
                      <span style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
                        <span
                          style={{
                            width: "8px",
                            height: "8px",
                            borderRadius: "50%",
                            backgroundColor: "#3b82f6",
                          }}
                        />
                        Trung bình (≥60%)
                      </span>
                      <span style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
                        <span
                          style={{
                            width: "8px",
                            height: "8px",
                            borderRadius: "50%",
                            backgroundColor: "#9ca3af",
                          }}
                        />
                        Thấp (&lt;60%)
                      </span>
                    </div>
                  </div>
                )}
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}
