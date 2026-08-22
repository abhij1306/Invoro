'use client';

import { useMemo, useReducer } from 'react';

import type { MonitorJob, AlertCreatePayload, AlertUpdatePayload } from '../../lib/api/types';
import { Button, Dropdown, Field, Input } from '../ui/primitives';
import { InlineAlert } from '../ui/patterns';
import {
  failFormSubmit,
  settleFormSubmit,
  startFormSubmit,
  toggleSelectedValue,
} from './monitor-form-state';

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

type AlertFormState = {
  url: string;
  targetFields: string[];
  condition: string;
  pollInterval: string;
  webhookUrl: string;
  error: string;
  submitting: boolean;
};

type AlertFormAction =
  | { type: 'urlChanged'; value: string }
  | { type: 'fieldToggled'; field: string }
  | { type: 'conditionChanged'; value: string }
  | { type: 'pollIntervalChanged'; value: string }
  | { type: 'webhookUrlChanged'; value: string }
  | { type: 'submitStarted' }
  | { type: 'submitFailed'; message: string }
  | { type: 'submitSettled' }
  | { type: 'validationFailed'; message: string };

function alertFormReducer(state: AlertFormState, action: AlertFormAction): AlertFormState {
  switch (action.type) {
    case 'urlChanged':
      return { ...state, url: action.value };
    case 'fieldToggled':
      return {
        ...state,
        targetFields: toggleSelectedValue(state.targetFields, action.field),
      };
    case 'conditionChanged':
      return { ...state, condition: action.value };
    case 'pollIntervalChanged':
      return { ...state, pollInterval: action.value };
    case 'webhookUrlChanged':
      return { ...state, webhookUrl: action.value };
    case 'submitStarted':
      return startFormSubmit(state);
    case 'submitFailed':
    case 'validationFailed':
      return failFormSubmit(state, action.message);
    case 'submitSettled':
      return settleFormSubmit(state);
  }
}

function sameFieldSet(left: readonly string[], right: readonly string[]) {
  if (left.length !== right.length) {
    return false;
  }
  const rightSet = new Set(right);
  return left.every((value) => rightSet.has(value));
}

export function AlertForm({ initial, onSubmit, onCancel, submitLabel }: Readonly<AlertFormProps>) {
  const initialUrl = alertInitialUrl(initial);
  const initialFields = initialAlertFields(initial);
  const [state, dispatch] = useReducer(alertFormReducer, {
    url: initialUrl,
    targetFields: initialFields,
    condition: initial?.condition ?? '',
    pollInterval: String(initial?.poll_interval_seconds ?? 300),
    webhookUrl: initial?.webhook_url ?? '',
    error: '',
    submitting: false,
  });
  const { url, targetFields, condition, pollInterval, webhookUrl, error, submitting } = state;
  const editing = Boolean(initial?.id);

  const currentValues = useMemo(() => {
    const values = initial?.last_known_values ?? {};
    return targetFields.map((field) => `${field}: ${formatValue(values[field])}`).join(' · ');
  }, [initial?.last_known_values, targetFields]);

  function toggleField(field: string) {
    dispatch({ type: 'fieldToggled', field });
  }

  async function submit() {
    const cleanUrl = url.trim();
    const cleanWebhook = webhookUrl.trim();
    const validationError = validateAlertForm(editing, cleanUrl, targetFields, cleanWebhook);
    if (validationError) return dispatch({ type: 'validationFailed', message: validationError });
    dispatch({ type: 'submitStarted' });
    try {
      const payload = buildAlertPayload(
        initial,
        initialFields,
        targetFields,
        condition,
        cleanWebhook,
        pollInterval,
      );
      await onSubmit(editing ? payload : { ...payload, url: cleanUrl });
    } catch (submitError) {
      dispatch({
        type: 'submitFailed',
        message: submitError instanceof Error ? submitError.message : 'Unable to save alert.',
      });
    } finally {
      dispatch({ type: 'submitSettled' });
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
              onChange={(event) => dispatch({ type: 'urlChanged', value: event.target.value })}
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
          {editing && currentValues ? <p className="type-caption m-0">{currentValues}</p> : null}
        </div>
        <div className="space-y-4">
          <Field label="Condition" hint="Optional. Example: price < 150">
            <Input
              value={condition}
              onChange={(event) =>
                dispatch({ type: 'conditionChanged', value: event.target.value })
              }
              placeholder="e.g. price < 150"
            />
          </Field>
          <Field label="Poll Interval">
            <Dropdown
              value={pollInterval}
              onChange={(value) => dispatch({ type: 'pollIntervalChanged', value })}
              options={intervalOptions}
            />
          </Field>
          <Field label="Webhook URL" hint="Optional. Empty stores deltas only.">
            <Input
              value={webhookUrl}
              onChange={(event) =>
                dispatch({ type: 'webhookUrlChanged', value: event.target.value })
              }
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

function initialAlertFields(initial: Partial<MonitorJob> | undefined) {
  const tracked = initial?.tracked_fields ?? [];
  if (!tracked.length) return ['price', 'availability'];
  return tracked;
}

function alertInitialUrl(initial: Partial<MonitorJob> | undefined) {
  return initial?.urls?.[0] ?? '';
}

function validateAlertForm(editing: boolean, url: string, fields: string[], webhook: string) {
  if (!editing && !/^https?:\/\//i.test(url)) return 'URL must start with http:// or https://.';
  if (!fields.length) return 'Select at least one field.';
  if (webhook && !/^https?:\/\//i.test(webhook))
    return 'Webhook URL must start with http:// or https://.';
  return '';
}

function buildAlertPayload(
  initial: Partial<MonitorJob> | undefined,
  initialFields: string[],
  fields: string[],
  condition: string,
  webhook: string,
  interval: string,
) {
  const tracked = Array.isArray(initial?.tracked_fields) ? initial.tracked_fields : initialFields;
  return {
    target_fields: fields,
    target_rules:
      sameFieldSet(fields, tracked) && initial?.target_rules?.length
        ? initial.target_rules
        : undefined,
    condition: condition.trim() || null,
    webhook_url: webhook || null,
    poll_interval_seconds: Number.parseInt(interval, 10),
  };
}

function formatValue(value: unknown) {
  if (value === null || value === undefined || value === '') return 'empty';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}
