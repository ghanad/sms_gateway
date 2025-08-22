import { useAuth } from './useAuth';

export function useFetch() {
  const { token } = useAuth();

  return async (path: string, init?: RequestInit) => {
    const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}${path}` , {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(init && init.headers),
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      }
    });
    if (!res.ok) throw new Error('Network error');
    return res.json();
  };
}
