import type { AlertJob, MonitorJob } from '../../lib/api/types';

export type { AlertJob, MonitorJob } from '../../lib/api/types';

export function alertToMonitor(alert: AlertJob): MonitorJob {
  return {
    id: alert.id,
    name: alert.url,
    urls: [alert.url],
    domains: [alert.domain],
    surface: alert.surface,
    tracked_fields: alert.target_fields,
    // These monitor-only fields are placeholders for shared monitor UI.
    // Actual alert timing uses poll_interval_seconds.
    schedule_interval_hours: 1,
    priority: 'background',
    retention_days: 90,
    status: alert.status,
    settings: {},
    target_rules: alert.target_rules,
    condition: alert.condition,
    webhook_url: alert.webhook_url,
    poll_interval_seconds: alert.poll_interval_seconds,
    last_known_values: alert.last_known_values,
    last_checked_at: alert.last_checked_at,
    last_error: alert.last_error,
    last_crawl_method: alert.last_crawl_method,
    last_run_at: null,
    next_run_at: null,
    created_at: alert.created_at,
    updated_at: alert.updated_at,
    change_count: 0,
  };
}
