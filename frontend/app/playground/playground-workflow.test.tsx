import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import { StrictMode, type PropsWithChildren } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { api } from '../../lib/api';
import type { PlaygroundSessionResponse } from '../../lib/api/types';
import {
  normalizeDiscoveredProducts,
  normalizePlaygroundResults,
  normalizeSitemap,
} from './playground-normalizers';
import { usePlaygroundWorkflow } from './use-playground-workflow';

vi.mock('../../lib/api', () => ({
  api: {
    createPlaygroundSession: vi.fn(),
    getPlaygroundSession: vi.fn(),
    playgroundDiscover: vi.fn(),
    playgroundSelect: vi.fn(),
    playgroundSelectCategory: vi.fn(),
    playgroundExtract: vi.fn(),
    playgroundPipeline: vi.fn(),
    playgroundResults: vi.fn(),
  },
}));

const apiMock = vi.mocked(api);

function session(
  state: PlaygroundSessionResponse['state'],
  stepData: Record<string, unknown> = {},
): PlaygroundSessionResponse {
  return {
    id: 17,
    input_url: 'https://example.com',
    state,
    step_data: stepData,
    created_at: '2026-06-24T00:00:00Z',
    updated_at: '2026-06-24T00:00:00Z',
  };
}

function wrapper() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return function Wrapper({ children }: PropsWithChildren) {
    return (
      <StrictMode>
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      </StrictMode>
    );
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  apiMock.playgroundDiscover.mockResolvedValue({
    session_id: 17,
    state: 'discovering',
    stage: 'sitemap',
    run_id: null,
    sitemap_url_count: null,
    message: 'started',
  });
  apiMock.playgroundExtract.mockResolvedValue({
    session_id: 17,
    state: 'extracting',
    run_ids: [101],
    url_count: 1,
  });
  apiMock.playgroundPipeline.mockResolvedValue({
    session_id: 17,
    state: 'running_pipeline',
    launched: {},
  });
  apiMock.playgroundResults.mockResolvedValue({ steps: {} });
});

