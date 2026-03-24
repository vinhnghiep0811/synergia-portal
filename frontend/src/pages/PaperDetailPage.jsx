import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { PaperDetail } from "../components/PaperDetail.jsx";
import { getPaperDetail } from "../services/paperApi.js";

function bytesToMB(bytes) {
  if (!bytes || Number.isNaN(bytes)) return 0;
  return bytes / (1024 * 1024);
}

function mapPaperDetail(detail) {
  return {
    id: detail.id,
    originalFilename: detail.original_filename,
    filename: detail.original_filename,
    title: detail.detected_title || detail.original_filename,
    status: detail.status,
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
    parseStatus: detail.parse_status,
    parseError: detail.parse_error,
    extractedTextPreview: detail.extracted_text_preview,
    detectedDoi: detail.detected_doi,
    detectedFingerprint: detail.detected_fingerprint,
    detectedTitle: detail.detected_title,

    // fallback
    authors: [],
    year: null,
    venue: null,
    canonicalKey:
      detail.detected_doi ||
      detail.detected_fingerprint ||
      detail.canonical_document_id ||
      "",
    hasDeterministicParse: detail.parse_status === "success",
    hasCanonicalMetadata: !!detail.canonical_document_id,
    hasLLMExtraction: false,
  };
}

export function PaperDetailPage() {
  const [paper, setPaper] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const { paperId } = useParams();
  const navigate = useNavigate();

  const loadPaperDetail = async () => {
    if (!paperId) {
      setPaper(null);
      return;
    }

    try {
      setError("");
      const detail = await getPaperDetail(paperId);
      setPaper(mapPaperDetail(detail));
    } catch (error) {
      setError(error.message || "Không thể tải chi tiết paper");
      setPaper(null);
    }
  };

  useEffect(() => {
    let isMounted = true;

    async function initialLoad() {
      if (!paperId) {
        setPaper(null);
        return;
      }

      try {
        setLoading(true);
        setError("");

        const detail = await getPaperDetail(paperId);

        if (!isMounted) return;

        setPaper(mapPaperDetail(detail));
      } catch (error) {
        if (!isMounted) return;
        setError(error.message || "Không thể tải chi tiết paper");
        setPaper(null);
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    initialLoad();

    return () => {
      isMounted = false;
    };
  }, [paperId]);

  useEffect(() => {
    if (!paperId || !paper) return;

    // Only poll if paper is still processing
    const isProcessing = paper.status === 'parse_queued' || 
                       paper.status === 'canonicalized' || 
                       paper.status === 'pending' ||
                       paper.parseStatus === 'processing';

    if (!isProcessing) return;

    const interval = setInterval(loadPaperDetail, 5000); // Poll every 5 seconds

    return () => clearInterval(interval);
  }, [paperId, paper]);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header__main">
          <button
            type="button"
            className="app-logo"
            onClick={() => navigate("/")}
          >
            SY
          </button>
          <div className="app-header__titles">
            <h1 className="app-title">Chi tiết tài liệu</h1>
            <p className="app-subtitle">
              Xem thông tin chi tiết của tài liệu đã chọn.
            </p>
          </div>
        </div>
        <div className="app-header__meta">
          <button
            className="btn btn--secondary"
            onClick={() => navigate("/papers")}
          >
            ← Quay lại danh sách
          </button>
          <span className="app-tag">Single workspace · VM on-prem</span>
        </div>
      </header>

      <main className="app-main app-main--papers">
        <div className="app-main__full">
          {loading ? (
            <div className="card" style={{ padding: "1rem" }}>
              Đang tải chi tiết tài liệu...
            </div>
          ) : error ? (
            <div className="card" style={{ padding: "1rem", color: "#dc2626" }}>
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
