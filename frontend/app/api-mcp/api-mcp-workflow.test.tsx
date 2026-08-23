import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ApiMcpPage from './page-view';

const apiMock = vi.hoisted(() => ({
  createApiKey: vi.fn(),
  listApiKeys: vi.fn(),
  revokeApiKey: vi.fn(),
}));

vi.mock('../../lib/api', () => ({
  api: apiMock,
  getPublicApiBaseUrl: () => 'https://api.example.com/api/v1',
}));

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <ApiMcpPage />
    </QueryClientProvider>,
  );
}

const existingKey = {
  id: 7,
  name: 'Production client',
  key_prefix: 'cai_existing',
  is_active: true,
  last_used_at: null,
  created_at: '2026-08-23T16:55:00Z',
};

describe('API and MCP workflow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMock.listApiKeys.mockResolvedValue([existingKey]);
    apiMock.revokeApiKey.mockResolvedValue(undefined);
    apiMock.createApiKey.mockResolvedValue({
      ...existingKey,
      id: 8,
      name: 'Local MCP',
      key_prefix: 'cai_secret_',
      api_key: 'cai_secret_once',
    });
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  it('lists, creates, copies, and revokes API keys', async () => {
    renderPage();

    expect(await screen.findByText('Production client')).toBeInTheDocument();
    expect(screen.getByText('Never')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/key name/i), { target: { value: ' Local MCP ' } });
    fireEvent.click(screen.getByRole('button', { name: /create key/i }));

    const secret = await screen.findByText('cai_secret_once');
    expect(apiMock.createApiKey.mock.calls[0]?.[0]).toBe('Local MCP');
    const secretCard = secret.closest('section');
    expect(secretCard).not.toBeNull();
    fireEvent.click(within(secretCard as HTMLElement).getByRole('button', { name: 'Copy' }));
    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith('cai_secret_once');
    });

    fireEvent.click(screen.getByRole('button', { name: 'Revoke' }));
    await waitFor(() => {
      expect(apiMock.revokeApiKey.mock.calls[0]?.[0]).toBe(7);
    });
  });

  it('shows working REST and MCP quick starts', async () => {
    renderPage();

    await screen.findByText('Production client');
    expect(
      screen.getByText(
        'curl -H "Authorization: Bearer <YOUR_API_KEY>" "https://api.example.com/api/v1/capabilities"',
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/app\.mcp_server\.server/)).toBeInTheDocument();
    expect(screen.getAllByText(/INVORO_API_KEY/)).toHaveLength(1);
  });
});
