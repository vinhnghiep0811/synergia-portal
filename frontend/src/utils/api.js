export const API_BASE_URL =
    import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function parseApiError(error) {
    const response = error.response;
    
    if (!response) return "Kết nối máy chủ thất bại";

    const data = response.data; 
    
    if (typeof data?.detail === "string") return data.detail;
    if (Array.isArray(data?.detail)) {
        return data.detail.map((item) => item?.msg || "Lỗi dữ liệu").join(", ");
    }
    
    return "Yêu cầu thất bại";
}