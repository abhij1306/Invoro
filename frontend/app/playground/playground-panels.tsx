'use client';

import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, CheckCircle2, Circle, ExternalLink, Loader2, Play } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';

import {
  DataRegionEmpty,
  DataRegionLoading,
  SurfacePanel,
  TableSurface,
} from '../../components/ui/patterns';
import { Badge, Button } from '../../components/ui/primitives';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../../components/ui/table';
import { api } from '../../lib/api';
import type { PlaygroundSessionResponse } from '../../lib/api/types';
import { cn } from '../../lib/utils';
import {
  collectNodeUrls,
  collectTreeUrls,
  type DiscoveredProduct,
  type ExtractedRecord,
  type NavNode,
  type NavTreeGroup,
  type SitemapGroup,
} from './playground-normalizers';

type PlaygroundSession = PlaygroundSessionResponse;

// ─── Sub-Components ────────────────────────────────────────────────────────────

// Phase = which step's logs we're showing. Used to seed milestone copy.
type ActivityPhase = 'discover' | 'extract';

type ActivityEntry = {
  key: string;
  text: string;
  status: 'done' | 'active' | 'pending';
  timestamp?: string;
};

// Map raw backend log messages to short, human-friendly lines.
// Returns null to drop noisy entries.
function humanizeLogMessage(raw: string): string | null {
  const msg = raw
    .trim()
    .replace(/^\[url:(https?:\/\/[^\s\]]+)\]\s*/i, '')
    .trim();
  if (!msg || hiddenPlaygroundLog(msg)) return null;
  for (const rule of PLAYGROUND_LOG_RULES) {
    if (rule.pattern.test(msg)) return rule.render(msg);
  }
  return msg.length > 120 ? `${msg.slice(0, 117)}…` : msg;
}

