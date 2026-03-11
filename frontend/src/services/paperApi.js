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