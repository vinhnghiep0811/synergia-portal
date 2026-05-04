import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { AppHeader } from "../components/AppHeader.jsx";
import {
  getPublishMetadataPreview,
  publishPaper,
  updatePublishMetadataDraft,
} from "../services/paperApi.js";

function listToMultiline(values) {
  if (!Array.isArray(values) || values.length === 0) return "";
  return values.join("\n");
}

function splitToList(value) {
  if (!value) return [];
  return value
    .split(/\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function mapPreviewToForm(preview) {
  const metadata = preview?.metadata || {};
  const evaluation = metadata.evaluation_setup || {};

  return {
    title: metadata.title || "",
    abstract: metadata.abstract || "",
    venue: metadata.venue || "",
    year: metadata.year == null ? "" : String(metadata.year),
    authorsText: listToMultiline(metadata.authors),

    problemStatement: metadata.problem_statement || "",
    mainMethod: metadata.main_method || "",
    contributionsText: listToMultiline(metadata.contributions),
    limitationsText: listToMultiline(metadata.limitations),

    datasetsText: (evaluation.datasets || []).join(", "),
    metricsText: (evaluation.metrics || []).join(", "),
    benchmarksText: (evaluation.benchmarks || []).join(", "),
  };
}

function buildPayload(form) {
  const year = form.year.trim() === "" ? null : Number(form.year);

  return {
    title: form.title.trim() || null,
    abstract: form.abstract.trim() || null,
    venue: form.venue.trim() || null,
    year: Number.isNaN(year) ? null : year,
    authors: splitToList(form.authorsText),

    problem_statement: form.problemStatement.trim() || null,
    main_method: form.mainMethod.trim() || null,
    contributions: splitToList(form.contributionsText),
    limitations: splitToList(form.limitationsText),

    evaluation_setup: {
      datasets: splitToList(form.datasetsText),
      metrics: splitToList(form.metricsText),
      benchmarks: splitToList(form.benchmarksText),
    },
  };
}

function formatStatus(value) {
  if (!value) return "-";
  return value.replace(/_/g, " ");
}

export function PublishConfirmPage() {
  const { paperId } = useParams();
  const navigate = useNavigate();

  const [preview, setPreview] = useState(null);
  const [form, setForm] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);

  const [loadError, setLoadError] = useState("");
  const [notice, setNotice] = useState(null);

  const canSubmit = !loading && !saving && !publishing && !!form;

  useEffect(() => {
    if (!notice || notice.type === "error") return;

    const timeout = setTimeout(() => {
      setNotice(null);
    }, 3500);

    return () => clearTimeout(timeout);
  }, [notice]);

  useEffect(() => {
    if (!paperId) return;

    let isMounted = true;

    async function loadPreview() {
      try {
        setLoading(true);
        setLoadError("");
        setNotice(null);
        const data = await getPublishMetadataPreview(paperId);
        if (!isMounted) return;

        setPreview(data);
        setForm(mapPreviewToForm(data));
      } catch (err) {
        if (!isMounted) return;
        setLoadError(err.message || "Không thể tải metadata publish");
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    loadPreview();

    return () => {
      isMounted = false;
    };
  }, [paperId]);

  function updateForm(field, value) {
    setForm((prev) => ({
      ...prev,
      [field]: value,
    }));
  }

  async function handleSaveDraft(throwOnError = false) {
    if (!paperId || !form) return;

    try {
      setSaving(true);
      setNotice(null);
      const payload = buildPayload(form);
      const data = await updatePublishMetadataDraft(paperId, payload);

      setPreview(data);
      setForm(mapPreviewToForm(data));
      setNotice({
        type: "success",
        message: "Đã lưu bản nháp metadata thành công.",
      });

      return data;
    } catch (err) {
      setNotice({
        type: "error",
        message: err.message || "Không thể lưu bản nháp metadata",
      });
      if (throwOnError) {
        throw err;
      }
    } finally {
      setSaving(false);
    }
  }

  async function handlePublish() {
    if (!paperId) return;

    try {
      setPublishing(true);
      setNotice(null);

      await handleSaveDraft(true);
      const result = await publishPaper(paperId);

      navigate(`/papers/${paperId}`, {
        replace: true,
        state: {
          message: `Published thành công phiên bản ${result.version_number}.`,
        },
      });
    } catch (err) {
      setNotice({
        type: "error",
        message: err.message || "Không thể publish tài liệu",
      });
    } finally {
      setPublishing(false);
    }
  }

  return (
    <div className="app-shell">
      <AppHeader
        title="Xác nhận Publish"
        subtitle="Kiểm duyệt và chỉnh sửa metadata trước khi publish tài liệu."
        extraAction={
          <button
            className="btn btn--secondary"
            style={{ marginRight: "1rem" }}
            onClick={() => navigate(`/papers/${paperId}`)}
          >
            ← Quay lại
          </button>
        }
      />

      <main className="app-main app-main--papers">
        <div className="app-main__full">
          {loading ? (
            <div className="card" style={{ padding: "3rem", textAlign: "center" }}>
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
                color: "white",
                animation: "spin 1s linear infinite"
              }}>
                ⚡
              </div>
              <h3 style={{
                fontSize: "1.1rem",
                fontWeight: "600",
                color: "#374151",
                margin: "0 0 0.5rem"
              }}>
                Đang tải metadata...
              </h3>
              <p style={{
                fontSize: "0.9rem",
                color: "#6b7280",
                margin: 0
              }}>
                Vui lòng chờ trong giây lát.
              </p>
            </div>
          ) : loadError ? (
            <div className="card" style={{ padding: "3rem", textAlign: "center" }}>
              <div style={{
                width: "48px",
                height: "48px",
                backgroundColor: "#ef4444",
                borderRadius: "50%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 1rem",
                fontSize: "1.5rem",
                color: "white"
              }}>
                ❌
              </div>
              <h3 style={{
                fontSize: "1.1rem",
                fontWeight: "600",
                color: "#dc2626",
                margin: "0 0 0.5rem"
              }}>
                Lỗi tải metadata
              </h3>
              <p style={{
                fontSize: "0.9rem",
                color: "#991b1b",
                margin: 0
              }}>
                {loadError}
              </p>
            </div>
          ) : (
            <section className="card publish-confirm-card">
              <header className="card__header">
                <div>
                  <h2 className="card__title">Xem trước Metadata</h2>
                  <p className="card__subtitle">
                    Kiểm tra và chỉnh sửa thông tin trước khi publish. Các trường đã được tự động điền từ Semantic Scholar và AI.
                  </p>
                </div>
              </header>

              {preview && (
                <div className="detail-section">
                  <h3 className="detail-section__title">Thông tin tài liệu</h3>
                  <dl className="detail-list">
                    <div className="detail-list__item">
                      <dt>Paper ID</dt>
                      <dd><code style={{ backgroundColor: "#f3f4f6", padding: "0.25rem 0.5rem", borderRadius: "4px", fontSize: "0.9rem" }}>{preview.paper_id}</code></dd>
                    </div>
                    <div className="detail-list__item">
                      <dt>Trạng thái Publish</dt>
                      <dd><span className={`status-badge status-badge--${preview.publication_status}`}>{formatStatus(preview.publication_status)}</span></dd>
                    </div>
                    <div className="detail-list__item">
                      <dt>Trạng thái Semantic</dt>
                      <dd><span className={`status-badge status-badge--${preview.semantic_status}`}>{formatStatus(preview.semantic_status)}</span></dd>
                    </div>
                    <div className="detail-list__item">
                      <dt>Trạng thái Extraction</dt>
                      <dd><span className={`status-badge status-badge--${preview.extraction_status}`}>{formatStatus(preview.extraction_status)}</span></dd>
                    </div>
                    <div className="detail-list__item">
                      <dt>Chế độ</dt>
                      <dd>
                        {preview.is_editing_draft ? (
                          <span style={{ color: "#059669", fontWeight: "500" }}> Đang sử dụng bản nháp đã lưu</span>
                        ) : (
                          <span style={{ color: "#6b7280", fontWeight: "500" }}> Sử dụng metadata tự động</span>
                        )}
                      </dd>
                    </div>
                  </dl>
                </div>
              )}

              {notice && (
                <div 
                  className={`card ${notice.type === "error" ? "card--error" : "card--success"}`}
                  style={{ 
                    marginBottom: "1.5rem",
                    padding: "1rem",
                    borderLeft: `4px solid ${notice.type === "error" ? "#dc2626" : "#059669"}`,
                    backgroundColor: notice.type === "error" ? "#fef2f2" : "#f0fdf4"
                  }}
                >
                  <span style={{ 
                    fontWeight: "500", 
                    color: notice.type === "error" ? "#dc2626" : "#059669" 
                  }}>
                    {notice.message}
                  </span>
                </div>
              )}

              {form && (
                <>
                  {/* Academic Header */}
                  <div style={{
                    borderBottom: "2px solid #1e3a5f",
                    paddingBottom: "1.5rem",
                    marginBottom: "2rem"
                  }}>
                    <h2 style={{
                      fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                      fontSize: "1.75rem",
                      fontWeight: "600",
                      color: "#1e3a5f",
                      margin: "0 0 0.5rem 0",
                      letterSpacing: "-0.02em"
                    }}>
                      📄 Biểu mẫu metadata bài báo khoa học
                    </h2>
                    <p style={{
                      fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                      fontSize: "0.95rem",
                      color: "#4a5568",
                      margin: 0,
                      fontStyle: "italic"
                    }}>
                      Vui lòng kiểm tra và chỉnh sửa thông tin bên dưới trước khi xuất bản
                    </p>
                  </div>

                  <div className="detail-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "2rem" }}>
                    {/* Left Column - Basic Metadata */}
                    <div className="detail-section" style={{
                      backgroundColor: "#fafbfc",
                      border: "1px solid #e2e8f0",
                      borderRadius: "8px",
                      padding: "1.5rem",
                      boxShadow: "0 1px 3px rgba(0,0,0,0.05)"
                    }}>
                      <div style={{
                        borderLeft: "4px solid #2c5282",
                        paddingLeft: "1rem",
                        marginBottom: "1.5rem"
                      }}>
                        <h3 style={{
                          fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                          fontSize: "1.1rem",
                          fontWeight: "600",
                          color: "#2c5282",
                          margin: "0 0 0.25rem 0"
                        }}>
                          Thông tin cơ bản
                        </h3>
                        <p style={{
                          fontSize: "0.8rem",
                          color: "#718096",
                          margin: 0
                        }}>
                          Thông tin bibliographic chính của bài báo
                        </p>
                      </div>

                      <div style={{ marginBottom: "1.25rem" }}>
                        <label style={{
                          display: "block",
                          fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                          fontSize: "0.85rem",
                          fontWeight: "600",
                          color: "#2d3748",
                          marginBottom: "0.5rem",
                          textTransform: "uppercase",
                          letterSpacing: "0.05em"
                        }}>
                          Tiêu đề bài báo <span style={{ color: "#e53e3e" }}>*</span>
                        </label>
                        <input
                          type="text"
                          value={form.title}
                          onChange={(e) => updateForm("title", e.target.value)}
                          placeholder="Nhập tiêu đề đầy đủ của bài báo"
                          style={{
                            width: "100%",
                            padding: "0.75rem 1rem",
                            border: "2px solid #cbd5e0",
                            borderRadius: "6px",
                            fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                            fontSize: "0.95rem",
                            backgroundColor: "#fff",
                            transition: "all 0.2s ease",
                            boxSizing: "border-box"
                          }}
                          onFocus={(e) => {
                            e.target.style.borderColor = "#2c5282";
                            e.target.style.boxShadow = "0 0 0 3px rgba(44, 82, 130, 0.1)";
                          }}
                          onBlur={(e) => {
                            e.target.style.borderColor = "#cbd5e0";
                            e.target.style.boxShadow = "none";
                          }}
                        />
                      </div>

                      <div style={{ marginBottom: "1.25rem" }}>
                        <label style={{
                          display: "block",
                          fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                          fontSize: "0.85rem",
                          fontWeight: "600",
                          color: "#2d3748",
                          marginBottom: "0.5rem",
                          textTransform: "uppercase",
                          letterSpacing: "0.05em"
                        }}>
                          Tóm tắt (Abstract)
                        </label>
                        <textarea
                          rows={5}
                          value={form.abstract}
                          onChange={(e) => updateForm("abstract", e.target.value)}
                          placeholder="Nhập tóm tắt nội dung chính của bài báo..."
                          style={{
                            width: "100%",
                            padding: "0.75rem 1rem",
                            border: "2px solid #cbd5e0",
                            borderRadius: "6px",
                            fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                            fontSize: "0.9rem",
                            lineHeight: "1.6",
                            backgroundColor: "#fff",
                            resize: "vertical",
                            transition: "all 0.2s ease",
                            boxSizing: "border-box"
                          }}
                          onFocus={(e) => {
                            e.target.style.borderColor = "#2c5282";
                            e.target.style.boxShadow = "0 0 0 3px rgba(44, 82, 130, 0.1)";
                          }}
                          onBlur={(e) => {
                            e.target.style.borderColor = "#cbd5e0";
                            e.target.style.boxShadow = "none";
                          }}
                        />
                      </div>

                      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "1rem", marginBottom: "1.25rem" }}>
                        <div>
                          <label style={{
                            display: "block",
                            fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                            fontSize: "0.85rem",
                            fontWeight: "600",
                            color: "#2d3748",
                            marginBottom: "0.5rem",
                            textTransform: "uppercase",
                            letterSpacing: "0.05em"
                          }}>
                            Hội thảo / Tạp chí
                          </label>
                          <input
                            type="text"
                            value={form.venue}
                            onChange={(e) => updateForm("venue", e.target.value)}
                            placeholder="VD: NeurIPS, ICML, Nature"
                            style={{
                              width: "100%",
                              padding: "0.75rem 1rem",
                              border: "2px solid #cbd5e0",
                              borderRadius: "6px",
                              fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                              fontSize: "0.9rem",
                              backgroundColor: "#fff",
                              transition: "all 0.2s ease",
                              boxSizing: "border-box"
                            }}
                            onFocus={(e) => {
                              e.target.style.borderColor = "#2c5282";
                              e.target.style.boxShadow = "0 0 0 3px rgba(44, 82, 130, 0.1)";
                            }}
                            onBlur={(e) => {
                              e.target.style.borderColor = "#cbd5e0";
                              e.target.style.boxShadow = "none";
                            }}
                          />
                        </div>

                        <div>
                          <label style={{
                            display: "block",
                            fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                            fontSize: "0.85rem",
                            fontWeight: "600",
                            color: "#2d3748",
                            marginBottom: "0.5rem",
                            textTransform: "uppercase",
                            letterSpacing: "0.05em"
                          }}>
                            Năm xuất bản
                          </label>
                          <input
                            type="number"
                            value={form.year}
                            onChange={(e) => updateForm("year", e.target.value)}
                            placeholder="2024"
                            min="1900"
                            max="2030"
                            style={{
                              width: "100%",
                              padding: "0.75rem 1rem",
                              border: "2px solid #cbd5e0",
                              borderRadius: "6px",
                              fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                              fontSize: "0.9rem",
                              backgroundColor: "#fff",
                              transition: "all 0.2s ease",
                              boxSizing: "border-box"
                            }}
                            onFocus={(e) => {
                              e.target.style.borderColor = "#2c5282";
                              e.target.style.boxShadow = "0 0 0 3px rgba(44, 82, 130, 0.1)";
                            }}
                            onBlur={(e) => {
                              e.target.style.borderColor = "#cbd5e0";
                              e.target.style.boxShadow = "none";
                            }}
                          />
                        </div>
                      </div>

                      <div style={{ marginBottom: "1.25rem" }}>
                        <label style={{
                          display: "block",
                          fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                          fontSize: "0.85rem",
                          fontWeight: "600",
                          color: "#2d3748",
                          marginBottom: "0.5rem",
                          textTransform: "uppercase",
                          letterSpacing: "0.05em"
                        }}>
                          Tác giả (mỗi tác giả một dòng)
                        </label>
                        <textarea
                          rows={5}
                          value={form.authorsText}
                          onChange={(e) => updateForm("authorsText", e.target.value)}
                          placeholder="Nguyễn Văn A&#10;Trần Thị B&#10;Lê Văn C"
                          style={{
                            width: "100%",
                            padding: "0.75rem 1rem",
                            border: "2px solid #cbd5e0",
                            borderRadius: "6px",
                            fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                            fontSize: "0.9rem",
                            lineHeight: "1.6",
                            backgroundColor: "#fff",
                            resize: "vertical",
                            transition: "all 0.2s ease",
                            boxSizing: "border-box"
                          }}
                          onFocus={(e) => {
                            e.target.style.borderColor = "#2c5282";
                            e.target.style.boxShadow = "0 0 0 3px rgba(44, 82, 130, 0.1)";
                          }}
                          onBlur={(e) => {
                            e.target.style.borderColor = "#cbd5e0";
                            e.target.style.boxShadow = "none";
                          }}
                        />
                      </div>
                    </div>

                    {/* Right Column - AI Metadata */}
                    <div>
                      <div className="detail-section" style={{
                        backgroundColor: "#fafbfc",
                        border: "1px solid #e2e8f0",
                        borderRadius: "8px",
                        padding: "1.5rem",
                        marginBottom: "1.5rem",
                        boxShadow: "0 1px 3px rgba(0,0,0,0.05)"
                      }}>
                        <div style={{
                          borderLeft: "4px solid #744210",
                          paddingLeft: "1rem",
                          marginBottom: "1.5rem"
                        }}>
                          <h3 style={{
                            fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                            fontSize: "1.1rem",
                            fontWeight: "600",
                            color: "#744210",
                            margin: "0 0 0.25rem 0"
                          }}>
                            🔬 Phân tích nội dung (AI)
                          </h3>
                          <p style={{
                            fontSize: "0.8rem",
                            color: "#718096",
                            margin: 0
                          }}>
                            Các thông tin được trích xuất tự động từ nội dung bài báo
                          </p>
                        </div>

                        <div style={{ marginBottom: "1.25rem" }}>
                          <label style={{
                            display: "block",
                            fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                            fontSize: "0.85rem",
                            fontWeight: "600",
                            color: "#2d3748",
                            marginBottom: "0.5rem"
                          }}>
                            Trở ngại nghiên cứu (Research Problem)
                          </label>
                          <textarea
                            rows={3}
                            value={form.problemStatement}
                            onChange={(e) => updateForm("problemStatement", e.target.value)}
                            placeholder="Mô tả vấn đề chính mà bài báo giải quyết..."
                            style={{
                              width: "100%",
                              padding: "0.75rem 1rem",
                              border: "2px solid #d69e2e",
                              borderRadius: "6px",
                              fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                              fontSize: "0.9rem",
                              lineHeight: "1.6",
                              backgroundColor: "#fffbeb",
                              resize: "vertical",
                              transition: "all 0.2s ease",
                              boxSizing: "border-box"
                            }}
                            onFocus={(e) => {
                              e.target.style.borderColor = "#975a16";
                              e.target.style.boxShadow = "0 0 0 3px rgba(151, 90, 22, 0.1)";
                            }}
                            onBlur={(e) => {
                              e.target.style.borderColor = "#d69e2e";
                              e.target.style.boxShadow = "none";
                            }}
                          />
                        </div>

                        <div style={{ marginBottom: "1.25rem" }}>
                          <label style={{
                            display: "block",
                            fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                            fontSize: "0.85rem",
                            fontWeight: "600",
                            color: "#2d3748",
                            marginBottom: "0.5rem"
                          }}>
                            Phương pháp chính (Methodology)
                          </label>
                          <textarea
                            rows={3}
                            value={form.mainMethod}
                            onChange={(e) => updateForm("mainMethod", e.target.value)}
                            placeholder="Mô tả phương pháp, kỹ thuật đề xuất..."
                            style={{
                              width: "100%",
                              padding: "0.75rem 1rem",
                              border: "2px solid #d69e2e",
                              borderRadius: "6px",
                              fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                              fontSize: "0.9rem",
                              lineHeight: "1.6",
                              backgroundColor: "#fffbeb",
                              resize: "vertical",
                              transition: "all 0.2s ease",
                              boxSizing: "border-box"
                            }}
                            onFocus={(e) => {
                              e.target.style.borderColor = "#975a16";
                              e.target.style.boxShadow = "0 0 0 3px rgba(151, 90, 22, 0.1)";
                            }}
                            onBlur={(e) => {
                              e.target.style.borderColor = "#d69e2e";
                              e.target.style.boxShadow = "none";
                            }}
                          />
                        </div>

                        <div style={{ marginBottom: "1.25rem" }}>
                          <label style={{
                            display: "block",
                            fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                            fontSize: "0.85rem",
                            fontWeight: "600",
                            color: "#2d3748",
                            marginBottom: "0.5rem"
                          }}>
                            Đóng góp (Contributions)
                          </label>
                          <textarea
                            rows={4}
                            value={form.contributionsText}
                            onChange={(e) => updateForm("contributionsText", e.target.value)}
                            placeholder="Liệt kê các đóng góp chính (mỗi dòng một đóng góp)..."
                            style={{
                              width: "100%",
                              padding: "0.75rem 1rem",
                              border: "2px solid #d69e2e",
                              borderRadius: "6px",
                              fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                              fontSize: "0.9rem",
                              lineHeight: "1.6",
                              backgroundColor: "#fffbeb",
                              resize: "vertical",
                              transition: "all 0.2s ease",
                              boxSizing: "border-box"
                            }}
                            onFocus={(e) => {
                              e.target.style.borderColor = "#975a16";
                              e.target.style.boxShadow = "0 0 0 3px rgba(151, 90, 22, 0.1)";
                            }}
                            onBlur={(e) => {
                              e.target.style.borderColor = "#d69e2e";
                              e.target.style.boxShadow = "none";
                            }}
                          />
                        </div>

                        <div style={{ marginBottom: "0" }}>
                          <label style={{
                            display: "block",
                            fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                            fontSize: "0.85rem",
                            fontWeight: "600",
                            color: "#2d3748",
                            marginBottom: "0.5rem"
                          }}>
                            Hạn chế (Limitations)
                          </label>
                          <textarea
                            rows={4}
                            value={form.limitationsText}
                            onChange={(e) => updateForm("limitationsText", e.target.value)}
                            placeholder="Liệt kê các hạn chế và phạm vi áp dụng..."
                            style={{
                              width: "100%",
                              padding: "0.75rem 1rem",
                              border: "2px solid #d69e2e",
                              borderRadius: "6px",
                              fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                              fontSize: "0.9rem",
                              lineHeight: "1.6",
                              backgroundColor: "#fffbeb",
                              resize: "vertical",
                              transition: "all 0.2s ease",
                              boxSizing: "border-box"
                            }}
                            onFocus={(e) => {
                              e.target.style.borderColor = "#975a16";
                              e.target.style.boxShadow = "0 0 0 3px rgba(151, 90, 22, 0.1)";
                            }}
                            onBlur={(e) => {
                              e.target.style.borderColor = "#d69e2e";
                              e.target.style.boxShadow = "none";
                            }}
                          />
                        </div>
                      </div>

                      {/* Evaluation Section */}
                      <div className="detail-section" style={{
                        backgroundColor: "#f0fff4",
                        border: "1px solid #9ae6b4",
                        borderRadius: "8px",
                        padding: "1.5rem",
                        boxShadow: "0 1px 3px rgba(0,0,0,0.05)"
                      }}>
                        <div style={{
                          borderLeft: "4px solid " + "#276749",
                          paddingLeft: "1rem",
                          marginBottom: "1.5rem"
                        }}>
                          <h4 style={{
                            fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                            fontSize: "1rem",
                            fontWeight: "600",
                            color: "#276749",
                            margin: "0 0 0.25rem 0"
                          }}>
                            📊 Cài đặt đánh giá thực nghiệm
                          </h4>
                          <p style={{
                            fontSize: "0.8rem",
                            color: "#718096",
                            margin: 0
                          }}>
                            Dataset, metrics và benchmarks được sử dụng
                          </p>
                        </div>

                        <div style={{ marginBottom: "1rem" }}>
                          <label style={{
                            display: "block",
                            fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                            fontSize: "0.8rem",
                            fontWeight: "600",
                            color: "#2d3748",
                            marginBottom: "0.375rem"
                          }}>
                            Dataset
                          </label>
                          <textarea
                            rows={2}
                            value={form.datasetsText}
                            onChange={(e) => updateForm("datasetsText", e.target.value)}
                            placeholder="ImageNet, COCO, SQuAD..."
                            style={{
                              width: "100%",
                              padding: "0.625rem 0.875rem",
                              border: "2px solid #9ae6b4",
                              borderRadius: "6px",
                              fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                              fontSize: "0.85rem",
                              lineHeight: "1.5",
                              backgroundColor: "#fff",
                              resize: "vertical",
                              transition: "all 0.2s ease",
                              boxSizing: "border-box"
                            }}
                            onFocus={(e) => {
                              e.target.style.borderColor = "#276749";
                              e.target.style.boxShadow = "0 0 0 3px rgba(39, 103, 73, 0.1)";
                            }}
                            onBlur={(e) => {
                              e.target.style.borderColor = "#9ae6b4";
                              e.target.style.boxShadow = "none";
                            }}
                          />
                        </div>

                        <div style={{ marginBottom: "1rem" }}>
                          <label style={{
                            display: "block",
                            fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                            fontSize: "0.8rem",
                            fontWeight: "600",
                            color: "#2d3748",
                            marginBottom: "0.375rem"
                          }}>
                            Metrics
                          </label>
                          <textarea
                            rows={2}
                            value={form.metricsText}
                            onChange={(e) => updateForm("metricsText", e.target.value)}
                            placeholder="Accuracy, F1-score, BLEU..."
                            style={{
                              width: "100%",
                              padding: "0.625rem 0.875rem",
                              border: "2px solid #9ae6b4",
                              borderRadius: "6px",
                              fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                              fontSize: "0.85rem",
                              lineHeight: "1.5",
                              backgroundColor: "#fff",
                              resize: "vertical",
                              transition: "all 0.2s ease",
                              boxSizing: "border-box"
                            }}
                            onFocus={(e) => {
                              e.target.style.borderColor = "#276749";
                              e.target.style.boxShadow = "0 0 0 3px rgba(39, 103, 73, 0.1)";
                            }}
                            onBlur={(e) => {
                              e.target.style.borderColor = "#9ae6b4";
                              e.target.style.boxShadow = "none";
                            }}
                          />
                        </div>

                        <div>
                          <label style={{
                            display: "block",
                            fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                            fontSize: "0.8rem",
                            fontWeight: "600",
                            color: "#2d3748",
                            marginBottom: "0.375rem"
                          }}>
                            Benchmarks
                          </label>
                          <textarea
                            rows={2}
                            value={form.benchmarksText}
                            onChange={(e) => updateForm("benchmarksText", e.target.value)}
                            placeholder="GLUE, SuperGLUE, SQuAD 2.0..."
                            style={{
                              width: "100%",
                              padding: "0.625rem 0.875rem",
                              border: "2px solid #9ae6b4",
                              borderRadius: "6px",
                              fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                              fontSize: "0.85rem",
                              lineHeight: "1.5",
                              backgroundColor: "#fff",
                              resize: "vertical",
                              transition: "all 0.2s ease",
                              boxSizing: "border-box"
                            }}
                            onFocus={(e) => {
                              e.target.style.borderColor = "#276749";
                              e.target.style.boxShadow = "0 0 0 3px rgba(39, 103, 73, 0.1)";
                            }}
                            onBlur={(e) => {
                              e.target.style.borderColor = "#9ae6b4";
                              e.target.style.boxShadow = "none";
                            }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                </>
              )}

              {/* Action Buttons */}
              <div style={{
                display: "flex",
                gap: "1rem",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "1.5rem 2rem",
                marginTop: "2rem",
                backgroundColor: "#f7fafc",
                border: "2px solid #e2e8f0",
                borderRadius: "8px"
              }}>
                <div style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.5rem",
                  fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                  fontSize: "0.85rem",
                  color: "#718096"
                }}>
                  <span style={{ color: "#e53e3e" }}>*</span>
                  <span>Các trường bắt buộc phải điền đầy đủ thông tin</span>
                </div>

                <div style={{ display: "flex", gap: "1rem" }}>
                  <button
                    className="btn btn--secondary"
                    onClick={handleSaveDraft}
                    disabled={!canSubmit}
                    style={{
                      padding: "0.875rem 2rem",
                      fontSize: "0.9rem",
                      fontWeight: "600",
                      fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                      border: "2px solid #4a5568",
                      backgroundColor: "#fff",
                      color: "#4a5568",
                      borderRadius: "6px",
                      cursor: "pointer",
                      transition: "all 0.2s ease",
                      boxShadow: "0 1px 2px rgba(0,0,0,0.05)"
                    }}
                    onMouseEnter={(e) => {
                      if (!e.target.disabled) {
                        e.target.style.backgroundColor = "#f7fafc";
                        e.target.style.borderColor = "#2d3748";
                        e.target.style.color = "#2d3748";
                      }
                    }}
                    onMouseLeave={(e) => {
                      e.target.style.backgroundColor = "#fff";
                      e.target.style.borderColor = "#4a5568";
                      e.target.style.color = "#4a5568";
                    }}
                  >
                    💾 {saving ? "Đang lưu..." : "Lưu bản nháp"}
                  </button>
                  <button
                    className="btn btn--primary"
                    onClick={handlePublish}
                    disabled={!canSubmit}
                    style={{
                      padding: "0.875rem 2rem",
                      fontSize: "0.9rem",
                      fontWeight: "600",
                      fontFamily: "Segoe UI, Roboto, system-ui, sans-serif",
                      border: "2px solid #2c5282",
                      backgroundColor: "#2c5282",
                      color: "#fff",
                      borderRadius: "6px",
                      cursor: "pointer",
                      transition: "all 0.2s ease",
                      boxShadow: "0 2px 4px rgba(44, 82, 130, 0.2)"
                    }}
                    onMouseEnter={(e) => {
                      if (!e.target.disabled) {
                        e.target.style.backgroundColor = "#1a365d";
                        e.target.style.borderColor = "#1a365d";
                        e.target.style.transform = "translateY(-1px)";
                        e.target.style.boxShadow = "0 4px 6px rgba(44, 82, 130, 0.3)";
                      }
                    }}
                    onMouseLeave={(e) => {
                      e.target.style.backgroundColor = "#2c5282";
                      e.target.style.borderColor = "#2c5282";
                      e.target.style.transform = "translateY(0)";
                      e.target.style.boxShadow = "0 2px 4px rgba(44, 82, 130, 0.2)";
                    }}
                  >
                    📤 {publishing ? "Đang xuất bản..." : "Xuất bản bài báo"}
                  </button>
                </div>
              </div>
            </section>
          )}
        </div>
      </main>
    </div>
  );
}