describe('usePlaygroundWorkflow', () => {
  it('creates a session and automatically starts discovery exactly once in Strict Mode', async () => {
    apiMock.createPlaygroundSession.mockResolvedValue(session('created'));
    apiMock.getPlaygroundSession.mockResolvedValue(session('created'));

    const { result } = renderHook(() => usePlaygroundWorkflow(), { wrapper: wrapper() });

    act(() => {
      result.current.setUrl('https://example.com');
    });
    act(() => {
      result.current.handleStart();
    });

    await waitFor(() => {
      expect(apiMock.createPlaygroundSession).toHaveBeenCalledWith({
        url: 'https://example.com',
        urls: [],
        category_limit: 10,
      });
      expect(apiMock.playgroundDiscover).toHaveBeenCalledTimes(1);
      expect(apiMock.playgroundDiscover).toHaveBeenCalledWith(17);
    });
  });

  it('chains successful product selection into extraction with the same session', async () => {
    apiMock.createPlaygroundSession.mockResolvedValue(session('discovered'));
    apiMock.getPlaygroundSession.mockResolvedValue(session('discovered'));
    apiMock.playgroundSelect.mockResolvedValue(session('extracting'));

    const { result } = renderHook(() => usePlaygroundWorkflow(), { wrapper: wrapper() });
    act(() => result.current.setUrl('https://example.com'));
    act(() => result.current.handleStart());
    await waitFor(() => expect(result.current.sessionId).toBe(17));

    act(() => result.current.setSelectedUrls(new Set(['https://example.com/p/1'])));
    act(() => result.current.handleSelect());

    await waitFor(() => {
      expect(apiMock.playgroundSelect).toHaveBeenCalledWith(17, {
        urls: ['https://example.com/p/1'],
      });
      expect(apiMock.playgroundExtract).toHaveBeenCalledTimes(1);
      expect(apiMock.playgroundExtract).toHaveBeenCalledWith(17);
    });
  });

  it('surfaces discover failure, retries explicitly, and resets the workflow defaults', async () => {
    apiMock.createPlaygroundSession.mockResolvedValue(session('created'));
    apiMock.getPlaygroundSession.mockResolvedValue(session('created'));
    apiMock.playgroundDiscover
      .mockRejectedValueOnce(new Error('Discovery failed'))
      .mockResolvedValueOnce({
        session_id: 17,
        state: 'discovering',
        stage: 'sitemap',
        run_id: null,
        sitemap_url_count: null,
        message: 'started',
      });

    const { result } = renderHook(() => usePlaygroundWorkflow(), { wrapper: wrapper() });
    act(() => result.current.setUrl('https://example.com'));
    act(() => result.current.setCategoryLimit(25));
    act(() => result.current.handleStart());

    await waitFor(() => expect(result.current.error).toBe('Discovery failed'));
    act(() => result.current.retryDiscover());
    await waitFor(() => expect(apiMock.playgroundDiscover).toHaveBeenCalledTimes(2));

    act(() => result.current.handleReset());
    expect(result.current.sessionId).toBeNull();
    expect(result.current.url).toBe('');
    expect(result.current.categoryLimit).toBe(10);
    expect(result.current.selectedUrls.size).toBe(0);
    expect(result.current.pipelineOptions).toEqual({
      enrich: false,
      compare: false,
      monitor: false,
      audit: false,
    });
  });

  it('allows session creation to be retried after failure', async () => {
    apiMock.createPlaygroundSession
      .mockRejectedValueOnce(new Error('Create failed'))
      .mockResolvedValueOnce(session('discovered'));
    apiMock.getPlaygroundSession.mockResolvedValue(session('discovered'));

    const { result } = renderHook(() => usePlaygroundWorkflow(), { wrapper: wrapper() });
    act(() => result.current.setUrl('https://example.com'));
    act(() => result.current.handleStart());
    await waitFor(() => expect(result.current.error).toBe('Create failed'));

    act(() => result.current.handleStart());
    await waitFor(() => {
      expect(apiMock.createPlaygroundSession).toHaveBeenCalledTimes(2);
      expect(result.current.sessionId).toBe(17);
      expect(result.current.error).toBe('');
    });
  });

  it('does not extract after failed selection and retries through the same action', async () => {
    apiMock.createPlaygroundSession.mockResolvedValue(session('discovered'));
    apiMock.getPlaygroundSession.mockResolvedValue(session('discovered'));
    apiMock.playgroundSelect
      .mockRejectedValueOnce(new Error('Selection failed'))
      .mockResolvedValueOnce(session('extracting'));

    const { result } = renderHook(() => usePlaygroundWorkflow(), { wrapper: wrapper() });
    act(() => result.current.setUrl('https://example.com'));
    act(() => result.current.handleStart());
    await waitFor(() => expect(result.current.sessionId).toBe(17));
    act(() => result.current.setSelectedUrls(new Set(['https://example.com/p/1'])));

    act(() => result.current.handleSelect());
    await waitFor(() => expect(result.current.error).toBe('Selection failed'));
    expect(apiMock.playgroundExtract).not.toHaveBeenCalled();

    act(() => result.current.handleSelect());
    await waitFor(() => {
      expect(apiMock.playgroundSelect).toHaveBeenCalledTimes(2);
      expect(apiMock.playgroundExtract).toHaveBeenCalledTimes(1);
    });
  });

  it('surfaces extraction failure and retries without repeating selection', async () => {
    apiMock.createPlaygroundSession.mockResolvedValue(session('discovered'));
    apiMock.getPlaygroundSession.mockResolvedValue(session('discovered'));
    apiMock.playgroundSelect.mockResolvedValue(session('extracting'));
    apiMock.playgroundExtract
      .mockRejectedValueOnce(new Error('Extraction failed'))
      .mockResolvedValueOnce({
        session_id: 17,
        state: 'extracting',
        run_ids: [101],
        url_count: 1,
      });

    const { result } = renderHook(() => usePlaygroundWorkflow(), { wrapper: wrapper() });
    act(() => result.current.setUrl('https://example.com'));
    act(() => result.current.handleStart());
    await waitFor(() => expect(result.current.sessionId).toBe(17));
    act(() => result.current.setSelectedUrls(new Set(['https://example.com/p/1'])));
    act(() => result.current.handleSelect());

    await waitFor(() => expect(result.current.error).toBe('Extraction failed'));
    act(() => result.current.retryExtract());
    await waitFor(() => {
      expect(apiMock.playgroundSelect).toHaveBeenCalledTimes(1);
      expect(apiMock.playgroundExtract).toHaveBeenCalledTimes(2);
    });
  });

  it('preserves optional pipeline options and retries pipeline failure', async () => {
    apiMock.createPlaygroundSession.mockResolvedValue(session('extracted'));
    apiMock.getPlaygroundSession.mockResolvedValue(session('extracted'));
    apiMock.playgroundPipeline
      .mockRejectedValueOnce(new Error('Pipeline failed'))
      .mockResolvedValueOnce({ session_id: 17, state: 'running_pipeline', launched: {} });

    const { result } = renderHook(() => usePlaygroundWorkflow(), { wrapper: wrapper() });
    act(() => result.current.setUrl('https://example.com'));
    act(() => result.current.handleStart());
    await waitFor(() => expect(result.current.sessionId).toBe(17));

    act(() => {
      result.current.setPipelineOptions({
        enrich: true,
        compare: false,
        monitor: true,
        audit: true,
      });
    });
    act(() => result.current.handlePipeline());
    await waitFor(() => expect(result.current.error).toBe('Pipeline failed'));

    act(() => result.current.retryPipeline());
    await waitFor(() => {
      expect(apiMock.playgroundPipeline).toHaveBeenLastCalledWith(17, {
        enrich: true,
        compare: false,
        monitor: true,
        audit: true,
      });
    });
  });
});

