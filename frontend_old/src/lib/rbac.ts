export type Role = 'admin' | 'user';

export function hasRole(role: Role | undefined, required: Role): boolean {
  if (!role) return false;
  return role === required;
}
