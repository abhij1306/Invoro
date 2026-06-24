import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { TopBarProvider, useTopBarHeader } from '../../components/layout/top-bar-context';
import UcpAuditPage from './ucp-audit-page';
import {
  UcpContractPanel,
  UcpDimensionTable,
  UcpFixSequence,
  UcpScoreSummary,
} from './ucp-audit-components';
import { useUcpAudit } from './use-ucp-audit';

vi.mock('next/navigation', () => ({
  usePathname: () => '/ucp-audit',
}));

const apiMock = vi.hoisted(() => ({
  createUcpAuditJob: vi.fn(),
  exportUcpAuditJson: vi.fn((jobId: number) => `/api/ucp-audit/jobs/${jobId}/export.json`),
  exportUcpAuditMarkdown: vi.fn((jobId: number) => `/api/ucp-audit/jobs/${jobId}/export.md`),
  getUcpAuditJob: vi.fn(),
  listUcpAuditJobs: vi.fn(),
}));

vi.mock('../../lib/api', () => ({
  api: apiMock,
}));

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      mutations: { retry: false },
      queries: { retry: false },
    },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <UcpAuditHarness />
    </QueryClientProvider>,
  );
}

function renderShellPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      mutations: { retry: false },
      queries: { retry: false },
    },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <TopBarProvider>
        <HeaderActions />
        <UcpAuditPage />
      </TopBarProvider>
    </QueryClientProvider>,
  );
}

function HeaderActions() {
  const header = useTopBarHeader();
  return <>{header?.actions ?? null}</>;
}

function UcpAuditHarness() {
  const controller = useUcpAudit();
  return (
    <>
      {controller.error ? <div>{controller.error}</div> : null}
      <label>
        Domain
        <input
          value={controller.domain}
          onChange={(event) => controller.setDomain(event.target.value)}
        />
      </label>
      <button type="button" onClick={controller.startAudit}>
        Start Audit
      </button>
    </>
  );
}

describe('UcpAuditPage', () => {
  beforeEach(() => {
    apiMock.createUcpAuditJob.mockReset();
    apiMock.getUcpAuditJob.mockReset();
    apiMock.listUcpAuditJobs.mockReset();
    apiMock.createUcpAuditJob.mockResolvedValue({
      id: 101,
      user_id: 1,
      domain: 'dashingdiva.com',
      status: 'queued',
      options: {},
      summary: {},
      created_at: new Date('2026-05-18T00:00:00Z').toISOString(),
      updated_at: new Date('2026-05-18T00:00:00Z').toISOString(),
      completed_at: null,
    });
    apiMock.listUcpAuditJobs.mockResolvedValue([]);
  });

  it('clears the required-domain error when a domain is entered', async () => {
    renderPage();

    fireEvent.click(screen.getByRole('button', { name: /start audit/i }));

    expect(await screen.findByText('Domain is required.')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/domain/i), {
      target: { value: 'https://dashingdiva.com' },
    });

    await waitFor(() => {
      expect(screen.queryByText('Domain is required.')).not.toBeInTheDocument();
    });
  });

  it('uses the current domain from the shell start button', async () => {
    renderShellPage();

    fireEvent.change(screen.getByLabelText(/domain/i), {
      target: { value: 'https://dashingdiva.com' },
    });
    const startButtons = await screen.findAllByRole('button', { name: /start audit/i });
    fireEvent.click(startButtons[0]);

    await waitFor(() => {
      expect(apiMock.createUcpAuditJob).toHaveBeenCalledWith({
        domain: 'https://dashingdiva.com',
        options: {
          sample_size: 5,
          llm_enabled: false,
          report_formats: ['json', 'markdown'],
        },
      });
    });
    expect(screen.queryByText('Domain is required.')).not.toBeInTheDocument();
  });

  it('rejects domains with paths before submit', async () => {
    renderPage();

    fireEvent.change(screen.getByLabelText(/domain/i), {
      target: { value: 'https://dashingdiva.com/products/1' },
    });
    fireEvent.click(screen.getByRole('button', { name: /start audit/i }));

    expect(
      await screen.findByText('Enter only the domain, without a path or query string.'),
    ).toBeInTheDocument();
    expect(apiMock.createUcpAuditJob).not.toHaveBeenCalled();
  });

  it('renders evidence, product samples, signal details, and gate caps', () => {
    const report = sampleReport();

    render(
      <>
        <UcpScoreSummary report={report} job={sampleJob()} />
        <UcpDimensionTable report={report} loading={false} />
        <UcpContractPanel report={report} />
      </>,
    );

    expect(
      screen.getByText(/Structured markup blocked - overall score capped at 30/i),
    ).toBeInTheDocument();
    expect(screen.getByText('structured_price: 100')).toBeInTheDocument();
    expect(screen.getAllByText('1 sprint').length).toBeGreaterThan(0);
    expect(screen.getByText('SIGNAL AUDIT')).toBeInTheDocument();
    expect(screen.getByText('STRUCTURED MARKUP')).toBeInTheDocument();
    expect(screen.getByText('PRODUCT SAMPLE MATRIX')).toBeInTheDocument();
    expect(screen.getAllByText('Product JSON-LD').length).toBeGreaterThan(0);
    expect(screen.getByText('Sitemap')).toBeInTheDocument();
    expect(screen.getAllByText('example.com/p/1').length).toBeGreaterThan(0);
    expect(screen.getByText('product page')).toBeInTheDocument();
    expect(screen.getByText('gptbot')).toBeInTheDocument();
    expect(screen.getByText('blocked')).toBeInTheDocument();
    expect(screen.getByText('Widget')).toBeInTheDocument();
  });

  it('shows full markdown export link for completed reports', async () => {
    apiMock.listUcpAuditJobs.mockResolvedValue([sampleJob()]);
    apiMock.getUcpAuditJob.mockResolvedValue({
      job: sampleJob(),
      page_results: [],
      report: sampleReport(),
    });

    renderShellPage();

    const link = await screen.findByRole('link', { name: /export report/i });

    await waitFor(() => {
      expect(link).toHaveAttribute('href', '/api/ucp-audit/jobs/101/export.md');
    });
    expect(link).toHaveAttribute('download');
  });

  it('exports roadmap evidence', async () => {
    const createObjectURL = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:test');
    const revokeObjectURL = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => undefined);

    render(<UcpFixSequence report={sampleReport()} />);

    fireEvent.click(screen.getByRole('button', { name: /export roadmap/i }));

    const blob = createObjectURL.mock.calls[0][0] as Blob;
    await expect(blob.text()).resolves.toContain('structured_price: 100');
    expect(click).toHaveBeenCalled();

    createObjectURL.mockRestore();
    revokeObjectURL.mockRestore();
    click.mockRestore();
  });
});

