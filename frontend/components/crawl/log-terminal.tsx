'use client';

import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  Clock,
  Database,
  Dot,
  Globe,
  HardDrive,
  Layers,
  Monitor,
  RefreshCw,
  ShieldAlert,
  XCircle,
  Zap,
} from 'lucide-react';
import React, { memo, useEffect, useMemo, useRef, useState } from 'react';
import type { RefObject } from 'react';

import type { CrawlLog, CrawlRecord } from '../../lib/api/types';
import { cn } from '../../lib/utils';
import {
  formatDurationMs,
  formatTimeHms,
  humanizeFieldName,
  normalizeField,
  parseApiDate,
} from '../../lib/crawl/format';
import { uniqueRequestedFields } from '../../lib/crawl/fields';
import { cleanRecordForDisplay } from '../../lib/crawl/record-utils';
import { isInformativeValue, qualityLevelFromScore } from '../../lib/crawl/quality';
import { scrollViewportToBottom } from '../../lib/crawl/scroll';
import { Button } from '../ui/primitives';
import { acquisitionDiagnosticsSummary, recordConfidenceSummary } from './crawl-diagnostics';
import {
  buildLogSiteGroups,
  getLogStage,
  isPersistenceSummaryLog,
  LOG_PATTERNS,
  logMessageIsError,
  parseStartingLog,
  sanitizeLogMessage,
  siteDomId,
  STAGE_CONFIG,
  TERMINAL_STRINGS,
} from './log-terminal-utils';
import type { LogStage, LogSiteGroup } from './log-terminal-utils';
import { PayloadPeekPanel } from './log-terminal-payload';

