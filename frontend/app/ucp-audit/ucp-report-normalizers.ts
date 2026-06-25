import type { UcpAuditReport } from '../../lib/api/types';
import { isRecord } from '../../lib/utils/type-guards';

export type FindingCopy = Record<
  string,
  {
    description: string;
    fix: string;
    effort: string;
    action: string;
    impact: 'critical' | 'high' | 'medium';
  }
>;

export type NormalizedFinding = {
  id: string;
  code: string;
  dimension: string;
  severity: string;
  description: string;
  fix: string;
  effort: string;
  action: string;
  impact: 'critical' | 'high' | 'medium';
  evidence: Array<Record<string, unknown>>;
};

export type ContractTransport = {
  service?: string;
  transport?: string;
  endpoint?: string;
  reachable?: boolean;
  negotiated?: boolean;
  profile_required?: boolean;
  status_code?: number;
  error?: string;
  tool_names?: string[];
};

export type UcpContract = {
  catalog?: {
    domain?: string;
    pages_crawled?: number;
    sampled_urls?: string[];
    crawl_errors?: string[];
  };
  structured_markup?: {
    product_jsonld_count?: number;
    jsonld_block_count?: number;
    jsonld_parse_errors?: string[];
    open_graph?: Record<string, string>;
  };
  product_records?: Array<Record<string, unknown>>;
  discovery?: {
    robots_directives?: Record<string, string[]>;
    sitemap_found?: boolean;
  };
  ai_assessment?: {
    enabled?: boolean;
    results?: Array<{
      url?: string;
      findings?: Array<Record<string, unknown>>;
      simulated_queries?: Array<{ query?: string; answerable?: boolean; gap?: string }>;
      llm_provider?: string;
      llm_model?: string;
      error?: string;
    }>;
    contradictions?: Array<{ url?: string; flags?: Array<Record<string, unknown>> }>;
  };
  manifest?: Record<string, unknown>;
  services?: string[];
  capabilities?: string[];
  missing_required_services?: string[];
  missing_required_capabilities?: string[];
  transports?: ContractTransport[];
  schemas?: Array<Record<string, unknown>>;
  payment_handlers?: string[];
};

export type UcpRoadmapItem = {
  id: string;
  subSkill: string;
  priority: string;
  action: string;
  source: string;
  evidence: Array<Record<string, unknown>>;
  effort: string;
  dependsOn: string[];
};

export function formatUnknownText(value: unknown, fallback = ''): string {
  if (value == null || value === '') return fallback;
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean' || typeof value === 'bigint') {
    return String(value);
  }
  if (Array.isArray(value)) {
    const items = value.flatMap((item) => {
      const text = formatUnknownText(item);
      return text ? [text] : [];
    });
    return items.length ? items.join(', ') : fallback;
  }
  try {
    return JSON.stringify(value) ?? fallback;
  } catch {
    return fallback;
  }
}

export function normalizeEvidence(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter(isRecord) : [];
}

export function evidenceToLines(evidence: unknown): string[] {
  return normalizeEvidence(evidence)
    .flatMap((entry) =>
      Object.entries(entry).flatMap(([key, value]) => {
        if (Array.isArray(value)) {
          return value.map((item) => `${key}: ${formatUnknownText(item, '-')}`);
        }
        const rendered = isRecord(value) ? JSON.stringify(value) : formatUnknownText(value, '-');
        return [`${key}: ${rendered}`];
      }),
    )
    .slice(0, 12);
}

export function normalizeFinding(
  finding: Record<string, unknown>,
  index: number,
  findingCopy: FindingCopy,
): NormalizedFinding {
  const code = formatUnknownText(finding.code, 'unknown_finding');
  const dimension = formatUnknownText(finding.dimension_id ?? finding.dimension);
  const copy = findingCopy[code] ?? {
    description: formatUnknownText(finding.message, code),
    fix: 'Inspect the exported signal payload and repair the missing catalog signal.',
    effort: 'review',
    action: `Resolve ${code}`,
    impact: 'medium' as const,
  };
  return {
    id: `${dimension}-${code}-${index}`,
    code,
    dimension,
    severity: formatUnknownText(finding.severity, 'info'),
    description: formatUnknownText(finding.message, copy.description),
    fix: copy.fix,
    effort: copy.effort,
    action: copy.action,
    impact: copy.impact,
    evidence: normalizeEvidence(finding.evidence),
  };
}

export function normalizeFindings(
  report: UcpAuditReport | null,
  findingCopy: FindingCopy,
): NormalizedFinding[] {
  return (report?.findings ?? [])
    .filter(isRecord)
    .map((finding, index) => normalizeFinding(finding, index, findingCopy));
}

export function getContract(report: UcpAuditReport | null): UcpContract {
  const raw = report?.report_json?.ucp_contract;
  return isRecord(raw) ? (raw as UcpContract) : {};
}

export function getRoadmap(
  report: UcpAuditReport | null,
  findingCopy: FindingCopy,
): UcpRoadmapItem[] {
  const raw = report?.report_json?.repair_roadmap;
  if (Array.isArray(raw) && raw.length) {
    return raw.filter(isRecord).map((roadmap, index) => {
      const subSkill = formatUnknownText(roadmap.sub_skill, 'aid');
      return {
        id: `${subSkill}-${index}`,
        subSkill,
        priority: formatUnknownText(roadmap.priority, 'medium'),
        action: formatUnknownText(roadmap.action, 'Repair AI discoverability signal'),
        source: formatUnknownText(roadmap.source, 'AI Discoverability Score guidance'),
        evidence: normalizeEvidence(roadmap.evidence),
        effort: formatUnknownText(roadmap.effort, 'review'),
        dependsOn: Array.isArray(roadmap.depends_on)
          ? roadmap.depends_on.map((value) => formatUnknownText(value)).filter(Boolean)
          : [],
      };
    });
  }
  return (report?.findings ?? []).filter(isRecord).map((finding, index) => {
    const normalized = normalizeFinding(finding, index, findingCopy);
    return {
      id: normalized.id,
      subSkill: normalized.dimension,
      priority: normalized.impact,
      action: normalized.action,
      source: 'AI Discoverability Score guidance',
      evidence: normalized.evidence,
      effort: normalized.effort,
      dependsOn: [],
    };
  });
}
