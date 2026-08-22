'use client';

// Next.js App Router entrypoint for `/data-enrichment`; invoked by file-system routing.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ExternalLink, History, Loader2, Play, RefreshCcw } from 'lucide-react';
import { useMemo, useReducer, useState } from 'react';

import { HistoryDrawer, type HistoryItem } from '../../components/ui/history-drawer';

import {
  DataRegionEmpty,
  DataRegionLoading,
  InlineAlert,
  KVTile,
  PageHeader,
  TableSurface,
} from '../../components/ui/patterns';
import { Badge, Button } from '../../components/ui/primitives';
import { buttonVariants } from '../../components/ui/button-variants';
import { api } from '../../lib/api';
import { EnrichmentStatus, EnrichmentTableLoading } from './enrichment-components';
import type {
  DataEnrichmentJob,
  DataEnrichmentSourceRecordInput,
  EnrichedProduct,
} from '../../lib/api/types';
import { STORAGE_KEYS } from '../../lib/constants/storage-keys';
import { cn } from '../../lib/utils';

type PrefillPayload = {
  source_run_id?: number | null;
  records?: DataEnrichmentSourceRecordInput[];
};

type DataEnrichmentState = {
  llmEnabled: boolean;
  activeJobId: number | null;
  error: string;
  historyOpen: boolean;
  selectedProductId: number | null;
};

type DataEnrichmentAction =
  | { type: 'llmChanged'; enabled: boolean }
  | { type: 'jobCreated'; jobId: number }
  | { type: 'failed'; message: string }
  | { type: 'historyChanged'; open: boolean }
  | { type: 'productSelected'; productId: number | null }
  | { type: 'historyJobSelected'; jobId: number };

const INITIAL_DATA_ENRICHMENT_STATE: DataEnrichmentState = {
  llmEnabled: false,
  activeJobId: null,
  error: '',
  historyOpen: false,
  selectedProductId: null,
};

function dataEnrichmentReducer(
  state: DataEnrichmentState,
  action: DataEnrichmentAction,
): DataEnrichmentState {
  switch (action.type) {
    case 'llmChanged':
      return { ...state, llmEnabled: action.enabled };
    case 'jobCreated':
      return { ...state, error: '', activeJobId: action.jobId };
    case 'failed':
      return { ...state, error: action.message };
    case 'historyChanged':
      return { ...state, historyOpen: action.open };
    case 'productSelected':
      return { ...state, selectedProductId: action.productId };
    case 'historyJobSelected':
      return { ...state, activeJobId: action.jobId };
  }
}

function loadPrefill(): PrefillPayload {
  if (typeof window === 'undefined') return {};
  const stored = window.sessionStorage.getItem(STORAGE_KEYS.DATA_ENRICHMENT_PREFILL);
  if (!stored) return {};
  try {
    const parsed = JSON.parse(stored) as PrefillPayload;
    return {
      source_run_id: typeof parsed.source_run_id === 'number' ? parsed.source_run_id : null,
      records: Array.isArray(parsed.records) ? parsed.records : [],
    };
  } catch {
    return {};
  } finally {
    window.sessionStorage.removeItem(STORAGE_KEYS.DATA_ENRICHMENT_PREFILL);
  }
}

