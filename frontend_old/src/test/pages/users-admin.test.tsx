import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';
import UsersAdmin from '../../pages/UsersAdmin';
import { AuthProvider } from '../../hooks/useAuth';
import { mockServerB } from '../__mocks__/serverB';

mockServerB();

describe('Users Admin', () => {
  it('renders user list', async () => {
    render(
      <AuthProvider>
        <BrowserRouter>
          <UsersAdmin />
        </BrowserRouter>
      </AuthProvider>
    );
    expect((await screen.findAllByText('admin')).length).toBeGreaterThan(0);
  });
});
