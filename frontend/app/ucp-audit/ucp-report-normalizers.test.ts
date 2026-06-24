import { describe, expect, it } from 'vitest';

import type { UcpAuditReport } from '../../lib/api/types';
import {
  evidenceToLines,
  getContract,
  getRoadmap,
  normalizeFindings,
  type FindingCopy,
} from './ucp-report-normalizers';

const findingCopy: FindingCopy = {
  KNOWN: {
    description: 'Known description',
    fix: 'Known fix',
    effort: '1 hour',
    action: 'Known action',
    impact: 'high',
  },
};

function report(overrides: Record<string, unknown> = {}): UcpAuditReport {
  return {
    id: 1,
    job_id: 2,
    overall_score: 50,
    dimension_scores: [],
    findings: [],
    report_json: {},
    markdown_report: '',
    created_at: '2026-06-01T00:00:00Z',
    updated_at: '2026-06-01T00:00:00Z',
    ...overrides,
  } as UcpAuditReport;
}

describe('UCP report normalizers', () => {
  it('handles a missing report', () => {
    expect(normalizeFindings(null, findingCopy)).toEqual([]);
    expect(getContract(null)).toEqual({});
    expect(getRoadmap(null, findingCopy)).toEqual([]);
  });

  it('normalizes partial reports and falls back from findings to roadmap items', () => {
    const partial = report({
      findings: [{ code: 'KNOWN', dimension_id: 'D-AID1' }],
      report_json: { ucp_contract: { catalog: { pages_crawled: 1 } } },
    });

    expect(normalizeFindings(partial, findingCopy)[0]).toMatchObject({
      code: 'KNOWN',
      dimension: 'D-AID1',
      action: 'Known action',
      evidence: [],
    });
    expect(getContract(partial).catalog?.pages_crawled).toBe(1);
    expect(getRoadmap(partial, findingCopy)[0]).toMatchObject({
      subSkill: 'D-AID1',
      action: 'Known action',
      effort: '1 hour',
    });
  });

  it('ignores malformed findings, evidence and roadmap entries', () => {
    const malformed = report({
      findings: [null, 'bad', { code: 'UNKNOWN', evidence: [null, 'bad', { url: 'ok' }] }],
      report_json: {
        ucp_contract: ['bad'],
        repair_roadmap: [
          null,
          'bad',
          { sub_skill: 'catalog', evidence: ['bad'], depends_on: 'bad' },
        ],
      },
    });

    expect(normalizeFindings(malformed, findingCopy)).toHaveLength(1);
    expect(normalizeFindings(malformed, findingCopy)[0].evidence).toEqual([{ url: 'ok' }]);
    expect(getContract(malformed)).toEqual({});
    expect(getRoadmap(malformed, findingCopy)).toEqual([
      expect.objectContaining({ subSkill: 'catalog', evidence: [], dependsOn: [] }),
    ]);
    expect(evidenceToLines([null, 'bad', { nested: { valid: true } }])).toEqual([
      'nested: {"valid":true}',
    ]);
  });
});
