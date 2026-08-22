'use client';
import { Globe, Info, Plus, SlidersHorizontal, Sparkles } from 'lucide-react';
import type { Route } from 'next';
import { useRouter } from 'next/navigation';
import { startTransition, useCallback, useEffect, useMemo, useReducer } from 'react';
import { cn } from '../../lib/utils';
import { InlineAlert, TabBar } from '../ui/patterns';
import { Badge, Button, Dropdown, Card, Input, Textarea, Toggle, Tooltip } from '../ui/primitives';
import { api } from '../../lib/api';
import type { CrawlConfig, CrawlDomain } from '../../lib/api/types';
import { CRAWL_DEFAULTS, CRAWL_LIMITS } from '../../lib/constants/crawl-defaults';
import { getNormalizedDomain } from '../../lib/format/domain';
import { telemetryErrorPayload, trackEvent } from '../../lib/telemetry/events';
import {
  AdditionalFieldInput,
  CsvFileField,
  FieldEditorHeader,
  ManualFieldEditor,
  SettingSection,
  SliderRow,
  SitemapConfigFields,
  TargetUrlField,
} from './shared-components';
import {
  clampNumber,
  deriveSurface,
  type FieldRow,
  type CategoryMode,
  type PdpMode,
  normalizeField,
  parseLines,
  parseRequestedCategoryMode,
  parseRequestedCrawlTab,
  parseRequestedPdpMode,
  uniqueRequestedFields,
} from './shared';
import {
  applyDiagnosticsPreset,
  BROWSER_ENGINE_OPTIONS,
  buildDispatch,
  buildFieldRowFromSuggestion,
  canPreview,
  CAPTURE_NETWORK_OPTIONS,
  diagnosticsPresetForProfile,
  EXTRACTION_SOURCE_OPTIONS,
  FETCH_MODE_OPTIONS,
  inferRunTypeHint,
  isSingleUrlMode,
  JS_MODE_OPTIONS,
  mergeFieldRows,
  normalizeHttpLookupDomain,
  parseOptionalClampedNumber,
  selectRelevantSelectorRecords,
  selectorGenerationFields,
  surfaceLabel,
  TRAVERSAL_MODE_OPTIONS,
  type BrowserEngine,
  type CaptureNetworkMode,
  type DiagnosticsPreset,
  type ExtractionSource,
  type FetchMode,
  type JsMode,
  type TraversalDropdownValue,
} from './crawl-config-logic';
import { resolveAutoSurface } from './auto-surface';
import { CrawlActionButtons } from './crawl-action-buttons';
import { testCrawlFieldRow } from './crawl-field-test';
import {
  ADVANCED_COLUMN_CLASS,
  ADVANCED_CONTROL_ROW_CLASS,
  ADVANCED_SECTION_TITLE_CLASS,
  ADVANCED_SUBSECTION_CLASS,
  bindCrawlConfigLocalDispatch,
  buildInitialLocalState,
  crawlConfigLocalReducer,
  RUN_SETUP_CONTROL_CLASS,
  RUN_SETUP_LABEL_CLASS,
  RUN_SETUP_ROW_CLASS,
  type CrawlConfigScreenProps,
  useCrawlRouteState,
} from './crawl-config-state';
import { DOMAIN_OPTIONS, DOMAIN_TABS } from './domain-surface-config';
import * as crawlConfigForm from './use-crawl-config';
import { useCrawlConfigLifecycle } from './use-crawl-config-lifecycle';
import { CrawlConfigScreenContent } from './crawl-config-screen-content';

