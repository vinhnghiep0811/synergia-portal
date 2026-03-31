import { useMemo, useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { PaperList } from "../components/PaperList.jsx";
import { getPapers, getPaperDetail } from "../services/paperApi.js";
import { AppHeader } from "../components/AppHeader.jsx";

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
    detectedTitle: null, // Will be fetched later for processed papers
    detectedDoi: null, // Will be fetched later for processed papers
    detectedFingerprint: null, // Will be fetched later for processed papers
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

        const mappedPapers = data.map(mapPaperListItem);

        // Fetch details for processed papers to get detected_title
        const processedPapers = mappedPapers.filter(
          (p) => p.status === "processed" || p.status === "duplicate_detected"
        );

        if (processedPapers.length > 0) {
          const detailedPapers = await Promise.all(
            processedPapers.map(async (paper) => {
              try {
                const detail = await getPaperDetail(paper.id);
                console.log(`Full API response for paper ${paper.id}:`, detail);
                console.log(`Available DOI fields:`, {
                  detected_doi: detail.detected_doi,
                  doi: detail.doi,
                  canonical_doi: detail.canonical_doi,
                  metadata_doi: detail.metadata_doi,
                  paper_doi: detail.paper_doi,
                  allKeys: Object.keys(detail)
                });
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
                // If detail fetch fails, keep original
                console.warn(`Failed to fetch details for paper ${paper.id}:`, error);
                return paper;
              }
            })
          );

          // Merge processed papers with their details
          const finalPapers = mappedPapers.map((paper) => {
            const detailed = detailedPapers.find((d) => d.id === paper.id);
            return detailed || paper;
          });

          if (!isMounted) return;
          setPapers(finalPapers);
        } else {
          if (!isMounted) return;
          setPapers(mappedPapers);
        }
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
      <AppHeader 
        title="Danh sách tài liệu"
        subtitle="Xem các paper đã upload và trạng thái xử lý."
      />

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

