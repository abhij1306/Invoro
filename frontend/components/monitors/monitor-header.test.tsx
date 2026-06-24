import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { MonitorJob } from '../../lib/api/types';
import { MonitorHeader } from './monitor-header';

const monitor: MonitorJob = {
  id: 1,
  name: 'Widget watch',
  urls: ['https://example.com/products/widget'],
  domains: ['example.com'],
  surface: 'ecommerce_detail',
  tracked_fields: ['price'],
  schedule_interval_hours: 1,
  priority: 'background',
  retention_days: 30,
  status: 'active',
  settings: {},
  condition: null,
  webhook_url: null,
  poll_interval_seconds: null,
  last_known_values: {},
  last_checked_at: null,
  consecutive_failure_count: 0,
  last_error: null,
  last_crawl_method: null,
  last_run_at: null,
  next_run_at: null,
  created_at: '2026-05-21T00:00:00Z',
  updated_at: '2026-05-21T00:00:00Z',
};

describe('MonitorHeader', () => {
  it('wires the delete dialog description for screen readers', async () => {
    render(
      <MonitorHeader
        monitor={monitor}
        runPending={false}
        runError=""
        onRunNow={vi.fn()}
        onUpdateStatus={vi.fn().mockResolvedValue(undefined)}
        onDelete={vi.fn().mockResolvedValue(undefined)}
        onSave={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /more actions/i }));
    fireEvent.click(screen.getByRole('button', { name: /delete/i }));

    const dialog = await screen.findByRole('dialog', { name: /delete this monitor/i });
    expect(dialog).toHaveAttribute('aria-describedby', 'monitor-delete-description');
    expect(screen.getByText(/this permanently deletes the monitor/i)).toHaveAttribute(
      'id',
      'monitor-delete-description',
    );
  });
});
