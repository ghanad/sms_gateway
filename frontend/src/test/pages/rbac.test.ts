import { canAccess } from '../../lib/rbac';

describe('rbac', () => {
  it('admin can access admin', () => {
    expect(canAccess('admin', 'admin')).toBe(true);
  });
  it('user cannot access admin', () => {
    expect(canAccess('user', 'admin')).toBe(false);
  });
});
