'use client';

import { ArrowRight, CheckCircle2, Circle, Loader2, Play, Search } from 'lucide-react';
import { InlineAlert, PageHeader, SurfacePanel } from '../../components/ui/patterns';
import { Button } from '../../components/ui/primitives';
import { cn } from '../../lib/utils';
import { collectTreeUrls } from './playground-normalizers';
import {
  ActivityLogPanel,
  CategoryDiscoverySummary,
  ExtractedDataPreview,
  NavTreePanel,
  PickerPanel,
  PipelineResultsPanel,
} from './playground-panels';
import {
  clampCategoryLimit,
  parseUrlInput,
  type PlaygroundWorkflow,
} from './use-playground-workflow';

const STEPS = [
  { id: 'discover', label: 'Discover' },
  { id: 'select', label: 'Select Products' },
  { id: 'extract', label: 'Extract' },
  { id: 'pipeline', label: 'Pipeline' },
  { id: 'results', label: 'Results' },
] as const;

export function PlaygroundView({ workflow }: { workflow: PlaygroundWorkflow }) {
  return (
    <div className="page-stack-lg">
      <PageHeader
        title="Playground"
        description="Explore any domain — discover, extract, enrich, compare, and monitor from one place."
        actions={
          workflow.session ? (
            <Button size="sm" variant="ghost" onClick={workflow.handleReset}>
              Start New
            </Button>
          ) : undefined
        }
      />
      {workflow.error ? <InlineAlert message={workflow.error} /> : null}
      {workflow.session ? (
        <SessionWorkspace workflow={workflow} />
      ) : (
        <UrlIntake workflow={workflow} />
      )}
    </div>
  );
}

function UrlIntake({ workflow }: { workflow: PlaygroundWorkflow }) {
  const { url, setUrl, categoryLimit, setCategoryLimit, createSession, handleStart } = workflow;
  function updateLimit(value: string) {
    const parsed = value ? Number(value) : 1;
    setCategoryLimit(clampCategoryLimit(Number.isFinite(parsed) ? parsed : 1));
  }
  return (
    <SurfacePanel>
      <div className="p-6">
        <h3 className="type-heading-3 mb-2">Enter URL(s) to explore</h3>
        <p className="type-body-sm mb-4">
          Paste brand homepages, category pages, or listing URLs. Category URLs are shown first.
        </p>
        <div className="grid gap-3 sm:grid-cols-[1fr_140px_auto]">
          <textarea
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder={'https://brand-a.example\nhttps://brand-b.example'}
            rows={4}
            className="border-divider focus-ring bg-panel min-h-24 flex-1 resize-y rounded-md border px-3 py-2 font-mono text-sm"
          />
          <label className="grid content-start gap-2">
            <span className="type-label">Limit</span>
            <input
              type="number"
              min={1}
              max={50}
              value={categoryLimit}
              onChange={(event) => updateLimit(event.target.value)}
              className="border-divider focus-ring bg-panel rounded-md border px-3 py-2 text-sm"
            />
          </label>
          <Button
            className="self-start"
            onClick={handleStart}
            disabled={createSession.isPending || parseUrlInput(url).length === 0}
          >
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
  );
}

function SessionWorkspace({ workflow }: { workflow: PlaygroundWorkflow }) {
  return (
    <>
      <PlaygroundStepper currentStep={workflow.currentStep} />
      <PlaygroundStage workflow={workflow} />
    </>
  );
}

function PlaygroundStepper({ currentStep }: { currentStep: number }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      {STEPS.map((step, index) => (
        <div key={step.id} className="flex items-center gap-1.5">
          <StepIcon index={index} currentStep={currentStep} />
          <span
            className={cn(
              'font-medium',
              index === currentStep && 'text-accent',
              index > currentStep && 'text-muted',
            )}
          >
            {step.label}
          </span>
          {index < STEPS.length - 1 ? <ArrowRight className="text-muted mx-1 size-3" /> : null}
        </div>
      ))}
    </div>
  );
}

function StepIcon({ index, currentStep }: { index: number; currentStep: number }) {
  if (index < currentStep) return <CheckCircle2 className="text-success size-4" />;
  if (index === currentStep) return <Circle className="text-accent size-4 fill-[var(--accent)]" />;
  return <Circle className="text-muted size-4" />;
}

