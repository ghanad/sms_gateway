import React from 'react';
import { useAuth } from './useAuth';

export function useFetch<T = any>(url: string) {
  const { token } = useAuth();
  const [data, setData] = React.useState<T | null>(null);
  const [error, setError] = React.useState<Error | null>(null);

  React.useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch(url, {
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        });
        if (!res.ok) throw new Error('Network error');
        const json = await res.json();
        setData(json);
      } catch (e: any) {
        setError(e);
      }
    };
    fetchData();
  }, [url, token]);

  return { data, error };
}
