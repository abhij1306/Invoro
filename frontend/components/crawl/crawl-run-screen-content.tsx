'use client';
import {
  ArrowRightCircle,
  Brain,
  ChevronsDown,
  Clock,
  Download,
  History,
  Plus,
} from 'lucide-react';
import { HistoryDrawer } from '../ui/history-drawer';
import {
  InlineAlert,
  PageHeader,
  RunSummaryChips,
  RunWorkspaceShell,
  SectionHeader,
  TabBar,
} from '../ui/patterns';
import { Badge, Button, Card } from '../ui/primitives';
import type { ResultSummaryQualityLevel } from '../../lib/api/types';
import { ACTIVE_STATUSES } from '../../lib/constants/crawl-statuses';
import { getDomain } from '../../lib/format/domain';
import { ActionButton, LogTerminal } from './shared-components';
import {
  humanizeVerdict,
  humanizeQuality,
  type OutputTabKey,
  scrollViewportToBottom,
} from './shared';
import { AlertBuilderDrawer } from './alert-builder-drawer';
import { downloadMarkdown } from './markdown-output-utils';
import type { CrawlRunScreenModel } from './use-crawl-run-screen-model';
import { RunOutputContent } from './crawl-run-output-content';

function RunOutputSummary({
  llmRequested,
  llmTouchedRecords,
  llmTouchedFields,
  duration,
  verdict,
  quality,
}: Readonly<{
  llmRequested: boolean;
  llmTouchedRecords: number;
  llmTouchedFields: number;
  duration: string;
  verdict: string;
  quality: ResultSummaryQualityLevel;
}>) {
  return (
    <div className="flex flex-wrap items-center justify-end gap-2.5">
      {llmRequested ? (
        <Badge
          tone={llmTouchedRecords > 0 ? 'accent' : 'neutral'}
          title={
            llmTouchedRecords > 0
              ? `LLM used ${llmTouchedRecords} record(s) / ${llmTouchedFields} field(s)`
              : 'LLM enabled, no visible repair'
          }
        >
          {llmTouchedRecords > 0
            ? `LLM used ${llmTouchedRecords} rec / ${llmTouchedFields} fld`
            : 'LLM on, no visible repair'}
        </Badge>
      ) : (
        <Badge tone="neutral">LLM off</Badge>
      )}
      <RunSummaryChips
        duration={duration}
        verdict={humanizeVerdict(verdict).toLowerCase()}
        quality={humanizeQuality(quality).toLowerCase()}
      />
    </div>
  );
}

