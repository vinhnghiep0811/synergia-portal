import { useMemo, useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { PaperStatusBadge } from "./PaperStatusBadge.jsx";
import { CanonicalLink } from "./CanonicalLink.jsx";
import { getPaperFileViewUrl, getCanonicalDocumentByPaper, getPaperDetail } from "../services/paperApi.js";
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
  const [activeTab, setActiveTab] = useState("pending"); // "pending", "processing", or "processed"
  const [pendingPage, setPendingPage] = useState(1);
  const [processingPage, setProcessingPage] = useState(1);
  const [processedPage, setProcessedPage] = useState(1);
  const [pendingSort, setPendingSort] = useState("newest"); // "newest" or "oldest"
  const [processingSort, setProcessingSort] = useState("newest"); // "newest" or "oldest"
  const [processedSort, setProcessedSort] = useState("newest"); // "newest" or "oldest"
  const [enhancedPapers, setEnhancedPapers] = useState([]);
  const [lastUpdate, setLastUpdate] = useState(Date.now());
  const itemsPerPage = 5;
  const navigate = useNavigate();

  // Auto-refresh every 5 seconds for real-time updates
  useEffect(() => {
    const interval = setInterval(() => {
      setLastUpdate(Date.now());
      console.log("🔄 Auto-refreshing PaperList for real-time updates");
    }, 5000); // 5 seconds

    return () => clearInterval(interval);
  }, []);

  // Also refresh when page becomes visible (user switches back to tab)
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        setLastUpdate(Date.now());
        console.log("👁️ Page became visible, refreshing PaperList");
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, []);

  // Debug: Log papers data
  console.log("PaperList received papers:", papers.map(p => ({
    id: p.id,
    processing_status: p.processing_status,
    publication_status: p.publication_status,
    processing_stage: p.processing_stage,
    originalFilename: p.originalFilename
  })));

  // Fetch details for processing and processed papers to get detected_title
  useMemo(() => {
    async function fetchPapersDetails() {
      console.log("🔄 Fetching paper details - papers updated or auto-refresh triggered");
      
      // Only fetch details for processing and processed papers
      const papersNeedingDetails = papers.filter(
        (p) => p.processing_status === "processing" ||
               p.processing_status === "processed" || 
               p.processing_status === "completed" || 
               p.processing_status === "failed" ||
               p.processing_status === "duplicate_detected"
      );

      if (papersNeedingDetails.length === 0) {
        setEnhancedPapers(papers);
        return;
      }

      console.log("Fetching details for processing and processed papers...");
      
      const enhanced = await Promise.all(
        papersNeedingDetails.map(async (paper) => {
          try {
            const detail = await getPaperDetail(paper.id);
            return {
              ...paper,
              detectedTitle: detail.detected_title,
              title: detail.detected_title || paper.title,
              detectedDoi: detail.detected_doi || detail.doi || detail.canonical_doi || detail.metadata_doi || detail.paper_doi,
              detectedFingerprint: detail.detected_fingerprint,
              canonicalKey: detail.detected_doi || detail.detected_fingerprint || detail.canonical_document_id || "",
              authors: detail.authors || [],
              year: detail.year || null,
              venue: detail.venue || null,
            };
          } catch (error) {
            console.warn(`Failed to fetch details for paper ${paper.id}:`, error);
            return paper;
          }
        })
      );

      // Combine with pending papers (no need to fetch details for them)
      const pendingPapers = papers.filter(
        (p) => !(p.processing_status === "processing" ||
                p.processing_status === "processed" || 
                p.processing_status === "completed" || 
                p.processing_status === "failed" ||
                p.processing_status === "duplicate_detected")
      );

      const finalPapers = [...pendingPapers, ...enhanced];
      setEnhancedPapers(finalPapers);
      console.log("✅ Enhanced papers updated:", finalPapers.length);
    }

    if (papers.length > 0) {
      fetchPapersDetails();
    }
  }, [papers, lastUpdate]); // Add lastUpdate to trigger re-fetch

  function openPaperPdf(event, paperId) {
    event.stopPropagation();
    window.open(getPaperFileViewUrl(paperId), "_blank");
  }

  const filtered = useMemo(() => {
    return enhancedPapers.filter((p) => {
      // First filter by active tab
      const isInPendingTab = activeTab === "pending" && (
        p.processing_status === "pending"
      );
      const isInProcessingTab = activeTab === "processing" && (
        p.processing_status === "processing" ||
        p.processing_status === "parsing" ||
        p.processing_status === "enriching" ||
        p.processing_status === "llm_extracting" ||
        p.processing_status === "parse_queued" ||
        p.processing_status === "canonicalized"
      );
      const isInProcessedTab = activeTab === "processed" && (
        p.processing_status === "processed" || 
        p.processing_status === "completed" || 
        p.processing_status === "failed" ||
        p.processing_status === "duplicate_detected"
      );
      
      if (!isInPendingTab && !isInProcessingTab && !isInProcessedTab) return false;

      // Then apply search filter
      const textMatch =
        !searchText ||
        (activeTab === "pending" &&
          (p.originalFilename || p.filename || "")
            .toLowerCase()
            .includes(searchText.toLowerCase())) ||
        (activeTab === "processing" &&
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
        ) ||
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
  }, [enhancedPapers, searchText, activeTab]);

  // Sort by upload date (newest first) and paginate
  const sortedFiltered = useMemo(() => {
    return [...filtered].sort((a, b) => {
      const dateA = new Date(a.uploadedAt || 0);
      const dateB = new Date(b.uploadedAt || 0);
      
      // Use appropriate sort based on active tab
      if (activeTab === "pending") {
        return pendingSort === "newest" ? dateB - dateA : dateA - dateB;
      } else if (activeTab === "processing") {
        return processingSort === "newest" ? dateB - dateA : dateA - dateB;
      } else if (activeTab === "processed") {
        return processedSort === "newest" ? dateB - dateA : dateA - dateB;
      }
      
      // Default: newest first
      return dateB - dateA;
    });
  }, [filtered, activeTab, pendingSort, processingSort, processedSort]);

  const paginatedPending = useMemo(() => {
    const pending = sortedFiltered.filter(p => 
      p.processing_status === "pending"
    );
    const startIndex = (pendingPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    return pending.slice(startIndex, endIndex);
  }, [sortedFiltered, pendingPage]);

  const paginatedProcessing = useMemo(() => {
    const processing = sortedFiltered.filter(p => 
      p.processing_status === "processing" ||
      p.processing_status === "parsing" ||
      p.processing_status === "enriching" ||
      p.processing_status === "llm_extracting" ||
      p.processing_status === "parse_queued" ||
      p.processing_status === "canonicalized"
    );
    const startIndex = (processingPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    return processing.slice(startIndex, endIndex);
  }, [sortedFiltered, processingPage]);

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
      p.processing_status === "pending"
    );
    return Math.ceil(pending.length / itemsPerPage);
  }, [sortedFiltered]);

  const totalProcessingPages = useMemo(() => {
    const processing = sortedFiltered.filter(p => 
      p.processing_status === "processing" ||
      p.processing_status === "parsing" ||
      p.processing_status === "enriching" ||
      p.processing_status === "llm_extracting" ||
      p.processing_status === "parse_queued" ||
      p.processing_status === "canonicalized"
    );
    return Math.ceil(processing.length / itemsPerPage);
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
                : activeTab === "processing"
                ? "Tìm kiếm theo tiêu đề, DOI"
                : "Tìm kiếm theo tiêu đề, DOI"
            }
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
          />
          <button
            className="btn btn--secondary"
            style={{ marginLeft: "0.5rem", fontSize: "0.8rem", padding: "0.4rem 0.8rem" }}
            onClick={() => {
              setLastUpdate(Date.now());
              console.log("🔄 Manual refresh triggered by user");
            }}
            title="Làm mới danh sách"
          >
            🔄 Làm mới
          </button>
        </div>
      </header>

      {/* Tabs */}
      <div className="tabs">
        <button
          className={`tab ${activeTab === "pending" ? "tab--active" : ""}`}
          onClick={() => setActiveTab("pending")}
        >
          <div className="tab__indicator tab__indicator--pending"></div>
          Đang chờ
        </button>
        <button
          className={`tab ${activeTab === "processing" ? "tab--active" : ""}`}
          onClick={() => setActiveTab("processing")}
        >
          <div className="tab__indicator tab__indicator--processing"></div>
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
            Không có tài liệu nào đang chờ
          </h3>
          <p style={{
            fontSize: "0.9rem",
            color: "#6b7280",
            margin: 0
          }}>
            Tất cả tài liệu đã được xử lý. Hãy tải lên tài liệu mới để bắt đầu.
          </p>
        </div>
      )}

      {/* Content for processing tab */}
      {activeTab === "processing" && paginatedProcessing.length > 0 && (
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
                  backgroundColor: "#3b82f6",
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
                Đang xử lý ({(processingPage - 1) * itemsPerPage + 1}-{Math.min(processingPage * itemsPerPage, sortedFiltered.filter(p => 
                  p.processing_status === "processing" ||
                  p.processing_status === "parsing" ||
                  p.processing_status === "enriching" ||
                  p.processing_status === "llm_extracting" ||
                  p.processing_status === "parse_queued" ||
                  p.processing_status === "canonicalized"
                ).length)} / {sortedFiltered.filter(p => 
                  p.processing_status === "processing" ||
                  p.processing_status === "parsing" ||
                  p.processing_status === "enriching" ||
                  p.processing_status === "llm_extracting" ||
                  p.processing_status === "parse_queued" ||
                  p.processing_status === "canonicalized"
                ).length})
              </h3>
            </div>
            
            {/* Sorting controls for processing papers */}
            <div className="sort-controls">
              <button
                className={`sort-btn ${processingSort === "newest" ? "sort-btn--active" : ""}`}
                onClick={() => {
                  if (processingSort !== "newest") {
                    setProcessingSort("newest");
                    setProcessingPage(1); // Reset to first page when sorting changes
                  }
                }}
              >
                Gần nhất
              </button>
              <button
                className={`sort-btn ${processingSort === "oldest" ? "sort-btn--active" : ""}`}
                onClick={() => {
                  if (processingSort !== "oldest") {
                    setProcessingSort("oldest");
                    setProcessingPage(1); // Reset to first page when sorting changes
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
                  <th>Tải lên</th>
                  <th>Canonical</th>
                  <th>Chi tiết</th>
                  <th>Xem PDF</th>
                </tr>
              </thead>
              <tbody>
                {paginatedProcessing.map((paper) => (
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

          {/* Pagination for processing */}
          {totalProcessingPages > 1 && (
            <div className="pagination">
              <button
                className="pagination__btn pagination__btn--arrow"
                disabled={processingPage === 1}
                onClick={() => {
                  if (processingPage > 1) {
                    setProcessingPage(processingPage - 1);
                  }
                }}
              >
                ←
              </button>
              <div className="pagination__numbers">
                {generatePaginationNumbers(processingPage, totalProcessingPages).map((num, index) => (
                  num === '...' ? (
                    <span key={`ellipsis-${index}`} className="pagination__ellipsis">...</span>
                  ) : (
                    <button
                      key={num}
                      className={`pagination__btn pagination__btn--number ${processingPage === num ? 'pagination__btn--active' : ''}`}
                      onClick={() => {
                        if (processingPage !== num) {
                          setProcessingPage(num);
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
                disabled={processingPage === totalProcessingPages}
                onClick={() => {
                  if (processingPage < totalProcessingPages) {
                    setProcessingPage(processingPage + 1);
                  }
                }}
              >
                →
              </button>
            </div>
          )}
        </div>
      )}

      {/* Empty state for processing tab */}
      {activeTab === "processing" && paginatedProcessing.length === 0 && (
        <div style={{ 
          padding: "3rem", 
          textAlign: "center", 
          backgroundColor: "#eff6ff",
          borderRadius: "8px",
          border: "1px solid #bfdbfe",
          marginBottom: "2rem"
        }}>
          <div style={{
            width: "48px",
            height: "48px",
            backgroundColor: "#3b82f6",
            borderRadius: "50%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            margin: "0 auto 1rem",
            fontSize: "1.5rem",
            color: "white"
          }}>
            ⚡
          </div>
          <h3 style={{
            fontSize: "1.1rem",
            fontWeight: "600",
            color: "#1e40af",
            margin: "0 0 0.5rem"
          }}>
            Không có tài liệu nào đang xử lý
          </h3>
          <p style={{
            fontSize: "0.9rem",
            color: "#3730a3",
            margin: 0
          }}>
            Không có tài liệu nào đang trong quá trình xử lý.
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
                        {paper.detected_title || paper.title || paper.originalFilename || paper.filename || "Không có tiêu đề"}
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
