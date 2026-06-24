import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { TopBarProvider } from '../../components/layout/top-bar-context';
import AlertDetailPage from './[id]/page-view';
import NewAlertPage from './new/page-view';

const pushMock = vi.fn();
const apiMock = vi.hoisted(() => ({
  create: vi.fn(),
  get: vi.fn(),
  remove: vi.fn(),
  test: vi.fn(),
  update: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  usePathname: () => '/alerts',
  useRouter: () => ({ push: pushMock }),
}));

vi.mock('../../lib/api', () => ({
  alertsApi: apiMock,
}));

vi.mock('./alert-helpers', () => ({
  alertToMonitor: (alert: Record<string, unknown>) => alert,
}));

vi.mock('../../components/monitors/alert-form', () => ({
  AlertForm: ({ onSubmit }: { onSubmit: (payload: Record<string, unknown>) => Promise<void> }) => (
    <button onClick={() => void onSubmit({ name: 'Low stock', poll_interval_seconds: 300 })}>
      Submit alert
    </button>
  ),
}));

vi.mock('../../components/monitors/monitor-header', () => ({
  MonitorHeader: ({
    onDelete,
    onRunNow,
    onSave,
    onUpdateStatus,
    runError,
  }: {
    onDelete: () => Promise<void>;
    onRunNow: () => void;
    onSave: (payload: Record<string, unknown>) => Promise<void>;
    onUpdateStatus: (status: string) => Promise<void>;
    runError?: string;
  }) => (
    <div>
      {runError ? <p>{runError}</p> : null}
      <button onClick={onRunNow}>Test alert</button>
      <button onClick={() => void onUpdateStatus('paused')}>Pause alert</button>
      <button onClick={() => void onSave({ name: 'Updated alert' })}>Save alert</button>
      <button onClick={() => void onDelete()}>Delete alert</button>
    </div>
  ),
}));

vi.mock('../../components/monitors/monitor-detail-tabs', () => ({
  MonitorDetailTabs: () => <div>Alert tabs</div>,
}));

vi.mock('../../components/monitors/monitor-skeleton', () => ({
  MonitorDetailSkeleton: () => <div>Loading alert</div>,
}));

function wrapper(children: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return (
    <QueryClientProvider client={client}>
      <TopBarProvider>{children}</TopBarProvider>
    </QueryClientProvider>
  );
}

const alert = {
  id: 11,
  name: 'Low stock',
  status: 'active',
  priority: 'medium',
  schedule_interval_hours: 1,
  retention_days: 30,
  tracked_fields: ['availability'],
  settings: {},
  created_at: '2026-06-01T00:00:00Z',
  updated_at: '2026-06-01T00:00:00Z',
};

describe('alert workflows', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMock.get.mockResolvedValue(alert);
    apiMock.update.mockResolvedValue(alert);
    apiMock.remove.mockResolvedValue(undefined);
    apiMock.test.mockResolvedValue({ run_id: 77, matched: true });
  });

  it('creates an alert and navigates to its detail page', async () => {
    apiMock.create.mockResolvedValue({ ...alert, id: 12 });
    render(wrapper(<NewAlertPage />));

    fireEvent.click(screen.getByRole('button', { name: 'Submit alert' }));

    await waitFor(() => {
      expect(apiMock.create).toHaveBeenCalledWith({
        name: 'Low stock',
        poll_interval_seconds: 300,
      });
      expect(pushMock).toHaveBeenCalledWith('/alerts/12');
    });
  });

  it('tests, updates, saves, and deletes an alert with the expected API calls', async () => {
    render(wrapper(<AlertDetailPage params={{ id: '11' }} />));
    expect(await screen.findByText('Alert tabs')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Test alert' }));
    expect(await screen.findByText('Poll completed · run_id: 77')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Pause alert' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save alert' }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete alert' }));

    await waitFor(() => {
      expect(apiMock.update).toHaveBeenCalledWith('11', { status: 'paused' });
      expect(apiMock.update).toHaveBeenCalledWith('11', { name: 'Updated alert' });
      expect(apiMock.remove).toHaveBeenCalledWith('11');
      expect(pushMock).toHaveBeenCalledWith('/alerts');
    });
  });

  it('surfaces alert poll failures without losing the detail view', async () => {
    apiMock.test.mockRejectedValue(new Error('Poll failed'));
    render(wrapper(<AlertDetailPage params={{ id: '11' }} />));
    expect(await screen.findByText('Alert tabs')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Test alert' }));

    expect(await screen.findByText('Poll failed')).toBeInTheDocument();
    expect(screen.getByText('Alert tabs')).toBeInTheDocument();
  });
});
