export type MonitorPriority = 'on_demand' | 'priority' | 'background';
export type MonitorStatus = 'active' | 'paused' | 'archived' | 'triggered' | 'error';
export type MonitorEventType = 'field_changed' | 'record_new' | 'record_removed';
export type NotificationStatus = 'pending' | 'sent' | 'skipped';

export interface AlertTargetRule {
  path: string;
  label?: string | null;
  operator?: string;
  value?: unknown;
  variant_match?: Record<string, unknown> | null;
}

export interface MonitorJob {
  id: number;
  name: string;
  urls: string[];
  domains: string[];
  surface: string;
  tracked_fields: string[];
  schedule_interval_hours: number;
  priority: MonitorPriority;
  retention_days: number;
  status: MonitorStatus;
  settings: Record<string, unknown>;
  target_rules?: AlertTargetRule[];
  condition?: string | null;
  webhook_url?: string | null;
  poll_interval_seconds?: number | null;
  last_known_values?: Record<string, unknown>;
  last_checked_at?: string | null;
  consecutive_failure_count?: number;
  last_error?: string | null;
  last_crawl_method?: string | null;
  last_run_at: string | null;
  next_run_at: string | null;
  created_at: string;
  updated_at: string;
  change_count?: number;
}

export interface MonitorEvent {
  id: number;
  monitor_id: number;
  run_id: number | null;
  source_url: string;
  event_type: MonitorEventType;
  field_name: string | null;
  old_value: unknown;
  new_value: unknown;
  detected_at: string;
  notified_at?: string | null;
  notification_status?: NotificationStatus;
  condition_met?: boolean;
}

export interface MonitorSnapshotRecord {
  id: number;
  snapshot_id: number;
  monitor_id: number;
  source_url: string;
  url_identity_key: string;
  field_values: Record<string, unknown>;
  created_at: string;
}

export interface MonitorSnapshot {
  id: number;
  monitor_id: number;
  run_id: number;
  snapshot_data?: Record<string, unknown>;
  record_count: number;
  change_count: number;
  created_at: string;
}

export interface MonitorCreatePayload {
  name: string;
  urls: string[];
  surface: string;
  tracked_fields: string[];
  schedule_interval_hours: number;
  priority: MonitorPriority;
  retention_days: number;
  requested_fields: string[];
  settings?: Record<string, unknown>;
}

export interface MonitorUpdatePayload {
  name?: string;
  tracked_fields?: string[];
  schedule_interval_hours?: number;
  priority?: MonitorPriority;
  retention_days?: number;
  status?: MonitorStatus;
  settings?: Record<string, unknown>;
  condition?: string | null;
  webhook_url?: string | null;
  poll_interval_seconds?: number | null;
}

export interface AlertCreatePayload {
  url: string;
  target_fields: string[];
  target_rules?: AlertTargetRule[];
  condition?: string | null;
  webhook_url?: string | null;
  poll_interval_seconds: number;
}

export interface AlertUpdatePayload {
  target_fields?: string[];
  target_rules?: AlertTargetRule[];
  condition?: string | null;
  webhook_url?: string | null;
  poll_interval_seconds?: number | null;
  status?: MonitorStatus;
}

export interface AlertJob {
  id: number;
  url: string;
  domain: string;
  surface: string;
  target_fields: string[];
  target_rules?: AlertTargetRule[];
  condition?: string | null;
  webhook_url?: string | null;
  poll_interval_seconds: number;
  status: MonitorStatus;
  last_checked_at: string | null;
  last_known_values: Record<string, unknown>;
  last_error?: string | null;
  last_crawl_method?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AlertTestResponse {
  alert: AlertJob;
  run_id: number;
  current_snapshot: Record<string, unknown>;
  delta_count: number;
}

export interface AlertHistoryItem {
  id: number;
  alert_id: number;
  source_url: string;
  event_type: MonitorEventType;
  field_name: string | null;
  previous_value: unknown;
  current_value: unknown;
  detected_at: string;
  condition_met: boolean;
}

export interface WebhookDelivery {
  id: number;
  monitor_id: number;
  event_id: number | null;
  status: string;
  attempt: number;
  response_code?: number | null;
  error_message?: string | null;
  payload_preview: Record<string, unknown>;
  delivered_at?: string | null;
  created_at: string;
}

export interface RunNowResponse {
  run_id: number;
  dispatched_at: string;
  url_count: number;
  run_ids?: number[];
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface InAppNotification {
  id: number;
  user_id: number | null;
  monitor_id: number;
  event_count: number;
  message: string;
  read: boolean;
  read_at: string | null;
  created_at: string;
}
