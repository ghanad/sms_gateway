export function canAccess(role: string | null, required: string) {
  if (!role) return false;
  if (required === 'user') return true;
  if (required === 'admin') return role === 'admin';
  return false;
}