function hiddenPlaygroundLog(message: string) {
  return (
    /^\[corr:/i.test(message) ||
    (/^\[ROBOTS\]/i.test(message) && /No robots\.txt/i.test(message)) ||
    /listing_escalation_skipped/i.test(message)
  );
}

type LogRewriteRule = { pattern: RegExp; render: (message: string) => string };
const fixedLogRule = (pattern: RegExp, text: string): LogRewriteRule => ({
  pattern,
  render: () => text,
});
const countLogRule = (pattern: RegExp, prefix: string, fallback: string): LogRewriteRule => ({
  pattern,
  render: (message) => {
    const count = message.match(pattern)?.[1];
    return count ? `${prefix}${count} record${count === '1' ? '' : 's'}` : fallback;
  },
});

const PLAYGROUND_LOG_RULES: LogRewriteRule[] = [
  {
    pattern: /Resolved (\d+) seed URL/i,
    render: (message) => {
      const count = message.match(/Resolved (\d+) seed URL/i)?.[1];
      return count
        ? `Resolved ${count} target URL${count === '1' ? '' : 's'}`
        : 'Resolved target URLs';
    },
  },
  fixedLogRule(/Starting crawl run/i, 'Connecting to target site'),
  fixedLogRule(/Launched .* browser/i, 'Launching browser engine'),
  fixedLogRule(/Rotating proxy profile detected/i, 'Rotating proxy profile'),
  {
    pattern: /Page loaded in (\d+)ms/i,
    render: (message) => {
      const value = message.match(/Page loaded in (\d+)ms/i)?.[1];
      return value ? `Page loaded (${value}ms)` : 'Page loaded';
    },
  },
  fixedLogRule(/Acquired payload via/i, 'Fetched page content'),
  fixedLogRule(/HTTP transport fallback/i, 'Retrying with alternate transport'),
  fixedLogRule(/Escalating to browser/i, 'Escalating to full browser render'),
  fixedLogRule(/Traversal complete/i, 'Finished page traversal'),
  fixedLogRule(
    /(?=.*(?:scroll|load_more|paginate))(?=.*(?:traversal|listing))/i,
    'Discovered pagination pattern',
  ),
  countLogRule(/Normalized (\d+) record/i, 'Parsed ', 'Parsing records'),
  countLogRule(/Persisted (\d+) record/i, 'Saved ', 'Saving records'),
  {
    pattern: /Extracted \d+ records/i,
    render: (message) => {
      const match = message.match(/Extracted (\d+) records using ([\w-]+)/i);
      return match
        ? `Extracted ${match[1]} record${match[1] === '1' ? '' : 's'} (${match[2]})`
        : 'Extracted records';
    },
  },
  {
    pattern: /Pipeline finished/i,
    render: (message) => {
      const match = message.match(/Pipeline finished\. (\d+) records/i);
      return match
        ? `Run complete (${match[1]} record${match[1] === '1' ? '' : 's'})`
        : 'Run complete';
    },
  },
  fixedLogRule(/Stopped after reaching max_records/i, 'Reached record limit'),
  fixedLogRule(/retrying browser render/i, 'Retrying with browser render'),
];

export function ActivityLogPanel({
  title,
  subtitle,
  runId,
  startedAt,
  phase,
}: {
  title: string;
  subtitle: React.ReactNode;
  runId?: number;
  startedAt?: string;
  phase: ActivityPhase;
}) {
  // Poll backend logs for this run while the panel is mounted.
  const logsQuery = useQuery({
    queryKey: ['playground-crawl-logs', runId],
    queryFn: () => api.getCrawlLogs(runId!, { limit: 200 }),
    enabled: runId !== undefined && runId !== null,
    refetchInterval: 2000,
  });

  // Live elapsed clock so the UI never looks frozen even with no log activity.
  // Date.now / Date.parse are impure, so we initialize via lazy useState and
  // resync when startedAt changes (derive-from-prop pattern). useMemo would
  // be flagged by react-hooks/purity for calling impure functions.
  const computeStartMs = (value: string | undefined): number =>
    value ? Date.parse(value) : Date.now();
  const [startMs, setStartMs] = useState(() => computeStartMs(startedAt));
  const [prevStartedAt, setPrevStartedAt] = useState(startedAt);
  if (startedAt !== prevStartedAt) {
    setPrevStartedAt(startedAt);
    setStartMs(computeStartMs(startedAt));
  }
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);
  const elapsedSec = Math.max(0, Math.floor((now - startMs) / 1000));
  const slow = elapsedSec >= 30;
  const stalled = elapsedSec >= 90;

  // Build the rendered entries: a small set of seeded milestones followed by
  // humanized real backend logs. Earlier entries are marked done; the last
  // one becomes the active spinner row.
  const entries: ActivityEntry[] = useMemo(() => {
    const seeded: ActivityEntry[] =
      phase === 'discover'
        ? [
            { key: 'seed-init', text: 'Session started', status: 'done' },
            { key: 'seed-resolve', text: 'Resolving target URL', status: 'done' },
          ]
        : [
            { key: 'seed-init', text: 'Extraction job created', status: 'done' },
            { key: 'seed-batch', text: 'Queued selected pages', status: 'done' },
          ];

    const rawLogs = logsQuery.data ?? [];
    const seen = new Set<string>();
    const fromLogs: ActivityEntry[] = [];
    for (const log of rawLogs) {
      const text = humanizeLogMessage(log.message);
      if (!text) continue;
      // Dedupe consecutive identical lines (e.g. repeated page-loaded events).
      if (seen.has(text)) continue;
      seen.add(text);
      fromLogs.push({
        key: `log-${log.id}`,
        text,
        status: 'done',
        timestamp: log.created_at,
      });
    }

    const all = [...seeded, ...fromLogs];

    // The last visible entry is the one currently in flight; everything
    // before it is done. We always show an active row to keep the spinner
    // alive — derive it from the most recent log if we have one, otherwise
    // fall back to a generic phase message.
    const activeText = phase === 'discover' ? 'Parsing response' : 'Parsing extracted data';
    if (all.length === 0) {
      all.push({ key: 'active-fallback', text: activeText, status: 'active' });
    } else {
      // Promote the last entry to active.
      const last = all[all.length - 1];
      all[all.length - 1] = { ...last, status: 'active' };
    }
    return all;
  }, [logsQuery.data, phase]);

  const elapsedLabel =
    elapsedSec < 60 ? `${elapsedSec}s` : `${Math.floor(elapsedSec / 60)}m ${elapsedSec % 60}s`;

  return (
    <SurfacePanel>
      <div className="border-divider flex items-center justify-between gap-3 border-b px-4 py-3">
        <div className="flex items-center gap-3">
          <Loader2 className="text-accent size-5 animate-spin" />
          <div>
            <p className="m-0 font-medium">{title}</p>
            <p className="text-muted m-0 text-sm">{subtitle}</p>
          </div>
        </div>
        <span className="text-muted font-mono text-xs">{elapsedLabel}</span>
      </div>
      <ul className="space-y-2 px-6 py-4 text-sm">
        {entries.map((entry) => (
          <li key={entry.key} className="flex items-start gap-2">
            {entry.status === 'done' && (
              <CheckCircle2 className="text-success mt-0.5 size-4 shrink-0" />
            )}
            {entry.status === 'active' && (
              <Loader2 className="text-accent mt-0.5 size-4 shrink-0 animate-spin" />
            )}
            {entry.status === 'pending' && <Circle className="text-muted mt-0.5 size-4 shrink-0" />}
            <span className={cn(entry.status === 'pending' && 'text-muted')}>{entry.text}</span>
          </li>
        ))}
      </ul>
      {slow && (
        <div className="border-divider flex items-start gap-2 border-t px-6 py-3 text-xs">
          <AlertTriangle
            className={cn('mt-0.5 size-4 shrink-0', stalled ? 'text-danger' : 'text-warning')}
          />
          <span className="text-muted">
            {stalled
              ? 'This is taking longer than usual. The site may have heavy bot defenses or the page may be slow to render. You can keep waiting or start a new session with a different URL.'
              : 'Still working. Some sites with strong bot protection take longer to crawl.'}
          </span>
        </div>
      )}
    </SurfacePanel>
  );
}

