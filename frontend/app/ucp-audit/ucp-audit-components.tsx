'use client';

import { useMemo, useState } from 'react';
import { AlertTriangle, Check, CheckSquare, Download, ShieldAlert, Sparkles } from 'lucide-react';

import { DataRegionEmpty, DataRegionLoading, TableSurface } from '../../components/ui/patterns';
import { Badge, Button, Card } from '../../components/ui/primitives';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../../components/ui/table';
import { cn } from '../../lib/utils';
import type { UcpAuditJob, UcpAuditReport } from '../../lib/api/types';

const DIMENSION_META: Record<string, { label: string; subtitle: string; desc: string }> = {
  'D-UCP1': {
    label: 'Discovery Profile',
    subtitle: '/.well-known/ucp',
    desc: 'Checks whether the store publishes a valid UCP discovery profile.',
  },
  'D-UCP2': {
    label: 'Services & Capabilities',
    subtitle: 'Declared contract map',
    desc: 'Checks dev.ucp.shopping plus catalog, cart, checkout, order, fulfillment, and discount capabilities.',
  },
  'D-UCP3': {
    label: 'Transport Negotiation',
    subtitle: 'REST / MCP / embedded',
    desc: 'Probes declared transports and treats profile-required MCP responses as partial negotiation.',
  },
  'D-UCP4': {
    label: 'Catalog Contract',
    subtitle: 'Search and lookup payloads',
    desc: 'Validates catalog search and lookup declarations and schema availability.',
  },
  'D-UCP5': {
    label: 'Cart & Checkout Contract',
    subtitle: 'Cart and checkout shapes',
    desc: 'Validates cart and checkout payload contracts without executing state-changing flows.',
  },
  'D-UCP6': {
    label: 'Order & Policy Contract',
    subtitle: 'Order, fulfillment, payment',
    desc: 'Validates order, fulfillment, discount, and payment-handler coverage.',
  },
};

const FINDING_COPY: Record<
  string,
  {
    description: string;
    fix: string;
    effort: string;
    action: string;
    impact: 'critical' | 'high' | 'medium';
  }
> = {
  manifest_missing: {
    description: 'No UCP discovery profile was found at /.well-known/ucp.',
    fix: 'Publish a valid UCP discovery profile at /.well-known/ucp.',
    effort: '1 hour',
    action: 'Publish discovery profile',
    impact: 'critical',
  },
  manifest_invalid: {
    description: 'The UCP discovery profile has structural errors.',
    fix: 'Fix missing UCP objects, version fields, or malformed service declarations.',
    effort: '2 hours',
    action: 'Fix discovery profile',
    impact: 'critical',
  },
  manifest_redirected: {
    description: 'The UCP profile did not resolve at the canonical well-known path.',
    fix: 'Serve /.well-known/ucp directly without redirect hops.',
    effort: '1 hour',
    action: 'Remove discovery redirect',
    impact: 'medium',
  },
  signing_keys_missing: {
    description: 'The UCP profile is missing usable top-level signing keys.',
    fix: "Add a top-level signing_keys array with at least one public JWK using use='sig'.",
    effort: '2-4 hours',
    action: 'Add signing keys',
    impact: 'medium',
  },
  cache_control_missing: {
    description: 'The discovery profile response is missing required cache headers.',
    fix: 'Serve Cache-Control: public, max-age=300 or another public max-age of at least 60 seconds.',
    effort: '1 hour',
    action: 'Add cache headers',
    impact: 'medium',
  },
  service_missing: {
    description: 'Required UCP shopping service is not declared.',
    fix: 'Add dev.ucp.shopping to the UCP services map.',
    effort: '1 hour',
    action: 'Declare shopping service',
    impact: 'critical',
  },
  service_invalid: {
    description: 'One or more UCP service entries are malformed.',
    fix: 'Add required service version, transport, endpoint, schema, and spec fields.',
    effort: '2 hours',
    action: 'Fix service entries',
    impact: 'high',
  },
  capability_missing: {
    description: 'Required UCP shopping capabilities are missing.',
    fix: 'Declare catalog, cart, checkout, order, fulfillment, and discount capabilities.',
    effort: '2-4 hours',
    action: 'Declare missing capabilities',
    impact: 'high',
  },
  capability_invalid: {
    description: 'One or more UCP capability entries are malformed.',
    fix: 'Add required capability version, schema, and spec fields.',
    effort: '2 hours',
    action: 'Fix capability entries',
    impact: 'high',
  },
  capability_version_mismatch: {
    description: 'Capability versions do not match the shopping service version.',
    fix: 'Align capability versions with dev.ucp.shopping so capability intersection succeeds.',
    effort: '2 hours',
    action: 'Align capability versions',
    impact: 'medium',
  },
  transport_missing: {
    description: 'No REST, MCP, or embedded UCP transport was declared.',
    fix: 'Expose at least one supported UCP transport endpoint or embedded contract.',
    effort: '1 sprint',
    action: 'Expose transport',
    impact: 'critical',
  },
  transport_unreachable: {
    description: 'No declared UCP transport is reachable.',
    fix: 'Make at least one REST, MCP, A2A, or embedded transport reachable from the public web.',
    effort: '1 sprint',
    action: 'Fix transport reachability',
    impact: 'critical',
  },
  transport_negotiation_incomplete: {
    description: 'A transport is reachable but did not complete full negotiation.',
    fix: 'Complete MCP/REST negotiation or publish the required agent profile contract.',
    effort: '1 sprint',
    action: 'Complete transport negotiation',
    impact: 'high',
  },
  schema_missing: {
    description: 'Declared UCP payload schemas are incomplete.',
    fix: 'Attach schema URLs for all shopping payload contracts.',
    effort: '2 hours',
    action: 'Add schema declarations',
    impact: 'high',
  },
  schema_unreachable: {
    description: 'One or more declared UCP schemas could not be fetched as JSON.',
    fix: 'Make declared schema URLs public and JSON-readable.',
    effort: '2 hours',
    action: 'Fix schema URLs',
    impact: 'high',
  },
  schema_field_missing: {
    description: 'Declared schemas are missing required UCP payload fields.',
    fix: 'Add the missing fields to the relevant JSON Schema or OpenAPI component.',
    effort: '1 sprint',
    action: 'Add schema fields',
    impact: 'high',
  },
  catalog_contract_missing: {
    description: 'Catalog search or lookup payload contracts are incomplete.',
    fix: 'Expose catalog search and lookup schemas or MCP tools.',
    effort: '1 sprint',
    action: 'Repair catalog contract',
    impact: 'high',
  },
  cart_checkout_contract_missing: {
    description: 'Cart or checkout payload contracts are incomplete.',
    fix: 'Expose cart and checkout schemas or tools without relying on storefront UI.',
    effort: '1 sprint',
    action: 'Repair cart and checkout contract',
    impact: 'high',
  },
  order_policy_contract_missing: {
    description: 'Order, fulfillment, discount, or policy payload contracts are incomplete.',
    fix: 'Expose order, fulfillment, discount, return, and policy payload schemas.',
    effort: '1 sprint',
    action: 'Repair order and policy contract',
    impact: 'medium',
  },
  payment_handler_missing: {
    description: 'No UCP payment handler was declared.',
    fix: 'Declare a UCP payment handler such as Google Pay or Shopify card handling.',
    effort: '2-4 hours',
    action: 'Declare payment handler',
    impact: 'medium',
  },
};

