'use client';

import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Copy,
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
import React, { useEffect, useRef } from 'react';
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
import { syntaxHighlightJsonNodes } from '../../lib/ui/syntax';
import { Button } from '../ui/primitives';
import { acquisitionDiagnosticsSummary, recordConfidenceSummary } from './crawl-diagnostics';
import {
  getLogStage,
  isPersistenceSummaryLog,
  LOG_PATTERNS,
  logMessageIsError,
  parseStartingLog,
  sanitizeLogMessage,
  STAGE_CONFIG,
  TERMINAL_STRINGS,
} from './log-terminal-utils';
import type { LogStage, LogSiteGroup } from './log-terminal-utils';

export function useLogViewport(_logCount: number, ref?: RefObject<HTMLDivElement | null>) {
  const internalRef = useRef<HTMLDivElement | null>(null);
  const targetRef = ref ?? internalRef;

  useEffect(() => {
    if (!ref) {
      scrollViewportToBottom(internalRef);
    }
  }, [_logCount, ref]);

  return targetRef;
}
export function getLogIconDescriptor(level: string, message: string) {
  const msg = message.toLowerCase();
  const context = logIconContext(level, message, msg);
  const Icon = ICON_RULES.find((rule) => rule.matches(context))?.Icon ?? Dot;
  const iconCls =
    ICON_TONE_RULES.find((rule) => rule.matches(context))?.className ?? 'text-secondary';
  return { Icon, iconCls };
}

type LogIconContext = {
  level: string;
  msg: string;
  isWarning: boolean;
  isError: boolean;
  hasUrl: boolean;
  isBrowser: boolean;
  isChallenge: boolean;
  isComplete: boolean;
  isRetry: boolean;
};
function includesAny(text: string, values: string[]) {
  return values.some((value) => text.includes(value));
}
function logIconContext(level: string, message: string, msg: string): LogIconContext {
  return {
    level,
    msg,
    isWarning: ['warning', 'warn'].includes(level),
    isError: logMessageIsError(level, message),
    hasUrl: /https?:\/\//i.test(message),
    isBrowser: includesAny(msg, ['browser', 'playwright', 'patchright', 'headless']),
    isChallenge: includesAny(msg, ['challenge', 'blocked', 'captcha', 'bot check']),
    isComplete: includesAny(msg, ['complete', 'success', 'done', 'finished']),
    isRetry: msg.includes('retry'),
  };
}
const ICON_RULES = [
  { matches: (c: LogIconContext) => c.isError, Icon: XCircle },
  { matches: (c: LogIconContext) => c.isWarning, Icon: AlertTriangle },
  { matches: (c: LogIconContext) => c.msg.includes('starting crawl'), Icon: Activity },
  { matches: (c: LogIconContext) => c.msg.includes('ignoring robots.txt'), Icon: ShieldAlert },
  { matches: (c: LogIconContext) => c.msg.includes('extracted'), Icon: Database },
  {
    matches: (c: LogIconContext) => includesAny(c.msg, ['normalized', 'normalised']),
    Icon: Layers,
  },
  { matches: (c: LogIconContext) => c.msg.includes('persisted'), Icon: HardDrive },
  { matches: (c: LogIconContext) => includesAny(c.msg, ['acquiring', 'fetching']), Icon: Globe },
  { matches: (c: LogIconContext) => c.isBrowser, Icon: Monitor },
  { matches: (c: LogIconContext) => c.msg.includes('record'), Icon: Database },
  { matches: (c: LogIconContext) => includesAny(c.msg, ['page loaded', 'page load']), Icon: Zap },
  { matches: (c: LogIconContext) => c.isChallenge, Icon: ShieldAlert },
  { matches: (c: LogIconContext) => c.hasUrl, Icon: Globe },
  { matches: (c: LogIconContext) => c.isRetry || c.msg.includes('refresh'), Icon: RefreshCw },
  { matches: (c: LogIconContext) => c.isComplete, Icon: CheckCircle2 },
];
const ICON_TONE_RULES = [
  { matches: (c: LogIconContext) => c.isError || c.isChallenge, className: 'text-danger' },
  {
    matches: (c: LogIconContext) => c.isWarning || c.msg.includes('ignoring robots.txt'),
    className: 'text-warning',
  },
  { matches: (c: LogIconContext) => c.msg.includes('resolved'), className: 'text-muted ' },
  {
    matches: (c: LogIconContext) =>
      includesAny(c.msg, ['starting crawl', 'acquired', 'acquiring', 'fetching']) ||
      c.isBrowser ||
      c.hasUrl,
    className: 'text-info',
  },
  {
    matches: (c: LogIconContext) =>
      includesAny(c.msg, ['extracted', 'persisted', 'record']) || c.isComplete,
    className: 'text-success',
  },
  {
    matches: (c: LogIconContext) =>
      includesAny(c.msg, ['normalized', 'normalised', 'page loaded', 'page load']),
    className: 'text-warning',
  },
  { matches: (c: LogIconContext) => c.isRetry, className: 'text-info' },
  { matches: (c: LogIconContext) => c.level === 'debug', className: 'text-muted' },
];

