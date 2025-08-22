import { request } from './client';

export interface User {
  id: string;
  username: string;
  role: string;
}

export function listUsers() {
  return request<User[]>('/api/users');
}
