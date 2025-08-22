export const API_BASE = import.meta.env.VITE_API_BASE_URL as string;

export async function apiFetch(path: string, options?: RequestInit, token?: string | null) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(options && options.headers),
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    }
  });
  if (!res.ok) throw new Error('Network error');
  return res.json();
}