function useDataEnrichmentModel() {
  const queryClient = useQueryClient();
  const [initialPrefill] = useState(loadPrefill);
  const [state, dispatch] = useReducer(dataEnrichmentReducer, INITIAL_DATA_ENRICHMENT_STATE);
  const { llmEnabled, activeJobId, error, historyOpen, selectedProductId } = state;

  const sourceRecords = enrichmentSourceRecords(initialPrefill);
  const sourceRecordIds = sourceRecords
    .map((record) => record.id)
    .filter((id): id is number => typeof id === 'number');

  const jobsQuery = useQuery({
    queryKey: ['data-enrichment-jobs'],
    queryFn: () => api.listDataEnrichmentJobs({ limit: 20 }),
    refetchInterval: 4000,
  });

  const historyItems: HistoryItem[] = useMemo(() => {
    return (jobsQuery.data ?? []).map((job) => ({
      id: job.id,
      status: job.status,
      created_at: job.created_at,
      label: job.source_run_id ? `From Run #${job.source_run_id}` : 'Direct Input',
      meta: `${Number(job.summary?.accepted_count ?? 0)} records enriched`,
    }));
  }, [jobsQuery.data]);

  const defaultJobId = defaultEnrichmentJobId(sourceRecords.length, jobsQuery.data?.[0]?.id);
  const resolvedJobId = resolveId(activeJobId, defaultJobId);
  const detailQuery = useQuery({
    queryKey: ['data-enrichment-job', resolvedJobId],
    queryFn: () => api.getDataEnrichmentJob(resolvedJobId ?? 0),
    enabled: resolvedJobId !== null,
    refetchInterval: (query) => {
      const status = String(query.state.data?.job?.status ?? '');
      return status === 'pending' || status === 'running' ? 2500 : false;
    },
  });
  const activeJob = resolveEnrichmentJob(detailQuery.data?.job, jobsQuery.data, resolvedJobId);
  const isRunning = enrichmentIsRunning(activeJob?.status);

  const products = enrichmentProducts(detailQuery.data?.enriched_products);
  const { resolvedProductId, selectedProduct } = resolveEnrichmentProduct(
    products,
    selectedProductId,
  );
  const completedCount = products.filter((product) => product.status === 'enriched').length;
  const semanticCount = products.filter((product) =>
    Boolean(product.intent_attributes?.length),
  ).length;

  const createMutation = useMutation({
    mutationFn: () =>
      api.createDataEnrichmentJob({
        source_run_id: initialPrefill.source_run_id ?? null,
        source_record_ids: sourceRecordIds,
        source_records: sourceRecords,
        options: {
          max_source_records: 500,
          llm_enabled: llmEnabled,
        },
      }),
    onSuccess: async (job) => {
      dispatch({ type: 'jobCreated', jobId: job.id });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['data-enrichment-jobs'] }),
        queryClient.invalidateQueries({ queryKey: ['data-enrichment-job', job.id] }),
      ]);
    },
    onError: (mutationError) => {
      dispatch({
        type: 'failed',
        message:
          mutationError instanceof Error ? mutationError.message : 'Unable to start enrichment.',
      });
    },
  });

  const descriptionText = enrichmentDescription(
    sourceRecords.length,
    completedCount,
    semanticCount,
    activeJob,
  );

  return {
    llmEnabled,
    dispatch,
    sourceRecords,
    sourceRecordIds,
    jobsQuery,
    historyItems,
    resolvedJobId,
    detailQuery,
    activeJob,
    isRunning,
    products,
    resolvedProductId,
    selectedProduct,
    completedCount,
    semanticCount,
    createMutation,
    descriptionText,
    error,
    historyOpen,
  };
}

export default function DataEnrichmentPage() {
  const model = useDataEnrichmentModel();
  return <DataEnrichmentView model={model} />;
}

type DataEnrichmentModel = ReturnType<typeof useDataEnrichmentModel>;

function enrichmentSourceRecords(prefill: PrefillPayload) {
  return prefill.records ?? [];
}
function defaultEnrichmentJobId(sourceCount: number, firstJobId: number | undefined) {
  return sourceCount ? null : (firstJobId ?? null);
}
function resolveId(primary: number | null, fallback: number | null) {
  return primary ?? fallback;
}
function resolveEnrichmentJob(
  detail: DataEnrichmentJob | undefined,
  jobs: DataEnrichmentJob[] | undefined,
  id: number | null,
) {
  return detail ?? jobs?.find((job) => job.id === id) ?? null;
}
function enrichmentIsRunning(status: string | undefined) {
  return status === 'pending' || status === 'running';
}
function enrichmentProducts(products: EnrichedProduct[] | undefined) {
  return products ?? [];
}
function resolveEnrichmentProduct(products: EnrichedProduct[], selectedId: number | null) {
  const resolvedProductId = products.some((product) => product.id === selectedId)
    ? selectedId
    : (products[0]?.id ?? null);
  return {
    resolvedProductId,
    selectedProduct: products.find((product) => product.id === resolvedProductId) ?? null,
  };
}
function enrichmentDescription(
  sourceCount: number,
  completedCount: number,
  semanticCount: number,
  job: DataEnrichmentJob | null,
) {
  const parts = [];
  if (sourceCount > 0) parts.push(`${sourceCount} selected`);
  if (completedCount > 0) parts.push(`${completedCount} enriched`);
  if (semanticCount > 0) parts.push(`${semanticCount} semantic`);
  if (job) parts.push(`Mode: ${job.options?.llm_enabled ? 'LLM' : 'Rules'}`);
  return (
    parts.join(' · ') ||
    'Normalize ecommerce detail records into category, price, attribute, and discovery fields.'
  );
}

