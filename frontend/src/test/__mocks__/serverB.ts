export function mockServerB() {
  global.fetch = (input: RequestInfo, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input.url;
    if (url.endsWith('/api/auth/login')) {
      return Promise.resolve(
        new Response(
          JSON.stringify({ access_token: 'mock-token', role: 'admin' }),
          { status: 200 }
        )
      );
    }
    if (url.endsWith('/api/messages')) {
      return Promise.resolve(
        new Response(
          JSON.stringify([
            { id: '1', content: 'hello', status: 'sent' },
          ]),
          { status: 200 }
        )
      );
    }
    if (url.includes('/api/messages/')) {
      return Promise.resolve(
        new Response(
          JSON.stringify({ id: '1', content: 'hello', status: 'sent' }),
          { status: 200 }
        )
      );
    }
    if (url.endsWith('/api/users')) {
      return Promise.resolve(
        new Response(
          JSON.stringify([
            {
              id: 1,
              name: 'Admin',
              username: 'admin',
              daily_quota: 100,
              api_key: 'key',
              note: '',
              active: true,
            },
          ]),
          { status: 200 }
        )
      );
    }
    if (url.includes('/api/users/') && url.endsWith('/password')) {
      return Promise.resolve(new Response('{}', { status: 200 }));
    }
    return Promise.reject(new Error('Unknown endpoint: ' + url));
  };
}
