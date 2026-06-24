import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { TopBarProvider } from '../../components/layout/top-bar-context';
import MonitorDetailPage from './[id]/page-view';
import NewMonitorPage from './new/page-view';

const pushMock = vi.fn();
const apiMock = vi.hoisted(() => ({
  create: vi.fn(),
  get: vi.fn(),
  remove: vi.fn(),
  runNow: vi.fn(),
  update: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  usePathname: () => '/monitors',
  useRouter: () => ({ push: pushMock }),
}));

vi.mock('../../lib/api', () => ({
  monitorsApi: apiMock,
}));

vi.mock('../../components/monitors/monitor-form', () => ({
  MonitorForm: ({
    onSubmit,
  }: {
    onSubmit: (payload: Record<string, unknown>) => Promise<void>;
  }) => (
    <button onClick={() => void onSubmit({ name: 'Price watch', urls: ['https://example.com'] })}>
      Submit monitor
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
      <button onClick={onRunNow}>Run monitor</button>
      <button onClick={() => void onUpdateStatus('paused')}>Pause monitor</button>
      <button onClick={() => void onSave({ name: 'Updated monitor' })}>Save monitor</button>
      <button onClick={() => void onDelete()}>Delete monitor</button>
    </div>
  ),
}));

vi.mock('../../components/monitors/monitor-detail-tabs', () => ({
  MonitorDetailTabs: () => <div>Monitor tabs</div>,
}));

vi.mock('../../components/monitors/monitor-skeleton', () => ({
  MonitorDetailSkeleton: () => <div>Loading monitor</div>,
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

const monitor = {
  id: 7,
  name: 'Price watch',
  status: 'active',
  priority: 'medium',
  schedule_interval_hours: 24,
  retention_days: 30,
  tracked_fields: ['price'],
  settings: {},
  created_at: '2026-06-01T00:00:00Z',
  updated_at: '2026-06-01T00:00:00Z',
};

describe('monitor workflows', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMock.get.mockResolvedValue(monitor);
    apiMock.update.mockResolvedValue(monitor);
    apiMock.remove.mockResolvedValue(undefined);
    apiMock.runNow.mockResolvedValue({ run_id: 55, dispatched_at: '', url_count: 1 });
  });

  it('creates a monitor and navigates to its detail page', async () => {
    apiMock.create.mockResolvedValue({ ...monitor, id: 9 });
    render(wrapper(<NewMonitorPage />));

    fireEvent.click(screen.getByRole('button', { name: 'Submit monitor' }));

    await waitFor(() => {
      expect(apiMock.create).toHaveBeenCalledWith({
        name: 'Price watch',
        urls: ['https://example.com'],
      });
      expect(pushMock).toHaveBeenCalledWith('/monitors/9');
    });
  });

  it('runs, updates, saves, and deletes a monitor with the expected API calls', async () => {
    render(wrapper(<MonitorDetailPage params={{ id: '7' }} />));
    expect(await screen.findByText('Monitor tabs')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Run monitor' }));
    expect(await screen.findByText('Run dispatched · run_id: 55')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Pause monitor' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save monitor' }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete monitor' }));

    await waitFor(() => {
      expect(apiMock.update).toHaveBeenCalledWith('7', { status: 'paused' });
      expect(apiMock.update).toHaveBeenCalledWith('7', { name: 'Updated monitor' });
      expect(apiMock.remove).toHaveBeenCalledWith('7');
      expect(pushMock).toHaveBeenCalledWith('/monitors');
    });
  });

  it('surfaces run failures without losing the detail view', async () => {
    apiMock.runNow.mockRejectedValue(new Error('Dispatch unavailable'));
    render(wrapper(<MonitorDetailPage params={{ id: '7' }} />));
    expect(await screen.findByText('Monitor tabs')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Run monitor' }));

    expect(await screen.findByText('Dispatch unavailable')).toBeInTheDocument();
    expect(screen.getByText('Monitor tabs')).toBeInTheDocument();
  });
});