export function StageChip({ stage, showIcon = true }: { stage: LogStage; showIcon?: boolean }) {
  const config = STAGE_CONFIG[stage];
  let Icon = Activity;
  if (stage === 'acquisition') Icon = Globe;
  if (stage === 'extraction') Icon = Database;
  if (stage === 'normalize') Icon = Layers;
  if (stage === 'persistence') Icon = HardDrive;

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 text-xs tracking-wide uppercase',
        config.textOnlyClass,
      )}
    >
      {showIcon ? <Icon className="size-3" /> : null}
      <span>{config.label}</span>
    </span>
  );
}

export function severityTone(group: LogSiteGroup, index: number) {
  // REMOVED ALL BACKGROUND COLORS AS PER USER REQUEST - TERMINAL IS NOW MONOCHROMATIC
  if (group.hasError) {
    return 'bg-transparent border-l-2 border-l-danger';
  }
  if (group.hasWarning) {
    return 'bg-transparent border-l-2 border-l-warning';
  }
  if (group.recordCount > 0 || group.stageLogs.persistence.length > 0) {
    return 'bg-transparent border-l-2 border-l-success';
  }
  return index % 2 === 0
    ? 'bg-[color-mix(in_srgb,var(--bg-alt)_40%,transparent)]'
    : 'bg-transparent';
}

export function payloadSnapshot(group: LogSiteGroup) {
  if (!group.records.length) {
    return '';
  }
  const payload =
    group.records.length === 1
      ? cleanRecordForDisplay(group.records[0])
      : group.records.map(cleanRecordForDisplay);
  return JSON.stringify(payload, null, 2);
}

export function publicFieldNames(record: CrawlRecord) {
  return Object.entries(record.data ?? {}).flatMap(([key, value]) =>
    !key.startsWith('_') && isInformativeValue(value) ? [key] : [],
  );
}

export function groupConfidence(group: LogSiteGroup): { score: number; level: string } | null {
  const scores = group.records
    .map(recordConfidenceSummary)
    .filter((value): value is { score: number; level: string } => value !== null);
  if (!scores.length) {
    return null;
  }
  const average = scores.reduce((total, item) => total + item.score, 0) / scores.length;
  return {
    score: average,
    level: String(qualityLevelFromScore(average)),
  };
}

export function groupDurationMs(group: LogSiteGroup, activeNowMs?: number): number | null {
  const recordDurations = group.records
    .map((record) => acquisitionDiagnosticsSummary(record).durationMs)
    .filter((value): value is number => value !== null);
  const startedAt = group.logs[0]?.created_at;
  if (!startedAt) {
    return null;
  }
  const startedMs = parseApiDate(startedAt).getTime();
  if (!Number.isFinite(startedMs)) {
    return null;
  }
  const lastLog = group.logs.at(-1);
  const endCandidatesMs = [
    activeNowMs,
    lastLog?.created_at ? parseApiDate(lastLog.created_at).getTime() : null,
    ...group.records.map((record) => parseApiDate(record.created_at).getTime()),
    ...recordDurations.map((durationMs) => startedMs + durationMs),
  ].filter((value): value is number => typeof value === 'number' && Number.isFinite(value));
  if (!endCandidatesMs.length) {
    return null;
  }
  return Math.max(0, Math.max(...endCandidatesMs) - startedMs);
}

export function groupStillActive(group: LogSiteGroup) {
  if (!group.url) {
    return false;
  }
  const lastMessage = sanitizeLogMessage(group.logs.at(-1)?.message ?? '').toLowerCase();
  return !(
    group.stageLogs.persistence.length > 0 ||
    group.hasError ||
    lastMessage.includes('processing failed') ||
    lastMessage.includes('timed out') ||
    lastMessage.includes('stopped after reaching max_records')
  );
}

