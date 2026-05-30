import { useMemo, useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { PaperStatusBadge } from "./PaperStatusBadge.jsx";
import { CanonicalLink } from "./CanonicalLink.jsx";
import { getPaperFileViewUrl, getPaperDetail } from "../services/paperApi.js";
import { formatDate } from "../utils/formatDate.js";

const actionButtonStyle = {
  fontSize: "0.8rem",
  padding: "0.2rem 0.4rem",
  textDecoration: "underline",
  background: "none",
  border: "none",
  cursor: "pointer",
};

export function PaperList({ papers, selectedId, lastUpdateTime }) {
  const [searchText, setSearchText] = useState("");

  // Load activeTab from localStorage on mount, default to "pending"
  const [activeTab, setActiveTabState] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('paperList_activeTab');
      return saved || "pending";
    }
    return "pending";
  });

  // Wrapper to update both state and localStorage
  const setActiveTab = (tab) => {
    setActiveTabState(tab);
    setUserManuallySwitched(true); // Mark that user manually switched
    if (typeof window !== 'undefined') {
      localStorage.setItem('paperList_activeTab', tab);
    }
  };

  const [pendingPage, setPendingPage] = useState(1);
  const [processingPage, setProcessingPage] = useState(1);
  const [processedPage, setProcessedPage] = useState(1);
  const [processedSubTab, setProcessedSubTab] = useState("all"); // "all" | "drafted" | "published"
  const [pendingSort, setPendingSort] = useState("newest"); // "newest" or "oldest"
  const [processingSort, setProcessingSort] = useState("newest"); // "newest" or "oldest"
  const [processedSort, setProcessedSort] = useState("newest"); // "newest" or "oldest"
  const [enhancedPapers, setEnhancedPapers] = useState([]);
  const [refreshTick, setRefreshTick] = useState(0);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [userManuallySwitched, setUserManuallySwitched] = useState(false);
  const itemsPerPage = 5;
  const navigate = useNavigate();

  // Sync with parent component's lastUpdateTime prop for coordinated real-time updates
  useEffect(() => {
    if (lastUpdateTime) {
      setLastUpdate(lastUpdateTime);
      console.log("🔄 PaperList synced with parent update:", new Date(lastUpdateTime).toLocaleTimeString());
    }
  }, [lastUpdateTime]);

  // Auto-refresh every 5 seconds for real-time updates as backup
  useEffect(() => {
    const interval = setInterval(() => {
      setRefreshTick((previous) => previous + 1);
    }, 5000); // 5 seconds

    return () => clearInterval(interval);
  }, []);

  // Also refresh when page becomes visible (user switches back to tab)
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        setRefreshTick((previous) => previous + 1);
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => document.removeEventListener("visibilitychange", handleVisibilityChange);
  }, []);

  // Fetch details for processing and processed papers to get detected_title
  useEffect(() => {
    let isCancelled = false;

    async function fetchPapersDetails() {
      // Only fetch details for processing and processed papers
      const papersNeedingDetails = papers.filter(
        (p) => p.processing_status === "processing" ||
               p.processing_status === "processed" || 
               p.processing_status === "completed" || 
               p.processing_status === "failed" ||
               p.processing_status === "duplicate_detected"
      );

      if (papersNeedingDetails.length === 0) {
        if (!isCancelled) {
          setEnhancedPapers(papers);
        }
        return;
      }
      
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
      if (!isCancelled) {
        setEnhancedPapers(finalPapers);
      }
    }

    if (papers.length > 0) {
      void fetchPapersDetails();
    } else {
      setEnhancedPapers([]);
    }

    return () => {
      isCancelled = true;
    };
  }, [papers, refreshTick]);

  // Intelligent tab switching: when current tab becomes empty, switch to tab with papers
  // Only auto-switch on initial load, not after user manually switched
  useEffect(() => {
    if (enhancedPapers.length === 0) return;
    if (userManuallySwitched) return; // Don't auto-switch if user manually switched

    // Count papers in each tab
    const pendingCount = enhancedPapers.filter(p => p.processing_status === "pending").length;
    const processingCount = enhancedPapers.filter(p =>
      p.processing_status === "processing" ||
      p.processing_status === "parsing" ||
      p.processing_status === "enriching" ||
      p.processing_status === "llm_extracting" ||
      p.processing_status === "parse_queued" ||
      p.processing_status === "canonicalized"
    ).length;
    const processedCount = enhancedPapers.filter(p =>
      p.processing_status === "processed" ||
      p.processing_status === "completed" ||
      p.processing_status === "failed" ||
      p.processing_status === "duplicate_detected"
    ).length;

    // Check if current tab is empty
    const currentTabEmpty =
      (activeTab === "pending" && pendingCount === 0) ||
      (activeTab === "processing" && processingCount === 0) ||
      (activeTab === "processed" && processedCount === 0);

    if (currentTabEmpty) {
      // Switch to the first tab that has papers, prioritizing processing > pending > processed
      if (processingCount > 0) {
        console.log(`🔄 Tab auto-switch: ${activeTab} is empty, switching to "processing" (${processingCount} papers)`);
        setActiveTabState("processing"); // Use setActiveTabState to avoid marking as manual switch
      } else if (pendingCount > 0) {
        console.log(`🔄 Tab auto-switch: ${activeTab} is empty, switching to "pending" (${pendingCount} papers)`);
        setActiveTabState("pending");
      } else if (processedCount > 0) {
        console.log(`🔄 Tab auto-switch: ${activeTab} is empty, switching to "processed" (${processedCount} papers)`);
        setActiveTabState("processed");
      }
    }
  }, [enhancedPapers, userManuallySwitched]); // Run when papers change

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
    let processed = sortedFiltered.filter(p => 
      p.processing_status === "processed" || 
      p.processing_status === "completed" || 
      p.processing_status === "failed" ||
      p.processing_status === "duplicate_detected"
    );
    // Filter by publication_status sub-tab
    if (processedSubTab === "drafted") {
      processed = processed.filter(p => p.publication_status === "draft" || !p.publication_status);
    } else if (processedSubTab === "published") {
      processed = processed.filter(p => p.publication_status === "published");
    }
    const startIndex = (processedPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    return processed.slice(startIndex, endIndex);
  }, [sortedFiltered, processedPage, processedSubTab]);

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
    let processed = sortedFiltered.filter(p => 
      p.processing_status === "processed" || 
      p.processing_status === "completed" || 
      p.processing_status === "failed" ||
      p.processing_status === "duplicate_detected"
    );
    // Filter by publication_status sub-tab
    if (processedSubTab === "drafted") {
      processed = processed.filter(p => p.publication_status === "draft" || !p.publication_status);
    } else if (processedSubTab === "published") {
      processed = processed.filter(p => p.publication_status === "published");
    }
    return Math.ceil(processed.length / itemsPerPage);
  }, [sortedFiltered, processedSubTab]);

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

  // Check if any papers are currently being processed for live indicator
  const hasProcessingPapers = enhancedPapers.some(p =>
    p.processing_status === "processing" ||
    p.processing_status === "parsing" ||
    p.processing_status === "enriching" ||
    p.processing_status === "llm_extracting"
  );

  // Format last update time
  const formatLastUpdate = (timestamp) => {
    if (!timestamp) return "";
    const date = new Date(timestamp);
    const now = new Date();
    const diff = Math.floor((now - date) / 1000); // seconds

    if (diff < 60) return "Vừa cập nhật";
    if (diff < 3600) return `${Math.floor(diff / 60)} phút trước`;
    return date.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
  };

  return (
    <section className="card list-card">
      <header className="card__header card__header--with-actions">
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.5rem" }}>
            <h2 className="card__title" style={{ margin: 0 }}>Danh sách tài liệu nghiên cứu</h2>
            {hasProcessingPapers && (
              <span style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.5rem",
                padding: "0.25rem 0.75rem",
                backgroundColor: "#dbeafe",
                color: "#1d4ed8",
                borderRadius: "999px",
                fontSize: "0.75rem",
                fontWeight: "600"
              }}>
                <span style={{
                  width: "6px",
                  height: "6px",
                  borderRadius: "50%",
                  backgroundColor: "#3b82f6",
                  animation: "pulse 1.5s infinite"
                }}></span>
                Đang cập nhật real-time
              </span>
            )}
          </div>
          <p className="card__subtitle" style={{ margin: 0, display: "flex", alignItems: "center", gap: "0.5rem" }}>
            Quản lý và theo dõi trạng thái xử lý của các tài liệu học thuật.
            <span style={{
              fontSize: "0.75rem",
              color: "#6b7280",
              fontStyle: "italic"
            }}>
              (Cập nhật: {formatLastUpdate(lastUpdate)})
            </span>
          </p>
        </div>
        <div className="list-filters">
          <input
            type="search"
            placeholder={
              activeTab === "pending"
                ? "Tìm kiếm theo tên file gốc"
                : activeTab === "processing"
                ? "Tìm kiếm theo tiêu đề tài liệu"
                : "Tìm kiếm theo tiêu đề tài liệu"
            }
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
          />
          {/* <button
            className="btn btn--secondary"
            style={{ marginLeft: "0.5rem", fontSize: "0.8rem", padding: "0.4rem 0.8rem" }}
            onClick={() => {
              setRefreshTick((previous) => previous + 1);
            }}
            title="Làm mới danh sách"
          >
            🔄 Làm mới
          </button> */}
        </div>
      </header>

      {/* Tabs with real-time counts */}
      <div className="tabs">
        <button
          className={`tab ${activeTab === "pending" ? "tab--active" : ""}`}
          onClick={() => setActiveTab("pending")}
        >
          <div className="tab__indicator tab__indicator--pending"></div>
          Đang chờ
          <span className="tab__badge" style={{
            marginLeft: "0.5rem",
            backgroundColor: activeTab === "pending" ? "#f59e0b" : "#e5e7eb",
            color: activeTab === "pending" ? "#fff" : "#6b7280",
            padding: "0.125rem 0.5rem",
            borderRadius: "999px",
            fontSize: "0.75rem",
            fontWeight: "600",
            transition: "all 0.3s ease"
          }}>
            {enhancedPapers.filter(p => p.processing_status === "pending").length}
          </span>
          {enhancedPapers.some(p => p.processing_status === "pending") && (
            <span className="tab__live-indicator" style={{
              marginLeft: "0.5rem",
              width: "6px",
              height: "6px",
              borderRadius: "50%",
              backgroundColor: "#f59e0b",
              animation: "pulse 2s infinite"
            }}></span>
          )}
        </button>
        <button
          className={`tab ${activeTab === "processing" ? "tab--active" : ""}`}
          onClick={() => setActiveTab("processing")}
        >
          <div className="tab__indicator tab__indicator--processing"></div>
          Đang xử lý
          <span className="tab__badge" style={{
            marginLeft: "0.5rem",
            backgroundColor: activeTab === "processing" ? "#3b82f6" : "#e5e7eb",
            color: activeTab === "processing" ? "#fff" : "#6b7280",
            padding: "0.125rem 0.5rem",
            borderRadius: "999px",
            fontSize: "0.75rem",
            fontWeight: "600",
            transition: "all 0.3s ease"
          }}>
            {enhancedPapers.filter(p =>
              p.processing_status === "processing" ||
              p.processing_status === "parsing" ||
              p.processing_status === "enriching" ||
              p.processing_status === "llm_extracting" ||
              p.processing_status === "parse_queued" ||
              p.processing_status === "canonicalized"
            ).length}
          </span>
          {enhancedPapers.some(p =>
            p.processing_status === "processing" ||
            p.processing_status === "parsing" ||
            p.processing_status === "enriching" ||
            p.processing_status === "llm_extracting"
          ) && (
            <span className="tab__live-indicator" style={{
              marginLeft: "0.5rem",
              width: "6px",
              height: "6px",
              borderRadius: "50%",
              backgroundColor: "#3b82f6",
              animation: "pulse 1.5s infinite"
            }}></span>
          )}
        </button>
        <button
          className={`tab ${activeTab === "processed" ? "tab--active" : ""}`}
          onClick={() => setActiveTab("processed")}
        >
          <div className="tab__indicator tab__indicator--processed"></div>
          Đã xử lý
          <span className="tab__badge" style={{
            marginLeft: "0.5rem",
            backgroundColor: activeTab === "processed" ? "#10b981" : "#e5e7eb",
            color: activeTab === "processed" ? "#fff" : "#6b7280",
            padding: "0.125rem 0.5rem",
            borderRadius: "999px",
            fontSize: "0.75rem",
            fontWeight: "600",
            transition: "all 0.3s ease"
          }}>
            {enhancedPapers.filter(p =>
              p.processing_status === "processed" ||
              p.processing_status === "completed" ||
              p.processing_status === "failed" ||
              p.processing_status === "duplicate_detected"
            ).length}
          </span>
        </button>
      </div>

      {/* Add CSS animation for live indicator */}
      <style>{`
        @keyframes pulse {
          0%, 100% {
            opacity: 1;
            transform: scale(1);
          }
          50% {
            opacity: 0.5;
            transform: scale(1.2);
          }
        }
      `}</style>

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
                  <th>Tệp</th>
                  <th>Dung lượng</th>
                  <th>Tải lên</th>
                  <th>Tài liệu chuẩn hóa</th>
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
                  <th>Tiêu đề</th>
                  <th>Trạng thái</th>
                  <th>Tải lên</th>
                  <th>Tài liệu chuẩn hóa</th>
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

      {activeTab === "processed"  && (
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

          {/* Sub-tabs for publication status */}
          <div style={{
            display: "flex",
            gap: "0.5rem",
            marginBottom: "1rem",
            padding: "0.5rem",
            backgroundColor: "#f9fafb",
            borderRadius: "8px",
          }}>
            <button
              onClick={() => {
                setProcessedSubTab("all");
                setProcessedPage(1);
              }}
              style={{
                padding: "0.5rem 1rem",
                borderRadius: "6px",
                border: "none",
                backgroundColor: processedSubTab === "all" ? "#fff" : "transparent",
                color: processedSubTab === "all" ? "#374151" : "#6b7280",
                fontWeight: processedSubTab === "all" ? "600" : "400",
                fontSize: "0.875rem",
                cursor: "pointer",
                boxShadow: processedSubTab === "all" ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
                transition: "all 0.2s ease",
              }}
            >
              Tất cả
              <span style={{
                marginLeft: "0.5rem",
                padding: "0.125rem 0.375rem",
                backgroundColor: "#e5e7eb",
                color: "#374151",
                borderRadius: "999px",
                fontSize: "0.75rem",
              }}>
                {sortedFiltered.filter(p => 
                  (p.processing_status === "processed" || 
                   p.processing_status === "completed" || 
                   p.processing_status === "failed" ||
                   p.processing_status === "duplicate_detected")
                ).length}
              </span>
            </button>
            <button
              onClick={() => {
                setProcessedSubTab("drafted");
                setProcessedPage(1);
              }}
              style={{
                padding: "0.5rem 1rem",
                borderRadius: "6px",
                border: "none",
                backgroundColor: processedSubTab === "drafted" ? "#fff" : "transparent",
                color: processedSubTab === "drafted" ? "#374151" : "#6b7280",
                fontWeight: processedSubTab === "drafted" ? "600" : "400",
                fontSize: "0.875rem",
                cursor: "pointer",
                boxShadow: processedSubTab === "drafted" ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
                transition: "all 0.2s ease",
              }}
            >
              Chưa xuất bản 
              <span style={{
                marginLeft: "0.5rem",
                padding: "0.125rem 0.375rem",
                backgroundColor: "#fef3c7",
                color: "#92400e",
                borderRadius: "999px",
                fontSize: "0.75rem",
              }}>
                {sortedFiltered.filter(p => 
                  (p.processing_status === "processed" || 
                   p.processing_status === "completed" || 
                   p.processing_status === "failed" ||
                   p.processing_status === "duplicate_detected") &&
                  (p.publication_status === "draft" || !p.publication_status)
                ).length}
              </span>
            </button>
            <button
              onClick={() => {
                setProcessedSubTab("published");
                setProcessedPage(1);
              }}
              style={{
                padding: "0.5rem 1rem",
                borderRadius: "6px",
                border: "none",
                backgroundColor: processedSubTab === "published" ? "#fff" : "transparent",
                color: processedSubTab === "published" ? "#374151" : "#6b7280",
                fontWeight: processedSubTab === "published" ? "600" : "400",
                fontSize: "0.875rem",
                cursor: "pointer",
                boxShadow: processedSubTab === "published" ? "0 1px 3px rgba(0,0,0,0.1)" : "none",
                transition: "all 0.2s ease",
              }}
            >
              Đã xuất bản
              <span style={{
                marginLeft: "0.5rem",
                padding: "0.125rem 0.375rem",
                backgroundColor: "#d1fae5",
                color: "#065f46",
                borderRadius: "999px",
                fontSize: "0.75rem",
              }}>
                {sortedFiltered.filter(p => 
                  (p.processing_status === "processed" || 
                   p.processing_status === "completed" || 
                   p.processing_status === "failed" ||
                   p.processing_status === "duplicate_detected") &&
                  p.publication_status === "published"
                ).length}
              </span>
            </button>
          </div>

          <div className="table-wrapper">
            <table className="paper-table">
              <thead>
                <tr>
                  <th>Tiêu đề</th>
                  <th>Trạng thái xử lý</th>
                  <th>Trạng thái xuất bản</th>
                  <th>Tài liệu chuẩn hóa</th>
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
                    <td className="paper-title-cell" style={{ maxWidth: "300px", wordWrap: "break-word", whiteSpace: "normal", overflow: "hidden", textOverflow: "ellipsis" }}>
                      <div className="paper-title-main" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {paper.detected_title || paper.title || paper.originalFilename || paper.filename || "Không có tiêu đề"}
                      </div>
                      {paper.venue && <div className="paper-title-sub">{paper.venue}</div>}
                    </td>
                    <td>
                      <PaperStatusBadge status={paper.processing_status} />
                    </td>
                    <td>
                      <span style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "0.375rem",
                        padding: "0.25rem 0.75rem",
                        backgroundColor: paper.publication_status === "published" ? "#d1fae5" : "#fef3c7",
                        color: paper.publication_status === "published" ? "#065f46" : "#92400e",
                        borderRadius: "999px",
                        fontSize: "0.75rem",
                        fontWeight: "600",
                        textTransform: "capitalize",
                      }}>
                        <span style={{
                          width: "6px",
                          height: "6px",
                          borderRadius: "50%",
                          backgroundColor: paper.publication_status === "published" ? "#10b981" : "#f59e0b",
                        }} />
                        {paper.publication_status === "published" ? "Published" : "Drafted"}
                      </span>
                    </td>
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
          backgroundColor: processedSubTab === "published" ? "#f0fdf4" : processedSubTab === "drafted" ? "#fffbeb" : "#f0fdf4",
          borderRadius: "8px",
          border: `1px solid ${processedSubTab === "published" ? "#bbf7d0" : processedSubTab === "drafted" ? "#fde68a" : "#bbf7d0"}`,
          marginBottom: "2rem"
        }}>
          <div style={{
            width: "48px",
            height: "48px",
            backgroundColor: processedSubTab === "published" ? "#22c55e" : processedSubTab === "drafted" ? "#f59e0b" : "#22c55e",
            borderRadius: "50%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            margin: "0 auto 1rem",
            fontSize: "1.5rem",
            color: "white"
          }}>
            {processedSubTab === "published" ? "✅" : processedSubTab === "drafted" ? "📝" : "✅"}
          </div>
          <h3 style={{
            fontSize: "1.1rem",
            fontWeight: "600",
            color: processedSubTab === "published" ? "#166534" : processedSubTab === "drafted" ? "#92400e" : "#166534",
            margin: "0 0 0.5rem"
          }}>
            {processedSubTab === "published" 
              ? "Không có tài liệu nào đã publish" 
              : processedSubTab === "drafted" 
                ? "Không có tài liệu nào ở trạng thái draft" 
                : "Không có tài liệu nào đã xử lý"}
          </h3>
          <p style={{
            fontSize: "0.9rem",
            color: processedSubTab === "published" ? "#15803d" : processedSubTab === "drafted" ? "#b45309" : "#15803d",
            margin: 0
          }}>
            {processedSubTab === "published" 
              ? "Chưa có tài liệu nào được publish. Hãy publish tài liệu từ trạng thái draft." 
              : processedSubTab === "drafted" 
                ? "Tất cả tài liệu đã xử lý đều đã được publish hoặc chưa có tài liệu nào." 
                : "Chưa có tài liệu nào được xử lý hoàn tất. Hãy tải lên tài liệu để bắt đầu xử lý."}
          </p>
        </div>
      )}

      {/* Remove old combined empty state - now handled separately */}
    </section>
  );
}
