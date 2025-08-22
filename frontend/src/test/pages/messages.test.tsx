import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import MessagesList from '../../pages/MessagesList';
import { AuthProvider } from '../../hooks/useAuth';

describe('Messages page', () => {
  beforeEach(() => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => [
        { id: '1', to: '+1', status: 'sent', created: new Date().toISOString() }
      ]
    } as any);
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });
  it('renders list of messages', async () => {
    render(
      <MemoryRouter>
        <AuthProvider>
          <MessagesList />
        </AuthProvider>
      </MemoryRouter>
    );
    expect(await screen.findByText('1')).toBeInTheDocument();
  });
});
