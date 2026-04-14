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
                <div className="detail-grid">
                  <div className="detail-section" style={{ marginBottom: "2rem" }}>
                    <h3 className="detail-section__title">Metadata cơ bản</h3>

                    <label className="form-label">
                      Tiêu đề
                      <input
                        type="text"
                        value={form.title}
                        onChange={(e) => updateForm("title", e.target.value)}
                        placeholder="Nhập tiêu đề bài báo"
                      />
                    </label>

                    <label className="form-label">
                      Tóm tắt
                      <textarea
                        rows={5}
                        value={form.abstract}
                        onChange={(e) => updateForm("abstract", e.target.value)}
                        placeholder="Nhập tóm tắt nội dung chính"
                        style={{ 
                          resize: "vertical",
                          fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                          fontSize: "0.9rem",
                          lineHeight: "1.5"
                        }}
                      />
                    </label>

                    <div className="detail-grid" style={{ gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                      <label className="form-label">
                        Hội thảo/Tạp chí
                        <input
                          type="text"
                          value={form.venue}
                          onChange={(e) => updateForm("venue", e.target.value)}
                          placeholder="VD: NeurIPS, ICML, ArXiv"
                        />
                      </label>

                      <label className="form-label">
                        Năm xuất bản
                        <input
                          type="number"
                          value={form.year}
                          onChange={(e) => updateForm("year", e.target.value)}
                          placeholder="VD: 2024"
                          min="1900"
                          max="2030"
                        />
                      </label>
                    </div>

                    <label className="form-label">
                      Tác giả
                      <textarea
                        rows={5}
                        value={form.authorsText}
                        onChange={(e) => updateForm("authorsText", e.target.value)}
                        placeholder="Nguyễn Văn A&#10;Trần Thị B&#10;Lê Văn C"
                        style={{ 
                          resize: "vertical",
                          fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                          fontSize: "0.9rem",
                          lineHeight: "1.5"
                        }}
                      />
                    </label>
                  </div>

                  <div className="detail-section" style={{ marginBottom: "2rem" }}>
                    <h3 className="detail-section__title">Metadata từ AI</h3>

                    <label className="form-label">
                      <span style={{ fontWeight: "600", color: "#374151" }}>Vấn đề nghiên cứu</span>
                      <textarea
                        rows={3}
                        value={form.problemStatement}
                        onChange={(e) => updateForm("problemStatement", e.target.value)}
                        placeholder="Mô tả vấn đề chính mà bài báo giải quyết"
                        style={{ 
                          resize: "vertical",
                          fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                          fontSize: "0.9rem",
                          lineHeight: "1.5"
                        }}
                      />
                    </label>

                    <label className="form-label">
                      <span style={{ fontWeight: "600", color: "#374151" }}>Phương pháp chính</span>
                      <textarea
                        rows={3}
                        value={form.mainMethod}
                        onChange={(e) => updateForm("mainMethod", e.target.value)}
                        placeholder="Mô tả phương pháp/kỹ thuật đề xuất"
                        style={{ 
                          resize: "vertical",
                          fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                          fontSize: "0.9rem",
                          lineHeight: "1.5"
                        }}
                      />
                    </label>

                    <label className="form-label">
                      <span style={{ fontWeight: "600", color: "#374151" }}>Đóng góp</span>
                      <textarea
                        rows={4}
                        value={form.contributionsText}
                        onChange={(e) => updateForm("contributionsText", e.target.value)}
                        placeholder="Đề xuất phương pháp mới&#10;Cải thiện độ chính xác&#10;Giảm thời gian xử lý"
                        style={{ 
                          resize: "vertical",
                          fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                          fontSize: "0.9rem",
                          lineHeight: "1.5"
                        }}
                      />
                    </label>

                    <label className="form-label">
                      <span style={{ fontWeight: "600", color: "#374151" }}>Hạn chế</span>
                      <textarea
                        rows={4}
                        value={form.limitationsText}
                        onChange={(e) => updateForm("limitationsText", e.target.value)}
                        placeholder="Chỉ hoạt động trên dữ liệu cụ thể&#10;Cần tính toán cao&#10;Chưa thử nghiệm trên quy mô lớn"
                        style={{ 
                          resize: "vertical",
                          fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                          fontSize: "0.9rem",
                          lineHeight: "1.5"
                        }}
                      />
                    </label>

                    <div className="detail-section" style={{ marginTop: "2rem", marginBottom: "1rem" }}>
                      <h4 className="detail-section__title" style={{ fontSize: "1.1rem", marginBottom: "1rem", color: "#1f2937" }}>Cài đặt đánh giá</h4>
                      
                      <label className="form-label">
                        <span style={{ fontWeight: "600", color: "#374151" }}>Dataset</span>
                        <textarea
                          rows={2}
                          value={form.datasetsText}
                          onChange={(e) => updateForm("datasetsText", e.target.value)}
                          placeholder="ImageNet, COCO, SQuAD"
                          style={{ 
                            resize: "vertical",
                            fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                            fontSize: "0.9rem",
                            lineHeight: "1.5"
                          }}
                        />
                      </label>

                      <label className="form-label">
                        <span style={{ fontWeight: "600", color: "#374151" }}>Metrics</span>
                        <textarea
                          rows={2}
                          value={form.metricsText}
                          onChange={(e) => updateForm("metricsText", e.target.value)}
                          placeholder="Accuracy, F1-score, BLEU"
                          style={{ 
                            resize: "vertical",
                            fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                            fontSize: "0.9rem",
                            lineHeight: "1.5"
                          }}
                        />
                      </label>

                      <label className="form-label">
                        <span style={{ fontWeight: "600", color: "#374151" }}>Benchmarks</span>
                        <textarea
                          rows={2}
                          value={form.benchmarksText}
                          onChange={(e) => updateForm("benchmarksText", e.target.value)}
                          placeholder="GLUE, SuperGLUE, SQuAD 2.0"
                          style={{ 
                            resize: "vertical",
                            fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                            fontSize: "0.9rem",
                            lineHeight: "1.5"
                          }}
                        />
                      </label>
                    </div>
                  </div>
                </div>
              )}

              <div style={{ 
                display: "flex", 
                gap: "1rem", 
                justifyContent: "flex-end",
                padding: "1.5rem 0 0 0",
                borderTop: "1px solid #e5e7eb",
                marginTop: "2rem"
              }}>
                <button 
                  className="btn btn--secondary" 
                  onClick={handleSaveDraft} 
                  disabled={!canSubmit}
                  style={{ 
                    padding: "0.75rem 1.5rem",
                    fontSize: "0.9rem",
                    fontWeight: "500"
                  }}
                >
                  {saving ? "Đang lưu..." : "Lưu bản nháp"}
                </button>
                <button 
                  className="btn btn--primary" 
                  onClick={handlePublish} 
                  disabled={!canSubmit}
                  style={{ 
                    padding: "0.75rem 1.5rem",
                    fontSize: "0.9rem",
                    fontWeight: "500"
                  }}
                >
                  {publishing ? "Đang publish..." : "Publish snapshot"}
                </button>
              </div>
            </section>
          )}
        </div>
      </main>
    </div>
  );
}
