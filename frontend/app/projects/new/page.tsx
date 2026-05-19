'use client';

import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { Rocket, Settings2 } from 'lucide-react';

import { Button, Input } from '../../../components/ui/primitives';
import { InlineAlert, PageHeader, SurfacePanel } from '../../../components/ui/patterns';
import { api } from '../../../lib/api';

const defaultFields = ['price', 'was_price', 'availability', 'title'];
const optionalFields = ['discount_percent', 'rating', 'seller_name', 'image_count'];

export default function NewProjectPage() {
  const router = useRouter();
  const [name, setName] = useState('Competitive pricing watch');
  const [description, setDescription] = useState('');
  const [listingUrl, setListingUrl] = useState('');
  const [category, setCategory] = useState('jeans');
  const [fields, setFields] = useState<string[]>(defaultFields);
  const [maxPages, setMaxPages] = useState(5);
  const [maxItems, setMaxItems] = useState(200);
  const [error, setError] = useState('');

  const launchMutation = useMutation({
    mutationFn: async () => {
      const listingUrlValue = listingUrl.trim();
      const competitors = domainListFromUrls([listingUrlValue]);
      const project = await api.createOrchestrationProject({
        name,
        description,
        competitors,
        category,
        tracked_fields: fields,
      });
      const workflow = await api.createOrchestrationWorkflow({
        template_id: 'competitive_pricing_snapshot',
        project_id: project.id,
        label: name,
        intent_inputs: {
          listing_url: listingUrlValue,
          category,
          fields,
        },
        advanced_overrides: {
          max_pages_listing: maxPages,
          max_items_detail: maxItems,
        },
      });
      return { project, workflow };
    },
    onSuccess: ({ project }) => router.push(`/projects/${project.id}`),
    onError: (mutationError) =>
      setError(mutationError instanceof Error ? mutationError.message : 'Project launch failed.'),
  });

  function toggleField(field: string) {
    setFields((current) =>
      current.includes(field) ? current.filter((item) => item !== field) : [...current, field],
    );
  }

  return (
    <div className="page-stack-lg">
      <PageHeader title="New Project" description="Competitive Pricing Snapshot MVP." />
      {error ? <InlineAlert message={error} /> : null}
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="page-stack">
          <SurfacePanel className="p-5">
            <p className="type-label mb-3">Use case</p>
            <div className="border-accent bg-accent-subtle rounded-[var(--radius-md)] border p-4">
              <p className="text-foreground m-0 font-semibold">Competitive Pricing Snapshot</p>
              <p className="text-muted m-0 mt-1 text-sm">
                Listing crawl, detail crawl, comparison table, monitor continuation.
              </p>
            </div>
          </SurfacePanel>
          <SurfacePanel className="grid gap-4 p-5 md:grid-cols-2">
            <label className="space-y-1.5">
              <span className="type-label">Project name</span>
              <Input value={name} onChange={(event) => setName(event.target.value)} />
            </label>
            <label className="space-y-1.5">
              <span className="type-label">Description</span>
              <Input value={description} onChange={(event) => setDescription(event.target.value)} />
            </label>
            <label className="space-y-1.5">
              <span className="type-label">Listing URL</span>
              <Input value={listingUrl} onChange={(event) => setListingUrl(event.target.value)} />
            </label>
            <label className="space-y-1.5">
              <span className="type-label">Category</span>
              <Input value={category} onChange={(event) => setCategory(event.target.value)} />
            </label>
          </SurfacePanel>
          <SurfacePanel className="p-5">
            <p className="type-label mb-3">Fields</p>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {[...defaultFields, ...optionalFields].map((field) => (
                <label
                  key={field}
                  className="border-border bg-background-elevated flex min-h-10 items-center gap-2 rounded-[var(--radius-md)] border px-3 text-sm"
                >
                  <input
                    type="checkbox"
                    checked={fields.includes(field)}
                    onChange={() => toggleField(field)}
                  />
                  <span>{field}</span>
                </label>
              ))}
            </div>
          </SurfacePanel>
          <SurfacePanel className="grid gap-4 p-5 md:grid-cols-2">
            <label className="space-y-1.5">
              <span className="type-label">Listing pages</span>
              <Input
                type="number"
                min={1}
                max={100}
                value={maxPages}
                onChange={(event) => setMaxPages(Number(event.target.value))}
              />
            </label>
            <label className="space-y-1.5">
              <span className="type-label">Detail items</span>
              <Input
                type="number"
                min={1}
                max={1000}
                value={maxItems}
                onChange={(event) => setMaxItems(Number(event.target.value))}
              />
            </label>
          </SurfacePanel>
        </div>
        <SurfacePanel className="h-fit p-5">
          <div className="flex items-center gap-2">
            <Settings2 className="text-accent size-4" />
            <p className="type-label m-0">Review</p>
          </div>
          <dl className="mt-4 space-y-3 text-sm">
            <div>
              <dt className="text-muted">Listing URL</dt>
              <dd className="m-0 break-all">{listingUrl || '-'}</dd>
            </div>
            <div>
              <dt className="text-muted">Category</dt>
              <dd className="m-0">{category || '-'}</dd>
            </div>
            <div>
              <dt className="text-muted">Fields</dt>
              <dd className="m-0">{fields.join(', ')}</dd>
            </div>
            <div>
              <dt className="text-muted">Advanced</dt>
              <dd className="m-0">fetch_mode auto, llm_enabled false</dd>
            </div>
          </dl>
          <Button
            type="button"
            className="mt-5 w-full"
            disabled={!name.trim() || !listingUrl.trim() || launchMutation.isPending}
            onClick={() => launchMutation.mutate()}
          >
            <Rocket className="size-3.5" />
            {launchMutation.isPending ? 'Launching...' : 'Launch Project'}
          </Button>
        </SurfacePanel>
      </div>
    </div>
  );
}

function domainListFromUrls(urls: string[]): string[] {
  const domains: string[] = [];
  for (const rawUrl of urls) {
    try {
      const host = new URL(rawUrl).hostname.replace(/^www\./, '');
      if (host && !domains.includes(host)) {
        domains.push(host);
      }
    } catch {
      continue;
    }
  }
  return domains;
}
