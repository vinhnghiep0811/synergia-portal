import { API_BASE_URL, parseApiError } from "../utils/api";

/**
 * Upload một file PDF
 * @param {File} file
 * @returns {Promise<import("../types/paper").PaperUploadResponse>}
 */
export async function uploadPaper(file) {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(`${API_BASE_URL}/api/papers/upload`, {
        method: "POST",
        body: formData,
    });

    if (!response.ok) {
        const message = await parseApiError(response);
        throw new Error(`${file.name}: ${message}`);
    }

    return response.json();
}

/**
 * Upload nhiều file PDF
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
    const response = await fetch(
        `${API_BASE_URL}/api/papers?skip=${skip}&limit=${limit}`
    );

    if (!response.ok) {
        const message = await parseApiError(response);
        throw new Error(message);
    }

    return response.json();
}

/**
 * Lấy chi tiết paper theo id
 * @param {string} paperId
 * @returns {Promise<import("../types/paper").PaperDetailResponse>}
 */
export async function getPaperDetail(paperId) {
  const response = await fetch(`${API_BASE_URL}/api/papers/${paperId}`);

  if (!response.ok) {
    const message = await parseApiError(response);
    throw new Error(message);
  }

  return response.json();
}