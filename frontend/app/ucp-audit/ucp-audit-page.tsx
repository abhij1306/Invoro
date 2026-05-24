'use client';

import { useMemo, useState } from 'react';
import { Play, RefreshCcw, Layers, CheckSquare, History, Network } from 'lucide-react';

import { InlineAlert, PageHeader } from '../../components/ui/patterns';
import { Button, Input } from '../../components/ui/primitives';
import { HistoryDrawer, type HistoryItem } from '../../components/ui/history-drawer';
import {
  UcpContractPanel,
  UcpDimensionTable,
  UcpFixSequence,
  UcpScoreSummary,
} from './ucp-audit-components';
import { useUcpAudit } from './use-ucp-audit';
import { cn } from '../../lib/utils';

export default function UcpAuditPage() {
  const controller = useUcpAudit();
  const [activeTab, setActiveTab] = useState<'compliance' | 'contract' | 'fix-sequence'>(
    'compliance',
  );
  const [historyOpen, setHistoryOpen] = useState(false);

  const description =
    controller.activeJob && controller.report
      ? `${controller.activeJob.domain} · score ${controller.report.overall_score}`
      : 'Run deterministic UCP compliance checks against ecommerce domains.';

  const tabOptions = [
    { id: 'compliance', label: 'Compliance Index', icon: Layers },
    { id: 'contract', label: 'Contract Checks', icon: Network },
    { id: 'fix-sequence', label: 'Repair Roadmap', icon: CheckSquare },
  ] as const;

  const historyItems: HistoryItem[] = useMemo(() => {
    return controller.historyItems.map((job) => ({
      id: job.id,
      status: job.status,
      created_at: job.created_at,
      label: job.domain,
      meta:
        job.summary?.overall_score != null
          ? `${job.summary.overall_score}/100 index`
          : 'Audit run queued',
    }));
  }, [controller.historyItems]);

  return (
    <div className="page-stack gap-5">
      <PageHeader
        title="UCP Audit"
        description={description}
        actions={
          <div className="flex w-full flex-wrap items-center justify-end gap-2">
            <Button type="button" variant="neutral" size="sm" onClick={() => setHistoryOpen(true)}>
              <History className="size-3" />
              History
            </Button>
            <Button
              type="button"
              variant="neutral"
              size="sm"
              onClick={() => void controller.detailQuery.refetch()}
              disabled={!controller.resolvedJobId || controller.detailQuery.isFetching}
            >
              <RefreshCcw
                className={cn('size-3', controller.detailQuery.isFetching && 'animate-spin')}
              />
              Refresh
            </Button>
            <Button
              type="button"
              variant="action"
              size="sm"
              onClick={controller.startAudit}
              disabled={controller.createPending || controller.isRunning}
            >
              <Play className="size-3" />
              {controller.createPending || controller.isRunning ? 'Auditing...' : 'Start Audit'}
            </Button>
          </div>
        }
      />

      {controller.error ? (
        <div className="animate-in fade-in slide-in-from-top-1 duration-200">
          <InlineAlert tone="danger" message={controller.error} />
        </div>
      ) : null}

      {/* Horizontal Compact Config Ribbon (Saves huge space) */}
      <section className="border-border bg-panel border-l-accent relative overflow-hidden rounded-[var(--radius-lg)] border border-l-4 p-4 shadow-sm">
        <div className="grid gap-4 sm:grid-cols-[1fr_140px] sm:items-end">
          <label className="grid gap-1">
            <span className="field-label">Target Domain</span>
            <Input
              value={controller.domain}
              onChange={(event) => controller.setDomain(event.target.value)}
              placeholder="example-domain.com"
              className="border-border focus:border-accent h-[var(--control-height)] font-mono text-sm"
              aria-label="Domain"
            />
          </label>

          <label className="grid gap-1">
            <span className="field-label">Sample Size</span>
            <Input
              type="number"
              min={1}
              max={50}
              value={controller.options.sample_size}
              onChange={(event) =>
                controller.setOptions((current) => ({
                  ...current,
                  sample_size: Number(event.target.value || 1),
                }))
              }
              className="h-[var(--control-height)] font-mono text-sm"
            />
          </label>
        </div>
      </section>

      {/* Full-Width Analytical Workspace Dashboard */}
      <div className="page-stack w-full gap-5">
        {/* Overall Score & Dimension metrics */}
        <UcpScoreSummary
          report={controller.report}
          job={controller.activeJob}
          loading={controller.detailQuery.isLoading || controller.isRunning}
        />

        {/* Workspace tab selectors */}
        <div className="border-border bg-panel flex w-full flex-wrap gap-1 rounded-[var(--radius-lg)] border p-1">
          {tabOptions.map((tab) => {
            const TabIcon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'type-control flex min-w-[120px] flex-1 cursor-pointer items-center justify-center gap-2 rounded-[var(--radius-md)] px-3 py-2 transition-all',
                  isActive
                    ? 'bg-accent text-accent-fg shadow-sm'
                    : 'text-muted hover:bg-background-alt hover:text-foreground',
                )}
              >
                <TabIcon className="size-3.5" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Tab viewports spanning full width */}
        <div className="animate-in fade-in w-full min-w-0 duration-300">
          {activeTab === 'compliance' && (
            <UcpDimensionTable
              report={controller.report}
              loading={controller.detailQuery.isLoading}
            />
          )}
          {activeTab === 'contract' && <UcpContractPanel report={controller.report} />}
          {activeTab === 'fix-sequence' && <UcpFixSequence report={controller.report} />}
        </div>
      </div>

      {/* Drawer Overlay for Timeline History */}
      <HistoryDrawer
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        items={historyItems}
        activeId={controller.resolvedJobId}
        onSelect={(id) => {
          const matched = controller.historyItems.find((j) => j.id === id);
          if (matched) controller.selectJob(matched);
        }}
        title="UCP Compliance Audit Runs"
      />
    </div>
  );
}
