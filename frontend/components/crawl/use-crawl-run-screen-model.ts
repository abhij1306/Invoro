'use client';
import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { useCallback, useDeferredValue, useEffect, useMemo, useReducer, useRef } from 'react';
import type { HistoryItem } from '../ui/history-drawer';
import { api } from '../../lib/api';
import { getApiWebSocketBaseUrl } from '../../lib/api/client';
import type { CrawlLog, CrawlRecord } from '../../lib/api/types';
import { CRAWL_DEFAULTS } from '../../lib/constants/crawl-defaults';
import { POLLING_INTERVALS, RETRY_LIMITS } from '../../lib/constants/timing';
import { getDomain } from '../../lib/format/domain';
import { parseApiDate } from '../../lib/format/date';
import { telemetryErrorPayload, trackEvent } from '../../lib/telemetry/events';
import { cleanRecordForDisplay, mergeLogs, type OutputTabKey } from './shared';
import { useCrawlRunStore } from './crawl-run-store';
import { buildMarkdownDocument, isMarkdownOutputRun } from './markdown-output-utils';
import { buildInitialCrawlRunLocalState, crawlRunLocalReducer } from './crawl-run-state';
import { useLiveClock, useTerminalRecordSync, useTerminalSync } from './use-run-polling';
import { useRunWorkspace } from './use-run-workspace';
import { useCrawlRunController } from './use-crawl-run-controller';

function failedWithoutRecords(run: ReturnType<typeof useRunWorkspace>['run']) {
  return Boolean(
    run &&
    (run.status === 'failed' || run.status === 'proxy_exhausted') &&
    Number(run.result_summary?.record_count ?? 0) === 0,
  );
}

function resolveOutputTab(
  outputTab: OutputTabKey,
  markdown: boolean,
  learning: boolean,
  failed: boolean,
): OutputTabKey {
  if (failed && (outputTab === 'table' || outputTab === 'markdown')) {
    return 'logs';
  } else if ((outputTab === 'learning' && !learning) || outputTab === 'run_config') {
    return markdown ? 'markdown' : 'table';
  } else if (markdown && outputTab === 'table') {
    return 'markdown';
  } else if (!markdown && outputTab === 'markdown') {
    return 'table';
  }
  return outputTab;
}

function deriveOutputState(
  run: ReturnType<typeof useRunWorkspace>['run'],
  terminal: boolean,
  live: boolean,
  outputTab: OutputTabKey,
) {
  const markdownOutputRun = isMarkdownOutputRun(run);
  const showRunLearningTab = Boolean(run?.run_type === 'crawl' && terminal);
  const effectiveOutputTab = resolveOutputTab(
    outputTab,
    markdownOutputRun,
    showRunLearningTab,
    failedWithoutRecords(run),
  );
  return {
    markdownOutputRun,
    showRunLearningTab,
    effectiveOutputTab,
    shouldFetchTableRecords: Boolean(run) && effectiveOutputTab === 'table',
    shouldFetchJsonRecords:
      Boolean(run) && (effectiveOutputTab === 'json' || effectiveOutputTab === 'markdown'),
    shouldFetchLogs: Boolean(run) && (live || effectiveOutputTab === 'logs'),
  };
}

function pollInterval(enabled: boolean) {
  return enabled ? POLLING_INTERVALS.ACTIVE_JOB_MS : false;
}

function activePanelPoll(live: boolean, enabled: boolean) {
  return pollInterval(live && enabled);
}

function logPanelPoll(live: boolean, enabled: boolean, socketConnected: boolean) {
  return pollInterval(live && enabled && !socketConnected);
}

function effectiveStartTime(createdAt: string | null | undefined, fallback: number) {
  return createdAt ? parseApiDate(createdAt).getTime() : fallback;
}

function resultTotals(
  tableQuery: { data?: { meta?: { total?: number } } },
  jsonQuery: { data?: { meta?: { total?: number } } },
  tableCount: number,
  recordCount: number,
) {
  return {
    tableTotal: tableQuery.data?.meta?.total ?? tableCount,
    recordsTotal: jsonQuery.data?.meta?.total ?? recordCount,
  };
}

function hasMoreJsonPreview(
  previewCount: number,
  loadedCount: number,
  total: number,
  capped: boolean,
) {
  return previewCount < loadedCount || (loadedCount < total && !capped);
}

function terminalSyncNeeded(
  terminal: boolean,
  summaryCount: number,
  verdict: string,
  knownCount: number,
) {
  const recordsExpected =
    terminal && (summaryCount > 0 || verdict === 'success' || verdict === 'partial');
  return recordsExpected && knownCount < Math.max(1, summaryCount);
}

function both(left: boolean, right: boolean) {
  return left && right;
}

