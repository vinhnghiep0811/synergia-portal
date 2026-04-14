// services/adminApi.js
import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// Tạo axios instance chung cho toàn bộ admin API
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: true,           // ← QUAN TRỌNG: gửi cookie (OAuth session)
});

// Interceptor tự động thêm Bearer token (nếu có trong localStorage)
apiClient.interceptors.request.use(
  (config) => {
    const token =
      localStorage.getItem("token") ||
      localStorage.getItem("access_token") ||
      localStorage.getItem("auth_token");

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// ==================== ADMIN API ====================
export const getAdminOverview = async () => {
  const response = await apiClient.get("/api/admin/overview");
  return response.data;
};

export const getAdminPapers = async (page = 1, pageSize = 20, q = "") => {
  const response = await apiClient.get("/api/admin/papers", {
    params: { page, page_size: pageSize, q },
  });
  return response.data;
};

export const getAdminCanonicalDocuments = async (
  page = 1,
  pageSize = 20,
  sort_by = "created_at",
  sort_order = "desc"
) => {
  const response = await apiClient.get("/api/admin/canonical-documents", {
    params: { page, page_size: pageSize, sort_by, sort_order },
  });
  return response.data;
};

export const getAdminActivities = async (page = 1, pageSize = 20) => {
  const skip = (page - 1) * pageSize;
  const response = await apiClient.get("/api/admin/activity", {
    params: { skip, limit: pageSize },
  });
  return response.data;
};