export function NavTreePanel({
  groups,
  selected,
  onToggleUrls,
  onSelectAll,
  onConfirm,
  confirmLabel,
  confirmDisabled,
  isLoading,
}: {
  groups: NavTreeGroup[];
  selected: Set<string>;
  onToggleUrls: (urls: string[]) => void;
  onSelectAll: () => void;
  onConfirm: () => void;
  confirmLabel: string;
  confirmDisabled: boolean;
  isLoading: boolean;
}) {
  const initialOpen = useMemo(
    () => groups.flatMap((group) => group.tree.map((_, index) => `${group.inputUrl}-${index}`)),
    [groups],
  );
  const initialOpenSet = useMemo(() => new Set(initialOpen), [initialOpen]);
  const [openOverrides, setOpenOverrides] = useState<Set<string>>(() => new Set());
  const open = useMemo(() => {
    const next = new Set(initialOpenSet);
    openOverrides.forEach((key) => {
      if (next.has(key)) next.delete(key);
      else next.add(key);
    });
    return next;
  }, [initialOpenSet, openOverrides]);
  function toggleOpen(key: string) {
    setOpenOverrides((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }
  const totalUrls = groups.flatMap((group) => collectTreeUrls(group.tree)).length;

  return (
    <SurfacePanel>
      <div className="border-divider flex items-center justify-between gap-3 border-b px-4 py-3">
        <div>
          <p className="type-label m-0">Navigation categories ({totalUrls})</p>
          <p className="text-muted m-0 text-sm">Pick one or more category branches to crawl.</p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="ghost" onClick={onSelectAll}>
            Select All (max 50)
          </Button>
          <Button size="sm" onClick={onConfirm} disabled={confirmDisabled}>
            {isLoading ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Play className="size-3.5" />
            )}
            {confirmLabel}
          </Button>
        </div>
      </div>
      <div className="divide-divider divide-y">
        {groups.map((group) => (
          <div key={group.inputUrl} className="p-4">
            <div className="mb-3 flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="m-0 truncate font-mono text-sm">{group.inputUrl}</p>
                <p className="text-muted m-0 text-xs">
                  {collectTreeUrls(group.tree).length} category URL(s) from {group.source}
                  {group.error ? ` (${group.error})` : ''}
                </p>
              </div>
              <Badge tone={group.error ? 'warning' : 'success'}>{group.source}</Badge>
            </div>
            <div className="space-y-1">
              {group.tree.map((node, index) => (
                <NavTreeNode
                  key={`${group.inputUrl}-${node.label}-${index}`}
                  node={node}
                  nodeKey={`${group.inputUrl}-${index}`}
                  selected={selected}
                  open={open}
                  onToggleOpen={toggleOpen}
                  onToggleUrls={onToggleUrls}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </SurfacePanel>
  );
}

function NavTreeNode({
  node,
  nodeKey,
  selected,
  open,
  onToggleOpen,
  onToggleUrls,
  depth = 0,
}: {
  node: NavNode;
  nodeKey: string;
  selected: Set<string>;
  open: Set<string>;
  onToggleOpen: (key: string) => void;
  onToggleUrls: (urls: string[]) => void;
  depth?: number;
}) {
  const urls = collectNodeUrls(node);
  const hasChildren = node.children.length > 0;
  const isOpen = open.has(nodeKey);
  const selectedCount = urls.filter((item) => selected.has(item)).length;
  const allSelected = urls.length > 0 && selectedCount === urls.length;
  const someSelected = selectedCount > 0 && selectedCount < urls.length;

  return (
    <div>
      <div
        className={cn(
          'hover:bg-background-alt flex items-center gap-2 rounded-md px-2 py-1.5 text-sm',
          (allSelected || someSelected) && 'bg-background-alt',
        )}
        style={{ paddingLeft: `${depth * 18 + 8}px` }}
      >
        {hasChildren ? (
          <button
            type="button"
            className="text-muted flex size-5 shrink-0 items-center justify-center rounded"
            onClick={() => {
              onToggleOpen(nodeKey);
            }}
            aria-label={isOpen ? 'Collapse category' : 'Expand category'}
          >
            {isOpen ? '-' : '+'}
          </button>
        ) : (
          <span className="size-5 shrink-0" aria-hidden="true" />
        )}
        <input
          type="checkbox"
          aria-label={`Select ${node.label || node.url || 'category'}`}
          checked={allSelected}
          ref={(el) => {
            if (el) el.indeterminate = someSelected;
          }}
          onChange={() => onToggleUrls(urls)}
          disabled={urls.length === 0}
          className="size-4 rounded"
        />
        <button
          type="button"
          className="min-w-0 flex-1 text-left"
          onClick={() => {
            if (hasChildren) {
              onToggleOpen(nodeKey);
              return;
            }
            onToggleUrls(urls);
          }}
        >
          <span className="block truncate font-medium">{node.label}</span>
          {node.url && (
            <span className="text-muted block truncate font-mono text-xs">{node.url}</span>
          )}
        </button>
        {hasChildren && <Badge tone="neutral">{urls.length}</Badge>}
      </div>
      {hasChildren && isOpen && (
        <div className="space-y-1">
          {node.children.map((child, childIndex) => {
            const childKey = `${nodeKey}-${child.url ?? child.label}-${childIndex}`;
            return (
              <NavTreeNode
                key={childKey}
                node={child}
                nodeKey={childKey}
                selected={selected}
                open={open}
                onToggleOpen={onToggleOpen}
                onToggleUrls={onToggleUrls}
                depth={depth + 1}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

export function PickerPanel({
  mode,
  title,
  description,
  items,
  selected,
  onToggle,
  onSelectAll,
  onConfirm,
  confirmLabel,
  confirmDisabled,
  isLoading,
  emptyTitle,
  emptyDescription,
}: {
  mode: 'single' | 'multi';
  title: string;
  description: string;
  items: DiscoveredProduct[];
  selected: Set<string>;
  onToggle: (url: string) => void;
  onSelectAll?: () => void;
  onConfirm: () => void;
  confirmLabel: string;
  confirmDisabled: boolean;
  isLoading: boolean;
  emptyTitle: string;
  emptyDescription: string;
}) {
  const showBrandPrice = items.some((item) => item.brand || item.price || item.title);
  return (
    <SurfacePanel>
      <div className="border-divider flex items-center justify-between border-b px-4 py-3">
        <div>
          <p className="type-label m-0">{title}</p>
          <p className="text-muted m-0 text-sm">{description}</p>
        </div>
        <div className="flex gap-2">
          {mode === 'multi' && onSelectAll && items.length > 0 && (
            <Button size="sm" variant="ghost" onClick={onSelectAll}>
              Select All (max 50)
            </Button>
          )}
          <Button size="sm" onClick={onConfirm} disabled={confirmDisabled}>
            {isLoading ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <Play className="size-3.5" />
            )}
            {confirmLabel}
          </Button>
        </div>
      </div>
      <TableSurface>
        {items.length === 0 ? (
          <DataRegionEmpty title={emptyTitle} description={emptyDescription} />
        ) : (
          <Table className="compact-data-table">
            <TableHeader>
              <TableRow>
                <TableHead className="w-[40px]">{''}</TableHead>
                <TableHead>{showBrandPrice ? 'Product' : 'URL'}</TableHead>
                {showBrandPrice && (
                  <>
                    <TableHead className="w-[120px]">Brand</TableHead>
                    <TableHead className="w-[100px]">Price</TableHead>
                  </>
                )}
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.slice(0, 50).map((item) => {
                const isChecked = selected.has(item.url);
                return (
                  <TableRow
                    key={item.url}
                    className="cursor-pointer"
                    onClick={(e) => {
                      if ((e.target as HTMLElement).tagName === 'INPUT') return;
                      onToggle(item.url);
                    }}
                  >
                    <TableCell>
                      <input
                        type={mode === 'single' ? 'radio' : 'checkbox'}
                        name={mode === 'single' ? 'picker-single' : undefined}
                        checked={isChecked}
                        onChange={() => onToggle(item.url)}
                        onClick={(e) => e.stopPropagation()}
                        className="size-4 rounded"
                      />
                    </TableCell>
                    <TableCell>
                      <div className="min-w-0">
                        <p className="m-0 truncate text-sm font-medium">{item.title || item.url}</p>
                        {item.title && (
                          <p className="text-muted m-0 truncate font-mono text-xs">{item.url}</p>
                        )}
                      </div>
                    </TableCell>
                    {showBrandPrice && (
                      <>
                        <TableCell className="truncate text-sm">{item.brand || '-'}</TableCell>
                        <TableCell className="text-sm">{item.price || '-'}</TableCell>
                      </>
                    )}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </TableSurface>
    </SurfacePanel>
  );
}

export function CategoryDiscoverySummary({ groups }: { groups: SitemapGroup[] }) {
  const foundCount = groups.filter((group) => group.urls.length > 0).length;
  return (
    <SurfacePanel>
      <div className="border-divider border-b px-4 py-3">
        <p className="type-label m-0">Discovery Status</p>
        <p className="text-muted m-0 text-sm">
          {foundCount} of {groups.length} input URL(s) returned category links.
        </p>
      </div>
      <div className="divide-divider divide-y">
        {groups.map((group) => (
          <div key={group.inputUrl} className="flex items-start justify-between gap-4 px-4 py-3">
            <div className="min-w-0">
              <p className="m-0 truncate font-mono text-sm">{group.inputUrl}</p>
              <p className="text-muted m-0 text-xs">
                {group.urls.length > 0
                  ? `${group.urls.length} category URL(s) from ${group.source}`
                  : group.error
                    ? `No category URLs. ${group.error}`
                    : 'No category URLs.'}
              </p>
            </div>
            <Badge tone={group.urls.length > 0 ? 'success' : 'warning'}>
              {group.urls.length > 0 ? 'found' : group.source}
            </Badge>
          </div>
        ))}
      </div>
    </SurfacePanel>
  );
}

export function PipelineStepCard({
  label,
  stepData,
}: {
  label: string;
  stepData?: Record<string, unknown>;
}) {
  if (!stepData) return null;

  const status = stepData.status as string;
  return (
    <div className="border-divider flex items-center justify-between rounded-md border px-4 py-3">
      <div className="flex items-center gap-2">
        {status === 'running' && <Loader2 className="text-accent size-4 animate-spin" />}
        {status === 'completed' && <CheckCircle2 className="text-success size-4" />}
        {status === 'created' && <Circle className="text-muted size-4" />}
        {status === 'failed' && <Circle className="text-danger size-4" />}
        <span className="text-sm font-medium">{label}</span>
      </div>
      <Badge tone={status === 'failed' ? 'danger' : status === 'running' ? 'info' : 'neutral'}>
        {status ? status.charAt(0).toUpperCase() + status.slice(1) : status}
      </Badge>
    </div>
  );
}

export function ExtractedDataPreview({
  records,
  isLoading,
}: {
  records: ExtractedRecord[];
  isLoading: boolean;
}) {
  if (isLoading) {
    return (
      <SurfacePanel>
        <div className="p-4">
          <DataRegionLoading count={3} />
        </div>
      </SurfacePanel>
    );
  }

  if (records.length === 0) {
    return (
      <SurfacePanel>
        <div className="p-4">
          <DataRegionEmpty
            title="No records extracted"
            description="The crawl completed but produced no structured records."
          />
        </div>
      </SurfacePanel>
    );
  }

  // Get field names from first record
  const fieldNames = Object.keys(records[0]?.data ?? {}).slice(0, 6);

  return (
    <SurfacePanel>
      <div className="border-divider flex items-center justify-between border-b px-4 py-3">
        <div>
          <p className="type-label m-0">Extracted Data ({records.length} records)</p>
          <p className="text-muted m-0 text-sm">Preview across all extracted product pages.</p>
        </div>
      </div>
      <TableSurface>
        <Table className="compact-data-table">
          <TableHeader>
            <TableRow>
              {fieldNames.map((field) => (
                <TableHead key={field}>{field}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {records.slice(0, 10).map((record) => (
              <TableRow key={record.id}>
                {fieldNames.map((field) => (
                  <TableCell key={field} className="max-w-[200px] truncate text-sm">
                    {String((record.data as Record<string, unknown>)?.[field] ?? '-')}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableSurface>
    </SurfacePanel>
  );
}

export function PipelineResultsPanel({
  session,
  extractedRunIds,
  onReset,
}: {
  session: PlaygroundSession;
  extractedRunIds: number[];
  onReset?: () => void;
}) {
  const isRunning = session.state === 'running_pipeline';

  return (
    <SurfacePanel>
      <div className="border-divider border-b px-4 py-3">
        <p className="type-label m-0">Pipeline Results</p>
        <p className="text-muted m-0 text-sm">
          {isRunning ? 'Operations in progress...' : 'Latest downstream job state.'}
        </p>
      </div>
      <div className="space-y-3 p-4">
        <PipelineStepCard
          label="Enrichment"
          stepData={session.step_data?.enrich as Record<string, unknown> | undefined}
        />
        <PipelineStepCard
          label="Product Intelligence"
          stepData={session.step_data?.compare as Record<string, unknown> | undefined}
        />
        <PipelineStepCard
          label="Monitor"
          stepData={session.step_data?.monitor as Record<string, unknown> | undefined}
        />
      </div>
      {(onReset || extractedRunIds.length > 0) && (
        <div className="border-divider flex gap-2 border-t px-4 py-3">
          {onReset && (
            <Button size="sm" variant="ghost" onClick={onReset}>
              Start New Session
            </Button>
          )}
          {extractedRunIds[0] ? (
            <Button size="sm" variant="action" asChild>
              <a
                href={`/runs?run_id=${String(extractedRunIds[0])}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                <ExternalLink className="size-3.5" />
                View Run
              </a>
            </Button>
          ) : null}
        </div>
      )}
    </SurfacePanel>
  );
}
