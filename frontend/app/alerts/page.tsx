'use client';

import Link from 'next/link';
import type { Route } from 'next';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus } from 'lucide-react';
import { useMemo, useState } from 'react';

import { alertsApi } from '../../lib/api';
import type { MonitorStatus } from '../../lib/api/types';
import { alertToMonitor } from './alert-helpers';
import { Button } from '../../components/ui/primitives';
import { ConfirmDialog } from '../../components/ui/dialog';
import {
  InlineAlert,
  MutedPanelMessage,
  PageHeader,
  SurfacePanel,
  TabBar,
} from '../../components/ui/patterns';
import { MonitorListItem } from '../../components/monitors/monitor-list-item';
import { MonitorListSkeleton } from '../../components/monitors/monitor-skeleton';

const statusOptions: Array<{ value: MonitorStatus | 'all'; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'active', label: 'Active' },
  { value: 'paused', label: 'Paused' },
  { value: 'triggered', label: 'Triggered' },
  { value: 'error', label: 'Error' },
  { value: 'archived', label: 'Archived' },
];

export default function AlertsPage() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<MonitorStatus | 'all'>('all');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [runningId, setRunningId] = useState<number | null>(null);
  const [deleteTargetId, setDeleteTargetId] = useState<number | null>(null);

  const alertsQuery = useQuery({
    queryKey: ['alerts', statusFilter],
    queryFn: () =>
      alertsApi.list({
        status: statusFilter === 'all' ? undefined : statusFilter,
      }),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: MonitorStatus }) =>
      alertsApi.update(id, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['alerts'] }),
    onError: (mutationError) =>
      setError(mutationError instanceof Error ? mutationError.message : 'Alert update failed.'),
  });

  const deleteMutation = useMutation({
    mutationFn: alertsApi.remove,
    onSuccess: async () => {
      setNotice('Alert deleted.');
      setDeleteTargetId(null);
      await queryClient.invalidateQueries({ queryKey: ['alerts'] });
    },
    onError: (mutationError) =>
      setError(mutationError instanceof Error ? mutationError.message : 'Delete failed.'),
  });

  const alerts = useMemo(
    // Alert rows reuse MonitorListItem, so alertToMonitor fills monitor-only UI placeholders.
    // Actual alert cadence comes from poll_interval_seconds, not these stub fields.
    () => (alertsQuery.data ?? []).map(alertToMonitor),
    [alertsQuery.data],
  );

  async function testAlert(id: number) {
    setRunningId(id);
    setError('');
    setNotice('');
    try {
      const response = await alertsApi.test(id);
      setNotice(`Poll completed · run_id: ${response.run_id}`);
      await queryClient.invalidateQueries({ queryKey: ['alerts'] });
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : 'Alert poll failed.');
    } finally {
      setRunningId(null);
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        title="Product Alerts"
        description="Single-product price and availability alerts with optional webhooks."
        actions={
          <Button asChild size="sm">
            <Link href="/alerts/new">
              <Plus className="size-3.5" />
              New Alert
            </Link>
          </Button>
        }
      />
      {notice ? (
        <div className="alert-surface alert-success px-3 py-2 text-sm">{notice}</div>
      ) : null}
      {error ? <InlineAlert message={error} /> : null}
      <SurfacePanel className="overflow-visible">
        <div className="border-divider flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
          <TabBar
            value={statusFilter}
            onChange={(value) => setStatusFilter(value as MonitorStatus | 'all')}
            options={statusOptions}
            compact
          />
        </div>
        {alertsQuery.isPending ? (
          <MonitorListSkeleton />
        ) : alerts.length ? (
          <div className="divide-border divide-y">
            {alerts.map((alert) => (
              <MonitorListItem
                key={alert.id}
                monitor={alert}
                detailHref={`/alerts/${alert.id}` as Route}
                running={runningId === alert.id}
                onRunNow={(id) => void testAlert(id)}
                onPause={(id) => updateMutation.mutate({ id, status: 'paused' })}
                onResume={(id) => updateMutation.mutate({ id, status: 'active' })}
                onDelete={(id) => setDeleteTargetId(id)}
              />
            ))}
          </div>
        ) : (
          <div className="space-y-3 p-4">
            <MutedPanelMessage
              title="No alerts yet"
              description="Create your first alert to track price or availability changes."
            />
            <Button asChild size="sm">
              <Link href="/alerts/new">
                <Plus className="size-3.5" />
                New Alert
              </Link>
            </Button>
          </div>
        )}
      </SurfacePanel>
      <ConfirmDialog
        open={deleteTargetId !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTargetId(null);
        }}
        title="Delete this alert?"
        description="Scheduled checks stop. Existing snapshots, events, and delivery logs remain until retention cleanup."
        confirmLabel="Delete Alert"
        pending={deleteMutation.isPending}
        danger
        error={error || undefined}
        onConfirm={() => {
          if (deleteTargetId !== null) {
            deleteMutation.mutate(deleteTargetId);
          }
        }}
      />
    </div>
  );
}
