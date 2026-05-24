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

  it('renders evidence, schema fields, transport details, and gate caps', () => {
    const report = sampleReport();

    render(
      <>
        <UcpScoreSummary report={report} job={sampleJob()} />
        <UcpDimensionTable report={report} loading={false} />
        <UcpContractPanel report={report} />
      </>,
    );

    expect(screen.getByText(/Discovery blocked - overall score capped at 30/i)).toBeInTheDocument();
    expect(screen.getByText(/Transport blocked - overall score capped at 45/i)).toBeInTheDocument();
    expect(screen.getByText('missing_schema_fields: price')).toBeInTheDocument();
    expect(screen.getByText('1 sprint')).toBeInTheDocument();
    expect(screen.getByText('SCHEMA MATRIX')).toBeInTheDocument();
    expect(screen.getByText('Catalog')).toBeInTheDocument();
    expect(screen.getByText('price')).toBeInTheDocument();
    expect(screen.getByText('Add missing price.')).toBeInTheDocument();
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
    await expect(blob.text()).resolves.toContain('missing_schema_fields: price');
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
        dimension_id: 'D-UCP1',
        score: 0,
        status: 'fail',
        weight: 0.2,
        findings: [
          {
            code: 'manifest_invalid',
            dimension_id: 'D-UCP1',
            severity: 'blocking',
            message: 'Manifest invalid.',
            evidence: [{ errors: ['Missing required array: signing_keys'] }],
          },
        ],
      },
      {
        dimension_id: 'D-UCP4',
        score: 60,
        status: 'warning',
        weight: 0.15,
        findings: [
          {
            code: 'catalog_contract_missing',
            dimension_id: 'D-UCP4',
            severity: 'warning',
            message: 'Catalog contract incomplete.',
            evidence: [{ missing_schema_fields: ['price'] }],
          },
        ],
      },
    ],
    findings: [
      {
        code: 'manifest_invalid',
        dimension_id: 'D-UCP1',
        severity: 'blocking',
        message: 'Manifest invalid.',
        evidence: [{ errors: ['Missing required array: signing_keys'] }],
      },
      {
        code: 'catalog_contract_missing',
        dimension_id: 'D-UCP4',
        severity: 'warning',
        message: 'Catalog contract incomplete.',
        evidence: [{ missing_schema_fields: ['price'] }],
      },
    ],
    report_json: {
      domain: 'example.com',
      d_ucp1_gate_applied: true,
      d_ucp1_gate_max_score: 30,
      d_ucp3_gate_applied: true,
      d_ucp3_gate_max_score: 45,
      ucp_contract: {
        manifest: { valid: false },
        services: ['dev.ucp.shopping'],
        capabilities: ['dev.ucp.shopping.catalog.search'],
        transports: [
          {
            service: 'dev.ucp.shopping',
            transport: 'mcp',
            endpoint: 'https://example.com/ucp',
            reachable: false,
            negotiated: false,
            status_code: 404,
            error: 'tools/list failed',
          },
        ],
        schemas: [
          {
            url: 'https://example.com/catalog.schema.json',
            reachable: true,
            valid_json: true,
            schema_valid: true,
            field_results: {
              catalog: {
                product_id: true,
                title: true,
                price: false,
                currency: true,
                availability: true,
              },
            },
            llm_analysis: { summary: 'Add missing price.' },
          },
        ],
      },
      repair_roadmap: [
        {
          sub_skill: 'catalog',
          priority: 'high',
          finding_codes: ['catalog_contract_missing'],
          action: 'Repair catalog contract',
          source: 'UCP Overview and UCP Schema Reference',
          evidence: [{ missing_schema_fields: ['price'] }],
          effort: '1 sprint',
          depends_on: ['discovery', 'capabilities', 'transport'],
        },
      ],
    },
    markdown_report: '',
    created_at: new Date('2026-05-18T00:00:00Z').toISOString(),
    updated_at: new Date('2026-05-18T00:00:00Z').toISOString(),
  };
}
