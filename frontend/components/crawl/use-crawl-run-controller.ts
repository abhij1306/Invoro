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

  const visibleRecords = effectiveOutputTab === 'table' ? tableRecords : records;
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
  const batchSourceRecords = tableRecords.length ? tableRecords : records;
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
  const ecommerceDetailRun = String(run?.surface ?? '') === 'ecommerce_detail';
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

  const summaryRecordsFromRun = Number(run?.result_summary?.record_count ?? 0) || 0;
  const summaryRecordsFromTable =
    Number(tableRecordsQueryData?.meta?.total ?? tableRecordsQueryData?.items?.length ?? 0) || 0;
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

  const batchFromResultsUrls = selectedResultUrls.length ? selectedResultUrls : resultUrls;
  const productIntelligenceRecords = selectedRecords.length ? selectedRecords : batchSourceRecords;
  const dataEnrichmentRecords = selectedRecords.length ? selectedRecords : batchSourceRecords;

  function toggleRecord(id: number, checked: boolean) {
    setSelectedIds((current) =>
      checked ? Array.from(new Set([...current, id])) : current.filter((value) => value !== id),
    );
  }

  function selectAll(recordIds: number[]) {
    setSelectedIds(Array.from(new Set(recordIds)));
  }

  function clearSelection() {
    setSelectedIds([]);
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
    if (!productIntelligenceRecords.length) return;
    storeProductIntelligencePrefill({
      source_run_id: run?.id ?? null,
      source_domain: run?.url ?? '',
      records: productIntelligenceRecords.map(({ id, run_id, source_url, data }) => ({
        id,
        run_id,
        source_url,
        data,
      })),
    });
    router.replace('/product-intelligence');
  }

  function triggerDataEnrichmentFromResults() {
    if (!dataEnrichmentRecords.length) return;
    storeDataEnrichmentPrefill({
      source_run_id: run?.id ?? null,
      records: dataEnrichmentRecords.map(({ id, run_id, source_url, data }) => ({
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
    resultUrls,
    selectedResultUrls,
    llmSummary,
    listingRun,
    ecommerceDetailRun,
    verdict,
    completedQualityLevel,
    emptyRecordsState,
    summaryRecordsFromRun,
    summary,
    batchFromResultsUrls,
    batchFromResultsLabel: selectedResultUrls.length
      ? `Batch Crawl Selected (${selectedResultUrls.length})`
      : `Batch Crawl (${resultUrls.length})`,
    productIntelligenceRecords,
    productIntelligenceLabel: selectedRecords.length
      ? `Product Intelligence Selected (${selectedRecords.length})`
      : `Product Intelligence (${productIntelligenceRecords.length})`,
    dataEnrichmentRecords,
    dataEnrichmentLabel: selectedRecords.length
      ? `Enrich Selected (${selectedRecords.length})`
      : `Enrich Records (${dataEnrichmentRecords.length})`,
    toggleRecord,
    selectAll,
    clearSelection,
    resetToConfig,
    downloadExport,
    runControl,
    triggerBatchCrawlFromResults,
    triggerProductIntelligenceFromResults,
    triggerDataEnrichmentFromResults,
  };
}
