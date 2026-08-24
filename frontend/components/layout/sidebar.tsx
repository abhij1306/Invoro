'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { Route } from 'next';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import type { ComponentType, RefObject } from 'react';
import {
  Bell,
  BrainCircuit,
  BriefcaseBusiness,
  ChevronLeft,
  ChevronRight,
  Clock3,
  DatabaseZap,
  FileChartColumn,
  FolderKanban,
  Grid2x2,
  KeyRound,
  LogOut,
  Radar,
  SearchCheck,
  Settings2,
  ShieldCheck,
  WandSparkles,
  X,
} from 'lucide-react';

import { api, monitorsApi } from '../../lib/api';
import type { User } from '../../lib/api/types';
import { STORAGE_KEYS } from '../../lib/constants/storage-keys';
import { awsDemoMode } from '../../lib/config/demo-mode';
import { trapFocus } from '../../lib/focus-trap';
import { cn } from '../../lib/utils';
import { InlineAlert } from '../ui/alert';
import { LogoMark } from './logo-mark';

const navGroups = [
  {
    label: 'Primary',
    items: [
      { href: '/dashboard', label: 'Dashboard', icon: Grid2x2 },
      { href: '/playground', label: 'Playground', icon: FolderKanban },
      { href: '/crawl', label: 'Crawl Studio', icon: WandSparkles },
      { href: '/runs', label: 'History', icon: Clock3 },
      { href: '/jobs', label: 'Jobs', icon: BriefcaseBusiness },
      { href: '/api-mcp', label: 'API & MCP', icon: KeyRound },
    ],
  },
  {
    label: 'Monitoring',
    items: [
      { href: '/monitors', label: 'Monitors', icon: Radar },
      { href: '/alerts', label: 'Product Alerts', icon: Bell },
    ],
  },
  {
    label: 'Intelligence',
    items: [
      { href: '/data-enrichment', label: 'Data Enrichment', icon: FileChartColumn },
      { href: '/product-intelligence', label: 'Product Intelligence', icon: BrainCircuit },
    ],
  },
  {
    label: 'Memory',
    items: [
      { href: '/selectors', label: 'Selector Tool', icon: SearchCheck, exactMatch: true },
      { href: '/selectors/manage', label: 'Domain Memory', icon: DatabaseZap },
    ],
  },
  {
    label: 'Admin',
    items: [
      { href: '/admin/users', label: 'Users', icon: ShieldCheck },
      { href: '/admin/llm', label: 'LLM Config', icon: Settings2 },
    ],
  },
] as const satisfies ReadonlyArray<{
  label: string;
  items: ReadonlyArray<{
    href: string;
    label: string;
    icon: ComponentType<{ className?: string }>;
    exactMatch?: boolean;
  }>;
}>;

const visibleNavGroups = awsDemoMode
  ? navGroups.filter((group) => group.label !== 'Monitoring')
  : navGroups;

const navSkeletonKeys = visibleNavGroups.flatMap((group) =>
  group.items.map((item) => `nav-${item.href}`),
);

export function SidebarSkeletonNavigation() {
  return navSkeletonKeys.map((key) => <div key={key} className="skeleton h-8 w-full rounded-md" />);
}

function isNavItemActive(pathname: string, item: (typeof navGroups)[number]['items'][number]) {
  if ('exactMatch' in item && item.exactMatch) return pathname === item.href;
  return pathname === item.href || pathname.startsWith(`${item.href}/`);
}

function getSidebarTogglePresentation(mobile: boolean, collapsed: boolean) {
  if (mobile) return { label: 'Close navigation', Icon: X };
  if (collapsed) return { label: 'Expand sidebar', Icon: ChevronRight };
  return { label: 'Collapse sidebar', Icon: ChevronLeft };
}

