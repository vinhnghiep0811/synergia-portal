import { apiClient } from "./apiClient";
import { parseApiError } from "../utils/api";

/**
 * Tìm kiếm ngữ nghĩa các tài liệu
 * @param {string} query - Câu truy vấn tìm kiếm
 * @param {number} [top_k=5] - Số kết quả trả về
 * @returns {Promise<Object>} Kết quả tìm kiếm
 */
export async function semanticSearch(query, top_k = 5) {
  try {
    const response = await apiClient.post("/api/search/semantic", {
      query,
      top_k,
    });
    return response.data;
  } catch (error) {
    const message = await parseApiError(error);
    throw new Error(message);
  }
}

/**
 * Tìm kiếm theo từ khóa các tài liệu
 * @param {string} query - Từ khóa tìm kiếm
 * @param {number} [limit=10] - Số kết quả trả về
 * @returns {Promise<Object>} Kết quả tìm kiếm
 */
export async function keywordSearch(query, limit = 10) {
  try {
    const response = await apiClient.get(`/api/search/keyword?query=${encodeURIComponent(query)}&limit=${limit}`);
    return response.data;
  } catch (error) {
    const message = await parseApiError(error);
    throw new Error(message);
  }
}
