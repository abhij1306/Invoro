'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { api } from '../../lib/api';
import type { PlaygroundSessionResponse } from '../../lib/api/types';
import {
  normalizeDiscoveredProducts,
  normalizePlaygroundResults,
  normalizeSitemap,
  playgroundStepIndex,
  sessionNeedsPolling,
  type PlaygroundSessionState,
} from './playground-normalizers';

const CATEGORY_LIMIT_MIN = 1;
const CATEGORY_LIMIT_MAX = 50;
const DEFAULT_PIPELINE_OPTIONS = {
  enrich: false,
  compare: false,
  monitor: false,
  audit: false,
};

export function clampCategoryLimit(value: number): number {
  if (!Number.isFinite(value)) return 10;
  return Math.min(CATEGORY_LIMIT_MAX, Math.max(CATEGORY_LIMIT_MIN, Math.trunc(value)));
}

export function parseUrlInput(value: string): string[] {
  return Array.from(
    new Set(
      value
        .split(/\r?\n/)
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  );
}

export function usePlaygroundWorkflow() {
  const queryClient = useQueryClient();
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [url, setUrl] = useState('');
  const [categoryLimit, setCategoryLimit] = useState(10);
  const [error, setError] = useState('');
  const [selectedUrls, setSelectedUrls] = useState<Set<string>>(new Set());
  const [pipelineOptions, setPipelineOptions] = useState(DEFAULT_PIPELINE_OPTIONS);
  const autoDiscoverFiredRef = useRef(false);
  const previousSelectionStageRef = useRef<string | undefined>(undefined);
  const sessionIdRef = useRef<number | null>(null);

  const sessionQuery = useQuery({
    queryKey: ['playground-session', sessionId],
    queryFn: () => api.getPlaygroundSession(sessionId!),
    enabled: sessionId !== null,
    refetchInterval: (query) => (sessionNeedsPolling(query.state.data) ? 3000 : false),
  });
  const session = sessionQuery.data as PlaygroundSessionResponse | undefined;
  const state = session?.state as PlaygroundSessionState | undefined;
  const hasResultsState =
    state === 'extracted' || state === 'running_pipeline' || state === 'complete';

  const resultsQuery = useQuery({
    queryKey: ['playground-results', sessionId],
    queryFn: () => api.playgroundResults(sessionId!),
    enabled: sessionId !== null && hasResultsState,
    refetchInterval: () => (sessionNeedsPolling(session) ? 3000 : false),
  });

  const invalidateSession = useCallback(
    () => queryClient.invalidateQueries({ queryKey: ['playground-session', sessionId] }),
    [queryClient, sessionId],
  );

  const createSession = useMutation({
    mutationFn: (inputUrl: string) => {
      const inputUrls = parseUrlInput(inputUrl);
      return api.createPlaygroundSession({
        url: inputUrls[0] ?? inputUrl,
        urls: inputUrls.slice(1),
        category_limit: clampCategoryLimit(categoryLimit),
      });
    },
    onSuccess: (data) => {
      sessionIdRef.current = data.id;
      autoDiscoverFiredRef.current = false;
      setSessionId(data.id);
      setError('');
    },
    onError: (err: Error) => setError(err.message),
  });

  const startDiscover = useMutation({
    mutationFn: (sid: number) => api.playgroundDiscover(sid),
    onSuccess: invalidateSession,
    onError: (err: Error) => setError(err.message),
  });

  const startExtract = useMutation({
    mutationFn: (sid: number) => api.playgroundExtract(sid),
    onSuccess: invalidateSession,
    onError: (err: Error) => setError(err.message),
  });

  const selectProducts = useMutation({
    mutationFn: ({ sid, urls }: { sid: number; urls: string[] }) =>
      api.playgroundSelect(sid, { urls }),
    onSuccess: (_data, variables) => {
      if (sessionIdRef.current !== variables.sid) return;
      void invalidateSession();
      startExtract.mutate(variables.sid);
    },
    onError: (err: Error) => setError(err.message),
  });

  const selectCategory = useMutation({
    mutationFn: ({ sid, categoryUrls }: { sid: number; categoryUrls: string[] }) =>
      api.playgroundSelectCategory(sid, { urls: categoryUrls }),
    onSuccess: invalidateSession,
    onError: (err: Error) => setError(err.message),
  });

  const runPipeline = useMutation({
    mutationFn: ({ sid, options }: { sid: number; options: typeof pipelineOptions }) =>
      api.playgroundPipeline(sid, options),
    onSuccess: invalidateSession,
    onError: (err: Error) => setError(err.message),
  });

  useEffect(() => {
    if (state !== 'created' || sessionId === null || autoDiscoverFiredRef.current) return;
    autoDiscoverFiredRef.current = true;
    startDiscover.mutate(sessionId);
  }, [sessionId, startDiscover, state]);

  useEffect(() => {
    if (state === previousSelectionStageRef.current) return;
    previousSelectionStageRef.current = state;
    if (state === 'sitemap_listed' || state === 'discovered') {
      setSelectedUrls(new Set());
    }
  }, [state]);

  const handleStart = useCallback(() => {
    const inputUrls = parseUrlInput(url);
    if (!inputUrls.length) return;
    setError('');
    createSession.mutate(inputUrls.join('\n'));
  }, [createSession, url]);

  const handleSelect = useCallback(() => {
    if (sessionId === null || selectedUrls.size === 0) return;
    selectProducts.mutate({ sid: sessionId, urls: Array.from(selectedUrls) });
  }, [selectProducts, selectedUrls, sessionId]);

  const handlePipeline = useCallback(() => {
    if (sessionId === null) return;
    runPipeline.mutate({ sid: sessionId, options: pipelineOptions });
  }, [pipelineOptions, runPipeline, sessionId]);

  const handleReset = useCallback(() => {
    setSessionId(null);
    setUrl('');
    setCategoryLimit(10);
    setError('');
    setSelectedUrls(new Set());
    setPipelineOptions(DEFAULT_PIPELINE_OPTIONS);
    sessionIdRef.current = null;
    autoDiscoverFiredRef.current = false;
    previousSelectionStageRef.current = undefined;
  }, []);

  const retryDiscover = useCallback(() => {
    if (sessionId === null) return;
    setError('');
    autoDiscoverFiredRef.current = true;
    startDiscover.mutate(sessionId);
  }, [sessionId, startDiscover]);

  const retryExtract = useCallback(() => {
    if (sessionId === null) return;
    setError('');
    startExtract.mutate(sessionId);
  }, [sessionId, startExtract]);

  const retryPipeline = useCallback(() => {
    if (sessionId === null) return;
    setError('');
    runPipeline.mutate({ sid: sessionId, options: pipelineOptions });
  }, [pipelineOptions, runPipeline, sessionId]);

  const discoveredProducts = useMemo(() => normalizeDiscoveredProducts(session), [session]);
  const sitemap = useMemo(() => normalizeSitemap(session), [session]);
  const normalizedResults = useMemo(
    () => normalizePlaygroundResults(resultsQuery.data),
    [resultsQuery.data],
  );
  const hasPipelineActivity = Boolean(
    session?.step_data?.enrich ||
    session?.step_data?.compare ||
    session?.step_data?.monitor ||
    session?.step_data?.audit,
  );

  const toggleProduct = useCallback((productUrl: string) => {
    setSelectedUrls((previous) => {
      const next = new Set(previous);
      if (next.has(productUrl)) next.delete(productUrl);
      else if (next.size < 50) next.add(productUrl);
      return next;
    });
  }, []);

  const toggleProducts = useCallback((productUrls: string[]) => {
    setSelectedUrls((previous) => {
      const next = new Set(previous);
      const allSelected = productUrls.every((productUrl) => next.has(productUrl));
      if (allSelected) {
        productUrls.forEach((productUrl) => next.delete(productUrl));
      } else {
        for (const productUrl of productUrls) {
          if (next.size >= 50 && !next.has(productUrl)) break;
          next.add(productUrl);
        }
      }
      return next;
    });
  }, []);

  const selectUrls = useCallback((productUrls: string[]) => {
    setSelectedUrls(new Set(productUrls.slice(0, 50)));
  }, []);

  const selectAll = useCallback(() => {
    setSelectedUrls(new Set(discoveredProducts.slice(0, 50).map((product) => product.url)));
  }, [discoveredProducts]);

  return {
    sessionId,
    session,
    state,
    currentStep: state ? playgroundStepIndex(state) : -1,
    url,
    setUrl,
    categoryLimit,
    setCategoryLimit: (value: number) => setCategoryLimit(clampCategoryLimit(value)),
    error,
    selectedUrls,
    setSelectedUrls,
    pipelineOptions,
    setPipelineOptions,
    sessionQuery,
    resultsQuery,
    createSession,
    startDiscover,
    selectProducts,
    selectCategory,
    startExtract,
    runPipeline,
    handleStart,
    handleSelect,
    handlePipeline,
    handleReset,
    retryDiscover,
    retryExtract,
    retryPipeline,
    discoveredProducts,
    sitemapUrls: sitemap.urls,
    sitemapSource: sitemap.sourceLabel,
    sitemapGroups: sitemap.groups,
    navTreeGroups: sitemap.navTreeGroups,
    resultsSteps: normalizedResults.steps,
    extractedRecords: normalizedResults.records,
    extractedRunIds: normalizedResults.runIds,
    hasPipelineActivity,
    toggleProduct,
    toggleProducts,
    selectUrls,
    selectAll,
  };
}