function DataEnrichmentView({ model }: { model: DataEnrichmentModel }) {
  const {
    dispatch,
    sourceRecords,
    historyItems,
    resolvedJobId,
    detailQuery,
    activeJob,
    isRunning,
    products,
    descriptionText,
    error,
    historyOpen,
  } = model;
  return (
    <div className="page-stack h-full">
      <PageHeader
        title="Data Enrichment"
        description={descriptionText}
        actions={<EnrichmentActions model={model} />}
      />

      <EnrichmentError error={error} />

      {isRunning ? (
        <EnrichmentStatus
          sourceCount={Number(activeJob?.summary?.accepted_count ?? sourceRecords.length)}
          llmEnabled={Boolean(activeJob?.options?.llm_enabled)}
        />
      ) : null}

      {/* ── Main Results ── */}
      <TableSurface className="mb-8" contentClassName="flex flex-col">
        <header className="border-divider flex flex-wrap items-center justify-between gap-4 border-b px-4 py-3">
          <div className="flex items-center gap-3">
            <h2 className="type-label-mono">
              {products.length > 0 ? 'ENRICHED OUTPUT' : 'SELECTED RECORDS'}
            </h2>
          </div>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="quiet"
              size="sm"
              onClick={() => void detailQuery.refetch()}
              disabled={!resolvedJobId || detailQuery.isFetching}
            >
              <RefreshCcw className="mr-1.5 size-3" />
              Refresh
            </Button>
            <Button
              type="button"
              variant="quiet"
              size="icon"
              className="shrink-0"
              onClick={() => dispatch({ type: 'historyChanged', open: true })}
              aria-label="Enrichment History"
            >
              <History className="size-3.5" />
            </Button>
          </div>
        </header>

        <EnrichmentBody model={model} />
      </TableSurface>

      <HistoryDrawer
        open={historyOpen}
        onClose={() => dispatch({ type: 'historyChanged', open: false })}
        items={historyItems}
        activeId={resolvedJobId}
        onSelect={(id) => dispatch({ type: 'historyJobSelected', jobId: id })}
        title="Enrichment History"
      />
    </div>
  );
}

function enrichmentActionLabel(model: DataEnrichmentModel) {
  if (model.createMutation.isPending || model.activeJob?.status === 'pending') return 'Starting...';
  if (model.isRunning) return 'Enriching...';
  return 'Enrich Selected';
}

function EnrichmentActions({ model }: { model: DataEnrichmentModel }) {
  return (
    <div className="flex w-full flex-wrap items-center justify-end gap-2">
      <label className={cn(buttonVariants({ variant: 'neutral', size: 'sm' }), 'cursor-pointer')}>
        <input
          type="checkbox"
          checked={model.llmEnabled}
          onChange={(event) =>
            model.dispatch({ type: 'llmChanged', enabled: event.target.checked })
          }
          className="border-divider text-accent focus:ring-accent size-3 cursor-pointer rounded"
        />
        LLM Enrichment
      </label>
      <Button
        type="button"
        variant="action"
        size="sm"
        disabled={
          !model.sourceRecordIds.length || model.createMutation.isPending || model.isRunning
        }
        onClick={() => model.createMutation.mutate()}
      >
        <Play className="size-3" />
        {enrichmentActionLabel(model)}
      </Button>
    </div>
  );
}

function EnrichmentError({ error }: { error: string }) {
  return error ? <InlineAlert tone="danger" message={error} /> : null;
}

// EnrichedProductRow removed - replaced by split master-detail layout

function recordTitle(record: DataEnrichmentSourceRecordInput) {
  const title = record.data?.title;
  return typeof title === 'string' && title.trim()
    ? title
    : record.source_url?.replace(/^https?:\/\/(www\.)?/, '') || `Record #${record.id}`;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '';
  if (Array.isArray(value)) return value.join(', ');
  if (typeof value === 'object') {
    // Handle price object from EnrichmentStatus
    if ('amount' in value || 'price_min' in value) {
      const p = value as Record<string, unknown>;
      const amount = p.amount ?? p.price_min;
      const currency = (p.currency as string) || '';
      if (typeof amount === 'number') {
        return `${currency} ${amount.toFixed(2)}`.trim();
      }
    }
    return JSON.stringify(value);
  }
  return String(value);
}

