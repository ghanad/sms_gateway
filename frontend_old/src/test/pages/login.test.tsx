import { render, screen, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';
import Login from '../../pages/Login';
import { AuthProvider } from '../../hooks/useAuth';
import { mockServerB } from '../__mocks__/serverB';

mockServerB();

describe('Login Page', () => {
  it('logs in user', async () => {
    render(
      <AuthProvider>
        <BrowserRouter>
          <Login />
        </BrowserRouter>
      </AuthProvider>
    );
    fireEvent.change(screen.getByPlaceholderText(/email/i), {
      target: { value: 'admin' },
    });
    fireEvent.change(screen.getByPlaceholderText(/password/i), {
      target: { value: 'pass' },
    });
    fireEvent.click(screen.getByText(/log in/i));
    // since login sets localStorage, check token
    await screen.findByText(/log in/i);
    expect(localStorage.getItem('token')).toBe('mock-token');
  });
});
