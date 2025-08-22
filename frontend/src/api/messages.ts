import { apiFetch } from './client';

export async function listMessages(token: string | null) {
  try {
    return await apiFetch('/api/messages', {}, token);
  } catch {
    return [];
  }
}

export async function getMessage(token: string | null, id: string) {
  try {
    return await apiFetch(`/api/messages/${id}`, {}, token);
  } catch {
    return null;
  }
}
