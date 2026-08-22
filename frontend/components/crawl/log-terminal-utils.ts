import type { CrawlLog, CrawlRecord } from '../../lib/api/types';
import { acquisitionDiagnosticsSummary } from './crawl-diagnostics';

export function logMessageIsError(level: string, message: string): boolean {
  const normalizedLevel = String(level || '').toLowerCase();
  if (normalizedLevel === 'error') return true;
  if (normalizedLevel) return false;
  const text = String(message || '');
  const lowered = text.toLowerCase();
  if (
    /\b(no|not|none|no longer)\s+(error|errors|failed)\b/i.test(text) ||
    lowered.includes('no errors found') ||
    lowered.includes('validation failed check passed')
  ) {
    return false;
  }
  return /^\s*(error|failed)\b/i.test(text);
}

export type LogStage = 'acquisition' | 'extraction' | 'normalize' | 'persistence' | 'system';

export interface LogStageConfig {
  label: string;
  borderClass: string;
  chipClass: string;
  textOnlyClass: string;
  panelClass: string;
}

const DISPLAY_LOG_STAGES: LogStage[] = ['acquisition', 'extraction', 'normalize', 'persistence'];

export const STAGE_CONFIG: Record<LogStage, LogStageConfig> = {
  acquisition: {
    label: 'Acquire',
    borderClass: 'border-info/30',
    chipClass: 'bg-info text-white font-medium',
    textOnlyClass: 'text-info font-medium',
    panelClass: 'border-info/20 bg-info-bg',
  },
  extraction: {
    label: 'Extract',
    borderClass: 'border-accent/30',
    chipClass: 'bg-accent text-accent-fg font-medium',
    textOnlyClass: 'text-accent font-medium',
    panelClass: 'border-accent/20 bg-accent-subtle',
  },
  normalize: {
    label: 'Normalize',
    borderClass: 'border-warning/30',
    chipClass: 'bg-warning text-white font-bold',
    textOnlyClass: 'text-warning font-bold',
    panelClass: 'border-warning/20 bg-warning-bg',
  },
  persistence: {
    label: 'Persist',
    borderClass: 'border-info/30',
    chipClass: 'bg-info text-white font-bold',
    textOnlyClass: 'text-info font-bold',
    panelClass: 'border-info/20 bg-info-bg',
  },
  system: {
    label: 'Run',
    borderClass: 'border-border-strong',
    chipClass: 'bg-zinc-700 text-white font-medium',
    textOnlyClass: 'text-muted font-medium',
    panelClass: 'border-border bg-subtle-panel',
  },
};

export const TERMINAL_STRINGS = {
  FIELDS: 'Fields',
  CONFIDENCE: 'Confidence',
  TIME: 'Time',
  RUN_EVENTS: 'Run Events',
  PENDING: 'Pending…',
  SITE_PAYLOAD: 'Site payload',
  PAYLOAD_PEEK: 'Payload Peek',
  NO_LOGS: 'No logs.',
  NO_PAYLOAD: 'No persisted payload for this site yet.',
} as const;

export const LOG_PATTERNS = {
  STARTING_CRAWL: /^Starting crawl run for (https?:\/\/\S+?)(?: \((\d+)\/(\d+)\))?$/i,
  ROBOTS_IGNORE: /ignoring robots\.txt/i,
  PERSISTENCE_SUMMARY: /\bpersisted\s+\d+\s+record/i,
  ROBOTS_PREFIX: /^\[ROBOTS\]\s*/i,
  HEADLESS_BROWSER: /launched headless browser \(([^,]+),[^)]+\)/i,
  URL_PREFIX: /^\[url:(https?:\/\/[^\s\]]+)\]\s*/i,
  URL: /https?:\/\/[^\s]+/g,
  COUNTER: /\(\d+\/\d+\)/,
} as const;

const LOG_STAGE_SIGNALS: Array<[LogStage, string[]]> = [
  ['persistence', ['persisted', 'persisting', 'committed']],
  ['normalize', ['normalized', 'normalised', 'schema validation cleaned']],
  [
    'extraction',
    [
      'extracted',
      'extraction yielded',
      'rejected detail extraction',
      'traversal yielded',
      'selector self-heal',
    ],
  ],
  [
    'acquisition',
    ['acquiring', 'robots', 'proxy', 'browser', 'navigation', 'page loaded', 'acquired payload'],
  ],
];

export function getLogStage(message: string): LogStage {
  const text = message.toLowerCase();
  return (
    LOG_STAGE_SIGNALS.find(([, signals]) => signals.some((signal) => text.includes(signal)))?.[0] ??
    'system'
  );
}

