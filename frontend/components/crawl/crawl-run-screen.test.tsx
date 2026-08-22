import { QueryClient } from '@tanstack/react-query';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { POLLING_INTERVALS } from '../../lib/constants/timing';
import { storeProductIntelligencePrefill } from './crawl-run-prefill';
import {
  apiMock,
  describeCrawlRunScreen,
  makeDomainRecipe,
  makeRecord,
  replaceMock,
  renderRunScreen,
  renderRunScreenWithClient,
  runningRun,
  terminalRun,
} from './crawl-run-screen.test-harness';

describeCrawlRunScreen(() => {
  it('prefills Product Intelligence from selected listing records', async () => {
    apiMock.getCrawl.mockResolvedValue({
      ...terminalRun(101),
      surface: 'ecommerce_listing',
      url: 'https://www.belk.com/category',
      settings: { crawl_module: 'category', crawl_mode: 'single' },
    });
    apiMock.getRecords.mockResolvedValue({
      items: [
        {
          ...makeRecord(1),
          source_url: 'https://www.belk.com/p/1',
          data: {
            brand: "Levi's",
            title: '511 Jeans',
            price: '$59.99',
            url: 'https://www.belk.com/p/1',
          },
        },
      ],
      meta: { page: 1, limit: 100, total: 1 },
    });

    renderRunScreen();

    const productButton = await screen.findByRole(
      'button',
      { name: 'Product Intelligence (1)' },
      { timeout: 5000 },
    );
    fireEvent.click(productButton);

    expect(replaceMock).toHaveBeenCalledWith('/product-intelligence');
    expect(
      JSON.parse(window.sessionStorage.getItem('product-intelligence-prefill-v1') || '{}'),
    ).toEqual({
      source_run_id: 101,
      source_domain: 'https://www.belk.com/category',
      records: [
        {
          id: 1,
          run_id: 101,
          source_url: 'https://www.belk.com/p/1',
          data: {
            brand: "Levi's",
            title: '511 Jeans',
            price: '$59.99',
            url: 'https://www.belk.com/p/1',
          },
        },
      ],
    });
  });

  it('prefills Product Intelligence from selected detail records', async () => {
    apiMock.getCrawl.mockResolvedValue({
      ...terminalRun(101),
      surface: 'ecommerce_detail',
      url: 'https://www.belk.com/p/levi-s-511-slim-fit-stretch-jeans/32009271204401.html',
      settings: { crawl_module: 'pdp', crawl_mode: 'single' },
    });
    apiMock.getRecords.mockResolvedValue({
      items: [
        {
          ...makeRecord(1),
          source_url:
            'https://www.belk.com/p/levi-s-511-slim-fit-stretch-jeans/32009271204401.html',
          data: {
            brand: "Levi's",
            title: '511 Slim Fit Stretch Jeans',
            price: '$59.99',
            sku_upc: '00194500874886',
            barcode: '00194500874886',
            product_id: '32009271204401',
            url: 'https://www.belk.com/p/levi-s-511-slim-fit-stretch-jeans/32009271204401.html',
          },
        },
      ],
      meta: { page: 1, limit: 100, total: 1 },
    });

    renderRunScreen();

    const productButton = await screen.findByRole(
      'button',
      { name: 'Product Intelligence (1)' },
      { timeout: 5000 },
    );
    fireEvent.click(productButton);

    expect(replaceMock).toHaveBeenCalledWith('/product-intelligence');
    expect(
      JSON.parse(window.sessionStorage.getItem('product-intelligence-prefill-v1') || '{}'),
    ).toMatchObject({
      source_run_id: 101,
      source_domain: 'https://www.belk.com/p/levi-s-511-slim-fit-stretch-jeans/32009271204401.html',
      records: [
        {
          id: 1,
          run_id: 101,
          data: {
            sku_upc: '00194500874886',
            barcode: '00194500874886',
            product_id: '32009271204401',
          },
        },
      ],
    });
  });

  it('falls back to reduced Product Intelligence prefill when session storage is full', () => {
    const stored = new Map<string, string>();
    const setItemMock = vi.fn((key: string, value: string) => {
      stored.set(key, value);
    });
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    setItemMock.mockImplementationOnce(() => {
      throw new DOMException('Quota exceeded', 'QuotaExceededError');
    });
    const storage = {
      setItem: setItemMock,
      getItem: (key: string) => stored.get(key) ?? null,
      removeItem: (key: string) => {
        stored.delete(key);
      },
    } as unknown as Storage;
    try {
      storeProductIntelligencePrefill(
        {
          source_run_id: 101,
          source_domain: 'https://www.belk.com/category',
          records: [
            {
              id: 1,
              run_id: 101,
              source_url: 'https://www.belk.com/p/1',
              data: {
                brand: "Levi's",
                title: '511 Jeans',
                price: '$59.99',
                url: 'https://www.belk.com/p/1',
              },
            },
          ],
        },
        storage,
      );

      expect(consoleSpy).toHaveBeenCalled();
      expect(JSON.parse(storage.getItem('product-intelligence-prefill-v1') || '{}')).toEqual({
        source_run_id: 101,
        source_domain: 'https://www.belk.com/category',
        records: [
          {
            id: 1,
            run_id: 101,
            source_url: 'https://www.belk.com/p/1',
            data: {},
          },
        ],
      });
    } finally {
      consoleSpy.mockRestore();
    }
  });

  it('reports when no reusable cookie state was observed for a browser run', async () => {
    apiMock.getDomainRecipe.mockResolvedValue({
      ...makeDomainRecipe(),
      acquisition_evidence: {
        ...makeDomainRecipe().acquisition_evidence,
        cookie_memory_available: false,
      },
    });

    renderRunScreen();

    const learningButtons = await screen.findAllByRole('button', { name: 'Learning' });
    fireEvent.click(learningButtons.at(-1)!);

    expect(
      await screen.findByText(/Cookie Memory: No reusable state observed/i),
    ).toBeInTheDocument();
  });

  it('renders completed summary chips from persisted backend values', async () => {
    apiMock.getCrawl.mockResolvedValue({
      ...terminalRun(101),
      result_summary: {
        extraction_verdict: 'success',
        record_count: 2,
        duration_ms: 65_000,
        quality_summary: {
          level: 'high',
        },
      },
    });
    apiMock.getRecords.mockResolvedValue({
      items: [],
      meta: { page: 1, limit: 100, total: 0 },
    });

    renderRunScreen();

    expect(await screen.findByText('1m 5s')).toBeInTheDocument();
    expect(screen.getByText('success')).toBeInTheDocument();
    expect(screen.getByText('high')).toBeInTheDocument();
  });

  it('keeps completed runs in the terminal workspace even without records', async () => {
    apiMock.getRecords.mockResolvedValue({
      items: [],
      meta: { page: 1, limit: 100, total: 0 },
    });

    renderRunScreen();

    expect(await screen.findByRole('button', { name: 'Excel (CSV)' })).toBeInTheDocument();
  });

  it('keeps the live workspace visible when summary counts are zero', async () => {
    apiMock.getCrawl.mockResolvedValue(runningRun(101));
    apiMock.getRecords.mockResolvedValue({
      items: [makeRecord(1), makeRecord(2)],
      meta: { page: 1, limit: 100, total: 2 },
    });

    renderRunScreen();

    await screen.findByText('Live Log Stream');
    expect(screen.getByRole('button', { name: 'Hard Kill' })).toBeInTheDocument();
    expect(screen.getByText('activity_stream.log')).toBeInTheDocument();
  });

  it('supports progressive table loading for large result sets', async () => {
    apiMock.getRecords.mockImplementation(
      (_runId: number, params?: { page?: number; limit?: number }) => {
        const page = Math.max(1, params?.page ?? 1);
        const limit = params?.limit ?? 100;
        const total = 150;
        const start = (page - 1) * limit;
        const count = Math.max(0, Math.min(limit, total - start));
        return Promise.resolve({
          items: Array.from({ length: count }, (_, index) => makeRecord(start + index + 1)),
          meta: { page, limit, total },
        });
      },
    );

    renderRunScreen();
    await waitFor(() => {
      expect(apiMock.getRecords).toHaveBeenCalledWith(101, { page: 1, limit: 100 });
    });

    const loadMoreButton = await screen.findByRole('button', { name: 'Load More' });
    fireEvent.click(loadMoreButton);

    await waitFor(() => {
      expect(apiMock.getRecords).toHaveBeenCalledWith(101, { page: 1, limit: 200 });
    });

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'Load More' })).not.toBeInTheDocument();
    });
  });

  it('shows recoverable panel refresh errors when records polling fails', async () => {
    apiMock.getRecords.mockRejectedValueOnce(new Error('records fetch failed'));

    renderRunScreen();

    expect(await screen.findByText('Some live panels failed to refresh')).toBeInTheDocument();
    expect(
      await screen.findByText(
        (content) =>
          content.includes('Unable to refresh') && content.includes('records fetch failed'),
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retry failed panels' })).toBeInTheDocument();
  });

  it('refetches table records on mount even if the cache contains a fresh empty page', async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          staleTime: 60_000,
        },
      },
    });

    queryClient.setQueryData(['crawl-run', 101], terminalRun(101));
    queryClient.setQueryData(['crawl-records-table', 101, 1], {
      items: [],
      meta: { page: 1, limit: 100, total: 0 },
    });

    apiMock.getRecords.mockResolvedValue({
      items: [makeRecord(1), makeRecord(2)],
      meta: { page: 1, limit: 100, total: 2 },
    });

    renderRunScreenWithClient(queryClient);

    await waitFor(() => {
      expect(apiMock.getRecords).toHaveBeenCalledWith(101, { page: 1, limit: 100 });
    });

    await waitFor(() => {
      expect(screen.getByText('Item 1')).toBeInTheDocument();
    });
  });

  it('keeps cached latest-run table rows visible when reopening from history', async () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          staleTime: 60_000,
        },
      },
    });

    const cachedRows = {
      items: [makeRecord(1), makeRecord(2)],
      meta: { page: 1, limit: 100, total: 2 },
    };

    queryClient.setQueryData(['crawl-run', 101], terminalRun(101));
    queryClient.setQueryData(['crawl-records-table', 101, 1], cachedRows);

    apiMock.getRecords.mockResolvedValue(cachedRows);

    renderRunScreenWithClient(queryClient);

    expect(await screen.findByText('Item 1')).toBeInTheDocument();

    await waitFor(() => {
      expect(apiMock.getRecords).toHaveBeenCalledWith(101, { page: 1, limit: 100 });
    });
  });

  it('refetches recent completed runs when summary records are present but the first table fetch is empty', async () => {
    const completedAt = new Date().toISOString();
    apiMock.getCrawl.mockResolvedValue({
      ...terminalRun(101),
      updated_at: completedAt,
      completed_at: completedAt,
      result_summary: {
        extraction_verdict: 'success',
        record_count: 2,
      },
    });

    let callCount = 0;
    apiMock.getRecords.mockImplementation(
      (_runId: number, params?: { page?: number; limit?: number }) => {
        callCount += 1;
        const limit = params?.limit ?? 100;
        if (callCount === 1) {
          return Promise.resolve({
            items: [],
            meta: { page: 1, limit, total: 0 },
          });
        }
        return Promise.resolve({
          items: [makeRecord(1), makeRecord(2)],
          meta: { page: 1, limit, total: 2 },
        });
      },
    );

    renderRunScreen();

    await waitFor(() => {
      expect(apiMock.getRecords).toHaveBeenCalledWith(101, { page: 1, limit: 100 });
    });

    await new Promise((resolve) => window.setTimeout(resolve, POLLING_INTERVALS.RECORDS_MS + 100));

    await waitFor(() => {
      expect(apiMock.getRecords.mock.calls.length).toBeGreaterThanOrEqual(2);
    });

    await waitFor(() => {
      expect(screen.getByText('Item 1')).toBeInTheDocument();
    });
  });

  it('retries both table and JSON record queries during terminal reconciliation', async () => {
    apiMock.getCrawl.mockResolvedValue({
      ...terminalRun(101),
      updated_at: '2026-04-08T10:05:00Z',
      completed_at: '2026-04-08T10:05:00Z',
      result_summary: {
        extraction_verdict: 'success',
        record_count: 2,
      },
    });

    let tableCalls = 0;
    let jsonCalls = 0;
    apiMock.getRecords.mockImplementation(
      (_runId: number, params?: { page?: number; limit?: number }) => {
        const limit = params?.limit ?? 100;
        if (params?.page === 1) {
          tableCalls += 1;
          return tableCalls === 1
            ? { items: [], meta: { page: 1, limit, total: 0 } }
            : { items: [makeRecord(1), makeRecord(2)], meta: { page: 1, limit, total: 2 } };
        }
        jsonCalls += 1;
        return jsonCalls === 1
          ? { items: [], meta: { page: 1, limit, total: 0 } }
          : { items: [makeRecord(1), makeRecord(2)], meta: { page: 1, limit, total: 2 } };
      },
    );

    renderRunScreen();

    await waitFor(() => {
      expect(apiMock.getRecords.mock.calls).toEqual(
        expect.arrayContaining([
          [101, { page: 1, limit: 100 }],
          [101, { limit: 100 }],
        ]),
      );
    });

    await new Promise((resolve) => window.setTimeout(resolve, POLLING_INTERVALS.RECORDS_MS + 100));

    await waitFor(() => {
      expect(tableCalls).toBeGreaterThanOrEqual(2);
      expect(jsonCalls).toBeGreaterThanOrEqual(2);
    });
  });

  it('reconciles older completed runs when the first table fetch is empty but records are expected', async () => {
    apiMock.getCrawl.mockResolvedValue({
      ...terminalRun(101),
      updated_at: '2026-04-08T10:05:00Z',
      completed_at: '2026-04-08T10:05:00Z',
      result_summary: {
        extraction_verdict: 'success',
        record_count: 2,
      },
    });

    let callCount = 0;
    apiMock.getRecords.mockImplementation(
      (_runId: number, params?: { page?: number; limit?: number }) => {
        callCount += 1;
        const limit = params?.limit ?? 100;
        if (callCount === 1) {
          return Promise.resolve({
            items: [],
            meta: { page: 1, limit, total: 0 },
          });
        }
        return Promise.resolve({
          items: [makeRecord(1), makeRecord(2)],
          meta: { page: 1, limit, total: 2 },
        });
      },
    );

    renderRunScreen();

    await waitFor(() => {
      expect(apiMock.getRecords).toHaveBeenCalledWith(101, { page: 1, limit: 100 });
    });

    await new Promise((resolve) => window.setTimeout(resolve, POLLING_INTERVALS.RECORDS_MS + 100));

    await waitFor(() => {
      expect(apiMock.getRecords.mock.calls.length).toBeGreaterThanOrEqual(2);
    });

    await waitFor(() => {
      expect(screen.getByText('Item 1')).toBeInTheDocument();
    });
  });
});
