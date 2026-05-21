'use client';

import * as DialogPrimitive from '@radix-ui/react-dialog';
import { useQuery } from '@tanstack/react-query';
import {
  ArrowRightCircle,
  Bell,
  Brain,
  Check,
  ChevronsDown,
  Clock,
  Copy,
  Download,
  History,
  Info,
  PackageSearch,
  Plus,
  RefreshCcw,
  Search,
  X,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useDeferredValue, useEffect, useMemo, useRef, useState } from 'react';

import { HistoryDrawer, type HistoryItem } from '../ui/history-drawer';

import { cn } from '../../lib/utils';
import { syntaxHighlightJson } from '../../lib/ui/syntax';
import {
  DataRegionEmpty,
  DataRegionLoading,
  DetailRow,
  InlineAlert,
  PageHeader,
  RunSummaryChips,
  RunWorkspaceShell,
  SectionHeader,
  TabBar,
} from '../ui/patterns';
import { Badge, Button, Card, Dropdown, Input, Textarea, Tooltip } from '../ui/primitives';
import { alertsApi, api } from '../../lib/api';
import { getApiWebSocketBaseUrl } from '../../lib/api/client';
import type {
  AlertTargetRule,
  CrawlLog,
  CrawlRecord,
  CrawlRun,
  ResultSummaryQualityLevel,
} from '../../lib/api/types';
import { CRAWL_DEFAULTS } from '../../lib/constants/crawl-defaults';
import { ACTIVE_STATUSES } from '../../lib/constants/crawl-statuses';
import { STORAGE_KEYS } from '../../lib/constants/storage-keys';
import { POLLING_INTERVALS, RETRY_LIMITS } from '../../lib/constants/timing';
import { getDomain } from '../../lib/format/domain';
import { telemetryErrorPayload, trackEvent } from '../../lib/telemetry/events';
import { parseApiDate } from '../../lib/format/date';
import { humanizeStatus, runsStatusTone as statusTone } from '../../lib/ui/status';
import {
  ActionButton,
  cleanRecordForDisplay,
  copyJson,
  extractRecordUrl,
  extractionVerdict,
  extractionVerdictTone,
  formatDuration,
  formatDurationMs,
  estimateDataQuality,
  humanizeFieldName,
  humanizeVerdict,
  humanizeQuality,
  inferDomainFromSurface,
  isEmptyCandidateValue,
  isListingRun,
  LogTerminal,
  type OutputTabKey,
  qualityTone,
  RecordsTable,
  scoreFieldQuality,
  scrollViewportToBottom,
  uniqueNumbers,
  uniqueStrings,
} from './shared';
import { useRunStatusFlags, useTerminalSync } from './use-run-polling';

type CrawlRunScreenProps = {
  runId: number;
};

function selectorWinnerLabel(selectorKind: string | null | undefined): string {
  const normalized = String(selectorKind || '')
    .trim()
    .toLowerCase();
  if (!normalized) return 'Selector winner';
  if (normalized === 'xpath') return 'XPath winner';
  if (normalized === 'css_selector') return 'CSS selector winner';
  return `${selectorKind} winner`;
}

function mergeRecords(current: CrawlRecord[], incoming: CrawlRecord[]) {
  const byId = new Map<number, CrawlRecord>();
  for (const row of current) byId.set(row.id, row);
  for (const row of incoming) byId.set(row.id, row);
  return Array.from(byId.values()).sort((a, b) => a.id - b.id);
}

function mergeLogs(current: CrawlLog[], incoming: CrawlLog[]) {
  const byId = new Map<number, CrawlLog>();
  for (const row of current) byId.set(row.id, row);
  for (const row of incoming) byId.set(row.id, row);
  return Array.from(byId.values())
    .sort((a, b) => a.id - b.id)
    .slice(-CRAWL_DEFAULTS.MAX_LIVE_LOGS);
}

function llmTouchedFieldNames(record: CrawlRecord): string[] {
  const raw =
    record.raw_data && typeof record.raw_data === 'object'
      ? (record.raw_data as Record<string, unknown>)
      : {};
  const touched = new Set<string>();
  const source = typeof raw._source === 'string' ? raw._source : '';
  if (source.startsWith('llm_')) {
    touched.add('_record');
  }
  const fieldSources =
    raw._field_sources && typeof raw._field_sources === 'object'
      ? (raw._field_sources as Record<string, unknown>)
      : {};
  for (const [fieldName, value] of Object.entries(fieldSources)) {
    if (
      Array.isArray(value) &&
      value.some((item) => typeof item === 'string' && item.startsWith('llm_'))
    ) {
      touched.add(fieldName);
    }
  }
  return Array.from(touched);
}

type ProductIntelligencePrefillPayload = {
  source_run_id: number | null;
  source_domain: string;
  records: Array<Pick<CrawlRecord, 'id' | 'run_id' | 'source_url' | 'data'>>;
};

type DataEnrichmentPrefillPayload = {
  source_run_id: number | null;
  records: Array<Pick<CrawlRecord, 'id' | 'run_id' | 'source_url' | 'data'>>;
};

export function storeProductIntelligencePrefill(
  payload: ProductIntelligencePrefillPayload,
  storage: Storage = window.sessionStorage,
) {
  try {
    storage.setItem(STORAGE_KEYS.PRODUCT_INTELLIGENCE_PREFILL, JSON.stringify(payload));
  } catch (error) {
    console.error('Unable to store full Product Intelligence prefill.', error);
    const reducedPayload = {
      ...payload,
      records: payload.records.slice(0, CRAWL_DEFAULTS.TABLE_PAGE_SIZE * 4).map((record) => ({
        id: record.id,
        run_id: record.run_id,
        source_url: record.source_url,
        data: {},
      })),
    };
    try {
      storage.setItem(STORAGE_KEYS.PRODUCT_INTELLIGENCE_PREFILL, JSON.stringify(reducedPayload));
    } catch (fallbackError) {
      console.error('Unable to store reduced Product Intelligence prefill.', fallbackError);
      storage.removeItem(STORAGE_KEYS.PRODUCT_INTELLIGENCE_PREFILL);
    }
  }
}

export function storeDataEnrichmentPrefill(
  payload: DataEnrichmentPrefillPayload,
  storage: Storage = window.sessionStorage,
) {
  const serializedPayload = JSON.stringify(payload);
  try {
    storage.setItem(STORAGE_KEYS.DATA_ENRICHMENT_PREFILL, serializedPayload);
  } catch (error) {
    console.error(
      'Unable to store Data Enrichment prefill for triggerDataEnrichmentFromResults.',
      error,
    );
    if (isStorageQuotaError(error)) {
      try {
        storage.removeItem(STORAGE_KEYS.PRODUCT_INTELLIGENCE_PREFILL);
        storage.removeItem(STORAGE_KEYS.BULK_PREFILL);
        storage.setItem(STORAGE_KEYS.DATA_ENRICHMENT_PREFILL, serializedPayload);
        return;
      } catch (fallbackError) {
        console.error(
          'Unable to store Data Enrichment prefill after clearing older keys.',
          fallbackError,
        );
      }
    }
    storage.removeItem(STORAGE_KEYS.DATA_ENRICHMENT_PREFILL);
  }
}

function isStorageQuotaError(error: unknown) {
  return (
    error instanceof DOMException &&
    (error.name === 'QuotaExceededError' || error.name === 'NS_ERROR_DOM_QUOTA_REACHED')
  );
}

