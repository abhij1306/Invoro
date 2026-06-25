import type { CrawlRecord } from '../../lib/api/types';
import { qualityLevelFromScore } from '../../lib/crawl/quality';
import {
  nonEmptyStringOrNull,
  nonNegativeNumberOrNull,
  objectOrNull,
  stringList,
} from '../../lib/utils/type-guards';

export type AcquisitionDiagnosticsSummary = {
  finalUrl: string | null;
  phaseTimingsMs: Record<string, number>;
  durationMs: number | null;
};

export type LlmFieldSourceSummary = {
  recordTouched: boolean;
  touchedFieldNames: string[];
};

export type RecordConfidenceSummary = {
  score: number;
  level: string;
};

export function normalizePhaseTimingMap(value: unknown): Record<string, number> {
  const payload = objectOrNull(value);
  if (!payload) return {};

  const normalized: Record<string, number> = {};
  for (const [key, rawValue] of Object.entries(payload)) {
    const timing = nonNegativeNumberOrNull(rawValue);
    if (timing !== null) normalized[key] = timing;
  }
  return normalized;
}

export function acquisitionDiagnosticsSummary(
  record: Pick<CrawlRecord, 'source_trace'>,
): AcquisitionDiagnosticsSummary {
  const sourceTrace = objectOrNull(record.source_trace);
  const acquisition = objectOrNull(sourceTrace?.acquisition);
  const browserDiagnostics = objectOrNull(acquisition?.browser_diagnostics);
  const phaseTimingsMs = normalizePhaseTimingMap(browserDiagnostics?.phase_timings_ms);

  return {
    finalUrl: nonEmptyStringOrNull(acquisition?.final_url),
    phaseTimingsMs,
    durationMs: phaseTimingsMs.total ?? null,
  };
}

export function llmFieldSourceSummary(
  record: Pick<CrawlRecord, 'raw_data'>,
): LlmFieldSourceSummary {
  const rawData = objectOrNull(record.raw_data);
  const source = nonEmptyStringOrNull(rawData?._source);
  const recordTouched = Boolean(source?.startsWith('llm_'));
  const touched = new Set<string>();
  if (recordTouched) touched.add('_record');

  const fieldSources = objectOrNull(rawData?._field_sources);
  if (fieldSources) {
    for (const [fieldName, value] of Object.entries(fieldSources)) {
      if (stringList(value).some((item) => item.startsWith('llm_'))) {
        touched.add(fieldName);
      }
    }
  }

  return {
    recordTouched,
    touchedFieldNames: Array.from(touched),
  };
}

export function recordConfidenceSummary(
  record: Pick<CrawlRecord, 'raw_data' | 'discovered_data'>,
): RecordConfidenceSummary | null {
  const rawData = objectOrNull(record.raw_data);
  const discoveredData = objectOrNull(record.discovered_data);
  const payload = objectOrNull(rawData?._confidence) ?? objectOrNull(discoveredData?.confidence);
  if (!payload) return null;

  const score = nonNegativeNumberOrNull(payload.score);
  if (score === null) return null;

  const explicitLevel = nonEmptyStringOrNull(payload.level);
  return {
    score,
    level: (explicitLevel ?? String(qualityLevelFromScore(score))).toLowerCase(),
  };
}
