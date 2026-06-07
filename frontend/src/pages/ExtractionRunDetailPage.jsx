import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getExtractionRunDetail } from "../services/paperApi.js";
import { AppHeader } from "../components/AppHeader.jsx";

// TODO: đặt false sau khi kiểm chứng xong
const USE_MOCK_EVALUATION_SETUP = false;
const MOCK_EVALUATION_SETUP = {
  value: {
    datasets: ["QM9", "ImageNet"],
    metrics: ["mean absolute error", "error ratio", "accuracy"],
    benchmarks: [
      "hand‑engineered molecular representations (Coulomb Matrix, Bag of Bonds, BAML, ECFP4, HDAD)",
      "Molecular Graph Convolution (GC)",
      "Gated Graph Neural Network (GG‑NN)",
    ],
  },
  evidence: [],
};

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
        setRun(data);
      } catch (err) {
        setError(
          err.message || "Không thể tải chi tiết extraction run"
        );
        setRun(null);
      } finally {
        setLoading(false);
      }
    }

    loadRunDetail();
  }, [runId]);

  function formatDate(dateString) {
    if (!dateString) return "-";

    return new Date(dateString).toLocaleDateString(
      "vi-VN",
      {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      }
    );
  }

  function formatLLMProvider(provider, modelName) {
    const p = (provider || "").toLowerCase();
    const m = (modelName || "").toLowerCase();

    if (p === "regex_parsing") return "Regex Parsing";
    if (p === "gemini") return "Gemini";
    if (p === "ollama" && m.includes("gemma"))
      return "Gemma (Ollama)";
    if (p === "ollama") return "Ollama";

    return provider || "-";
  }

  function renderEvidence(evidence) {
    if (!Array.isArray(evidence) || !evidence.length)
      return null;

    return (
      <div style={{ marginTop: "1rem" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            marginBottom: ".75rem",
            paddingBottom: ".5rem",
            borderBottom: "2px solid #e2e8f0"
          }}
        >
          <span style={{ fontSize: "1rem" }}>📄</span>
          <h5
            style={{
              margin: 0,
              color: "#475569",
              fontSize: ".85rem",
              fontWeight: "600",
              textTransform: "uppercase",
              letterSpacing: "0.5px"
            }}
          >
            Evidence ({evidence.length})
          </h5>
        </div>

        {evidence.map((item, index) => (
          <div
            key={index}
            style={{
              background: "linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)",
              border: "1px solid #cbd5e1",
              borderRadius: "12px",
              padding: "1rem",
              marginBottom: ".75rem",
              boxShadow: "0 2px 4px rgba(0,0,0,0.05)"
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
                fontSize: ".75rem",
                color: "#64748b",
                marginBottom: ".75rem",
                fontWeight: "500"
              }}
            >
              <span style={{ 
                background: "#3b82f6", 
                color: "white",
                padding: "0.2rem 0.5rem",
                borderRadius: "4px",
                fontSize: ".7rem",
                fontWeight: "600"
              }}>
                Page {item.page || "N/A"}
              </span>
              <span>•</span>
              <span>{item.section || "N/A"}</span>
            </div>

            <div
              style={{
                background: "white",
                padding: "1rem",
                borderLeft: "4px solid #3b82f6",
                borderRadius: "8px",
                fontSize: ".9rem",
                lineHeight: "1.6",
                color: "#334155",
                boxShadow: "0 1px 3px rgba(0,0,0,0.1)"
              }}
            >
              {item.snippet}
            </div>
          </div>
        ))}
      </div>
    );
  }

  function renderValueWithEvidence(title, field) {
    if (!field?.value) return null;

    const sectionColors = {
      "Problem Statement": { bg: "#fef3c7", border: "#f59e0b", icon: "❓" },
      "Main Method": { bg: "#dbeafe", border: "#3b82f6", icon: "⚙️" },
      "Evaluation Setup": { bg: "#d1fae5", border: "#10b981", icon: "📊" }
    };

    const colors = sectionColors[title] || { bg: "#f1f5f9", border: "#64748b", icon: "📝" };

    return (
      <div style={{ marginBottom: "1.5rem" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            marginBottom: "1rem",
            padding: "0.75rem 1rem",
            background: colors.bg,
            borderRadius: "10px",
            borderLeft: `4px solid ${colors.border}`
          }}
        >
          <span style={{ fontSize: "1.2rem" }}>{colors.icon}</span>
          <h4
            style={{
              margin: 0,
              fontWeight: "700",
              color: "#0f172a",
              fontSize: "1rem"
            }}
          >
            {title}
          </h4>
        </div>

        <div
          style={{
            background: "white",
            padding: "1.25rem",
            borderRadius: "12px",
            border: "1px solid #e2e8f0",
            color: "#334155",
            lineHeight: "1.8",
            boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
            minWidth: 0,
            overflow: "hidden",
          }}
        >
          {typeof field.value === "object"
            ? (
              <pre
                style={{
                  background: "#f8fafc",
                  padding: "1rem",
                  borderRadius: "8px",
                  overflow: "auto",
                  fontSize: ".85rem",
                  border: "1px solid #e2e8f0",
                  margin: 0,
                  maxWidth: "100%",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  overflowWrap: "break-word",
                }}
              >
                {JSON.stringify(
                  field.value,
                  null,
                  2
                )}
              </pre>
            )
            : field.value}
        </div>

        {renderEvidence(field.evidence)}
      </div>
    );
  }

  function renderArrayWithEvidence(
    title,
    items
  ) {
    if (!items?.length) return null;

    const sectionColors = {
      "Contributions": { bg: "#fce7f3", border: "#ec4899", icon: "💡" },
      "Limitations": { bg: "#fee2e2", border: "#ef4444", icon: "⚠️" }
    };

    const colors = sectionColors[title] || { bg: "#f1f5f9", border: "#64748b", icon: "📋" };

    return (
      <div style={{ marginBottom: "1.5rem" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            marginBottom: "1rem",
            padding: "0.75rem 1rem",
            background: colors.bg,
            borderRadius: "10px",
            borderLeft: `4px solid ${colors.border}`
          }}
        >
          <span style={{ fontSize: "1.2rem" }}>{colors.icon}</span>
          <h4
            style={{
              margin: 0,
              fontWeight: "700",
              color: "#0f172a",
              fontSize: "1rem"
            }}
          >
            {title} ({items.length})
          </h4>
        </div>

        {items.map((item, index) => (
          <div
            key={index}
            style={{
              marginBottom: "1.25rem",
              background: "white",
              padding: "1.25rem",
              borderRadius: "12px",
              border: "1px solid #e2e8f0",
              boxShadow: "0 1px 3px rgba(0,0,0,0.05)"
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: "0.75rem",
                marginBottom: "0.75rem"
              }}
            >
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: "28px",
                  height: "28px",
                  background: colors.bg,
                  color: colors.border,
                  borderRadius: "50%",
                  fontSize: ".8rem",
                  fontWeight: "700",
                  flexShrink: 0
                }}
              >
                {index + 1}
              </span>
              <div
                style={{
                  flex: 1,
                  color: "#334155",
                  lineHeight: "1.7",
                  fontSize: ".95rem"
                }}
              >
                {item.value}
              </div>
            </div>

            {renderEvidence(item.evidence)}
          </div>
        ))}
      </div>
    );
  }

  if (loading) {
    return (
      <div className="app-shell">
        <AppHeader
          title="Extraction Run Detail"
        />

        <main className="app-main">
          <div
            className="card"
            style={{
              padding: "3rem",
              textAlign: "center"
            }}
          >
            Loading...
          </div>
        </main>
      </div>
    );
  }

  if (error || !run) {
    return (
      <div className="app-shell">
        <AppHeader
          title="Chi tiết quá trình trích xuất"
        />

        <main className="app-main">
          <div
            className="card"
            style={{
              color: "#dc2626",
              textAlign: "center",
              padding: "3rem"
            }}
          >
            {error}

            <div style={{ marginTop: "1rem" }}>
              <button
                className="btn btn--secondary"
                onClick={() => navigate(-1)}
              >
                Quay lại
              </button>
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="app-shell">

      <AppHeader
        title="Chi tiết quá trình trích xuất"
        subtitle="Kết quả trích xuất thông tin học thuật"
      />

      <main className="app-main app-main--papers">
        <div className="app-main__full">

          <section className="card">

            <header
              className="card__header"
            >
              <div>
                <h2>
                  Extraction Run #{run.id}
                </h2>

                <p
                  style={{
                    color: "#64748b"
                  }}
                >
                  Canonical ID:
                  {" "}
                  <span
                    style={{
                      fontFamily:
                        "monospace"
                    }}
                  >
                    {
                      run.canonical_document_id
                    }
                  </span>
                </p>
              </div>

              <button
                className="btn btn--secondary"
                onClick={() =>
                  navigate(-1)
                }
              >
                ← Quay lại
              </button>
            </header>

            {/* INFO */}
            <div
              style={{
                marginTop: "2rem",
                padding: "1.5rem",
                borderRadius: "16px",
                background: "linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)",
                border: "1px solid #e2e8f0",
                boxShadow: "0 4px 6px rgba(0,0,0,0.05)"
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.75rem",
                  marginBottom: "1.5rem",
                  paddingBottom: "1rem",
                  borderBottom: "2px solid #e2e8f0"
                }}
              >
                <span style={{ fontSize: "1.5rem" }}>📊</span>
                <h3
                  style={{
                    margin: 0,
                    fontSize: "1.25rem",
                    fontWeight: "700",
                    color: "#0f172a"
                  }}
                >
                  Thông tin quá trình trích xuất
                </h3>
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns:
                    "1fr 1fr",
                  gap: "1.5rem",
                  marginTop: "1rem"
                }}
              >
                <div className="card">
                  <dl className="detail-list">

                    <div className="detail-list__item">
                      <dt>Trạng thái</dt>

                      <dd>
                        <span
                          style={{
                            background:
                              run.status ===
                              "completed"
                                ? "#22c55e"
                                : "#f59e0b",

                            color: "white",
                            padding:
                              ".4rem .75rem",
                            borderRadius:
                              "8px"
                          }}
                        >
                          {
                            run.status
                          }
                        </span>
                      </dd>
                    </div>

                    <div className="detail-list__item">
                      <dt>Nhà cung cấp</dt>
                      <dd>
                        {formatLLMProvider(
                          run.provider,
                          run.model_name
                        )}
                      </dd>
                    </div>

                    <div className="detail-list__item">
                      <dt>Mô hình</dt>
                      <dd>
                        {
                          run.model_name
                        }
                      </dd>
                    </div>

                  </dl>
                </div>

                <div className="card">
                  <dl className="detail-list">

                    <div className="detail-list__item">
                      <dt>
                        Lượng token sử dụng
                      </dt>

                      <dd>
                        {
                          run.token_input
                        }
                        {" → "}
                        {
                          run.token_output
                        }
                      </dd>
                    </div>

                    <div className="detail-list__item">
                      <dt>
                        Ngày tạo
                      </dt>

                      <dd>
                        {formatDate(
                          run.created_at
                        )}
                      </dd>
                    </div>

                    <div className="detail-list__item">
                      <dt>
                        Cập nhật lần cuối
                      </dt>

                      <dd>
                        {formatDate(
                          run.updated_at
                        )}
                      </dd>
                    </div>

                  </dl>
                </div>
              </div>
            </div>

            {/* RESULT */}

            <div
              style={{
                marginTop: "2rem",
                padding: "1.5rem",
                borderRadius: "16px",
                background: "linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)",
                border: "1px solid #e2e8f0",
                boxShadow: "0 4px 6px rgba(0,0,0,0.05)"
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.75rem",
                  marginBottom: "1.5rem",
                  paddingBottom: "1rem",
                  borderBottom: "2px solid #e2e8f0"
                }}
              >
                <span style={{ fontSize: "1.5rem" }}>🧠</span>
                <h3
                  style={{
                    margin: 0,
                    fontSize: "1.25rem",
                    fontWeight: "700",
                    color: "#0f172a"
                  }}
                >
                  Nội dung được trích xuất
                </h3>
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns:
                    "1fr 1fr",
                  gap: "2rem",
                  marginTop: "1rem",
                  minWidth: 0,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    flexDirection:
                      "column",
                    gap: "0",
                    minWidth: 0,
                  }}
                >
                  <div className="card" style={{ padding: "1.5rem", borderRadius: "12px", border: "1px solid #e2e8f0", boxShadow: "0 2px 4px rgba(0,0,0,0.05)" }}>
                    {renderValueWithEvidence(
                      "I.Vấn đề nghiên cứu",
                      run.problem_statement
                    )}
                  </div>

                  <div className="card" style={{ padding: "1.5rem", borderRadius: "12px", border: "1px solid #e2e8f0", boxShadow: "0 2px 4px rgba(0,0,0,0.05)" }}>
                    {renderValueWithEvidence(
                      "II.Phương pháp chính",
                      run.main_method
                    )}
                  </div>

                  <div className="card" style={{ padding: "1.5rem", borderRadius: "12px", border: "1px solid #e2e8f0", boxShadow: "0 2px 4px rgba(0,0,0,0.05)" }}>
                    {renderArrayWithEvidence(
                      "III.Đóng góp",
                      run.contributions
                    )}
                  </div>
                </div>

                <div
                  style={{
                    display: "flex",
                    flexDirection:
                      "column",
                    gap: "0",
                    minWidth: 0,
                  }}
                >
                  <div className="card" style={{ padding: "1.5rem", borderRadius: "12px", border: "1px solid #e2e8f0", boxShadow: "0 2px 4px rgba(0,0,0,0.05)" }}>
                    {renderArrayWithEvidence(
                      "IV.Hạn chế",
                      run.limitations
                    )}
                  </div>

                  <div className="card" style={{ padding: "1.5rem", borderRadius: "12px", border: "1px solid #e2e8f0", boxShadow: "0 2px 4px rgba(0,0,0,0.05)", minWidth: 0 }}>
                    {renderValueWithEvidence(
                      "V.Thiết lập đánh giá",
                      USE_MOCK_EVALUATION_SETUP
                        ? MOCK_EVALUATION_SETUP
                        : run.evaluation_setup
                    )}
                  </div>
                </div>
              </div>
            </div>

          </section>
        </div>
      </main>

    </div>
  );
}