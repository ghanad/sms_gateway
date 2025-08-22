import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Login from '../../pages/Login';
import { AuthProvider } from '../../hooks/useAuth';
import * as authApi from '../../api/auth';

describe('Login page', () => {
  it('submits credentials', async () => {
    const spy = vi.spyOn(authApi, 'login').mockResolvedValue({ access_token: 't', role: 'admin' });
    render(
      <MemoryRouter>
        <AuthProvider>
          <Login />
        </AuthProvider>
      </MemoryRouter>
    );
    fireEvent.change(screen.getByPlaceholderText(/username/i), { target: { value: 'admin' } });
    fireEvent.change(screen.getByPlaceholderText(/password/i), { target: { value: 'pw' } });
    fireEvent.click(screen.getByText(/login/i));
    await screen.findByText(/login/i);
    expect(spy).toHaveBeenCalledWith('admin', 'pw');
  });
});
