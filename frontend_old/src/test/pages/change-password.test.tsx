import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';
import ChangePassword from '../../pages/ChangePassword';
import { AuthProvider } from '../../hooks/useAuth';
import { mockServerB } from '../__mocks__/serverB';

mockServerB();

describe('ChangePassword', () => {
  it('renders change password form', async () => {
    localStorage.setItem('user', 'admin');
    localStorage.setItem('token', 'mock');
    render(
      <AuthProvider>
        <BrowserRouter>
          <ChangePassword />
        </BrowserRouter>
      </AuthProvider>
    );
    expect(await screen.findByText('Change Password')).toBeInTheDocument();
  });
});
