import axios from "axios";
import { API_BASE_URL } from "../utils/api.js";

export const apiClient = axios.create({
  baseURL: API_BASE_URL, 
  withCredentials: true,
});

let isRefreshing = false;
let failedQueue = [];

// Add request interceptor to include auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    // Only set Content-Type for JSON requests, let Axios handle FormData
    if (!(config.data instanceof FormData)) {
      config.headers['Content-Type'] = 'application/json';
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

function processQueue(error) {
  failedQueue.forEach(({ resolve, reject }) => error ? reject(error) : resolve(null));
  failedQueue = [];
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (
      error.response?.status !== 401 ||
      originalRequest._retry ||
      originalRequest.url?.includes("/api/auth/refresh") ||
      originalRequest.url?.includes("/api/auth/google")
    ) {
      return Promise.reject(error);
    }

    originalRequest._retry = true;

    if (isRefreshing) {
      return new Promise((resolve, reject) => failedQueue.push({ resolve, reject }))
        .then(() => apiClient(originalRequest));
    }

    isRefreshing = true;
    try {
      await apiClient.post("/api/auth/refresh");
      processQueue(null);
      return apiClient(originalRequest);
    } catch {
      processQueue(new Error("refresh failed"));
      return Promise.reject(error);
    } finally {
      isRefreshing = false;
    }
  }
);