function deriveCrawlRoutePresentation(
  crawlDomain: CrawlDomain,
  crawlTab: CrawlConfig['module'],
  categoryMode: CategoryMode,
  pdpMode: PdpMode,
  targetUrl: string,
) {
  const modePickerEnabled = crawlDomain === 'commerce' || crawlDomain === 'jobs';
  const selectedMode: CategoryMode | PdpMode = crawlTab === 'category' ? categoryMode : pdpMode;
  const activeMode: CategoryMode | PdpMode = modePickerEnabled ? selectedMode : 'single';
  const surface = deriveSurface(crawlDomain, crawlTab);
  const autoSurfaceResolution = surface === 'auto' ? resolveAutoSurface(targetUrl, crawlTab) : null;
  const effectiveSurface = autoSurfaceResolution?.surface ?? surface;
  const domainTabs = DOMAIN_TABS[crawlDomain];
  return {
    activeMode,
    surface,
    effectiveSurface,
    domainTabs,
    activeTabLabel:
      domainTabs.find((tab) => tab.value === crawlTab)?.label ?? surfaceLabel(surface),
    showSurfaceTabs: domainTabs.length > 1,
    showModePicker: modePickerEnabled,
    singleUrlMode: isSingleUrlMode(crawlTab, activeMode),
  };
}

function lookupKey(enabled: boolean, domain: string, surface: string) {
  return enabled && domain && surface ? `${domain}|${surface}` : '';
}

function hasCrawlTarget(
  crawlTab: CrawlConfig['module'],
  activeMode: CategoryMode | PdpMode,
  sitemapDomain: string,
  singleUrlMode: boolean,
  targetUrl: string,
  bulkUrls: string,
  csvFile: File | null,
) {
  if (crawlTab === 'category' && activeMode === 'sitemap') return sitemapDomain.trim().length > 0;
  if (singleUrlMode) return targetUrl.trim().length > 0;
  return bulkUrls.trim().length > 0 || csvFile !== null;
}

