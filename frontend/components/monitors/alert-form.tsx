'use client';

import { useMemo, useState } from 'react';

import type { MonitorJob, AlertCreatePayload, AlertUpdatePayload } from '../../lib/api/types';
import { Button, Dropdown, Field, Input } from '../ui/primitives';
import { InlineAlert } from '../ui/patterns';

interface AlertFormProps {
  initial?: Partial<MonitorJob>;
  onSubmit: (payload: AlertCreatePayload | AlertUpdatePayload) => Promise<void>;
  onCancel: () => void;
  submitLabel: string;
}

const fieldOptions = ['price', 'availability', 'sku', 'title', 'brand', 'variants'];
const intervalOptions = [
  { value: '60', label: '1 min' },
  { value: '300', label: '5 min' },
  { value: '900', label: '15 min' },
  { value: '1800', label: '30 min' },
  { value: '3600', label: '1 hour' },
];

export function AlertForm({ initial, onSubmit, onCancel, submitLabel }: Readonly<AlertFormProps>) {
  const initialUrl = initial?.urls?.[0] ?? '';
  const initialFields = (() => {
    const initialTrackedFields = initial?.tracked_fields ?? [];
    if (!initialTrackedFields.length) {
      return ['price', 'availability'];
    }
    const filteredFields = initialTrackedFields.filter((field) => fieldOptions.includes(field));
    const droppedFields = initialTrackedFields.filter((field) => !fieldOptions.includes(field));
    if (process.env.NODE_ENV === 'development' && droppedFields.length) {
      console.warn(
        `alert-form initial.tracked_fields contained unsupported fields: ${droppedFields.join(', ')}`,
      );
    }
    return filteredFields;
  })();
  const [url, setUrl] = useState(initialUrl);
  const [targetFields, setTargetFields] = useState<string[]>(initialFields);
  const [condition, setCondition] = useState(initial?.condition ?? '');
  const [pollInterval, setPollInterval] = useState(String(initial?.poll_interval_seconds ?? 300));
  const [webhookUrl, setWebhookUrl] = useState(initial?.webhook_url ?? '');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const editing = Boolean(initial?.id);

  const currentValues = useMemo(() => {
    const values = initial?.last_known_values ?? {};
    return targetFields.map((field) => `${field}: ${formatValue(values[field])}`).join(' · ');
  }, [initial?.last_known_values, targetFields]);

  function toggleField(field: string) {
    setTargetFields((current) =>
      current.includes(field) ? current.filter((item) => item !== field) : [...current, field],
    );
  }

  async function submit() {
    setError('');
    const cleanUrl = url.trim();
    const cleanWebhook = webhookUrl.trim();
    if (!editing && !/^https?:\/\//i.test(cleanUrl)) {
      setError('URL must start with http:// or https://.');
      return;
    }
    if (!targetFields.length) {
      setError('Select at least one field.');
      return;
    }
    if (cleanWebhook && !/^https?:\/\//i.test(cleanWebhook)) {
      setError('Webhook URL must start with http:// or https://.');
      return;
    }
    setSubmitting(true);
    try {
      const fieldsChanged =
        JSON.stringify(targetFields) !== JSON.stringify(initial?.tracked_fields ?? initialFields);
      const payload = {
        target_fields: targetFields,
        target_rules: !fieldsChanged && initial?.target_rules?.length ? initial.target_rules : undefined,
        condition: condition.trim() || null,
        webhook_url: cleanWebhook || null,
        poll_interval_seconds: Number.parseInt(pollInterval, 10),
      };
      await onSubmit(editing ? payload : { ...payload, url: cleanUrl });
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Unable to save alert.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-4">
      {error ? <InlineAlert message={error} /> : null}
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-4">
          <Field label="URL">
            <Input
              value={url}
              disabled={editing}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://example.com/product"
            />
          </Field>
          <div className="space-y-1.5">
            <div className="field-label">Alert Fields</div>
            <div className="flex flex-wrap gap-2">
              {fieldOptions.map((field) => (
                <label key={field} className="type-body-sm flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={targetFields.includes(field)}
                    onChange={() => toggleField(field)}
                  />
                  {field}
                </label>
              ))}
            </div>
          </div>
          {editing && currentValues ? (
            <p className="text-muted type-caption m-0">{currentValues}</p>
          ) : null}
        </div>
        <div className="space-y-4">
          <Field label="Condition" hint="Optional. Example: price < 150">
            <Input
              value={condition}
              onChange={(event) => setCondition(event.target.value)}
              placeholder="e.g. price < 150"
            />
          </Field>
          <Field label="Poll Interval">
            <Dropdown value={pollInterval} onChange={setPollInterval} options={intervalOptions} />
          </Field>
          <Field label="Webhook URL" hint="Optional. Empty stores deltas only.">
            <Input
              value={webhookUrl}
              onChange={(event) => setWebhookUrl(event.target.value)}
              placeholder="https://agent.example/webhook"
            />
          </Field>
        </div>
      </div>
      <div className="border-border flex justify-end gap-2 border-t pt-4">
        <Button type="button" variant="quiet" onClick={onCancel} disabled={submitting}>
          Cancel
        </Button>
        <Button type="button" onClick={() => void submit()} disabled={submitting}>
          {submitting ? 'Saving...' : submitLabel}
        </Button>
      </div>
    </div>
  );
}

function formatValue(value: unknown) {
  if (value === null || value === undefined || value === '') return 'empty';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}
