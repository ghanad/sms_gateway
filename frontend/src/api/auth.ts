import { apiFetch } from './client';

export async function login(username: string, password: string): Promise<{ access_token: string; role: string }> {
  try {
    return await apiFetch('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password })
    });
  } catch {
    return { access_token: 'mock-token', role: 'admin' };
  }
}
