import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PaperStatusBadge } from "./PaperStatusBadge.jsx";
import { CanonicalLink } from "./CanonicalLink.jsx";
import { getPaperFileViewUrl, getCanonicalDocumentByPaper } from "../services/paperApi.js";
import { formatDate } from "../utils/formatDate.js";

const actionButtonStyle = {
  fontSize: "0.8rem",
  padding: "0.2rem 0.4rem",
  textDecoration: "underline",
  background: "none",
  border: "none",
  cursor: "pointer",
};

export function PaperList({ papers, selectedId }) {
  const [searchText, setSearchText] = useState("");
  const [activeTab, setActiveTab] = useState("pending"); // "pending" or "processed"
  const [pendingPage, setPendingPage] = useState(1);
  const [processedPage, setProcessedPage] = useState(1);
  const [pendingSort, setPendingSort] = useState("newest"); // "newest" or "oldest"
  const [processedSort, setProcessedSort] = useState("newest"); // "newest" or "oldest"
  const itemsPerPage = 5;
  const navigate = useNavigate();

  // Debug: Log papers data
  console.log("PaperList received papers:", papers.map(p => ({
    id: p.id,
    
    processing_status: p.processing_status,
    publication_status: p.publication_status,
    processing_stage: p.processing_stage,
    originalFilename: p.originalFilename
  })));

  function openPaperPdf(event, paperId) {
    event.stopPropagation();
    window.open(getPaperFileViewUrl(paperId), "_blank");
  }

  const filtered = useMemo(() => {
    return papers.filter((p) => {
      // First filter by active tab
      const isInPendingTab = activeTab === "pending" && (
        p.processing_status === "pending"
      );
      const isInProcessedTab = activeTab === "processed" && (
        p.processing_status === "processed" || p.processing_status === "completed" || p.processing_status === "failed"
      );
      
      if (!isInPendingTab && !isInProcessedTab) return false;

      // Then apply search filter
      const textMatch =
        !searchText ||
        (activeTab === "pending" &&
          (p.originalFilename || p.filename || "")
            .toLowerCase()
            .includes(searchText.toLowerCase())) ||
        (activeTab === "processed" &&
          (
            ((p.detectedTitle || p.title || "") && (p.detectedTitle || p.title || "")
              .toLowerCase()
              .includes(searchText.toLowerCase())) ||
            (p.detectedDoi && p.detectedDoi !== null && p.detectedDoi !== undefined && (
              console.log(`Checking DOI search: searching for "${searchText}" in DOI "${p.detectedDoi}"`),
              p.detectedDoi.toLowerCase().includes(searchText.toLowerCase()) ||
              // Handle DOI format like "10.1234/example" when user searches "1234" or "example"
              (searchText.match(/^\d+$/) && p.detectedDoi.includes(`10.${searchText}/`)) ||
              (searchText.includes('.') && p.detectedDoi.includes(searchText))
            )) ||
            (p.authors &&
              p.authors.join(", ").toLowerCase().includes(searchText.toLowerCase())) ||
            (p.canonicalKey || "").toLowerCase().includes(searchText.toLowerCase()) ||
            p.id.toLowerCase().includes(searchText.toLowerCase())
          )
        );

      return textMatch;
    });
  }, [papers, searchText, activeTab]);

  // Sort by upload date (newest first) and paginate
  const sortedFiltered = useMemo(() => {
    return [...filtered].sort((a, b) => {
      const dateA = new Date(a.uploadedAt || 0);
      const dateB = new Date(b.uploadedAt || 0);
      
      // Use appropriate sort based on active tab
      if (activeTab === "pending") {
        return pendingSort === "newest" ? dateB - dateA : dateA - dateB;
      } else if (activeTab === "processed") {
        return processedSort === "newest" ? dateB - dateA : dateA - dateB;
      }
      
      // Default: newest first
      return dateB - dateA;
    });
  }, [filtered, activeTab, pendingSort, processedSort]);

  const paginatedPending = useMemo(() => {
    const pending = sortedFiltered.filter(p => 
      p.processing_status === "pending" ||
      p.processing_status === "parse_queued" ||
      p.processing_status === "canonicalized"
    );
    const startIndex = (pendingPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    return pending.slice(startIndex, endIndex);
  }, [sortedFiltered, pendingPage]);

  const paginatedProcessed = useMemo(() => {
    const processed = sortedFiltered.filter(p => 
      p.processing_status === "processed" || 
      p.processing_status === "completed" || 
      p.processing_status === "failed" ||
      p.processing_status === "duplicate_detected"
    );
    const startIndex = (processedPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    return processed.slice(startIndex, endIndex);
  }, [sortedFiltered, processedPage]);

  const totalPendingPages = useMemo(() => {
    const pending = sortedFiltered.filter(p => 
      p.processing_status === "pending" ||
      p.processing_status === "parse_queued" ||
      p.processing_status === "canonicalized"
    );
    return Math.ceil(pending.length / itemsPerPage);
  }, [sortedFiltered]);

  const totalProcessedPages = useMemo(() => {
    const processed = sortedFiltered.filter(p => 
      p.processing_status === "processed" || 
      p.processing_status === "completed" || 
      p.processing_status === "failed" ||
      p.processing_status === "duplicate_detected"
    );
    return Math.ceil(processed.length / itemsPerPage);
  }, [sortedFiltered]);

  // Generate pagination numbers with ellipsis
  const generatePaginationNumbers = (currentPage, totalPages) => {
    const maxVisible = 5; // Maximum visible page numbers
    const numbers = [];
    
    if (totalPages <= maxVisible) {
      // Show all pages if total is small
      for (let i = 1; i <= totalPages; i++) {
        numbers.push(i);
      }
    } else {
      // Show first, current, last with ellipsis
      if (currentPage <= 3) {
        // Show 1,2,3,4,...,last
        for (let i = 1; i <= 4; i++) {
          numbers.push(i);
        }
        numbers.push('...');
        numbers.push(totalPages);
      } else if (currentPage >= totalPages - 2) {
        // Show 1,...,last-3,last-2,last-1,last
        numbers.push(1);
        numbers.push('...');
        for (let i = totalPages - 3; i <= totalPages; i++) {
          numbers.push(i);
        }
      } else {
        // Show 1,...,current-1,current,current+1,...,last
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
  };

  return (
    <section className="card list-card">
      <header className="card__header card__header--with-actions">
        <div>
          <h2 className="card__title">Danh sách tài liệu nghiên cứu</h2>
          <p className="card__subtitle">
            Quản lý và theo dõi trạng thái xử lý của các tài liệu học thuật.
          </p>
        </div>
        <div className="list-filters">
          <input
            type="search"
            placeholder={
              activeTab === "pending" 
                ? "Tìm kiếm theo tên file gốc" 
                : "Tìm kiếm theo tiêu đề, DOI"
            }
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
          />
        </div>
      </header>

      {/* Tabs */}
      <div className="tabs">
        <button
          className={`tab ${activeTab === "pending" ? "tab--active" : ""}`}
          onClick={() => setActiveTab("pending")}
        >
          <div className="tab__indicator tab__indicator--pending"></div>
          Đang xử lý
        </button>
        <button
          className={`tab ${activeTab === "processed" ? "tab--active" : ""}`}
          onClick={() => setActiveTab("processed")}
        >
          <div className="tab__indicator tab__indicator--processed"></div>
          Đã xử lý
        </button>
      </div>

      {/* Content based on active tab */}
      {activeTab === "pending" && paginatedPending.length > 0 && (
        <div style={{ marginBottom: "2rem" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: "1rem",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
              }}
            >
              <div
                style={{
                  width: "8px",
                  height: "8px",
                  borderRadius: "999px",
                  backgroundColor: "#f59e0b",
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
                Đang chờ xử lý ({(pendingPage - 1) * itemsPerPage + 1}-{Math.min(pendingPage * itemsPerPage, sortedFiltered.filter(p => 
                  p.processing_status === "pending" ||
                  p.processing_status === "parse_queued" ||
                  p.processing_status === "canonicalized"
                ).length)} / {sortedFiltered.filter(p => 
                  p.processing_status === "pending" ||
                  p.processing_status === "parse_queued" ||
                  p.processing_status === "canonicalized"
                ).length})
              </h3>
            </div>
            
            {/* Sorting controls for pending papers */}
            <div className="sort-controls">
              <button
                className={`sort-btn ${pendingSort === "newest" ? "sort-btn--active" : ""}`}
                onClick={() => {
                  if (pendingSort !== "newest") {
                    setPendingSort("newest");
                    setPendingPage(1); // Reset to first page when sorting changes
                  }
                }}
              >
                Gần nhất
              </button>
              <button
                className={`sort-btn ${pendingSort === "oldest" ? "sort-btn--active" : ""}`}
                onClick={() => {
                  if (pendingSort !== "oldest") {
                    setPendingSort("oldest");
                    setPendingPage(1); // Reset to first page when sorting changes
                  }
                }}
              >
                Lâu nhất
              </button>
            </div>
          </div>

          <div className="table-wrapper">
            <table className="paper-table">
              <thead>
                <tr>
                  <th>Mã</th>
                  <th>Tệp</th>
                  <th>Dung lượng</th>
                  <th>Tải lên</th>
                  <th>Canonical</th>
                  <th>Chi tiết</th>
                  <th>Xem PDF</th>
                </tr>
              </thead>
              <tbody>
                {paginatedPending.map((paper) => (
                  <tr
                    key={paper.id}
                    className={
                      paper.id === selectedId
                        ? "paper-row paper-row--selected"
                        : "paper-row"
                    }
                    style={{ cursor: "pointer" }}
                    onClick={() => navigate(`/papers/${paper.id}`)}
                  >
                    <td>
                      <div className="simple-list-id">{paper.id}</div>
                    </td>
                    <td className="paper-title-cell" style={{ maxWidth: "250px", wordWrap: "break-word", whiteSpace: "normal", overflow: "hidden", textOverflow: "ellipsis" }}>
                      <div className="paper-title-main" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {paper.originalFilename || paper.filename || "Unknown file"}
                      </div>
                    </td>
                    <td>{paper.sizeMB != null ? `${paper.sizeMB.toFixed(1)} MB` : "-"}</td>
                    <td>{paper.uploadedAt ? formatDate(paper.uploadedAt) : "-"}</td>
                    <td>
                      <CanonicalLink paperId={paper.id} />
                    </td>
                    <td>
                      <button
                        className="btn btn--link"
                        style={{ ...actionButtonStyle, color: "#4f46e5" }}
                        onClick={(event) => {
                          event.stopPropagation();
                          navigate(`/papers/${paper.id}`);
                        }}
                      >
                        Xem
                      </button>
                    </td>
                    <td>
                      <button
                        className="btn btn--link"
                        style={{ ...actionButtonStyle, color: "#0f766e" }}
                        onClick={(event) => openPaperPdf(event, paper.id)}
                      >
                        PDF
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination for pending */}
          {totalPendingPages > 1 && (
            <div className="pagination">
              <button
                className="pagination__btn pagination__btn--arrow"
                disabled={pendingPage === 1}
                onClick={() => {
                  if (pendingPage > 1) {
                    setPendingPage(pendingPage - 1);
                  }
                }}
              >
                ←
              </button>
              <div className="pagination__numbers">
                {generatePaginationNumbers(pendingPage, totalPendingPages).map((num, index) => (
                  num === '...' ? (
                    <span key={`ellipsis-${index}`} className="pagination__ellipsis">...</span>
                  ) : (
                    <button
                      key={num}
                      className={`pagination__btn pagination__btn--number ${pendingPage === num ? 'pagination__btn--active' : ''}`}
                      onClick={() => {
                        if (pendingPage !== num) {
                          setPendingPage(num);
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
                disabled={pendingPage === totalPendingPages}
                onClick={() => {
                  if (pendingPage < totalPendingPages) {
                    setPendingPage(pendingPage + 1);
                  }
                }}
              >
                →
              </button>
            </div>
          )}
        </div>
      )}

      {/* Empty state for pending tab */}
      {activeTab === "pending" && paginatedPending.length === 0 && (
        <div style={{ 
          padding: "3rem", 
          textAlign: "center", 
          backgroundColor: "#f9fafb",
          borderRadius: "8px",
          border: "1px solid #e5e7eb",
          marginBottom: "2rem"
        }}>
          <div style={{
            width: "48px",
            height: "48px",
            backgroundColor: "#fbbf24",
            borderRadius: "50%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            margin: "0 auto 1rem",
            fontSize: "1.5rem",
            color: "white"
          }}>
            📄
          </div>
          <h3 style={{
            fontSize: "1.1rem",
            fontWeight: "600",
            color: "#374151",
            margin: "0 0 0.5rem"
          }}>
            Không có tài liệu nào đang xử lý
          </h3>
          <p style={{
            fontSize: "0.9rem",
            color: "#6b7280",
            margin: 0
          }}>
            Tất cả tài liệu đã được xử lý xong. Hãy tải lên tài liệu mới để bắt đầu.
          </p>
        </div>
      )}

      {activeTab === "processed" && paginatedProcessed.length > 0 && (
        <div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: "1rem",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
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
                Đã xử lý ({(processedPage - 1) * itemsPerPage + 1}-{Math.min(processedPage * itemsPerPage, sortedFiltered.filter(p => 
                  p.processing_status === "processed" || 
                  p.processing_status === "completed" || 
                  p.processing_status === "failed" ||
                  p.processing_status === "duplicate_detected"
                ).length)} / {sortedFiltered.filter(p => 
                  p.processing_status === "processed" || 
                  p.processing_status === "completed" || 
                  p.processing_status === "failed" ||
                  p.processing_status === "duplicate_detected"
                ).length})
              </h3>
            </div>
            
            {/* Sorting controls for processed papers */}
            <div className="sort-controls">
              <button
                className={`sort-btn ${processedSort === "newest" ? "sort-btn--active" : ""}`}
                onClick={() => {
                  if (processedSort !== "newest") {
                    setProcessedSort("newest");
                    setProcessedPage(1); // Reset to first page when sorting changes
                  }
                }}
              >
                Gần nhất
              </button>
              <button
                className={`sort-btn ${processedSort === "oldest" ? "sort-btn--active" : ""}`}
                onClick={() => {
                  if (processedSort !== "oldest") {
                    setProcessedSort("oldest");
                    setProcessedPage(1); // Reset to first page when sorting changes
                  }
                }}
              >
                Lâu nhất
              </button>
            </div>
          </div>

          <div className="table-wrapper">
            <table className="paper-table">
              <thead>
                <tr>
                  <th>Mã</th>
                  <th>Tiêu đề</th>
                  <th>Trạng thái</th>
                  <th>Năm</th>
                  <th>Canonical</th>
                  <th>Chi tiết</th>
                  <th>Xem PDF</th>
                </tr>
              </thead>
              <tbody>
                {paginatedProcessed.map((paper) => (
                  <tr
                    key={paper.id}
                    className={
                      paper.id === selectedId
                        ? "paper-row paper-row--selected"
                        : "paper-row"
                    }
                    style={{ cursor: "pointer" }}
                    onClick={() => navigate(`/papers/${paper.id}`)}
                  >
                    <td>
                      <div className="simple-list-id">{paper.id}</div>
                    </td>
                    <td className="paper-title-cell" style={{ maxWidth: "300px", wordWrap: "break-word", whiteSpace: "normal", overflow: "hidden", textOverflow: "ellipsis" }}>
                      <div className="paper-title-main" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {paper.detectedTitle || paper.title || paper.originalFilename || paper.filename || "Không có tiêu đề"}
                      </div>
                      {paper.venue && <div className="paper-title-sub">{paper.venue}</div>}
                    </td>
                    <td>
                      <PaperStatusBadge status={paper.processing_status} />
                    </td>
                    <td>{paper.year || "-"}</td>
                    <td>
                      <CanonicalLink paperId={paper.id} />
                    </td>
                    <td>
                      <button
                        className="btn btn--link"
                        style={{ ...actionButtonStyle, color: "#4f46e5" }}
                        onClick={(event) => {
                          event.stopPropagation();
                          navigate(`/papers/${paper.id}`);
                        }}
                      >
                        Xem
                      </button>
                    </td>
                    <td>
                      <button
                        className="btn btn--link"
                        style={{ ...actionButtonStyle, color: "#0f766e" }}
                        onClick={(event) => openPaperPdf(event, paper.id)}
                      >
                        PDF
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination for processed */}
          {totalProcessedPages > 1 && (
            <div className="pagination">
              <button
                className="pagination__btn pagination__btn--arrow"
                disabled={processedPage === 1}
                onClick={() => {
                  if (processedPage > 1) {
                    setProcessedPage(processedPage - 1);
                  }
                }}
              >
                ←
              </button>
              <div className="pagination__numbers">
                {generatePaginationNumbers(processedPage, totalProcessedPages).map((num, index) => (
                  num === '...' ? (
                    <span key={`ellipsis-${index}`} className="pagination__ellipsis">...</span>
                  ) : (
                    <button
                      key={num}
                      className={`pagination__btn pagination__btn--number ${processedPage === num ? 'pagination__btn--active' : ''}`}
                      onClick={() => {
                        if (processedPage !== num) {
                          setProcessedPage(num);
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
                disabled={processedPage === totalProcessedPages}
                onClick={() => {
                  if (processedPage < totalProcessedPages) {
                    setProcessedPage(processedPage + 1);
                  }
                }}
              >
                →
              </button>
            </div>
          )}
        </div>
      )}

      {/* Empty state for processed tab */}
      {activeTab === "processed" && paginatedProcessed.length === 0 && (
        <div style={{ 
          padding: "3rem", 
          textAlign: "center", 
          backgroundColor: "#f0fdf4",
          borderRadius: "8px",
          border: "1px solid #bbf7d0",
          marginBottom: "2rem"
        }}>
          <div style={{
            width: "48px",
            height: "48px",
            backgroundColor: "#22c55e",
            borderRadius: "50%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            margin: "0 auto 1rem",
            fontSize: "1.5rem",
            color: "white"
          }}>
            ✅
          </div>
          <h3 style={{
            fontSize: "1.1rem",
            fontWeight: "600",
            color: "#166534",
            margin: "0 0 0.5rem"
          }}>
            Không có tài liệu nào đã xử lý
          </h3>
          <p style={{
            fontSize: "0.9rem",
            color: "#15803d",
            margin: 0
          }}>
            Chưa có tài liệu nào được xử lý hoàn tất. Hãy tải lên tài liệu để bắt đầu xử lý.
          </p>
        </div>
      )}

      {/* Remove old combined empty state - now handled separately */}
    </section>
  );
}
