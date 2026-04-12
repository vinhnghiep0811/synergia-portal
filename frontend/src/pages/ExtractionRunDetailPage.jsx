import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getExtractionRunDetail } from "../services/paperApi.js";
import { AppHeader } from "../components/AppHeader.jsx";

export function ExtractionRunDetailPage() {
  const { runId } = useParams();
  const navigate = useNavigate();

  const [run, setRun] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadRunDetail() {
      if (!runId) return;

      try {
        setLoading(true);
        setError("");
        const data = await getExtractionRunDetail(runId);
        console.log("📦 Extraction run data received:", data);
        setRun(data);
      } catch (err) {
        console.error("❌ Error loading extraction run:", err);
        setError(err.message || "Không thể tải chi tiết extraction run");
        setRun(null);
      } finally {
        setLoading(false);
      }
    }

    loadRunDetail();
  }, [runId]);

  function formatDate(dateString) {
    if (!dateString) return "-";
    const date = new Date(dateString);
    return date.toLocaleDateString("vi-VN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function formatLLMProvider(provider, modelName) {
    const normalizedProvider = (provider || "").toLowerCase();
    const normalizedModel = (modelName || "").toLowerCase();

    if (normalizedProvider === "gemini") return "Gemini";
    if (normalizedProvider === "ollama" && normalizedModel.includes("gemma")) {
      return "Gemma (Ollama)";
    }
    if (normalizedProvider === "ollama") return "Ollama";
    if (normalizedModel.includes("gemini")) return "Gemini";
    if (normalizedModel.includes("gemma")) return "Gemma";
    if (provider) return provider;
    return "-";
  }

  // ==================== RENDER HELPERS ====================
  function renderEvidence(evidence) {
    if (!Array.isArray(evidence) || evidence.length === 0) return null;

    return (
      <div style={{ marginTop: "1rem" }}>
        <h5 style={{ fontSize: "0.9rem", fontWeight: "600", marginBottom: "0.5rem", color: "#374151" }}>
          Evidence
        </h5>
        {evidence.map((item, index) => (
          <div key={index} style={{
            backgroundColor: "#f8fafc",
            border: "1px solid #e2e8f0",
            borderRadius: "6px",
            padding: "1rem",
            marginBottom: "0.75rem"
          }}>
            <div style={{ fontSize: "0.85rem", color: "#64748b", marginBottom: "0.5rem" }}>
              Page {item.page || "N/A"} • Section: {item.section || "N/A"}
            </div>
            <div style={{
              fontFamily: "monospace",
              fontSize: "0.875rem",
              backgroundColor: "#ffffff",
              padding: "0.75rem",
              borderRadius: "4px",
              borderLeft: "3px solid #3b82f6"
            }}>
              {item.snippet}
            </div>
          </div>
        ))}
      </div>
    );
  }

  function renderValueWithEvidence(title, field) {
    if (!field?.value) return null;

    const value = field.value;
    let displayValue = typeof value === "string" || typeof value === "number" 
      ? value 
      : value && typeof value === "object" 
        ? <pre style={{ backgroundColor: "#f8fafc", padding: "1rem", borderRadius: "6px", fontSize: "0.85rem", overflow: "auto", margin: 0, color: "#1e3a8a" }}>
            {JSON.stringify(value, null, 2)}
          </pre>
        : String(value);

    return (
      <div className="extraction-field">
        <h4 className="extraction-field__title">{title}</h4>
        <div className="extraction-field__content">{displayValue}</div>
        {field.evidence && renderEvidence(field.evidence)}
      </div>
    );
  }

  function renderArrayWithEvidence(title, items) {
    if (!Array.isArray(items) || items.length === 0) return null;

    return (
      <div className="extraction-field">
        <h4 className="extraction-field__title">{title}</h4>
        {items.map((item, index) => (
          <div key={index} style={{ marginBottom: "1.25rem" }}>
            <div className="extraction-field__content">
              {item?.value || "No value provided"}
            </div>
            {item?.evidence && renderEvidence(item.evidence)}
          </div>
        ))}
      </div>
    );
  }

  if (loading) {
    return (
      <div className="app-shell">
        <AppHeader title="Extraction Run Detail" subtitle="Chi tiết quá trình trích xuất bằng LLM" />
        <main className="app-main app-main--papers">
          <div className="app-main__full">
            <div className="card" style={{ padding: "3rem", textAlign: "center" }}>
              Đang tải chi tiết extraction run...
            </div>
          </div>
        </main>
      </div>
    );
  }

  if (error || !run) {
    return (
      <div className="app-shell">
        <AppHeader title="Extraction Run Detail" subtitle="Chi tiết quá trình trích xuất bằng LLM" />
        <main className="app-main app-main--papers">
          <div className="app-main__full">
            <div className="card" style={{ padding: "2rem", textAlign: "center", color: "#dc2626" }}>
              {error || "Không tìm thấy extraction run"}
              <div style={{ marginTop: "1.5rem" }}>
                <button className="btn btn--secondary" onClick={() => navigate(-1)}>
                  Quay lại
                </button>
              </div>
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <AppHeader 
        title="Extraction Run Detail" 
        subtitle="Chi tiết quá trình trích xuất thông tin học thuật bằng LLM" 
      />

      <main className="app-main app-main--papers">
        <div className="app-main__full">
          <section className="card">
            <header className="card__header">
              <div>
                <h2 className="card__title">Extraction Run #{run.id}</h2>
                <p className="card__subtitle">
                  Canonical Document ID: <span style={{ fontFamily: "monospace" }}>{run.canonical_document_id}</span>
                </p>
              </div>
              <button className="btn btn--secondary" onClick={() => navigate(-1)}>
                ← Quay lại
              </button>
            </header>

            {/* ==================== THÔNG TIN RUN - Chia 3/3 ==================== */}
            <div className="detail-section">
              <h3 className="detail-section__title">Thông tin trích xuất</h3>
              <div style={{ 
                display: "grid", 
                gridTemplateColumns: "1fr 1fr", 
                gap: "2rem" 
              }}>
                {/* Cột trái - 3 thông tin */}
                <dl className="detail-list">
                  <div className="detail-list__item">
                    <dt>Status</dt>
                    <dd>
                      <span style={{
                        backgroundColor: run.status === 'completed' ? '#22c55e' : '#f59e0b',
                        color: 'white',
                        padding: '0.35rem 0.75rem',
                        borderRadius: '6px',
                        fontSize: '0.85rem',
                        fontWeight: '500'
                      }}>
                        {run.status?.toUpperCase() || "UNKNOWN"}
                      </span>
                    </dd>
                  </div>
                  <div className="detail-list__item"><dt>Provider</dt><dd>{formatLLMProvider(run.provider, run.model_name)}</dd></div>
                  <div className="detail-list__item"><dt>Model</dt><dd>{run.model_name || "-"}</dd></div>
                  <div className="detail-list__item"><dt>Prompt Version</dt><dd>{run.prompt_version || "-"}</dd></div>
                </dl>

                {/* Cột phải - 3 thông tin */}
                <dl className="detail-list">
                  <div className="detail-list__item"><dt>Token Usage</dt><dd>{run.token_input ?? 0} → {run.token_output ?? 0}</dd></div>
                  <div className="detail-list__item"><dt>Created At</dt><dd>{formatDate(run.created_at)}</dd></div>
                  <div className="detail-list__item"><dt>Updated At</dt><dd>{formatDate(run.updated_at)}</dd></div>
                </dl>
              </div>
            </div>

            {/* ==================== KẾT QUẢ TRÍCH XUẤT - 2 cột ==================== */}
            <div className="detail-section">
              <h3 className="detail-section__title">Kết quả trích xuất</h3>
              <div style={{ 
                display: "grid", 
                gridTemplateColumns: "1fr 1fr", 
                gap: "2rem" 
              }}>
                {/* Cột trái */}
                <div>
                  {renderValueWithEvidence("Problem Statement", run.problem_statement)}
                  {renderValueWithEvidence("Main Method", run.main_method)}
                  {renderArrayWithEvidence("Contributions", run.contributions)}
                </div>

                {/* Cột phải */}
                <div>
                  {renderArrayWithEvidence("Limitations", run.limitations)}
                  {renderValueWithEvidence("Evaluation Setup", run.evaluation_setup)}
                </div>
              </div>
            </div>

            {/* Raw LLM Response */}
            {/* {run.raw_llm_response && (
              <div className="detail-section" style={{ marginTop: "2rem" }}>
                <h3 className="detail-section__title">Raw LLM Response</h3>
                <div style={{
                  backgroundColor: "#0f172a",
                  color: "#e2e8f0",
                  padding: "1.25rem",
                  borderRadius: "8px",
                  fontFamily: "monospace",
                  fontSize: "0.85rem",
                  lineHeight: "1.6",
                  maxHeight: "500px",
                  overflow: "auto",
                  whiteSpace: "pre-wrap"
                }}>
                  {run.raw_llm_response}
                </div>
              </div>
            )} */}
          </section>
        </div>
      </main>
    </div>
  );
}