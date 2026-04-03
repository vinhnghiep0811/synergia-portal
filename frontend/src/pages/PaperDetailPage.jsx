import { useState, useEffect } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import { PaperDetail } from "../components/PaperDetail.jsx";
import {
  getCanonicalDocumentByPaper,
  getPaperDetail,
} from "../services/paperApi.js";
import { AppHeader } from "../components/AppHeader.jsx";

function bytesToMB(bytes) {
  if (!bytes || Number.isNaN(bytes)) return 0;
  return bytes / (1024 * 1024);
}

function mapCanonicalAuthors(authors) {
  if (!Array.isArray(authors)) return [];
  return authors.map((author) => author?.name).filter(Boolean);
}

function mapPaperDetail(detail, canonical) {
  const matchStatus = canonical?.match_status || null;
  const enrichmentStatus = canonical?.enrichment_status || null;

  const semanticScholarStatus = !detail.canonical_document_id
    ? "not_linked"
    : enrichmentStatus || detail.publication_status || "pending";

  return {
    id: detail.id,
    originalFilename: detail.original_filename,
    filename: detail.original_filename,
    title: canonical?.title || canonical?.title_candidate || detail.detected_title || detail.original_filename,
    status: detail.processing_status || detail.status,                    // ← giữ nguyên
    processing_status: detail.processing_status,
    processing_stage: detail.processing_stage,
    processing_error: detail.processing_error,
    publication_status: detail.publication_status,

    mimeType: detail.mime_type,
    fileSizeBytes: detail.file_size_bytes,
    sizeMB: bytesToMB(detail.file_size_bytes),
    uploadedAt: detail.created_at,
    updatedAt: detail.updated_at,

    canonicalDocumentId: detail.canonical_document_id,
    uploaderId: detail.uploader_id,
    storagePath: detail.storage_path,
    fileHashSha256: detail.file_hash_sha256,
    uploadSource: detail.upload_source,
    extractedTextPreview: detail.extracted_text_preview,
    detectedTitle: detail.detected_title,
    detectedDoi: detail.detected_doi,
    detectedFingerprint: detail.detected_fingerprint,

    semanticScholarStatus,
    matchStatus,
    semanticSource: canonical?.metadata_source || null,
    ssMatchConfidence: canonical?.ss_match_confidence || null,
    ssPaperId: canonical?.ss_paper_id || null,

    canonicalTitle: canonical?.title || null,
    canonicalTitleCandidate: canonical?.title_candidate || null,
    canonicalAbstract: canonical?.abstract || null,
    canonicalVenue: canonical?.venue || null,
    canonicalPublicationYear: canonical?.publication_year || null,
    canonicalAuthors: mapCanonicalAuthors(canonical?.authors_json),

    parseStatus: detail.processing_stage === "parsing"
      ? "processing"
      : detail.processing_stage && detail.processing_stage !== "parsing"
      ? "done"
      : null,
    parseError: detail.processing_error,
    hasLLMExtraction: detail.processing_stage === "llm_extracting" && detail.processing_status !== "failed",
  };
}

export function PaperDetailPage() {
  const [paper, setPaper] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const { paperId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  const loadPaperDetail = async (showLoading = false) => {
    if (!paperId) return;

    console.log(`%c🔄 loadPaperDetail called (location.key = ${location.key})`, 'color:#22c55e;font-weight:bold');

    if (showLoading) setLoading(true);
    try {
      setError("");
      const detail = await getPaperDetail(paperId);
      const canonical = await getCanonicalDocumentByPaper(paperId);
      const mapped = mapPaperDetail(detail, canonical);
      
      console.log("%c📦 FRESH paper data:", 'color:#f59e0b;font-weight:bold', {
        processing_status: mapped.processing_status,
        processing_stage: mapped.processing_stage,
        semanticScholarStatus: mapped.semanticScholarStatus,
        status: mapped.status,                    // ← log thêm để debug
      });
      
      setPaper(mapped);
    } catch (err) {
      console.error("❌ Load paper error:", err);
      setError(err.message || "Không thể tải chi tiết paper");
      setPaper(null);
    } finally {
      if (showLoading) setLoading(false);
    }
  };

  // ==================== FETCH MỖI LẦN VÀO TRANG (bao gồm BACK) ====================
  useEffect(() => {
    let isMounted = true;
    setLoading(true);

    const fetchData = async () => {
      await loadPaperDetail();
      if (isMounted) setLoading(false);
    };

    fetchData();

    const handlePageShow = (e) => {
      if (e.persisted) {
        console.log('%c📌 RESTORED FROM BFCACHE → refetch', 'color:#f59e0b;font-weight:bold');
        setPaper(null);           // ← clear stale data
        loadPaperDetail(true);
      }
    };
    window.addEventListener('pageshow', handlePageShow);

    return () => {
      isMounted = false;
      window.removeEventListener('pageshow', handlePageShow);
    };
  }, [paperId, location.key]);

  // ==================== POLLING – ĐÃ SỬA ĐIỀU KIỆN ====================
  useEffect(() => {
    if (!paperId || !paper) return;

    // ✅ Điều kiện polling mới: poll cho đến khi thực sự hoàn thành
    const isFinalStatus = 
      paper.processing_status === "completed" ||
      paper.processing_status === "processed" ||
      paper.processing_status === "failed" ||
      paper.processing_status === "duplicate_detected";

    if (isFinalStatus) {
      console.log('%c✅ Paper đã hoàn tất, dừng polling', 'color:#16a34a');
      return;
    }

    console.log('%c⏳ Bắt đầu polling mỗi 3s (status đang xử lý)', 'color:#8b5cf6');
    const interval = setInterval(() => loadPaperDetail(), 3000);

    return () => clearInterval(interval);
  }, [paperId, paper?.processing_status, location.key]);   // depend vào processing_status

  return (
    <div className="app-shell">
      <AppHeader
        title="Chi tiết tài liệu"
        subtitle="Xem thông tin chi tiết của tài liệu đã chọn."
        showUploadButton={true}
        extraAction={
          <button
            className="btn btn--secondary"
            onClick={() => navigate("/papers")}
            style={{ marginRight: "1rem" }}
          >
            ← Quay lại danh sách
          </button>
        }
      />

      <main className="app-main app-main--papers">
        <div className="app-main__full">
          {loading ? (
            <div className="card" style={{ padding: "2rem", textAlign: "center" }}>
              Đang tải chi tiết tài liệu...
            </div>
          ) : error ? (
            <div className="card" style={{ padding: "2rem", color: "#dc2626" }}>
              {error}
            </div>
          ) : (
            <PaperDetail paper={paper} />
          )}
        </div>
      </main>
    </div>
  );
}