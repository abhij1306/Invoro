'use client';

import type { AppRouterInstance } from 'next/dist/shared/lib/app-router-context.shared-runtime';
import { useEffect, useMemo } from 'react';

import { api } from '../../lib/api';
import type { CrawlRecord, CrawlRun, ResultSummaryQualityLevel } from '../../lib/api/types';
import { STORAGE_KEYS } from '../../lib/constants/storage-keys';
import {
  estimateDataQuality,
  extractRecordUrl,
  extractionVerdict,
  formatDuration,
  formatDurationMs,
  inferDomainFromSurface,
  isListingRun,
  uniqueStrings,
} from './shared';
import type { OutputTabKey } from './shared';
import { storeDataEnrichmentPrefill, storeProductIntelligencePrefill } from './crawl-run-prefill';
import { llmFieldSourceSummary } from './crawl-diagnostics';
import type { CrawlRunLocalAction } from './crawl-run-state';

type Refetchable = { refetch: () => Promise<unknown> };

type ControllerOptions = {
  runId: number;
  run: CrawlRun | undefined;
  terminal: boolean;
  localNow: number;
  effectiveStartMs: number;
  effectiveOutputTab: OutputTabKey;
  selectedIds: number[];
  setSelectedIds: (next: number[] | ((current: number[]) => number[])) => void;
  tableRecords: CrawlRecord[];
  records: CrawlRecord[];
  recordsTotal: number;
  tableRecordsQueryData?: { items?: CrawlRecord[]; meta?: { total?: number } };
  resetWorkspaceUi: () => void;
  resetLogCursor: () => void;
  dispatchLocal: React.Dispatch<CrawlRunLocalAction>;
  router: AppRouterInstance;
  runQuery: Refetchable;
  logsQuery: Refetchable;
  tableRecordsQuery: Refetchable;
  jsonRecordsQuery: Refetchable;
};