export type LogSiteGroup = {
  key: string;
  label: string;
  url: string;
  index: number | null;
  total: number | null;
  logs: CrawlLog[];
  stageLogs: Record<LogStage, CrawlLog[]>;
  records: CrawlRecord[];
  hasError: boolean;
  hasWarning: boolean;
  lastStage: LogStage;
  recordCount: number;
};

export function sanitizeLogMessage(message: string) {
  return String(message || '')
    .replace(LOG_PATTERNS.URL_PREFIX, '')
    .replace(/\s*\[corr=[^\]]+\]/gi, '')
    .replace(/\s{2,}/g, ' ')
    .trim();
}

export function parseStartingLog(message: string) {
  const match = sanitizeLogMessage(message).match(LOG_PATTERNS.STARTING_CRAWL);
  if (!match) {
    return null;
  }
  const [, url, indexValue, totalValue] = match;
  return {
    url,
    index: indexValue ? Number.parseInt(indexValue, 10) : null,
    total: totalValue ? Number.parseInt(totalValue, 10) : null,
  };
}

export function isPersistenceSummaryLog(message: string) {
  return LOG_PATTERNS.PERSISTENCE_SUMMARY.test(String(message || ''));
}

function isWarningLog(log: CrawlLog) {
  const level = String(log.level || '').toLowerCase();
  if (level === 'warn' || level === 'warning') {
    return true;
  }
  const text = String(log.message || '').toLowerCase();
  return (
    text.includes('partial') ||
    text.includes('yielded 0 records') ||
    text.includes('retrying') ||
    text.includes('rejected detail extraction')
  );
}

function isHiddenLogMessage(message: string) {
  return LOG_PATTERNS.ROBOTS_IGNORE.test(String(message || ''));
}

function matchesSiteUrl(record: CrawlRecord, siteUrl: string) {
  const candidates = new Set<string>();
  for (const value of [
    record.source_url,
    record.data?.url,
    record.raw_data?.url,
    acquisitionDiagnosticsSummary(record).finalUrl,
  ]) {
    const text = typeof value === 'string' ? value.trim() : '';
    if (text) {
      candidates.add(text);
    }
  }
  return candidates.has(siteUrl);
}

function siteLabel(url: string, index: number | null, total: number | null) {
  const prefix = index && total ? `${index}/${total}` : index ? String(index) : null;
  return prefix ? `${prefix} ${url}` : url;
}

export function siteDomId(groupKey: string) {
  return `site-log-${groupKey.replace(/[^a-z0-9_-]+/gi, '-')}`;
}

type LogSiteGroupDraft = Omit<
  LogSiteGroup,
  'records' | 'hasError' | 'hasWarning' | 'lastStage' | 'recordCount'
>;

function emptyStageLogs(): Record<LogStage, CrawlLog[]> {
  return {
    acquisition: [],
    extraction: [],
    normalize: [],
    persistence: [],
    system: [],
  };
}

function createSiteGroup({
  key,
  url,
  index,
  total,
}: {
  key: string;
  url: string;
  index: number | null;
  total: number | null;
}): LogSiteGroupDraft {
  return {
    key,
    label: siteLabel(url, index, total),
    url,
    index,
    total,
    logs: [],
    stageLogs: emptyStageLogs(),
  };
}

function createRunGroup(key: string): LogSiteGroupDraft {
  return {
    key,
    label: TERMINAL_STRINGS.RUN_EVENTS,
    url: '',
    index: null,
    total: null,
    logs: [],
    stageLogs: emptyStageLogs(),
  };
}

function addLogToGroup(group: LogSiteGroupDraft, log: CrawlLog, stage: LogStage) {
  group.logs.push(log);
  group.stageLogs[stage].push(log);
}

function firstUrlInLog(message: string): string {
  return sanitizeLogMessage(message).match(/https?:\/\/[^\s]+/i)?.[0] ?? '';
}

export function buildLogSiteGroups(logs: CrawlLog[], records: CrawlRecord[] = []): LogSiteGroup[] {
  const state = createLogGroupingState(logs);
  for (const [logIndex, log] of logs.entries()) {
    if (isHiddenLogMessage(log.message)) continue;
    if (routePrefixedLog(state, log)) continue;
    if (routeStartingLog(state, log, logIndex)) continue;
    if (routeInferredLog(state, log)) continue;
    routeFallbackLog(state, log);
  }
  flushPendingRunLogs(state);
  return state.groups.map((group) => finalizeLogGroup(group, records));
}