export function Sidebar({
  pathname,
  user,
  mobileOpen,
  mobileMenuTriggerRef,
  onMobileClose,
}: Readonly<{
  pathname: string;
  user: User;
  mobileOpen: boolean;
  mobileMenuTriggerRef: RefObject<HTMLButtonElement | null>;
  onMobileClose: () => void;
}>) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [collapsed, setCollapsed] = useState(false);
  const [sidebarReady, setSidebarReady] = useState(false);
  const [mobileViewport, setMobileViewport] = useState(false);
  const [monitorLastVisit, setMonitorLastVisit] = useState('');
  const sidebarRef = useRef<HTMLElement | null>(null);
  const mobileCloseRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    const mobileMedia = window.matchMedia('(max-width: 760px)');
    const syncMobileViewport = () => setMobileViewport(mobileMedia.matches);
    syncMobileViewport();
    mobileMedia.addEventListener('change', syncMobileViewport);
    return () => mobileMedia.removeEventListener('change', syncMobileViewport);
  }, []);

  useEffect(() => {
    if (!mobileViewport && mobileOpen) onMobileClose();
  }, [mobileOpen, mobileViewport, onMobileClose]);

  useEffect(() => {
    if (!mobileOpen || !mobileViewport) return;
    const opener = mobileMenuTriggerRef.current;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const focusFrame = window.requestAnimationFrame(() => mobileCloseRef.current?.focus());
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onMobileClose();
        return;
      }
      trapFocus(event, sidebarRef.current);
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      window.cancelAnimationFrame(focusFrame);
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', handleKeyDown);
      if (opener?.isConnected) opener.focus();
    };
  }, [mobileMenuTriggerRef, mobileOpen, mobileViewport, onMobileClose]);

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEYS.SIDEBAR_COLLAPSED);
    const initialCollapsed =
      stored === 'true' || stored === 'false'
        ? stored === 'true'
        : window.matchMedia('(max-width: 1279px)').matches;
    const initialMonitorLastVisit =
      window.localStorage.getItem(STORAGE_KEYS.MONITORS_LAST_VISIT) ?? '';
    const frame = window.requestAnimationFrame(() => {
      setCollapsed(initialCollapsed);
      setMonitorLastVisit(initialMonitorLastVisit);
      setSidebarReady(true);
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    if (!sidebarReady) return;
    window.localStorage.setItem(STORAGE_KEYS.SIDEBAR_COLLAPSED, String(collapsed));
  }, [collapsed, sidebarReady]);

  const monitorsQuery = useQuery({
    queryKey: ['sidebar-monitors'],
    queryFn: () => monitorsApi.list({ status: 'active' }),
    staleTime: 60_000,
    enabled: !awsDemoMode,
  });
  const monitorPulse = Boolean(
    monitorsQuery.data?.some((monitor) => {
      if (!monitor.change_count) return false;
      if (!monitorLastVisit) return true;
      return new Date(monitor.updated_at).getTime() > new Date(monitorLastVisit).getTime();
    }),
  );
  const logoutMutation = useMutation({
    mutationFn: () => api.logout(),
    onSuccess: () => {
      queryClient.clear();
      router.replace('/login');
      router.refresh();
    },
  });
  const visuallyCollapsed = collapsed && !mobileViewport;
  const sidebarToggle = getSidebarTogglePresentation(mobileViewport, visuallyCollapsed);
  const SidebarToggleIcon = sidebarToggle.Icon;

  return (
    <>
      <button
        type="button"
        className={cn('app-sidebar-backdrop', mobileOpen && 'is-open')}
        aria-hidden="true"
        tabIndex={-1}
        onClick={onMobileClose}
      />
      <aside
        ref={sidebarRef}
        inert={mobileViewport && !mobileOpen}
        aria-hidden={mobileViewport && !mobileOpen ? true : undefined}
        tabIndex={-1}
        className={cn(
          'app-sidebar',
          visuallyCollapsed && 'is-collapsed',
          mobileOpen && 'is-mobile-open',
        )}
      >
        <div className="app-sidebar-header">
          <LogoMark collapsed={visuallyCollapsed} />
          <button
            ref={mobileCloseRef}
            id="app-sidebar-toggle"
            data-testid="app-sidebar-toggle"
            type="button"
            onClick={() => {
              if (mobileViewport) {
                onMobileClose();
                return;
              }
              setCollapsed((value) => !value);
            }}
            className="app-icon-button"
            aria-controls="app-sidebar-navigation"
            aria-expanded={mobileViewport ? mobileOpen : !visuallyCollapsed}
            aria-label={sidebarToggle.label}
            title={sidebarToggle.label}
          >
            <SidebarToggleIcon className="size-4" />
          </button>
        </div>

        <nav id="app-sidebar-navigation" className="app-sidebar-nav" aria-label="Main navigation">
          {visibleNavGroups.map((group) => (
            <div key={group.label} className="app-sidebar-group">
              <div className="space-y-1">
                {group.items.map((item) => {
                  const active = isNavItemActive(pathname, item);
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.href}
                      href={item.href as Route}
                      onClick={onMobileClose}
                      aria-label={item.label}
                      title={collapsed ? item.label : undefined}
                      className={cn(
                        'app-nav-item relative',
                        active && 'is-active',
                        visuallyCollapsed && 'is-collapsed',
                      )}
                    >
                      <Icon className="app-nav-icon" />
                      {item.href === '/monitors' && monitorPulse ? (
                        <span
                          className="bg-accent absolute right-2 size-1.5 rounded-full"
                          aria-hidden
                        />
                      ) : null}
                      {!visuallyCollapsed && <span className="truncate">{item.label}</span>}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="app-sidebar-footer">
          {!visuallyCollapsed ? (
            <div className="app-sidebar-footer-row">
              <div className="min-w-0">
                <div className="app-sidebar-footer-title truncate">{user.email}</div>
                <div className="app-sidebar-footer-subtitle capitalize">{user.role}</div>
              </div>
              <button
                type="button"
                className="app-icon-button"
                onClick={() => logoutMutation.mutate()}
                disabled={logoutMutation.isPending}
                aria-label="Log out"
                title="Log out"
              >
                <LogOut className="size-3.5" />
              </button>
            </div>
          ) : (
            <button
              type="button"
              className="app-icon-button mx-auto"
              onClick={() => logoutMutation.mutate()}
              disabled={logoutMutation.isPending}
              aria-label="Log out"
              title={`Log out ${user.email}`}
            >
              <LogOut className="size-3.5" />
            </button>
          )}
          {logoutMutation.isError ? (
            <InlineAlert
              className="mt-2"
              tone="danger"
              message={
                <div className="flex items-center justify-between gap-2">
                  <span>Could not log out.</span>
                  <button
                    type="button"
                    className="font-medium underline"
                    onClick={() => logoutMutation.mutate()}
                  >
                    Retry
                  </button>
                </div>
              }
            />
          ) : null}
        </div>
      </aside>
    </>
  );
}
