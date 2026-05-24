'use client';

import { useMemo, useState } from 'react';
import {
  AlertTriangle,
  Check,
  CheckSquare,
  Download,
  ExternalLink,
  Info,
  ShieldAlert,
  Sparkles,
} from 'lucide-react';

import { DataRegionEmpty, DataRegionLoading, TableSurface } from '../../components/ui/patterns';
import { Badge, Button } from '../../components/ui/primitives';
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
    description: 'The UCP discovery profile exists but the shopping service contract is invalid.',
    fix: 'Declare dev.ucp.shopping and a valid UCP profile shape.',
    effort: '2 hours',
    action: 'Fix discovery profile',
    impact: 'critical',
  },
  service_missing: {
    description: 'Required UCP shopping service is not declared.',
    fix: 'Add dev.ucp.shopping to the UCP services map.',
    effort: '1 hour',
    action: 'Declare shopping service',
    impact: 'critical',
  },
  capability_missing: {
    description: 'Required UCP shopping capabilities are missing.',
    fix: 'Declare catalog, cart, checkout, order, fulfillment, and discount capabilities.',
    effort: '2-4 hours',
    action: 'Declare missing capabilities',
    impact: 'high',
  },
  transport_missing: {
    description: 'No REST, MCP, or embedded UCP transport was declared.',
    fix: 'Expose at least one supported UCP transport endpoint or embedded contract.',
    effort: '1 sprint',
    action: 'Expose transport',
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
};

type ContractTransport = {
  service?: string;
  transport?: string;
  endpoint?: string;
  reachable?: boolean;
  negotiated?: boolean;
  profile_required?: boolean;
  status_code?: number;
};

type UcpContract = {
  manifest?: { found?: boolean; valid?: boolean; supported_versions?: string[] };
  services?: string[];
  capabilities?: string[];
  missing_required_services?: string[];
  missing_required_capabilities?: string[];
  transports?: ContractTransport[];
  schemas?: Array<{ url?: string; reachable?: boolean; valid_json?: boolean; title?: string }>;
  payment_handlers?: string[];
};

type RepairRoadmapItem = {
  sub_skill?: string;
  priority?: string;
  finding_codes?: string[];
  action?: string;
  source?: string;
};

