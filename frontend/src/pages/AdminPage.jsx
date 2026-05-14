import { useCallback, useEffect, useMemo, useState } from "react";
import { AppHeader } from "../components/AppHeader.jsx";
import {
  getAdminActivities,
  getAdminCanonicalDocuments,
  getAdminConfiguration,
  getAdminEvaluationReport,
  getAdminOverview,
  getAdminPapers,
  getAdminProcessingLogs,
  updateAdminConfiguration,
  validateAdminConfiguration,
} from "../services/adminApi.js";

const TAB_CONFIG = [
  { key: "overview", label: "Tổng quan" },
  { key: "papers", label: "Papers" },
  { key: "canonical", label: "Canonical" },
  { key: "activities", label: "Activity log" },
  { key: "processing", label: "Processing log" },
  { key: "config", label: "Cấu hình" },
  { key: "evaluation", label: "Dữ liệu đánh giá" },
];

function formatDate(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString("vi-VN");
}

function getStatusColor(status) {
  const key = String(status || "").toLowerCase();
  if (key.includes("success") || key === "completed" || key === "published") return "#16a34a";
  if (key.includes("warn") || key === "warning" || key === "pending") return "#d97706";
  if (key.includes("error") || key === "failed") return "#dc2626";
  return "#2563eb";
}

function Pagination({ page, totalPages, onChange }) {
  if (totalPages <= 1) return null;

  const pages = [];
  const start = Math.max(1, page - 2);
  const end = Math.min(totalPages, start + 4);
  for (let i = start; i <= end; i += 1) pages.push(i);

  return (
    <div style={{ display: "flex", gap: "0.5rem", justifyContent: "center", marginTop: "1rem" }}>
      <button type="button" onClick={() => onChange(Math.max(1, page - 1))} disabled={page === 1}>
        ‹
      </button>
      {pages.map((p) => (
        <button
          key={p}
          type="button"
          onClick={() => onChange(p)}
          style={{
            minWidth: "2rem",
            background: p === page ? "#2563eb" : "white",
            color: p === page ? "white" : "inherit",
            border: "1px solid #d1d5db",
            borderRadius: "0.25rem",
          }}
        >
          {p}
        </button>
      ))}
      <button type="button" onClick={() => onChange(Math.min(totalPages, page + 1))} disabled={page === totalPages}>
        ›
      </button>
    </div>
  );
}