type LogGroupingState = {
  groups: LogSiteGroupDraft[];
  groupMap: Map<string, LogSiteGroupDraft>;
  activeGroupKeyByUrl: Map<string, string>;
  currentGroup: LogSiteGroupDraft | null;
  pendingRunLogs: CrawlLog[];
  untitledCounter: number;
  isParallel: boolean;
};

function createLogGroupingState(logs: CrawlLog[]): LogGroupingState {
  return {
    groups: [],
    groupMap: new Map(),
    activeGroupKeyByUrl: new Map(),
    currentGroup: null,
    pendingRunLogs: [],
    untitledCounter: 0,
    isParallel: logs.some((log) => LOG_PATTERNS.URL_PREFIX.test(log.message)),
  };
}

function registerSiteGroup(state: LogGroupingState, group: LogSiteGroupDraft) {
  state.groups.push(group);
  state.groupMap.set(group.key, group);
  state.activeGroupKeyByUrl.set(group.url, group.key);
}

function routePrefixedLog(state: LogGroupingState, log: CrawlLog) {
  const match = log.message.match(LOG_PATTERNS.URL_PREFIX);
  if (!match) return false;
  const url = match[1];
  const groupKey = state.activeGroupKeyByUrl.get(url);
  let group = groupKey ? state.groupMap.get(groupKey) : undefined;
  if (!group) {
    group = createSiteGroup({
      key: `site:prefixed:${log.id}:${url}`,
      url,
      index: null,
      total: null,
    });
    registerSiteGroup(state, group);
  }
  const cleanLog = { ...log, message: log.message.replace(LOG_PATTERNS.URL_PREFIX, '') };
  addLogToGroup(group, cleanLog, getLogStage(cleanLog.message));
  state.currentGroup = group;
  return true;
}

function routeStartingLog(state: LogGroupingState, log: CrawlLog, logIndex: number) {
  const start = parseStartingLog(log.message);
  if (!start) return false;
  flushPendingRunLogs(state);
  const group = createSiteGroup({
    key: `site:${start.index ?? logIndex}:${log.id}:${start.url}`,
    url: start.url,
    index: start.index,
    total: start.total,
  });
  registerSiteGroup(state, group);
  addLogToGroup(group, log, 'system');
  state.currentGroup = group;
  return true;
}

function routeInferredLog(state: LogGroupingState, log: CrawlLog) {
  const url = firstUrlInLog(log.message);
  if (!url) return false;
  const groupKey = state.activeGroupKeyByUrl.get(url);
  let group = groupKey ? state.groupMap.get(groupKey) : undefined;
  if (!group && (state.currentGroup === null || state.isParallel)) {
    group = createSiteGroup({
      key: `site:inferred:${log.id}:${url}`,
      url,
      index: null,
      total: null,
    });
    registerSiteGroup(state, group);
    attachPendingLogs(state, group);
  }
  if (!group) return false;
  addLogToGroup(group, log, getLogStage(log.message));
  state.currentGroup = group;
  return true;
}

function routeFallbackLog(state: LogGroupingState, log: CrawlLog) {
  if (!state.currentGroup) {
    state.pendingRunLogs.push(log);
    return;
  }
  addLogToGroup(state.currentGroup, log, getLogStage(log.message));
}

function attachPendingLogs(state: LogGroupingState, group: LogSiteGroupDraft) {
  if (state.currentGroup || !state.pendingRunLogs.length) return;
  for (const log of state.pendingRunLogs) addLogToGroup(group, log, getLogStage(log.message));
  state.pendingRunLogs = [];
}

function flushPendingRunLogs(state: LogGroupingState) {
  if (!state.pendingRunLogs.length) return;
  state.untitledCounter += 1;
  const group = createRunGroup(`run:${state.untitledCounter}`);
  for (const log of state.pendingRunLogs) addLogToGroup(group, log, getLogStage(log.message));
  state.groups.push(group);
  state.pendingRunLogs = [];
}

function finalizeLogGroup(group: LogSiteGroupDraft, records: CrawlRecord[]): LogSiteGroup {
  const matchedRecords = group.url
    ? records.filter((record) => matchesSiteUrl(record, group.url))
    : [];
  const lastStage = ([...DISPLAY_LOG_STAGES, 'system'] as LogStage[]).reduce(
    (last, stage) => (group.stageLogs[stage].length ? stage : last),
    'system' as LogStage,
  );
  const hasError = group.logs.some((log) => logMessageIsError(log.level, log.message));
  return {
    ...group,
    records: matchedRecords,
    hasError,
    hasWarning: !hasError && group.logs.some(isWarningLog),
    lastStage,
    recordCount: matchedRecords.length,
  };
}
