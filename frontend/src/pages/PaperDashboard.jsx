import { useMemo, useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { PaperList } from "../components/PaperList.jsx";
import { getPapers } from "../services/paperApi.js";

const MOCK_PAPERS = [
  {
    id: "P-2024-0001",
    title:
      "Scaling Evidence-Backed Metadata Extraction for Academic PDFs in Small Research Groups",
    authors: ["Nguyen A.", "Tran B.", "Le C."],
    year: 2024,
    venue: "ArXiv",
    status: "processed",
    uploadedBy: "can.nguyen",
    uploadedAt: "2024-02-18T10:15:00Z",
    sizeMB: 1.8,
    canonicalKey: "10.1234/example-doi-0001",
    hasDeterministicParse: true,
    hasCanonicalMetadata: true,
    hasLLMExtraction: false,
  },
  {
    id: "P-2024-0002",
    title:
      "Human-in-the-loop Knowledge Structuring with Canonical Caching for On-prem LLM Pipelines",
    authors: ["Pham D.", "Hoang E."],
    year: 2023,
    venue: "NeurIPS (Workshop)",
    status: "pending",
    uploadedBy: "researcher01",
    uploadedAt: "2024-02-19T09:02:00Z",
    sizeMB: 3.2,
    canonicalKey: "fingerprint:ab39f1",
    hasDeterministicParse: false,
    hasCanonicalMetadata: false,
    hasLLMExtraction: false,
  },
  {
    id: "P-2024-0003",
    title:
      "A Survey on Reference and Citation Importance Modeling in Scientific Literature",
    authors: ["Smith J.", "Kumar R."],
    year: 2022,
    venue: "ACL",
    status: "failed",
    uploadedBy: "can.nguyen",
    uploadedAt: "2024-02-16T15:40:00Z",
    sizeMB: 12.4,
    canonicalKey: "10.5555/example-doi-0003",
    hasDeterministicParse: true,
    hasCanonicalMetadata: false,
    hasLLMExtraction: false,
  },
];

function bytesToMB(bytes) {
  if (!bytes || Number.isNaN(bytes)) return 0;
  return bytes / (1024 * 1024);
}

function mapPaperListItem(item) {
  return {
    id: item.id,
    originalFilename: item.original_filename,
    filename: item.original_filename,
    status: item.status,
    mimeType: item.mime_type,
    fileSizeBytes: item.file_size_bytes,
    sizeMB: bytesToMB(item.file_size_bytes),
    uploadedAt: item.created_at,
    updatedAt: item.updated_at,

    // các field cũ để PaperList không bị vỡ
    title: item.original_filename,
    authors: [],
    year: null,
    venue: null,
    canonicalKey: "",
  };
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
    detectedTitle: detail.detected_title,

    // fallback
    authors: [],
    year: null,
    venue: null,
    canonicalKey: detail.detected_doi || detail.canonical_document_id || "",
    hasDeterministicParse: detail.parse_status === "success",
    hasCanonicalMetadata: !!detail.canonical_document_id,
    hasLLMExtraction: false,
  };
}

export function PaperDashboard() {
  const [papers, setPapers] = useState([]);
  const [loadingList, setLoadingList] = useState(true);
  const [listError, setListError] = useState("");
  const navigate = useNavigate();
  const location = useLocation(); // Hook để lấy state từ router
  const [successMessage, setSuccessMessage] = useState("");

  useEffect(() => {
    if (location.state?.message) {
      setSuccessMessage(location.state.message);
      const timer = setTimeout(() => setSuccessMessage(""), 5000);
      window.history.replaceState({}, document.title);
      return () => clearTimeout(timer);
    }
  }, [location]);

  useEffect(() => {
    let isMounted = true;

    async function loadPapers() {
      try {
        setLoadingList(true);
        setListError("");

        const data = await getPapers(0, 50);

        if (!isMounted) return;

        const mapped = data.map(mapPaperListItem);
        setPapers(mapped);
      } catch (error) {
        if (!isMounted) return;
        setListError(error.message || "Không thể tải danh sách paper");
      } finally {
        if (isMounted) {
          setLoadingList(false);
        }
      }
    }

    loadPapers();

    return () => {
      isMounted = false;
    };
  }, []);

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
            <h1 className="app-title">Danh sách tài liệu</h1>
            <p className="app-subtitle">
              Xem các paper đã upload và trạng thái xử lý.
            </p>
          </div>
        </div>
        <div className="app-header__meta">
          <span className="app-tag">Single workspace · VM on-prem</span>
        </div>
      </header>

      <main className="app-main app-main--papers">
        <div className="app-main__full">
          {successMessage && (
            <div className="card" style={{ 
              backgroundColor: "#f0fdf4", 
              color: "#16a34a", 
              padding: "1rem", 
              marginBottom: "1rem",
              border: "1px solid #bbf7d0",
              borderRadius: "8px",
              display: "flex",
              justifyContent: "space-between"
            }}>
              <span>{successMessage}</span>
              <button onClick={() => setSuccessMessage("")} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#16a34a' }}>✕</button>
            </div>
          )}

          {loadingList ? (
            <div className="card" style={{ padding: "1rem" }}>
              Đang tải danh sách tài liệu...
            </div>
          ) : listError ? (
            <div className="card" style={{ padding: "1rem", color: "#dc2626" }}>
              {listError}
            </div>
          ) : (
            <PaperList papers={papers} />
          )}
        </div>
      </main>
    </div>
  );
}