function PlaygroundStage({ workflow }: { workflow: PlaygroundWorkflow }) {
  switch (workflow.session?.state) {
    case 'created':
    case 'discovering':
      return <DiscoveringStage workflow={workflow} />;
    case 'sitemap_listed':
      return <SitemapStage workflow={workflow} />;
    case 'discovered':
      return <ProductSelectionStage workflow={workflow} />;
    case 'extracting':
      return <ExtractingStage workflow={workflow} />;
    case 'extracted':
      return <PipelineSelectionStage workflow={workflow} />;
    case 'running_pipeline':
    case 'complete':
      return <PipelineResultStage workflow={workflow} />;
    default:
      return null;
  }
}

function DiscoveringStage({ workflow }: { workflow: PlaygroundWorkflow }) {
  const session = workflow.session!;
  const inputUrls = Array.isArray(session.step_data?.input_urls)
    ? session.step_data.input_urls
    : null;
  const runId = (session.step_data?.discover as Record<string, unknown>)?.run_id as
    number | undefined;
  return (
    <ActivityLogPanel
      title="Discovering category URLs"
      subtitle={
        <>
          Checking <span className="font-mono">{session.input_url}</span>
          {inputUrls ? ` and ${String(Math.max(0, inputUrls.length - 1))} more URL(s)` : ''} in
          parallel.
        </>
      }
      runId={runId}
      startedAt={session.created_at}
      phase="discover"
    />
  );
}

function SitemapStage({ workflow }: { workflow: PlaygroundWorkflow }) {
  return (
    <>
      {workflow.sitemapGroups.length ? (
        <CategoryDiscoverySummary groups={workflow.sitemapGroups} />
      ) : null}
      {workflow.navTreeGroups.length ? (
        <TreeCategoryPicker workflow={workflow} />
      ) : (
        <FlatCategoryPicker workflow={workflow} />
      )}
    </>
  );
}

function confirmCategorySelection(workflow: PlaygroundWorkflow) {
  const categoryUrls = Array.from(workflow.selectedUrls);
  if (workflow.sessionId && categoryUrls.length)
    workflow.selectCategory.mutate({ sid: workflow.sessionId, categoryUrls });
}

function categoryConfirmLabel(count: number) {
  return count === 0 ? 'Pick URL(s)' : `Crawl ${count} URL${count === 1 ? '' : 's'}`;
}

function TreeCategoryPicker({ workflow }: { workflow: PlaygroundWorkflow }) {
  const { navTreeGroups, selectedUrls, toggleProducts, selectUrls, selectCategory } = workflow;
  return (
    <NavTreePanel
      groups={navTreeGroups}
      selected={selectedUrls}
      onToggleUrls={toggleProducts}
      onSelectAll={() => selectUrls(navTreeGroups.flatMap((group) => collectTreeUrls(group.tree)))}
      onConfirm={() => confirmCategorySelection(workflow)}
      confirmLabel={categoryConfirmLabel(selectedUrls.size)}
      confirmDisabled={selectedUrls.size === 0 || selectCategory.isPending}
      isLoading={selectCategory.isPending}
    />
  );
}

function FlatCategoryPicker({ workflow }: { workflow: PlaygroundWorkflow }) {
  const {
    session,
    sitemapSource,
    sitemapUrls,
    selectedUrls,
    toggleProduct,
    selectUrls,
    selectCategory,
  } = workflow;
  return (
    <PickerPanel
      mode="multi"
      title={`Category URLs from ${sitemapSource} (${sitemapUrls.length})`}
      description={categoryPickerDescription(sitemapSource)}
      items={sitemapUrls.map((url) => ({ url }))}
      selected={selectedUrls}
      onToggle={toggleProduct}
      onSelectAll={() => selectUrls(sitemapUrls)}
      onConfirm={() => confirmCategorySelection(workflow)}
      confirmLabel={categoryConfirmLabel(selectedUrls.size)}
      confirmDisabled={selectedUrls.size === 0 || selectCategory.isPending}
      isLoading={selectCategory.isPending}
      emptyTitle="No category links found"
      emptyDescription={`No category URLs found for ${session?.input_url ?? ''}. Try a category URL directly or raise the limit.`}
    />
  );
}

function categoryPickerDescription(source: string) {
  if (source === 'homepage')
    return 'Sitemap was unavailable, so category-like links were inferred from the homepage. Pick one or more URLs to crawl.';
  if (source === 'rendered site links' || source === 'mixed discovery')
    return 'Rendered site links were crawled to find category-like URLs. Pick one or more URLs to crawl.';
  return 'Pick one or more category, collection, or section URLs to crawl.';
}

