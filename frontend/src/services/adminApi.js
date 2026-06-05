import { apiClient } from "./apiClient";
import { parseApiError } from "../utils/api";

async function get(url, params) {
  try {
    const response = await apiClient.get(url, { params });
    return response.data;
  } catch (error) {
    throw new Error(await parseApiError(error));
  }
}

async function patch(url, payload) {
  try {
    const response = await apiClient.patch(url, payload);
    return response.data;
  } catch (error) {
    throw new Error(await parseApiError(error));
  }
}

async function post(url, payload) {
  try {
    const response = await apiClient.post(url, payload);
    return response.data;
  } catch (error) {
    throw new Error(await parseApiError(error));
  }
}

async function del(url) {
  try {
    const response = await apiClient.delete(url);
    return response.data;
  } catch (error) {
    throw new Error(await parseApiError(error));
  }
}

export async function getAdminOverview() {
  return get("/api/admin/overview");
}

export async function getAdminPapers(page = 1, pageSize = 20, q = "") {
  return get("/api/admin/papers", { page, page_size: pageSize, q });
}

export async function getAdminCanonicalDocuments(
  page = 1,
  pageSize = 20,
  sort_by = "created_at",
  sort_order = "desc"
) {
  return get("/api/admin/canonical-documents", {
    page,
    page_size: pageSize,
    sort_by,
    sort_order,
  });
}

export async function getAdminActivities(page = 1, pageSize = 20, options = {}) {
  const skip = (page - 1) * pageSize;
  return get("/api/admin/activity", {
    skip,
    limit: pageSize,
    ...options,
  });
}

export async function getAdminProcessingLogs(page = 1, pageSize = 20, options = {}) {
  const skip = (page - 1) * pageSize;
  return get("/api/admin/processing-logs", {
    skip,
    limit: pageSize,
    ...options,
  });
}

export async function getAdminConfiguration() {
  return get("/api/admin/configuration");
}

export async function updateAdminConfiguration(payload) {
  return patch("/api/admin/configuration", payload);
}

export async function validateAdminConfiguration(payload) {
  return post("/api/admin/configuration/validate", payload);
}

export async function getAdminEvaluationReport(windowDays = 7, searchSampleLimit = 20) {
  return get("/api/admin/evaluation-report", {
    window_days: windowDays,
    search_sample_limit: searchSampleLimit,
  });
}

export async function getAdminLLMPrompts() {
  return get("/api/admin/llm-prompts");
}

export async function updateAdminLLMPrompts(payload) {
  return patch("/api/admin/llm-prompts", payload);
}

export async function getAdminLLMModels() {
  return get("/api/admin/llm-models");
}

export async function addAdminLLMModel(payload) {
  return post("/api/admin/llm-models", payload);
}

export async function updateAdminLLMModel(modelId, payload) {
  return patch(`/api/admin/llm-models/${modelId}`, payload);
}

export async function removeAdminLLMModel(modelId) {
  return del(`/api/admin/llm-models/${modelId}`);
}

export async function deleteAdminCanonicalDocument(canonicalId, deletePapers = false) {
  return del(`/api/admin/canonical-documents/${canonicalId}?delete_papers=${deletePapers}`);
}

export async function deleteAdminPaper(paperId) {
  return del(`/api/admin/papers/${paperId}`);
}


