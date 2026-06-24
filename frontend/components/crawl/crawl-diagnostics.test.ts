import { describe, expect, it } from 'vitest';

import type { CrawlRecord } from '../../lib/api/types';
import {
  acquisitionDiagnosticsSummary,
  llmFieldSourceSummary,
  recordConfidenceSummary,
} from './crawl-diagnostics';

function record(overrides: Partial<CrawlRecord> = {}): CrawlRecord {
  return {
    id: 1,
    run_id: 2,
    source_url: 'https://example.com/original',
    data: {},
    raw_data: {},
    discovered_data: {},
    source_trace: {},
    raw_html_path: null,
    created_at: '2026-06-24T00:00:00Z',
    ...overrides,
  };
}

describe('crawl diagnostics normalization', () => {
  it('normalizes complete acquisition, phase timing, confidence, and LLM diagnostics', () => {
    const value = record({
      raw_data: {
        _source: 'llm_repair',
        _field_sources: {
          title: ['json_ld', 'llm_gap_fill'],
          price: ['dom'],
        },
        _confidence: { score: 0.82, level: 'HIGH' },
      },
      source_trace: {
        acquisition: {
          final_url: ' https://example.com/final ',
          browser_diagnostics: {
            phase_timings_ms: { navigation: 120, render: 30, total: 150 },
          },
        },
      },
    });

    expect(acquisitionDiagnosticsSummary(value)).toEqual({
      finalUrl: 'https://example.com/final',
      phaseTimingsMs: { navigation: 120, render: 30, total: 150 },
      durationMs: 150,
    });
    expect(llmFieldSourceSummary(value)).toEqual({
      recordTouched: true,
      touchedFieldNames: ['_record', 'title'],
    });
    expect(recordConfidenceSummary(value)).toEqual({ score: 0.82, level: 'high' });
  });

  it('returns empty summaries for partial diagnostics', () => {
    const value = record({ source_trace: { acquisition: { final_url: '  ' } } });

    expect(acquisitionDiagnosticsSummary(value)).toEqual({
      finalUrl: null,
      phaseTimingsMs: {},
      durationMs: null,
    });
    expect(llmFieldSourceSummary(value)).toEqual({
      recordTouched: false,
      touchedFieldNames: [],
    });
    expect(recordConfidenceSummary(value)).toBeNull();
  });

  it('tolerates nulls and arrays in unexpected positions', () => {
    const value = record({
      raw_data: { _field_sources: [], _confidence: [] },
      discovered_data: { confidence: null },
      source_trace: { acquisition: [] },
    });

    expect(acquisitionDiagnosticsSummary(value)).toEqual({
      finalUrl: null,
      phaseTimingsMs: {},
      durationMs: null,
    });
    expect(llmFieldSourceSummary(value).touchedFieldNames).toEqual([]);
    expect(recordConfidenceSummary(value)).toBeNull();
  });

  it('accepts numeric strings where existing renderers accept numbers', () => {
    const value = record({
      raw_data: { _confidence: { score: '0.6' } },
      source_trace: {
        acquisition: {
          browser_diagnostics: {
            phase_timings_ms: { navigation: '125', total: '250' },
          },
        },
      },
    });

    expect(acquisitionDiagnosticsSummary(value).phaseTimingsMs).toEqual({
      navigation: 125,
      total: 250,
    });
    expect(acquisitionDiagnosticsSummary(value).durationMs).toBe(250);
    expect(recordConfidenceSummary(value)).toEqual({ score: 0.6, level: 'medium' });
  });

  it('ignores unknown additional keys while preserving open diagnostic objects', () => {
    const value = record({
      raw_data: {
        _field_sources: {
          title: ['dom'],
          unknown_field: { nested: true },
        },
      },
      source_trace: {
        acquisition: {
          future_key: { anything: true },
          browser_diagnostics: {
            phase_timings_ms: { total: 75, invalid: 'later', nested: { value: 4 } },
          },
        },
        future_trace: ['open', 'data'],
      },
    });

    expect(acquisitionDiagnosticsSummary(value)).toEqual({
      finalUrl: null,
      phaseTimingsMs: { total: 75 },
      durationMs: 75,
    });
    expect(llmFieldSourceSummary(value).touchedFieldNames).toEqual([]);
  });

  it('treats missing _field_sources as no LLM-touched fields', () => {
    const value = record({ raw_data: { _source: 'json_ld' } });

    expect(llmFieldSourceSummary(value)).toEqual({
      recordTouched: false,
      touchedFieldNames: [],
    });
  });
});
