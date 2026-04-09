import { apiClient } from "./apiClient"; // Import instance Axios đã có Interceptor
import { parseApiError } from "../utils/api";

/**
 * Upload một file PDF
 * @param {File} file
 * @returns {Promise<import("../types/paper").PaperUploadResponse>}
 */
export async function uploadPaper(file) {
    const formData = new FormData();
    formData.append("file", file);

    try {
        // Axios tự động xử lý Content-Type cho FormData
        // Không cần truyền API_BASE_URL vì đã có trong apiClient config
        const response = await apiClient.post("/api/papers/upload", formData);
        
        return response.data; // Axios trả về dữ liệu trong thuộc tính .data
    } catch (error) {
        // Xử lý lỗi thông qua hàm parse chung
        const message = await parseApiError(error);
        throw new Error(`${file.name}: ${message}`);
    }
}

/**
 * Upload nhiều file PDF song song
 * @param {File[]} files
 * @returns {Promise<import("../types/paper").PaperUploadResponse[]>}
 */
export async function uploadManyPapers(files) {
    return Promise.all(files.map(uploadPaper));
}

/**
 * Lấy danh sách paper
 * @param {number} [skip=0]
 * @param {number} [limit=50]
 * @returns {Promise<import("../types/paper").PaperListItemResponse[]>}
 */
export async function getPapers(skip = 0, limit = 50) {
    try {
        const response = await apiClient.get("/api/papers", {
            params: { skip, limit } // Truyền query params dạng object cực kỳ sạch sẽ
        });
        return response.data;
    } catch (error) {
        const message = await parseApiError(error);
        throw new Error(message);
    }
}

/**
 * Lấy chi tiết paper theo id
 * @param {string} paperId
 * @returns {Promise<import("../types/paper").PaperDetailResponse>}
 */
export async function getPaperDetail(paperId) {
    try {
        const response = await apiClient.get(`/api/papers/${paperId}`);
        return response.data;
    } catch (error) {
        const message = await parseApiError(error);
        throw new Error(message);
    }
}

/**
 * Lấy canonical document theo paper id.
 * Trả về null khi paper chưa được link canonical.
 * @param {string} paperId
 * @returns {Promise<Object | null>}
 */
export async function getCanonicalDocumentByPaper(paperId) {
    try {
        const response = await apiClient.get(`/api/canonical-documents/by-paper/${paperId}`);
        return response.data;
    } catch (error) {
        if (error?.response?.status === 404) {
            return null;
        }

        const message = await parseApiError(error);
        throw new Error(message);
    }
}

/**
 * Lấy danh sách tất cả canonical documents
 * @param {number} [skip=0]
 * @param {number} [limit=50]
 * @returns {Promise<Array>}
 */
export async function getCanonicalDocuments(skip = 0, limit = 50) {
    try {
        const response = await apiClient.get("/api/canonical-documents", {
            params: { skip, limit }
        });
        return response.data;
    } catch (error) {
        const message = await parseApiError(error);
        throw new Error(message);
    }
}

/**
 * Lấy chi tiết canonical document theo id
 * @param {string} canonicalId
 * @returns {Promise<Object>}
 */
export async function getCanonicalDocumentDetail(canonicalId) {
    try {
        const response = await apiClient.get(`/api/canonical-documents/${canonicalId}`);
        return response.data;
    } catch (error) {
        const message = await parseApiError(error);
        throw new Error(message);
    }
}

/**
 * Lấy URL để mở PDF của paper trên tab mới
 * @param {string} paperId
 * @returns {string}
 */
export function getPaperFileViewUrl(paperId) {
    return apiClient.getUri({
        url: `/api/papers/${paperId}/file`,
    });
}

export async function getPapersByCanonicalId(canonicalId) {
  const res = await apiClient.get(`/canonical-documents/${canonicalId}/papers`);
  return res;
}

/**
 * Lấy danh sách extraction runs theo canonical document id
 * @param {string} canonicalId
 * @returns {Promise<Array>}
 */
export async function getExtractionRunsByCanonicalId(canonicalId) {
  try {
    const response = await apiClient.get(`/api/extraction-runs/canonical/${canonicalId}`);
    return response.data;
  } catch (error) {
    const message = await parseApiError(error);
    throw new Error(message);
  }
}

/**
 * Lấy chi tiết extraction run theo id
 * @param {string} runId
 * @returns {Promise<Object>}
 */
export async function getExtractionRunDetail(runId) {
  try {
    const response = await apiClient.get(`/api/extraction-runs/${runId}`);
    return response.data;
  } catch (error) {
    const message = await parseApiError(error);
    throw new Error(message);
  }
}

/**
 * Lấy metadata tổng hợp cho màn hình confirm publish.
 * @param {string} paperId
 * @returns {Promise<Object>}
 */
export async function getPublishMetadataPreview(paperId) {
    try {
        const response = await apiClient.get(`/api/papers/${paperId}/publish-metadata`);
        return response.data;
    } catch (error) {
        const message = await parseApiError(error);
        throw new Error(message);
    }
}

/**
 * Lưu metadata đã chỉnh sửa vào draft trên paper record.
 * @param {string} paperId
 * @param {Object} payload
 * @returns {Promise<Object>}
 */
export async function updatePublishMetadataDraft(paperId, payload) {
    try {
        const response = await apiClient.patch(`/api/papers/${paperId}/publish-metadata`, payload);
        return response.data;
    } catch (error) {
        const message = await parseApiError(error);
        throw new Error(message);
    }
}

/**
 * Publish paper và tạo publish version snapshot.
 * @param {string} paperId
 * @returns {Promise<Object>}
 */
export async function publishPaper(paperId) {
    try {
        const response = await apiClient.post(`/api/papers/${paperId}/publish`);
        return response.data;
    } catch (error) {
        const message = await parseApiError(error);
        throw new Error(message);
    }
}
