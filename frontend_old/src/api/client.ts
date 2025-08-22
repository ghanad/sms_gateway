export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export async function request<T>(
  url: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${url}`, options);
  if (!res.ok) throw new Error('API error');
  return res.json();
}
