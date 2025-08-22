import { request } from './client';

export interface Message {
  id: string;
  content: string;
  status: string;
}

export function listMessages() {
  return request<Message[]>('/api/messages');
}

export function getMessage(id: string) {
  return request<Message>(`/api/messages/${id}`);
}
