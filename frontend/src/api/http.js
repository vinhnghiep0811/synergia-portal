export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export async function getHealth() {
  const res = await fetch(`${API_BASE_URL}/api/health`);
  if (!res.ok) throw new Error(`Health failed: ${res.status}`);
  return res.json();
}