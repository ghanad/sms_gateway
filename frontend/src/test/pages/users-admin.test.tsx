import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import UsersAdmin from '../../pages/UsersAdmin';
import { AuthProvider } from '../../hooks/useAuth';

describe('Users admin page', () => {
  afterEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('denies non-admin', () => {
    localStorage.setItem('auth', JSON.stringify({ token: 't', role: 'user' }));
    render(
      <MemoryRouter>
        <AuthProvider>
          <UsersAdmin />
        </AuthProvider>
      </MemoryRouter>
    );
    expect(screen.getByText(/access denied/i)).toBeInTheDocument();
  });

  it('shows users for admin', async () => {
    localStorage.setItem('auth', JSON.stringify({ token: 't', role: 'admin' }));
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => [{ username: 'a', role: 'admin' }]
    } as any);
    render(
      <MemoryRouter>
        <AuthProvider>
          <UsersAdmin />
        </AuthProvider>
      </MemoryRouter>
    );
    expect(await screen.findByText('a')).toBeInTheDocument();
  });
});