type NormalizedFinding = {
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

type ContractTransport = {
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

type UcpContract = {
  manifest?: {
    found?: boolean;
    valid?: boolean;
    errors?: string[];
    supported_versions?: string[];
    target_version?: string;
    selected_version?: string;
    version_source?: string;
    content_type?: string;
    final_url?: string;
    redirect_chain?: string[];
    discovery_source?: string;
  };
  services?: string[];
  capabilities?: string[];
  missing_required_services?: string[];
  missing_required_capabilities?: string[];
  transports?: ContractTransport[];
  schemas?: Array<{
    url?: string;
    reachable?: boolean;
    valid_json?: boolean;
    schema_valid?: boolean;
    title?: string;
    error?: string;
    status_code?: number;
    content_type?: string;
    groups?: string[];
    field_results?: Record<string, Record<string, boolean>>;
    llm_analysis?: Record<string, unknown>;
  }>;
  payment_handlers?: string[];
};

export function UcpScoreSummary({
  report,
  job,
  loading = false,
}: Readonly<{ report: UcpAuditReport | null; job: UcpAuditJob | null; loading?: boolean }>) {
  const score = report?.overall_score ?? Number(job?.summary?.overall_score ?? 0);
  const findings = useNormalizedFindings(report);
  const blocking = findings.filter((finding) => finding.severity === 'blocking').length;
  const warnings = findings.filter((finding) => finding.severity !== 'blocking').length;
  const gateApplied = Boolean(report?.report_json?.d_ucp1_gate_applied);
  const transportGateApplied = Boolean(report?.report_json?.d_ucp3_gate_applied);
  const dUcp1GateMax = Number(report?.report_json?.d_ucp1_gate_max_score ?? 30);
  const dUcp3GateMax = Number(report?.report_json?.d_ucp3_gate_max_score ?? 45);

  return (
    <section className="border-border bg-panel overflow-hidden rounded-[var(--radius-lg)] border shadow-sm">
      <div className="grid gap-0 lg:grid-cols-[300px_1fr]">
        <div className="border-divider bg-background/30 relative flex flex-col items-center justify-center border-b p-6 lg:border-r lg:border-b-0">
          <div className="absolute inset-x-0 top-3 flex items-center justify-center gap-1.5">
            <Sparkles className="text-accent size-3 animate-pulse" />
            <span className="type-label-mono text-muted">UCP PROTOCOL INDEX</span>
          </div>
          {loading && !report ? (
            <LoadingScoreRing size={156} />
          ) : (
            <ScoreRing score={report ? score : 0} size={156} stroke={10} />
          )}
          <div className="mt-4 flex w-full flex-col gap-2.5 px-2">
            <SummaryRow label="Blocking gaps" value={blocking} tone="danger" />
            <SummaryRow label="Warnings" value={warnings} tone="warning" />
            <SummaryRow
              label="Run status"
              value={job?.status ?? 'pending'}
              tone={statusTone(job?.status)}
            />
          </div>
        </div>

        <div className="flex min-w-0 flex-col justify-center p-5">
          {gateApplied ? (
            <div className="border-danger/30 bg-danger/5 text-danger mb-4 flex items-center gap-2.5 rounded-[var(--radius-md)] border px-3 py-2.5">
              <ShieldAlert className="size-4 shrink-0" />
              <div className="leading-snug">
                <p className="type-subheading text-danger">
                  Discovery blocked - overall score capped at {dUcp1GateMax}.
                </p>
                <p className="type-caption text-danger/75 mt-0.5">
                  Publish /.well-known/ucp before other dimensions are evaluated.
                </p>
              </div>
            </div>
          ) : null}

          {transportGateApplied ? (
            <div className="border-danger/30 bg-danger/5 text-danger mb-4 flex items-center gap-2.5 rounded-[var(--radius-md)] border px-3 py-2.5">
              <ShieldAlert className="size-4 shrink-0" />
              <div className="leading-snug">
                <p className="type-subheading text-danger">
                  Transport blocked - overall score capped at {dUcp3GateMax}.
                </p>
                <p className="type-caption text-danger/75 mt-0.5">
                  Make one declared REST, MCP, or embedded transport reachable.
                </p>
              </div>
            </div>
          ) : null}

          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {report?.dimension_scores.map((dimension) => (
              <DimensionScoreCard
                key={dimension.dimension_id}
                dimension={dimension}
                blocked={gateApplied && dimension.dimension_id !== 'D-UCP1'}
              />
            )) ?? (
              <div className="col-span-full py-8">
                <DataRegionEmpty
                  title="Awaiting audit"
                  description="Supply a target domain and launch a UCP protocol audit."
                />
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

export function UcpDimensionTable({
  report,
  loading,
}: Readonly<{ report: UcpAuditReport | null; loading: boolean }>) {
  if (loading) {
    return (
      <TableSurface contentClassName="min-h-[280px]">
        <DataRegionLoading count={6} />
      </TableSurface>
    );
  }

  return (
    <TableSurface contentClassName="min-h-[280px]">
      <header className="border-divider bg-background/25 flex items-center justify-between gap-3 border-b px-4 py-3">
        <div>
          <h2 className="type-label-mono text-muted">UCP PROTOCOL DIMENSIONS</h2>
          <p className="type-caption text-muted mt-0.5">
            Compliance measured against discovery, services, transport, and payload contracts.
          </p>
        </div>
        {report ? (
          <Badge tone={badgeTone(scoreTone(report.overall_score))} className="font-normal">
            {report.overall_score}/100
          </Badge>
        ) : null}
      </header>

      {report ? (
        <div className="divide-divider bg-background/5 divide-y">
          {report.dimension_scores.map((dimension) => {
            const meta = DIMENSION_META[dimension.dimension_id] ?? {
              label: dimension.dimension_id,
              subtitle: '',
              desc: '',
            };
            const findings = dimension.findings.map((finding, index) =>
              normalizeFinding(finding, index),
            );

            return (
              <article
                key={dimension.dimension_id}
                className="hover:bg-background/10 grid gap-6 px-6 py-6 transition-colors lg:grid-cols-[300px_1fr]"
              >
                <div className="lg:border-divider/40 flex flex-col justify-start border-b pr-4 pb-4 lg:border-r lg:border-b-0 lg:pb-0">
                  <div className="mb-2 flex items-center gap-2">
                    <span className="font-mono text-xs text-foreground bg-background border-border/80 rounded border px-2 py-0.5">
                      {dimension.dimension_id}
                    </span>
                    <Badge tone={badgeTone(dimension.status)} className="scale-90">
                      {dimension.status}
                    </Badge>
                  </div>
                  <h3 className="type-subheading text-foreground mt-1">{meta.label}</h3>
                  <p className="type-caption text-muted mt-2 pr-2">{meta.desc}</p>
                </div>

                <div className="flex min-w-0 flex-col justify-center lg:pl-4">
                  <div className="mb-3.5 flex flex-wrap items-center gap-2">
                    <ScoreBadge score={dimension.score} />
                    <span className="type-label text-secondary">{meta.subtitle}</span>
                  </div>

                  {findings.length ? (
                    <ul className="grid w-full max-w-[760px] min-w-0 gap-2.5">
                      {findings.map((finding) => (
                        <li
                          key={finding.id}
                          className="border-border bg-panel flex w-full min-w-0 items-start gap-3 rounded-[var(--radius-md)] border p-4 shadow-sm"
                        >
                          <AlertTriangle
                            className={cn(
                              'mt-0.5 size-4 shrink-0',
                              finding.severity === 'blocking' ? 'text-danger' : 'text-warning',
                            )}
                          />
                          <div className="min-w-0 flex-1">
                            <div className="type-body-sm text-foreground">
                              {finding.description}
                            </div>
                            <div className="type-caption text-muted mt-1">{finding.fix}</div>
                            <div className="mt-2 flex flex-wrap items-center gap-1.5">
                              <Badge tone="neutral" className="font-mono lowercase">
                                {finding.effort}
                              </Badge>
                              <span className="font-sans text-xs font-medium text-secondary">{finding.action}</span>
                            </div>
                            <EvidenceChips evidence={finding.evidence} />
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="border-success-border bg-success-bg text-success-text flex w-full max-w-[760px] items-center gap-2.5 rounded-[var(--radius-md)] border p-3.5">
                      <Check className="text-success-text size-4 shrink-0" />
                      <span className="type-subheading text-success-text font-medium">
                        Protocol contract is present for this dimension.
                      </span>
                    </div>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      ) : (
        <DataRegionEmpty
          title="Ready for protocol audit"
          description="Run an audit to inspect the UCP contract."
        />
      )}
    </TableSurface>
  );
}

export function UcpContractPanel({ report }: Readonly<{ report: UcpAuditReport | null }>) {
  const contract = getContract(report);
  const schemas = contract.schemas ?? [];

  return (
    <TableSurface>
      <header className="border-divider bg-background/25 flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
        <div>
          <h2 className="type-label-mono text-muted">UCP CONTRACT CHECKS</h2>
          <p className="type-caption text-muted mt-0.5">
            Discovery profile and payload schema validation.
          </p>
        </div>
        {contract.manifest ? (
          <Badge tone={contract.manifest.valid ? 'success' : 'danger'}>
            profile {contract.manifest.valid ? 'valid' : 'invalid'}
          </Badge>
        ) : null}
      </header>

      {report ? (
        <div className="grid gap-5 p-4">
          <ManifestSummary contract={contract} findings={report.findings} />
          <TransportSummary transports={contract.transports ?? []} />
          <div>
            <h3 className="type-label-mono text-muted mb-2">SCHEMA MATRIX</h3>
            <div className="overflow-x-auto">
              {schemas.length ? (
                <Table className="min-w-[980px]">
                  <TableHeader>
                    <TableRow>
                      <TableHead>Schema</TableHead>
                      <TableHead>Result</TableHead>
                      <TableHead>Coverage</TableHead>
                      <TableHead>Missing</TableHead>
                      <TableHead>LLM / Error</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {schemas.map((schema, index) => (
                      <TableRow key={`${schema.url ?? 'schema'}-${index}`}>
                        <TableCell className="max-w-[320px] py-3 align-top">
                          <div className="font-mono text-xs text-foreground break-all">
                            {schema.url}
                          </div>
                          {schema.title ? (
                            <div className="type-caption text-muted mt-1 break-words">
                              {schema.title}
                            </div>
                          ) : null}
                        </TableCell>
                        <TableCell className="w-[120px] py-3 align-top">
                          <Badge
                            tone={
                              schema.reachable && schema.valid_json && schema.schema_valid
                                ? 'success'
                                : 'danger'
                            }
                          >
                            {schema.reachable && schema.valid_json && schema.schema_valid
                              ? 'schema'
                              : 'bad'}
                          </Badge>
                          {schema.status_code ? (
                            <div className="type-caption-mono text-muted mt-1">
                              {schema.status_code}
                            </div>
                          ) : null}
                        </TableCell>
                        <TableCell className="min-w-[360px] py-3 align-top">
                          <SchemaCoverageCell schema={schema} />
                        </TableCell>
                        <TableCell className="min-w-[220px] py-3 align-top">
                          <SchemaMissingCell schema={schema} />
                        </TableCell>
                        <TableCell className="type-caption max-w-[260px] py-3 align-top">
                          <SchemaAnalysisText schema={schema} />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <DataRegionEmpty
                  title="No schema declarations"
                  description="The manifest did not expose payload schema URLs."
                />
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className="py-8">
          <DataRegionEmpty
            title="No contract payload"
            description="Run an audit to inspect the UCP contract."
          />
        </div>
      )}
    </TableSurface>
  );
}

export function UcpFixSequence({ report }: Readonly<{ report: UcpAuditReport | null }>) {
  const roadmap = useMemo(() => getRoadmap(report), [report]);
  const storageKey = report?.job_id ? `ucp-fix-sequence-${report.job_id}` : null;
  const [done, setDone] = useState<Record<string, boolean>>({});
  const doneCount = roadmap.filter((item) => done[item.id]).length;
  const progressPercent = roadmap.length ? Math.round((doneCount / roadmap.length) * 100) : 0;

  function toggle(id: string) {
    const next = { ...done, [id]: !done[id] };
    setDone(next);
    if (storageKey && globalThis.window !== undefined) {
      globalThis.window.localStorage.setItem(storageKey, JSON.stringify(next));
    }
  }

  function exportPlan() {
    const lines = roadmap.map((item, index) => {
      const checked = done[item.id] ? 'x' : ' ';
      const evidenceLines = evidenceToLines(item.evidence)
        .map((line) => `   - ${line}`)
        .join('\n');
      const evidenceBlock = evidenceLines ? `\n${evidenceLines}` : '';
      return `- [${checked}] ${index + 1}. [${item.subSkill}] ${item.action} (${item.priority}, ${item.effort})\n   Source: ${item.source}${evidenceBlock}`;
    });
    const domain = formatUnknownText(report?.report_json?.domain, 'Audit Store');
    const content = `# UCP Repair Roadmap\n\nTarget Domain: ${domain}\nOverall Compliance: ${report?.overall_score ?? 0}/100\n\n${lines.join('\n\n')}\n`;
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `ucp-repair-roadmap-${report?.job_id ?? 'audit'}.md`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <TableSurface>
      <header className="border-divider bg-background/25 flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
        <div>
          <h2 className="type-label-mono text-muted">REPAIR ROADMAP</h2>
          <p className="type-caption text-muted mt-0.5">
            Grouped by UCP and Shopify repair sub-skills.
          </p>
        </div>
        <Button
          type="button"
          variant="download"
          size="sm"
          onClick={exportPlan}
          disabled={!roadmap.length}
        >
          <Download className="size-3.5" />
          Export roadmap
        </Button>
      </header>

      {roadmap.length ? (
        <div className="divide-divider flex flex-col gap-0 divide-y">
          <div className="bg-background/10 flex flex-wrap items-center justify-between gap-4 px-4 py-3">
            <div className="flex items-center gap-2">
              <CheckSquare className="text-success size-4" />
              <span className="type-label-mono text-foreground">ROADMAP PROGRESS:</span>
              <span className="type-caption-mono bg-background border-border text-success rounded border px-1.5 py-0.5">
                {doneCount} of {roadmap.length} fixed ({progressPercent}%)
              </span>
            </div>
            <div className="bg-border h-2 w-full shrink-0 overflow-hidden rounded-full md:w-48">
              <div
                className="bg-success h-full rounded-full transition-all duration-500"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>

          <ol className="divide-divider divide-y">
            {roadmap.map((item, index) => {
              const isChecked = done[item.id];
              const priorityTone = roadmapPriorityTone(item.priority);
              return (
                <li
                  key={item.id}
                  className={cn(
                    'grid gap-3 px-4 py-3.5 transition-all sm:grid-cols-[auto_1fr_auto] sm:items-start',
                    isChecked ? 'bg-background/10 opacity-70' : 'hover:bg-background/20',
                  )}
                >
                  <button
                    type="button"
                    onClick={() => toggle(item.id)}
                    className={cn(
                      'border-border mt-0.5 flex size-5 cursor-pointer items-center justify-center rounded-[var(--radius-sm)] border transition-all',
                      isChecked
                        ? 'bg-success border-success text-white'
                        : 'bg-background hover:border-accent',
                    )}
                    aria-label="Toggle roadmap action"
                  >
                    {isChecked ? <Check className="size-3.5" /> : null}
                  </button>

                  <div className="min-w-0">
                    <div
                      className={cn(
                        'type-body-sm text-foreground flex flex-wrap items-center gap-2',
                        isChecked && 'text-muted line-through',
                      )}
                    >
                      <span className="font-mono text-xs text-secondary">{index + 1}.</span>
                      <span className="font-mono text-xs bg-background border-border text-foreground font-medium rounded border px-1.5 py-0.5">
                        {item.subSkill}
                      </span>
                      <span>{item.action}</span>
                    </div>
                    <p className="type-caption text-muted mt-1">Source: {item.source}</p>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      <Badge tone="neutral" className="font-mono lowercase">
                        {item.effort}
                      </Badge>
                      {item.dependsOn.length ? (
                        <span className="font-mono text-xs text-muted">
                          Depends: {item.dependsOn.join(', ')}
                        </span>
                      ) : null}
                    </div>
                    <EvidenceChips evidence={item.evidence} />
                  </div>

                  <Badge tone={priorityTone}>{item.priority}</Badge>
                </li>
              );
            })}
          </ol>
        </div>
      ) : (
        <div className="py-8">
          <DataRegionEmpty
            title="No repair items"
            description="No UCP gaps were emitted for this run."
          />
        </div>
      )}
    </TableSurface>
  );
}

const SCHEMA_GROUP_LABELS: Record<string, string> = {
  catalog: 'Catalog',
  cart_checkout: 'Cart',
  order_policy: 'Order',
};

function ManifestSummary({
  contract,
  findings,
}: Readonly<{ contract: UcpContract; findings: Array<Record<string, unknown>> }>) {
  const manifest = contract.manifest;
  if (!manifest) return null;
  const signingKeyFindings = findingsForCodes(findings, ['signing_keys_missing']);
  const cacheFindings = findingsForCodes(findings, ['cache_control_missing']);
  const structuralFindings = findingsForCodes(findings, ['manifest_invalid']);
  const redirectFindings = findingsForCodes(findings, ['manifest_redirected']);
  let profileValue = 'invalid';
  if (manifest.found === false) {
    profileValue = 'not found';
  } else if (manifest.valid) {
    profileValue = 'valid';
  }

  return (
    <div>
      <h3 className="type-label-mono text-muted mb-2">DISCOVERY PROFILE</h3>
      <div className="grid gap-3 lg:grid-cols-2">
        <ManifestFact
          label="Profile"
          value={profileValue}
          tone={manifest.found === false || manifest.valid === false ? 'danger' : 'success'}
          detail={manifest.final_url}
        />
        <ManifestFact
          label="Version"
          value={manifest.selected_version || manifest.target_version || '-'}
          tone={manifest.selected_version ? 'success' : 'neutral'}
          detail={manifest.version_source ? `source: ${manifest.version_source}` : undefined}
        />
        <ManifestFact
          label="Signing keys"
          value={signingKeyFindings.length ? 'missing or invalid' : 'ok'}
          tone={signingKeyFindings.length ? 'warning' : 'success'}
        />
        <ManifestFact
          label="Cache-Control"
          value={cacheFindings.length ? 'needs header' : 'ok'}
          tone={cacheFindings.length ? 'warning' : 'success'}
        />
      </div>
      <EvidenceChips
        evidence={[
          ...structuralFindings.flatMap((finding) => finding.evidence),
          ...signingKeyFindings.flatMap((finding) => finding.evidence),
          ...cacheFindings.flatMap((finding) => finding.evidence),
          ...redirectFindings.flatMap((finding) => finding.evidence),
        ]}
      />
    </div>
  );
}

function ManifestFact({
  label,
  value,
  tone,
  detail,
}: Readonly<{ label: string; value: string; tone: string; detail?: string }>) {
  return (
    <div className="border-border bg-panel rounded-[var(--radius-md)] border p-3">
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="type-label text-secondary">{label}</span>
        <Badge tone={badgeTone(tone)}>{value}</Badge>
      </div>
      {detail ? <div className="font-mono text-xs text-foreground mt-1 break-all">{detail}</div> : null}
    </div>
  );
}

function TransportSummary({ transports }: Readonly<{ transports: ContractTransport[] }>) {
  if (!transports.length) {
    return (
      <div>
        <h3 className="type-label-mono text-muted mb-2">TRANSPORTS</h3>
        <DataRegionEmpty
          title="No declared transports"
          description="The manifest did not expose REST, MCP, A2A, or embedded transports."
        />
      </div>
    );
  }
  return (
    <div>
      <h3 className="type-label-mono text-muted mb-2">TRANSPORTS</h3>
      <div className="overflow-x-auto">
        <Table className="min-w-[820px]">
          <TableHeader>
            <TableRow>
              <TableHead>Transport</TableHead>
              <TableHead>Negotiation</TableHead>
              <TableHead>Endpoint</TableHead>
              <TableHead>Details</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {transports.map((transport, index) => {
              const negotiationTone = transportNegotiationTone(transport);
              const negotiationLabel = transportNegotiationLabel(transport);
              let detail = <span className="text-muted">-</span>;
              if (transport.error) {
                detail = <span className="text-danger">{transport.error}</span>;
              } else if (transport.tool_names?.length) {
                detail = (
                  <span className="text-muted">Tools: {transport.tool_names.join(', ')}</span>
                );
              }

              return (
                <TableRow key={`${transport.transport ?? 'transport'}-${index}`}>
                  <TableCell className="py-3 align-top">
                    <div className="font-mono text-xs text-foreground">
                      {(transport.transport ?? 'unknown').toUpperCase()}
                    </div>
                    {transport.service ? (
                      <div className="type-caption text-muted mt-1">{transport.service}</div>
                    ) : null}
                  </TableCell>
                  <TableCell className="py-3 align-top">
                    <Badge tone={negotiationTone}>{negotiationLabel}</Badge>
                    {transport.status_code ? (
                      <div className="font-mono text-xs text-muted mt-1">
                        HTTP {transport.status_code}
                      </div>
                    ) : null}
                  </TableCell>
                  <TableCell className="max-w-[300px] py-3 align-top">
                    <div className="font-mono text-xs text-foreground break-all">
                      {transport.endpoint || '-'}
                    </div>
                  </TableCell>
                  <TableCell className="type-caption max-w-[320px] py-3 align-top break-words">{detail}</TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

function SchemaCoverageCell({
  schema,
}: Readonly<{ schema: NonNullable<UcpContract['schemas']>[number] }>) {
  const groups = activeSchemaGroups(schema);
  if (!groups.length) {
    return <span className="type-caption-mono text-muted">No UCP payload group detected</span>;
  }
  return (
    <div className="grid gap-2 sm:grid-cols-3">
      {groups.map((group) => (
        <SchemaGroupSummary key={group} schema={schema} group={group} />
      ))}
    </div>
  );
}

function SchemaGroupSummary({
  schema,
  group,
}: Readonly<{ schema: NonNullable<UcpContract['schemas']>[number]; group: string }>) {
  const fields = schema.field_results?.[group] ?? {};
  const entries = Object.entries(fields);
  const total = entries.length;
  const present = entries.filter(([, value]) => value).length;
  const percent = total ? Math.round((present / total) * 100) : 0;
  const complete = total > 0 && present === total;
  return (
    <div className="border-border bg-background-alt/30 rounded px-2.5 py-2">
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="type-label text-secondary">{SCHEMA_GROUP_LABELS[group] ?? group}</span>
        <span className={cn('font-mono text-xs font-semibold', complete ? 'text-success' : 'text-danger')}>
          {present}/{total}
        </span>
      </div>
      <div className="bg-border h-1.5 overflow-hidden rounded-full">
        <div
          className={cn('h-full rounded-full', complete ? 'bg-success' : 'bg-danger')}
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

function SchemaMissingCell({
  schema,
}: Readonly<{ schema: NonNullable<UcpContract['schemas']>[number] }>) {
  const missing = activeSchemaGroups(schema)
    .flatMap((group) =>
      Object.entries(schema.field_results?.[group] ?? {})
        .filter(([, present]) => !present)
        .map(([field]) => field),
    )
    .filter((field, index, fields) => fields.indexOf(field) === index);
  if (!missing.length) {
    return <span className="font-mono text-xs text-success font-medium">Complete</span>;
  }
  return (
    <div className="flex max-w-[260px] flex-wrap gap-1">
      {missing.map((field) => (
        <Badge key={field} tone="danger" className="font-mono lowercase">
          {field}
        </Badge>
      ))}
    </div>
  );
}

function activeSchemaGroups(schema: NonNullable<UcpContract['schemas']>[number]) {
  const declared = (schema.groups ?? []).filter((group) => schema.field_results?.[group]);
  if (declared.length) return declared;
  return Object.entries(schema.field_results ?? {})
    .filter(([, fields]) => Object.values(fields).some(Boolean))
    .map(([group]) => group);
}

function SchemaAnalysisText({
  schema,
}: Readonly<{ schema: NonNullable<UcpContract['schemas']>[number] }>) {
  const llmSummary =
    schema.llm_analysis && typeof schema.llm_analysis.summary === 'string'
      ? schema.llm_analysis.summary
      : '';
  if (llmSummary) return <span className="text-accent">{llmSummary}</span>;
  if (schema.error) return <span className="text-danger">{schema.error}</span>;
  return <span className="text-muted">-</span>;
}

function EvidenceChips({ evidence }: Readonly<{ evidence: Array<Record<string, unknown>> }>) {
  const lines = evidenceToLines(evidence);
  if (!lines.length) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-1">
      {lines.map((line, index) => (
        <code
          key={`${line}-${index}`}
          className="font-mono text-xs text-foreground bg-background-alt/80 border-border/80 rounded border px-1.5 py-0.5"
        >
          {line}
        </code>
      ))}
    </div>
  );
}

function evidenceToLines(evidence: Array<Record<string, unknown>> = []): string[] {
  return evidence
    .flatMap((entry) =>
      Object.entries(entry).flatMap(([key, value]) => {
        if (Array.isArray(value)) {
          return value.map((item) => `${key}: ${formatEvidenceValue(item)}`);
        }
        if (value && typeof value === 'object') {
          return `${key}: ${JSON.stringify(value)}`;
        }
        return `${key}: ${formatEvidenceValue(value)}`;
      }),
    )
    .filter((line) => line.trim().length > 0)
    .slice(0, 12);
}

function findingsForCodes(findings: Array<Record<string, unknown>>, codes: string[]) {
  return findings
    .filter((finding) => codes.includes(formatUnknownText(finding.code)))
    .map((finding) => ({
      ...finding,
      evidence: Array.isArray(finding.evidence)
        ? (finding.evidence as Array<Record<string, unknown>>)
        : [],
    }));
}

function formatEvidenceValue(value: unknown): string {
  return formatUnknownText(value, '-');
}

function formatUnknownText(value: unknown, fallback = ''): string {
  if (value == null || value === '') return fallback;
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean' || typeof value === 'bigint') {
    return String(value);
  }
  if (Array.isArray(value)) {
    const items: string[] = value.map((item) => formatUnknownText(item)).filter(Boolean);
    return items.length ? items.join(', ') : fallback;
  }
  try {
    return JSON.stringify(value) ?? fallback;
  } catch {
    return fallback;
  }
}

function DimensionScoreCard({
  dimension,
  blocked,
}: Readonly<{
  dimension: UcpAuditReport['dimension_scores'][number];
  blocked: boolean;
}>) {
  const meta = DIMENSION_META[dimension.dimension_id] ?? {
    label: dimension.dimension_id,
    subtitle: '',
    desc: '',
  };
  return (
    <Card
      className={cn(
        'relative flex min-h-[160px] flex-col justify-between p-5 hover:border-accent/60 hover:scale-[1.02] hover:shadow-md duration-300 ease-out bg-panel border-border rounded-[var(--radius-lg)] border',
        blocked && 'pointer-events-none opacity-35 select-none',
      )}
    >
      {blocked ? (
        <div className="bg-background/10 absolute inset-0 z-10 flex items-center justify-center rounded-[var(--radius-lg)] backdrop-blur-[0.5px]">
          <span className="type-caption-mono text-danger border-danger/45 bg-background/90 rotate-12 rounded border px-2 py-0.5 shadow">
            BLOCKED
          </span>
        </div>
      ) : null}
      <div className="flex items-start justify-between gap-3">
        <ScoreRing score={dimension.score} size={70} stroke={8} compact />
        {dimension.findings.length ? (
          <Badge tone="danger" className="type-caption-mono">
            {dimension.findings.length} gaps
          </Badge>
        ) : (
          <Badge tone="success" className="type-caption-mono">
            READY
          </Badge>
        )}
      </div>
      <div className="mt-3.5">
        <h4 className="type-subheading text-foreground">{meta.label}</h4>
        <p className="type-caption text-muted mt-1.5 mb-0">{meta.subtitle}</p>
      </div>
    </Card>
  );
}

function SummaryRow({
  label,
  value,
  tone,
}: Readonly<{ label: string; value: string | number; tone: string }>) {
  const badgeToneVal = (tone === 'success' || tone === 'warning' || tone === 'danger' || tone === 'neutral' || tone === 'accent' || tone === 'info')
    ? tone
    : 'neutral';

  return (
    <div className="border-border/40 flex items-center justify-between border-b pb-1.5">
      <span className="type-label text-muted">{label}</span>
      <Badge tone={badgeToneVal} className="font-mono lowercase">
        {value}
      </Badge>
    </div>
  );
}

function ScoreRing({
  score,
  size,
  stroke,
  compact = false,
}: Readonly<{ score: number; size: number; stroke: number; compact?: boolean }>) {
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (Math.max(0, Math.min(100, score)) / 100) * circumference;
  return (
    <div
      className="relative grid shrink-0 place-items-center"
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} className="-rotate-90">
        <defs>
          <linearGradient id="score-ring-success" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="var(--success)" />
            <stop offset="100%" stopColor="color-mix(in srgb, var(--success) 60%, black)" />
          </linearGradient>
          <linearGradient id="score-ring-warning" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="var(--warning)" />
            <stop offset="100%" stopColor="color-mix(in srgb, var(--warning) 60%, black)" />
          </linearGradient>
          <linearGradient id="score-ring-danger" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="var(--danger)" />
            <stop offset="100%" stopColor="color-mix(in srgb, var(--danger) 60%, black)" />
          </linearGradient>
        </defs>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          className="stroke-border-subtle/50"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={
            score >= 80
              ? 'url(#score-ring-success)'
              : score >= 50
                ? 'url(#score-ring-warning)'
                : 'url(#score-ring-danger)'
          }
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 800ms ease-out' }}
        />
      </svg>
      <div className="absolute text-center select-none">
        <div
          className={cn(
            'text-foreground tabular-nums font-semibold',
            compact ? 'type-display-sm' : 'type-display',
          )}
        >
          {score}
        </div>
        {!compact && <div className="type-caption-mono text-muted mt-0.5 leading-none">/100</div>}
      </div>
    </div>
  );
}

function LoadingScoreRing({ size }: Readonly<{ size: number }>) {
  return (
    <div
      className="border-border bg-background-alt grid animate-pulse place-items-center rounded-full border"
      style={{ width: size, height: size }}
    >
      <div className="bg-border h-10 w-16 rounded" />
    </div>
  );
}

function ScoreBadge({ score }: Readonly<{ score: number }>) {
  return <Badge tone={badgeTone(scoreTone(score))}>{score}</Badge>;
}

function useNormalizedFindings(report: UcpAuditReport | null) {
  return useMemo(
    () => (report?.findings ?? []).map((finding, index) => normalizeFinding(finding, index)),
    [report],
  );
}

function normalizeFinding(finding: Record<string, unknown>, index: number): NormalizedFinding {
  const code = formatUnknownText(finding.code, 'unknown_finding');
  const dimension = formatUnknownText(finding.dimension_id ?? finding.dimension);
  const copy = FINDING_COPY[code] ?? {
    description: formatUnknownText(finding.message, code),
    fix: 'Inspect the exported UCP contract payload and repair the declared service contract.',
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
    evidence: Array.isArray(finding.evidence)
      ? (finding.evidence as Array<Record<string, unknown>>)
      : [],
  };
}

function getContract(report: UcpAuditReport | null): UcpContract {
  const raw = report?.report_json?.ucp_contract;
  return raw && typeof raw === 'object' ? raw : {};
}

function getRoadmap(report: UcpAuditReport | null) {
  const raw = report?.report_json?.repair_roadmap;
  if (Array.isArray(raw) && raw.length) {
    return raw.map((item, index) => {
      const roadmap = item;
      const subSkill = formatUnknownText(roadmap.sub_skill, 'ucp');
      return {
        id: `${subSkill}-${index}`,
        subSkill,
        priority: formatUnknownText(roadmap.priority, 'medium'),
        action: formatUnknownText(roadmap.action, 'Repair UCP contract'),
        source: formatUnknownText(roadmap.source, 'UCP Overview and UCP Schema Reference'),
        evidence: Array.isArray(roadmap.evidence)
          ? (roadmap.evidence as Array<Record<string, unknown>>)
          : [],
        effort: formatUnknownText(roadmap.effort, 'review'),
        dependsOn: Array.isArray(roadmap.depends_on)
          ? roadmap.depends_on.map(formatUnknownText)
          : [],
      };
    });
  }
  return (report?.findings ?? []).map((finding, index) => {
    const normalized = normalizeFinding(finding, index);
    return {
      id: normalized.id,
      subSkill: normalized.dimension,
      priority: normalized.impact,
      action: normalized.action,
      source: 'UCP Overview and UCP Schema Reference',
      evidence: normalized.evidence,
      effort: normalized.effort,
      dependsOn: [],
    };
  });
}

function scoreTone(score: number) {
  if (score >= 80) return 'success';
  if (score >= 50) return 'warning';
  return 'danger';
}

function roadmapPriorityTone(priority: string) {
  if (priority === 'critical') return 'danger';
  if (priority === 'high') return 'warning';
  return 'neutral';
}

function transportNegotiationTone(transport: ContractTransport) {
  if (transport.negotiated) return 'success';
  if (transport.reachable || transport.profile_required) return 'warning';
  return 'danger';
}

function transportNegotiationLabel(transport: ContractTransport) {
  if (transport.negotiated) return 'negotiated';
  if (transport.profile_required) return 'profile required';
  if (transport.reachable) return 'reachable';
  return 'unreachable';
}

function statusTone(status?: string) {
  if (status === 'complete') return 'success';
  if (status === 'failed') return 'danger';
  if (status === 'queued' || status === 'running') return 'warning';
  return 'neutral';
}

function badgeTone(value: string) {
  if (value === 'success' || value === 'pass' || value === 'complete') return 'success';
  if (value === 'warning' || value === 'queued' || value === 'running') return 'warning';
  if (value === 'danger' || value === 'fail' || value === 'failed' || value === 'blocking') {
    return 'danger';
  }
  return 'neutral';
}
