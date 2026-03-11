export const API_BASE_URL =
    import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function parseApiError(response) {
    try {
        const data = await response.json();
        if (typeof data?.detail === "string") return data.detail;
        if (Array.isArray(data?.detail)) {
            return data.detail.map((item) => item?.msg || "Validation error").join(", ");
        }
        return "Request failed";
    } catch {
        return "Request failed";
    }
}