describe('Playground normalizers', () => {
  it('normalizes stable display fields and ignores malformed or unknown diagnostics', () => {
    const value = session('discovered', {
      discover: {
        products: [
          { url: 'https://example.com/p/1', title: 'One', unknown: { future: true } },
          null,
          ['invalid'],
        ],
      },
      sitemap: {
        source: 'rendered_site_links',
        urls: ['https://example.com/c/1', 4],
        groups: { 'https://example.com': ['https://example.com/c/1', null] },
        sources: { 'https://example.com': 'homepage' },
        trees: {
          'https://example.com': [
            {
              label: 'Category',
              children: [
                { label: 'Leaf', url: 'https://example.com/c/1', children: [] },
                { label: 5, children: [] },
              ],
            },
          ],
        },
        diagnostics: { open: ['anything'] },
      },
    });

    expect(normalizeDiscoveredProducts(value)).toEqual([
      { url: 'https://example.com/p/1', title: 'One' },
    ]);
    expect(normalizeSitemap(value)).toMatchObject({
      urls: ['https://example.com/c/1'],
      sourceLabel: 'rendered site links',
      groups: [
        {
          inputUrl: 'https://example.com',
          urls: ['https://example.com/c/1'],
          source: 'homepage',
        },
      ],
    });
  });

  it('normalizes terminal extracted records and run IDs', () => {
    expect(
      normalizePlaygroundResults({
        steps: {
          extract: {
            records: [
              {
                id: 1,
                run_id: 101,
                source_url: 'https://example.com/p/1',
                data: { title: 'One' },
              },
              { id: 'bad' },
            ],
            run_ids: [101, 'bad'],
            diagnostics: { unknown: true },
          },
        },
      }),
    ).toEqual({
      steps: {
        extract: {
          records: [
            {
              id: 1,
              run_id: 101,
              source_url: 'https://example.com/p/1',
              data: { title: 'One' },
            },
            { id: 'bad' },
          ],
          run_ids: [101, 'bad'],
          diagnostics: { unknown: true },
        },
      },
      records: [
        {
          id: 1,
          run_id: 101,
          source_url: 'https://example.com/p/1',
          data: { title: 'One' },
        },
      ],
      runIds: [101],
    });
  });
});