export function groupFieldCoverage(group: LogSiteGroup, requestedFields: string[]) {
  const requested = uniqueRequestedFields(requestedFields);
  const normalizedRequested = requested.map(normalizeField);
  const foundNormalized = new Set<string>();
  const foundOriginal = new Map<string, string>();

  for (const record of group.records) {
    for (const field of publicFieldNames(record)) {
      const normalized = normalizeField(field);
      foundNormalized.add(normalized);
      if (!foundOriginal.has(normalized)) {
        foundOriginal.set(normalized, field);
      }
    }
  }

  if (requested.length) {
    const covered = requested.filter(
      (field, index) =>
        foundNormalized.has(normalizedRequested[index]) || foundNormalized.has(field),
    );
    return {
      foundCount: covered.length,
      totalCount: requested.length,
      labels: covered,
    };
  }

  const labels = Array.from(foundOriginal.values());
  return {
    foundCount: labels.length,
    totalCount: labels.length,
    labels,
  };
}

export function toneForConfidence(level: string) {
  if (level === 'high') return 'text-success';
  if (level === 'medium') return 'text-warning';
  if (level === 'low') return 'text-danger';
  return 'text-muted';
}

type ExpandedLogRow = {
  key: string;
  stage: LogStage;
  level: string;
  message: string;
  createdAt?: string | null;
  payloadAction?: boolean;
};

export function buildExpandedRows(
  group: LogSiteGroup,
  coverage: ReturnType<typeof groupFieldCoverage>,
  confidence: ReturnType<typeof groupConfidence>,
  durationMs: number | null,
): ExpandedLogRow[] {
  const rows: ExpandedLogRow[] = group.logs.map((log) => ({
    key: `log-${log.id}`,
    stage: parseStartingLog(log.message) ? 'system' : getLogStage(log.message),
    level: log.level,
    message: log.message,
    createdAt: log.created_at,
  }));

  if (coverage.totalCount > 0 || coverage.labels.length > 0 || confidence) {
    const parts: string[] = [];
    if (coverage.totalCount > 0) {
      const labels = coverage.labels.length
        ? coverage.labels.map(humanizeFieldName).join(', ')
        : 'none';
      parts.push(
        `${TERMINAL_STRINGS.FIELDS} ${coverage.foundCount}/${coverage.totalCount}: ${labels}`,
      );
    }
    if (confidence) {
      parts.push(`${TERMINAL_STRINGS.CONFIDENCE} ${Math.round(confidence.score * 100)}%`);
    }
    if (durationMs !== null) {
      parts.push(`${TERMINAL_STRINGS.TIME} ${formatDurationMs(durationMs)}`);
    }
    rows.push({
      key: `${group.key}-fields`,
      stage: 'persistence',
      level: 'info',
      message: parts.join(' | '),
      payloadAction: group.records.length > 0,
    });
  }

  return rows;
}

export function formatShortUrlLabel(url: string) {
  try {
    const parsed = new URL(url);
    const domain = parsed.hostname.replace(/^www\./, '');
    const parts = parsed.pathname.split('/').filter(Boolean);
    const lastPart = parts.at(-1) || '';
    if (parts.length > 1) {
      return `${domain}/.../${lastPart}`;
    }
    return domain + (lastPart ? `/${lastPart}` : '');
  } catch {
    return url.length > 40 ? url.slice(0, 40) + '…' : url;
  }
}

export function ShortenedUrl({ url }: { url: string }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="text-info decoration-info/20 hover:text-accent underline underline-offset-4 transition-colors"
      title={url}
      onClick={(e) => e.stopPropagation()}
    >
      {formatShortUrlLabel(url)}
    </a>
  );
}

export function renderLogContent(message: string, isStartingCrawl: boolean): React.ReactNode {
  let text = sanitizeLogMessage(message).replace(LOG_PATTERNS.ROBOTS_PREFIX, '');
  text = text.replace(
    LOG_PATTERNS.HEADLESS_BROWSER,
    (_, engine) => `Launched ${engine.trim()} browser`,
  );

  const urlRegex = LOG_PATTERNS.URL;
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match;

  while ((match = urlRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    parts.push(<ShortenedUrl key={match.index} url={match[0]} />);
    lastIndex = urlRegex.lastIndex;
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  const baseContent = parts.length > 0 ? parts : [text];

  if (isStartingCrawl) {
    return baseContent.map((part) => {
      if (typeof part === 'string') {
        const counterMatch = part.match(LOG_PATTERNS.COUNTER);
        if (counterMatch && counterMatch.index !== undefined) {
          const before = part.slice(0, counterMatch.index);
          const after = part.slice(counterMatch.index + counterMatch[0].length);
          return (
            <React.Fragment key={`${before}-${counterMatch[0]}-${after}`}>
              {before}
              <span className="text-blue-400/70">{counterMatch[0]}</span>
              {after}
            </React.Fragment>
          );
        }
      }
      return part;
    });
  }

  return baseContent;
}
