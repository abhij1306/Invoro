'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, Clipboard, KeyRound, PlugZap, Terminal, Trash2, X } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useMemo, useState } from 'react';

import { InlineAlert, SectionCard, StatusDot } from '../../components/ui/patterns';
import { Button, Field, Input } from '../../components/ui/primitives';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../../components/ui/table';
import { api, getPublicApiBaseUrl } from '../../lib/api';
import type { ApiKeyCreated } from '../../lib/api/types';
import { formatJobsTimestamp } from '../../lib/format/date';

const apiKeysQueryKey = ['api-keys'] as const;

export default function ApiMcpPage() {
  const queryClient = useQueryClient();
  const [name, setName] = useState('');
  const [createdKey, setCreatedKey] = useState<ApiKeyCreated | null>(null);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const publicApiBaseUrl = getPublicApiBaseUrl();

  const keysQuery = useQuery({
    queryKey: apiKeysQueryKey,
    queryFn: api.listApiKeys,
  });
  const createMutation = useMutation({
    mutationFn: api.createApiKey,
    onSuccess: async (created) => {
      setCreatedKey(created);
      setName('');
      setError('');
      setNotice('API key created. Copy it now; Invoro will not show it again.');
      await queryClient.invalidateQueries({ queryKey: apiKeysQueryKey });
    },
    onError: (mutationError) => {
      setNotice('');
      setError(errorMessage(mutationError, 'Could not create API key.'));
    },
  });
  const revokeMutation = useMutation({
    mutationFn: api.revokeApiKey,
    onSuccess: async () => {
      setError('');
      setNotice('API key revoked.');
      await queryClient.invalidateQueries({ queryKey: apiKeysQueryKey });
    },
    onError: (mutationError) => {
      setNotice('');
      setError(errorMessage(mutationError, 'Could not revoke API key.'));
    },
  });

  const keys = keysQuery.data ?? [];
  const bearer = createdKey?.api_key ?? '<YOUR_API_KEY>';
  const curlExample = useMemo(
    () => `curl -H "Authorization: Bearer ${bearer}" "${publicApiBaseUrl}/capabilities"`,
    [bearer, publicApiBaseUrl],
  );
  const mcpExample = useMemo(
    () =>
      `$env:INVORO_API_KEY='${bearer}'\n$env:INVORO_API_BASE_URL='${publicApiBaseUrl}'\ncd backend\nuv run --frozen --extra mcp python -m app.mcp_server.server`,
    [bearer, publicApiBaseUrl],
  );

  function createKey() {
    const cleaned = name.trim();
    if (!cleaned) {
      setNotice('');
      setError('Enter a key name.');
      return;
    }
    setError('');
    createMutation.mutate(cleaned);
  }

  async function copyText(value: string, label: string) {
    try {
      await navigator.clipboard.writeText(value);
      setError('');
      setNotice(`${label} copied.`);
    } catch {
      setNotice('');
      setError(`Could not copy ${label.toLowerCase()}. Select and copy it manually.`);
    }
  }

  return (
    <div className="page-stack-lg">
      {notice ? <InlineAlert tone="success" message={notice} /> : null}
      {error ? <InlineAlert tone="danger" message={error} /> : null}

      {createdKey ? (
        <SectionCard
          title="Save your new API key"
          description="This secret is shown once. Store it in a password manager or secret store."
          icon={KeyRound}
          action={
            <Button
              variant="quiet"
              size="sm"
              aria-label="Dismiss new API key"
              onClick={() => setCreatedKey(null)}
            >
              <X className="size-3.5" />
              Dismiss
            </Button>
          }
        >
          <div className="flex min-w-0 items-center gap-2">
            <code className="border-border bg-background text-foreground min-w-0 flex-1 overflow-x-auto rounded-md border px-3 py-2 font-mono text-sm">
              {createdKey.api_key}
            </code>
            <Button
              variant="secondary"
              onClick={() => void copyText(createdKey.api_key, 'API key')}
            >
              <Clipboard className="size-3.5" />
              Copy
            </Button>
          </div>
        </SectionCard>
      ) : null}

      <SectionCard
        title="Create API key"
        description="Keys inherit your account access and authenticate both the public REST API and MCP server."
        icon={KeyRound}
      >
        <form
          className="flex items-end gap-3 max-sm:flex-col max-sm:items-stretch"
          onSubmit={(event) => {
            event.preventDefault();
            createKey();
          }}
        >
          <Field label="Key name" required className="min-w-0 flex-1">
            <Input
              value={name}
              maxLength={100}
              autoComplete="off"
              placeholder="Local MCP"
              onChange={(event) => setName(event.target.value)}
            />
          </Field>
          <Button type="submit" disabled={!name.trim() || createMutation.isPending}>
            <KeyRound className="size-3.5" />
            {createMutation.isPending ? 'Creating…' : 'Create key'}
          </Button>
        </form>
      </SectionCard>

      <SectionCard
        title="API keys"
        description="Revoked credentials stop authenticating immediately. Last used tracks real API use only."
        icon={KeyRound}
      >
        {keysQuery.isPending ? (
          <p className="type-body-sm">Loading API keys…</p>
        ) : keysQuery.isError ? (
          <InlineAlert
            tone="danger"
            message={
              <span>
                Could not load API keys.{' '}
                <button className="font-medium underline" onClick={() => void keysQuery.refetch()}>
                  Retry
                </button>
              </span>
            }
          />
        ) : keys.length ? (
          <div className="border-border overflow-hidden rounded-md border">
            <Table className="min-w-[760px]">
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Prefix</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last used</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {keys.map((key) => (
                  <TableRow key={key.id}>
                    <TableCell className="text-foreground font-medium">{key.name}</TableCell>
                    <TableCell className="font-mono">{key.key_prefix}…</TableCell>
                    <TableCell>
                      <span className="inline-flex items-center gap-1.5 text-sm">
                        <StatusDot tone={key.is_active ? 'success' : 'neutral'} />
                        {key.is_active ? 'Active' : 'Revoked'}
                      </span>
                    </TableCell>
                    <TableCell>{formatTimestamp(key.last_used_at)}</TableCell>
                    <TableCell>{formatTimestamp(key.created_at)}</TableCell>
                    <TableCell className="text-right">
                      {key.is_active ? (
                        <Button
                          variant="destructive"
                          size="sm"
                          disabled={revokeMutation.isPending}
                          onClick={() => revokeMutation.mutate(key.id)}
                        >
                          <Trash2 className="size-3.5" />
                          Revoke
                        </Button>
                      ) : (
                        <span className="text-muted text-xs">Revoked</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : (
          <p className="type-body-sm">No API keys yet. Create one above to connect a client.</p>
        )}
      </SectionCard>

      <div className="grid gap-4 xl:grid-cols-2">
        <QuickStartCard
          title="Public REST API"
          description={`Bearer-authenticated endpoints live at ${publicApiBaseUrl}. Single-URL extraction is HTTP-only.`}
          icon={Terminal}
          example={curlExample}
          onCopy={() => void copyText(curlExample, 'REST example')}
        />
        <QuickStartCard
          title="MCP server"
          description="Run the thin MCP wrapper from this repository. It calls the same public API and uses the same key."
          icon={PlugZap}
          example={mcpExample}
          onCopy={() => void copyText(mcpExample, 'MCP command')}
        />
      </div>
    </div>
  );
}

function QuickStartCard({
  title,
  description,
  icon,
  example,
  onCopy,
}: Readonly<{
  title: string;
  description: string;
  icon: LucideIcon;
  example: string;
  onCopy: () => void;
}>) {
  return (
    <SectionCard
      title={title}
      description={description}
      icon={icon}
      action={
        <Button variant="secondary" size="sm" onClick={onCopy}>
          <Clipboard className="size-3.5" />
          Copy
        </Button>
      }
    >
      <pre className="border-border bg-background text-secondary overflow-x-auto rounded-md border p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap">
        {example}
      </pre>
      <div className="text-success-text mt-3 flex items-center gap-1.5 text-xs">
        <Check className="size-3.5" />
        Uses existing API authentication and rate limits
      </div>
    </SectionCard>
  );
}

function formatTimestamp(value: string | null) {
  return value ? formatJobsTimestamp(value) : 'Never';
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error && error.message ? error.message : fallback;
}
