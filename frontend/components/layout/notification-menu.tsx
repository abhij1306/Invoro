'use client';

import { Bell, Check } from 'lucide-react';
import type { Route } from 'next';
import Link from 'next/link';

import { formatRelativeTime } from '../../lib/format/date';

type NotificationItem = {
  id: number;
  monitor_id: number;
  message: string;
  created_at: string;
};

export function NotificationMenu({
  open,
  count,
  pending,
  items,
  onToggle,
  onClose,
  onRead,
}: {
  open: boolean;
  count: number;
  pending: boolean;
  items: NotificationItem[];
  onToggle: () => void;
  onClose: () => void;
  onRead: (id: number) => void;
}) {
  return (
    <div className="relative">
      <button
        type="button"
        className="app-icon-button relative"
        aria-label="Notifications"
        onClick={onToggle}
      >
        <Bell className="size-3.5" />
        {count > 0 ? (
          <span className="bg-danger absolute -top-1 -right-1 min-w-4 rounded-full px-1 text-center text-xs leading-4 font-semibold text-white">
            {count}
          </span>
        ) : null}
      </button>
      {open ? (
        <div className="border-border bg-background-elevated absolute top-9 right-0 z-[250] w-[min(340px,calc(100vw-32px))] rounded-lg border p-2 shadow-lg">
          <div className="border-divider flex items-center justify-between border-b px-2 py-1.5">
            <p className="type-label m-0">Notifications</p>
            <span className="type-caption">{count} unread</span>
          </div>
          <div className="max-h-80 overflow-y-auto py-1">
            <NotificationItems {...{ pending, items, onClose, onRead }} />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function NotificationItems({
  pending,
  items,
  onClose,
  onRead,
}: {
  pending: boolean;
  items: NotificationItem[];
  onClose: () => void;
  onRead: (id: number) => void;
}) {
  if (pending) {
    return (
      <div className="space-y-2 p-2">
        <div className="skeleton h-12 w-full" />
        <div className="skeleton h-12 w-full" />
      </div>
    );
  }
  if (!items.length) {
    return <p className="text-muted m-0 px-2 py-4 text-center text-sm">No unread notifications.</p>;
  }
  return items.map((item) => (
    <div key={item.id} className="hover:bg-background-alt flex items-start gap-2 rounded-md p-2">
      <Link
        href={`/monitors/${item.monitor_id}` as Route}
        className="min-w-0 flex-1"
        onClick={onClose}
      >
        <p className="text-foreground m-0 truncate text-sm font-medium">{item.message}</p>
        <p className="type-caption m-0">{formatRelativeTime(item.created_at)}</p>
      </Link>
      <button
        type="button"
        className="app-icon-button"
        aria-label="Mark notification read"
        onClick={() => onRead(item.id)}
      >
        <Check className="size-3.5" />
      </button>
    </div>
  ));
}