export function AdminPage() {
  const [activeTab, setActiveTab] = useState("overview");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [overview, setOverview] = useState(null);
  const [papers, setPapers] = useState([]);
  const [papersTotal, setPapersTotal] = useState(0);
  const [papersPage, setPapersPage] = useState(1);
  const papersPageSize = 10;

  const [canonicalDocs, setCanonicalDocs] = useState([]);
  const [canonicalTotal, setCanonicalTotal] = useState(0);
  const [canonicalPage, setCanonicalPage] = useState(1);
  const canonicalPageSize = 10;

  const [activities, setActivities] = useState([]);
  const [activitiesTotal, setActivitiesTotal] = useState(0);
  const [activitiesPage, setActivitiesPage] = useState(1);
  const activitiesPageSize = 20;

  const [processingLogs, setProcessingLogs] = useState([]);
  const [processingTotal, setProcessingTotal] = useState(0);
  const [processingPage, setProcessingPage] = useState(1);
  const [processingErrorsOnly, setProcessingErrorsOnly] = useState(false);
  const [processingFamily, setProcessingFamily] = useState("all");
  const processingPageSize = 20;

  const [config, setConfig] = useState(null);
  const [configForm, setConfigForm] = useState({
    llm_provider: "gemini",
    llm_model: "",
    embedding_model: "",
    metadata_match_threshold: 0.7,
    pipeline_retry_limit: 3,
    pipeline_timeout_seconds: 300,
    telegram_enabled: false,
    telegram_chat_id: "",
    semantic_scholar_api_key: "",
    telegram_bot_token: "",
  });
  const [isSavingConfig, setIsSavingConfig] = useState(false);
  const [validationResults, setValidationResults] = useState({});
  const [validatingService, setValidatingService] = useState(null);
  const [configSuccess, setConfigSuccess] = useState("");

  const [evaluation, setEvaluation] = useState(null);
  const [windowDays, setWindowDays] = useState(7);

  const runWithState = useCallback(async (task) => {
    setLoading(true);
    setError("");
    try {
      await task();
    } catch (err) {
      setError(err.message || "Không thể tải dữ liệu admin");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadOverview = useCallback(() => {
    return runWithState(async () => {
      const data = await getAdminOverview();
      setOverview(data);
    });
  }, [runWithState]);

  const loadPapers = useCallback(() => {
    return runWithState(async () => {
      const data = await getAdminPapers(papersPage, papersPageSize);
      setPapers(data.items || []);
      setPapersTotal(data.pagination?.total || 0);
    });
  }, [papersPage, runWithState]);

  const loadCanonical = useCallback(() => {
    return runWithState(async () => {
      const data = await getAdminCanonicalDocuments(canonicalPage, canonicalPageSize);
      setCanonicalDocs(data.items || []);
      setCanonicalTotal(data.pagination?.total || 0);
    });
  }, [canonicalPage, runWithState]);

  const loadActivities = useCallback(() => {
    return runWithState(async () => {
      const data = await getAdminActivities(activitiesPage, activitiesPageSize);
      setActivities(data.items || []);
      setActivitiesTotal(data.total || 0);
    });
  }, [activitiesPage, runWithState]);

  const loadProcessingLogs = useCallback(() => {
    return runWithState(async () => {
      const data = await getAdminProcessingLogs(processingPage, processingPageSize, {
        event_family: processingFamily,
        errors_only: processingErrorsOnly,
        days: 7,
      });
      setProcessingLogs(data.items || []);
      setProcessingTotal(data.total || 0);
    });
  }, [processingPage, processingFamily, processingErrorsOnly, runWithState]);

  const loadConfig = useCallback(() => {
    return runWithState(async () => {
      const data = await getAdminConfiguration();
      setConfig(data);
      setConfigForm({
        llm_provider: data.llm_provider || "gemini",
        llm_model: data.llm_model || "",
        embedding_model: data.embedding_model || "",
        metadata_match_threshold: data.metadata_match_threshold ?? 0.7,
        pipeline_retry_limit: data.pipeline_retry_limit ?? 3,
        pipeline_timeout_seconds: data.pipeline_timeout_seconds ?? 300,
        telegram_enabled: Boolean(data.telegram_enabled),
        telegram_chat_id: data.telegram_chat_id || "",
        semantic_scholar_api_key: "",
        telegram_bot_token: "",
      });
      setValidationResults({});
      setConfigSuccess("");
    });
  }, [runWithState]);

  const loadEvaluation = useCallback(() => {
    return runWithState(async () => {
      const data = await getAdminEvaluationReport(windowDays, 20);
      setEvaluation(data);
    });
  }, [windowDays, runWithState]);

  useEffect(() => {
    if (activeTab === "overview") void loadOverview();
    if (activeTab === "papers") void loadPapers();
    if (activeTab === "canonical") void loadCanonical();
    if (activeTab === "activities") void loadActivities();
    if (activeTab === "processing") void loadProcessingLogs();
    if (activeTab === "config") void loadConfig();
    if (activeTab === "evaluation") void loadEvaluation();
  }, [
    activeTab,
    loadOverview,
    loadPapers,
    loadCanonical,
    loadActivities,
    loadProcessingLogs,
    loadConfig,
    loadEvaluation,
  ]);

  const paperTotalPages = useMemo(
    () => Math.max(1, Math.ceil(papersTotal / papersPageSize)),
    [papersTotal]
  );
  const canonicalTotalPages = useMemo(
    () => Math.max(1, Math.ceil(canonicalTotal / canonicalPageSize)),
    [canonicalTotal]
  );
  const activitiesTotalPages = useMemo(
    () => Math.max(1, Math.ceil(activitiesTotal / activitiesPageSize)),
    [activitiesTotal]
  );
  const processingTotalPages = useMemo(
    () => Math.max(1, Math.ceil(processingTotal / processingPageSize)),
    [processingTotal]
  );

  const updateConfigField = useCallback((field, value) => {
    setConfigForm((prev) => ({ ...prev, [field]: value }));
    setValidationResults((prev) => {
      const next = { ...prev };
      if (field.startsWith("llm_")) delete next.llm;
      if (field.startsWith("semantic_scholar")) delete next.semantic_scholar;
      if (field.startsWith("telegram_")) delete next.telegram;
      if (field.startsWith("embedding_")) delete next.embedding;
      return next;
    });
  }, []);

  const testService = useCallback(async (service) => {
    setValidatingService(service);
    setError("");
    try {
      const payload = {
        service,
        llm_provider: configForm.llm_provider,
        llm_model: configForm.llm_model || undefined,
        embedding_model: configForm.embedding_model || undefined,
        semantic_scholar_api_key: configForm.semantic_scholar_api_key || undefined,
        telegram_bot_token: configForm.telegram_bot_token || undefined,
        telegram_chat_id: configForm.telegram_chat_id || undefined,
        pipeline_timeout_seconds: Number(configForm.pipeline_timeout_seconds) || undefined,
      };
      const data = await validateAdminConfiguration(payload);
      const newResults = { ...validationResults };
      for (const r of data.results) {
        newResults[r.service] = r;
      }
      setValidationResults(newResults);
    } catch (err) {
      setError(err.message || "Kiểm tra kết nối thất bại");
    } finally {
      setValidatingService(null);
    }
  }, [configForm, validationResults]);

  const switchToDefaults = useCallback(async () => {
    setIsSavingConfig(true);
    setError("");
    setConfigSuccess("");
    try {
      const updated = await updateAdminConfiguration({ use_default_settings: true });
      setConfig(updated);
      setConfigForm({
        llm_provider: updated.llm_provider || "gemini",
        llm_model: updated.llm_model || "",
        embedding_model: updated.embedding_model || "",
        metadata_match_threshold: updated.metadata_match_threshold ?? 0.7,
        pipeline_retry_limit: updated.pipeline_retry_limit ?? 3,
        pipeline_timeout_seconds: updated.pipeline_timeout_seconds ?? 300,
        telegram_enabled: Boolean(updated.telegram_enabled),
        telegram_chat_id: updated.telegram_chat_id || "",
        semantic_scholar_api_key: "",
        telegram_bot_token: "",
      });
      setValidationResults({});
      setConfigSuccess("Đã chuyển về cấu hình mặc định (.env) thành công.");
    } catch (err) {
      setError(err.message || "Chuyển về cấu hình mặc định thất bại");
    } finally {
      setIsSavingConfig(false);
    }
  }, []);

  const saveConfig = useCallback(async () => {
    setIsSavingConfig(true);
    setError("");
    setConfigSuccess("");
    try {
      const payload = {
        llm_provider: configForm.llm_provider,
        llm_model: configForm.llm_model,
        embedding_model: configForm.embedding_model,
        metadata_match_threshold: Number(configForm.metadata_match_threshold),
        pipeline_retry_limit: Number(configForm.pipeline_retry_limit),
        pipeline_timeout_seconds: Number(configForm.pipeline_timeout_seconds),
        telegram_enabled: Boolean(configForm.telegram_enabled),
        telegram_chat_id: configForm.telegram_chat_id || null,
      };
      if (configForm.semantic_scholar_api_key.trim()) {
        payload.semantic_scholar_api_key = configForm.semantic_scholar_api_key.trim();
      }
      if (configForm.telegram_bot_token.trim()) {
        payload.telegram_bot_token = configForm.telegram_bot_token.trim();
      }

      const updated = await updateAdminConfiguration(payload);
      setConfig(updated);
      setConfigForm((prev) => ({
        ...prev,
        semantic_scholar_api_key: "",
        telegram_bot_token: "",
      }));
      setConfigSuccess("Cấu hình đã được lưu và xác thực thành công.");
    } catch (err) {
      setError(err.message || "Lưu cấu hình thất bại");
    } finally {
      setIsSavingConfig(false);
    }
  }, [configForm]);


  const exportEvaluationData = useCallback(() => {
    if (!evaluation) return;
    const blob = new Blob([JSON.stringify(evaluation, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `admin-evaluation-${new Date().toISOString()}.json`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }, [evaluation]);

  return (
    <div className="app-shell">
      <AppHeader title="Quản trị hệ thống" subtitle="UC-04: Vận hành và cấu hình hệ thống" />

      <main className="app-main app-main--papers">
        <div className="app-main__full">
          <div className="tabs">
            {TAB_CONFIG.map((tab) => (
              <button
                key={tab.key}
                type="button"
                className={`tab ${activeTab === tab.key ? "tab--active" : ""}`}
                onClick={() => setActiveTab(tab.key)}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {error && (
            <div className="card" style={{ marginBottom: "1rem", padding: "1rem", color: "#b91c1c" }}>
              {error}
            </div>
          )}

          {loading && (
            <div className="card" style={{ marginBottom: "1rem", padding: "1rem" }}>
              Đang tải dữ liệu...
            </div>
          )}

          {activeTab === "overview" && overview && (
            <div style={{ display: "grid", gap: "1rem", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))" }}>
              <div className="card" style={{ padding: "1rem" }}>
                <h3 style={{ marginTop: 0 }}>Tài liệu</h3>
                <div><strong>Tổng số:</strong> {overview.total_papers}</div>
                <div><strong>Trùng lặp:</strong> {overview.duplicate_count}</div>
              </div>

              <div className="card" style={{ padding: "1rem" }}>
                <h3 style={{ marginTop: 0 }}>Pipeline</h3>
                <div><strong>Jobs đang xử lý:</strong> {overview.operations?.jobs_processing ?? 0}</div>
                <div><strong>Jobs lỗi:</strong> {overview.operations?.jobs_failed ?? 0}</div>
                <div><strong>Cache hit:</strong> {overview.operations?.cache_hits ?? 0}</div>
                <div><strong>Cache miss:</strong> {overview.operations?.cache_misses ?? 0}</div>
              </div>

              <div className="card" style={{ padding: "1rem" }}>
                <h3 style={{ marginTop: 0 }}>Logs</h3>
                <div><strong>Activity:</strong> {overview.operations?.total_activity_logs ?? 0}</div>
                <div><strong>Processing:</strong> {overview.operations?.total_processing_logs ?? 0}</div>
              </div>

              <div className="card" style={{ padding: "1rem" }}>
                <h3 style={{ marginTop: 0 }}>Admin hiện tại</h3>
                <div><strong>Email:</strong> {overview.current_admin?.email || "-"}</div>
                <div><strong>Role:</strong> {overview.current_admin?.role || "-"}</div>
              </div>
            </div>
          )}

          {activeTab === "papers" && (
            <div className="card" style={{ padding: "1rem" }}>
              <h3 style={{ marginTop: 0 }}>
                Papers ({papersTotal}) - Trang {papersPage}/{paperTotalPages}
              </h3>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr>
                      <th style={{ textAlign: "left" }}>Filename</th>
                      <th style={{ textAlign: "left" }}>Status</th>
                      <th style={{ textAlign: "left" }}>Stage</th>
                      <th style={{ textAlign: "left" }}>Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {papers.map((paper) => (
                      <tr key={paper.id}>
                        <td>{paper.original_filename}</td>
                        <td>
                          <span style={{ color: getStatusColor(paper.processing_status) }}>
                            {paper.processing_status}
                          </span>
                        </td>
                        <td>{paper.processing_stage || "-"}</td>
                        <td>{formatDate(paper.created_at)}</td>
                      </tr>
                    ))}
                    {papers.length === 0 && (
                      <tr>
                        <td colSpan={4} style={{ textAlign: "center", padding: "1rem" }}>Không có dữ liệu</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
              <Pagination page={papersPage} totalPages={paperTotalPages} onChange={setPapersPage} />
            </div>
          )}

          {activeTab === "canonical" && (
            <div className="card" style={{ padding: "1rem" }}>
              <h3 style={{ marginTop: 0 }}>
                Canonical Documents ({canonicalTotal}) - Trang {canonicalPage}/{canonicalTotalPages}
              </h3>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr>
                      <th style={{ textAlign: "left" }}>Key</th>
                      <th style={{ textAlign: "left" }}>Title</th>
                      <th style={{ textAlign: "left" }}>Status</th>
                      <th style={{ textAlign: "left" }}>Papers</th>
                    </tr>
                  </thead>
                  <tbody>
                    {canonicalDocs.map((doc) => (
                      <tr key={doc.id}>
                        <td style={{ fontFamily: "monospace" }}>{doc.canonical_key}</td>
                        <td>{doc.title || doc.title_candidate || "-"}</td>
                        <td>{doc.enrichment_status || "-"}</td>
                        <td>{doc.paper_count || 0}</td>
                      </tr>
                    ))}
                    {canonicalDocs.length === 0 && (
                      <tr>
                        <td colSpan={4} style={{ textAlign: "center", padding: "1rem" }}>Không có dữ liệu</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
              <Pagination page={canonicalPage} totalPages={canonicalTotalPages} onChange={setCanonicalPage} />
            </div>
          )}

          {activeTab === "activities" && (
            <div className="card" style={{ padding: "1rem" }}>
              <h3 style={{ marginTop: 0 }}>
                Activity log ({activitiesTotal}) - Trang {activitiesPage}/{activitiesTotalPages}
              </h3>
              {activities.map((item) => (
                <div key={item.id} style={{ borderBottom: "1px solid #e5e7eb", padding: "0.75rem 0" }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <strong>{item.event_label}</strong>
                    <span>{formatDate(item.created_at)}</span>
                  </div>
                  <div>{item.message}</div>
                  <div style={{ color: "#6b7280", fontSize: "0.875rem" }}>
                    Actor: {item.actor_display} · Status: {item.status}
                  </div>
                </div>
              ))}
              {activities.length === 0 && <div>Không có dữ liệu.</div>}
              <Pagination page={activitiesPage} totalPages={activitiesTotalPages} onChange={setActivitiesPage} />
            </div>
          )}

          {activeTab === "processing" && (
            <div className="card" style={{ padding: "1rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: "0.75rem" }}>
                <h3 style={{ margin: 0 }}>
                  Processing log ({processingTotal}) - Trang {processingPage}/{processingTotalPages}
                </h3>
                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                  <select value={processingFamily} onChange={(e) => setProcessingFamily(e.target.value)}>
                    <option value="all">Tất cả</option>
                    <option value="parse">Parse</option>
                    <option value="semantic_scholar">Semantic Scholar</option>
                    <option value="llm_extraction">LLM Extraction</option>
                    <option value="duplicate">Duplicate</option>
                    <option value="canonical">Canonical</option>
                  </select>
                  <label style={{ display: "flex", gap: "0.25rem", alignItems: "center" }}>
                    <input
                      type="checkbox"
                      checked={processingErrorsOnly}
                      onChange={(e) => setProcessingErrorsOnly(e.target.checked)}
                    />
                    Chỉ lỗi
                  </label>
                </div>
              </div>
              {processingLogs.map((item) => (
                <div key={item.id} style={{ borderBottom: "1px solid #e5e7eb", padding: "0.75rem 0" }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <strong>{item.event_label}</strong>
                    <span>{formatDate(item.created_at)}</span>
                  </div>
                  <div>{item.message}</div>
                  <div style={{ color: "#6b7280", fontSize: "0.875rem" }}>
                    Event: {item.event_type} · Status:{" "}
                    <span style={{ color: getStatusColor(item.status) }}>{item.status}</span>
                  </div>
                </div>
              ))}
              {processingLogs.length === 0 && <div>Không có dữ liệu.</div>}
              <Pagination page={processingPage} totalPages={processingTotalPages} onChange={setProcessingPage} />
            </div>
          )}

          {activeTab === "config" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              {/* Header with mode indicator and default settings button */}
              <div className="card" style={{ padding: "1rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.75rem" }}>
                  <div>
                    <h3 style={{ marginTop: 0, marginBottom: "0.25rem" }}>Cấu hình hệ thống</h3>
                    <p style={{ color: "#6b7280", margin: 0, fontSize: "0.875rem" }}>
                      Cập nhật tham số vận hành. Hệ thống sẽ kiểm tra kết nối trước khi lưu.
                    </p>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                    <span style={{
                      padding: "0.25rem 0.75rem", borderRadius: "999px", fontSize: "0.8rem", fontWeight: 500,
                      background: config?.source === "env_default" ? "#dcfce7" : "#dbeafe",
                      color: config?.source === "env_default" ? "#166534" : "#1e40af",
                    }}>
                      {config?.source === "env_default" ? "⚙️ Default (.env)" : "🔧 Custom config"}
                    </span>
                    <button
                      type="button"
                      className="btn btn--secondary"
                      onClick={switchToDefaults}
                      disabled={isSavingConfig || config?.source === "env_default"}
                      style={{ fontSize: "0.85rem", padding: "0.5rem 1rem", minHeight: "auto" }}
                    >
                      Dùng Default Settings
                    </button>
                  </div>
                </div>

                {configSuccess && (
                  <div style={{ marginTop: "0.75rem", padding: "0.6rem 1rem", borderRadius: "8px", background: "#dcfce7", color: "#166534", fontSize: "0.875rem" }}>
                    ✅ {configSuccess}
                  </div>
                )}
                {config?.updated_at && (
                  <div style={{ marginTop: "0.5rem", color: "#6b7280", fontSize: "0.8rem" }}>
                    Cập nhật gần nhất: {formatDate(config.updated_at)} bởi {config.updated_by || "-"}
                  </div>
                )}
              </div>

              {/* LLM Configuration Section */}
              <div className="card" style={{ padding: "1rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
                  <h4 style={{ margin: 0 }}>🤖 LLM Provider</h4>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    {validationResults.llm && (
                      <span style={{
                        padding: "0.2rem 0.6rem", borderRadius: "999px", fontSize: "0.75rem", fontWeight: 500,
                        background: validationResults.llm.ok ? "#dcfce7" : "#fee2e2",
                        color: validationResults.llm.ok ? "#166534" : "#b91c1c",
                      }}>
                        {validationResults.llm.ok ? "✓ Kết nối OK" : "✕ Lỗi"}
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => testService("llm")}
                      disabled={validatingService !== null}
                      style={{ fontSize: "0.8rem", padding: "0.35rem 0.75rem", cursor: "pointer", borderRadius: "8px", border: "1px solid #d1d5db", background: validatingService === "llm" ? "#f3f4f6" : "#fff" }}
                    >
                      {validatingService === "llm" ? "Đang kiểm tra..." : "Test kết nối"}
                    </button>
                  </div>
                </div>
                {validationResults.llm && !validationResults.llm.ok && (
                  <div style={{ padding: "0.5rem 0.75rem", borderRadius: "8px", background: "#fef2f2", color: "#b91c1c", fontSize: "0.8rem", marginBottom: "0.75rem" }}>
                    {validationResults.llm.message}
                  </div>
                )}
                {validationResults.llm && validationResults.llm.ok && (
                  <div style={{ padding: "0.5rem 0.75rem", borderRadius: "8px", background: "#f0fdf4", color: "#166534", fontSize: "0.8rem", marginBottom: "0.75rem" }}>
                    {validationResults.llm.message}
                  </div>
                )}
                <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "1fr 1fr" }}>
                  <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", fontSize: "0.85rem", fontWeight: 500, color: "#374151" }}>
                    Provider
                    <select value={configForm.llm_provider} onChange={(e) => updateConfigField("llm_provider", e.target.value)} style={{ width: "100%", padding: "0.5rem", borderRadius: "8px", border: "1px solid #d1d5db" }}>
                      <option value="gemini">Gemini</option>
                      <option value="ollama">Ollama</option>
                    </select>
                  </label>
                  <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", fontSize: "0.85rem", fontWeight: 500, color: "#374151" }}>
                    Model name
                    <input type="text" value={configForm.llm_model} onChange={(e) => updateConfigField("llm_model", e.target.value)} placeholder="e.g. gemini-2.5-pro" style={{ width: "100%", padding: "0.5rem", borderRadius: "8px", border: "1px solid #d1d5db", boxSizing: "border-box" }} />
                  </label>
                </div>
              </div>

              {/* Semantic Scholar Section */}
              <div className="card" style={{ padding: "1rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
                  <h4 style={{ margin: 0 }}>📚 Semantic Scholar</h4>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    {validationResults.semantic_scholar && (
                      <span style={{
                        padding: "0.2rem 0.6rem", borderRadius: "999px", fontSize: "0.75rem", fontWeight: 500,
                        background: validationResults.semantic_scholar.ok ? "#dcfce7" : "#fee2e2",
                        color: validationResults.semantic_scholar.ok ? "#166534" : "#b91c1c",
                      }}>
                        {validationResults.semantic_scholar.ok ? "✓ API key hợp lệ" : "✕ Lỗi"}
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => testService("semantic_scholar")}
                      disabled={validatingService !== null}
                      style={{ fontSize: "0.8rem", padding: "0.35rem 0.75rem", cursor: "pointer", borderRadius: "8px", border: "1px solid #d1d5db", background: validatingService === "semantic_scholar" ? "#f3f4f6" : "#fff" }}
                    >
                      {validatingService === "semantic_scholar" ? "Đang kiểm tra..." : "Test kết nối"}
                    </button>
                  </div>
                </div>
                {validationResults.semantic_scholar && !validationResults.semantic_scholar.ok && (
                  <div style={{ padding: "0.5rem 0.75rem", borderRadius: "8px", background: "#fef2f2", color: "#b91c1c", fontSize: "0.8rem", marginBottom: "0.75rem" }}>
                    {validationResults.semantic_scholar.message}
                  </div>
                )}
                {validationResults.semantic_scholar && validationResults.semantic_scholar.ok && (
                  <div style={{ padding: "0.5rem 0.75rem", borderRadius: "8px", background: "#f0fdf4", color: "#166534", fontSize: "0.8rem", marginBottom: "0.75rem" }}>
                    {validationResults.semantic_scholar.message}
                  </div>
                )}
                <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", fontSize: "0.85rem", fontWeight: 500, color: "#374151" }}>
                  API key (nhập mới để cập nhật)
                  <input type="password" value={configForm.semantic_scholar_api_key} onChange={(e) => updateConfigField("semantic_scholar_api_key", e.target.value)} placeholder="Nhập API key..." style={{ width: "100%", padding: "0.5rem", borderRadius: "8px", border: "1px solid #d1d5db", boxSizing: "border-box" }} />
                </label>
                <div style={{ marginTop: "0.5rem", color: "#6b7280", fontSize: "0.8rem" }}>
                  Key hiện tại: {config?.semantic_scholar_api_key_masked || "(chưa cấu hình)"}
                </div>
              </div>

              {/* Embedding Section */}
              <div className="card" style={{ padding: "1rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
                  <h4 style={{ margin: 0 }}>🧠 Embedding Model</h4>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    {validationResults.embedding && (
                      <span style={{
                        padding: "0.2rem 0.6rem", borderRadius: "999px", fontSize: "0.75rem", fontWeight: 500,
                        background: validationResults.embedding.ok ? "#dcfce7" : "#fee2e2",
                        color: validationResults.embedding.ok ? "#166534" : "#b91c1c",
                      }}>
                        {validationResults.embedding.ok ? "✓ Model OK" : "✕ Lỗi"}
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => testService("embedding")}
                      disabled={validatingService !== null}
                      style={{ fontSize: "0.8rem", padding: "0.35rem 0.75rem", cursor: "pointer", borderRadius: "8px", border: "1px solid #d1d5db", background: validatingService === "embedding" ? "#f3f4f6" : "#fff" }}
                    >
                      {validatingService === "embedding" ? "Đang kiểm tra..." : "Test kết nối"}
                    </button>
                  </div>
                </div>
                {validationResults.embedding && !validationResults.embedding.ok && (
                  <div style={{ padding: "0.5rem 0.75rem", borderRadius: "8px", background: "#fef2f2", color: "#b91c1c", fontSize: "0.8rem", marginBottom: "0.75rem" }}>
                    {validationResults.embedding.message}
                  </div>
                )}
                {validationResults.embedding && validationResults.embedding.ok && (
                  <div style={{ padding: "0.5rem 0.75rem", borderRadius: "8px", background: "#f0fdf4", color: "#166534", fontSize: "0.8rem", marginBottom: "0.75rem" }}>
                    {validationResults.embedding.message}
                  </div>
                )}
                <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", fontSize: "0.85rem", fontWeight: 500, color: "#374151" }}>
                  Model name
                  <input type="text" value={configForm.embedding_model} onChange={(e) => updateConfigField("embedding_model", e.target.value)} placeholder="e.g. BAAI/bge-small-en-v1.5" style={{ width: "100%", padding: "0.5rem", borderRadius: "8px", border: "1px solid #d1d5db", boxSizing: "border-box" }} />
                </label>
              </div>

              {/* Telegram Section */}
              <div className="card" style={{ padding: "1rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
                  <h4 style={{ margin: 0 }}>📨 Telegram Bot</h4>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    {validationResults.telegram && (
                      <span style={{
                        padding: "0.2rem 0.6rem", borderRadius: "999px", fontSize: "0.75rem", fontWeight: 500,
                        background: validationResults.telegram.ok ? "#dcfce7" : "#fee2e2",
                        color: validationResults.telegram.ok ? "#166534" : "#b91c1c",
                      }}>
                        {validationResults.telegram.ok ? "✓ Bot OK" : "✕ Lỗi"}
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => testService("telegram")}
                      disabled={validatingService !== null}
                      style={{ fontSize: "0.8rem", padding: "0.35rem 0.75rem", cursor: "pointer", borderRadius: "8px", border: "1px solid #d1d5db", background: validatingService === "telegram" ? "#f3f4f6" : "#fff" }}
                    >
                      {validatingService === "telegram" ? "Đang kiểm tra..." : "Test kết nối"}
                    </button>
                  </div>
                </div>
                {validationResults.telegram && !validationResults.telegram.ok && (
                  <div style={{ padding: "0.5rem 0.75rem", borderRadius: "8px", background: "#fef2f2", color: "#b91c1c", fontSize: "0.8rem", marginBottom: "0.75rem" }}>
                    {validationResults.telegram.message}
                  </div>
                )}
                {validationResults.telegram && validationResults.telegram.ok && (
                  <div style={{ padding: "0.5rem 0.75rem", borderRadius: "8px", background: "#f0fdf4", color: "#166534", fontSize: "0.8rem", marginBottom: "0.75rem" }}>
                    {validationResults.telegram.message}
                  </div>
                )}
                <label style={{ display: "inline-flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem", fontSize: "0.85rem", fontWeight: 500 }}>
                  <input type="checkbox" checked={configForm.telegram_enabled} onChange={(e) => updateConfigField("telegram_enabled", e.target.checked)} />
                  Bật Telegram notification
                </label>
                <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "1fr 1fr" }}>
                  <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", fontSize: "0.85rem", fontWeight: 500, color: "#374151" }}>
                    Bot token (nhập mới để cập nhật)
                    <input type="password" value={configForm.telegram_bot_token} onChange={(e) => updateConfigField("telegram_bot_token", e.target.value)} placeholder="Nhập bot token..." style={{ width: "100%", padding: "0.5rem", borderRadius: "8px", border: "1px solid #d1d5db", boxSizing: "border-box" }} />
                  </label>
                  <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", fontSize: "0.85rem", fontWeight: 500, color: "#374151" }}>
                    Chat ID
                    <input type="text" value={configForm.telegram_chat_id} onChange={(e) => updateConfigField("telegram_chat_id", e.target.value)} placeholder="e.g. -1001234567890" style={{ width: "100%", padding: "0.5rem", borderRadius: "8px", border: "1px solid #d1d5db", boxSizing: "border-box" }} />
                  </label>
                </div>
                <div style={{ marginTop: "0.5rem", color: "#6b7280", fontSize: "0.8rem" }}>
                  Token hiện tại: {config?.telegram_bot_token_masked || "(chưa cấu hình)"}
                </div>
              </div>

              {/* Pipeline Parameters */}
              <div className="card" style={{ padding: "1rem" }}>
                <h4 style={{ margin: "0 0 0.75rem" }}>⚡ Pipeline Parameters</h4>
                <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "1fr 1fr 1fr" }}>
                  <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", fontSize: "0.85rem", fontWeight: 500, color: "#374151" }}>
                    Metadata match threshold
                    <input type="number" min={0} max={1} step={0.01} value={configForm.metadata_match_threshold} onChange={(e) => updateConfigField("metadata_match_threshold", e.target.value)} style={{ width: "100%", padding: "0.5rem", borderRadius: "8px", border: "1px solid #d1d5db", boxSizing: "border-box" }} />
                  </label>
                  <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", fontSize: "0.85rem", fontWeight: 500, color: "#374151" }}>
                    Retry limit
                    <input type="number" min={0} max={10} value={configForm.pipeline_retry_limit} onChange={(e) => updateConfigField("pipeline_retry_limit", e.target.value)} style={{ width: "100%", padding: "0.5rem", borderRadius: "8px", border: "1px solid #d1d5db", boxSizing: "border-box" }} />
                  </label>
                  <label style={{ display: "flex", flexDirection: "column", gap: "0.25rem", fontSize: "0.85rem", fontWeight: 500, color: "#374151" }}>
                    Timeout (seconds)
                    <input type="number" min={10} max={3600} value={configForm.pipeline_timeout_seconds} onChange={(e) => updateConfigField("pipeline_timeout_seconds", e.target.value)} style={{ width: "100%", padding: "0.5rem", borderRadius: "8px", border: "1px solid #d1d5db", boxSizing: "border-box" }} />
                  </label>
                </div>
              </div>

              {/* Save Actions */}
              <div className="card" style={{ padding: "1rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.75rem" }}>
                  <div style={{ fontSize: "0.85rem", color: "#6b7280" }}>
                    Lưu sẽ tự động xác thực tất cả kết nối. Nếu bất kỳ dịch vụ nào sai, cấu hình sẽ không được lưu.
                  </div>
                  <div style={{ display: "flex", gap: "0.5rem" }}>
                    <button
                      type="button"
                      onClick={() => testService("all")}
                      disabled={validatingService !== null || isSavingConfig}
                      className="btn btn--secondary"
                      style={{ fontSize: "0.85rem", padding: "0.5rem 1rem", minHeight: "auto" }}
                    >
                      {validatingService === "all" ? "Đang kiểm tra tất cả..." : "Kiểm tra tất cả"}
                    </button>
                    <button
                      type="button"
                      onClick={saveConfig}
                      disabled={isSavingConfig || validatingService !== null}
                      className="btn btn--primary"
                      style={{ fontSize: "0.85rem", padding: "0.5rem 1.2rem", minHeight: "auto" }}
                    >
                      {isSavingConfig ? "Đang lưu và xác thực..." : "Lưu cấu hình"}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === "evaluation" && evaluation && (
            <div className="card" style={{ padding: "1rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: "0.75rem", flexWrap: "wrap" }}>
                <h3 style={{ margin: 0 }}>Dữ liệu đánh giá PoC</h3>
                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                  <input
                    type="number"
                    min={1}
                    max={365}
                    value={windowDays}
                    onChange={(e) => setWindowDays(Number(e.target.value) || 7)}
                  />
                  <button type="button" onClick={() => void loadEvaluation()}>
                    Làm mới
                  </button>
                  <button type="button" onClick={exportEvaluationData}>
                    Export JSON
                  </button>
                </div>
              </div>

              <p style={{ color: "#6b7280" }}>
                Cửa sổ dữ liệu: {evaluation.window_days} ngày · sinh lúc {formatDate(evaluation.generated_at)}
              </p>

              <div style={{ display: "grid", gap: "0.75rem", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
                <div><strong>Tổng papers:</strong> {evaluation.summary.total_papers}</div>
                <div><strong>Draft:</strong> {evaluation.summary.draft_papers}</div>
                <div><strong>Published:</strong> {evaluation.summary.published_papers}</div>
                <div><strong>Jobs xử lý:</strong> {evaluation.summary.jobs_processing}</div>
                <div><strong>Jobs lỗi:</strong> {evaluation.summary.jobs_failed}</div>
                <div><strong>Cache hit:</strong> {evaluation.summary.cache_hits}</div>
                <div><strong>Cache miss:</strong> {evaluation.summary.cache_misses}</div>
                <div><strong>Cache hit rate:</strong> {(evaluation.summary.cache_hit_rate * 100).toFixed(2)}%</div>
                <div><strong>Avg pipeline:</strong> {evaluation.summary.avg_pipeline_seconds?.toFixed(2) || "-"}s</div>
              </div>

              <h4 style={{ marginBottom: "0.5rem" }}>Pipeline errors</h4>
              {evaluation.processing_errors.length === 0 && <div>Không có lỗi trong cửa sổ hiện tại.</div>}
              {evaluation.processing_errors.map((item) => (
                <div key={item.event_type}>
                  {item.event_type}: {item.count}
                </div>
              ))}

              <h4 style={{ marginBottom: "0.5rem", marginTop: "1rem" }}>Search samples</h4>
              {evaluation.search_samples.length === 0 && <div>Chưa có search log.</div>}
              {evaluation.search_samples.map((item, idx) => (
                <div key={`${item.event_type}-${item.created_at}-${idx}`} style={{ borderBottom: "1px solid #e5e7eb", padding: "0.5rem 0" }}>
                  <div>
                    <strong>{item.event_type}</strong> · {formatDate(item.created_at)}
                  </div>
                  <div style={{ color: "#6b7280" }}>
                    Query: "{item.query}" · Kết quả: {item.result_count} · top/limit: {item.top_k_or_limit}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