function EnrichmentBody({ model }: { model: DataEnrichmentModel }) {
  const { isRunning, completedCount, activeJob, detailQuery, products, sourceRecords } = model;
  if (isRunning && completedCount === 0)
    return <EnrichmentTableLoading llmEnabled={Boolean(activeJob?.options?.llm_enabled)} />;
  if (detailQuery.isLoading && !isRunning) return <DataRegionLoading count={8} className="px-0" />;
  if (products.length) return <EnrichedProductSplitView model={model} />;
  if (sourceRecords.length) return <SourceRecordList records={sourceRecords} />;
  return (
    <DataRegionEmpty
      title="No records selected"
      description="Open an ecommerce detail run and send selected records here to begin enrichment."
    />
  );
}

function EnrichedProductSplitView({ model }: { model: DataEnrichmentModel }) {
  return (
    <div className="divide-divider flex h-[600px] flex-col divide-y lg:flex-row lg:divide-x lg:divide-y-0">
      <EnrichedProductSidebar model={model} />
      <EnrichedProductDetails product={model.selectedProduct} />
    </div>
  );
}

function EnrichedProductSidebar({ model }: { model: DataEnrichmentModel }) {
  return (
    <div className="bg-background-alt/10 flex min-h-0 w-full shrink-0 flex-col lg:w-80">
      <div className="border-divider bg-subtle-panel/30 border-b p-3">
        <span className="type-caption-mono uppercase">
          Record Selector ({model.products.length})
        </span>
      </div>
      <div className="flex-1 space-y-1 overflow-y-auto p-2">
        {model.products.map((product) => (
          <EnrichedProductOption key={product.id} model={model} product={product} />
        ))}
      </div>
    </div>
  );
}

