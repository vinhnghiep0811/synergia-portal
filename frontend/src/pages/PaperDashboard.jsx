import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { PaperList } from "../components/PaperList.jsx";
import { PaperDetail } from "../components/PaperDetail.jsx";

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

export function PaperDashboard() {
  const [papers, setPapers] = useState(MOCK_PAPERS);
  const { paperId } = useParams();
  const navigate = useNavigate();

  const selectedId = paperId ?? (papers[0]?.id ?? null);

  function handleSelect(id) {
    navigate(`/papers/${id}`);
  }

  const selectedPaper = useMemo(
    () => papers.find((p) => p.id === selectedId) ?? null,
    [papers, selectedId]
  );

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
          <PaperList
            papers={papers}
            onSelect={handleSelect}
            selectedId={selectedId}
          />
        </div>
        <div className="app-main__below">
          <PaperDetail paper={selectedPaper} />
        </div>
      </main>
    </div>
  );
}

