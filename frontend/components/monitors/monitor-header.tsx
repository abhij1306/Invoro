'use client';

import * as DialogPrimitive from '@radix-ui/react-dialog';
import {
  ArrowLeft,
  MoreHorizontal,
  Pause,
  Play,
  RotateCw,
  Settings,
  Trash2,
  X,
} from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';

import type {
  MonitorJob,
  MonitorStatus,
  MonitorUpdatePayload,
  AlertCreatePayload,
  AlertUpdatePayload,
} from '../../lib/api/types';
import { formatNextRun, formatRelativeTime } from '../../lib/format/date';
import { formatSeconds } from '../../lib/format/time';
import { cn } from '../../lib/utils';
import { Button } from '../ui/primitives';
import { ConfirmDialog } from '../ui/dialog';
import { KVTile } from '../ui/patterns';
import { MonitorForm } from './monitor-form';
import { MonitorPriorityBadge, MonitorStatusBadge } from './monitor-badges';
import { AlertForm } from './alert-form';

type MonitorHeaderProps = Readonly<{
  monitor: MonitorJob;
  runPending: boolean;
  runError: string;
  onRunNow: () => void;
  onUpdateStatus: (status: MonitorStatus) => Promise<void>;
  onDelete: () => Promise<void>;
  onSave: (
    payload: MonitorUpdatePayload | AlertCreatePayload | AlertUpdatePayload,
  ) => Promise<void>;
}>;

export function MonitorHeader({
  monitor,
  runPending,
  runError,
  onRunNow,
  onUpdateStatus,
  onDelete,
  onSave,
}: MonitorHeaderProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [statusPending, setStatusPending] = useState(false);
  const [deletePending, setDeletePending] = useState(false);
  const active = monitor.status === 'active';
  const isAlert = Boolean(monitor.poll_interval_seconds);
  const parentHref = isAlert ? '/alerts' : '/monitors';
  const parentLabel = isAlert ? 'Product Alerts' : 'Monitors';
  const visibleDomains = monitor.domains.slice(0, 3).join(', ');
  const hiddenDomains = Math.max(0, monitor.domains.length - 3);

  async function updateStatus(status: MonitorStatus) {
    setStatusPending(true);
    try {
      await onUpdateStatus(status);
    } finally {
      setStatusPending(false);
    }
  }

  async function remove() {
    setDeletePending(true);
    try {
      await onDelete();
      setDeleteOpen(false);
    } finally {
      setDeletePending(false);
    }
  }

  return (
    <div className="border-border card-gradient rounded-[var(--radius-lg)] border p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 space-y-2">
          <Link
            href={parentHref}
            className="text-muted hover:text-foreground type-caption inline-flex items-center gap-1"
          >
            <ArrowLeft className="size-3.5" />
            {parentLabel}
          </Link>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="type-heading-2 m-0 truncate">
              {isAlert ? monitor.urls[0] : monitor.name}
            </h2>
            <MonitorStatusBadge status={monitor.status} />
            <MonitorPriorityBadge priority={monitor.priority} />
          </div>
          <p className="text-secondary type-body-sm">
            every{' '}
            {isAlert
              ? formatSeconds(monitor.poll_interval_seconds ?? 0)
              : `${monitor.schedule_interval_hours}h`}{' '}
            · {monitor.urls.length} URL
            {monitor.urls.length === 1 ? '' : 's'} · {visibleDomains}
            {hiddenDomains ? ` +${hiddenDomains}` : ''}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant="neutral"
            disabled={statusPending}
            onClick={() => void updateStatus(active ? 'paused' : 'active')}
          >
            {active ? <Pause className="size-3.5" /> : <Play className="size-3.5" />}
            {active ? 'Pause' : 'Resume'}
          </Button>
          <Button type="button" variant="neutral" onClick={() => setEditOpen(true)}>
            <Settings className="size-3.5" />
            Edit
          </Button>
          <Button type="button" onClick={onRunNow} disabled={runPending}>
            <RotateCw className={cn('size-3.5', runPending && 'animate-spin')} />
            {runPending ? 'Running...' : 'Run Now'}
          </Button>
          <div className="relative">
            <Button
              type="button"
              variant="quiet"
              size="icon"
              aria-label="More actions"
              onClick={() => setMenuOpen((value) => !value)}
            >
              <MoreHorizontal className="size-4" />
            </Button>
            {menuOpen ? (
              <div className="border-border bg-background-elevated shadow-card absolute right-0 z-20 mt-1 w-36 rounded-[var(--radius-md)] border py-1">
                <button
                  type="button"
                  onClick={() => {
                    setMenuOpen(false);
                    setDeleteOpen(true);
                  }}
                  className="text-danger hover:bg-danger-bg flex w-full items-center gap-2 px-3 py-2 text-sm"
                >
                  <Trash2 className="size-3.5" />
                  Delete
                </button>
              </div>
            ) : null}
          </div>
        </div>
      </div>
      {runError ? <p className="text-danger type-caption mt-3">{runError}</p> : null}
      <div className="mt-5 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <KVTile
          label={isAlert ? 'Last Checked' : 'Last Run'}
          value={formatRelativeTime(isAlert ? monitor.last_checked_at : monitor.last_run_at)}
        />
        <KVTile label="Next Run" value={formatNextRun(monitor.next_run_at)} />
        <KVTile label="Tracked" value={monitor.tracked_fields.join(', ')} />
        <KVTile
          label={isAlert ? 'Condition' : 'Retention'}
          value={isAlert ? monitor.condition || 'Any delta' : `${monitor.retention_days} days`}
        />
      </div>
      <DialogPrimitive.Root open={editOpen} onOpenChange={setEditOpen}>
        <DialogPrimitive.Portal>
          <DialogPrimitive.Overlay className="fixed inset-0 z-[100] bg-[color-mix(in_srgb,var(--bg-base)_34%,black)]" />
          <DialogPrimitive.Content className="border-border bg-background shadow-card fixed top-0 right-0 z-[101] h-dvh w-[min(560px,100vw)] overflow-y-auto border-l p-5">
            <div className="mb-5 flex items-center justify-between gap-4">
              <DialogPrimitive.Title className="type-heading-3">
                Edit {isAlert ? 'alert' : 'monitor'}
              </DialogPrimitive.Title>
              <DialogPrimitive.Close asChild>
                <Button type="button" variant="quiet" size="icon" aria-label="Close">
                  <X className="size-4" />
                </Button>
              </DialogPrimitive.Close>
            </div>
            {isAlert ? (
              <AlertForm
                initial={monitor}
                submitLabel="Save Changes"
                onCancel={() => setEditOpen(false)}
                onSubmit={async (payload) => {
                  await onSave(payload);
                  setEditOpen(false);
                }}
              />
            ) : (
              <MonitorForm
                initial={monitor}
                submitLabel="Save Changes"
                onCancel={() => setEditOpen(false)}
                onSubmit={async (payload) => {
                  await onSave(payload);
                  setEditOpen(false);
                }}
              />
            )}
          </DialogPrimitive.Content>
        </DialogPrimitive.Portal>
      </DialogPrimitive.Root>
      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title={`Delete this ${isAlert ? 'alert' : 'monitor'}?`}
        description={`This permanently deletes the ${isAlert ? 'alert' : 'monitor'}, its snapshots, events, URL state, and notifications.`}
        confirmLabel={`Delete ${isAlert ? 'Alert' : 'Monitor'}`}
        pending={deletePending}
        danger
        onConfirm={() => void remove()}
      />
    </div>
  );
}