function ProductSelectionStage({ workflow }: { workflow: PlaygroundWorkflow }) {
  const {
    discoveredProducts,
    selectedUrls,
    toggleProduct,
    selectAll,
    handleSelect,
    selectProducts,
  } = workflow;
  return (
    <PickerPanel
      mode="multi"
      title={`Products Found (${discoveredProducts.length})`}
      description="Select up to 50 products to extract detailed data from."
      items={discoveredProducts}
      selected={selectedUrls}
      onToggle={toggleProduct}
      onSelectAll={selectAll}
      onConfirm={handleSelect}
      confirmLabel={`Extract ${selectedUrls.size} Product${selectedUrls.size === 1 ? '' : 's'}`}
      confirmDisabled={selectedUrls.size === 0 || selectProducts.isPending}
      isLoading={selectProducts.isPending}
      emptyTitle="No products found"
      emptyDescription="The crawl didn't find product links on this page. Try a different URL."
    />
  );
}

function ExtractingStage({ workflow }: { workflow: PlaygroundWorkflow }) {
  const session = workflow.session!;
  const extract = session.step_data?.extract as Record<string, unknown>;
  return (
    <ActivityLogPanel
      title="Extracting product details"
      subtitle={
        <>Crawling {String(extract?.url_count ?? '?')} product pages for structured data.</>
      }
      runId={extract?.run_id as number | undefined}
      startedAt={session.updated_at}
      phase="extract"
    />
  );
}

function PipelineSelectionStage({ workflow }: { workflow: PlaygroundWorkflow }) {
  return (
    <>
      <ExtractedDataPreview
        records={workflow.extractedRecords}
        isLoading={workflow.resultsQuery.isPending}
      />
      <PipelineOptionsPanel workflow={workflow} />
      {workflow.hasPipelineActivity ? (
        <PipelineResultsPanel
          session={workflow.session!}
          extractedRunIds={workflow.extractedRunIds}
        />
      ) : null}
    </>
  );
}

function PipelineOptionsPanel({ workflow }: { workflow: PlaygroundWorkflow }) {
  const { pipelineOptions, setPipelineOptions, runPipeline, handlePipeline } = workflow;
  const updateOption = (key: keyof typeof pipelineOptions, checked: boolean) =>
    setPipelineOptions((previous) => ({ ...previous, [key]: checked }));
  const disabled = runPipeline.isPending || !Object.values(pipelineOptions).some(Boolean);
  return (
    <SurfacePanel>
      <div className="border-divider border-b px-4 py-3">
        <p className="type-label m-0">Extraction Complete</p>
        <p className="text-muted m-0 text-sm">Choose what to do with the extracted data.</p>
      </div>
      <div className="grid gap-4 p-6 sm:grid-cols-2">
        <PipelineOption
          label="Enrich Data"
          description="Fill missing brand, category, and product attributes."
          checked={pipelineOptions.enrich}
          onChange={(checked) => updateOption('enrich', checked)}
        />
        <PipelineOption
          label="Product Intelligence"
          description="Find competitor prices on Google, Amazon, Flipkart."
          checked={pipelineOptions.compare}
          onChange={(checked) => updateOption('compare', checked)}
        />
        <PipelineOption
          label="Create Monitor"
          description="Watch for price and availability changes on these products."
          checked={pipelineOptions.monitor}
          onChange={(checked) => updateOption('monitor', checked)}
        />
      </div>
      <div className="border-divider flex justify-end border-t px-4 py-3">
        <Button onClick={handlePipeline} disabled={disabled}>
          {runPipeline.isPending ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Play className="size-4" />
          )}
          Run Pipeline
        </Button>
      </div>
    </SurfacePanel>
  );
}

function PipelineOption({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="border-divider hover:bg-background-alt flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-0.5 size-4 rounded"
      />
      <div>
        <p className="m-0 text-sm font-medium">{label}</p>
        <p className="text-muted m-0 text-xs">{description}</p>
      </div>
    </label>
  );
}

function PipelineResultStage({ workflow }: { workflow: PlaygroundWorkflow }) {
  return (
    <>
      <ExtractedDataPreview
        records={workflow.extractedRecords}
        isLoading={workflow.resultsQuery.isPending}
      />
      <PipelineResultsPanel
        session={workflow.session!}
        extractedRunIds={workflow.extractedRunIds}
        onReset={workflow.handleReset}
      />
    </>
  );
}
