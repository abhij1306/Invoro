'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { Trash2 } from 'lucide-react';

import { api } from '../../lib/api';
import { httpErrorStatus } from '../../lib/api/client';
import { awsDemoMode } from '../../lib/config/demo-mode';
import { trapFocus } from '../../lib/focus-trap';
import { getAuthSessionQueryOptions, isAuthRoute } from './auth-session-query';
import { Button } from '../ui/button';
import { ConfirmDialog } from '../ui/confirm-dialog';
import type { TopBarState } from './top-bar-context';
import { TopBarProvider, useTopBarHeader } from './top-bar-context';
import { ThemeToggle } from '../ui/theme-toggle';
import { LogoMark } from './logo-mark';
import { Sidebar, SidebarSkeletonNavigation } from './sidebar';
import { NotificationMenu } from './notification-menu';
import './app-shell.module.css';
import './auth-shell.module.css';

const metricSkeletonKeys = ['metric-crawls', 'metric-records', 'metric-domains', 'metric-health'];

const resetDialogCopy = {
  title: 'Reset workspace data',
  description:
    'Delete crawl runs, records, logs, artifacts, runtime cookie files, learned domain memory, saved cookie memory, field feedback, host protection memory, Product Intelligence data, and Data Enrichment data.',
  confirmLabel: 'Reset Workspace Data',
} as const;

const resetForbiddenMessage =
  'The API refused reset (admin-only on an older backend build, or a stale session). Stop and restart the FastAPI server so it loads the latest code, then try again, or sign out and sign back in.';

export function AppShell({ children }: Readonly<{ children: ReactNode }>) {
  const pathname = usePathname();
  const router = useRouter();
  const authRoute = isAuthRoute(pathname);

  const authQuery = useQuery(getAuthSessionQueryOptions(pathname));

  useEffect(() => {
    if (!authRoute && authQuery.error && httpErrorStatus(authQuery.error) === 401) {
      router.replace('/login');
    }
  }, [authQuery.error, authRoute, router]);

  if (authRoute) {
    return <AuthShell>{children}</AuthShell>;
  }

  if (authQuery.isPending) {
    return (
      <div className="app-shell-root">
        <div className="app-shell-grid">
          <aside className="app-sidebar">
            <div className="app-sidebar-header">
              <LogoMark />
            </div>
            <div className="app-sidebar-nav">
              <SidebarSkeletonNavigation />
            </div>
          </aside>
          <div className="app-main-col">
            <div className="app-topbar">
              <div className="skeleton h-4 w-36" />
            </div>
            <main className="app-page-frame">
              <div className="app-page-inner page-stack-lg">
                <div className="grid grid-cols-4 gap-3">
                  {metricSkeletonKeys.map((key) => (
                    <div
                      key={key}
                      className="border-border card-gradient space-y-3 rounded-lg border p-4"
                    >
                      <div className="skeleton h-3 w-20" />
                      <div className="skeleton h-8 w-28" />
                    </div>
                  ))}
                </div>
                <div className="skeleton h-72 w-full rounded-lg" />
              </div>
            </main>
          </div>
        </div>
      </div>
    );
  }

  if (authQuery.error && httpErrorStatus(authQuery.error) === 401) {
    return (
      <div className="app-shell-feedback">
        <div className="border-border card-gradient max-w-sm rounded-lg border p-6 text-center">
          <p className="type-subheading">Session expired</p>
          <p className="text-secondary mt-1.5 text-sm leading-relaxed">Redirecting to login…</p>
        </div>
      </div>
    );
  }

  if (authQuery.error) {
    return (
      <div className="app-shell-feedback">
        <div className="border-border card-gradient max-w-sm rounded-lg border p-6 text-center">
          <p className="type-subheading">Unable to load session</p>
          <p className="text-secondary mt-1.5 text-sm leading-relaxed">
            Refresh to retry, or sign in again if the session expired.
          </p>
          <div className="mt-4 flex justify-center">
            <ThemeToggle compact />
          </div>
        </div>
      </div>
    );
  }

  return (
    <TopBarProvider>
      <div className="app-shell-root">
        <a
          href="#main-content"
          className="ui-on-accent-surface focus:bg-accent sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:rounded-md focus:px-3 focus:py-2 focus:text-sm"
        >
          Skip to main content
        </a>
        <div className="app-shell-grid">
          <Sidebar pathname={pathname} user={authQuery.data} />
          <ShellContent pathname={pathname} canResetWorkspace={authQuery.data?.role === 'admin'}>
            {children}
          </ShellContent>
        </div>
      </div>
    </TopBarProvider>
  );
}