import {
  buildExpandedRows,
  formatShortUrlLabel,
  getLogIconDescriptor,
  groupConfidence,
  groupDurationMs,
  groupFieldCoverage,
  groupStillActive,
  payloadSnapshot,
  renderLogContent,
  severityTone,
  ShortenedUrl,
  StageChip,
  toneForConfidence,
  useLogViewport,
} from './log-terminal-presentation';
export const LogTerminal = memo(function LogTerminal({
  logs,
  records = [],
  requestedFields = [],
  live = false,
  viewportRef,
}: Readonly<{
  logs: CrawlLog[];
  records?: CrawlRecord[];
  requestedFields?: string[];
  live?: boolean;
  viewportRef?: RefObject<HTMLDivElement | null>;
}>) {
  const ref = useLogViewport(logs.length, viewportRef);
  const peekPanelRef = useRef<HTMLDivElement | null>(null);
  const peekReturnFocusRef = useRef<HTMLElement | null>(null);
  const [nowMs, setNowMs] = useState(() => Date.now());
  const [peekedGroupKey, setPeekedGroupKey] = useState<string | null>(null);
  const [peekedRecordIndex, setPeekedRecordIndex] = useState(0);
  const [expandedGroupPreference, setExpandedGroupPreference] = useState<
    string | null | '__auto__'
  >('__auto__');
  const [triageCursor, setTriageCursor] = useState(0);
  const groups = useMemo(() => buildLogSiteGroups(logs, records), [logs, records]);
  const siteOrdinalByKey = useMemo(() => {
    let ordinal = 0;
    const values = new Map<string, number>();
    for (const group of groups) {
      if (!group.url) {
        continue;
      }
      ordinal += 1;
      values.set(group.key, ordinal);
    }
    return values;
  }, [groups]);
  const issueGroups = useMemo(
    () => groups.filter((group) => group.hasError || group.hasWarning),
    [groups],
  );
  const activePeekedGroupKey = useMemo(
    () =>
      peekedGroupKey && groups.some((group) => group.key === peekedGroupKey)
        ? peekedGroupKey
        : null,
    [groups, peekedGroupKey],
  );
  const peekedGroup = useMemo(
    () => groups.find((group) => group.key === activePeekedGroupKey) ?? null,
    [activePeekedGroupKey, groups],
  );
  const expandedGroupKey = useMemo(() => {
    if (
      expandedGroupPreference &&
      expandedGroupPreference !== '__auto__' &&
      groups.some((group) => group.key === expandedGroupPreference)
    ) {
      return expandedGroupPreference;
    }
    if (expandedGroupPreference === null) {
      return null;
    }
    if (live && groups.length > 0) {
      return groups[groups.length - 1].key;
    }
    return issueGroups[0]?.key ?? null;
  }, [expandedGroupPreference, groups, issueGroups, live]);
  const safePeekedRecordIndex = peekedGroup
    ? Math.min(peekedRecordIndex, Math.max(peekedGroup.records.length - 1, 0))
    : 0;
  const peekedRecordJson =
    peekedGroup && peekedGroup.records[safePeekedRecordIndex]
      ? JSON.stringify(cleanRecordForDisplay(peekedGroup.records[safePeekedRecordIndex]), null, 2)
      : '';
  const safeTriageCursor = issueGroups.length ? Math.min(triageCursor, issueGroups.length - 1) : 0;
  const activeGroupKey = live && groups.length > 0 ? groups[groups.length - 1].key : null;

  useEffect(() => {
    if (!live) {
      return;
    }
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [live]);

  useEffect(() => {
    if (!activePeekedGroupKey) {
      return;
    }
    const handlePointerDown = (event: MouseEvent) => {
      const panel = peekPanelRef.current;
      if (!panel) {
        return;
      }
      if (!panel.contains(event.target as Node)) {
        setPeekedGroupKey(null);
      }
    };
    document.addEventListener('mousedown', handlePointerDown);
    return () => document.removeEventListener('mousedown', handlePointerDown);
  }, [activePeekedGroupKey]);

  const timelineTicks = useMemo(() => {
    if (!groups.length) {
      return [];
    }
    const start = parseApiDate(groups[0].logs[0]?.created_at ?? new Date().toISOString()).getTime();
    const end = parseApiDate(
      groups[groups.length - 1].logs.at(-1)?.created_at ??
        groups[0].logs[0]?.created_at ??
        new Date().toISOString(),
    ).getTime();
    const range = Math.max(1, end - start);
    return groups.map((group) => {
      const createdAt = group.logs[0]?.created_at ?? new Date().toISOString();
      const percent = ((parseApiDate(createdAt).getTime() - start) / range) * 100;
      return {
        key: group.key,
        percent,
        tone: group.hasError
          ? 'bg-danger'
          : group.hasWarning
            ? 'bg-warning'
            : group.recordCount > 0
              ? 'bg-emerald-400'
              : 'bg-white/15',
      };
    });
  }, [groups]);

  const jumpToGroup = (groupKey: string) => {
    const el = document.getElementById(siteDomId(groupKey));
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      el.classList.add('log-entry-highlight');
      setTimeout(() => el.classList.remove('log-entry-highlight'), 2000);
    }
    setExpandedGroupPreference(groupKey);
  };

  const toggleGroup = (groupKey: string) => {
    if (groupKey === activeGroupKey) {
      return;
    }
    setExpandedGroupPreference((current) => (current === groupKey ? null : groupKey));
  };

  const navigateTriage = (dir: 'next' | 'prev') => {
    if (!issueGroups.length) {
      return;
    }
    const delta = dir === 'next' ? 1 : -1;
    const nextIndex = (safeTriageCursor + delta + issueGroups.length) % issueGroups.length;
    setTriageCursor(nextIndex);
    jumpToGroup(issueGroups[nextIndex].key);
  };

  return (
    <div
      className="crawl-terminal-shell group/terminal relative flex flex-col overflow-hidden rounded-none border"
      onFocusCapture={(event) => {
        if (!activePeekedGroupKey) peekReturnFocusRef.current = event.target as HTMLElement;
      }}
      style={{
        borderColor: 'var(--terminal-border)',
        backgroundColor: 'var(--terminal-bg)',
        color: 'var(--terminal-fg)',
        boxShadow: 'var(--terminal-shadow)',
      }}
    >
      <div
        className="flex h-9 items-center justify-between border-b bg-[color-mix(in_srgb,var(--text-primary)_5%,transparent)] px-6"
        style={{ borderColor: 'var(--terminal-border)' }}
      >
        <div className="flex items-center gap-2">
          <span className="relative flex size-2">
            <span
              className={cn(
                'absolute inline-flex h-full w-full animate-ping rounded-full opacity-75',
                live ? 'bg-emerald-500' : 'bg-slate-400',
              )}
            ></span>
            <span
              className={cn(
                'relative inline-flex size-2 rounded-full',
                live ? 'bg-emerald-500' : 'bg-slate-400',
              )}
            ></span>
          </span>
          <span className="type-label-mono text-xs tracking-[0.25em] uppercase">
            activity_stream.log
          </span>
        </div>
        <div className="flex items-center gap-3">
          <div className="group/scrubber relative flex h-2 w-32 cursor-crosshair items-center rounded-sm bg-[color-mix(in_srgb,var(--text-primary)_8%,transparent)]">
            {timelineTicks.map((tick) => (
              <button
                key={tick.key}
                type="button"
                aria-label={`Jump to ${tick.key}`}
                onClick={() => jumpToGroup(tick.key)}
                className={cn(
                  'focus-visible:ring-accent absolute h-full w-0.5 cursor-pointer transition-transform hover:scale-y-125 focus-visible:scale-y-125 focus-visible:ring-1 focus-visible:outline-none',
                  tick.tone,
                )}
                style={{ left: `${tick.percent}%` }}
              />
            ))}
          </div>
          <div className="flex items-center gap-3 opacity-60 transition-opacity group-focus-within/terminal:opacity-100 group-hover/terminal:opacity-100">
            <button
              type="button"
              onClick={() => navigateTriage('prev')}
              className="type-label-mono hover:text-accent focus-visible:text-accent focus-visible:outline-none"
            >
              Prev
            </button>
            <span className="bg-muted h-3 w-px opacity-20" />
            <button
              type="button"
              onClick={() => navigateTriage('next')}
              className="type-label-mono hover:text-accent focus-visible:text-accent focus-visible:outline-none"
            >
              Next
            </button>
          </div>
        </div>
      </div>

      <div
        ref={ref}
        className="crawl-activity-log max-h-[78vh] min-h-[62vh] overflow-y-auto"
        role="log"
        aria-live={live ? 'polite' : 'off'}
        aria-atomic="false"
      >
        {groups.length ? (
          groups.map((group, index) => (
            <LogGroupSection
              key={group.key}
              {...{
                group,
                index,
                activeGroupKey,
                expandedGroupKey,
                requestedFields,
                live,
                nowMs,
                siteOrdinalByKey,
                toggleGroup,
                setPeekedGroupKey,
                setPeekedRecordIndex,
              }}
            />
          ))
        ) : (
          <div className="px-6 py-8 text-center text-xs italic opacity-55">
            {live ? 'Waiting for log stream...' : 'No log activity recorded'}
          </div>
        )}
      </div>

      <PayloadPeekPanel
        {...{
          activePeekedGroupKey,
          peekPanelRef,
          peekReturnFocusRef,
          peekedGroup,
          safePeekedRecordIndex,
          peekedRecordJson,
          setPeekedGroupKey,
        }}
      />
    </div>
  );
});

