import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
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
  return authors
    .map((author) => author?.name)
    .filter(Boolean);
}

function mapPaperDetail(detail, canonical) {
  const matchStatus = canonical?.match_status || null;
  const enrichmentStatus = canonical?.enrichment_status || null;

  const semanticScholarStatus = !detail.canonical_document_id
    ? "not_linked"
    : enrichmentStatus || "pending";

  return {
    id: detail.id,
    originalFilename: detail.original_filename,
    filename: detail.original_filename,
    title:
      canonical?.title ||
      canonical?.title_candidate ||
      detail.detected_title ||
      detail.original_filename,
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
    semanticScholarStatus,
    matchStatus,
    canonicalEnrichmentStatus: enrichmentStatus,
    semanticSource: canonical?.metadata_source || null,
    ssMatchConfidence: canonical?.ss_match_confidence || null,
    ssPaperId: canonical?.ss_paper_id || null,
    canonicalTitle: canonical?.title || null,
    canonicalTitleCandidate: canonical?.title_candidate || null,
    canonicalAbstract: canonical?.abstract || null,
    canonicalVenue: canonical?.venue || null,
    canonicalPublicationYear: canonical?.publication_year || null,
    canonicalAuthors: mapCanonicalAuthors(canonical?.authors_json),

    // fallback for existing consumers
    authors: mapCanonicalAuthors(canonical?.authors_json),
    year: canonical?.publication_year || null,
    venue: canonical?.venue || null,
    canonicalKey:
      canonical?.canonical_key ||
      detail.detected_doi ||
      detail.detected_fingerprint ||
      detail.canonical_document_id ||
      "",
    hasDeterministicParse: detail.parse_status === "done",
    hasCanonicalMetadata: enrichmentStatus === "enriched",
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
      const canonical = await getCanonicalDocumentByPaper(paperId);
      setPaper(mapPaperDetail(detail, canonical));
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
        const canonical = await getCanonicalDocumentByPaper(paperId);

        if (!isMounted) return;

        setPaper(mapPaperDetail(detail, canonical));
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

    // Only poll while parse pipeline is still running
    const isParseProcessing =
      paper.status === "parse_queued" ||
      paper.status === "pending" ||
      paper.status === "parsing" ||
      paper.parseStatus === "queued" ||
      paper.parseStatus === "processing";

    const isEnrichProcessing =
      paper.canonicalDocumentId &&
      (paper.semanticScholarStatus === "pending" ||
        paper.semanticScholarStatus === "enriching");

    if (!isParseProcessing && !isEnrichProcessing) return;

    const interval = setInterval(loadPaperDetail, 5000); // Poll every 5 seconds

    return () => clearInterval(interval);
  }, [paperId, paper]);

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
