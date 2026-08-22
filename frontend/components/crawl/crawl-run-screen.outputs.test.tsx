import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { LogTerminal } from './log-terminal';
import {
  apiMock,
  alertsApiMock,
  describeCrawlRunScreen,
  makeDomainRecipe,
  makeLog,
  makeRecord,
  MockWebSocket,
  pushMock,
  renderRunScreen,
  replaceMock,
  terminalRun,
} from './crawl-run-screen.test-harness';

describeCrawlRunScreen(() => {
  it('renders decoded Thai URLs in the JSON preview without changing the underlying records payload', async () => {
    apiMock.getRecords.mockResolvedValue({
      items: [
        {
          ...makeRecord(1),
          data: {
            title: 'Item 1',
            url: 'https://www.shop.ving.run/product/%E0%B8%AA%E0%B8%B5%E0%B8%94%E0%B8%B3',
          },
        },
      ],
      meta: { page: 1, limit: 400, total: 1 },
    });

    renderRunScreen();

    const jsonButtons = await screen.findAllByRole('button', { name: 'JSON' });
    fireEvent.click(jsonButtons.at(-1)!);

    await waitFor(() => {
      expect(screen.getByText(/https:\/\/www\.shop\.ving\.run\/product\/สีดำ/)).toBeInTheDocument();
    });

    expect(screen.queryByText(/%E0%B8%AA%E0%B8%B5%E0%B8%94%E0%B8%B3/)).not.toBeInTheDocument();
  });

  it('creates variant alert rules from the JSON result builder', async () => {
    apiMock.getRecords.mockResolvedValue({
      items: [
        {
          ...makeRecord(1),
          source_url: 'https://example.com/products/shirt',
          data: {
            title: 'Variant Shirt',
            url: 'https://example.com/products/shirt',
            variants: [
              { sku: 'shirt-s', size: 'S', availability: 'in_stock', price: '999.00' },
              { sku: 'shirt-m', size: 'M', availability: 'out_of_stock', price: '1099.00' },
            ],
          },
        },
      ],
      meta: { page: 1, limit: 400, total: 1 },
    });

    renderRunScreen();

    const jsonButtons = await screen.findAllByRole('button', { name: 'JSON' });
    fireEvent.click(jsonButtons.at(-1)!);
    fireEvent.click(await screen.findByRole('button', { name: 'Alert' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Any Availability' }));
    fireEvent.click(screen.getByRole('button', { name: 'Create Alert' }));

    await waitFor(() => {
      expect(alertsApiMock.create).toHaveBeenCalledWith({
        url: 'https://example.com/products/shirt',
        target_fields: ['variants'],
        target_rules: [
          {
            path: 'variants[*].availability',
            label: 'Any variant availability',
            operator: 'changed',
            value: undefined,
          },
        ],
        condition: null,
        webhook_url: null,
        poll_interval_seconds: 300,
      });
    });
    expect(pushMock).toHaveBeenCalledWith('/alerts/42');
  });

  it('keeps payload peek limited to the cleaned JSON record', async () => {
    apiMock.getRecords.mockResolvedValue({
      items: [
        {
          ...makeRecord(1),
          data: {
            title: 'Item 1',
            url: 'https://example.com/p/1',
            _internal_metric: 'hidden',
          },
          raw_data: {
            _confidence: { score: 0.4 },
          },
          source_trace: {
            acquisition: { final_url: 'https://example.com/p/1' },
          },
        },
      ],
      meta: { page: 1, limit: 100, total: 1 },
    });
    apiMock.getCrawlLogs.mockResolvedValue([
      makeLog(1, 'Starting crawl run for https://example.com/p/1 (1/1)'),
      makeLog(2, 'Persisted 1 record(s) for https://example.com/p/1'),
    ]);

    renderRunScreen();

    fireEvent.click(await screen.findByRole('button', { name: 'Logs' }));
    const peekButton = await screen.findByRole('button', { name: 'Peek' });
    peekButton.focus();
    fireEvent.click(peekButton);

    const dialog = await screen.findByRole('dialog', { name: 'Payload Peek' });
    expect(dialog).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Close' })).toHaveFocus();
    expect(screen.getByText(/"title": "Item 1"/)).toBeInTheDocument();
    expect(screen.queryByText(/raw_record/)).not.toBeInTheDocument();
    expect(screen.queryByText(/source_trace/)).not.toBeInTheDocument();
    expect(screen.queryByText(/_confidence/)).not.toBeInTheDocument();
    expect(screen.queryByText(/_internal_metric/)).not.toBeInTheDocument();

    fireEvent.keyDown(dialog, { key: 'Escape' });
    expect(screen.queryByRole('dialog', { name: 'Payload Peek' })).not.toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Peek' })).toHaveFocus();
    });
  });

  it('does not reopen the log websocket when incoming messages advance the log cursor', async () => {
    apiMock.getCrawlLogs.mockResolvedValue([makeLog(1, 'First log line')]);

    renderRunScreen();

    fireEvent.click(await screen.findByRole('button', { name: 'Logs' }));

    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });
    expect(MockWebSocket.instances[0].url).toContain('after_id=1');

    MockWebSocket.instances[0].onmessage?.({
      data: JSON.stringify(makeLog(2, 'Second log line')),
    });

    expect(await screen.findByText('Second log line')).toBeInTheDocument();
    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });
  });

  it('keeps final per-url duration from the latest persisted record timestamp', async () => {
    apiMock.getRecords.mockResolvedValue({
      items: [
        {
          ...makeRecord(1),
          data: {
            title: 'Item 1',
            url: 'https://example.com/p/1',
          },
          raw_data: {
            _confidence: { score: 0.4 },
          },
          source_trace: {
            acquisition: {
              final_url: 'https://example.com/p/1',
              browser_diagnostics: {
                phase_timings_ms: { total: 9000 },
              },
            },
          },
          created_at: new Date('2026-04-08T10:00:42Z').toISOString(),
        },
      ],
      meta: { page: 1, limit: 100, total: 1 },
    });
    apiMock.getCrawlLogs.mockResolvedValue([
      makeLog(1, 'Starting crawl run for https://example.com/p/1 (1/1)'),
      makeLog(2, 'Persisted 1 record(s) for https://example.com/p/1'),
    ]);

    renderRunScreen();

    fireEvent.click(await screen.findByRole('button', { name: 'Logs' }));

    expect(await screen.findByText('40%')).toBeInTheDocument();
    expect(screen.getByText('0m 42s')).toBeInTheDocument();
  });

  it('ticks duration for every active parallel site group', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-08T10:00:10Z'));

    render(
      <LogTerminal
        live
        logs={[
          makeLog(1, 'Starting crawl run for https://example.com/p/1 (1/2)'),
          makeLog(2, 'Starting crawl run for https://example.com/p/2 (2/2)'),
        ]}
      />,
    );

    expect(screen.getAllByText('0m 10s')).toHaveLength(2);
  });

  it('keeps ticking after extraction until a terminal event arrives', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-04-08T10:00:10Z'));

    render(
      <LogTerminal
        live
        logs={[
          {
            ...makeLog(1, 'Starting crawl run for https://example.com/p/1 (1/1)'),
            created_at: '2026-04-08T10:00:00Z',
          },
          {
            ...makeLog(2, 'Extracted 1 record for https://example.com/p/1'),
            created_at: '2026-04-08T10:00:05Z',
          },
        ]}
      />,
    );

    expect(screen.getByText('0m 10s')).toBeInTheDocument();
  });

  it('preserves selected records when switching from table to logs', async () => {
    apiMock.getRecords.mockResolvedValue({
      items: [makeRecord(1), makeRecord(2)],
      meta: { page: 1, limit: 100, total: 2 },
    });

    renderRunScreen();

    fireEvent.click(await screen.findByRole('checkbox', { name: 'Select record 1' }));
    expect(
      screen.getByRole('button', { name: 'Product Intelligence Selected (1)' }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Logs' }));

    expect(
      screen.getByRole('button', { name: 'Product Intelligence Selected (1)' }),
    ).toBeInTheDocument();
  });

  it('prefills batch crawl with the originating jobs domain from listing runs', async () => {
    apiMock.getCrawl.mockResolvedValue({
      ...terminalRun(101),
      surface: 'job_listing',
      url: 'https://example.com/careers',
      settings: { crawl_module: 'category', crawl_mode: 'single' },
    });
    apiMock.getRecords.mockResolvedValue({
      items: [
        {
          ...makeRecord(1),
          source_url: 'https://jobs.example.com/posting/1',
          data: { title: 'Role 1', url: 'https://jobs.example.com/posting/1' },
        },
      ],
      meta: { page: 1, limit: 100, total: 1 },
    });

    renderRunScreen();

    const batchButton = await screen.findByRole('button', { name: 'Batch Crawl (1)' });
    fireEvent.click(batchButton);

    expect(replaceMock).toHaveBeenCalledWith('/crawl?module=pdp&mode=batch');
    expect(window.sessionStorage.getItem('bulk-crawl-prefill-v1')).toBe(
      JSON.stringify({
        domain: 'jobs',
        urls: ['https://jobs.example.com/posting/1'],
      }),
    );
  });

  it('keeps batch crawl result URLs available after switching from table to logs', async () => {
    apiMock.getCrawl.mockResolvedValue({
      ...terminalRun(101),
      surface: 'ecommerce_listing',
      url: 'https://www.karenmillen.com/categories/womens-dresses',
      settings: { crawl_module: 'category', crawl_mode: 'single' },
      result_summary: {
        extraction_verdict: 'partial',
        record_count: 2,
      },
    });
    apiMock.getRecords.mockImplementation(
      (_runId: number, params?: { page?: number; limit?: number }) => {
        const limit = params?.limit ?? 100;
        return Promise.resolve({
          items: [
            {
              ...makeRecord(1),
              source_url: 'https://www.karenmillen.com/p/1',
              data: { title: 'Dress 1', url: 'https://www.karenmillen.com/p/1' },
            },
            {
              ...makeRecord(2),
              source_url: 'https://www.karenmillen.com/p/2',
              data: { title: 'Dress 2', url: 'https://www.karenmillen.com/p/2' },
            },
          ],
          meta: { page: 1, limit, total: 2 },
        });
      },
    );

    renderRunScreen();

    const logsTab = await screen.findByRole('button', { name: 'Logs' });
    fireEvent.click(logsTab);

    const batchButton = await screen.findByRole('button', { name: 'Batch Crawl (2)' });
    fireEvent.click(batchButton);

    expect(replaceMock).toHaveBeenCalledWith('/crawl?module=pdp&mode=batch');
    expect(window.sessionStorage.getItem('bulk-crawl-prefill-v1')).toBe(
      JSON.stringify({
        domain: 'commerce',
        urls: ['https://www.karenmillen.com/p/1', 'https://www.karenmillen.com/p/2'],
      }),
    );
  });

  it('triggers direct CSV export downloads from the terminal workspace', async () => {
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    try {
      renderRunScreen();

      const button = await screen.findByRole('button', { name: 'Excel (CSV)' });
      fireEvent.click(button);

      expect(apiMock.exportCsv).toHaveBeenCalledWith(101);
      expect(clickSpy).toHaveBeenCalledTimes(1);
    } finally {
      clickSpy.mockRestore();
    }
  });

  it('uses formatted markdown as the primary output for content runs', async () => {
    apiMock.getCrawl.mockResolvedValue({
      ...terminalRun(101),
      url: 'https://codeforces.com/',
      surface: 'content_detail',
      requested_fields: ['title', 'markdown', 'url'],
      result_summary: {
        extraction_verdict: 'success',
        record_count: 1,
      },
    });
    apiMock.getRecords.mockResolvedValue({
      items: [
        {
          ...makeRecord(1),
          source_url: 'https://codeforces.com/',
          data: {
            title: 'Codeforces',
            markdown:
              '# Codeforces\n\nProgramming contests and **practice**.\n\n- Contests\n- Problemset\n\n[Visit](https://codeforces.com/)',
            url: 'https://codeforces.com/',
          },
        },
      ],
      meta: { page: 1, limit: 100, total: 1 },
    });

    renderRunScreen();

    expect(await screen.findByRole('heading', { name: 'Codeforces' })).toBeInTheDocument();
    const markdownButtons = screen.getAllByRole('button', { name: 'Markdown' });
    expect(markdownButtons.some((button) => button.getAttribute('aria-pressed') === 'true')).toBe(
      true,
    );
    expect(screen.queryByRole('button', { name: /Table/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Excel (CSV)' })).not.toBeInTheDocument();
    expect(screen.getByText(/Programming contests and/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Visit' })).toHaveAttribute(
      'href',
      'https://codeforces.com/',
    );
  });

  it('keeps table and exports visible for failed terminal runs with records', async () => {
    apiMock.getCrawl.mockResolvedValue({
      ...terminalRun(101),
      status: 'failed',
      result_summary: {
        extraction_verdict: 'partial',
        record_count: 2,
        error: 'One URL failed.',
      },
    });

    renderRunScreen();

    expect(await screen.findByRole('button', { name: /Table \(2\)/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Excel (CSV)' })).toBeInTheDocument();
  });

  it('renders completed-run learning tab without run-config tab', async () => {
    renderRunScreen();

    expect(await screen.findByRole('button', { name: 'Learning' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Run Config' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Learning' }));
    expect(await screen.findByRole('heading', { name: 'Run Learning' })).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Keep' }).length).toBeGreaterThan(0);
  });

  it('renders learning as XPath winners without extracted values', async () => {
    apiMock.getDomainRecipe.mockResolvedValue({
      ...makeDomainRecipe(),
      field_learning: [
        {
          field_name: 'variant_axes',
          value: { Size: ['S', 'M'] },
          source_labels: ['dom_selector'],
          selector_kind: 'xpath',
          selector_value: "//select[@name='size']",
          source_record_ids: [1],
          feedback: null,
        },
      ],
    });

    renderRunScreen();

    fireEvent.click(await screen.findByRole('button', { name: 'Learning' }));
    expect(await screen.findByText(/XPath winner/)).toBeInTheDocument();
    expect(screen.queryByText(/Value:/)).not.toBeInTheDocument();
  });

  it('applies keep and reject field learning actions from the completed-run panel', async () => {
    renderRunScreen();

    fireEvent.click(await screen.findByRole('button', { name: 'Learning' }));
    expect(await screen.findByRole('heading', { name: 'Run Learning' })).toBeInTheDocument();
    const keepButtons = screen.getAllByRole('button', { name: 'Keep' });
    const rejectButtons = screen.getAllByRole('button', { name: 'Reject' });

    fireEvent.click(keepButtons[0]);
    await waitFor(() => {
      expect(apiMock.applyDomainRecipeFieldAction).toHaveBeenCalledWith(101, {
        field_name: 'price',
        action: 'keep',
        selector_kind: 'xpath',
        selector_value: "//span[@class='price']/text()",
        source_record_ids: [1],
      });
    });

    fireEvent.click(rejectButtons[0]);
    await waitFor(() => {
      expect(apiMock.applyDomainRecipeFieldAction).toHaveBeenCalledWith(101, {
        field_name: 'price',
        action: 'reject',
        selector_kind: 'xpath',
        selector_value: "//span[@class='price']/text()",
        source_record_ids: [1],
      });
    });
  });

  it('hides learning for batch runs', async () => {
    apiMock.getCrawl.mockResolvedValue({
      ...terminalRun(101),
      run_type: 'batch',
    });

    renderRunScreen();

    expect(await screen.findByRole('button', { name: /Table \(2\)/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Learning' })).not.toBeInTheDocument();
    expect(apiMock.getDomainRecipe).not.toHaveBeenCalled();
  });
});
