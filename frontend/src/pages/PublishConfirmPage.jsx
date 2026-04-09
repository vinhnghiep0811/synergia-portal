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
        title="Confirm Publish"
        subtitle="Kiểm duyệt metadata từ Semantic Scholar + Gemini trước khi publish."
        extraAction={
          <button
            className="btn btn--secondary"
            style={{ marginRight: "1rem" }}
            onClick={() => navigate(`/papers/${paperId}`)}
          >
            ← Quay lại paper
          </button>
        }
      />

      <main className="app-main app-main--papers">
        <div className="app-main__full">
          {loading ? (
            <div className="card" style={{ padding: "2rem", textAlign: "center" }}>
              Đang tải metadata để confirm publish...
            </div>
          ) : loadError ? (
            <div className="card" style={{ padding: "2rem", color: "#dc2626" }}>
              {loadError}
            </div>
          ) : (
            <section className="card publish-confirm-card">
              <header className="card__header">
                <div>
                  <h2 className="card__title">Metadata kiểm duyệt</h2>
                  <p className="card__subtitle">
                    Bước 1: kiểm tra dữ liệu auto-fill. Bước 2: chỉnh sửa nếu cần. Bước 3: publish snapshot.
                  </p>
                </div>
              </header>

              {preview && (
                <div className="publish-meta-summary">
                  <div className="publish-meta-summary__item">
                    <span className="publish-meta-summary__label">Paper ID</span>
                    <span className="publish-meta-summary__value">{preview.paper_id}</span>
                  </div>
                  <div className="publish-meta-summary__item">
                    <span className="publish-meta-summary__label">Publication status</span>
                    <span className="publish-meta-summary__value">{formatStatus(preview.publication_status)}</span>
                  </div>
                  <div className="publish-meta-summary__item">
                    <span className="publish-meta-summary__label">Semantic status</span>
                    <span className="publish-meta-summary__value">{formatStatus(preview.semantic_status)}</span>
                  </div>
                  <div className="publish-meta-summary__item">
                    <span className="publish-meta-summary__label">Extraction status</span>
                    <span className="publish-meta-summary__value">{formatStatus(preview.extraction_status)}</span>
                  </div>
                  <div className="publish-meta-summary__item">
                    <span className="publish-meta-summary__label">Draft mode</span>
                    <span className="publish-meta-summary__value">
                      {preview.is_editing_draft ? "Using saved draft" : "Using auto-generated metadata"}
                    </span>
                  </div>
                </div>
              )}

              {notice && (
                <div
                  className={`publish-callout publish-callout--${
                    notice.type === "error" ? "error" : "success"
                  }`}
                >
                  {notice.message}
                </div>
              )}

              {form && (
                <div className="publish-form-grid">
                  <div className="publish-form-section">
                    <h3 className="publish-form-section__title">Semantic metadata</h3>

                    <label className="form-label">
                      Title
                      <input
                        type="text"
                        value={form.title}
                        onChange={(e) => updateForm("title", e.target.value)}
                      />
                    </label>

                    <label className="form-label">
                      Abstract
                      <textarea
                        className="publish-textarea"
                        rows={5}
                        value={form.abstract}
                        onChange={(e) => updateForm("abstract", e.target.value)}
                      />
                    </label>

                    <div className="publish-inline-grid">
                      <label className="form-label">
                        Venue
                        <input
                          type="text"
                          value={form.venue}
                          onChange={(e) => updateForm("venue", e.target.value)}
                        />
                      </label>

                      <label className="form-label">
                        Year
                        <input
                          type="number"
                          value={form.year}
                          onChange={(e) => updateForm("year", e.target.value)}
                        />
                      </label>
                    </div>

                    <label className="form-label">
                      Authors (moi dong 1 tac gia)
                      <textarea
                        className="publish-textarea"
                        rows={5}
                        value={form.authorsText}
                        onChange={(e) => updateForm("authorsText", e.target.value)}
                      />
                    </label>
                  </div>

                  <div className="publish-form-section">
                    <h3 className="publish-form-section__title">LLM metadata</h3>

                    <label className="form-label">
                      Problem statement
                      <textarea
                        className="publish-textarea"
                        rows={3}
                        value={form.problemStatement}
                        onChange={(e) => updateForm("problemStatement", e.target.value)}
                      />
                    </label>

                    <label className="form-label">
                      Main method
                      <textarea
                        className="publish-textarea"
                        rows={3}
                        value={form.mainMethod}
                        onChange={(e) => updateForm("mainMethod", e.target.value)}
                      />
                    </label>

                    <label className="form-label">
                      Contributions (moi dong 1 y)
                      <textarea
                        className="publish-textarea"
                        rows={4}
                        value={form.contributionsText}
                        onChange={(e) => updateForm("contributionsText", e.target.value)}
                      />
                    </label>

                    <label className="form-label">
                      Limitations (moi dong 1 y)
                      <textarea
                        className="publish-textarea"
                        rows={4}
                        value={form.limitationsText}
                        onChange={(e) => updateForm("limitationsText", e.target.value)}
                      />
                    </label>

                    <label className="form-label">
                      Datasets (phay hoac xuong dong)
                      <textarea
                        className="publish-textarea"
                        rows={2}
                        value={form.datasetsText}
                        onChange={(e) => updateForm("datasetsText", e.target.value)}
                      />
                    </label>

                    <label className="form-label">
                      Metrics (phay hoac xuong dong)
                      <textarea
                        className="publish-textarea"
                        rows={2}
                        value={form.metricsText}
                        onChange={(e) => updateForm("metricsText", e.target.value)}
                      />
                    </label>

                    <label className="form-label">
                      Benchmarks (phay hoac xuong dong)
                      <textarea
                        className="publish-textarea"
                        rows={2}
                        value={form.benchmarksText}
                        onChange={(e) => updateForm("benchmarksText", e.target.value)}
                      />
                    </label>
                  </div>
                </div>
              )}

              <div className="publish-actions">
                <button className="btn btn--secondary" onClick={handleSaveDraft} disabled={!canSubmit}>
                  {saving ? "Đang lưu..." : "Lưu bản nháp"}
                </button>
                <button className="btn btn--primary" onClick={handlePublish} disabled={!canSubmit}>
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