function EnrichedProductOption({
  model,
  product,
}: {
  model: DataEnrichmentModel;
  product: EnrichedProduct;
}) {
  const isProcessing = product.status === 'pending' || product.status === 'running';
  const title = product.source_url
    ? product.source_url.replace(/^https?:\/\/(www\.)?/, '')
    : `Record #${product.source_record_id}`;
  return (
    <button
      type="button"
      onClick={() => model.dispatch({ type: 'productSelected', productId: product.id })}
      className={cn(
        'flex w-full flex-col gap-1.5 rounded-md border p-3 text-left transition-colors',
        product.id === model.resolvedProductId
          ? 'border-accent bg-accent-subtle/50'
          : 'border-border bg-background hover:bg-background-elevated',
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <Badge tone="neutral" className="h-5 shrink-0 px-1.5 font-mono text-xs opacity-75">
          #{product.source_record_id}
        </Badge>
        {isProcessing ? (
          <div className="flex items-center gap-1 opacity-60">
            <Loader2 className="text-accent size-3 animate-spin" />
            <span className="type-caption-mono">Processing</span>
          </div>
        ) : null}
      </div>
      <div
        className="type-body-sm text-foreground w-full truncate font-medium"
        title={product.source_url}
      >
        {title}
      </div>
    </button>
  );
}

function EnrichedProductDetails({ product }: { product: EnrichedProduct | null | undefined }) {
  return (
    <div className="bg-background flex min-h-0 min-w-0 flex-1 flex-col">
      {product ? (
        <div className="flex-1 space-y-6 overflow-y-auto p-6">
          {/* Header info */}
          <div className="border-divider border-b pb-4">
            <div className="flex items-center gap-2">
              <span className="type-heading-3">Enriched Record Details</span>
              <Badge tone="neutral" className="font-mono text-xs">
                Record #{product.source_record_id}
              </Badge>
            </div>
            {product.source_url ? (
              <a
                href={product.source_url}
                target="_blank"
                rel="noreferrer"
                className="text-accent type-body-sm mt-1 flex items-center gap-1 truncate hover:underline"
              >
                {product.source_url}
                <ExternalLink className="size-3 shrink-0" />
              </a>
            ) : null}
          </div>

          {/* Detail Groups */}
          <div className="space-y-6">
            {/* Core Attributes (Row 1: Full width) */}
            <div className="border-border bg-subtle-panel/20 space-y-4 rounded-lg border p-4">
              <h3 className="type-label-mono flex items-center gap-1.5 uppercase">
                <span className="bg-accent size-1.5 rounded-full" />
                Core Attributes
              </h3>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
                <KVTile
                  label="Price (Normalized)"
                  value={formatValue(product.price_normalized) || '--'}
                />
                <KVTile label="Color Family" value={product.color_family || '--'} />
                <KVTile
                  label="Size Normalized"
                  value={product.size_normalized?.join(', ') || '--'}
                />
                <KVTile label="Size System" value={product.size_system || '--'} />
                <KVTile label="Gender Normalized" value={product.gender_normalized || '--'} />
                <KVTile
                  label="Materials Normalized"
                  value={product.materials_normalized?.join(', ') || '--'}
                />
                <KVTile label="Availability" value={product.availability_normalized || '--'} />
              </div>
            </div>

            {/* Taxonomy & Context (Row 2: Full width) */}
            <div className="border-border bg-subtle-panel/20 space-y-4 rounded-lg border p-4">
              <h3 className="type-label-mono flex items-center gap-1.5 uppercase">
                <span className="bg-info size-1.5 rounded-full" />
                Taxonomy & Context
              </h3>
              <div className="grid grid-cols-1 gap-4">
                <KVTile label="Category Path" value={product.category_path || '--'} />
                <KVTile label="Audience" value={product.audience?.join(', ') || '--'} />
              </div>
            </div>

            {/* Semantic & AI Insights (Row 3: Full width) */}
            <div className="border-border bg-subtle-panel/20 space-y-4 rounded-lg border p-4">
              <h3 className="type-label-mono flex items-center gap-1.5 uppercase">
                <span className="bg-success size-1.5 rounded-full" />
                AI & Semantic Enrichment
              </h3>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-4">
                <KVTile
                  label="Intent Attributes"
                  value={<EnrichmentTags values={product.intent_attributes} tone="accent" />}
                />
                <KVTile
                  label="Style Tags"
                  value={<EnrichmentTags values={product.style_tags} tone="neutral" />}
                />
                <KVTile
                  label="AI Discovery Tags"
                  value={<EnrichmentTags values={product.ai_discovery_tags} tone="info" />}
                />
                <KVTile
                  label="Suggested Bundles"
                  value={<EnrichmentTags values={product.suggested_bundles} tone="success" />}
                />
              </div>

              <div className="pt-2">
                <KVTile
                  label="SEO Keywords"
                  value={<KeywordTags values={product.seo_keywords} />}
                />
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="grid flex-1 place-items-center p-6 text-center">
          <div className="text-muted type-body">
            Select a record from the list to view full enrichment details.
          </div>
        </div>
      )}
    </div>
  );
}

function EnrichmentTags({
  values,
  tone,
}: {
  values: string[] | null | undefined;
  tone: 'accent' | 'neutral' | 'info' | 'success';
}) {
  if (!values?.length) return '--';
  return (
    <div className="flex flex-wrap gap-1.5 pt-1">
      {values.map((value) => (
        <Badge key={value} tone={tone} className="text-xs font-normal">
          {value}
        </Badge>
      ))}
    </div>
  );
}

function KeywordTags({ values }: { values: string[] | null | undefined }) {
  if (!values?.length) return '--';
  return (
    <div className="flex flex-wrap gap-1.5 pt-1">
      {values.map((value) => (
        <span
          key={value}
          className="bg-background-elevated border-border text-secondary rounded-full border px-2 py-0.5 text-xs"
        >
          {value}
        </span>
      ))}
    </div>
  );
}

function SourceRecordList({
  records: sourceRecords,
}: {
  records: DataEnrichmentSourceRecordInput[];
}) {
  return (
    <div className="divide-divider divide-y overflow-auto">
      {sourceRecords.map((record, index) => {
        const badgeValue = record.id ?? record.source_url;
        return (
          <div
            key={record.id == null ? `record-index-${index}` : `record-${record.id}`}
            className="hover:bg-accent/[0.04] flex items-center gap-3 px-4 py-2.5 transition-colors"
          >
            <span className="text-muted w-6 shrink-0 font-mono text-xs">{index + 1}</span>
            <div className="min-w-0 flex-1">
              <div className="type-body-sm truncate font-medium">{recordTitle(record)}</div>
              <div className="type-caption flex items-center gap-2">
                {record.source_url ? (
                  <a
                    href={record.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-accent truncate opacity-80 hover:underline"
                    title={record.source_url}
                  >
                    {record.source_url}
                  </a>
                ) : null}
              </div>
            </div>
            {badgeValue ? (
              <Badge tone="neutral" className="h-5 shrink-0 px-1.5 font-mono text-xs opacity-60">
                #{badgeValue}
              </Badge>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