function AuthShell({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className="auth-shell">
      <div className="auth-shell-card">
        <div className="auth-shell-header">
          <div className="auth-shell-brand">
            <LogoMark auth />
          </div>
          <ThemeToggle compact />
        </div>
        {children}
      </div>
    </div>
  );
}

function ShellContent({
  children,
  pathname,
  canResetWorkspace,
}: Readonly<{ children: ReactNode; pathname: string; canResetWorkspace: boolean }>) {
  const header = useTopBarHeader();
  const topBar = header?.pathKey === pathname ? header : getFallbackHeader(pathname);
  const router = useRouter();
  const queryClient = useQueryClient();
  const [resetPending, setResetPending] = useState(false);
  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const [resetError, setResetError] = useState('');
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const resetTriggerRef = useRef<HTMLButtonElement | null>(null);
  const resetDialogRef = useRef<HTMLDialogElement | null>(null);
  const resetConfirmRef = useRef<HTMLButtonElement | null>(null);
  const resetPreviousFocusRef = useRef<HTMLElement | null>(null);
  const resetPendingRef = useRef(resetPending);
  const notificationCountQuery = useQuery({
    queryKey: ['notifications-unread-count'],
    queryFn: api.notificationUnreadCount,
    staleTime: 30_000,
    enabled: !awsDemoMode,
  });
  const notificationsQuery = useQuery({
    queryKey: ['notifications-unread'],
    queryFn: () => api.listNotifications({ limit: 10 }),
    enabled: notificationsOpen && !awsDemoMode,
  });
  const markReadMutation = useMutation({
    mutationFn: api.markNotificationRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-unread'] });
    },
  });

  useEffect(() => {
    resetPendingRef.current = resetPending;
  }, [resetPending]);

  useEffect(() => {
    if (!resetDialogOpen) {
      return;
    }
    const previousFocusRef = resetPreviousFocusRef;
    const resetTrigger = resetTriggerRef.current;
    const previousFocus = previousFocusRef.current;
    const previousOverflow = document.body.style.overflow;
    const previousTouchAction = document.body.style.touchAction;
    document.body.style.overflow = 'hidden';
    document.body.style.touchAction = 'none';
    const frame = window.requestAnimationFrame(() => resetConfirmRef.current?.focus());
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        if (resetPendingRef.current) {
          return;
        }
        event.preventDefault();
        setResetDialogOpen(false);
        return;
      }
      trapFocus(event, resetDialogRef.current);
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = previousOverflow;
      document.body.style.touchAction = previousTouchAction;
      const restoreTarget = previousFocus?.isConnected ? previousFocus : resetTrigger;
      restoreTarget?.focus();
      previousFocusRef.current = null;
    };
  }, [resetDialogOpen]);

  async function executeReset() {
    if (!canResetWorkspace) return;
    setResetPending(true);
    setResetError('');
    try {
      await api.resetApplicationData();
      globalThis.location.reload();
    } catch (error) {
      const status = httpErrorStatus(error);
      if (status === 401) {
        router.replace('/login');
        return;
      }
      if (status === 403) {
        setResetError(resetForbiddenMessage);
        return;
      }
      setResetError(error instanceof Error ? error.message : 'Failed to reset workspace data.');
    } finally {
      setResetPending(false);
    }
  }

  function handleSelectedReset() {
    if (!canResetWorkspace) return;
    setResetError('');
    resetPreviousFocusRef.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : resetTriggerRef.current;
    setResetDialogOpen(true);
  }

  const resetLabel = resetPending ? 'Resetting Workspace…' : 'Reset Workspace';

  return (
    <div className="app-main-col">
      <header className="app-topbar">
        <div className="app-topbar-main">
          <h1 className="app-topbar-title">{topBar.title}</h1>
        </div>
        <div className="app-topbar-actions">
          {topBar.actions ? (
            <div className="flex flex-wrap items-center gap-2">{topBar.actions}</div>
          ) : null}
          {canResetWorkspace ? (
            <div className="flex items-center gap-2">
              <Button
                ref={resetTriggerRef}
                type="button"
                onClick={handleSelectedReset}
                disabled={resetPending}
                variant="destructive"
                size="sm"
              >
                <Trash2 className="size-3" />
                {resetLabel}
              </Button>
            </div>
          ) : null}
          <ThemeToggle compact />
          {!awsDemoMode ? (
            <NotificationMenu
              open={notificationsOpen}
              count={notificationCountQuery.data?.count ?? 0}
              pending={notificationsQuery.isPending}
              items={notificationsQuery.data ?? []}
              onToggle={() => setNotificationsOpen((value) => !value)}
              onClose={() => setNotificationsOpen(false)}
              onRead={(id) => markReadMutation.mutate(id)}
            />
          ) : null}
        </div>
      </header>

      <main id="main-content" className="app-page-frame">
        <div className="app-page-inner">{children}</div>
      </main>
      {canResetWorkspace && resetDialogOpen ? (
        <ConfirmDialog
          dialogRef={resetDialogRef}
          confirmRef={resetConfirmRef}
          titleId="reset-workspace-title"
          descriptionId="reset-workspace-description"
          title={resetDialogCopy.title}
          description={resetDialogCopy.description}
          error={resetError}
          pending={resetPending}
          pendingLabel="Working…"
          confirmLabel={resetDialogCopy.confirmLabel}
          overlayClassName="overlay-scrim fixed inset-0 z-[100] grid place-items-center p-4"
          onCancel={() => setResetDialogOpen(false)}
          onConfirm={() => void executeReset()}
        />
      ) : null}
    </div>
  );
}