type LogGroupSectionProps = {
  group: LogSiteGroup;
  index: number;
  activeGroupKey: string | null;
  expandedGroupKey: string | null;
  requestedFields: string[];
  live: boolean;
  nowMs: number;
  siteOrdinalByKey: Map<string, number>;
  toggleGroup: (key: string) => void;
  setPeekedGroupKey: React.Dispatch<React.SetStateAction<string | null>>;
  setPeekedRecordIndex: React.Dispatch<React.SetStateAction<number>>;
};

function LogGroupSection({
  group,
  index,
  activeGroupKey,
  expandedGroupKey,
  requestedFields,
  live,
  nowMs,
  siteOrdinalByKey,
  toggleGroup,
  setPeekedGroupKey,
  setPeekedRecordIndex,
}: LogGroupSectionProps) {
  const isLiveActive = group.key === activeGroupKey;
  const expanded = expandedGroupKey === group.key || isLiveActive;
  const isRunEventGroup = !group.url;
  const payload = payloadSnapshot(group);
  const confidence = groupConfidence(group);
  const coverage = groupFieldCoverage(group, requestedFields);
  const activeGroup = live && groupStillActive(group);
  const durationMs = groupDurationMs(group, activeGroup ? nowMs : undefined);
  const lastLog = group.logs.at(-1);
  const summaryLog =
    [...group.logs].reverse().find((log) => !isPersistenceSummaryLog(log.message)) ?? lastLog;
  const expandedRows = buildExpandedRows(group, coverage, confidence, durationMs);
  return (
    <section id={siteDomId(group.key)} className="overflow-hidden">
      <LogGroupSummaryRow
        {...{
          group,
          index,
          isLiveActive,
          expanded,
          isRunEventGroup,
          payload,
          confidence,
          coverage,
          durationMs,
          summaryLog,
          siteOrdinalByKey,
          toggleGroup,
          setPeekedGroupKey,
          setPeekedRecordIndex,
        }}
      />
      {expanded ? (
        <ExpandedLogRows
          groupKey={group.key}
          rows={expandedRows}
          {...{ setPeekedGroupKey, setPeekedRecordIndex }}
        />
      ) : null}
    </section>
  );
}

