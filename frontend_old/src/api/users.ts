import { request } from './client';

export interface User {
  id: number;
  name: string;
  username: string;
  daily_quota: number;
  api_key: string;
  note?: string;
  active: boolean;
}

export interface UserCreate {
  name: string;
  username: string;
  daily_quota: number;
  api_key: string;
  password: string;
  note?: string;
}

export function listUsers() {
  return request<User[]>('/api/users');
}

export function createUser(data: UserCreate) {
  return request<User>('/api/users', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateUser(id: number, data: Partial<User>) {
  return request<User>(`/api/users/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export function deleteUser(id: number) {
  return request<void>(`/api/users/${id}`, { method: 'DELETE' });
}

export function activateUser(id: number) {
  return request<User>(`/api/users/${id}/activate`, { method: 'POST' });
}

export function deactivateUser(id: number) {
  return request<User>(`/api/users/${id}/deactivate`, { method: 'POST' });
}

export function changePassword(username: string, password: string) {
  return request<void>(`/api/users/${username}/password`, {
    method: 'POST',
    body: JSON.stringify({ password }),
  });
}