function sampleJob() {
  return {
    id: 101,
    user_id: 1,
    domain: 'example.com',
    status: 'complete',
    options: {},
    summary: { overall_score: 30 },
    created_at: new Date('2026-05-18T00:00:00Z').toISOString(),
    updated_at: new Date('2026-05-18T00:00:00Z').toISOString(),
    completed_at: new Date('2026-05-18T00:00:00Z').toISOString(),
  };
}

function sampleReport() {
  return {
    id: 201,
    job_id: 101,
    overall_score: 30,
    dimension_scores: [
      {
        dimension_id: 'D-AID1',
        score: 80,
        status: 'warning',
        weight: 0.2,
        findings: [
          {
            code: 'AID1_OPEN_GRAPH_MISSING',
            dimension_id: 'D-AID1',
            severity: 'warning',
            message: 'No Open Graph product signal was detected.',
            evidence: [{ product_jsonld: 1 }],
          },
        ],
      },
      {
        dimension_id: 'D-AID4',
        score: 70,
        status: 'warning',
        weight: 0.15,
        findings: [
          {
            code: 'AID4_PRICE_STALE',
            dimension_id: 'D-AID4',
            severity: 'warning',
            message: 'Structured price diverges from visible price by more than 5%.',
            evidence: [
              {
                url: 'https://example.com/p/1',
                structured_price: 100,
                dom_price: 120,
              },
            ],
          },
        ],
      },
      {
        dimension_id: 'D-AID2',
        score: 60,
        status: 'warning',
        weight: 0.15,
        findings: [
          {
            code: 'AID2_VARIANTS_MISSING',
            dimension_id: 'D-AID2',
            severity: 'warning',
            message: 'Variant, size, or color data is missing.',
            evidence: [{ missing_fields: ['variants'] }],
          },
        ],
      },
    ],
    findings: [
      {
        code: 'AID1_OPEN_GRAPH_MISSING',
        dimension_id: 'D-AID1',
        severity: 'warning',
        message: 'No Open Graph product signal was detected.',
        evidence: [{ product_jsonld: 1 }],
      },
      {
        code: 'AID4_PRICE_STALE',
        dimension_id: 'D-AID4',
        severity: 'warning',
        message: 'Structured price diverges from visible price by more than 5%.',
        evidence: [
          {
            url: 'https://example.com/p/1',
            structured_price: 100,
            dom_price: 120,
          },
        ],
      },
      {
        code: 'AID2_VARIANTS_MISSING',
        dimension_id: 'D-AID2',
        severity: 'warning',
        message: 'Variant, size, or color data is missing.',
        evidence: [{ missing_fields: ['variants'] }],
      },
    ],
    report_json: {
      domain: 'example.com',
      d_ucp1_gate_applied: true,
      d_ucp1_gate_max_score: 30,
      d_ucp3_gate_applied: false,
      d_ucp3_gate_max_score: 0,
      ucp_contract: {
        catalog: {
          domain: 'example.com',
          pages_crawled: 2,
          sampled_urls: ['https://example.com', 'https://example.com/p/1'],
          crawl_errors: [],
        },
        structured_markup: {
          product_jsonld_count: 1,
          jsonld_block_count: 1,
          jsonld_parse_errors: [],
          open_graph: { '@type': 'product' },
        },
        product_records: [
          {
            source_url: 'https://example.com/p/1',
            title: 'Widget',
            price: '120',
            brand: 'Example',
          },
        ],
        discovery: {
          robots_directives: { gptbot: ['/'] },
          sitemap_found: true,
        },
      },
      repair_roadmap: [
        {
          sub_skill: 'freshness availability',
          priority: 'high',
          finding_codes: ['AID4_PRICE_STALE'],
          action: 'Keep structured prices aligned with visible DOM prices.',
          source: 'AI Discoverability Score guidance',
          evidence: [{ structured_price: 100, dom_price: 120 }],
          effort: '1 sprint',
          depends_on: ['structured markup', 'catalog completeness'],
        },
      ],
    },
    markdown_report: '',
    created_at: new Date('2026-05-18T00:00:00Z').toISOString(),
    updated_at: new Date('2026-05-18T00:00:00Z').toISOString(),
  };
}