type CoverageSummary = ReturnType<typeof groupFieldCoverage>;
type ConfidenceSummary = ReturnType<typeof groupConfidence>;
type ExpandedLogRow = ReturnType<typeof buildExpandedRows>[number];

type LogGroupSummaryProps = Pick<
  LogGroupSectionProps,
  | 'group'
  | 'index'
  | 'siteOrdinalByKey'
  | 'toggleGroup'
  | 'setPeekedGroupKey'
  | 'setPeekedRecordIndex'
> & {
  isLiveActive: boolean;
  expanded: boolean;
  isRunEventGroup: boolean;
  payload: unknown;
  confidence: ConfidenceSummary;
  coverage: CoverageSummary;
  durationMs: number | null;
  summaryLog: CrawlLog | undefined;
};

function LogGroupSummaryRow(props: LogGroupSummaryProps) {
  const { group, index, isRunEventGroup, coverage, confidence, durationMs, summaryLog } = props;
  return (
    <div
      className={cn(
        'group/row grid w-full cursor-pointer items-center gap-3 px-6 py-1 text-left text-xs transition-colors outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-inset',
        isRunEventGroup
          ? 'grid-cols-[32px_minmax(280px,1fr)_auto_minmax(260px,1.4fr)_60px]'
          : 'grid-cols-[32px_minmax(280px,2fr)_75px_80px_85px_auto_minmax(200px,1.2fr)_80px_70px]',
        severityTone(group, index),
      )}
    >
      <div className="text-muted text-xs font-medium opacity-60">
        {groupOrdinal(props).toString().padStart(2, '0')}
      </div>
      <LogGroupIdentity group={group} isRunEventGroup={isRunEventGroup} />
      {isRunEventGroup ? null : <LogGroupMetrics {...{ coverage, confidence, durationMs }} />}
      <LogGroupStage group={group} isRunEventGroup={isRunEventGroup} />
      <div className="min-w-0">
        <div className="text-secondary truncate text-xs" title={summaryLog?.message || ''}>
          {summaryLog ? sanitizeLogMessage(summaryLog.message) : TERMINAL_STRINGS.PENDING}
        </div>
      </div>
      {isRunEventGroup ? null : <PayloadPeekAction {...props} />}
      <LogGroupExpandButton {...props} />
    </div>
  );
}

