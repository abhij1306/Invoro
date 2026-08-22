import type {
  CrawlDomain,
  CrawlLog,
  CrawlRecord,
  CrawlRun,
  CrawlSurface,
} from '../../lib/api/types';
import { CRAWL_DEFAULTS } from '../../lib/constants/crawl-defaults';
import { SURFACE_DISPATCH } from './domain-surface-config';

export {
  cleanRequestedField,
  uniqueFields,
  uniqueNumbers,
  uniqueRequestedFields,
  uniqueStrings,
  validateAdditionalFieldName,
} from '../../lib/crawl/fields';
export {
  clampNumber,
  decodeUrlForDisplay,
  decodeUrlsForDisplay,
  extractionVerdict,
  extractionVerdictTone,
  formatCellDisplay,
  formatDuration,
  formatDurationMs,
  humanizeFieldName,
  humanizeVerdict,
  isEmptyCandidateValue,
  normalizeField,
  parseLines,
  presentCandidateValue,
  progressPercent,
  stringifyCell,
} from '../../lib/crawl/format';
export { scrollViewportToBottom } from '../../lib/crawl/scroll';
export {
  cleanRecord,
  cleanRecordForDisplay,
  copyJson,
  extractRecordUrl,
  readRecordValue,
} from '../../lib/crawl/record-utils';
export {
  estimateDataQuality,
  humanizeQuality,
  qualityLevelFromScore,
  qualityTone,
  scoreFieldQuality,
  scoreRecordQuality,
} from '../../lib/crawl/quality';
export type { QualityLevel, QualitySnapshot } from '../../lib/crawl/quality';
export { buildLogSiteGroups, getLogStage } from './log-terminal-utils';
export type { FieldRow, FieldRowMessageTone, ValidationState } from './form-fields';

export type CrawlTab = 'category' | 'pdp';
export type CategoryMode = 'single' | 'sitemap' | 'bulk';
export type PdpMode = 'single' | 'batch' | 'csv';
export type PendingDispatch = {
  runType: 'crawl' | 'batch' | 'csv';
  surface: CrawlSurface;
  url?: string;
  urls?: string[];
  settings: Record<string, unknown>;
  additionalFields: string[];
  csvFile: File | null;
};
export type OutputTabKey = 'markdown' | 'table' | 'json' | 'logs' | 'learning' | 'run_config';

export function selectorWinnerLabel(selectorKind: string | null | undefined): string {
  const normalized = String(selectorKind || '')
    .trim()
    .toLowerCase();
  if (!normalized) return 'Selector winner';
  if (normalized === 'xpath') return 'XPath winner';
  if (normalized === 'css_selector') return 'CSS selector winner';
  return `${selectorKind} winner`;
}

export function mergeRecords(current: CrawlRecord[], incoming: CrawlRecord[]) {
  const byId = new Map<number, CrawlRecord>();
  for (const row of current) byId.set(row.id, row);
  for (const row of incoming) byId.set(row.id, row);
  return Array.from(byId.values()).sort((a, b) => a.id - b.id);
}

export function mergeLogs(current: CrawlLog[], incoming: CrawlLog[]) {
  const byId = new Map<number, CrawlLog>();
  for (const row of current) byId.set(row.id, row);
  for (const row of incoming) byId.set(row.id, row);
  return Array.from(byId.values())
    .sort((a, b) => a.id - b.id)
    .slice(-CRAWL_DEFAULTS.MAX_LIVE_LOGS);
}

export function parseRequestedCrawlTab(value: string | null): CrawlTab | null {
  return value === 'category' || value === 'pdp' ? value : null;
}

export function parseRequestedCategoryMode(value: string | null): CategoryMode | null {
  return value === 'single' || value === 'sitemap' || value === 'bulk' ? value : null;
}

export function parseRequestedPdpMode(value: string | null): PdpMode | null {
  return value === 'single' || value === 'batch' || value === 'csv' ? value : null;
}

export function deriveSurface(domain: CrawlDomain, module: CrawlTab): CrawlSurface {
  if (domain === 'auto') return 'auto';
  if (domain === 'forum_thread') return 'forum_detail';
  return SURFACE_DISPATCH[`${domain}:${module}`];
}

export function inferDomainFromSurface(surface: string | null | undefined): CrawlDomain | null {
  const normalized = String(surface || '').toLowerCase();
  if (normalized === 'auto') return 'auto';
  if (normalized.startsWith('job_')) return 'jobs';
  if (normalized.startsWith('ecommerce_')) return 'commerce';
  if (normalized.startsWith('automobile_')) return 'automobiles';
  if (normalized.startsWith('article_')) return 'article';
  if (normalized.startsWith('content_')) return 'content';
  if (normalized === 'forum_detail') return 'forum_thread';
  return null;
}

function inferRunModule(run?: CrawlRun): CrawlTab | null {
  if (!run) return null;
  const settings = run.settings && typeof run.settings === 'object' ? run.settings : {};
  const configuredModule = typeof settings.crawl_module === 'string' ? settings.crawl_module : '';
  if (configuredModule === 'category' || configuredModule === 'pdp') return configuredModule;
  const configuredMode = typeof settings.crawl_mode === 'string' ? settings.crawl_mode : '';
  if (configuredMode === 'bulk' || configuredMode === 'sitemap') return 'category';
  if (configuredMode === 'batch' || configuredMode === 'csv') return 'pdp';
  const surface = String(run.surface || '').toLowerCase();
  if (surface.includes('listing')) return 'category';
  if (surface.includes('detail')) return 'pdp';
  return null;
}

export function isListingRun(run?: CrawlRun) {
  return inferRunModule(run) === 'category';
}
