import { apiFetch } from './client';

export async function listUsers(token: string | null) {
  try {
    return await apiFetch('/api/users', {}, token);
  } catch {
    return [];
  }
}
