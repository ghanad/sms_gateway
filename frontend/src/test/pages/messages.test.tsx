import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';
import MessagesList from '../../pages/MessagesList';
import { AuthProvider } from '../../hooks/useAuth';
import { mockServerB } from '../__mocks__/serverB';

mockServerB();

describe('Messages List', () => {
  it('renders messages', async () => {
    render(
      <AuthProvider>
        <BrowserRouter>
          <MessagesList />
        </BrowserRouter>
      </AuthProvider>
    );
    expect(await screen.findByText('hello')).toBeInTheDocument();
  });
});