function useCrawlConfigScreenModel({
  requestedTab,
  requestedCategoryMode,
  requestedPdpMode,
}: Readonly<CrawlConfigScreenProps>) {
  const router = useRouter();
  const { routeState, dispatchRoute, bulkPrefillRouteSyncGuardRef } = useCrawlRouteState({
    requestedTab,
    requestedCategoryMode,
    requestedPdpMode,
  });
  const { crawlTab, crawlDomain, categoryMode, pdpMode } = routeState;
  const {
    handleSubmit,
    setValue,
    fieldRows,
    setFieldRows,
    targetUrl,
    bulkUrls,
    maxRecords,
    proxyInput,
    isSubmitting,
  } = crawlConfigForm.useCrawlConfig();
  const [localState, dispatchLocal] = useReducer(
    crawlConfigLocalReducer,
    undefined,
    buildInitialLocalState,
  );
  const {
    sitemapDomain,
    sitemapFilterKeyword,
    sitemapMaxUrls,
    csvFile,
    smartExtraction,
    studioMode,
    runProfile,
    respectRobotsTxt,
    proxyEnabled,
    savedProfileDomain,
    savedProfileLoaded,
    savedProfileMessage,
    additionalDraft,
    additionalFields,
    generatingSelectors,
    savingDomainMemory,
    fieldConfigMessage,
    fieldConfigError,
    fieldRowMessages,
    activeFieldTestId,
    configError,
  } = localState;
  const localDispatch = useMemo(() => bindCrawlConfigLocalDispatch(dispatchLocal), [dispatchLocal]);

  const {
    activeMode,
    surface,
    effectiveSurface,
    domainTabs,
    activeTabLabel,
    showSurfaceTabs,
    showModePicker,
    singleUrlMode,
  } = useMemo(
    () => deriveCrawlRoutePresentation(crawlDomain, crawlTab, categoryMode, pdpMode, targetUrl),
    [categoryMode, crawlDomain, crawlTab, pdpMode, targetUrl],
  );
  const normalizedTargetDomain = normalizeHttpLookupDomain(targetUrl);
  const profileLookupKey = lookupKey(singleUrlMode, normalizedTargetDomain, effectiveSurface);
  const domainMemoryLookupKey = lookupKey(singleUrlMode, normalizedTargetDomain, effectiveSurface);
  const diagnosticsPreset = diagnosticsPresetForProfile(runProfile);
  const setLifecycleBulkUrls = useCallback(
    (value: string) => setValue('bulkUrls', value),
    [setValue],
  );
  const { loadDomainMemoryForUrl, markProfileDirty } = useCrawlConfigLifecycle({
    profileLookupKey,
    domainMemoryLookupKey,
    targetUrl,
    normalizedTargetDomain,
    effectiveSurface,
    bulkPrefillRouteSyncGuardRef,
    dispatchRoute,
    localDispatch,
    setBulkUrls: setLifecycleBulkUrls,
    setFieldRows,
  });

  useEffect(() => {
    const routeMode = crawlTab === 'category' ? requestedCategoryMode : requestedPdpMode;
    if (
      bulkPrefillRouteSyncGuardRef.current ||
      (requestedTab === crawlTab && routeMode === activeMode)
    ) {
      return;
    }
    const nextUrl = `/crawl?module=${crawlTab}&mode=${activeMode}`;
    if (typeof window !== 'undefined') {
      const currentUrl = `${window.location.pathname}${window.location.search}`;
      if (currentUrl !== nextUrl) {
        window.history.replaceState(null, '', nextUrl);
      }
    }
  }, [
    activeMode,
    bulkPrefillRouteSyncGuardRef,
    crawlTab,
    requestedCategoryMode,
    requestedPdpMode,
    requestedTab,
  ]);

  useEffect(() => {
    if (bulkPrefillRouteSyncGuardRef.current && crawlTab === 'pdp' && pdpMode === 'batch') {
      bulkPrefillRouteSyncGuardRef.current = false;
    }
  }, [bulkPrefillRouteSyncGuardRef, crawlTab, pdpMode]);

  const config = useMemo<CrawlConfig>(
    () => ({
      module: crawlTab,
      domain: crawlDomain,
      mode: activeMode,
      target_url: targetUrl,
      bulk_urls: bulkUrls,
      sitemap_domain: activeMode === 'sitemap' ? sitemapDomain.trim() : undefined,
      sitemap_filter_keyword:
        activeMode === 'sitemap' ? sitemapFilterKeyword.trim() || 'collections' : undefined,
      sitemap_max_urls: activeMode === 'sitemap' ? sitemapMaxUrls : undefined,
      csv_file: csvFile,
      smart_extraction: smartExtraction,
      max_records: clampNumber(
        maxRecords,
        CRAWL_LIMITS.MIN_RECORDS,
        CRAWL_LIMITS.MAX_RECORDS,
        CRAWL_DEFAULTS.MAX_RECORDS,
      ),
      respect_robots_txt: respectRobotsTxt,
      proxy_enabled: proxyEnabled,
      proxy_lines: proxyEnabled ? parseLines(proxyInput) : [],
      additional_fields: additionalFields,
    }),
    [
      additionalFields,
      bulkUrls,
      activeMode,
      crawlDomain,
      crawlTab,
      csvFile,
      maxRecords,
      proxyEnabled,
      proxyInput,
      respectRobotsTxt,
      sitemapDomain,
      sitemapFilterKeyword,
      sitemapMaxUrls,
      smartExtraction,
      targetUrl,
    ],
  );

  async function startCrawl() {
    localDispatch.setConfigError('');
    try {
      const parsedConfig = crawlConfigForm.crawlConfigSchema.safeParse(
        crawlConfigForm.transformFormToSubmission({
          mode: config.mode,
          targetUrl: config.target_url,
          bulkUrls: config.bulk_urls,
          maxRecords,
        }),
      );
      if (!parsedConfig.success) {
        throw new Error(parsedConfig.error.issues[0]?.message ?? 'Unable to launch crawl.');
      }
      const dispatch = buildDispatch(config, fieldRows, {
        runProfile,
        studioMode,
      });
      if (studioMode === 'advanced') {
        trackEvent('advanced_mode_selected_vs_effective', {
          module: config.module,
          selected_advanced_mode: runProfile.fetch_profile.traversal_mode,
          effective_advanced_mode: dispatch.settings.advanced_mode ?? null,
        });
      }
      let response: { run_id: number };
      if (dispatch.runType === 'csv') {
        if (!dispatch.csvFile) {
          throw new Error('CSV file is missing.');
        }
        response = await api.createCsvCrawl({
          file: dispatch.csvFile,
          surface: dispatch.surface,
          additionalFields: dispatch.additionalFields,
          settings: dispatch.settings,
        });
      } else {
        response = await api.createCrawl({
          run_type: dispatch.runType,
          url: dispatch.url,
          urls: dispatch.urls,
          surface: dispatch.surface,
          settings: dispatch.settings,
          additional_fields: dispatch.additionalFields,
        });
      }
      startTransition(() => {
        router.replace(`/crawl?run_id=${response.run_id}` as Route);
        router.refresh();
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to launch crawl.';
      trackEvent(
        'crawl_submit_error_rate',
        telemetryErrorPayload(error, {
          module: config.module,
          mode: config.mode,
          surface,
          studio_mode: studioMode,
          smart_extraction: config.smart_extraction,
          run_type_hint: inferRunTypeHint(config),
        }),
      );
      localDispatch.setConfigError(message);
    }
  }

  function addManualField() {
    setFieldRows((current) => [
      ...current,
      {
        id: crawlConfigForm.createManualFieldRowId(),
        fieldName: '',
        cssSelector: '',
        xpath: '',
        regex: '',
        cssState: 'idle',
        xpathState: 'idle',
        regexState: 'idle',
      },
    ]);
  }

  async function generateFieldSelectors() {
    const target = targetUrl.trim();
    if (!target) {
      localDispatch.setFieldConfigError('Enter a target URL before generating selectors.');
      return;
    }
    const expectedColumns = selectorGenerationFields(effectiveSurface, fieldRows, additionalFields);
    if (!expectedColumns.length) {
      localDispatch.setFieldConfigError(
        'Add at least one field or additional field before generating selectors.',
      );
      return;
    }
    localDispatch.setGeneratingSelectors(true);
    localDispatch.setFieldConfigError('');
    try {
      const response = await api.suggestSelectors({
        url: target,
        expected_columns: expectedColumns,
        surface: effectiveSurface,
      });
      const incomingRows = expectedColumns.map((fieldName) =>
        buildFieldRowFromSuggestion(
          fieldName,
          response.suggestions[normalizeField(fieldName)]?.[0],
        ),
      );
      setFieldRows((current) => mergeFieldRows(current, incomingRows));
      localDispatch.setFieldRowMessages({});
      localDispatch.setFieldConfigMessage(
        `Generated selector suggestions for ${expectedColumns.length} field${expectedColumns.length === 1 ? '' : 's'}.`,
      );
    } catch (error) {
      localDispatch.setFieldConfigError(
        error instanceof Error ? error.message : 'Unable to generate selectors.',
      );
    } finally {
      localDispatch.setGeneratingSelectors(false);
    }
  }

  async function testFieldRow(row: FieldRow) {
    await testCrawlFieldRow({
      row,
      targetUrl,
      setActiveId: localDispatch.setActiveFieldTestId,
      setMessage: (rowId, tone, message) =>
        localDispatch.setFieldRowMessages((current) => ({
          ...current,
          [rowId]: { tone, message },
        })),
    });
  }

  async function saveToDomainMemory() {
    const target = targetUrl.trim();
    const domain = getNormalizedDomain(target);
    if (!target || !domain) {
      localDispatch.setFieldConfigError('Enter a target URL before saving domain memory.');
      return;
    }
    const dedupedMap = new Map<string, FieldRow>();
    for (const row of fieldRows) {
      const field = normalizeField(row.fieldName);
      if (field && (row.cssSelector.trim() || row.xpath.trim() || row.regex.trim())) {
        dedupedMap.set(field, row);
      }
    }
    const dedupedRows = Array.from(dedupedMap.values());
    if (!dedupedRows.length) {
      localDispatch.setFieldConfigError(
        'Add at least one selector row before saving domain memory.',
      );
      return;
    }
    localDispatch.setSavingDomainMemory(true);
    localDispatch.setFieldConfigError('');
    try {
      const existingRecords = selectRelevantSelectorRecords(
        await api.listSelectors({ domain }),
        effectiveSurface,
      );
      const existingByField = new Map(
        existingRecords.map((record) => [normalizeField(record.field_name), record] as const),
      );
      const settled = await Promise.allSettled(
        dedupedRows.map(async (row) => {
          const fieldName = normalizeField(row.fieldName);
          const payload = {
            field_name: fieldName,
            css_selector: row.cssSelector.trim() || undefined,
            xpath: row.xpath.trim() || undefined,
            regex: row.regex.trim() || undefined,
            source: 'crawl_config',
            status: 'validated' as const,
            is_active: true,
          };
          const existing = existingByField.get(fieldName);
          if (existing) {
            await api.updateSelector(existing.id, payload);
            return;
          }
          await api.createSelector({
            domain,
            surface: effectiveSurface,
            ...payload,
          });
        }),
      );
      const failedCount = settled.filter((result) => result.status === 'rejected').length;
      const savedCount = settled.length - failedCount;
      if (failedCount) {
        localDispatch.setFieldConfigError(
          `Saved ${savedCount} selector${savedCount === 1 ? '' : 's'}, ${failedCount} failed.`,
        );
      } else {
        localDispatch.setFieldConfigMessage(
          `Saved ${savedCount} selector${savedCount === 1 ? '' : 's'} to domain memory.`,
        );
      }
      if (savedCount) {
        await loadDomainMemoryForUrl(target);
      }
    } catch (error) {
      localDispatch.setFieldConfigError(
        error instanceof Error ? error.message : 'Unable to save domain memory.',
      );
    } finally {
      localDispatch.setSavingDomainMemory(false);
    }
  }
  const hasTarget = hasCrawlTarget(
    crawlTab,
    activeMode,
    sitemapDomain,
    singleUrlMode,
    targetUrl,
    bulkUrls,
    csvFile,
  );
  const canSubmit =
    hasTarget && canPreview(config, fieldRows, { runProfile, studioMode }) && !isSubmitting;
  return {
    crawlTab,
    activeMode,
    activeTabLabel,
    showSurfaceTabs,
    dispatchRoute,
    domainTabs,
    showModePicker,
    categoryMode,
    pdpMode,
    canSubmit,
    isSubmitting,
    handleSubmit,
    startCrawl,
    bulkUrls,
    setValue,
    csvFile,
    localDispatch,
    sitemapDomain,
    sitemapFilterKeyword,
    sitemapMaxUrls,
    targetUrl,
    savedProfileMessage,
    additionalDraft,
    additionalFields,
    crawlDomain,
    studioMode,
    smartExtraction,
    proxyEnabled,
    proxyInput,
    singleUrlMode,
    savedProfileLoaded,
    savedProfileDomain,
    effectiveSurface,
    generatingSelectors,
    generateFieldSelectors,
    addManualField,
    savingDomainMemory,
    saveToDomainMemory,
    fieldRows,
    fieldConfigMessage,
    fieldConfigError,
    fieldRowMessages,
    setFieldRows,
    activeFieldTestId,
    testFieldRow,
    configError,
    runProfile,
    markProfileDirty,
    respectRobotsTxt,
    maxRecords,
    diagnosticsPreset,
  };
}

export type CrawlConfigScreenModel = ReturnType<typeof useCrawlConfigScreenModel>;

export function CrawlConfigScreen(props: Readonly<CrawlConfigScreenProps>) {
  const model = useCrawlConfigScreenModel(props);
  return <CrawlConfigScreenContent model={model} />;
}
