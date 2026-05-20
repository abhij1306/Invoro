'use client';

import Link from 'next/link';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowRightCircle, Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';

import { ConfirmDialog } from '../../components/ui/dialog';
import { Button } from '../../components/ui/primitives';
import {
  DataRegionEmpty,
  DataRegionError,
  InlineAlert,
  DataRegionLoading,
  PageHeader,
  SurfacePanel,
  TableSurface,
} from '../../components/ui/patterns';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../../components/ui/table';
import { api } from '../../lib/api';
import { formatRelativeTime } from '../../lib/format/date';

export default function ProjectsPage() {
  const queryClient = useQueryClient();
  const [deleteTarget, setDeleteTarget] = useState<{
    id: number;
    name: string;
  } | null>(null);
  const [error, setError] = useState('');
  const projectsQuery = useQuery({
    queryKey: ['orchestration-projects'],
    queryFn: api.listOrchestrationProjects,
  });
  const deleteMutation = useMutation({
    mutationFn: (projectId: number) => api.deleteOrchestrationProject(projectId),
    onSuccess: async () => {
      setDeleteTarget(null);
      await queryClient.invalidateQueries({ queryKey: ['orchestration-projects'] });
    },
    onError: (mutationError) =>
      setError(mutationError instanceof Error ? mutationError.message : 'Unable to delete project.'),
  });
  const projects = projectsQuery.data ?? [];

  return (
    <div className="page-stack-lg">
      <PageHeader
        title="Projects"
        description="Business workflows backed by normal crawl runs."
        actions={
          <Button asChild size="sm">
            <Link href="/projects/new">
              <Plus className="size-3.5" />
              New Project
            </Link>
          </Button>
        }
      />
      {error ? <InlineAlert message={error} /> : null}
      <SurfacePanel>
        <div className="border-divider flex items-center justify-between border-b px-4 py-3">
          <div>
            <p className="type-label m-0">Active projects</p>
            <p className="text-muted m-0 text-sm">
              Grouped workflows, runs, monitors, and exports.
            </p>
          </div>
        </div>
        <TableSurface>
          {projectsQuery.isError ? (
            <DataRegionError message="Unable to load projects." />
          ) : projectsQuery.isPending ? (
            <DataRegionLoading count={5} />
          ) : projects.length ? (
            <Table className="compact-data-table table-fixed">
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[32%]">Project</TableHead>
                  <TableHead className="w-[20%]">Competitors</TableHead>
                  <TableHead className="w-[18%]">Category</TableHead>
                  <TableHead className="w-[18%]">Updated</TableHead>
                  <TableHead className="w-[16%] text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {projects.map((project) => (
                  <TableRow key={project.id}>
                    <TableCell>
                      <div className="min-w-0">
                        <Link
                          href={`/projects/${project.id}`}
                          className="link-accent block truncate font-medium no-underline"
                        >
                          {project.name}
                        </Link>
                        <p className="text-muted m-0 truncate text-xs">{project.description}</p>
                      </div>
                    </TableCell>
                    <TableCell className="truncate">
                      {project.competitors.join(', ') || '-'}
                    </TableCell>
                    <TableCell className="truncate">{project.category || '-'}</TableCell>
                    <TableCell>{formatRelativeTime(project.updated_at)}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button asChild size="sm" variant="action">
                          <Link href={`/projects/${project.id}`}>
                            Open
                            <ArrowRightCircle className="size-3" />
                          </Link>
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="destructive"
                          onClick={() => setDeleteTarget({ id: project.id, name: project.name })}
                        >
                          <Trash2 className="size-3.5" />
                          Delete
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <DataRegionEmpty
              title="No projects yet"
              description="Create a guided pricing project."
            />
          )}
        </TableSurface>
      </SurfacePanel>
      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        title="Delete this project?"
        description={
          deleteTarget
            ? `This permanently deletes project "${deleteTarget.name}" and its workflow shells. Linked crawl runs and promoted monitors stay.`
            : ''
        }
        confirmLabel="Delete Project"
        pending={deleteMutation.isPending}
        danger
        error={error || undefined}
        onConfirm={() => {
          if (deleteTarget) {
            deleteMutation.mutate(deleteTarget.id);
          }
        }}
      />
    </div>
  );
}