export function useCrawlRunController(options: ControllerOptions) {
  const {
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
    tableRecordsQueryData,
    resetWorkspaceUi,
    resetLogCursor,
    dispatchLocal,
    router,
    runQuery,
    logsQuery,
    tableRecordsQuery,
    jsonRecordsQuery,
  } = options;

  useEffect(() => {
    resetWorkspaceUi();
    resetLogCursor();
    dispatchLocal({ type: 'runChanged', sessionStartMs: Date.now() });
  }, [dispatchLocal, resetLogCursor, resetWorkspaceUi, runId]);

  const visibleColumns = useMemo(() => {
    const columns = new Set<string>();
    const columnSourceRecords = records.length ? records : tableRecords;
    for (const record of columnSourceRecords) {
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
    const urlKeys = new Set(['url', 'source_url', 'product_url']);
    return Array.from(columns).sort((a, b) => {
      const aIsUrl = urlKeys.has(a.toLowerCase());
      const bIsUrl = urlKeys.has(b.toLowerCase());
      if (aIsUrl && !bIsUrl) return -1;
      if (!aIsUrl && bIsUrl) return 1;
      return 0;
    });
  }, [records, tableRecords]);

  const visibleRecords = recordsForOutputTab(effectiveOutputTab, tableRecords, records);
  const visibleRecordIds = useMemo(
    () => new Set(visibleRecords.map((record) => record.id)),
    [visibleRecords],
  );
  const visibleSelectedIds = useMemo(
    () => selectedIds.filter((id) => visibleRecordIds.has(id)),
    [selectedIds, visibleRecordIds],
  );
  const selectedRecords = useMemo(
    () =>
      visibleRecords.filter(
        (record) => record.run_id === runId && visibleSelectedIds.includes(record.id),
      ),
    [runId, visibleRecords, visibleSelectedIds],
  );
  const batchSourceRecords = preferredRecords(tableRecords, records);
  const resultUrls = useMemo(
    () => uniqueStrings(batchSourceRecords.map((record) => extractRecordUrl(record))),
    [batchSourceRecords],
  );
  const selectedResultUrls = useMemo(
    () => uniqueStrings(selectedRecords.map((record) => extractRecordUrl(record))),
    [selectedRecords],
  );
  const llmSummary = useMemo(() => {
    const touchedFields = new Set<string>();
    let touchedRecords = 0;
    for (const record of batchSourceRecords) {
      const fields = llmFieldSourceSummary(record).touchedFieldNames;
      if (!fields.length) continue;
      touchedRecords += 1;
      fields.forEach((fieldName) => touchedFields.add(fieldName));
    }
    return {
      requested: Boolean(run?.settings?.llm_enabled),
      touchedRecords,
      touchedFields: touchedFields.size,
    };
  }, [batchSourceRecords, run?.settings?.llm_enabled]);

  const listingRun = isListingRun(run);
  const ecommerceDetailRun = isEcommerceDetailRun(run);
  const verdict = extractionVerdict(run);
  const persistedQualityLevel = useMemo(() => {
    const level = String(run?.result_summary?.quality_summary?.level ?? '')
      .trim()
      .toLowerCase();
    return level === 'high' || level === 'medium' || level === 'low' || level === 'unknown'
      ? (level as ResultSummaryQualityLevel)
      : null;
  }, [run?.result_summary?.quality_summary?.level]);
  const quality = useMemo(
    () => estimateDataQuality(batchSourceRecords, visibleColumns),
    [batchSourceRecords, visibleColumns],
  );
  const completedQualityLevel = resolveCompletedQualityLevel(
    terminal,
    persistedQualityLevel,
    quality.level,
  );
  const emptyRecordsState = emptyStateForVerdict(verdict);
  const { summaryRecordsFromRun, summary } = buildRunSummary({
    run,
    terminal,
    localNow,
    effectiveStartMs,
    recordsTotal,
    tableRecordsQueryData,
    visibleColumnCount: visibleColumns.length,
  });
  const batchFromResultsUrls = preferredValues(selectedResultUrls, resultUrls);
  const downstreamRecords = preferredValues(selectedRecords, batchSourceRecords);
  const labels = buildResultActionLabels(
    selectedResultUrls,
    resultUrls,
    selectedRecords,
    downstreamRecords,
  );

  function toggleRecord(id: number, checked: boolean) {
    setSelectedIds((current) =>
      checked ? Array.from(new Set([...current, id])) : current.filter((value) => value !== id),
    );
  }

  function selectAll(recordIds: number[]) {
    setSelectedIds(Array.from(new Set(recordIds)));
  }

  function resetToConfig() {
    router.replace('/crawl?module=category&mode=single');
  }

  function downloadExport(kind: 'csv' | 'json') {
    dispatchLocal({ type: 'runActionErrorCleared' });
    try {
      const anchor = document.createElement('a');
      anchor.href = kind === 'csv' ? api.exportCsv(runId) : api.exportJson(runId);
      anchor.download = `run-${runId}.${kind}`;
      anchor.style.display = 'none';
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
    } catch (error) {
      dispatchLocal({
        type: 'runActionFailed',
        message: error instanceof Error ? error.message : 'Unable to download export.',
      });
    }
  }

  async function runControl() {
    dispatchLocal({ type: 'runActionStarted', pendingKey: 'kill' });
    try {
      await api.killCrawl(runId);
      await Promise.all([
        runQuery.refetch(),
        logsQuery.refetch(),
        tableRecordsQuery.refetch(),
        jsonRecordsQuery.refetch(),
      ]);
    } catch (error) {
      dispatchLocal({
        type: 'runActionFailed',
        message: error instanceof Error ? error.message : 'Unable to kill crawl.',
      });
    } finally {
      dispatchLocal({ type: 'runActionFinished' });
    }
  }

  function triggerBatchCrawlFromResults() {
    if (!batchFromResultsUrls.length) return;
    window.sessionStorage.setItem(
      STORAGE_KEYS.BULK_PREFILL,
      JSON.stringify({
        domain: inferDomainFromSurface(run?.surface) ?? 'commerce',
        urls: batchFromResultsUrls,
      }),
    );
    router.replace('/crawl?module=pdp&mode=batch');
  }

  function triggerProductIntelligenceFromResults() {
    if (!downstreamRecords.length) return;
    storeProductIntelligencePrefill({
      source_run_id: run?.id ?? null,
      source_domain: run?.url ?? '',
      records: downstreamRecords.map(({ id, run_id, source_url, data }) => ({
        id,
        run_id,
        source_url,
        data,
      })),
    });
    router.replace('/product-intelligence');
  }

  function triggerDataEnrichmentFromResults() {
    if (!downstreamRecords.length) return;
    storeDataEnrichmentPrefill({
      source_run_id: run?.id ?? null,
      records: downstreamRecords.map(({ id, run_id, source_url, data }) => ({
        id,
        run_id,
        source_url,
        data,
      })),
    });
    router.replace('/data-enrichment');
  }

  return {
    visibleColumns,
    visibleSelectedIds,
    selectedRecords,
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
    batchFromResultsLabel: labels.batch,
    downstreamRecords,
    productIntelligenceLabel: labels.intelligence,
    dataEnrichmentLabel: labels.enrichment,
    toggleRecord,
    selectAll,
    resetToConfig,
    downloadExport,
    runControl,
    triggerBatchCrawlFromResults,
    triggerProductIntelligenceFromResults,
    triggerDataEnrichmentFromResults,
  };
}

function recordsForOutputTab(
  tab: OutputTabKey,
  tableRecords: CrawlRecord[],
  records: CrawlRecord[],
) {
  return tab === 'table' ? tableRecords : records;
}

function preferredRecords(primary: CrawlRecord[], fallback: CrawlRecord[]) {
  return primary.length ? primary : fallback;
}

function preferredValues<T>(primary: T[], fallback: T[]) {
  return primary.length ? primary : fallback;
}

function isEcommerceDetailRun(run: CrawlRun | undefined) {
  return run?.surface === 'ecommerce_detail';
}

function resolveCompletedQualityLevel(
  terminal: boolean,
  persisted: ResultSummaryQualityLevel | null,
  estimated: ResultSummaryQualityLevel,
) {
  if (!terminal) return estimated;
  return persisted ?? estimated;
}

function emptyStateForVerdict(verdict: string) {
  if (verdict === 'blocked')
    return {
      title: 'Access blocked',
      description:
        'The target site blocked acquisition for this run. Check Logs or browser diagnostics for challenge details.',
    };
  return {
    title: 'No records captured yet',
    description: 'Records will appear here once extraction returns rows.',
  };
}

function buildRunSummary({
  run,
  terminal,
  localNow,
  effectiveStartMs,
  recordsTotal,
  tableRecordsQueryData,
  visibleColumnCount,
}: Pick<
  ControllerOptions,
  'run' | 'terminal' | 'localNow' | 'effectiveStartMs' | 'recordsTotal' | 'tableRecordsQueryData'
> & { visibleColumnCount: number }) {
  const counts = runSummaryCounts(run, tableRecordsQueryData);
  const duration = runSummaryDuration(run, terminal, localNow, effectiveStartMs);
  return {
    summaryRecordsFromRun: counts.records,
    summary: {
      records: Math.max(counts.records, recordsTotal, counts.tableRecords),
      pages: Math.max(counts.pages, counts.currentPage, counts.progressPage),
      fields: visibleColumnCount,
      duration,
    },
  };
}

function numeric(value: unknown) {
  return Number(value) || 0;
}

function runSummaryCounts(
  run: CrawlRun | undefined,
  tableData: ControllerOptions['tableRecordsQueryData'],
) {
  const tableTotal = firstDefined(tableData?.meta?.total, tableData?.items?.length);
  const completedPages = firstDefined(
    run?.result_summary?.processed_urls,
    run?.result_summary?.completed_urls,
  );
  return {
    records: numeric(run?.result_summary?.record_count),
    tableRecords: numeric(tableTotal),
    pages: numeric(completedPages),
    currentPage: numeric(run?.result_summary?.current_url_index),
    progressPage: progressPageCount(run?.result_summary?.progress),
  };
}

function progressPageCount(value: unknown) {
  return numeric(value) > 0 ? 1 : 0;
}

function firstDefined<T>(...values: Array<T | null | undefined>) {
  return values.find((value) => value !== null && value !== undefined);
}

function runSummaryDuration(
  run: CrawlRun | undefined,
  terminal: boolean,
  localNow: number,
  startMs: number,
) {
  const persisted = terminal ? formatDurationMs(run?.result_summary?.duration_ms) : null;
  const end = terminal ? run?.completed_at : new Date(localNow).toISOString();
  return persisted ?? formatDuration(new Date(startMs).toISOString(), end);
}

function buildResultActionLabels(
  selectedUrls: string[],
  allUrls: string[],
  selectedRecords: CrawlRecord[],
  downstreamRecords: CrawlRecord[],
) {
  return {
    batch: selectedUrls.length
      ? `Batch Crawl Selected (${selectedUrls.length})`
      : `Batch Crawl (${allUrls.length})`,
    intelligence: selectedRecords.length
      ? `Product Intelligence Selected (${selectedRecords.length})`
      : `Product Intelligence (${downstreamRecords.length})`,
    enrichment: selectedRecords.length
      ? `Enrich Selected (${selectedRecords.length})`
      : `Enrich Records (${downstreamRecords.length})`,
  };
}