export function CrawlRunScreenContent({
  runId,
  model,
}: Readonly<{ runId: number; model: CrawlRunScreenModel }>) {
  const {
    router,
    alertBuilderOpen,
    setAlertBuilderOpen,
    historyOpen,
    setHistoryOpen,
    runQuery,
    run,
    records,
    resetToConfig,
    historyItems,
  } = model;
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

      <RunLoadingPanel runId={runId} model={model} />

      <RunPanelErrors model={model} />
      <LiveRunPanel model={model} />

      <TerminalRunPanel model={model} />
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
function RunLoadingPanel({ runId, model }: { runId: number; model: CrawlRunScreenModel }) {
  if (!model.showRunLoadingState) return null;
  return (
    <Card className="space-y-3 px-6 py-8">
      <SectionHeader
        title="Loading Crawl"
        description="Fetching run details and restoring the workspace."
      />
      <div className="text-muted type-body leading-relaxed">Run #{runId} is loading.</div>
    </Card>
  );
}

function RunPanelErrors({ model }: { model: CrawlRunScreenModel }) {
  const { panelRefreshErrors, retryFailedPanels } = model;
  if (!panelRefreshErrors.length) return null;
  return (
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
        <Button variant="neutral" type="button" size="sm" onClick={() => void retryFailedPanels()}>
          Retry failed panels
        </Button>
      </div>
    </Card>
  );
}

function LiveRunPanel({ model }: { model: CrawlRunScreenModel }) {
  const {
    logSocketOnline,
    run,
    elapsedLabel,
    liveJumpAvailable,
    logViewportRef,
    dispatchLocal,
    runActionPending,
    runControl,
    logs,
    batchSourceRecords,
  } = model;
  if (model.showRunLoadingState || model.terminal) return null;
  return (
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
            <span className="border-divider bg-background-elevated text-foreground type-body inline-flex h-8 items-center gap-1.5 rounded-sm border px-3 tabular-nums">
              <Clock className="size-3.5" />
              {elapsedLabel}
            </span>
          ) : null}

          {liveJumpAvailable ? (
            <button
              type="button"
              onClick={() => {
                scrollViewportToBottom(logViewportRef);
                dispatchLocal({ type: 'liveJumpChanged', available: false });
              }}
              className="bg-background-alt shadow-card type-control inline-flex items-center gap-1 rounded-md px-2.5 py-1.5"
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
  );
}

function TerminalRunPanel({ model }: { model: CrawlRunScreenModel }) {
  const { run, runActionError } = model;
  const runErrorMessage =
    typeof run?.result_summary?.error === 'string' ? run.result_summary.error : '';
  if (model.showRunLoadingState || !model.terminal) return null;
  return (
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
          actions={<TerminalRunActions model={model} />}
          tabs={<RunOutputTabs model={model} />}
          summary={<RunOutputSummaryView model={model} />}
          content={<RunOutputContent model={model} />}
        />
      </Card>
    </div>
  );
}

function RunOutputTabs({ model }: { model: CrawlRunScreenModel }) {
  const { effectiveOutputTab, setOutputTab, markdownOutputRun, summary, showRunLearningTab } =
    model;
  const primary = markdownOutputRun
    ? { value: 'markdown', label: 'Markdown' }
    : { value: 'table', label: `Table (${summary.records})` };
  const learning = showRunLearningTab ? [{ value: 'learning', label: 'Learning' }] : [];
  return (
    <TabBar
      value={effectiveOutputTab}
      variant="underline"
      onChange={(value) => setOutputTab(value as OutputTabKey)}
      options={[
        primary,
        { value: 'json', label: 'JSON' },
        { value: 'logs', label: 'Logs' },
        ...learning,
      ]}
    />
  );
}

function RunOutputSummaryView({ model }: { model: CrawlRunScreenModel }) {
  return (
    <RunOutputSummary
      llmRequested={model.llmSummary.requested}
      llmTouchedRecords={model.llmSummary.touchedRecords}
      llmTouchedFields={model.llmSummary.touchedFields}
      duration={model.summary.duration}
      verdict={model.verdict}
      quality={model.completedQualityLevel}
    />
  );
}
function TerminalRunActions({ model }: { model: CrawlRunScreenModel }) {
  const {
    listingRun,
    batchFromResultsUrls,
    triggerBatchCrawlFromResults,
    batchFromResultsLabel,
    ecommerceDetailRun,
    downstreamRecords,
    triggerProductIntelligenceFromResults,
    productIntelligenceLabel,
    triggerDataEnrichmentFromResults,
    dataEnrichmentLabel,
    markdownOutputRun,
    markdownDocument,
    run,
    downloadExport,
    setHistoryOpen,
  } = model;
  return (
    <>
      {listingRun && batchFromResultsUrls.length ? (
        <Button variant="action" type="button" size="sm" onClick={triggerBatchCrawlFromResults}>
          <ArrowRightCircle className="size-3" />
          {batchFromResultsLabel}
        </Button>
      ) : null}
      {(listingRun || ecommerceDetailRun) && downstreamRecords.length ? (
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
      {ecommerceDetailRun && downstreamRecords.length ? (
        <Button variant="action" type="button" size="sm" onClick={triggerDataEnrichmentFromResults}>
          <Brain className="size-3" />
          {dataEnrichmentLabel}
        </Button>
      ) : null}
      {markdownOutputRun ? (
        <Button
          variant="download"
          type="button"
          size="sm"
          disabled={!markdownDocument}
          onClick={() => downloadMarkdown(markdownDocument, run)}
        >
          <Download className="size-3" />
          Markdown
        </Button>
      ) : (
        <Button
          variant="download"
          type="button"
          size="sm"
          onClick={() => void downloadExport('csv')}
        >
          <Download className="size-3" />
          Excel (CSV)
        </Button>
      )}
      <Button
        variant="download"
        type="button"
        size="sm"
        onClick={() => void downloadExport('json')}
      >
        <Download className="size-3" />
        JSON
      </Button>
      <Button variant="neutral" type="button" size="sm" onClick={() => setHistoryOpen(true)}>
        <History className="size-3" />
        History
      </Button>
    </>
  );
}
