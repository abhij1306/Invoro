'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowRight,
  CheckCircle2,
  Circle,
  Download,
  ExternalLink,
  Loader2,
  Play,
  Search,
} from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';

import {
  DataRegionEmpty,
  DataRegionLoading,
  InlineAlert,
  PageHeader,
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
import { cn } from '../../lib/utils';

// ─── Types ───────────────────────────────────────────────────────────────────

type SessionState =
  | 'created'
  | 'discovering'
  | 'discovered'
  | 'extracting'
  | 'extracted'
  | 'running_pipeline'
  | 'complete';

type PlaygroundSession = {
  id: number;
  input_url: string;
  state: SessionState;
  step_data: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

type DiscoveredProduct = {
  url: string;
  title?: string;
  brand?: string;
  price?: string;
  image?: string;
};

// ─── Steps ───────────────────────────────────────────────────────────────────

const STEPS = [
  { id: 'discover', label: 'Discover' },
  { id: 'select', label: 'Select Products' },
  { id: 'extract', label: 'Extract' },
  { id: 'pipeline', label: 'Pipeline' },
  { id: 'results', label: 'Results' },
] as const;

function stepIndex(state: SessionState): number {
  switch (state) {
    case 'created':
      return 0;
    case 'discovering':
      return 0;
    case 'discovered':
      return 1;
    case 'extracting':
      return 2;
    case 'extracted':
      return 3;
    case 'running_pipeline':
      return 4;
    case 'complete':
      return 4;
    default:
      return 0;
  }
}

// ─── Main Component ──────────────────────────────────────────────────────────

export default function PlaygroundPage() {
  const queryClient = useQueryClient();
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');
  const [selectedUrls, setSelectedUrls] = useState<Set<string>>(new Set());
  const [pipelineOptions, setPipelineOptions] = useState({
    enrich: false,
    compare: false,
    monitor: false,
    audit: false,
  });

  // ─── Session polling ─────────────────────────────────────────────────────

  const sessionQuery = useQuery({
    queryKey: ['playground-session', sessionId],
    queryFn: () => api.getPlaygroundSession(sessionId!),
    enabled: sessionId !== null,
    refetchInterval: (query) => {
      const state = query.state.data?.state;
      if (state === 'discovering' || state === 'extracting' || state === 'running_pipeline') {
        return 3000;
      }
      return false;
    },
  });

  const session = sessionQuery.data as PlaygroundSession | undefined;
  const currentStep = session ? stepIndex(session.state) : -1;

  // ─── Mutations ───────────────────────────────────────────────────────────

  const createSession = useMutation({
    mutationFn: (inputUrl: string) =>
      api.createPlaygroundSession({ url: inputUrl }) as Promise<PlaygroundSession>,
    onSuccess: (data) => {
      setSessionId(data.id);
      setError('');
    },
    onError: (err: Error) => setError(err.message),
  });

  const startDiscover = useMutation({
    mutationFn: (sid: number) => api.playgroundDiscover(sid),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['playground-session', sessionId] }),
    onError: (err: Error) => setError(err.message),
  });

  const selectProducts = useMutation({
    mutationFn: ({ sid, urls }: { sid: number; urls: string[] }) =>
      api.playgroundSelect(sid, { urls }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['playground-session', sessionId] }),
    onError: (err: Error) => setError(err.message),
  });

  const startExtract = useMutation({
    mutationFn: (sid: number) => api.playgroundExtract(sid),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['playground-session', sessionId] }),
    onError: (err: Error) => setError(err.message),
  });

  const runPipeline = useMutation({
    mutationFn: ({ sid, options }: { sid: number; options: typeof pipelineOptions }) =>
      api.playgroundPipeline(sid, options),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['playground-session', sessionId] }),
    onError: (err: Error) => setError(err.message),
  });

  // ─── Handlers ────────────────────────────────────────────────────────────

  const handleStart = useCallback(() => {
    const trimmed = url.trim();
    if (!trimmed) return;
    setError('');
    createSession.mutate(trimmed);
  }, [url, createSession]);

  const handleDiscover = useCallback(() => {
    if (!sessionId) return;
    startDiscover.mutate(sessionId);
  }, [sessionId, startDiscover]);

  const handleSelect = useCallback(() => {
    if (!sessionId || selectedUrls.size === 0) return;
    selectProducts.mutate({ sid: sessionId, urls: Array.from(selectedUrls) });
  }, [sessionId, selectedUrls, selectProducts]);

  const handleExtract = useCallback(() => {
    if (!sessionId) return;
    startExtract.mutate(sessionId);
  }, [sessionId, startExtract]);

  const handlePipeline = useCallback(() => {
    if (!sessionId) return;
    runPipeline.mutate({ sid: sessionId, options: pipelineOptions });
  }, [sessionId, pipelineOptions, runPipeline]);

  const handleReset = useCallback(() => {
    setSessionId(null);
    setUrl('');
    setError('');
    setSelectedUrls(new Set());
    setPipelineOptions({ enrich: false, compare: false, monitor: false, audit: false });
  }, []);

  // Auto-start discovery after session creation
  useEffect(() => {
    if (session?.state === 'created' && sessionId && !startDiscover.isPending) {
      startDiscover.mutate(sessionId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.state, sessionId]);

  // ─── Derived data ────────────────────────────────────────────────────────

  const discoveredProducts: DiscoveredProduct[] =
    (session?.step_data?.discover as Record<string, unknown>)?.products as DiscoveredProduct[] ?? [];

  const toggleProduct = (productUrl: string) => {
    setSelectedUrls((prev) => {
      const next = new Set(prev);
      if (next.has(productUrl)) {
        next.delete(productUrl);
      } else if (next.size < 50) {
        next.add(productUrl);
      }
      return next;
    });
  };

  const selectAll = () => {
    const all = discoveredProducts.slice(0, 50).map((p) => p.url);
    setSelectedUrls(new Set(all));
  };

  // ─── Render ──────────────────────────────────────────────────────────────

  return (
    <div className="page-stack-lg">
      <PageHeader
        title="Playground"
        description="Explore any domain — discover, extract, enrich, compare, and monitor from one place."
        actions={
          session ? (
            <Button size="sm" variant="ghost" onClick={handleReset}>
              Start New
            </Button>
          ) : undefined
        }
      />

      {error && <InlineAlert message={error} />}

      {/* ─── URL Input (no session yet) ─────────────────────────────────── */}
      {!session && (
        <SurfacePanel>
          <div className="p-6">
            <h3 className="type-label mb-2">Enter a URL to explore</h3>
            <p className="text-muted mb-4 text-sm">
              Paste a category page, brand page, or product listing URL. The system will discover
              what products are available.
            </p>
            <div className="flex gap-3">
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleStart()}
                placeholder="https://www.example.com/category/shoes"
                className="border-divider flex-1 rounded-md border bg-[var(--bg-panel)] px-3 py-2 text-sm focus-ring"
              />
              <Button onClick={handleStart} disabled={createSession.isPending || !url.trim()}>
                {createSession.isPending ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Search className="size-4" />
                )}
                Explore
              </Button>
            </div>
          </div>
        </SurfacePanel>
      )}

      {/* ─── Stepper ────────────────────────────────────────────────────── */}
      {session && (
        <>
          <div className="flex items-center gap-2 text-sm">
            {STEPS.map((step, idx) => (
              <div key={step.id} className="flex items-center gap-1.5">
                {idx < currentStep ? (
                  <CheckCircle2 className="size-4 text-success" />
                ) : idx === currentStep ? (
                  <Circle className="size-4 fill-[var(--accent)] text-[var(--accent)]" />
                ) : (
                  <Circle className="text-muted size-4" />
                )}
                <span
                  className={cn(
                    'font-medium',
                    idx === currentStep && 'text-[var(--accent-text)]',
                    idx > currentStep && 'text-muted',
                  )}
                >
                  {step.label}
                </span>
                {idx < STEPS.length - 1 && <ArrowRight className="text-muted mx-1 size-3" />}
              </div>
            ))}
          </div>

          {/* ─── Step: Discovering ──────────────────────────────────────── */}
          {(session.state === 'discovering' || session.state === 'created') && (
            <SurfacePanel>
              <div className="flex items-center gap-3 p-6">
                <Loader2 className="size-5 animate-spin text-[var(--accent)]" />
                <div>
                  <p className="font-medium">Discovering products...</p>
                  <p className="text-muted text-sm">
                    Crawling <span className="font-mono">{session.input_url}</span> to find available
                    products.
                  </p>
                </div>
              </div>
            </SurfacePanel>
          )}

          {/* ─── Step: Select Products ─────────────────────────────────── */}
          {session.state === 'discovered' && (
            <SurfacePanel>
              <div className="border-divider flex items-center justify-between border-b px-4 py-3">
                <div>
                  <p className="type-label m-0">
                    Products Found ({discoveredProducts.length})
                  </p>
                  <p className="text-muted m-0 text-sm">
                    Select up to 50 products to extract detailed data from.
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" variant="ghost" onClick={selectAll}>
                    Select All (max 50)
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => {
                      handleSelect();
                      // After selection, immediately start extraction
                      setTimeout(() => handleExtract(), 500);
                    }}
                    disabled={selectedUrls.size === 0 || selectProducts.isPending}
                  >
                    <Play className="size-3.5" />
                    Extract {selectedUrls.size} Products
                  </Button>
                </div>
              </div>
              <TableSurface>
                {discoveredProducts.length === 0 ? (
                  <DataRegionEmpty
                    title="No products found"
                    description="The crawl didn't find product links on this page. Try a different URL."
                  />
                ) : (
                  <Table className="compact-data-table">
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-[40px]">{''}</TableHead>
                        <TableHead>Product</TableHead>
                        <TableHead className="w-[120px]">Brand</TableHead>
                        <TableHead className="w-[100px]">Price</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {discoveredProducts.slice(0, 100).map((product) => (
                        <TableRow
                          key={product.url}
                          className="cursor-pointer"
                          onClick={() => toggleProduct(product.url)}
                        >
                          <TableCell>
                            <input
                              type="checkbox"
                              checked={selectedUrls.has(product.url)}
                              onChange={() => toggleProduct(product.url)}
                              className="size-4 rounded"
                            />
                          </TableCell>
                          <TableCell>
                            <div className="min-w-0">
                              <p className="m-0 truncate font-medium text-sm">
                                {product.title || product.url}
                              </p>
                              <p className="text-muted m-0 truncate text-xs font-mono">
                                {product.url}
                              </p>
                            </div>
                          </TableCell>
                          <TableCell className="truncate text-sm">
                            {product.brand || '-'}
                          </TableCell>
                          <TableCell className="text-sm">{product.price || '-'}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </TableSurface>
            </SurfacePanel>
          )}

          {/* ─── Step: Extracting ──────────────────────────────────────── */}
          {session.state === 'extracting' && (
            <SurfacePanel>
              <div className="flex items-center gap-3 p-6">
                <Loader2 className="size-5 animate-spin text-[var(--accent)]" />
                <div>
                  <p className="font-medium">Extracting product details...</p>
                  <p className="text-muted text-sm">
                    Crawling{' '}
                    {String((session.step_data?.extract as Record<string, unknown>)?.url_count ?? '?')}{' '}
                    product pages for structured data.
                  </p>
                </div>
              </div>
            </SurfacePanel>
          )}

          {/* ─── Step: Pipeline Selection ──────────────────────────────── */}
          {session.state === 'extracted' && (
            <SurfacePanel>
              <div className="border-divider border-b px-4 py-3">
                <p className="type-label m-0">Extraction Complete</p>
                <p className="text-muted m-0 text-sm">
                  Choose what to do with the extracted data.
                </p>
              </div>
              <div className="grid gap-4 p-6 sm:grid-cols-2">
                <label className="border-divider flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition hover:bg-[var(--bg-alt)]">
                  <input
                    type="checkbox"
                    checked={pipelineOptions.enrich}
                    onChange={(e) =>
                      setPipelineOptions((prev) => ({ ...prev, enrich: e.target.checked }))
                    }
                    className="mt-0.5 size-4 rounded"
                  />
                  <div>
                    <p className="m-0 font-medium text-sm">Enrich Data</p>
                    <p className="text-muted m-0 text-xs">
                      Fill missing brand, category, and product attributes.
                    </p>
                  </div>
                </label>
                <label className="border-divider flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition hover:bg-[var(--bg-alt)]">
                  <input
                    type="checkbox"
                    checked={pipelineOptions.compare}
                    onChange={(e) =>
                      setPipelineOptions((prev) => ({ ...prev, compare: e.target.checked }))
                    }
                    className="mt-0.5 size-4 rounded"
                  />
                  <div>
                    <p className="m-0 font-medium text-sm">Product Intelligence</p>
                    <p className="text-muted m-0 text-xs">
                      Find competitor prices on Google, Amazon, Flipkart.
                    </p>
                  </div>
                </label>
                <label className="border-divider flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition hover:bg-[var(--bg-alt)]">
                  <input
                    type="checkbox"
                    checked={pipelineOptions.monitor}
                    onChange={(e) =>
                      setPipelineOptions((prev) => ({ ...prev, monitor: e.target.checked }))
                    }
                    className="mt-0.5 size-4 rounded"
                  />
                  <div>
                    <p className="m-0 font-medium text-sm">Create Monitor</p>
                    <p className="text-muted m-0 text-xs">
                      Watch for price and availability changes on these products.
                    </p>
                  </div>
                </label>
                <label className="border-divider flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition hover:bg-[var(--bg-alt)]">
                  <input
                    type="checkbox"
                    checked={pipelineOptions.audit}
                    onChange={(e) =>
                      setPipelineOptions((prev) => ({ ...prev, audit: e.target.checked }))
                    }
                    className="mt-0.5 size-4 rounded"
                  />
                  <div>
                    <p className="m-0 font-medium text-sm">AI Audit</p>
                    <p className="text-muted m-0 text-xs">
                      Check AI discoverability score for the source domain.
                    </p>
                    <Badge tone="info" className="mt-1">
                      Independent — runs on input URL
                    </Badge>
                  </div>
                </label>
              </div>
              <div className="border-divider flex justify-end border-t px-4 py-3">
                <Button
                  onClick={handlePipeline}
                  disabled={
                    runPipeline.isPending ||
                    (!pipelineOptions.enrich &&
                      !pipelineOptions.compare &&
                      !pipelineOptions.monitor &&
                      !pipelineOptions.audit)
                  }
                >
                  {runPipeline.isPending ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <Play className="size-4" />
                  )}
                  Run Pipeline
                </Button>
              </div>
            </SurfacePanel>
          )}

          {/* ─── Step: Pipeline Running / Results ──────────────────────── */}
          {(session.state === 'running_pipeline' || session.state === 'complete') && (
            <SurfacePanel>
              <div className="border-divider border-b px-4 py-3">
                <p className="type-label m-0">Pipeline Results</p>
                <p className="text-muted m-0 text-sm">
                  {session.state === 'running_pipeline'
                    ? 'Operations in progress...'
                    : 'All operations complete.'}
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
                <PipelineStepCard
                  label="AI Audit"
                  stepData={session.step_data?.audit as Record<string, unknown> | undefined}
                />
              </div>
              <div className="border-divider flex gap-2 border-t px-4 py-3">
                <Button size="sm" variant="ghost" onClick={handleReset}>
                  Start New Session
                </Button>
                {Boolean(
                  session.step_data?.extract &&
                    (session.step_data.extract as Record<string, unknown>).run_id,
                ) && (
                    <Button size="sm" variant="action" asChild>
                      <a
                        href={`/runs?run_id=${String((session.step_data.extract as Record<string, unknown>).run_id)}`}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        <ExternalLink className="size-3.5" />
                        View Run
                      </a>
                    </Button>
                  )}
              </div>
            </SurfacePanel>
          )}
        </>
      )}
    </div>
  );
}

// ─── Sub-Components ────────────────────────────────────────────────────────────

function PipelineStepCard({
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
        {status === 'running' && <Loader2 className="size-4 animate-spin text-[var(--accent)]" />}
        {status === 'completed' && <CheckCircle2 className="size-4 text-success" />}
        {status === 'created' && <CheckCircle2 className="size-4 text-success" />}
        {status === 'failed' && <Circle className="size-4 text-danger" />}
        <span className="font-medium text-sm">{label}</span>
      </div>
      <Badge tone={status === 'running' ? 'info' : status === 'failed' ? 'danger' : 'neutral'}>
        {status}
      </Badge>
    </div>
  );
}
