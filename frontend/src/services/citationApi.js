import { apiClient } from "./apiClient";
import { parseApiError } from "../utils/api";

export async function getCitationNetwork({
  runId = null,
  minScore = 0,
  limitEdges = 300,
  includeAllDocuments = false,
} = {}) {
  try {
    const params = {
      min_score: minScore,
      limit_edges: limitEdges,
    };

    if (runId) {
      params.run_id = runId;
    }
    if (typeof includeAllDocuments === "boolean") {
      params.include_all_documents = includeAllDocuments;
    }

    const response = await apiClient.get("/api/citation-graph/network", { params });
    return response.data;
  } catch (error) {
    const message = await parseApiError(error);
    throw new Error(message);
  }
}

export async function enqueueGlobalCitationRescore({
  algorithmVersion = null,
  forceFullRebuild = true,
} = {}) {
  try {
    const payload = {
      force_full_rebuild: Boolean(forceFullRebuild),
    };
    if (algorithmVersion) {
      payload.algorithm_version = algorithmVersion;
    }

    const response = await apiClient.post("/api/citation-graph/runs/score", payload);
    return response.data;
  } catch (error) {
    const message = await parseApiError(error);
    throw new Error(message);
  }
}

export async function getCitationRescoreJobStatus(jobId) {
  try {
    const response = await apiClient.get(`/api/citation-graph/jobs/${jobId}/status`);
    return response.data;
  } catch (error) {
    const message = await parseApiError(error);
    throw new Error(message);
  }
}

export async function getCitationEdgeMentions(edgeId, limit = 30) {
  try {
    const response = await apiClient.get(`/api/citation-graph/edges/${edgeId}/mentions`, {
      params: { limit },
    });
    return response.data;
  } catch (error) {
    const message = await parseApiError(error);
    throw new Error(message);
  }
}