export function UcpScoreSummary({
  report,
  job,
}: Readonly<{ report: UcpAuditReport | null; job: UcpAuditJob | null }>) {
  const score = report?.overall_score ?? Number(job?.summary?.overall_score ?? 0);
  const findings = useNormalizedFindings(report);
  const blocking = findings.filter((finding) => finding.severity === 'blocking').length;
  const warnings = findings.filter((finding) => finding.severity !== 'blocking').length;
  const gateApplied = Boolean(report?.report_json?.d_ucp1_gate_applied);

  return (
    <section className="border-border bg-panel overflow-hidden rounded-[var(--radius-lg)] border shadow-sm">
      <div className="grid gap-0 lg:grid-cols-[300px_1fr]">
        <div className="border-divider bg-background/30 relative flex flex-col items-center justify-center border-b p-6 lg:border-r lg:border-b-0">
          <div className="absolute inset-x-0 top-3 flex items-center justify-center gap-1.5">
            <Sparkles className="text-accent size-3 animate-pulse" />
            <span className="text-muted font-sans text-xs font-semibold tracking-wider uppercase">
              UCP PROTOCOL INDEX
            </span>
          </div>
          <ScoreRing score={report ? score : 0} size={156} stroke={10} />
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
            <div className="border-danger/30 bg-danger/5 text-danger mb-4 flex items-center gap-2.5 rounded-[var(--radius-md)] border px-3 py-2.5 text-xs">
              <ShieldAlert className="size-4 shrink-0" />
              <div className="leading-snug font-semibold">
                Discovery blocked. UCP clients cannot locate this store contract.
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
          <h2 className="text-muted font-sans text-xs font-bold tracking-widest uppercase">
            UCP PROTOCOL DIMENSIONS
          </h2>
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
                    <span className="text-muted bg-background border-border/80 rounded border px-2 py-0.5 font-mono text-[10px] font-normal">
                      {dimension.dimension_id}
                    </span>
                    <Badge tone={badgeTone(dimension.status)} className="scale-90">
                      {dimension.status}
                    </Badge>
                  </div>
                  <h3 className="text-foreground mt-1 text-[14px] leading-snug font-normal">
                    {meta.label}
                  </h3>
                  <p className="text-muted mt-2 pr-2 text-[11.5px] leading-relaxed">{meta.desc}</p>
                </div>

                <div className="flex min-w-0 flex-col justify-center lg:pl-4">
                  <div className="mb-3.5 flex flex-wrap items-center gap-2">
                    <ScoreBadge score={dimension.score} />
                    <span className="type-caption text-secondary text-[11px] font-normal tracking-wider uppercase">
                      {meta.subtitle}
                    </span>
                  </div>

                  {findings.length ? (
                    <ul className="grid w-full max-w-[760px] min-w-0 gap-2.5">
                      {findings.map((finding) => (
                        <li
                          key={finding.id}
                          className="border-border/50 bg-background/20 flex w-full min-w-0 items-start gap-3 rounded-[var(--radius-md)] border p-4 shadow-sm"
                        >
                          <AlertTriangle
                            className={cn(
                              'mt-0.5 size-4 shrink-0',
                              finding.severity === 'blocking' ? 'text-danger' : 'text-warning',
                            )}
                          />
                          <div className="min-w-0 flex-1">
                            <div className="text-foreground text-[13px] leading-relaxed font-normal">
                              {finding.description}
                            </div>
                            <div className="text-muted mt-1 text-[11px]">{finding.fix}</div>
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="border-success/20 bg-success/5 text-success flex w-full max-w-[760px] items-center gap-2.5 rounded-[var(--radius-md)] border p-3.5 text-xs">
                      <Check className="text-success size-4 shrink-0" />
                      <span className="text-[12.5px] font-semibold">
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
  const transports = contract.transports ?? [];
  const schemas = contract.schemas ?? [];

  return (
    <TableSurface>
      <header className="border-divider bg-background/25 flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
        <div>
          <h2 className="text-muted font-sans text-xs font-bold tracking-widest uppercase">
            UCP CONTRACT CHECKS
          </h2>
          <p className="type-caption text-muted mt-0.5">
            Discovery profile, capabilities, transports, schemas, and payment handlers.
          </p>
        </div>
        {contract.manifest ? (
          <Badge tone={contract.manifest.valid ? 'success' : 'danger'}>
            profile {contract.manifest.valid ? 'valid' : 'invalid'}
          </Badge>
        ) : null}
      </header>

      {report ? (
        <div className="grid gap-4 p-4 lg:grid-cols-3">
          <ContractCard title="Services" items={contract.services ?? []} />
          <ContractCard title="Capabilities" items={contract.capabilities ?? []} />
          <ContractCard title="Payment Handlers" items={contract.payment_handlers ?? []} />

          <div className="lg:col-span-3">
            <h3 className="text-muted mb-2 font-sans text-xs font-bold tracking-widest uppercase">
              TRANSPORTS
            </h3>
            <div className="overflow-x-auto">
              <Table className="min-w-[760px]">
                <TableHeader>
                  <TableRow>
                    <TableHead>Service</TableHead>
                    <TableHead>Transport</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Endpoint</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {transports.length ? (
                    transports.map((transport, index) => (
                      <TableRow key={`${transport.endpoint ?? transport.transport}-${index}`}>
                        <TableCell className="font-mono text-xs">
                          {transport.service || '-'}
                        </TableCell>
                        <TableCell className="font-mono text-xs">
                          {transport.transport || '-'}
                        </TableCell>
                        <TableCell>
                          <Badge
                            tone={
                              transport.negotiated
                                ? 'success'
                                : transport.reachable
                                  ? 'warning'
                                  : 'danger'
                            }
                          >
                            {transport.negotiated
                              ? 'negotiated'
                              : transport.profile_required
                                ? 'profile required'
                                : transport.transport === 'embedded' && transport.reachable
                                  ? 'declared'
                                  : transport.reachable
                                    ? 'reachable'
                                    : 'failed'}
                          </Badge>
                        </TableCell>
                        <TableCell className="max-w-[360px] truncate font-mono text-xs">
                          {transport.endpoint ? (
                            <a
                              href={transport.endpoint}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-accent inline-flex items-center gap-1"
                            >
                              <span className="truncate">{transport.endpoint}</span>
                              <ExternalLink className="size-3" />
                            </a>
                          ) : (
                            '-'
                          )}
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell colSpan={4}>No transports declared.</TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </div>

          <div className="lg:col-span-3">
            <h3 className="text-muted mb-2 font-sans text-xs font-bold tracking-widest uppercase">
              SCHEMAS
            </h3>
            <div className="grid gap-2 md:grid-cols-2">
              {schemas.length ? (
                schemas.map((schema) => (
                  <div
                    key={schema.url}
                    className="border-border bg-background/25 flex items-center justify-between gap-3 rounded-[var(--radius-md)] border p-3"
                  >
                    <span className="truncate font-mono text-xs">{schema.url}</span>
                    <Badge tone={schema.reachable && schema.valid_json ? 'success' : 'danger'}>
                      {schema.reachable && schema.valid_json ? 'json' : 'bad'}
                    </Badge>
                  </div>
                ))
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
    if (storageKey && typeof window !== 'undefined') {
      window.localStorage.setItem(storageKey, JSON.stringify(next));
    }
  }

  function exportPlan() {
    const lines = roadmap.map((item, index) => {
      const checked = done[item.id] ? 'x' : ' ';
      return `- [${checked}] ${index + 1}. [${item.subSkill}] ${item.action} (${item.priority})\n   Source: ${item.source}`;
    });
    const content = `# UCP Repair Roadmap\n\nTarget Domain: ${(report?.report_json?.domain as string) ?? 'Audit Store'}\nOverall Compliance: ${report?.overall_score ?? 0}/100\n\n${lines.join('\n\n')}\n`;
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
          <h2 className="text-muted font-sans text-xs font-bold tracking-widest uppercase">
            REPAIR ROADMAP
          </h2>
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
              <span className="text-foreground font-mono text-xs font-normal">
                ROADMAP PROGRESS:
              </span>
              <span className="bg-background border-border text-success rounded border px-1.5 py-0.5 font-mono text-xs font-normal">
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
                        'text-foreground flex flex-wrap items-center gap-2 text-xs font-semibold',
                        isChecked && 'text-muted line-through',
                      )}
                    >
                      <span className="text-secondary font-mono">{index + 1}.</span>
                      <span className="bg-background/80 border-border rounded border px-1.5 py-0.5 font-mono text-[10px] leading-none">
                        {item.subSkill}
                      </span>
                      <span>{item.action}</span>
                    </div>
                    <p className="text-muted mt-1 text-[11px] leading-relaxed">
                      Source: {item.source}
                    </p>
                  </div>

                  <Badge
                    tone={
                      item.priority === 'critical'
                        ? 'danger'
                        : item.priority === 'high'
                          ? 'warning'
                          : 'neutral'
                    }
                  >
                    {item.priority}
                  </Badge>
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

function ContractCard({ title, items }: Readonly<{ title: string; items: string[] }>) {
  return (
    <section className="border-border bg-background/20 rounded-[var(--radius-md)] border p-4">
      <h3 className="text-muted mb-3 font-sans text-xs font-bold tracking-widest uppercase">
        {title}
      </h3>
      {items.length ? (
        <div className="flex flex-wrap gap-1.5">
          {items.map((item) => (
            <Badge key={item} tone="neutral" className="font-mono text-[10px]">
              {item}
            </Badge>
          ))}
        </div>
      ) : (
        <div className="text-muted flex items-center gap-2 text-xs">
          <Info className="size-3.5" />
          None declared
        </div>
      )}
    </section>
  );
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
    <div
      className={cn(
        'border-border bg-background/25 hover:border-accent/60 relative flex min-h-[160px] flex-col justify-between rounded-[var(--radius-md)] border p-5 transition-all duration-300 hover:scale-[1.02] hover:shadow-md',
        blocked && 'pointer-events-none opacity-35 select-none',
      )}
    >
      {blocked ? (
        <div className="bg-background/10 absolute inset-0 z-10 flex items-center justify-center rounded-[var(--radius-md)] backdrop-blur-[0.5px]">
          <span className="text-danger border-danger/45 bg-background/90 rotate-12 rounded border px-2 py-0.5 font-mono text-xs font-normal shadow">
            BLOCKED
          </span>
        </div>
      ) : null}
      <div className="flex items-start justify-between gap-3">
        <ScoreRing score={dimension.score} size={70} stroke={8} compact />
        {dimension.findings.length ? (
          <Badge tone="danger" className="font-mono text-[9px] font-normal">
            {dimension.findings.length} gaps
          </Badge>
        ) : (
          <Badge tone="success" className="font-mono text-[9px] font-normal">
            READY
          </Badge>
        )}
      </div>
      <div className="mt-3.5">
        <div className="text-foreground text-[13px] leading-snug font-normal">{meta.label}</div>
        <p className="text-muted mt-1.5 text-[11px] leading-normal">{meta.subtitle}</p>
      </div>
    </div>
  );
}

function SummaryRow({
  label,
  value,
  tone,
}: Readonly<{ label: string; value: string | number; tone: string }>) {
  return (
    <div className="border-border/40 flex items-center justify-between border-b pb-1.5">
      <span className="text-muted font-sans text-xs font-semibold tracking-wider uppercase">
        {label}
      </span>
      <span
        className={cn('bg-background-alt rounded px-1.5 py-0.5 font-mono text-xs', toneClass(tone))}
      >
        {value}
      </span>
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
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          className="stroke-border"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          className={ringClass(score)}
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
            'text-foreground font-mono leading-none font-normal tracking-tighter tabular-nums',
            compact ? 'text-sm' : 'text-3xl',
          )}
        >
          {score}
        </div>
        {!compact && (
          <div className="text-muted mt-0.5 font-mono text-[9px] leading-none font-normal uppercase">
            /100
          </div>
        )}
      </div>
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
  const code = String(finding.code ?? 'unknown_finding');
  const dimension = String(finding.dimension_id ?? finding.dimension ?? '');
  const copy = FINDING_COPY[code] ?? {
    description: String(finding.message || code),
    fix: 'Inspect the exported UCP contract payload and repair the declared service contract.',
    effort: 'review',
    action: `Resolve ${code}`,
    impact: 'medium' as const,
  };
  return {
    id: `${dimension}-${code}-${index}`,
    code,
    dimension,
    severity: String(finding.severity ?? 'info'),
    description: String(finding.message || copy.description),
    fix: copy.fix,
    effort: copy.effort,
    action: copy.action,
    impact: copy.impact,
  };
}

function getContract(report: UcpAuditReport | null): UcpContract {
  const raw = report?.report_json?.ucp_contract;
  return raw && typeof raw === 'object' ? (raw as UcpContract) : {};
}

function getRoadmap(report: UcpAuditReport | null) {
  const raw = report?.report_json?.repair_roadmap;
  if (Array.isArray(raw) && raw.length) {
    return raw.map((item, index) => {
      const roadmap = item as RepairRoadmapItem;
      return {
        id: `${roadmap.sub_skill ?? 'roadmap'}-${index}`,
        subSkill: String(roadmap.sub_skill ?? 'ucp'),
        priority: String(roadmap.priority ?? 'medium'),
        action: String(roadmap.action ?? 'Repair UCP contract'),
        source: String(roadmap.source ?? 'UCP Overview and UCP Schema Reference'),
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
    };
  });
}

function scoreTone(score: number) {
  if (score >= 80) return 'success';
  if (score >= 50) return 'warning';
  return 'danger';
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

function toneClass(tone: string) {
  if (tone === 'success') return 'text-success';
  if (tone === 'warning') return 'text-warning';
  if (tone === 'danger') return 'text-danger';
  return 'text-foreground';
}

function ringClass(score: number) {
  if (score >= 80) return 'stroke-success';
  if (score >= 50) return 'stroke-warning';
  return 'stroke-danger';
}
