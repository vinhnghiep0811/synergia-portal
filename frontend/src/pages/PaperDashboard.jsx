import { useMemo, useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { PaperList } from "../components/PaperList.jsx";
import { getPapers } from "../services/paperApi.js";
import { AppHeader } from "../components/AppHeader.jsx";

function bytesToMB(bytes) {
  if (!bytes || Number.isNaN(bytes)) return 0;
  return bytes / (1024 * 1024);
}

function mapPaperListItem(item) {
  return {
    id: item.id,
    originalFilename: item.original_filename,
    processing_status: item.processing_status,
    processing_stage: item.processing_stage,
    publication_status: item.publication_status,
    mimeType: item.mime_type,
    fileSizeBytes: item.file_size_bytes,
    sizeMB: bytesToMB(item.file_size_bytes),
    uploadedAt: item.created_at,
    updatedAt: item.updated_at,
    title: item.original_filename,
    authors: [],
    year: null,
    venue: null,
    canonicalKey: "",
    detectedTitle: null,
    detectedDoi: null,
    detectedFingerprint: null,
  };
}

export function PaperDashboard() {
  const [papers, setPapers] = useState([]);
  const [loadingList, setLoadingList] = useState(true);
  const [listError, setListError] = useState("");
  const navigate = useNavigate();
  const location = useLocation();
  const [successMessage, setSuccessMessage] = useState("");

  // ====================== LOAD PAPERS ======================
  const loadPapers = async () => {
    let isMounted = true;
    try {
      setLoadingList(true);
      setListError("");

      const data = await getPapers(0, 50);
      const mappedPapers = data.map(mapPaperListItem);

      // Fetch chi tiết cho processed papers (chỉ 1 lần)
      const processedPapers = mappedPapers.filter(
        (p) => ["processed", "completed", "failed", "duplicate_detected"].includes(p.processing_status)
      );

      if (processedPapers.length > 0) {
        const detailedPapers = await Promise.all(
          processedPapers.map(async (paper) => {
            try {
              const detail = await getPaperDetail(paper.id); // bạn đã import ở trên
              return {
                ...paper,
                detectedTitle: detail.detected_title,
                title: detail.detected_title || paper.title,
                detectedDoi: detail.detected_doi,
                detectedFingerprint: detail.detected_fingerprint,
                canonicalKey: detail.detected_doi || detail.detected_fingerprint || detail.canonical_document_id || "",
                authors: detail.authors || [],
                year: detail.year || null,
                venue: detail.venue || null,
              };
            } catch {
              return paper;
            }
          })
        );

        const finalPapers = mappedPapers.map((paper) => {
          const detailed = detailedPapers.find((d) => d.id === paper.id);
          return detailed || paper;
        });

        if (isMounted) setPapers(finalPapers);
      } else {
        if (isMounted) setPapers(mappedPapers);
      }
    } catch (error) {
      if (isMounted) setListError(error.message || "Không thể tải danh sách paper");
    } finally {
      if (isMounted) setLoadingList(false);
    }
  };

  // Initial load
  useEffect(() => {
    loadPapers();
  }, []);

  // ====================== CONDITIONAL POLLING ======================
  useEffect(() => {
    const hasProcessing = papers.some((p) =>
      ["pending", "parse_queued", "parsing", "enriching", "llm_extracting", "canonicalized", "processing"].includes(
        p.processing_status
      )
    );

    if (!hasProcessing) return;

    console.log("%c⏳ Bắt đầu polling real-time (chỉ khi có paper đang xử lý)", "color:#8b5cf6;font-weight:bold");

    const interval = setInterval(() => {
      loadPapers();
    }, 3000);

    return () => clearInterval(interval);
  }, [papers]); // Khi papers thay đổi → kiểm tra lại có còn cần poll không

  // Success message từ UploadPage
  useEffect(() => {
    if (location.state?.message) {
      setSuccessMessage(location.state.message);
      const timer = setTimeout(() => setSuccessMessage(""), 5000);
      window.history.replaceState({}, document.title);
      return () => clearTimeout(timer);
    }
  }, [location]);

  return (
    <div className="app-shell">
      <AppHeader title="Danh sách tài liệu" subtitle="Xem các paper đã upload và trạng thái xử lý." />

      <main className="app-main app-main--papers">
        <div className="app-main__full">
          {successMessage && (
            <div className="card" style={{ backgroundColor: "#f0fdf4", color: "#16a34a", padding: "1rem", marginBottom: "1rem", border: "1px solid #bbf7d0", borderRadius: "8px", display: "flex", justifyContent: "space-between" }}>
              <span>{successMessage}</span>
              <button onClick={() => setSuccessMessage("")} style={{ background: "none", border: "none", cursor: "pointer", color: "#16a34a" }}>✕</button>
            </div>
          )}

          {loadingList ? (
            <div className="card" style={{ padding: "1rem" }}>Đang tải danh sách tài liệu...</div>
          ) : listError ? (
            <div className="card" style={{ padding: "1rem", color: "#dc2626" }}>{listError}</div>
          ) : (
            <PaperList papers={papers} />
          )}
        </div>
      </main>
    </div>
  );
}