function groupOrdinal({ group, index, siteOrdinalByKey }: LogGroupSummaryProps) {
  return group.index ?? siteOrdinalByKey.get(group.key) ?? index + 1;
}

function LogGroupIdentity({
  group,
  isRunEventGroup,
}: {
  group: LogSiteGroup;
  isRunEventGroup: boolean;
}) {
  return (
    <div className="flex min-w-0 items-center gap-2">
      {isRunEventGroup ? null : <Globe className="text-muted size-3.5 shrink-0" />}
      {isRunEventGroup ? (
        <span className="text-secondary block truncate text-xs font-medium" title={group.label}>
          {group.label}
        </span>
      ) : (
        <a
          href={group.url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(event) => event.stopPropagation()}
          className="text-info block truncate text-xs font-normal underline-offset-4 hover:underline"
          title={group.url}
        >
          {formatShortUrlLabel(group.url)}
        </a>
      )}
    </div>
  );
}

function LogGroupMetrics({
  coverage,
  confidence,
  durationMs,
}: {
  coverage: CoverageSummary;
  confidence: ConfidenceSummary;
  durationMs: number | null;
}) {
  const confidenceTone = confidence ? toneForConfidence(confidence.level) : 'text-muted';
  return (
    <>
      <div
        className="border-border text-secondary flex items-center gap-1 rounded-md border bg-[color-mix(in_srgb,var(--bg-alt)_50%,transparent)] px-1.5 py-0.5 text-xs font-medium whitespace-nowrap shadow-sm"
        title="Fields Extracted"
      >
        <Database className="text-muted size-3 shrink-0" />
        <span>
          {coverage.foundCount}/{coverage.totalCount || 0}
        </span>
      </div>
      <div
        className="border-border text-secondary flex items-center gap-1 rounded-md border bg-[color-mix(in_srgb,var(--bg-alt)_50%,transparent)] px-1.5 py-0.5 text-xs font-medium whitespace-nowrap shadow-sm"
        title="Confidence Score"
      >
        <CheckCircle2 className={cn('size-3 shrink-0', confidenceTone)} />
        <span className={confidenceTone}>
          {confidence ? Math.round(confidence.score * 100) + '%' : '--'}
        </span>
      </div>
      <div
        className="border-border text-secondary flex items-center gap-1 rounded-md border bg-[color-mix(in_srgb,var(--bg-alt)_50%,transparent)] px-1.5 py-0.5 text-xs font-medium whitespace-nowrap shadow-sm"
        title="Duration"
      >
        <Clock className="text-muted size-3 shrink-0" />
        <span>{durationMs === null ? '--' : formatDurationMs(durationMs)}</span>
      </div>
    </>
  );
}

function LogGroupStage({
  group,
  isRunEventGroup,
}: {
  group: LogSiteGroup;
  isRunEventGroup: boolean;
}) {
  if (isRunEventGroup)
    return (
      <div className="flex items-center justify-center">
        <div className="type-label-mono text-xs uppercase">Run</div>
      </div>
    );
  return (
    <div className="flex items-center justify-center">
      {group.lastStage === 'system' ? null : <StageChip stage={group.lastStage} />}
    </div>
  );
}

function PayloadPeekAction({
  group,
  payload,
  setPeekedGroupKey,
  setPeekedRecordIndex,
}: LogGroupSummaryProps) {
  function open(event: React.MouseEvent) {
    event.stopPropagation();
    setPeekedGroupKey(group.key);
    setPeekedRecordIndex(0);
  }
  return (
    <div className="flex items-center justify-end">
      {payload ? (
        <Button type="button" variant="quiet" size="sm" onClick={open}>
          Peek
        </Button>
      ) : (
        <span className="type-caption text-xs opacity-25">--</span>
      )}
    </div>
  );
}

