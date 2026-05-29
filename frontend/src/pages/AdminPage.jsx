import { useCallback, useEffect, useMemo, useState } from "react";
import { AppHeader } from "../components/AppHeader.jsx";
import "../styles/AdminPage.css";
import {
  addAdminLLMProvider,
  getAdminActivities,
  getAdminCanonicalDocuments,
  getAdminConfiguration,
  getAdminLLMProviders,
  getAdminLLMPrompts,
  getAdminEvaluationReport,
  getAdminOverview,
  getAdminPapers,
  getAdminProcessingLogs,
  removeAdminLLMProvider,
  updateAdminConfiguration,
  updateAdminLLMPrompts,
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

function StatusBadge({ status }) {
  return (
    <span className="admin-status-pill" style={{ "--admin-status-color": getStatusColor(status) }}>
      {status || "-"}
    </span>
  );
}

function MiniBarChart({ items, emptyMessage }) {
  if (!items.length) {
    return <div className="admin-empty-state">{emptyMessage}</div>;
  }

  const max = Math.max(...items.map((item) => item.value), 1);
  return (
    <div className="admin-chart">
      {items.map((item) => {
        const width = Math.min(100, Math.max(0, (item.value / max) * 100));
        return (
          <div key={item.key} className="admin-chart__row">
            <div className="admin-chart__meta">
              <span className="admin-chart__label">{item.label}</span>
              <span className="admin-chart__value">{item.valueText || item.value}</span>
            </div>
            <div className="admin-chart__track">
              <span className="admin-chart__fill" style={{ width: `${width}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Pagination({ page, totalPages, onChange }) {
  if (totalPages <= 1) return null;

  const pages = [];
  const start = Math.max(1, page - 2);
  const end = Math.min(totalPages, start + 4);
  for (let i = start; i <= end; i += 1) pages.push(i);

  return (
    <div className="pagination">
      <button
        type="button"
        className="pagination__btn pagination__btn--arrow"
        onClick={() => onChange(Math.max(1, page - 1))}
        disabled={page === 1}
      >
        ‹
      </button>
      <div className="pagination__numbers">
        {pages.map((p) => (
          <button
            key={p}
            type="button"
            className={`pagination__btn pagination__btn--number ${p === page ? "pagination__btn--active" : ""}`}
            onClick={() => onChange(p)}
          >
            {p}
          </button>
        ))}
      </div>
      <button
        type="button"
        className="pagination__btn pagination__btn--arrow"
        onClick={() => onChange(Math.min(totalPages, page + 1))}
        disabled={page === totalPages}
      >
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
    llm_base_url: "",
    llm_extra_params: "",
    llm_api_key: "",
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

  const [llmProviders, setLlmProviders] = useState([]);
  const [newProviderName, setNewProviderName] = useState("");

  const [promptTemplates, setPromptTemplates] = useState([]);
  const [promptForm, setPromptForm] = useState({});
  const [isSavingPrompts, setIsSavingPrompts] = useState(false);
  const [promptSuccess, setPromptSuccess] = useState("");

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
      const [data, providerData, promptData] = await Promise.all([
        getAdminConfiguration(),
        getAdminLLMProviders(),
        getAdminLLMPrompts(),
      ]);

      setConfig(data);
      setConfigForm({
        llm_provider: data.llm_provider || "gemini",
        llm_model: data.llm_model || "",
        llm_base_url: data.llm_base_url || "",
        llm_extra_params: data.llm_extra_params
          ? JSON.stringify(data.llm_extra_params, null, 2)
          : "",
        llm_api_key: "",
        embedding_model: data.embedding_model || "",
        metadata_match_threshold: data.metadata_match_threshold ?? 0.7,
        pipeline_retry_limit: data.pipeline_retry_limit ?? 3,
        pipeline_timeout_seconds: data.pipeline_timeout_seconds ?? 300,
        telegram_enabled: Boolean(data.telegram_enabled),
        telegram_chat_id: data.telegram_chat_id || "",
        semantic_scholar_api_key: "",
        telegram_bot_token: "",
      });

      const providers = providerData?.providers || [];
      setLlmProviders(providers);

      const templates = promptData?.templates || [];
      setPromptTemplates(templates);
      const initialPromptForm = {};
      templates.forEach((template) => {
        initialPromptForm[template.key] = template.content || "";
      });
      setPromptForm(initialPromptForm);

      setValidationResults({});
      setConfigSuccess("");
      setPromptSuccess("");
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
  const overviewPipelineChart = useMemo(() => {
    const operations = overview?.operations || {};
    return [
      { key: "jobs_processing", label: "Jobs đang xử lý", value: Number(operations.jobs_processing || 0) },
      { key: "jobs_failed", label: "Jobs lỗi", value: Number(operations.jobs_failed || 0) },
      { key: "cache_hits", label: "Cache hit", value: Number(operations.cache_hits || 0) },
      { key: "cache_misses", label: "Cache miss", value: Number(operations.cache_misses || 0) },
    ];
  }, [overview]);
  const evaluationErrorChart = useMemo(
    () =>
      (evaluation?.processing_errors || []).map((item) => ({
        key: item.event_type,
        label: item.event_type,
        value: Number(item.count || 0),
      })),
    [evaluation]
  );
  const evaluationCacheChart = useMemo(() => {
    if (!evaluation) return [];
    return [
      {
        key: "cache_hit",
        label: "Cache hit",
        value: Number(evaluation.summary.cache_hits || 0),
      },
      {
        key: "cache_miss",
        label: "Cache miss",
        value: Number(evaluation.summary.cache_misses || 0),
      },
    ];
  }, [evaluation]);

  const providerOptions = useMemo(() => {
    if (llmProviders.length) return llmProviders;
    return [
      { name: "gemini", is_fallback: false, is_locked: false },
      { name: "ollama", is_fallback: true, is_locked: true },
    ];
  }, [llmProviders]);

  const updateConfigField = useCallback((field, value) => {
    setConfigForm((prev) => {
      if (field === "llm_provider") {
        return {
          ...prev,
          llm_provider: value,
          llm_model: "",
          llm_base_url: "",
          llm_extra_params: "",
          llm_api_key: "",
        };
      }
      return { ...prev, [field]: value };
    });
    setValidationResults((prev) => {
      const next = { ...prev };
      if (field.startsWith("llm_")) delete next.llm;
      if (field.startsWith("semantic_scholar")) delete next.semantic_scholar;
      if (field.startsWith("telegram_")) delete next.telegram;
      if (field.startsWith("embedding_")) delete next.embedding;
      return next;
    });
  }, []);

  const updatePromptField = useCallback((key, value) => {
    setPromptForm((prev) => ({ ...prev, [key]: value }));
    setPromptSuccess("");
  }, []);

  const parseExtraParams = useCallback((raw) => {
    if (!raw || !raw.trim()) return undefined;
    try {
      return JSON.parse(raw);
    } catch (err) {
      throw new Error("LLM extra params phải là JSON hợp lệ.");
    }
  }, []);

  const handleAddProvider = useCallback(async () => {
    const trimmed = newProviderName.trim();
    if (!trimmed) return;

    setError("");
    try {
      const data = await addAdminLLMProvider(trimmed);
      setLlmProviders(data.providers || []);
      setNewProviderName("");
    } catch (err) {
      setError(err.message || "Không thể thêm provider mới");
    }
  }, [newProviderName]);

  const handleRemoveProvider = useCallback(async (name) => {
    setError("");
    try {
      const data = await removeAdminLLMProvider(name);
      const providers = data.providers || [];
      setLlmProviders(providers);
      if (configForm.llm_provider === name && providers.length > 0) {
        const nextProvider = providers.find((item) => !item.is_locked) || providers[0];
        updateConfigField("llm_provider", nextProvider.name);
      }
    } catch (err) {
      setError(err.message || "Không thể xoá provider");
    }
  }, [configForm.llm_provider, updateConfigField]);

  const savePrompts = useCallback(async () => {
    setIsSavingPrompts(true);
    setError("");
    setPromptSuccess("");
    try {
      const payload = {
        templates: promptTemplates.map((template) => ({
          key: template.key,
          content: promptForm[template.key] ?? "",
        })),
      };
      const updated = await updateAdminLLMPrompts(payload);
      const templates = updated.templates || [];
      setPromptTemplates(templates);
      const nextPromptForm = {};
      templates.forEach((template) => {
        nextPromptForm[template.key] = template.content || "";
      });
      setPromptForm(nextPromptForm);
      setPromptSuccess("Prompt đã được lưu.");
    } catch (err) {
      setError(err.message || "Lưu prompt thất bại");
    } finally {
      setIsSavingPrompts(false);
    }
  }, [promptForm, promptTemplates]);

  const testService = useCallback(async (service) => {
    setValidatingService(service);
    setError("");
    try {
      const extraParams = parseExtraParams(configForm.llm_extra_params);
      const payload = {
        service,
        llm_provider: configForm.llm_provider,
        llm_model: configForm.llm_model || undefined,
        llm_base_url: configForm.llm_base_url || undefined,
        llm_extra_params: extraParams || undefined,
        llm_api_key: configForm.llm_api_key || undefined,
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
        llm_base_url: updated.llm_base_url || "",
        llm_extra_params: updated.llm_extra_params
          ? JSON.stringify(updated.llm_extra_params, null, 2)
          : "",
        llm_api_key: "",
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
      const extraParams = parseExtraParams(configForm.llm_extra_params);
      const payload = {
        llm_provider: configForm.llm_provider,
        llm_model: configForm.llm_model,
        llm_base_url: configForm.llm_base_url.trim() ? configForm.llm_base_url.trim() : null,
        embedding_model: configForm.embedding_model,
        metadata_match_threshold: Number(configForm.metadata_match_threshold),
        pipeline_retry_limit: Number(configForm.pipeline_retry_limit),
        pipeline_timeout_seconds: Number(configForm.pipeline_timeout_seconds),
        telegram_enabled: Boolean(configForm.telegram_enabled),
        telegram_chat_id: configForm.telegram_chat_id || null,
      };
      if (configForm.llm_extra_params.trim()) {
        payload.llm_extra_params = extraParams;
      } else {
        payload.llm_extra_params = null;
      }
      if (configForm.llm_api_key.trim()) {
        payload.llm_api_key = configForm.llm_api_key.trim();
      }
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
        llm_api_key: "",
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
    <div className="app-shell admin-page">
      <AppHeader title="Quản trị hệ thống" subtitle="UC-04: Vận hành và cấu hình hệ thống" />

      <main className="app-main app-main--papers">
        <div className="app-main__full">
          <div className="tabs admin-tabs">
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
            <div className="card admin-alert admin-alert--error">
              {error}
            </div>
          )}

          {loading && (
            <div className="card admin-alert">
              Đang tải dữ liệu...
            </div>
          )}

          {activeTab === "overview" && overview && (
            <div className="admin-overview-layout">
              <div className="admin-overview-grid">
                <div className="card admin-metric-card">
                  <h3 className="admin-card-title">Tài liệu</h3>
                  <div className="admin-kv-list">
                    <div className="admin-kv-row"><span>Tổng số</span><strong>{overview.total_papers}</strong></div>
                    <div className="admin-kv-row"><span>Trùng lặp</span><strong>{overview.duplicate_count}</strong></div>
                  </div>
                </div>

                <div className="card admin-metric-card">
                  <h3 className="admin-card-title">Pipeline</h3>
                  <div className="admin-kv-list">
                    <div className="admin-kv-row"><span>Jobs đang xử lý</span><strong>{overview.operations?.jobs_processing ?? 0}</strong></div>
                    <div className="admin-kv-row"><span>Jobs lỗi</span><strong>{overview.operations?.jobs_failed ?? 0}</strong></div>
                    <div className="admin-kv-row"><span>Cache hit</span><strong>{overview.operations?.cache_hits ?? 0}</strong></div>
                    <div className="admin-kv-row"><span>Cache miss</span><strong>{overview.operations?.cache_misses ?? 0}</strong></div>
                  </div>
                </div>

                <div className="card admin-metric-card">
                  <h3 className="admin-card-title">Logs</h3>
                  <div className="admin-kv-list">
                    <div className="admin-kv-row"><span>Activity</span><strong>{overview.operations?.total_activity_logs ?? 0}</strong></div>
                    <div className="admin-kv-row"><span>Processing</span><strong>{overview.operations?.total_processing_logs ?? 0}</strong></div>
                  </div>
                </div>

                <div className="card admin-metric-card">
                  <h3 className="admin-card-title">Admin hiện tại</h3>
                  <div className="admin-kv-list">
                    <div className="admin-kv-row"><span>Email</span><strong>{overview.current_admin?.email || "-"}</strong></div>
                    <div className="admin-kv-row"><span>Role</span><strong>{overview.current_admin?.role || "-"}</strong></div>
                  </div>
                </div>
              </div>

              <div className="card admin-chart-card">
                <div className="admin-chart-card__header">
                  <h3 className="admin-card-title">Biểu đồ vận hành</h3>
                  <span className="admin-chart-card__sub">So sánh nhanh trạng thái pipeline</span>
                </div>
                <MiniBarChart items={overviewPipelineChart} emptyMessage="Chưa có dữ liệu vận hành." />
              </div>
            </div>
          )}

          {activeTab === "papers" && (
            <div className="card admin-panel-card">
              <h3 className="admin-card-title">
                Papers ({papersTotal}) - Trang {papersPage}/{paperTotalPages}
              </h3>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Filename</th>
                      <th>Status</th>
                      <th>Stage</th>
                      <th>Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {papers.map((paper) => (
                      <tr key={paper.id}>
                        <td>{paper.original_filename}</td>
                        <td>
                          <StatusBadge status={paper.processing_status} />
                        </td>
                        <td>{paper.processing_stage || "-"}</td>
                        <td>{formatDate(paper.created_at)}</td>
                      </tr>
                    ))}
                    {papers.length === 0 && (
                      <tr>
                        <td colSpan={4} className="admin-table__empty">Không có dữ liệu</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
              <Pagination page={papersPage} totalPages={paperTotalPages} onChange={setPapersPage} />
            </div>
          )}

          {activeTab === "canonical" && (
            <div className="card admin-panel-card">
              <h3 className="admin-card-title">
                Canonical Documents ({canonicalTotal}) - Trang {canonicalPage}/{canonicalTotalPages}
              </h3>
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Key</th>
                      <th>Title</th>
                      <th>Status</th>
                      <th>Papers</th>
                    </tr>
                  </thead>
                  <tbody>
                    {canonicalDocs.map((doc) => (
                      <tr key={doc.id}>
                        <td className="admin-code">{doc.canonical_key}</td>
                        <td>{doc.title || doc.title_candidate || "-"}</td>
                        <td><StatusBadge status={doc.enrichment_status || "-"} /></td>
                        <td>{doc.paper_count || 0}</td>
                      </tr>
                    ))}
                    {canonicalDocs.length === 0 && (
                      <tr>
                        <td colSpan={4} className="admin-table__empty">Không có dữ liệu</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
              <Pagination page={canonicalPage} totalPages={canonicalTotalPages} onChange={setCanonicalPage} />
            </div>
          )}

          {activeTab === "activities" && (
            <div className="card admin-panel-card">
              <h3 className="admin-card-title">
                Activity log ({activitiesTotal}) - Trang {activitiesPage}/{activitiesTotalPages}
              </h3>
              <div className="admin-log-list">
                {activities.map((item) => (
                  <div key={item.id} className="admin-log-item">
                    <div className="admin-log-item__head">
                      <strong>{item.event_label}</strong>
                      <span>{formatDate(item.created_at)}</span>
                    </div>
                    <div className="admin-log-item__message">{item.message}</div>
                    <div className="admin-log-item__meta">
                      Actor: {item.actor_display} · Status: <StatusBadge status={item.status} />
                    </div>
                  </div>
                ))}
              </div>
              {activities.length === 0 && <div className="admin-empty-state">Không có dữ liệu.</div>}
              <Pagination page={activitiesPage} totalPages={activitiesTotalPages} onChange={setActivitiesPage} />
            </div>
          )}

          {activeTab === "processing" && (
            <div className="card admin-panel-card">
              <div className="admin-panel-head">
                <h3 className="admin-card-title">
                  Processing log ({processingTotal}) - Trang {processingPage}/{processingTotalPages}
                </h3>
                <div className="admin-filter-row">
                  <select
                    className="admin-input admin-input--compact"
                    value={processingFamily}
                    onChange={(e) => setProcessingFamily(e.target.value)}
                  >
                    <option value="all">Tất cả</option>
                    <option value="parse">Parse</option>
                    <option value="semantic_scholar">Semantic Scholar</option>
                    <option value="llm_extraction">LLM Extraction</option>
                    <option value="duplicate">Duplicate</option>
                    <option value="canonical">Canonical</option>
                  </select>
                  <label className="admin-check">
                    <input
                      type="checkbox"
                      checked={processingErrorsOnly}
                      onChange={(e) => setProcessingErrorsOnly(e.target.checked)}
                    />
                    Chỉ lỗi
                  </label>
                </div>
              </div>
              <div className="admin-log-list">
                {processingLogs.map((item) => (
                  <div key={item.id} className="admin-log-item">
                    <div className="admin-log-item__head">
                      <strong>{item.event_label}</strong>
                      <span>{formatDate(item.created_at)}</span>
                    </div>
                    <div className="admin-log-item__message">{item.message}</div>
                    <div className="admin-log-item__meta">
                      Event: {item.event_type} · Status: <StatusBadge status={item.status} />
                    </div>
                  </div>
                ))}
              </div>
              {processingLogs.length === 0 && <div className="admin-empty-state">Không có dữ liệu.</div>}
              <Pagination page={processingPage} totalPages={processingTotalPages} onChange={setProcessingPage} />
            </div>
          )}

          {activeTab === "config" && (
            <div className="admin-config-layout">
              {/* Header with mode indicator and default settings button */}
              <div className="card admin-panel-card">
                <div className="admin-panel-head">
                  <div>
                    <h3 className="admin-card-title">Cấu hình hệ thống</h3>
                    <p className="admin-muted-text">
                      Cập nhật tham số vận hành. Hệ thống sẽ kiểm tra kết nối trước khi lưu.
                    </p>
                  </div>
                  <div className="admin-filter-row">
                    <span className={`admin-chip ${config?.source === "env_default" ? "admin-chip--success" : "admin-chip--info"}`}>
                      {config?.source === "env_default" ? "⚙️ Default (.env)" : "🔧 Custom config"}
                    </span>
                    <button
                      type="button"
                      className="btn btn--secondary admin-btn-compact"
                      onClick={switchToDefaults}
                      disabled={isSavingConfig || config?.source === "env_default"}
                    >
                      Dùng Default Settings
                    </button>
                  </div>
                </div>

                {configSuccess && (
                  <div className="admin-callout admin-callout--success">
                    ✅ {configSuccess}
                  </div>
                )}
                {config?.updated_at && (
                  <div className="admin-meta-text">
                    Cập nhật gần nhất: {formatDate(config.updated_at)} bởi {config.updated_by || "-"}
                  </div>
                )}
              </div>

              {/* LLM Configuration Section */}
              <div className="card admin-panel-card admin-config-card">
                <div className="admin-config-card__head">
                  <h4 className="admin-card-subtitle">🤖 LLM Provider</h4>
                  <div className="admin-filter-row">
                    {validationResults.llm && (
                      <span className={`admin-chip ${validationResults.llm.ok ? "admin-chip--success" : "admin-chip--error"}`}>
                        {validationResults.llm.ok ? "✓ Kết nối OK" : "✕ Lỗi"}
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => testService("llm")}
                      disabled={validatingService !== null}
                      className="admin-test-btn"
                    >
                      {validatingService === "llm" ? "Đang kiểm tra..." : "Test kết nối"}
                    </button>
                  </div>
                </div>
                {validationResults.llm && !validationResults.llm.ok && (
                  <div className="admin-callout admin-callout--error">
                    {validationResults.llm.message}
                  </div>
                )}
                {validationResults.llm && validationResults.llm.ok && (
                  <div className="admin-callout admin-callout--success">
                    {validationResults.llm.message}
                  </div>
                )}
                <div className="admin-form-grid admin-form-grid--two">
                  <label className="admin-label">
                    Provider
                    <select className="admin-input" value={configForm.llm_provider} onChange={(e) => updateConfigField("llm_provider", e.target.value)}>
                      {providerOptions.map((provider) => (
                        <option key={provider.name} value={provider.name}>
                          {provider.name}{provider.is_fallback ? " (fallback)" : ""}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="admin-label">
                    Model name
                    <input className="admin-input" type="text" value={configForm.llm_model} onChange={(e) => updateConfigField("llm_model", e.target.value)} placeholder="e.g. gemini-2.5-pro" />
                  </label>
                </div>
                <label className="admin-label">
                  Base URL
                  <input
                    className="admin-input"
                    type="text"
                    value={configForm.llm_base_url}
                    onChange={(e) => updateConfigField("llm_base_url", e.target.value)}
                    placeholder="e.g. https://api.deepseek.com"
                  />
                </label>
                <label className="admin-label">
                  Extra params (JSON)
                  <textarea
                    className="admin-textarea"
                    rows={4}
                    value={configForm.llm_extra_params}
                    onChange={(e) => updateConfigField("llm_extra_params", e.target.value)}
                    placeholder='{"reasoning_effort": "high", "extra_body": {"thinking": {"type": "enabled"}}}'
                  />
                </label>
                <label className="admin-label">
                  API key (nhập mới để cập nhật)
                  <input
                    className="admin-input"
                    type="password"
                    value={configForm.llm_api_key}
                    onChange={(e) => updateConfigField("llm_api_key", e.target.value)}
                    placeholder="Nhập API key..."
                  />
                </label>
                <div className="admin-meta-text">
                  Key hiện tại: {config?.llm_api_key_masked || "(chưa cấu hình)"}
                </div>
                <div className="admin-provider-manager">
                  <label className="admin-label">
                    Thêm provider mới
                    <div className="admin-provider-add">
                      <input
                        className="admin-input"
                        type="text"
                        value={newProviderName}
                        onChange={(e) => setNewProviderName(e.target.value)}
                        placeholder="e.g. openai"
                      />
                      <button
                        type="button"
                        className="admin-test-btn"
                        onClick={handleAddProvider}
                        disabled={!newProviderName.trim()}
                      >
                        Thêm
                      </button>
                    </div>
                  </label>
                  <div className="admin-provider-list">
                    {providerOptions.map((provider) => (
                      <div key={provider.name} className="admin-provider-chip">
                        <span>{provider.name}</span>
                        {provider.is_fallback && <span className="admin-provider-tag">fallback</span>}
                        <button
                          type="button"
                          className="admin-provider-remove"
                          onClick={() => handleRemoveProvider(provider.name)}
                          disabled={provider.is_locked}
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                  </div>
                  <div className="admin-meta-text">
                    Ollama luôn được giữ làm fallback khi provider chính thất bại.
                  </div>
                </div>
              </div>

              {/* Prompt Templates Section */}
              <div className="card admin-panel-card admin-config-card">
                <div className="admin-config-card__head">
                  <h4 className="admin-card-subtitle">📝 Prompt LLM</h4>
                  <div className="admin-filter-row">
                    <button
                      type="button"
                      onClick={savePrompts}
                      disabled={isSavingPrompts}
                      className="admin-test-btn"
                    >
                      {isSavingPrompts ? "Đang lưu..." : "Lưu prompt"}
                    </button>
                  </div>
                </div>
                {promptSuccess && (
                  <div className="admin-callout admin-callout--success">
                    ✅ {promptSuccess}
                  </div>
                )}
                <div className="admin-meta-text">
                  Placeholder hỗ trợ: {"{{input_text}}, {{schema}}, {{output_shape}}, {{shape}}, {{broken_json}}, {{prompt_version}}."}
                </div>
                <div className="admin-prompt-grid">
                  {promptTemplates.length === 0 && (
                    <div className="admin-empty-state">Chưa có prompt để chỉnh sửa.</div>
                  )}
                  {promptTemplates.map((template) => (
                    <label key={template.key} className="admin-label admin-label--prompt">
                      {template.label}
                      <textarea
                        className="admin-textarea"
                        rows={10}
                        value={promptForm[template.key] || ""}
                        onChange={(e) => updatePromptField(template.key, e.target.value)}
                      />
                      <div className="admin-meta-text">
                        Key: {template.key} · {template.is_default ? "Default" : "Custom"}
                        {template.updated_at ? ` · Cập nhật ${formatDate(template.updated_at)}` : ""}
                        {template.updated_by ? ` · bởi ${template.updated_by}` : ""}
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              {/* Semantic Scholar Section */}
              <div className="card admin-panel-card admin-config-card">
                <div className="admin-config-card__head">
                  <h4 className="admin-card-subtitle">📚 Semantic Scholar</h4>
                  <div className="admin-filter-row">
                    {validationResults.semantic_scholar && (
                      <span className={`admin-chip ${validationResults.semantic_scholar.ok ? "admin-chip--success" : "admin-chip--error"}`}>
                        {validationResults.semantic_scholar.ok ? "✓ API key hợp lệ" : "✕ Lỗi"}
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => testService("semantic_scholar")}
                      disabled={validatingService !== null}
                      className="admin-test-btn"
                    >
                      {validatingService === "semantic_scholar" ? "Đang kiểm tra..." : "Test kết nối"}
                    </button>
                  </div>
                </div>
                {validationResults.semantic_scholar && !validationResults.semantic_scholar.ok && (
                  <div className="admin-callout admin-callout--error">
                    {validationResults.semantic_scholar.message}
                  </div>
                )}
                {validationResults.semantic_scholar && validationResults.semantic_scholar.ok && (
                  <div className="admin-callout admin-callout--success">
                    {validationResults.semantic_scholar.message}
                  </div>
                )}
                <label className="admin-label">
                  API key (nhập mới để cập nhật)
                  <input className="admin-input" type="password" value={configForm.semantic_scholar_api_key} onChange={(e) => updateConfigField("semantic_scholar_api_key", e.target.value)} placeholder="Nhập API key..." />
                </label>
                <div className="admin-meta-text">
                  Key hiện tại: {config?.semantic_scholar_api_key_masked || "(chưa cấu hình)"}
                </div>
              </div>

              {/* Embedding Section */}
              <div className="card admin-panel-card admin-config-card">
                <div className="admin-config-card__head">
                  <h4 className="admin-card-subtitle">🧠 Embedding Model</h4>
                  <div className="admin-filter-row">
                    {validationResults.embedding && (
                      <span className={`admin-chip ${validationResults.embedding.ok ? "admin-chip--success" : "admin-chip--error"}`}>
                        {validationResults.embedding.ok ? "✓ Model OK" : "✕ Lỗi"}
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => testService("embedding")}
                      disabled={validatingService !== null}
                      className="admin-test-btn"
                    >
                      {validatingService === "embedding" ? "Đang kiểm tra..." : "Test kết nối"}
                    </button>
                  </div>
                </div>
                {validationResults.embedding && !validationResults.embedding.ok && (
                  <div className="admin-callout admin-callout--error">
                    {validationResults.embedding.message}
                  </div>
                )}
                {validationResults.embedding && validationResults.embedding.ok && (
                  <div className="admin-callout admin-callout--success">
                    {validationResults.embedding.message}
                  </div>
                )}
                <label className="admin-label">
                  Model name
                  <input className="admin-input" type="text" value={configForm.embedding_model} onChange={(e) => updateConfigField("embedding_model", e.target.value)} placeholder="e.g. BAAI/bge-small-en-v1.5" />
                </label>
              </div>

              {/* Telegram Section */}
              <div className="card admin-panel-card admin-config-card">
                <div className="admin-config-card__head">
                  <h4 className="admin-card-subtitle">📨 Telegram Bot</h4>
                  <div className="admin-filter-row">
                    {validationResults.telegram && (
                      <span className={`admin-chip ${validationResults.telegram.ok ? "admin-chip--success" : "admin-chip--error"}`}>
                        {validationResults.telegram.ok ? "✓ Bot OK" : "✕ Lỗi"}
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => testService("telegram")}
                      disabled={validatingService !== null}
                      className="admin-test-btn"
                    >
                      {validatingService === "telegram" ? "Đang kiểm tra..." : "Test kết nối"}
                    </button>
                  </div>
                </div>
                {validationResults.telegram && !validationResults.telegram.ok && (
                  <div className="admin-callout admin-callout--error">
                    {validationResults.telegram.message}
                  </div>
                )}
                {validationResults.telegram && validationResults.telegram.ok && (
                  <div className="admin-callout admin-callout--success">
                    {validationResults.telegram.message}
                  </div>
                )}
                <label className="admin-check">
                  <input type="checkbox" checked={configForm.telegram_enabled} onChange={(e) => updateConfigField("telegram_enabled", e.target.checked)} />
                  Bật Telegram notification
                </label>
                <div className="admin-form-grid admin-form-grid--two">
                  <label className="admin-label">
                    Bot token (nhập mới để cập nhật)
                    <input className="admin-input" type="password" value={configForm.telegram_bot_token} onChange={(e) => updateConfigField("telegram_bot_token", e.target.value)} placeholder="Nhập bot token..." />
                  </label>
                  <label className="admin-label">
                    Chat ID
                    <input className="admin-input" type="text" value={configForm.telegram_chat_id} onChange={(e) => updateConfigField("telegram_chat_id", e.target.value)} placeholder="e.g. -1001234567890" />
                  </label>
                </div>
                <div className="admin-meta-text">
                  Token hiện tại: {config?.telegram_bot_token_masked || "(chưa cấu hình)"}
                </div>
              </div>

              {/* Pipeline Parameters */}
              <div className="card admin-panel-card admin-config-card">
                <h4 className="admin-card-subtitle">⚡ Pipeline Parameters</h4>
                <div className="admin-form-grid admin-form-grid--three">
                  <label className="admin-label">
                    Metadata match threshold
                    <input className="admin-input" type="number" min={0} max={1} step={0.01} value={configForm.metadata_match_threshold} onChange={(e) => updateConfigField("metadata_match_threshold", e.target.value)} />
                  </label>
                  <label className="admin-label">
                    Retry limit
                    <input className="admin-input" type="number" min={0} max={10} value={configForm.pipeline_retry_limit} onChange={(e) => updateConfigField("pipeline_retry_limit", e.target.value)} />
                  </label>
                  <label className="admin-label">
                    Timeout (seconds)
                    <input className="admin-input" type="number" min={10} max={3600} value={configForm.pipeline_timeout_seconds} onChange={(e) => updateConfigField("pipeline_timeout_seconds", e.target.value)} />
                  </label>
                </div>
              </div>

              {/* Save Actions */}
              <div className="card admin-panel-card">
                <div className="admin-panel-head">
                  <div className="admin-muted-text">
                    Lưu sẽ tự động xác thực tất cả kết nối. Nếu bất kỳ dịch vụ nào sai, cấu hình sẽ không được lưu.
                  </div>
                  <div className="admin-filter-row">
                    <button
                      type="button"
                      onClick={() => testService("all")}
                      disabled={validatingService !== null || isSavingConfig}
                      className="btn btn--secondary admin-btn-compact"
                    >
                      {validatingService === "all" ? "Đang kiểm tra tất cả..." : "Kiểm tra tất cả"}
                    </button>
                    <button
                      type="button"
                      onClick={saveConfig}
                      disabled={isSavingConfig || validatingService !== null}
                      className="btn btn--primary admin-btn-compact"
                    >
                      {isSavingConfig ? "Đang lưu và xác thực..." : "Lưu cấu hình"}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === "evaluation" && evaluation && (
            <div className="card admin-panel-card">
              <div className="admin-panel-head">
                <h3 className="admin-card-title">Dữ liệu đánh giá PoC</h3>
                <div className="admin-filter-row">
                  <input
                    className="admin-input admin-input--compact"
                    type="number"
                    min={1}
                    max={365}
                    value={windowDays}
                    onChange={(e) => setWindowDays(Number(e.target.value) || 7)}
                  />
                  <button className="admin-test-btn" type="button" onClick={() => void loadEvaluation()}>
                    Làm mới
                  </button>
                  <button className="admin-test-btn" type="button" onClick={exportEvaluationData}>
                    Export JSON
                  </button>
                </div>
              </div>

              <p className="admin-meta-text">
                Cửa sổ dữ liệu: {evaluation.window_days} ngày · sinh lúc {formatDate(evaluation.generated_at)}
              </p>

              <div className="admin-summary-grid">
                <div className="admin-summary-item"><span>Tổng papers</span><strong>{evaluation.summary.total_papers}</strong></div>
                <div className="admin-summary-item"><span>Draft</span><strong>{evaluation.summary.draft_papers}</strong></div>
                <div className="admin-summary-item"><span>Published</span><strong>{evaluation.summary.published_papers}</strong></div>
                <div className="admin-summary-item"><span>Jobs xử lý</span><strong>{evaluation.summary.jobs_processing}</strong></div>
                <div className="admin-summary-item"><span>Jobs lỗi</span><strong>{evaluation.summary.jobs_failed}</strong></div>
                <div className="admin-summary-item"><span>Cache hit</span><strong>{evaluation.summary.cache_hits}</strong></div>
                <div className="admin-summary-item"><span>Cache miss</span><strong>{evaluation.summary.cache_misses}</strong></div>
                <div className="admin-summary-item"><span>Cache hit rate</span><strong>{(evaluation.summary.cache_hit_rate * 100).toFixed(2)}%</strong></div>
                <div className="admin-summary-item"><span>Avg pipeline</span><strong>{evaluation.summary.avg_pipeline_seconds?.toFixed(2) || "-"}s</strong></div>
              </div>

              <div className="admin-evaluation-charts">
                <div className="admin-chart-card">
                  <div className="admin-chart-card__header">
                    <h4 className="admin-card-subtitle">Pipeline errors</h4>
                  </div>
                  <MiniBarChart items={evaluationErrorChart} emptyMessage="Không có lỗi trong cửa sổ hiện tại." />
                </div>
                <div className="admin-chart-card">
                  <div className="admin-chart-card__header">
                    <h4 className="admin-card-subtitle">Tỉ lệ cache</h4>
                  </div>
                  <MiniBarChart items={evaluationCacheChart} emptyMessage="Chưa có số liệu cache." />
                </div>
              </div>

              <h4 className="admin-card-subtitle">Search samples</h4>
              {evaluation.search_samples.length === 0 && <div className="admin-empty-state">Chưa có search log.</div>}
              {evaluation.search_samples.map((item, idx) => (
                <div key={`${item.event_type}-${item.created_at}-${idx}`} className="admin-log-item">
                  <div className="admin-log-item__head">
                    <strong>{item.event_type}</strong> · {formatDate(item.created_at)}
                  </div>
                  <div className="admin-log-item__meta">
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
