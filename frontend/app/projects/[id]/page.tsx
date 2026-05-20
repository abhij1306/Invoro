'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ExternalLink, FileDown, Play, Radar, Trash2 } from 'lucide-react';
import { useState } from 'react';

import { ConfirmDialog } from '../../../components/ui/dialog';
import { Badge, Button } from '../../../components/ui/primitives';
import {
  DataRegionEmpty,
  DataRegionError,
  DataRegionLoading,
  InlineAlert,
  PageHeader,
  StatusDot,
  SurfacePanel,
  TableSurface,
} from '../../../components/ui/patterns';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../../../components/ui/table';
import { api } from '../../../lib/api';
import { formatRelativeTime } from '../../../lib/format/date';

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const projectId = Number(params.id);
  const [notice, setNotice] = useState('');
  const [deleteOpen, setDeleteOpen] = useState(false);

  const projectQuery = useQuery({
    queryKey: ['orchestration-project', projectId],
    queryFn: () => api.getOrchestrationProject(projectId),
    enabled: Number.isFinite(projectId),
  });
  const workflowsQuery = useQuery({
    queryKey: ['orchestration-workflows', projectId],
    queryFn: () => api.listOrchestrationWorkflows(projectId),
    enabled: Number.isFinite(projectId),
    refetchInterval: (query) => {
      const workflows = query.state.data ?? [];
      return workflows.some((workflow) => ['queued', 'running'].includes(workflow.status))
        ? 5000
        : false;
    },
  });
  const latestWorkflow = workflowsQuery.data?.[0] ?? null;
  const statusQuery = useQuery({
    queryKey: ['orchestration-workflow-status', latestWorkflow?.id],
    queryFn: () => api.getOrchestrationWorkflowStatus(latestWorkflow?.id ?? 0),
    enabled: Boolean(latestWorkflow?.id),
    refetchInterval: (query) => {
      const workflow = query.state.data;
      return workflow && ['queued', 'running'].includes(workflow.status) ? 5000 : false;
    },
  });
  const workflow = statusQuery.data ?? latestWorkflow;
  const comparisonQuery = useQuery({
    queryKey: ['orchestration-price-comparison', workflow?.id],
    queryFn: () => api.getPriceComparison(workflow?.id ?? 0),
    enabled: Boolean(workflow?.id),
  });
  const promoteMutation = useMutation({
    mutationFn: () => api.promoteOrchestrationWorkflow(workflow?.id ?? 0, {}),
    onSuccess: async (response) => {
      setNotice(`Monitor created - monitor_id: ${response.monitor_id}`);
      await queryClient.invalidateQueries({ queryKey: ['orchestration-workflow-status'] });
      await queryClient.invalidateQueries({ queryKey: ['monitors'] });
    },
  });
  const deleteMutation = useMutation({
    mutationFn: () => api.deleteOrchestrationProject(projectId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['orchestration-projects'] });
      router.push('/projects');
    },
  });

  if (projectQuery.isPending) {
    return <DataRegionLoading count={6} />;
  }
  if (projectQuery.isError || !projectQuery.data) {
    return <DataRegionError message="Unable to load project." />;
  }

  const comparison = comparisonQuery.data;
  const detailRunId = comparison?.detail_run_id ?? null;

  return (
    <div className="page-stack-lg">
      <PageHeader
        title={projectQuery.data.name}
        description={`${projectQuery.data.category || 'Unscoped'} - ${projectQuery.data.competitors.join(', ')}`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {detailRunId ? (
              <>
                <Button asChild size="sm" variant="download">
                  <a href={api.exportCsv(detailRunId)}>
                    <FileDown className="size-3.5" />
                    CSV
                  </a>
                </Button>
                <Button asChild size="sm" variant="neutral">
                  <Link href={`/crawl?run_id=${detailRunId}`}>
                    <ExternalLink className="size-3.5" />
                    Crawl Studio
                  </Link>
                </Button>
              </>
            ) : null}
            <Button
              type="button"
              size="sm"
              variant="action"
              disabled={!workflow || workflow.status !== 'completed' || promoteMutation.isPending}
              onClick={() => promoteMutation.mutate()}
            >
              <Radar className="size-3.5" />
              Promote
            </Button>
            <Button
              type="button"
              size="sm"
              variant="destructive"
              disabled={deleteMutation.isPending}
              onClick={() => setDeleteOpen(true)}
            >
              <Trash2 className="size-3.5" />
              Delete
            </Button>
          </div>
        }
      />
      {notice ? (
        <div className="alert-surface alert-success px-3 py-2 text-sm">{notice}</div>
      ) : null}
      {promoteMutation.isError ? (
        <InlineAlert
          message={
            promoteMutation.error instanceof Error
              ? promoteMutation.error.message
              : 'Promotion failed.'
          }
        />
      ) : null}
      {deleteMutation.isError ? (
        <InlineAlert
          message={
            deleteMutation.error instanceof Error ? deleteMutation.error.message : 'Delete failed.'
          }
        />
      ) : null}
      <div className="grid gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
        <SurfacePanel className="p-5">
          <div className="flex items-center justify-between">
            <p className="type-label m-0">Workflow</p>
            {workflow ? (
              <Badge tone={workflow.status === 'completed' ? 'success' : 'info'} flat>
                {workflow.status}
              </Badge>
            ) : null}
          </div>
          {workflow ? (
            <div className="mt-4 space-y-3">
              <p className="text-foreground m-0 font-medium">{workflow.label}</p>
              <p className="text-muted m-0 text-sm">
                Started {formatRelativeTime(workflow.created_at)}
              </p>
              <div className="space-y-2">
                {workflow.steps.map((step) => (
                  <div
                    key={step.id}
                    className="border-border bg-background-elevated flex items-center justify-between rounded-[var(--radius-md)] border px-3 py-2 text-sm"
                  >
                    <span className="flex items-center gap-2">
                      <StatusDot
                        tone={
                          step.status === 'completed'
                            ? 'success'
                            : step.status === 'failed'
                              ? 'danger'
                              : 'info'
                        }
                      />
                      {formatStep(step.step_id)}
                    </span>
                    <span className="text-muted">
                      {step.run_id ? `run ${step.run_id}` : step.status}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : workflowsQuery.isPending ? (
            <DataRegionLoading count={3} />
          ) : (
            <DataRegionEmpty title="No workflows" description="Launch a project workflow first." />
          )}
        </SurfacePanel>
        <SurfacePanel>
          <div className="border-divider flex items-center justify-between border-b px-4 py-3">
            <div>
              <p className="type-label m-0">Price comparison</p>
              <p className="text-muted m-0 text-sm">Rows come from the detail crawl output.</p>
            </div>
            {workflow?.status === 'running' ? (
              <span className="text-muted inline-flex items-center gap-2 text-sm">
                <Play className="size-3.5" />
                Sequencing
              </span>
            ) : null}
          </div>
          <TableSurface>
            {comparisonQuery.isPending ? (
              <DataRegionLoading count={5} />
            ) : comparisonQuery.isError ? (
              <DataRegionError message="Unable to load comparison rows." />
            ) : comparison?.rows.length ? (
              <Table className="compact-data-table table-fixed">
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[30%]">Product</TableHead>
                    <TableHead className="w-[14%]">Brand</TableHead>
                    <TableHead className="w-[16%]">Domain</TableHead>
                    <TableHead className="w-[14%] text-right">Price</TableHead>
                    <TableHead className="w-[14%] text-right">Was</TableHead>
                    <TableHead className="w-[12%]">Availability</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {comparison.rows.map((row) => (
                    <TableRow key={row.record_id}>
                      <TableCell className="truncate">
                        <a
                          href={row.source_url}
                          target="_blank"
                          rel="noreferrer"
                          className="link-accent no-underline"
                        >
                          {row.product || row.source_url}
                        </a>
                      </TableCell>
                      <TableCell className="truncate">{row.brand || '-'}</TableCell>
                      <TableCell className="truncate">{row.domain || '-'}</TableCell>
                      <TableCell className="text-right tabular-nums">
                        {formatValue(row.price)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {formatValue(row.was_price)}
                      </TableCell>
                      <TableCell>{row.availability || '-'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <DataRegionEmpty
                title="No detail rows yet"
                description="Rows appear after listing and detail runs complete."
              />
            )}
          </TableSurface>
        </SurfacePanel>
      </div>
      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="Delete this project?"
        description={`This permanently deletes project "${projectQuery.data.name}" and its workflow shells. Linked crawl runs and promoted monitors stay.`}
        confirmLabel="Delete Project"
        pending={deleteMutation.isPending}
        danger
        onConfirm={() => deleteMutation.mutate()}
      />
    </div>
  );
}

function formatStep(value: string) {
  if (value === 'listing_run') return 'Listing run';
  if (value === 'detail_run') return 'Detail run';
  if (value === 'comparison_view') return 'Comparison view';
  return value;
}

function formatValue(value: unknown) {
  if (value === null || value === undefined || value === '') return '-';
  return String(value);
}