function LogGroupExpandButton({
  group,
  isLiveActive,
  expanded,
  toggleGroup,
}: LogGroupSummaryProps) {
  const label = isLiveActive
    ? 'Active logs for ' + (group.url || group.label)
    : (expanded ? 'Collapse' : 'Expand') + ' logs for ' + (group.url || group.label);
  return (
    <button
      type="button"
      aria-expanded={isLiveActive ? undefined : expanded}
      aria-label={label}
      disabled={isLiveActive}
      onClick={() => toggleGroup(group.key)}
      className="focus-ring flex items-center justify-end gap-1.5 rounded-sm pr-2"
    >
      <span className="text-muted font-mono text-xs uppercase">
        {isLiveActive ? (
          <span className="text-accent flex items-center gap-1.5 font-semibold">
            <span className="relative flex size-1.5">
              <span className="bg-accent absolute inline-flex h-full w-full animate-ping rounded-full opacity-75" />
              <span className="bg-accent relative inline-flex size-1.5 rounded-full" />
            </span>
            Active
          </span>
        ) : expanded ? (
          'Less'
        ) : (
          'More'
        )}
      </span>
      {isLiveActive ? null : (
        <ChevronDown
          className={cn(
            'text-muted size-3.5 transition-transform duration-200',
            expanded && 'rotate-180',
          )}
        />
      )}
    </button>
  );
}

function ExpandedLogRows({
  groupKey,
  rows,
  setPeekedGroupKey,
  setPeekedRecordIndex,
}: {
  groupKey: string;
  rows: ExpandedLogRow[];
  setPeekedGroupKey: LogGroupSectionProps['setPeekedGroupKey'];
  setPeekedRecordIndex: LogGroupSectionProps['setPeekedRecordIndex'];
}) {
  if (!rows.length)
    return (
      <div className="bg-[color-mix(in_srgb,var(--bg-alt)_60%,transparent)]">
        <div className="px-3 py-2 text-xs opacity-40">{TERMINAL_STRINGS.NO_LOGS}</div>
      </div>
    );
  return (
    <div className="bg-[color-mix(in_srgb,var(--bg-alt)_60%,transparent)]">
      <div className="overflow-hidden">
        {rows.map((row, index) => (
          <ExpandedLogRowView
            key={row.key}
            {...{ row, index, groupKey, setPeekedGroupKey, setPeekedRecordIndex }}
          />
        ))}
      </div>
    </div>
  );
}

function ExpandedLogRowView({
  row,
  index,
  groupKey,
  setPeekedGroupKey,
  setPeekedRecordIndex,
}: {
  row: ExpandedLogRow;
  index: number;
  groupKey: string;
  setPeekedGroupKey: LogGroupSectionProps['setPeekedGroupKey'];
  setPeekedRecordIndex: LogGroupSectionProps['setPeekedRecordIndex'];
}) {
  const { Icon: IconComponent, iconCls } = getLogIconDescriptor(row.level, row.message);
  function peek() {
    setPeekedGroupKey(groupKey);
    setPeekedRecordIndex(0);
  }
  return (
    <div
      className={cn(
        'grid grid-cols-[64px_24px_105px_minmax(0,1fr)_auto] items-center gap-4 px-6 py-0.5 text-xs',
        index % 2 === 0
          ? 'bg-[color-mix(in_srgb,var(--bg-alt)_35%,transparent)]'
          : 'bg-transparent',
      )}
    >
      <span className="text-muted font-mono text-xs font-normal tabular-nums">
        {row.createdAt ? formatTimeHms(row.createdAt) : '--'}
      </span>
      <div className="flex justify-center">
        <IconComponent className={cn('size-3.5', iconCls)} />
      </div>
      <div className="flex">
        <StageChip stage={row.stage} showIcon={false} />
      </div>
      <span className="text-secondary min-w-0 text-xs font-medium break-words">
        {row.createdAt ? renderLogContent(row.message, row.stage === 'system') : row.message}
      </span>
      <span className="flex items-center gap-2">
        {row.payloadAction ? (
          <Button type="button" variant="quiet" size="sm" onClick={peek}>
            Peek payload
          </Button>
        ) : null}
      </span>
    </div>
  );
}
