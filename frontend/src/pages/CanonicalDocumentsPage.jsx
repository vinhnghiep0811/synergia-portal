import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { getCanonicalDocuments, getCanonicalDocumentDetail } from "../services/paperApi.js";
import { AppHeader } from "../components/AppHeader.jsx";

export function CanonicalDocumentsPage() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchText, setSearchText] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [sortOrder, setSortOrder] = useState("newest"); // "newest" or "oldest"
  const itemsPerPage = 5;
  const navigate = useNavigate();

  const filteredDocuments = documents.filter(doc => 
    !searchText || 
    (doc.title && doc.title_candidate.toLowerCase().includes(searchText.toLowerCase())) ||
    (doc.doi && doc.doi.toLowerCase().includes(searchText.toLowerCase())) ||
    (doc.authors && doc.authors.some(author => author.toLowerCase().includes(searchText.toLowerCase()))) ||
    (doc.venue && doc.venue.toLowerCase().includes(searchText.toLowerCase())) ||
    (doc.canonical_key && doc.canonical_key.toLowerCase().includes(searchText.toLowerCase()))
  );

  const sortedDocuments = [...filteredDocuments].sort((a, b) => {
    const dateA = new Date(a.created_at || 0);
    const dateB = new Date(b.created_at || 0);
    return sortOrder === "newest" ? dateB - dateA : dateA - dateB;
  });

  const totalPages = Math.ceil(sortedDocuments.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const paginatedDocuments = sortedDocuments.slice(startIndex, endIndex);

  useEffect(() => {
    async function loadDocuments() {
      try {
        setLoading(true);
        setError("");
        const data = await getCanonicalDocuments(0, 100); // Get more for better pagination
        
        // Fetch details for each canonical document to get complete information
        const documentsWithDetails = await Promise.all(
          data.map(async (doc) => {
            try {
              const detail = await getCanonicalDocumentDetail(doc.id);
              return {
                ...doc,
                title: detail.title_candidate || doc.title,
                authors: detail.authors || doc.authors,
                venue: detail.venue || doc.venue,
                year: detail.publication_year || doc.year,
                doi: detail.doi || doc.doi,
                paper_count: detail.paper_count || doc.paper_count,
                created_at: detail.created_at || doc.created_at
              };
            } catch (error) {
              console.warn(`Failed to fetch details for canonical document ${doc.id}:`, error);
              return doc; // Keep original if detail fetch fails
            }
          })
        );
        
        setDocuments(documentsWithDetails);
      } catch (error) {
        setError(error.message || "Không thể tải danh sách canonical documents");
        setDocuments([]);
      } finally {
        setLoading(false);
      }
    }

    loadDocuments();
  }, []);

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

  function generatePaginationNumbers(currentPage, totalPages) {
    const maxVisible = 5;
    const numbers = [];
    
    if (totalPages <= maxVisible) {
      for (let i = 1; i <= totalPages; i++) {
        numbers.push(i);
      }
    } else {
      if (currentPage <= 3) {
        for (let i = 1; i <= 4; i++) {
          numbers.push(i);
        }
        numbers.push('...');
        numbers.push(totalPages);
      } else if (currentPage >= totalPages - 2) {
        numbers.push(1);
        numbers.push('...');
        for (let i = totalPages - 3; i <= totalPages; i++) {
          numbers.push(i);
        }
      } else {
        numbers.push(1);
        numbers.push('...');
        numbers.push(currentPage - 1);
        numbers.push(currentPage);
        numbers.push(currentPage + 1);
        numbers.push('...');
        numbers.push(totalPages);
      }
    }
    
    return numbers;
  }

  return (
    <div className="app-shell">
      <AppHeader 
        title="Tài liệu chuẩn hóa"
        subtitle="Quản lý và xem các tài liệu chuẩn hóa đã được trích xuất."
      />

      <main className="app-main app-main--papers">
        <div className="app-main__full">
          <section className="card list-card">
            <header className="card__header card__header--with-actions">
              <div>
                <h2 className="card__title">Danh sách tài liệu chuẩn hóa</h2>
                <p className="card__subtitle">
                  Tổng số: {documents.length} tài liệu chuẩn hóa
                </p>
              </div>
              <div className="list-filters">
                <input
                  type="search"
                  placeholder="Tìm kiếm theo tiêu đề, DOI, tác giả, venue..."
                  value={searchText}
                  onChange={(e) => setSearchText(e.target.value)}
                />
              </div>
            </header>

            {/* Sorting controls */}
            <div style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: "1rem",
            }}>
              <div style={{
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
              }}>
                <div
                  style={{
                    width: "8px",
                    height: "8px",
                    borderRadius: "999px",
                    backgroundColor: "#22c55e",
                  }}
                />
                <h3 style={{
                  fontSize: "0.95rem",
                  fontWeight: "600",
                  margin: 0,
                  color: "#374151",
                }}>
                  Hiển thị ({startIndex + 1}-{Math.min(endIndex, sortedDocuments.length)} / {sortedDocuments.length})
                </h3>
              </div>
              
              <div className="sort-controls">
                <button
                  className={`sort-btn ${sortOrder === "newest" ? "sort-btn--active" : ""}`}
                  onClick={() => {
                    if (sortOrder !== "newest") {
                      setSortOrder("newest");
                      setCurrentPage(1);
                    }
                  }}
                >
                  Mới nhất
                </button>
                <button
                  className={`sort-btn ${sortOrder === "oldest" ? "sort-btn--active" : ""}`}
                  onClick={() => {
                    if (sortOrder !== "oldest") {
                      setSortOrder("oldest");
                      setCurrentPage(1);
                    }
                  }}
                >
                  Cũ nhất
                </button>
              </div>
            </div>

            {loading ? (
              <div className="card" style={{ padding: "1rem" }}>
                Đang tải danh sách canonical documents...
              </div>
            ) : error ? (
              <div className="card" style={{ padding: "1rem", color: "#dc2626" }}>
                {error}
              </div>
            ) : paginatedDocuments.length === 0 ? (
              <div style={{ textAlign: "center", padding: "2rem", color: "#6b7280" }}>
                {searchText ? "Không tìm thấy canonical documents phù hợp." : "Không có canonical documents nào."}
              </div>
            ) : (
              <div className="table-wrapper">
                <table className="paper-table">
                  <thead>
                    <tr>
                      <th>Tiêu đề</th>
                      <th>Venue</th>
                      <th>DOI</th>
                      <th>Ngày tạo</th>
                      <th>Papers</th>
                      <th style={{ whiteSpace: "nowrap" }}>Chi tiết</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedDocuments.map((doc) => (
                      <tr key={doc.id} className="paper-row">
                        <td className="paper-title-cell">
                          <div className="paper-title-main">
                            {doc.title || "Không có tiêu đề"}
                          </div>
                          {doc.venue && <div className="paper-title-sub">{doc.venue}</div>}
                        </td>
                        <td>{doc.venue || "-"}</td>
                        <td>
                          {doc.doi ? (
                            <a 
                              href={`https://doi.org/${doc.doi}`} 
                              target="_blank" 
                              rel="noopener noreferrer"
                              style={{ color: "#4f46e5", textDecoration: "none" }}
                            >
                              {doc.doi}
                            </a>
                          ) : "-"}
                        </td>
                        <td>{formatDate(doc.created_at)}</td>
                        <td>
                          <span style={{ 
                            backgroundColor: "#f3f4f6", 
                            padding: "0.25rem 0.5rem", 
                            borderRadius: "4px", 
                            fontSize: "0.8rem",
                            color: "#6b7280"
                          }}>
                            {doc.paper_count || 0} papers
                          </span>
                        </td>
                        <td style={{ whiteSpace: "nowrap" }}>
                          <button
                            style={{
                              background: "none",
                              border: "none",
                              color: "#4f46e5",
                              textDecoration: "underline",
                              cursor: "pointer",
                              fontSize: "0.9rem",
                              padding: 0
                            }}
                            onClick={() => navigate(`/canonical/${doc.id}`)}
                          >
                            Chi tiết
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="pagination">
                <button
                  className="pagination__btn pagination__btn--arrow"
                  disabled={currentPage === 1}
                  onClick={() => {
                    if (currentPage > 1) {
                      setCurrentPage(currentPage - 1);
                    }
                  }}
                >
                  ←
                </button>
                <div className="pagination__numbers">
                  {generatePaginationNumbers(currentPage, totalPages).map((num, index) => (
                    num === '...' ? (
                      <span key={`ellipsis-${index}`} className="pagination__ellipsis">...</span>
                    ) : (
                      <button
                        key={num}
                        className={`pagination__btn pagination__btn--number ${currentPage === num ? 'pagination__btn--active' : ''}`}
                        onClick={() => {
                          if (currentPage !== num) {
                            setCurrentPage(num);
                          }
                        }}
                      >
                        {num}
                      </button>
                    )
                  ))}
                </div>
                <button
                  className="pagination__btn pagination__btn--arrow"
                  disabled={currentPage === totalPages}
                  onClick={() => {
                    if (currentPage < totalPages) {
                      setCurrentPage(currentPage + 1);
                    }
                  }}
                >
                  →
                </button>
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}
