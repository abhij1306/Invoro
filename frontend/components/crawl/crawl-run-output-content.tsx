'use client';
import { Bell, Copy } from 'lucide-react';
import { syntaxHighlightJsonNodes } from '../../lib/ui/syntax';
import {
  DataRegionEmpty,
  DataRegionLoading,
  DetailRow,
  InlineAlert,
  SectionHeader,
} from '../ui/patterns';
import { Badge, Button, Card } from '../ui/primitives';
import { CRAWL_DEFAULTS } from '../../lib/constants/crawl-defaults';
import { LogTerminal, RecordsTable } from './shared-components';
import { copyJson, selectorWinnerLabel } from './shared';
import { MarkdownOutputPanel } from './markdown-output';
import type { CrawlRunScreenModel } from './use-crawl-run-screen-model';

export function RunOutputContent({ model }: { model: CrawlRunScreenModel }) {
  return (
    <>
      <MarkdownRunOutput model={model} />

      <TableRunOutput model={model} />

      <JsonRunOutput model={model} />

      <LogsRunOutput model={model} />

      <LearningRunOutput model={model} />
    </>
  );
}

function MarkdownRunOutput({ model }: { model: CrawlRunScreenModel }) {
  const { jsonRecordsQuery, records, markdownDocument, emptyRecordsState } = model;
  if (model.effectiveOutputTab !== 'markdown') return null;
  return (
    <MarkdownOutputPanel
      isLoading={jsonRecordsQuery.isLoading && !records.length}
      markdown={markdownDocument}
      emptyTitle={emptyRecordsState.title}
      emptyDescription={emptyRecordsState.description}
    />
  );
}

function TableRunOutput({ model }: { model: CrawlRunScreenModel }) {
  const {
    tableRecordsQuery,
    tableRecords,
    visibleColumns,
    visibleSelectedIds,
    selectAll,
    toggleRecord,
    hasMoreTableRecords,
    tableTotal,
    setTablePage,
    emptyRecordsState,
  } = model;
  if (model.effectiveOutputTab !== 'table') return null;
  return (
    <div className="min-h-[55vh] space-y-3">
      {tableRecordsQuery.isLoading && !tableRecords.length ? (
        <DataRegionLoading count={5} className="px-0" />
      ) : tableRecords.length ? (
        <div className="space-y-3">
          <RecordsTable
            records={tableRecords}
            visibleColumns={visibleColumns}
            selectedIds={visibleSelectedIds}
            onSelectAll={(checked) =>
              selectAll(checked ? tableRecords.map((record) => record.id) : [])
            }
            onToggleRow={toggleRecord}
          />
          {hasMoreTableRecords ? (
            <div className="table-footer-rail flex items-center justify-between rounded-md px-6 py-2">
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
  );
}

function JsonRunOutput({ model }: { model: CrawlRunScreenModel }) {
  const {
    ecommerceDetailRun,
    records,
    setAlertBuilderOpen,
    recordsJson,
    hasMoreJsonRecords,
    jsonRecords,
    recordsTotal,
    setJsonVisibleCount,
    recordsFetchCapReached,
  } = model;
  if (model.effectiveOutputTab !== 'json') return null;
  return (
    <div className="relative min-h-[55vh]">
      <div className="absolute top-2 right-2 z-10 flex items-center gap-2">
        {ecommerceDetailRun && records.length ? (
          <Button variant="action" type="button" onClick={() => setAlertBuilderOpen(true)}>
            <Bell className="size-3.5" />
            Alert
          </Button>
        ) : null}
        <Button variant="quiet" type="button" onClick={() => void copyJson(records)}>
          <Copy className="size-3.5" />
          Copy
        </Button>
      </div>
      <pre className="crawl-terminal crawl-terminal-json max-h-[72vh] min-h-[55vh]">
        {syntaxHighlightJsonNodes(recordsJson)}
      </pre>
      {hasMoreJsonRecords ? (
        <div className="surface-muted text-muted type-body mt-2 flex items-center justify-between rounded-md px-6 py-2">
          <span>
            JSON previewing {jsonRecords.length} of {recordsTotal} records
          </span>
          <Button
            variant="neutral"
            type="button"
            onClick={() =>
              setJsonVisibleCount((current) => current + CRAWL_DEFAULTS.TABLE_PAGE_SIZE * 4)
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
  );
}

function LogsRunOutput({ model }: { model: CrawlRunScreenModel }) {
  const { logs, batchSourceRecords, run, logViewportRef } = model;
  if (model.effectiveOutputTab !== 'logs') return null;
  return (
    <div className="min-h-[55vh]">
      <LogTerminal
        logs={logs}
        records={batchSourceRecords}
        requestedFields={run?.requested_fields ?? []}
        viewportRef={logViewportRef}
      />
    </div>
  );
}

function LearningRunOutput({ model }: { model: CrawlRunScreenModel }) {
  const {
    domainRecipeQuery,
    domainRecipe,
    recipeActionError,
    recipeActionPending,
    applyFieldLearningAction,
  } = model;
  if (model.effectiveOutputTab !== 'learning') return null;
  return (
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
          {recipeActionError ? <InlineAlert tone="danger" message={recipeActionError} /> : null}
          <Card className="section-card space-y-4">
            <SectionHeader
              title="Run Learning"
              description={`Review extraction evidence for ${domainRecipe.domain} on ${domainRecipe.surface}. Keep what should compound, reject what should not.`}
            />
            <div className="grid gap-3 md:grid-cols-2">
              <div className="surface-muted text-secondary type-body rounded-md px-6 py-3 leading-relaxed">
                <div className="field-label mb-1">Requested Coverage</div>
                Requested: {domainRecipe.requested_field_coverage.requested.join(', ') || 'None'}
                <br />
                Found: {domainRecipe.requested_field_coverage.found.join(', ') || 'None'}
                <br />
                Missing: {domainRecipe.requested_field_coverage.missing.join(', ') || 'None'}
              </div>
              <div className="surface-muted text-secondary type-body rounded-md px-6 py-3 leading-relaxed">
                <div className="field-label mb-1">Acquisition Evidence</div>
                Method: {domainRecipe.acquisition_evidence.actual_fetch_method || '—'}
                <br />
                Browser Used: {domainRecipe.acquisition_evidence.browser_used ? 'Yes' : 'No'}
                <br />
                Browser Reason: {domainRecipe.acquisition_evidence.browser_reason || '—'}
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
                  Keep accepted field evidence or reject bad field evidence for future runs on this
                  domain and surface.
                </p>
              </div>
              {domainRecipe.field_learning.length ? (
                <div className="space-y-2">
                  {domainRecipe.field_learning.map((item) => {
                    const keepPending = recipeActionPending === `field:${item.field_name}:keep`;
                    const rejectPending = recipeActionPending === `field:${item.field_name}:reject`;
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
                                  tone={item.feedback.action === 'reject' ? 'warning' : 'success'}
                                >
                                  {item.feedback.action}
                                </Badge>
                              ) : null}
                            </div>
                            <div className="type-caption mt-1">
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
                <div className="surface-muted rounded-lg border border-dashed px-6 py-3">
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
  );
}
