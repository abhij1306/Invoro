'use client';

// Next.js App Router entrypoint for `/admin/llm`; invoked by file-system routing.
import { startTransition, useEffect, useState } from 'react';
import { CheckCircle2, PlugZap, Plus, Trash2 } from 'lucide-react';

import { Button, Dropdown, Field, Input } from '../../../components/ui/primitives';
import {
  DetailRow,
  InlineAlert,
  MutedPanelMessage,
  PageHeader,
  SectionCard,
  SurfaceSection,
} from '../../../components/ui/patterns';
import {
  Table,
  TableBody,
  TableHead,
  TableHeader,
  TableRow,
  TableCell,
} from '../../../components/ui/table';
import { api } from '../../../lib/api';
import type {
  LlmConfigCreatePayload,
  LlmConfigRecord,
  LlmCostLogRecord,
  LlmProviderCatalogItem,
} from '../../../lib/api/types';

const TASK_TYPES = [
  'general',
  'xpath_discovery',
  'missing_field_extraction',
  'field_cleanup_review',
  'page_classification',
  'schema_inference',
  'data_enrichment_semantic',
];

export default function AdminLlmPage() {
  const [providers, setProviders] = useState<LlmProviderCatalogItem[]>([]);
  const [configs, setConfigs] = useState<LlmConfigRecord[]>([]);
  const [costLog, setCostLog] = useState<LlmCostLogRecord[]>([]);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [form, setForm] = useState<LlmConfigCreatePayload>({
    provider: 'groq',
    model: 'llama-3.3-70b-versatile',
    task_type: 'xpath_discovery',
    api_key: '',
    per_domain_daily_budget_usd: '0',
    global_session_budget_usd: '0',
    is_active: true,
  });

  async function refreshRuntimeState() {
    try {
      const [nextConfigs, nextCostLog] = await Promise.all([
        api.listLlmConfigs(),
        api.listLlmCostLog(),
      ]);
      startTransition(() => {
        setConfigs(nextConfigs);
        setCostLog(nextCostLog);
      });
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Unable to load LLM settings.');
    }
  }

  async function handleSave() {
    setSaving(true);
    setError('');
    setMessage('');
    try {
      await api.createLlmConfig(form);
      setMessage('LLM config saved.');
      setForm((current) => ({ ...current, api_key: '' }));
      await refreshRuntimeState();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Unable to save LLM config.');
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    setTesting(true);
    setError('');
    setMessage('');
    try {
      const response = await api.testLlmConnection({
        provider: form.provider,
        model: form.model,
        api_key: form.api_key,
      });
      setMessage(response.message);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Connection test failed.');
    } finally {
      setTesting(false);
    }
  }

  async function handleDelete(configId: number) {
    setError('');
    setMessage('');
    try {
      await api.deleteLlmConfig(configId);
      setMessage('LLM config removed.');
      await refreshRuntimeState();
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : 'Unable to delete LLM config.');
    }
  }

  useEffect(() => {
    let cancelled = false;

    async function run() {
      try {
        const [nextProviders, nextConfigs, nextCostLog] = await Promise.all([
          api.listLlmProviders(),
          api.listLlmConfigs(),
          api.listLlmCostLog(),
        ]);
        if (cancelled) return;
        startTransition(() => {
          setProviders(nextProviders);
          setConfigs(nextConfigs);
          setCostLog(nextCostLog);
          const fallbackProvider = nextProviders[0];
          setForm((current) => {
            const matchingProvider = nextProviders.find(
              (provider) => provider.provider === current.provider,
            );
            if (matchingProvider) {
              const matchingModel = matchingProvider.recommended_models.includes(current.model);
              return matchingModel
                ? current
                : {
                    ...current,
                    model: matchingProvider.recommended_models[0] ?? current.model,
                  };
            }
            return {
              ...current,
              provider: fallbackProvider?.provider ?? current.provider,
              model: fallbackProvider?.recommended_models[0] ?? current.model,
            };
          });
        });
      } catch (nextError) {
        if (cancelled) return;
        setError(nextError instanceof Error ? nextError.message : 'Unable to load LLM settings.');
      }
    }

    void run();
    return () => {
      cancelled = true;
    };
  }, []);

  const recommendedModels =
    providers.find((provider) => provider.provider === form.provider)?.recommended_models ?? [];

  return (
    <div className="page-stack">
      <PageHeader
        title="LLM Config"
        description="Restore runtime provider control for selector suggestion, cleanup review, and extraction fallback tasks."
      />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        {/* ── Left column: create form + active configs */}
        <div className="page-stack">
          <SectionCard
            title="Create Config"
            description="Activate one provider/model per task. New active configs automatically replace the previous active config for the same task."
            className="space-y-5"
          >
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Provider">
                <Dropdown<string>
                  value={form.provider}
                  onChange={(provider) => {
                    const nextModel =
                      providers.find((row) => row.provider === provider)?.recommended_models?.[0] ??
                      '';
                    setForm((current) => ({
                      ...current,
                      provider,
                      model: nextModel || current.model,
                    }));
                  }}
                  options={providers.map((provider) => ({
                    value: provider.provider,
                    label: provider.label,
                  }))}
                />
              </Field>

              <Field label="Task">
                <Dropdown<string>
                  value={form.task_type}
                  onChange={(task_type) => setForm((current) => ({ ...current, task_type }))}
                  options={TASK_TYPES.map((taskType) => ({ value: taskType, label: taskType }))}
                />
              </Field>

              <Field label="Model" className="md:col-span-2">
                <Dropdown<string>
                  value={form.model}
                  onChange={(model) => setForm((current) => ({ ...current, model }))}
                  options={recommendedModels.map((model) => ({
                    value: model,
                    label: model,
                  }))}
                />
              </Field>

              <Field label="API Key" className="md:col-span-2">
                <Input
                  type="password"
                  value={form.api_key ?? ''}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, api_key: event.target.value }))
                  }
                  placeholder="Leave blank to rely on environment variables."
                />
              </Field>
            </div>

            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="neutral"
                onClick={() => void handleTest()}
                disabled={testing}
              >
                <PlugZap className="size-3.5" />
                {testing ? 'Testing…' : 'Test Connection'}
              </Button>
              <Button
                type="button"
                variant="action"
                onClick={() => void handleSave()}
                disabled={saving || !form.model.trim()}
              >
                <Plus className="size-3.5" />
                {saving ? 'Saving…' : 'Save Config'}
              </Button>
            </div>

            <div className="min-h-[52px]">
              {message ? <InlineAlert message={message} tone="neutral" /> : null}
              {error ? <InlineAlert message={error} tone="danger" /> : null}
            </div>
          </SectionCard>

          <SectionCard
            title="Active Configs"
            description="The active runtime snapshot available to selector discovery and cleanup tasks."
            className="space-y-4"
          >
            {configs.length ? (
              <div className="space-y-3">
                {configs.map((config) => (
                  <DetailRow key={config.id}>
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 space-y-1">
                        {/* Task name + active badge */}
                        <div className="flex items-center gap-2">
                          <span className="type-control text-foreground truncate !font-normal">
                            {config.task_type}
                          </span>
                          {config.is_active ? (
                            <span className="bg-success-bg text-success inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs leading-none font-normal">
                              <CheckCircle2 className="size-3" aria-hidden="true" />
                              active
                            </span>
                          ) : null}
                        </div>
                        {/* Provider · model */}
                        <p className="type-caption text-muted m-0">
                          {config.provider} · {config.model}
                        </p>
                        {/* API key status */}
                        <p className="type-caption text-muted m-0">
                          {config.api_key_set ? config.api_key_masked : 'env-backed or unset'}
                        </p>
                      </div>
                      <Button
                        type="button"
                        variant="destructive"
                        size="icon"
                        onClick={() => void handleDelete(config.id)}
                        aria-label="Delete config"
                      >
                        <Trash2 className="size-3.5" />
                      </Button>
                    </div>
                  </DetailRow>
                ))}
              </div>
            ) : (
              <MutedPanelMessage title="No configs saved" description="No LLM configs saved yet." />
            )}
          </SectionCard>
        </div>

        {/* ── Right column: cost log */}
        <div className="page-stack">
          <SectionCard
            title="Recent Cost Log"
            description="Latest LLM usage events recorded by the backend runtime."
            className="flex-1"
          >
            {costLog.length ? (
              <div className="custom-scrollbar max-h-[700px] overflow-x-auto overflow-y-auto">
                {/* Shared Table components — type-label-mono headers, accent hover rows */}
                <Table className="min-w-[850px] table-fixed">
                  <TableHeader>
                    <TableRow className="border-divider/50">
                      <TableHead className="w-[140px] px-0">Usage &amp; Cost</TableHead>
                      <TableHead className="w-[180px]">Task Type</TableHead>
                      <TableHead className="w-[200px]">Target Entity</TableHead>
                      <TableHead>Provider / Model</TableHead>
                      <TableHead className="w-[90px] px-0 text-right">Time</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(() => {
                      const now = new Date();
                      const todayStr = now.toDateString();
                      const yesterdayDate = new Date();
                      yesterdayDate.setDate(now.getDate() - 1);
                      const yesterdayStr = yesterdayDate.toDateString();
                      return costLog.slice(0, 40).map((entry) => {
                        const totalTokens = entry.input_tokens + entry.output_tokens;
                        const cost = parseFloat(entry.cost_usd) || 0;
                        return (
                          <TableRow key={entry.id} className="group transition-colors">
                            <TableCell className="px-0 py-4">
                              <div className="flex flex-col">
                                <div className="flex items-baseline gap-1.5">
                                  <span className="text-foreground type-caption-mono font-medium tabular-nums">
                                    {totalTokens.toLocaleString()}
                                  </span>
                                  <span className="text-muted type-caption">tokens</span>
                                </div>
                                <span className="text-accent type-label-mono mt-1 font-medium">
                                  ${cost > 0 && cost < 0.0001 ? cost.toFixed(6) : cost.toFixed(4)}
                                </span>
                              </div>
                            </TableCell>

                            {/* Task type */}
                            <TableCell className="px-4 py-4">
                              <span className="type-control text-foreground !font-normal">
                                {entry.task_type.replace(/_/g, ' ')}
                              </span>
                            </TableCell>

                            {/* Domain / run target */}
                            <TableCell
                              className="px-4 py-4"
                              title={entry.domain || `Run #${entry.run_id}`}
                            >
                              <span className="text-foreground/80 block truncate">
                                {entry.domain || (entry.run_id ? `Run #${entry.run_id}` : 'system')}
                              </span>
                            </TableCell>

                            {/* Provider + model stacked */}
                            <TableCell className="px-4 py-4">
                              <div className="flex flex-col overflow-hidden">
                                <span className="type-control text-foreground truncate !font-normal">
                                  {entry.provider}
                                </span>
                                <span
                                  className="type-caption text-muted truncate"
                                  title={entry.model}
                                >
                                  {entry.model}
                                </span>
                              </div>
                            </TableCell>

                            <TableCell className="px-0 py-4 text-right">
                              <span className="type-caption-mono text-muted group-hover:text-foreground transition-colors">
                                {(() => {
                                  const d = new Date(entry.created_at);
                                  const dStr = d.toDateString();
                                  const isToday = dStr === todayStr;
                                  const isYesterday = dStr === yesterdayStr;

                                  const timeStr = d.toLocaleTimeString([], {
                                    hour: '2-digit',
                                    minute: '2-digit',
                                    hour12: false,
                                  });
                                  const dateStr = d.toLocaleDateString('en-US', {
                                    month: '2-digit',
                                    day: '2-digit',
                                  });

                                  if (isToday) return timeStr;
                                  if (isYesterday) return `Yesterday ${timeStr}`;
                                  return `${dateStr} ${timeStr}`;
                                })()}
                              </span>
                            </TableCell>
                          </TableRow>
                        );
                      });
                    })()}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <div className="p-12 text-center">
                <MutedPanelMessage
                  title="No cost events"
                  description="Detailed LLM usage and token metrics will appear here once active."
                />
              </div>
            )}
          </SectionCard>
        </div>
      </div>
    </div>
  );
}
