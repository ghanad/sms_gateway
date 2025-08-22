import { describe, it, expect } from 'vitest';
import { hasRole } from '../../lib/rbac';

describe('RBAC util', () => {
  it('checks roles correctly', () => {
    expect(hasRole('admin', 'admin')).toBe(true);
    expect(hasRole('user', 'admin')).toBe(false);
  });
});