function historyItem(
  run: Awaited<ReturnType<typeof api.listCrawls>>['items'][number],
): HistoryItem {
  return {
    id: run.id,
    status: run.status,
    created_at: run.created_at,
    label: run.url ? getDomain(run.url) : 'Untitled Run',
    meta: `${run.run_type} · ${run.result_summary?.record_count ?? 0} records`,
  };
}

function elapsedTimeLabel(now: number, start: number) {
  const totalSeconds = Math.floor(Math.max(0, now - start) / 1000);
  return `${Math.floor(totalSeconds / 60)}m ${String(totalSeconds % 60).padStart(2, '0')}s`;
}

function recordsJsonValue(tab: OutputTabKey, records: CrawlRecord[]) {
  return tab === 'json' ? JSON.stringify(records.map(cleanRecordForDisplay), null, 2) : '';
}

export function useCrawlRunScreenModel(runId: number) {
  const router = useRouter();
  const selectedIds = useCrawlRunStore((state) => state.selectedIds);
  const setSelectedIds = useCrawlRunStore((state) => state.setSelectedIds);
  const outputTab = useCrawlRunStore((state) => state.outputTab);
  const setOutputTab = useCrawlRunStore((state) => state.setOutputTab);
  const tablePage = useCrawlRunStore((state) => state.tablePage);
  const setTablePage = useCrawlRunStore((state) => state.setTablePage);
  const jsonVisibleCount = useCrawlRunStore((state) => state.jsonVisibleCount);
  const setJsonVisibleCount = useCrawlRunStore((state) => state.setJsonVisibleCount);
  const alertBuilderOpen = useCrawlRunStore((state) => state.alertBuilderOpen);
  const setAlertBuilderOpen = useCrawlRunStore((state) => state.setAlertBuilderOpen);
  const historyOpen = useCrawlRunStore((state) => state.historyOpen);
  const setHistoryOpen = useCrawlRunStore((state) => state.setHistoryOpen);
  const resetWorkspaceUi = useCrawlRunStore((state) => state.resetWorkspaceUi);
  const [localState, dispatchLocal] = useReducer(
    crawlRunLocalReducer,
    undefined,
    buildInitialCrawlRunLocalState,
  );
  const {
    recipeActionPending,
    recipeActionError,
    liveJumpAvailable,
    runActionPending,
    runActionError,
    socketLogItems,
    logSocketConnected,
    sessionStartMs,
  } = localState;
  const logViewportRef = useRef<HTMLDivElement | null>(null);
  const logCursorRef = useRef<number | undefined>(undefined);
  const pollErrorEventKeysRef = useRef(new Set<string>());
  const { runQuery, run, live, terminal } = useRunWorkspace(runId);
  const localNow = useLiveClock(live);
  const { refetch: refetchRunQuery } = runQuery;
  const effectiveStartMs = effectiveStartTime(run?.created_at, sessionStartMs);
  const recordsFetchLimit = Math.min(
    800,
    Math.max(CRAWL_DEFAULTS.TABLE_PAGE_SIZE * 2, jsonVisibleCount),
  );
  const {
    markdownOutputRun,
    showRunLearningTab,
    effectiveOutputTab,
    shouldFetchTableRecords,
    shouldFetchJsonRecords,
    shouldFetchLogs,
  } = deriveOutputState(run, terminal, live, outputTab);

  const tableRecordsLimit = CRAWL_DEFAULTS.TABLE_PAGE_SIZE * 4 * tablePage;
  const tableRecordsQuery = useQuery({
    queryKey: ['crawl-records-table', runId, tableRecordsLimit],
    queryFn: () => api.getRecords(runId, { page: 1, limit: tableRecordsLimit }),
    enabled: shouldFetchTableRecords,
    refetchInterval: activePanelPoll(live, shouldFetchTableRecords),
    refetchIntervalInBackground: false,
    refetchOnMount: 'always',
  });
  const { refetch: refetchTableRecords } = tableRecordsQuery;

  const jsonRecordsQuery = useQuery({
    queryKey: ['crawl-records-json', runId, recordsFetchLimit],
    queryFn: () => api.getRecords(runId, { limit: recordsFetchLimit }),
    enabled: shouldFetchJsonRecords,
    refetchInterval: activePanelPoll(live, shouldFetchJsonRecords),
    refetchIntervalInBackground: false,
    refetchOnMount: 'always',
  });
  const { refetch: refetchJsonRecords } = jsonRecordsQuery;

  const logsQuery = useQuery({
    queryKey: ['crawl-logs', runId],
    queryFn: () => api.getCrawlLogs(runId, { limit: CRAWL_DEFAULTS.MAX_LIVE_LOGS }),
    enabled: shouldFetchLogs,
    refetchInterval: logPanelPoll(live, shouldFetchLogs, logSocketConnected),
    refetchIntervalInBackground: false,
  });
  const { refetch: refetchLogsQuery } = logsQuery;
  const domainRecipeQuery = useQuery({
    queryKey: ['crawl-domain-recipe', runId],
    queryFn: () => api.getDomainRecipe(runId),
    enabled: showRunLearningTab,
    refetchOnMount: 'always',
  });
  const { refetch: refetchDomainRecipeQuery } = domainRecipeQuery;

  const runsQuery = useQuery({
    queryKey: ['crawl-runs'],
    queryFn: () => api.listCrawls({ limit: 20 }),
  });

  const historyItems: HistoryItem[] = useMemo(() => {
    return (runsQuery.data?.items ?? []).map(historyItem);
  }, [runsQuery.data]);

  const records = useMemo(() => jsonRecordsQuery.data?.items ?? [], [jsonRecordsQuery.data?.items]);
  const markdownDocument = useMemo(() => buildMarkdownDocument(records), [records]);
  const recordsFetchCapReached = useMemo(
    () => records.length >= recordsFetchLimit && recordsFetchLimit >= 800,
    [records, recordsFetchLimit],
  );
  const tableRecords = useMemo(
    () => tableRecordsQuery.data?.items ?? [],
    [tableRecordsQuery.data?.items],
  );
  const { tableTotal, recordsTotal } = resultTotals(
    tableRecordsQuery,
    jsonRecordsQuery,
    tableRecords.length,
    records.length,
  );
  const jsonRecords = useMemo(
    () => records.slice(0, Math.min(records.length, jsonVisibleCount)),
    [records, jsonVisibleCount],
  );
  const deferredJsonRecords = useDeferredValue(jsonRecords);
  const hasMoreTableRecords = tableRecords.length < tableTotal;
  const hasMoreJsonRecords = hasMoreJsonPreview(
    jsonRecords.length,
    records.length,
    recordsTotal,
    recordsFetchCapReached,
  );
  const logs = useMemo(
    () => mergeLogs(logsQuery.data ?? [], socketLogItems),
    [logsQuery.data, socketLogItems],
  );
  const logCursorAfterId = logs.at(-1)?.id;
  const domainRecipe = domainRecipeQuery.data;
  const logSocketOnline = both(shouldFetchLogs, logSocketConnected);
  const elapsedLabel = useMemo(
    () => elapsedTimeLabel(localNow, effectiveStartMs),
    [effectiveStartMs, localNow],
  );
  const recordsJson = useMemo(
    () => recordsJsonValue(effectiveOutputTab, deferredJsonRecords),
    [deferredJsonRecords, effectiveOutputTab],
  );
  const showRunLoadingState = both(runQuery.isLoading, !run);
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
    logCursorRef.current = socketLogItems.length ? logCursorRef.current : logCursorAfterId;
  }, [logCursorAfterId, socketLogItems.length]);

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
    if (logCursorRef.current !== undefined) {
      query.set('after_id', String(logCursorRef.current));
    }
    const queryString = query.toString();
    const wsUrl = `${getApiWebSocketBaseUrl()}/api/crawls/${runId}/logs/ws${queryString ? `?${queryString}` : ''}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => dispatchLocal({ type: 'logSocketConnectionChanged', connected: true });
    ws.onclose = () => {
      dispatchLocal({ type: 'logSocketConnectionChanged', connected: false });
      // When the backend closes the stream at terminal status, refresh immediately
      // so the completed screen appears without manual page refresh.
      void refetchRunQuery();
      void refetchLogsQuery();
    };
    ws.onerror = () => dispatchLocal({ type: 'logSocketConnectionChanged', connected: false });
    ws.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data) as CrawlLog;
        if (!parsed || typeof parsed.id !== 'number') {
          return;
        }
        logCursorRef.current = parsed.id;
        dispatchLocal({ type: 'socketLogReceived', log: parsed });
      } catch {
        // Ignore malformed websocket payloads and rely on polling fallback.
      }
    };
    return () => ws.close();
  }, [refetchLogsQuery, refetchRunQuery, runId, shouldFetchLogs]);

  useEffect(() => {
    const pollErrorEventKeys = pollErrorEventKeysRef.current;
    if (!pollErrorEventKeys) {
      return;
    }
    for (const panel of panelRefreshErrors) {
      const message = panel.error instanceof Error ? panel.error.message : 'Unknown error';
      const eventKey = `${runId}:${panel.key}:${message}`;
      if (pollErrorEventKeys.has(eventKey)) {
        continue;
      }
      pollErrorEventKeys.add(eventKey);
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
        dispatchLocal({ type: 'liveJumpChanged', available: false });
      } else {
        dispatchLocal({ type: 'liveJumpChanged', available: true });
      }
    });
    return () => window.cancelAnimationFrame(frame);
  }, [logs, live]);

  const resetLogCursor = useCallback(() => {
    logCursorRef.current = undefined;
  }, []);
  const controller = useCrawlRunController({
    runId,
    run,
    terminal,
    localNow,
    effectiveStartMs,
    effectiveOutputTab,
    selectedIds,
    setSelectedIds,
    tableRecords,
    records,
    recordsTotal,
    tableRecordsQueryData: tableRecordsQuery.data,
    resetWorkspaceUi,
    resetLogCursor,
    dispatchLocal,
    router,
    runQuery,
    logsQuery,
    tableRecordsQuery,
    jsonRecordsQuery,
  });
  const {
    visibleColumns,
    visibleSelectedIds,
    batchSourceRecords,
    llmSummary,
    listingRun,
    ecommerceDetailRun,
    verdict,
    completedQualityLevel,
    emptyRecordsState,
    summaryRecordsFromRun,
    summary,
    batchFromResultsUrls,
    batchFromResultsLabel,
    downstreamRecords,
    productIntelligenceLabel,
    dataEnrichmentLabel,
    resetToConfig,
    downloadExport,
    runControl,
    triggerBatchCrawlFromResults,
    triggerProductIntelligenceFromResults,
    triggerDataEnrichmentFromResults,
    toggleRecord,
    selectAll,
  } = controller;

  const runErrorMessage =
    typeof run?.result_summary?.error === 'string' ? run.result_summary.error : '';
  const knownTableRecordsTotal = Math.max(tableTotal, tableRecordsQuery.data?.meta?.total ?? 0);
  const terminalRecordsNeedSync = terminalSyncNeeded(
    terminal,
    summaryRecordsFromRun,
    verdict,
    knownTableRecordsTotal,
  );
  useTerminalRecordSync({
    enabled: terminalRecordsNeedSync,
    intervalMs: POLLING_INTERVALS.RECORDS_MS,
    retryLimit: RETRY_LIMITS.TERMINAL_RECORDS_RETRY_LIMIT,
    runId,
    summaryRecordsFromRun,
    recordsFetchLimit,
    tableRecordsLimit,
    updatedAt: run?.updated_at ?? null,
    refetchJsonRecords,
    refetchTableRecords,
  });

  async function retryFailedPanels() {
    if (!panelRefreshErrors.length) {
      return;
    }
    await Promise.allSettled(panelRefreshErrors.map((panel) => panel.refetch()));
  }

  async function applyFieldLearningAction(
    fieldName: string,
    action: 'keep' | 'reject',
    selectorKind?: string | null,
    selectorValue?: string | null,
    sourceRecordIds?: number[],
  ) {
    const pendingKey = `field:${fieldName}:${action}` as const;
    dispatchLocal({ type: 'recipeStarted', pendingKey });
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
      dispatchLocal({
        type: 'recipeFailed',
        message:
          error instanceof Error
            ? error.message
            : `Unable to ${action} this field learning signal.`,
      });
    } finally {
      dispatchLocal({ type: 'recipeFinished' });
    }
  }

  return {
    router,
    setOutputTab,
    setTablePage,
    setJsonVisibleCount,
    alertBuilderOpen,
    setAlertBuilderOpen,
    historyOpen,
    setHistoryOpen,
    recipeActionPending,
    recipeActionError,
    liveJumpAvailable,
    runActionPending,
    runActionError,
    dispatchLocal,
    logViewportRef,
    runQuery,
    run,
    live,
    terminal,
    markdownOutputRun,
    showRunLearningTab,
    effectiveOutputTab,
    tableRecordsQuery,
    jsonRecordsQuery,
    domainRecipeQuery,
    historyItems,
    records,
    markdownDocument,
    recordsFetchCapReached,
    tableRecords,
    tableTotal,
    recordsTotal,
    jsonRecords,
    hasMoreTableRecords,
    hasMoreJsonRecords,
    logs,
    domainRecipe,
    logSocketOnline,
    elapsedLabel,
    recordsJson,
    showRunLoadingState,
    panelRefreshErrors,
    visibleColumns,
    visibleSelectedIds,
    batchSourceRecords,
    llmSummary,
    listingRun,
    ecommerceDetailRun,
    verdict,
    completedQualityLevel,
    emptyRecordsState,
    summary,
    batchFromResultsUrls,
    batchFromResultsLabel,
    downstreamRecords,
    productIntelligenceLabel,
    dataEnrichmentLabel,
    resetToConfig,
    downloadExport,
    runControl,
    triggerBatchCrawlFromResults,
    triggerProductIntelligenceFromResults,
    triggerDataEnrichmentFromResults,
    toggleRecord,
    selectAll,
    retryFailedPanels,
    applyFieldLearningAction,
  };
}

export type CrawlRunScreenModel = ReturnType<typeof useCrawlRunScreenModel>;
