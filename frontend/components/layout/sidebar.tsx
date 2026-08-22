'use client';

import { useQuery } from '@tanstack/react-query';
import type { Route } from 'next';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import type { ComponentType } from 'react';
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
  Radar,
  SearchCheck,
  Settings2,
  ShieldCheck,
  WandSparkles,
} from 'lucide-react';

import { monitorsApi } from '../../lib/api';
import { STORAGE_KEYS } from '../../lib/constants/storage-keys';
import { cn } from '../../lib/utils';
import { ThemeToggle } from '../ui/theme-toggle';
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

const navSkeletonKeys = navGroups.flatMap((group) => group.items.map((item) => `nav-${item.href}`));

export function SidebarSkeletonNavigation() {
  return navSkeletonKeys.map((key) => <div key={key} className="skeleton h-8 w-full rounded-md" />);
}

function isNavItemActive(pathname: string, item: (typeof navGroups)[number]['items'][number]) {
  if ('exactMatch' in item && item.exactMatch) return pathname === item.href;
  return pathname === item.href || pathname.startsWith(`${item.href}/`);
}

export function Sidebar({ pathname }: Readonly<{ pathname: string }>) {
  const [collapsed, setCollapsed] = useState(false);
  const [sidebarReady, setSidebarReady] = useState(false);
  const [monitorLastVisit, setMonitorLastVisit] = useState('');

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
  });
  const monitorPulse = Boolean(
    monitorsQuery.data?.some((monitor) => {
      if (!monitor.change_count) return false;
      if (!monitorLastVisit) return true;
      return new Date(monitor.updated_at).getTime() > new Date(monitorLastVisit).getTime();
    }),
  );

  return (
    <aside className={cn('app-sidebar', collapsed && 'is-collapsed')}>
      <div className="app-sidebar-header">
        <LogoMark collapsed={collapsed} />
        <button
          id="app-sidebar-toggle"
          data-testid="app-sidebar-toggle"
          type="button"
          onClick={() => setCollapsed((value) => !value)}
          className="app-icon-button"
          aria-controls="app-sidebar-navigation"
          aria-expanded={!collapsed}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight className="size-3.5" /> : <ChevronLeft className="size-3.5" />}
        </button>
      </div>

      <nav id="app-sidebar-navigation" className="app-sidebar-nav" aria-label="Main navigation">
        {navGroups.map((group) => (
          <div key={group.label} className="app-sidebar-group">
            <div className="space-y-1">
              {group.items.map((item) => {
                const active = isNavItemActive(pathname, item);
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href as Route}
                    aria-label={item.label}
                    title={collapsed ? item.label : undefined}
                    className={cn(
                      'app-nav-item relative',
                      active && 'is-active',
                      collapsed && 'is-collapsed',
                    )}
                  >
                    <Icon className="app-nav-icon" />
                    {item.href === '/monitors' && monitorPulse ? (
                      <span
                        className="bg-accent absolute right-2 size-1.5 rounded-full"
                        aria-hidden
                      />
                    ) : null}
                    {!collapsed && <span className="truncate">{item.label}</span>}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {!collapsed ? (
        <div className="app-sidebar-footer">
          <div className="app-sidebar-footer-row">
            <div>
              <div className="app-sidebar-footer-title">Display</div>
              <div className="app-sidebar-footer-subtitle">Theme preference</div>
            </div>
            <ThemeToggle compact />
          </div>
        </div>
      ) : null}
    </aside>
  );
}