export function CrawlRunScreen({ runId }: Readonly<CrawlRunScreenProps>) {
  const router = useRouter();
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [outputTab, setOutputTab] = useState<OutputTabKey>('table');
  const [recipeActionPending, setRecipeActionPending] = useState<
    `field:${string}:${'keep' | 'reject'}` | null
  >(null);
  const [recipeActionError, setRecipeActionError] = useState('');
  const [liveJumpAvailable, setLiveJumpAvailable] = useState(false);
  const [runActionPending, setRunActionPending] = useState<'kill' | null>(null);
  const [runActionError, setRunActionError] = useState('');
  const [tablePage, setTablePage] = useState(1);
  const [jsonVisibleCount, setJsonVisibleCount] = useState(CRAWL_DEFAULTS.TABLE_PAGE_SIZE * 4);
  const [alertBuilderOpen, setAlertBuilderOpen] = useState(false);
  const [socketLogItems, setSocketLogItems] = useState<CrawlLog[]>([]);
  const [logSocketConnected, setLogSocketConnected] = useState(false);
  const logViewportRef = useRef<HTMLDivElement | null>(null);
  const [sessionStartMs] = useState(() => Date.now());
  const [localNow, setLocalNow] = useState(() => Date.now());
  const pollErrorEventKeysRef = useRef<Set<string>>(new Set());
  const terminalRecordsRetryAttemptsRef = useRef(0);

  const runQuery = useQuery({
    queryKey: ['crawl-run', runId],
    queryFn: () => api.getCrawl(runId),
    refetchInterval: false,
    refetchOnMount: 'always',
  });
  const { refetch: refetchRunQuery } = runQuery;
  const run = runQuery.data;
  const { live, terminal } = useRunStatusFlags(run);
  const runCreatedMs = run?.created_at ? parseApiDate(run.created_at).getTime() : null;
  const effectiveStartMs = runCreatedMs ?? sessionStartMs;
  const recordsFetchLimit = Math.min(
    800,
    Math.max(CRAWL_DEFAULTS.TABLE_PAGE_SIZE * 2, jsonVisibleCount),
  );
  const failedRunWithoutRecords = Boolean(
    run &&
    (run.status === 'failed' || run.status === 'proxy_exhausted') &&
    Number(run?.result_summary?.record_count ?? 0) === 0,
  );
  const showRunLearningTab = Boolean(run?.run_type === 'crawl' && terminal);
  const effectiveOutputTab =
    failedRunWithoutRecords && outputTab === 'table'
      ? 'logs'
      : (outputTab === 'learning' && !showRunLearningTab) || outputTab === 'run_config'
        ? 'table'
        : outputTab;
  const shouldFetchTableRecords = Boolean(run) && effectiveOutputTab === 'table';
  const shouldFetchJsonRecords = Boolean(run) && effectiveOutputTab === 'json';
  const shouldFetchLogs = Boolean(run) && (live || effectiveOutputTab === 'logs');

  useEffect(() => {
    if (!live) return;
    const interval = setInterval(() => setLocalNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, [live]);

  const tableRecordsLimit = CRAWL_DEFAULTS.TABLE_PAGE_SIZE * 4 * tablePage;
  const tableRecordsQuery = useQuery({
    queryKey: ['crawl-records-table', runId, tableRecordsLimit],
    queryFn: () => api.getRecords(runId, { page: 1, limit: tableRecordsLimit }),
    enabled: shouldFetchTableRecords,
    refetchInterval: false,
    refetchOnMount: 'always',
  });
  const { refetch: refetchTableRecords } = tableRecordsQuery;

  const jsonRecordsQuery = useQuery({
    queryKey: ['crawl-records-json', runId, recordsFetchLimit],
    queryFn: () => api.getRecords(runId, { limit: recordsFetchLimit }),
    enabled: shouldFetchJsonRecords,
    refetchInterval: false,
    refetchOnMount: 'always',
  });
  const { refetch: refetchJsonRecords } = jsonRecordsQuery;

  const logsQuery = useQuery({
    queryKey: ['crawl-logs', runId],
    queryFn: () => api.getCrawlLogs(runId, { limit: CRAWL_DEFAULTS.MAX_LIVE_LOGS }),
    enabled: shouldFetchLogs,
    refetchInterval: false,
  });
  const { refetch: refetchLogsQuery } = logsQuery;
  const domainRecipeQuery = useQuery({
    queryKey: ['crawl-domain-recipe', runId],
    queryFn: () => api.getDomainRecipe(runId),
    enabled: showRunLearningTab,
    refetchInterval: false,
    refetchOnMount: 'always',
  });
  const { refetch: refetchDomainRecipeQuery } = domainRecipeQuery;

  const [historyOpen, setHistoryOpen] = useState(false);

  const runsQuery = useQuery({
    queryKey: ['crawl-runs'],
    queryFn: () => api.listCrawls({ limit: 20 }),
  });

  const historyItems: HistoryItem[] = useMemo(() => {
    return (runsQuery.data?.items ?? []).map((run) => ({
      id: run.id,
      status: run.status,
      created_at: run.created_at,
      label: run.url ? getDomain(run.url) : 'Untitled Run',
      meta: `${run.run_type} · ${run.result_summary?.record_count ?? 0} records`,
    }));
  }, [runsQuery.data]);

  const records = useMemo(() => jsonRecordsQuery.data?.items ?? [], [jsonRecordsQuery.data?.items]);
  const recordsFetchCapReached = useMemo(
    () => records.length >= recordsFetchLimit && recordsFetchLimit >= 800,
    [records, recordsFetchLimit],
  );
  const tableRecords = useMemo(
    () => tableRecordsQuery.data?.items ?? [],
    [tableRecordsQuery.data?.items],
  );
  const tableTotal = tableRecordsQuery.data?.meta?.total ?? tableRecords.length;
  const recordsTotal = jsonRecordsQuery.data?.meta?.total ?? records.length;
  const jsonRecords = useMemo(
    () => records.slice(0, Math.min(records.length, jsonVisibleCount)),
    [records, jsonVisibleCount],
  );
  const deferredJsonRecords = useDeferredValue(jsonRecords);
  const hasMoreTableRecords = tableRecords.length < tableTotal;
  const hasMoreJsonRecords =
    jsonRecords.length < records.length ||
    (records.length < recordsTotal && !recordsFetchCapReached);
  const logs = useMemo(
    () => mergeLogs(logsQuery.data ?? [], socketLogItems),
    [logsQuery.data, socketLogItems],
  );
  const logCursorAfterId = logs.at(-1)?.id;
  const domainRecipe = domainRecipeQuery.data;
  const logSocketOnline = shouldFetchLogs && logSocketConnected;
  const elapsedLabel = useMemo(() => {
    const elapsedMs = Math.max(0, localNow - effectiveStartMs);
    const totalS = Math.floor(elapsedMs / 1000);
    const m = Math.floor(totalS / 60);
    const s = totalS % 60;
    return `${m}m ${String(s).padStart(2, '0')}s`;
  }, [effectiveStartMs, localNow]);
  const recordsJson = useMemo(
    () =>
      effectiveOutputTab === 'json'
        ? JSON.stringify(deferredJsonRecords.map(cleanRecordForDisplay), null, 2)
        : '',
    [deferredJsonRecords, effectiveOutputTab],
  );
  const showRunLoadingState = runQuery.isLoading && !run;
  const panelRefreshErrors = useMemo(
    () =>
      [
        {
          key: 'run',
          label: 'run',
          error: runQuery.error,
          refetch: refetchRunQuery,
        },
        {
          key: 'records',
          label: 'records',
          error: tableRecordsQuery.error ?? jsonRecordsQuery.error,
          refetch: async () => {
            const tasks: Array<Promise<unknown>> = [];
            if (tableRecordsQuery.error) {
              tasks.push(refetchTableRecords());
            }
            if (jsonRecordsQuery.error) {
              tasks.push(refetchJsonRecords());
            }
            if (!tasks.length) {
              tasks.push(refetchTableRecords(), refetchJsonRecords());
            }
            await Promise.allSettled(tasks);
          },
        },
        {
          key: 'logs',
          label: 'logs',
          error: logsQuery.error,
          refetch: refetchLogsQuery,
        },
        {
          key: 'domain-recipe',
          label: 'domain recipe',
          error: domainRecipeQuery.error,
          refetch: refetchDomainRecipeQuery,
        },
      ].filter((panel) => panel.error),
    [
      runQuery.error,
      tableRecordsQuery.error,
      jsonRecordsQuery.error,
      logsQuery.error,
      domainRecipeQuery.error,
      refetchRunQuery,
      refetchTableRecords,
      refetchJsonRecords,
      refetchLogsQuery,
      refetchDomainRecipeQuery,
    ],
  );

  useTerminalSync(run, terminal, [runQuery, tableRecordsQuery, jsonRecordsQuery, logsQuery]);

  useEffect(() => {
    const isJsdom = typeof navigator !== 'undefined' && /jsdom/i.test(navigator.userAgent);
    if (
      !shouldFetchLogs ||
      typeof window === 'undefined' ||
      typeof WebSocket === 'undefined' ||
      isJsdom
    ) {
      return;
    }
    const query = new URLSearchParams();
    if (logCursorAfterId !== undefined) {
      query.set('after_id', String(logCursorAfterId));
    }
    const queryString = query.toString();
    const wsUrl = `${getApiWebSocketBaseUrl()}/api/crawls/${runId}/logs/ws${queryString ? `?${queryString}` : ''}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => setLogSocketConnected(true);
    ws.onclose = () => {
      setLogSocketConnected(false);
      // When the backend closes the stream at terminal status, refresh immediately
      // so the completed screen appears without manual page refresh.
      void refetchRunQuery();
      void refetchLogsQuery();
    };
    ws.onerror = () => setLogSocketConnected(false);
    ws.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data) as CrawlLog;
        if (!parsed || typeof parsed.id !== 'number') {
          return;
        }
        setSocketLogItems((current) => mergeLogs(current, [parsed]));
      } catch {
        // Ignore malformed websocket payloads and rely on polling fallback.
      }
    };
    return () => ws.close();
  }, [logCursorAfterId, refetchLogsQuery, refetchRunQuery, runId, shouldFetchLogs]);

  useEffect(() => {
    if (!live) {
      return;
    }

    const refetchPanels = () => {
      const tasks: Array<Promise<unknown>> = [refetchRunQuery()];
      if (shouldFetchTableRecords) {
        tasks.push(refetchTableRecords());
      }
      if (shouldFetchJsonRecords) {
        tasks.push(refetchJsonRecords());
      }
      if (shouldFetchLogs && !logSocketOnline) {
        tasks.push(refetchLogsQuery());
      }
      void Promise.allSettled(tasks);
    };

    const intervalId = window.setInterval(refetchPanels, POLLING_INTERVALS.ACTIVE_JOB_MS);
    return () => window.clearInterval(intervalId);
  }, [
    live,
    logSocketOnline,
    shouldFetchLogs,
    shouldFetchJsonRecords,
    shouldFetchTableRecords,
    refetchRunQuery,
    refetchTableRecords,
    refetchJsonRecords,
    refetchLogsQuery,
  ]);

  useEffect(() => {
    for (const panel of panelRefreshErrors) {
      const message = panel.error instanceof Error ? panel.error.message : 'Unknown error';
      const eventKey = `${runId}:${panel.key}:${message}`;
      if (pollErrorEventKeysRef.current.has(eventKey)) {
        continue;
      }
      pollErrorEventKeysRef.current.add(eventKey);
      trackEvent(
        'run_screen_poll_error_rate',
        telemetryErrorPayload(panel.error, {
          run_id: runId,
          panel: panel.key,
          live,
          terminal,
        }),
      );
    }
  }, [live, panelRefreshErrors, runId, terminal]);

  useEffect(() => {
    if (!live || !logViewportRef.current) {
      return;
    }
    const frame = window.requestAnimationFrame(() => {
      const node = logViewportRef.current;
      if (!node) {
        return;
      }
      const { scrollHeight, scrollTop, clientHeight } = node;
      const atBottom = scrollHeight - scrollTop - clientHeight < CRAWL_DEFAULTS.SCROLL_THRESHOLD_PX;
      if (atBottom) {
        node.scrollTop = scrollHeight;
        setLiveJumpAvailable(false);
      } else {
        setLiveJumpAvailable(true);
      }
    });
    return () => window.cancelAnimationFrame(frame);
  }, [logs, live]);

  const terminalRecordCount = Math.max(
    tableTotal,
    recordsTotal,
    Number(run?.result_summary?.record_count ?? 0) || 0,
  );

  const visibleColumns = useMemo(() => {
    const columns = new Set<string>();
    for (const record of [...tableRecords, ...records]) {
      for (const source of [record.data, record.raw_data]) {
        Object.keys(source ?? {}).forEach((key) => {
          const normalized = key.toLowerCase();
          if (
            !key.startsWith('_') &&
            normalized !== 'canonical_url' &&
            normalized !== 'source_run_id' &&
            normalized !== 'run_id' &&
            normalized !== 'product'
          ) {
            columns.add(key);
          }
        });
      }
    }
    const URL_KEYS = new Set(['url', 'source_url', 'product_url']);
    const sorted = Array.from(columns).sort((a, b) => {
      const aIsUrl = URL_KEYS.has(a.toLowerCase());
      const bIsUrl = URL_KEYS.has(b.toLowerCase());
      if (aIsUrl && !bIsUrl) return -1;
      if (!aIsUrl && bIsUrl) return 1;
      return 0;
    });
    return sorted;
  }, [tableRecords, records]);

  const filteredTableRecords = tableRecords;
  const visibleRecordIds = useMemo(
    () =>
      new Set(
        (effectiveOutputTab === 'table' ? filteredTableRecords : records).map(
          (record) => record.id,
        ),
      ),
    [effectiveOutputTab, filteredTableRecords, records],
  );
  const visibleSelectedIds = useMemo(
    () => selectedIds.filter((id) => visibleRecordIds.has(id)),
    [selectedIds, visibleRecordIds],
  );

  const selectedRecords = useMemo(
    () =>
      (effectiveOutputTab === 'table' ? filteredTableRecords : records).filter((record) =>
        visibleSelectedIds.includes(record.id),
      ),
    [effectiveOutputTab, filteredTableRecords, records, visibleSelectedIds],
  );
  const batchSourceRecords = useMemo(
    () => (tableRecords.length ? tableRecords : records),
    [records, tableRecords],
  );
  const llmSummary = useMemo(() => {
    const llmRequested = Boolean(run?.settings?.llm_enabled);
    const touchedFields = new Set<string>();
    let touchedRecords = 0;
    for (const record of batchSourceRecords) {
      const fields = llmTouchedFieldNames(record);
      if (!fields.length) {
        continue;
      }
      touchedRecords += 1;
      fields.forEach((fieldName) => touchedFields.add(fieldName));
    }
    return {
      requested: llmRequested,
      touchedRecords,
      touchedFields: touchedFields.size,
    };
  }, [batchSourceRecords, run?.settings?.llm_enabled]);
  const resultUrls = useMemo(
    () => uniqueStrings(batchSourceRecords.map((record) => extractRecordUrl(record))),
    [batchSourceRecords],
  );
  const selectedResultUrls = useMemo(
    () => uniqueStrings(selectedRecords.map((record) => extractRecordUrl(record))),
    [selectedRecords],
  );
  const listingRun = useMemo(() => isListingRun(run), [run]);
  const ecommerceDetailRun = String(run?.surface ?? '') === 'ecommerce_detail';
  const verdict = extractionVerdict(run);
  const runErrorMessage =
    typeof run?.result_summary?.error === 'string' ? run.result_summary.error : '';
  const persistedQualityLevel = useMemo(() => {
    const level = String(run?.result_summary?.quality_summary?.level ?? '')
      .trim()
      .toLowerCase();
    if (level === 'high' || level === 'medium' || level === 'low' || level === 'unknown') {
      return level as ResultSummaryQualityLevel;
    }
    return null;
  }, [run?.result_summary?.quality_summary?.level]);
  const quality = useMemo(
    () => estimateDataQuality(tableRecords.length ? tableRecords : records, visibleColumns),
    [tableRecords, records, visibleColumns],
  );
  const completedQualityLevel = terminal ? (persistedQualityLevel ?? quality.level) : quality.level;
  const emptyRecordsState =
    verdict === 'blocked'
      ? {
          title: 'Access blocked',
          description:
            'The target site blocked acquisition for this run. Check Logs or browser diagnostics for challenge details.',
        }
      : {
          title: 'No records captured yet',
          description: 'Records will appear here once extraction returns rows.',
        };
  const batchFromResultsUrls = selectedResultUrls.length ? selectedResultUrls : resultUrls;
  const batchFromResultsLabel = selectedResultUrls.length
    ? `Batch Crawl Selected (${selectedResultUrls.length})`
    : `Batch Crawl (${resultUrls.length})`;
  const productIntelligenceRecords = selectedRecords.length ? selectedRecords : batchSourceRecords;
  const productIntelligenceLabel = selectedRecords.length
    ? `Product Intelligence Selected (${selectedRecords.length})`
    : `Product Intelligence (${productIntelligenceRecords.length})`;
  const dataEnrichmentRecords = selectedRecords.length ? selectedRecords : batchSourceRecords;
  const dataEnrichmentLabel = selectedRecords.length
    ? `Enrich Selected (${selectedRecords.length})`
    : `Enrich Records (${dataEnrichmentRecords.length})`;

  const summaryRecordsFromRun = Number(run?.result_summary?.record_count ?? 0) || 0;
  const summaryRecordsFromTable =
    Number(tableRecordsQuery.data?.meta?.total ?? tableRecordsQuery.data?.items?.length ?? 0) || 0;
  const summaryPagesFromRun =
    Number(run?.result_summary?.processed_urls ?? run?.result_summary?.completed_urls ?? 0) || 0;
  const summaryCurrentUrlIndex = Number(run?.result_summary?.current_url_index ?? 0) || 0;
  const summary = {
    records: Math.max(summaryRecordsFromRun, recordsTotal, summaryRecordsFromTable),
    pages: Math.max(
      summaryPagesFromRun,
      summaryCurrentUrlIndex,
      Number(run?.result_summary?.progress ?? 0) > 0 ? 1 : 0,
    ),
    fields: visibleColumns.length,
    duration:
      (terminal ? formatDurationMs(run?.result_summary?.duration_ms) : null) ??
      formatDuration(
        new Date(effectiveStartMs).toISOString(),
        terminal ? run?.completed_at : new Date(localNow).toISOString(),
      ),
  };

  const knownTableRecordsTotal = Math.max(tableTotal, tableRecordsQuery.data?.meta?.total ?? 0);
  const terminalRecordsExpected =
    terminal && (summaryRecordsFromRun > 0 || verdict === 'success' || verdict === 'partial');
  const terminalRecordsNeedSync =
    terminalRecordsExpected && knownTableRecordsTotal < Math.max(1, summaryRecordsFromRun);

  useEffect(() => {
    if (!terminalRecordsNeedSync) {
      terminalRecordsRetryAttemptsRef.current = 0;
      return;
    }

    const intervalId = window.setInterval(() => {
      if (terminalRecordsRetryAttemptsRef.current >= RETRY_LIMITS.TERMINAL_RECORDS_RETRY_LIMIT) {
        window.clearInterval(intervalId);
        return;
      }
      terminalRecordsRetryAttemptsRef.current += 1;
      void Promise.allSettled([refetchTableRecords(), refetchJsonRecords()]);
    }, POLLING_INTERVALS.RECORDS_MS);

    return () => window.clearInterval(intervalId);
  }, [refetchJsonRecords, refetchTableRecords, terminalRecordsNeedSync]);

  function downloadExport(kind: 'csv' | 'json') {
    setRunActionError('');
    const filename = `run-${runId}.${kind}`;
    try {
      const href = kind === 'csv' ? api.exportCsv(runId) : api.exportJson(runId);
      const anchor = document.createElement('a');
      anchor.href = href;
      anchor.download = filename;
      anchor.style.display = 'none';
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
    } catch (error) {
      setRunActionError(error instanceof Error ? error.message : 'Unable to download export.');
    }
  }

  async function runControl() {
    setRunActionPending('kill');
    setRunActionError('');
    try {
      await api.killCrawl(runId);
      await Promise.all([
        runQuery.refetch(),
        logsQuery.refetch(),
        tableRecordsQuery.refetch(),
        jsonRecordsQuery.refetch(),
      ]);
    } catch (error) {
      setRunActionError(error instanceof Error ? error.message : 'Unable to kill crawl.');
    } finally {
      setRunActionPending(null);
    }
  }

  function resetToConfig() {
    router.replace('/crawl?module=category&mode=single');
  }

  async function retryFailedPanels() {
    if (!panelRefreshErrors.length) {
      return;
    }
    await Promise.allSettled(panelRefreshErrors.map((panel) => panel.refetch()));
  }

  function triggerBatchCrawlFromResults() {
    const urls = batchFromResultsUrls;
    if (!urls.length) {
      return;
    }
    const domain = inferDomainFromSurface(run?.surface) ?? 'commerce';
    window.sessionStorage.setItem(
      STORAGE_KEYS.BULK_PREFILL,
      JSON.stringify({
        domain,
        urls,
      }),
    );
    router.replace('/crawl?module=pdp&mode=batch');
  }

  function triggerProductIntelligenceFromResults() {
    if (!productIntelligenceRecords.length) {
      return;
    }
    storeProductIntelligencePrefill({
      source_run_id: run?.id ?? null,
      source_domain: run?.url ?? '',
      records: productIntelligenceRecords.map((record) => ({
        id: record.id,
        run_id: record.run_id,
        source_url: record.source_url,
        data: record.data,
      })),
    });
    router.replace('/product-intelligence');
  }

  function triggerDataEnrichmentFromResults() {
    if (!dataEnrichmentRecords.length) {
      return;
    }
    storeDataEnrichmentPrefill({
      source_run_id: run?.id ?? null,
      records: dataEnrichmentRecords.map((record) => ({
        id: record.id,
        run_id: record.run_id,
        source_url: record.source_url,
        data: record.data,
      })),
    });
    router.replace('/data-enrichment');
  }

  async function applyFieldLearningAction(
    fieldName: string,
    action: 'keep' | 'reject',
    selectorKind?: string | null,
    selectorValue?: string | null,
    sourceRecordIds?: number[],
  ) {
    const pendingKey = `field:${fieldName}:${action}` as const;
    setRecipeActionPending(pendingKey);
    setRecipeActionError('');
    try {
      await api.applyDomainRecipeFieldAction(runId, {
        field_name: fieldName,
        action,
        selector_kind: selectorKind ?? null,
        selector_value: selectorValue ?? null,
        source_record_ids: sourceRecordIds ?? [],
      });
      await refetchDomainRecipeQuery();
    } catch (error) {
      setRecipeActionError(
        error instanceof Error ? error.message : `Unable to ${action} this field learning signal.`,
      );
    } finally {
      setRecipeActionPending(null);
    }
  }

  if (runQuery.error) {
    return (
      <div className="page-stack">
        <PageHeader
          title="Crawl Studio"
          actions={
            <Button variant="action" type="button" size="sm" onClick={resetToConfig}>
              <Plus className="size-3" />
              New Crawl
            </Button>
          }
        />
        <Card className="space-y-3 px-6 py-8">
          <SectionHeader
            title="Unable to Load Crawl"
            description="The run workspace could not be restored."
          />
          <div className="text-danger type-body">
            {runQuery.error instanceof Error
              ? runQuery.error.message
              : 'Unknown crawl loading error.'}
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="page-stack gap-4">
      <PageHeader
        title={
          run?.url ? (
            <span className="inline-flex items-baseline gap-1.5">
              Run Details:{' '}
              <a
                href={run.url}
                target="_blank"
                rel="noreferrer"
                className="link-accent type-body leading-inherit underline-offset-2 hover:underline"
              >
                {getDomain(run.url).toLowerCase()}
              </a>
            </span>
          ) : (
            'Crawl Results'
          )
        }
        actions={
          <Button variant="action" type="button" size="sm" onClick={resetToConfig}>
            <Plus className="size-3" />
            New Crawl
          </Button>
        }
      />

      {showRunLoadingState ? (
        <Card className="space-y-3 px-6 py-8">
          <SectionHeader
            title="Loading Crawl"
            description="Fetching run details and restoring the workspace."
          />
          <div className="text-muted type-body leading-[var(--leading-relaxed)]">
            Run #{runId} is loading.
          </div>
        </Card>
      ) : null}

      {panelRefreshErrors.length ? (
        <Card className="space-y-3">
          <SectionHeader
            title="Some live panels failed to refresh"
            description="Data may be stale until these requests recover."
          />
          <InlineAlert
            message={
              <div className="space-y-1">
                {panelRefreshErrors.map((panel) => (
                  <div key={panel.key}>
                    Unable to refresh {panel.label}:{' '}
                    {panel.error instanceof Error ? panel.error.message : 'Unknown error.'}
                  </div>
                ))}
              </div>
            }
          />
          <div>
            <Button
              variant="neutral"
              type="button"
              size="sm"
              onClick={() => void retryFailedPanels()}
            >
              Retry failed panels
            </Button>
          </div>
        </Card>
      ) : null}
      {!showRunLoadingState && !terminal ? (
        <Card className="section-card overflow-hidden">
          <header className="border-border flex h-10 items-center justify-between border-b bg-[color-mix(in_srgb,var(--bg-alt)_40%,var(--bg-panel))] px-4">
            <span className="type-label-mono text-secondary flex items-center gap-2">
              Live Log Stream
              {logSocketOnline ? (
                <span
                  className="bg-success inline-block size-1.5 animate-pulse rounded-full"
                  aria-label="Connected"
                />
              ) : (
                <span
                  className="bg-muted inline-block size-1.5 rounded-full"
                  aria-label="Disconnected"
                />
              )}
            </span>
            <div className="flex items-center gap-3">
              {run ? (
                <span className="border-divider bg-background-elevated text-foreground type-body inline-flex h-8 items-center gap-1.5 rounded-[var(--radius-sm)] border px-3 tabular-nums">
                  <Clock className="size-3.5" />
                  {elapsedLabel}
                </span>
              ) : null}

              {liveJumpAvailable ? (
                <button
                  type="button"
                  onClick={() => {
                    scrollViewportToBottom(logViewportRef);
                    setLiveJumpAvailable(false);
                  }}
                  className="bg-background-alt shadow-card type-control inline-flex items-center gap-1 rounded-[var(--radius-md)] px-2.5 py-1.5"
                >
                  <ChevronsDown className="size-3.5" aria-hidden="true" />
                  Jump to Latest
                </button>
              ) : null}
              <ActionButton
                label={runActionPending === 'kill' ? 'Killing...' : 'Hard Kill'}
                onClick={() => void runControl()}
                disabled={!run || !ACTIVE_STATUSES.has(run.status) || runActionPending !== null}
                danger
              />
            </div>
          </header>
          <LogTerminal
            logs={logs}
            records={batchSourceRecords}
            requestedFields={run?.requested_fields ?? []}
            live
            viewportRef={logViewportRef}
          />
        </Card>
      ) : null}

      {!showRunLoadingState && terminal ? (
        <div className="space-y-4">
          <Card className="section-card">
            {runErrorMessage ? <InlineAlert tone="danger" message={runErrorMessage} /> : null}
            {runActionError ? <InlineAlert tone="danger" message={runActionError} /> : null}
            <RunWorkspaceShell
              header={
                run?.url ? (
                  <a
                    href={run.url}
                    target="_blank"
                    rel="noreferrer"
                    className="link-accent type-body block truncate underline-offset-2 hover:underline"
                  >
                    {run.url}
                  </a>
                ) : (
                  <p className="text-muted type-body">Waiting for completed run data.</p>
                )
              }
              actions={
                <>
                  {listingRun && batchFromResultsUrls.length ? (
                    <Button
                      variant="action"
                      type="button"
                      size="sm"
                      onClick={triggerBatchCrawlFromResults}
                    >
                      <ArrowRightCircle className="size-3" />
                      {batchFromResultsLabel}
                    </Button>
                  ) : null}
                  {listingRun && productIntelligenceRecords.length ? (
                    <Button
                      variant="neutral"
                      type="button"
                      size="sm"
                      onClick={triggerProductIntelligenceFromResults}
                    >
                      <Brain className="size-3" />
                      {productIntelligenceLabel}
                    </Button>
                  ) : null}
                  {ecommerceDetailRun && dataEnrichmentRecords.length ? (
                    <Button
                      variant="action"
                      type="button"
                      size="sm"
                      onClick={triggerDataEnrichmentFromResults}
                    >
                      <Brain className="size-3" />
                      {dataEnrichmentLabel}
                    </Button>
                  ) : null}
                  <Button
                    variant="download"
                    type="button"
                    size="sm"
                    onClick={() => void downloadExport('csv')}
                  >
                    <Download className="size-3" />
                    Excel (CSV)
                  </Button>
                  <Button
                    variant="download"
                    type="button"
                    size="sm"
                    onClick={() => void downloadExport('json')}
                  >
                    <Download className="size-3" />
                    JSON
                  </Button>
                  <Button
                    variant="neutral"
                    type="button"
                    size="sm"
                    onClick={() => setHistoryOpen(true)}
                  >
                    <History className="size-3" />
                    History
                  </Button>
                </>
              }
              tabs={
                <TabBar
                  value={effectiveOutputTab}
                  variant="underline"
                  onChange={(value) => setOutputTab(value as OutputTabKey)}
                  options={[
                    { value: 'table', label: `Table (${summary.records})` },
                    { value: 'json', label: 'JSON' },
                    { value: 'logs', label: 'Logs' },
                    ...(showRunLearningTab ? [{ value: 'learning', label: 'Learning' }] : []),
                  ]}
                />
              }
              summary={
                <div className="flex flex-wrap items-center justify-end gap-2.5">
                  {llmSummary.requested ? (
                    <Badge
                      tone={llmSummary.touchedRecords > 0 ? 'accent' : 'neutral'}
                      title={
                        llmSummary.touchedRecords > 0
                          ? `LLM used ${llmSummary.touchedRecords} record(s) / ${llmSummary.touchedFields} field(s)`
                          : 'LLM enabled, no visible repair'
                      }
                    >
                      {llmSummary.touchedRecords > 0
                        ? `LLM used ${llmSummary.touchedRecords} rec / ${llmSummary.touchedFields} fld`
                        : 'LLM on, no visible repair'}
                    </Badge>
                  ) : (
                    <Badge tone="neutral">LLM off</Badge>
                  )}
                  <RunSummaryChips
                    duration={summary.duration}
                    verdict={humanizeVerdict(verdict).toLowerCase()}
                    quality={humanizeQuality(completedQualityLevel).toLowerCase()}
                  />
                </div>
              }
              content={
                <>
                  {effectiveOutputTab === 'table' ? (
                    <div className="min-h-[55vh] space-y-3">
                      {tableRecordsQuery.isLoading && !tableRecords.length ? (
                        <DataRegionLoading count={5} className="px-0" />
                      ) : tableRecords.length ? (
                        <div className="space-y-3">
                          <RecordsTable
                            records={filteredTableRecords}
                            visibleColumns={visibleColumns}
                            selectedIds={visibleSelectedIds}
                            onSelectAll={(checked) =>
                              setSelectedIds(
                                checked ? filteredTableRecords.map((record) => record.id) : [],
                              )
                            }
                            onToggleRow={(id, checked) =>
                              setSelectedIds((current) =>
                                checked
                                  ? uniqueNumbers([...current, id])
                                  : current.filter((value) => value !== id),
                              )
                            }
                          />
                          {hasMoreTableRecords ? (
                            <div className="surface-muted text-muted type-body flex items-center justify-between rounded-[var(--radius-md)] px-6 py-2">
                              <span>
                                Showing {tableRecords.length} of {tableTotal} records
                              </span>
                              <Button
                                variant="neutral"
                                type="button"
                                onClick={() => setTablePage((current) => current + 1)}
                              >
                                Load More
                              </Button>
                            </div>
                          ) : null}
                          {hasMoreTableRecords ? (
                            <InlineAlert
                              tone="warning"
                              message={`Table view is currently showing ${tableRecords.length} of ${tableTotal} records. Load more rows or export JSON/CSV for the full dataset.`}
                            />
                          ) : null}
                        </div>
                      ) : (
                        <DataRegionEmpty
                          title={emptyRecordsState.title}
                          description={emptyRecordsState.description}
                          className="px-0"
                        />
                      )}
                    </div>
                  ) : null}

                  {effectiveOutputTab === 'json' ? (
                    <div className="relative min-h-[55vh]">
                      <div className="absolute top-2 right-2 z-10 flex items-center gap-2">
                        {ecommerceDetailRun && records.length ? (
                          <Button
                            variant="action"
                            type="button"
                            onClick={() => setAlertBuilderOpen(true)}
                          >
                            <Bell className="size-3.5" />
                            Alert
                          </Button>
                        ) : null}
                        <Button
                          variant="quiet"
                          type="button"
                          onClick={() => void copyJson(records)}
                        >
                          <Copy className="size-3.5" />
                          Copy
                        </Button>
                      </div>
                      <pre
                        className="crawl-terminal crawl-terminal-json max-h-[72vh] min-h-[55vh]"
                        dangerouslySetInnerHTML={{ __html: syntaxHighlightJson(recordsJson) }}
                      />
                      {hasMoreJsonRecords ? (
                        <div className="surface-muted text-muted type-body mt-2 flex items-center justify-between rounded-[var(--radius-md)] px-6 py-2">
                          <span>
                            JSON previewing {jsonRecords.length} of {recordsTotal} records
                          </span>
                          <Button
                            variant="neutral"
                            type="button"
                            onClick={() =>
                              setJsonVisibleCount(
                                (current) => current + CRAWL_DEFAULTS.TABLE_PAGE_SIZE * 4,
                              )
                            }
                          >
                            Load More JSON
                          </Button>
                        </div>
                      ) : null}
                      {records.length < recordsTotal && recordsFetchCapReached ? (
                        <InlineAlert
                          tone="warning"
                          message={`JSON preview capped at ${records.length} records for performance. Use JSON export for all ${recordsTotal} records.`}
                        />
                      ) : null}
                    </div>
                  ) : null}

                  {effectiveOutputTab === 'logs' ? (
                    <div className="min-h-[55vh]">
                      <LogTerminal
                        logs={logs}
                        records={batchSourceRecords}
                        requestedFields={run?.requested_fields ?? []}
                        viewportRef={logViewportRef}
                      />
                    </div>
                  ) : null}

                  {effectiveOutputTab === 'learning' ? (
                    <div className="min-h-[55vh] space-y-4">
                      {domainRecipeQuery.isLoading ? (
                        <Card className="section-card">
                          <SectionHeader
                            title="Run Learning"
                            description="Loading keep and reject recommendations for this run."
                          />
                        </Card>
                      ) : domainRecipe ? (
                        <div className="space-y-4">
                          {recipeActionError ? (
                            <InlineAlert tone="danger" message={recipeActionError} />
                          ) : null}
                          <Card className="section-card space-y-4">
                            <SectionHeader
                              title="Run Learning"
                              description={`Review extraction evidence for ${domainRecipe.domain} on ${domainRecipe.surface}. Keep what should compound, reject what should not.`}
                            />
                            <div className="grid gap-3 md:grid-cols-2">
                              <div className="surface-muted text-secondary type-body rounded-[var(--radius-md)] px-6 py-3 leading-[var(--leading-relaxed)]">
                                <div className="field-label mb-1">Requested Coverage</div>
                                Requested:{' '}
                                {domainRecipe.requested_field_coverage.requested.join(', ') ||
                                  'None'}
                                <br />
                                Found:{' '}
                                {domainRecipe.requested_field_coverage.found.join(', ') || 'None'}
                                <br />
                                Missing:{' '}
                                {domainRecipe.requested_field_coverage.missing.join(', ') || 'None'}
                              </div>
                              <div className="surface-muted text-secondary type-body rounded-[var(--radius-md)] px-6 py-3 leading-[var(--leading-relaxed)]">
                                <div className="field-label mb-1">Acquisition Evidence</div>
                                Method:{' '}
                                {domainRecipe.acquisition_evidence.actual_fetch_method || '—'}
                                <br />
                                Browser Used:{' '}
                                {domainRecipe.acquisition_evidence.browser_used ? 'Yes' : 'No'}
                                <br />
                                Browser Reason:{' '}
                                {domainRecipe.acquisition_evidence.browser_reason || '—'}
                                <br />
                                Cookie Memory:{' '}
                                {domainRecipe.acquisition_evidence.cookie_memory_available
                                  ? 'Saved'
                                  : domainRecipe.acquisition_evidence.browser_used
                                    ? 'No reusable state observed'
                                    : 'Not applicable'}
                              </div>
                            </div>

                            <div className="space-y-3">
                              <div>
                                <div className="field-label mb-0">Field Learning</div>
                                <p className="text-secondary type-body mt-1">
                                  Keep accepted field evidence or reject bad field evidence for
                                  future runs on this domain and surface.
                                </p>
                              </div>
                              {domainRecipe.field_learning.length ? (
                                <div className="space-y-2">
                                  {domainRecipe.field_learning.map((item) => {
                                    const keepPending =
                                      recipeActionPending === `field:${item.field_name}:keep`;
                                    const rejectPending =
                                      recipeActionPending === `field:${item.field_name}:reject`;
                                    return (
                                      <DetailRow
                                        key={`${item.field_name}:${item.selector_kind ?? 'source'}:${item.selector_value ?? item.source_labels.join(',')}`}
                                      >
                                        <div className="flex flex-wrap items-start justify-between gap-3">
                                          <div className="min-w-0 flex-1">
                                            <div className="flex flex-wrap items-center gap-2">
                                              <span className="type-control text-foreground">
                                                {item.field_name}
                                              </span>
                                              {item.selector_kind ? (
                                                <Badge tone="info">{item.selector_kind}</Badge>
                                              ) : (
                                                <Badge tone="neutral">non-selector</Badge>
                                              )}
                                              {item.feedback ? (
                                                <Badge
                                                  tone={
                                                    item.feedback.action === 'reject'
                                                      ? 'warning'
                                                      : 'success'
                                                  }
                                                >
                                                  {item.feedback.action}
                                                </Badge>
                                              ) : null}
                                            </div>
                                            <div className="type-caption text-muted mt-1">
                                              {selectorWinnerLabel(item.selector_kind)} · Sources:{' '}
                                              {item.source_labels.join(', ') || '—'}
                                            </div>
                                            {item.selector_value ? (
                                              <code className="type-caption-mono text-secondary mt-2 block truncate">
                                                {item.selector_value}
                                              </code>
                                            ) : null}
                                          </div>
                                          <div className="flex flex-wrap gap-2">
                                            <Button
                                              variant="neutral"
                                              type="button"
                                              size="sm"
                                              disabled={recipeActionPending !== null}
                                              onClick={() =>
                                                void applyFieldLearningAction(
                                                  item.field_name,
                                                  'keep',
                                                  item.selector_kind,
                                                  item.selector_value,
                                                  item.source_record_ids,
                                                )
                                              }
                                            >
                                              {keepPending ? 'Keeping…' : 'Keep'}
                                            </Button>
                                            <Button
                                              variant="quiet"
                                              type="button"
                                              size="sm"
                                              disabled={recipeActionPending !== null}
                                              onClick={() =>
                                                void applyFieldLearningAction(
                                                  item.field_name,
                                                  'reject',
                                                  item.selector_kind,
                                                  item.selector_value,
                                                  item.source_record_ids,
                                                )
                                              }
                                            >
                                              {rejectPending ? 'Rejecting…' : 'Reject'}
                                            </Button>
                                          </div>
                                        </div>
                                      </DetailRow>
                                    );
                                  })}
                                </div>
                              ) : (
                                <div className="surface-muted rounded-[var(--radius-lg)] border border-dashed px-6 py-3">
                                  <p className="type-body text-secondary m-0">
                                    No field learning signals were captured for this run.
                                  </p>
                                </div>
                              )}
                            </div>
                          </Card>
                        </div>
                      ) : (
                        <DataRegionEmpty
                          title="No learning data available"
                          description="This run did not produce reusable field-learning evidence."
                          className="px-0"
                        />
                      )}
                    </div>
                  ) : null}
                </>
              }
            />
          </Card>
        </div>
      ) : null}
      <AlertBuilderDrawer
        open={alertBuilderOpen}
        onOpenChange={setAlertBuilderOpen}
        records={records}
        run={run}
        onCreated={(alertId) => router.push(`/alerts/${alertId}`)}
      />
      <HistoryDrawer
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        items={historyItems}
        activeId={runId}
        onSelect={(id) => router.push(`/crawl?run_id=${id}`)}
        title="Crawl History"
      />
    </div>
  );
}

type AlertBuilderDrawerProps = Readonly<{
  open: boolean;
  onOpenChange: (open: boolean) => void;
  records: CrawlRecord[];
  run: CrawlRun | undefined;
  onCreated: (alertId: number) => void;
}>;

type AlertRuleDraft = AlertTargetRule & {
  id: string;
};

const alertIntervalOptions = [
  { value: '60', label: '1 min' },
  { value: '300', label: '5 min' },
  { value: '900', label: '15 min' },
  { value: '1800', label: '30 min' },
  { value: '3600', label: '1 hour' },
];

const alertOperatorOptions = [
  { value: 'changed', label: 'Changed' },
  { value: 'equals', label: 'Equals' },
  { value: 'not_equals', label: 'Not equals' },
  { value: 'less_than', label: 'Less than' },
  { value: 'greater_than', label: 'Greater than' },
  { value: 'exists', label: 'Exists' },
  { value: 'missing', label: 'Missing' },
];

function AlertBuilderDrawer({
  open,
  onOpenChange,
  records,
  run,
  onCreated,
}: AlertBuilderDrawerProps) {
  const [selectedRecordId, setSelectedRecordId] = useState('');
  const [rules, setRules] = useState<AlertRuleDraft[]>([]);
  const [pollInterval, setPollInterval] = useState('300');
  const [webhookUrl, setWebhookUrl] = useState('');
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);

  const selectedRecord = useMemo(() => {
    return records.find((record) => String(record.id) === selectedRecordId) ?? records[0];
  }, [records, selectedRecordId]);
  const selectedData = useMemo(() => recordData(selectedRecord), [selectedRecord]);
  const variants = useMemo(() => productVariants(selectedData), [selectedData]);
  const rootFields = useMemo(() => alertRootFields(selectedData), [selectedData]);
  const variantFields = useMemo(() => alertVariantFields(variants), [variants]);
  const recordOptions = useMemo(
    () =>
      records.map((record) => ({
        value: String(record.id),
        label: alertRecordLabel(record),
      })),
    [records],
  );

  function toggleRule(nextRule: AlertRuleDraft) {
    setRules((current) => {
      const existing = current.find((rule) => alertRuleSignature(rule) === alertRuleSignature(nextRule));
      if (existing) {
        return current.filter((rule) => rule.id !== existing.id);
      }
      return [...current, nextRule];
    });
  }

  function updateRule(id: string, patch: Partial<AlertRuleDraft>) {
    setRules((current) =>
      current.map((rule) => (rule.id === id ? { ...rule, ...patch } : rule)),
    );
  }

  async function createAlert() {
    setError('');
    if (!selectedRecord) {
      setError('No product record selected.');
      return;
    }
    if (!rules.length) {
      setError('Select at least one alert rule.');
      return;
    }
    const cleanWebhook = webhookUrl.trim();
    if (cleanWebhook && !/^https?:\/\//i.test(cleanWebhook)) {
      setError('Webhook URL must start with http:// or https://.');
      return;
    }
    const url = alertRecordUrl(selectedRecord, run);
    if (!url) {
      setError('Selected record has no URL.');
      return;
    }
    setPending(true);
    try {
      const targetRules = rules.map(({ id: _id, ...rule }) => ({
        ...rule,
        value: needsAlertRuleValue(rule.operator) ? rule.value : undefined,
      }));
      const alert = await alertsApi.create({
        url,
        target_fields: alertTargetFields(targetRules),
        target_rules: targetRules,
        condition: null,
        webhook_url: cleanWebhook || null,
        poll_interval_seconds: Number.parseInt(pollInterval, 10),
      });
      onOpenChange(false);
      onCreated(alert.id);
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : 'Unable to create alert.');
    } finally {
      setPending(false);
    }
  }

  return (
    <DialogPrimitive.Root open={open} onOpenChange={(nextOpen) => !pending && onOpenChange(nextOpen)}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-[100] bg-[color-mix(in_srgb,var(--bg-base)_34%,black)] animate-[fade-in_200ms_ease-out]" />
        <DialogPrimitive.Content className="border-border bg-background shadow-elevated fixed top-0 right-0 z-[101] flex h-dvh w-[min(720px,100vw)] flex-col border-l animate-[slide-in-right_250ms_cubic-bezier(0.16,1,0.3,1)]">

          {/* ── Sticky header ── */}
          <div className="border-border flex-none border-b px-6 py-5">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <DialogPrimitive.Title className="type-heading-1 m-0 flex items-center gap-2.5">
                  <span className="bg-accent/10 text-accent inline-flex size-8 items-center justify-center rounded-[var(--radius-md)]">
                    <Bell className="size-4" />
                  </span>
                  Alert Builder
                </DialogPrimitive.Title>
                <DialogPrimitive.Description className="text-muted type-body-sm mt-2 flex items-center gap-1.5 truncate">
                  {alertRecordUrl(selectedRecord, run) || 'No product URL'}
                </DialogPrimitive.Description>
              </div>
              <DialogPrimitive.Close asChild>
                <Button type="button" variant="quiet" size="icon" aria-label="Close" disabled={pending}>
                  <X className="size-4" />
                </Button>
              </DialogPrimitive.Close>
            </div>
          </div>

          {/* ── Scrollable body ── */}
          <div className="flex-1 overflow-y-auto px-6 py-5">
            {error ? <div className="mb-4"><InlineAlert tone="danger" message={error} /></div> : null}

            <div className="space-y-6">

              {/* ── Step 1: Record selector ── */}
              {recordOptions.length > 1 ? (
                <section>
                  <DrawerStepHeader step={1} title="Select Record" />
                  <div className="mt-3">
                    <Dropdown
                      value={selectedRecord ? String(selectedRecord.id) : ''}
                      onChange={setSelectedRecordId}
                      options={recordOptions}
                      ariaLabel="Record"
                      portal={false}
                    />
                  </div>
                </section>
              ) : null}

              {/* ── Step 2: Product fields ── */}
              <section>
                <DrawerStepHeader step={recordOptions.length > 1 ? 2 : 1} title="Product Fields" subtitle="Select fields to monitor for changes" />
                <div className="mt-3 grid gap-2.5 sm:grid-cols-2">
                  {rootFields.map((field) => {
                    const rule = buildAlertRule({
                      path: field,
                      label: `Product ${humanizeFieldName(field).toLowerCase()}`,
                    });
                    const isActive = rules.some((item) => alertRuleSignature(item) === alertRuleSignature(rule));
                    return (
                      <AlertFieldCard
                        key={field}
                        active={isActive}
                        label={humanizeFieldName(field)}
                        value={formatAlertValue(selectedData[field])}
                        onClick={() => toggleRule(rule)}
                      />
                    );
                  })}
                </div>
              </section>

              {/* ── Step 3: Variants ── */}
              {variants.length ? (
                <section>
                  <DrawerStepHeader
                    step={recordOptions.length > 1 ? 3 : 2}
                    title="Variants"
                    subtitle={`${variants.length} variant${variants.length !== 1 ? 's' : ''} detected`}
                  />

                  {/* Quick-select pills */}
                  <div className="mt-3 flex flex-wrap gap-2">
                    {variantFields.map((field) => {
                      const rule = buildAlertRule({
                        path: `variants[*].${field}`,
                        label: `Any variant ${humanizeFieldName(field).toLowerCase()}`,
                      });
                      return (
                        <Button
                          key={field}
                          type="button"
                          variant={
                            rules.some((item) => alertRuleSignature(item) === alertRuleSignature(rule))
                              ? 'action'
                              : 'neutral'
                          }
                          size="sm"
                          onClick={() => toggleRule(rule)}
                        >
                          <Bell className="size-3.5" />
                          Any {humanizeFieldName(field)}
                        </Button>
                      );
                    })}
                  </div>

                  {/* Per-variant cards */}
                  <div className="mt-3 space-y-2">
                    {variants.slice(0, 12).map((variant, index) => {
                      const hasActiveRule = variantFields.some((field) => {
                        const rule = buildAlertRule({
                          path: `variants[*].${field}`,
                          label: '',
                          variant_match: variantMatch(variant),
                        });
                        return rules.some((item) => alertRuleSignature(item) === alertRuleSignature(rule));
                      });
                      return (
                        <div
                          key={variantIdentity(variant, index)}
                          className={cn(
                            'border-border bg-panel rounded-[var(--radius-md)] border p-3 transition-colors',
                            hasActiveRule && 'border-l-accent border-l-2',
                          )}
                        >
                          <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2">
                            <span className="text-foreground type-body-sm font-semibold">
                              {variantTitle(variant, index)}
                            </span>
                            <Badge tone="neutral">
                              {formatAlertValue(variant.availability ?? variant.price ?? variant.sku)}
                            </Badge>
                          </div>
                          <div className="flex flex-wrap gap-2">
                            {variantFields.slice(0, 5).map((field) => {
                              const rule = buildAlertRule({
                                path: `variants[*].${field}`,
                                label: `${variantTitle(variant, index)} ${humanizeFieldName(field).toLowerCase()}`,
                                variant_match: variantMatch(variant),
                              });
                              return (
                                <Button
                                  key={field}
                                  type="button"
                                  size="sm"
                                  variant={
                                    rules.some(
                                      (item) => alertRuleSignature(item) === alertRuleSignature(rule),
                                    )
                                      ? 'action'
                                      : 'quiet'
                                  }
                                  onClick={() => toggleRule(rule)}
                                >
                                  {humanizeFieldName(field)}
                                </Button>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </section>
              ) : null}

              {/* ── Divider ── */}
              <hr className="border-border" />

              {/* ── Active rules ── */}
              <section>
                <DrawerStepHeader
                  step={recordOptions.length > 1 ? (variants.length ? 4 : 3) : (variants.length ? 3 : 2)}
                  title="Active Rules"
                  subtitle={rules.length ? `${rules.length} rule${rules.length !== 1 ? 's' : ''} configured` : undefined}
                />
                {rules.length ? (
                  <div className="mt-3 space-y-2">
                    {rules.map((rule) => (
                      <div
                        key={rule.id}
                        className="border-border bg-panel grid gap-3 rounded-[var(--radius-md)] border p-3.5 md:grid-cols-[1fr_150px_140px_auto]"
                      >
                        <div className="min-w-0">
                          <div className="text-foreground type-body-sm truncate font-semibold">
                            {rule.label || rule.path}
                          </div>
                          <div className="text-muted type-body-sm mt-0.5 truncate">{rule.path}</div>
                        </div>
                        <Dropdown
                          value={rule.operator || 'changed'}
                          onChange={(operator) => updateRule(rule.id, { operator })}
                          options={alertOperatorOptions}
                          ariaLabel="Operator"
                          size="sm"
                          portal={false}
                        />
                        {needsAlertRuleValue(rule.operator) ? (
                          <Input
                            value={String(rule.value ?? '')}
                            onChange={(event) => updateRule(rule.id, { value: event.target.value })}
                            placeholder="Value"
                          />
                        ) : (
                          <div />
                        )}
                        <Button
                          type="button"
                          variant="quiet"
                          size="icon"
                          aria-label="Remove rule"
                          onClick={() =>
                            setRules((current) => current.filter((item) => item.id !== rule.id))
                          }
                        >
                          <X className="size-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="mt-3">
                    <InlineAlert tone="warning" message="Click product fields or variant attributes above to add alert rules." />
                  </div>
                )}
              </section>

              {/* ── Settings panel ── */}
              <section className="bg-background-alt rounded-[var(--radius-lg)] p-4">
                <h3 className="type-body-sm text-foreground mb-3 font-semibold flex items-center gap-2">
                  <Clock className="text-muted size-4" />
                  Alert Settings
                </h3>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="grid gap-1.5">
                    <span className="field-label">Poll Interval</span>
                    <Dropdown
                      value={pollInterval}
                      onChange={setPollInterval}
                      options={alertIntervalOptions}
                      ariaLabel="Poll Interval"
                      portal={false}
                    />
                  </div>
                  <div className="grid gap-1.5">
                    <span className="field-label">Webhook URL</span>
                    <Input
                      value={webhookUrl}
                      onChange={(event) => setWebhookUrl(event.target.value)}
                      placeholder="https://agent.example/webhook"
                    />
                  </div>
                </div>
              </section>
            </div>
          </div>

          {/* ── Sticky footer ── */}
          <div className="border-border flex-none border-t bg-background px-6 py-4">
            <div className="flex items-center justify-between">
              <span className="type-body-sm text-muted">
                {rules.length ? `${rules.length} rule${rules.length !== 1 ? 's' : ''} selected` : 'No rules selected'}
              </span>
              <div className="flex gap-2">
                <Button type="button" variant="quiet" onClick={() => onOpenChange(false)} disabled={pending}>
                  Cancel
                </Button>
                <Button type="button" onClick={() => void createAlert()} disabled={pending || !rules.length}>
                  {pending ? 'Creating…' : 'Create Alert'}
                </Button>
              </div>
            </div>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

function DrawerStepHeader({ step, title, subtitle }: Readonly<{ step: number; title: string; subtitle?: string }>) {
  return (
    <div className="flex items-center gap-3">
      <span className="bg-accent text-accent-fg inline-flex size-6 items-center justify-center rounded-full text-xs font-bold">
        {step}
      </span>
      <div className="min-w-0">
        <h3 className="type-heading-3 m-0">{title}</h3>
        {subtitle ? <p className="text-muted type-body-sm m-0">{subtitle}</p> : null}
      </div>
    </div>
  );
}

function AlertFieldCard({
  active,
  label,
  value,
  onClick,
}: Readonly<{ active: boolean; label: string; value: string; onClick: () => void }>) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'group border-border bg-panel text-left rounded-[var(--radius-md)] border p-3.5 transition-all',
        'hover:shadow-card hover:border-accent/50',
        active && 'border-accent bg-accent-subtle shadow-card',
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-foreground type-body-sm block font-semibold">{label}</span>
        {active ? (
          <span className="bg-accent text-accent-fg inline-flex size-5 shrink-0 items-center justify-center rounded-full">
            <Check className="size-3" />
          </span>
        ) : (
          <span className="border-border group-hover:border-accent/40 inline-flex size-5 shrink-0 items-center justify-center rounded-full border transition-colors" />
        )}
      </div>
      <span className="text-secondary type-body-sm mt-1.5 block truncate">{value}</span>
    </button>
  );
}

function buildAlertRule(rule: Omit<AlertRuleDraft, 'id' | 'operator'> & { operator?: string }) {
  return {
    ...rule,
    id: `${rule.path}:${JSON.stringify(rule.variant_match ?? {})}`,
    operator: rule.operator ?? 'changed',
  };
}

function alertRuleSignature(rule: AlertTargetRule) {
  return `${rule.path}:${JSON.stringify(rule.variant_match ?? {})}`;
}

function needsAlertRuleValue(operator: string | undefined) {
  return ['equals', 'not_equals', 'less_than', 'greater_than'].includes(operator ?? '');
}

function alertTargetFields(rules: AlertTargetRule[]) {
  return uniqueStrings(
    rules.map((rule) => (rule.path.startsWith('variants[*].') ? 'variants' : rule.path.split('.')[0])),
  );
}

function recordData(record: CrawlRecord | undefined) {
  return record?.data && typeof record.data === 'object'
    ? (record.data as Record<string, unknown>)
    : {};
}

function productVariants(data: Record<string, unknown>) {
  return Array.isArray(data.variants)
    ? data.variants.filter(isRecordObject).map((item) => item as Record<string, unknown>)
    : [];
}

function alertRootFields(data: Record<string, unknown>) {
  const preferred = ['price', 'availability', 'sku', 'title', 'brand', 'currency', 'image_url'];
  return preferred.filter((field) => data[field] !== undefined && !isEmptyCandidateValue(data[field]));
}

function alertVariantFields(variants: Array<Record<string, unknown>>) {
  const preferred = ['availability', 'price', 'sku', 'size', 'color', 'currency'];
  const present = new Set<string>();
  variants.forEach((variant) => {
    preferred.forEach((field) => {
      if (variant[field] !== undefined && !isEmptyCandidateValue(variant[field])) {
        present.add(field);
      }
    });
  });
  return preferred.filter((field) => present.has(field));
}

function variantMatch(variant: Record<string, unknown>) {
  if (variant.sku) return { sku: variant.sku };
  const match: Record<string, unknown> = {};
  if (variant.size) match.size = variant.size;
  if (variant.color) match.color = variant.color;
  if (Object.keys(match).length) return match;
  if (variant.url) return { url: variant.url };
  return null;
}

function variantIdentity(variant: Record<string, unknown>, index: number) {
  return String(variant.sku || variant.url || `${variant.size || ''}:${variant.color || ''}:${index}`);
}

function variantTitle(variant: Record<string, unknown>, index: number) {
  const parts = [variant.size, variant.color, variant.sku].filter(Boolean).map(String);
  return parts.length ? parts.join(' · ') : `Variant ${index + 1}`;
}

function alertRecordLabel(record: CrawlRecord) {
  const data = recordData(record);
  return String(data.title || data.sku || data.url || record.source_url || `Record ${record.id}`);
}

function alertRecordUrl(record: CrawlRecord | undefined, run: CrawlRun | undefined) {
  if (!record) return '';
  const data = recordData(record);
  return String(data.url || record.source_url || run?.url || '');
}

function formatAlertValue(value: unknown) {
  if (value === null || value === undefined || value === '') return 'empty';
  if (Array.isArray(value)) return `${value.length} items`;
  if (isRecordObject(value)) return JSON.stringify(value);
  return String(value);
}

function isRecordObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value));
}