function getFallbackHeader(pathname: string): TopBarState {
  if (pathname.startsWith('/dashboard'))
    return {
      title: 'Dashboard',
      description: 'Overview of crawler activity across your workspace.',
    };
  if (pathname.startsWith('/crawl'))
    return {
      title: 'Crawl Studio',
      description: 'Configure sources, run jobs, and monitor execution.',
    };
  if (pathname.startsWith('/playground'))
    return {
      title: 'Playground',
      description:
        'Explore any domain — discover, extract, enrich, compare, and monitor from one place.',
    };
  if (pathname.startsWith('/data-enrichment'))
    return {
      title: 'Data Enrichment',
      description: 'Normalize ecommerce detail records into discovery fields.',
    };
  if (pathname.startsWith('/monitors'))
    return {
      title: 'Monitors',
      description: 'Schedule recurring crawls and inspect changes.',
    };
  if (pathname.startsWith('/alerts'))
    return {
      title: 'Product Alerts',
      description: 'Track single-product price and availability deltas.',
    };
  if (pathname.startsWith('/product-intelligence'))
    return {
      title: 'Product Intelligence',
      description: 'Find matching product pages and compare prices.',
    };
  if (pathname.startsWith('/runs/'))
    return {
      title: 'Run Details',
      description: 'Inspect a crawl run, logs, and extracted output.',
    };
  if (pathname.startsWith('/runs'))
    return { title: 'Run History', description: 'Review and manage previously submitted crawls.' };
  if (pathname.startsWith('/selectors/manage'))
    return {
      title: 'Domain Memory',
      description: 'Inspect learned selectors and saved run profiles by domain and surface.',
    };
  if (pathname.startsWith('/selectors'))
    return { title: 'Selector Tool', description: 'Suggest, test, and validate field selectors.' };
  if (pathname.startsWith('/admin/users'))
    return { title: 'Users', description: 'Manage workspace access and roles.' };
  if (pathname.startsWith('/admin/llm'))
    return { title: 'LLM Config', description: 'Control provider settings and prompts.' };
  if (pathname.startsWith('/jobs'))
    return { title: 'Jobs', description: 'Review worker activity and queued work.' };
  return { title: 'Invoro' };
}
