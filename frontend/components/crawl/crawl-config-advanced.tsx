'use client';
import { Info, Plus, SlidersHorizontal, Sparkles } from 'lucide-react';
import { cn } from '../../lib/utils';
import { InlineAlert } from '../ui/patterns';
import { Button, Card, Dropdown, Input, Tooltip } from '../ui/primitives';
import { CRAWL_DEFAULTS, CRAWL_LIMITS } from '../../lib/constants/crawl-defaults';
import {
  FieldEditorHeader,
  ManualFieldEditor,
  SettingSection,
  SliderRow,
} from './shared-components';
import { clampNumber, normalizeField } from './shared';
import {
  applyDiagnosticsPreset,
  BROWSER_ENGINE_OPTIONS,
  CAPTURE_NETWORK_OPTIONS,
  EXTRACTION_SOURCE_OPTIONS,
  FETCH_MODE_OPTIONS,
  JS_MODE_OPTIONS,
  parseOptionalClampedNumber,
  TRAVERSAL_MODE_OPTIONS,
  type BrowserEngine,
  type CaptureNetworkMode,
  type DiagnosticsPreset,
  type ExtractionSource,
  type FetchMode,
  type JsMode,
  type TraversalDropdownValue,
} from './crawl-config-logic';
import {
  ADVANCED_COLUMN_CLASS,
  ADVANCED_CONTROL_ROW_CLASS,
  ADVANCED_SECTION_TITLE_CLASS,
  ADVANCED_SUBSECTION_CLASS,
} from './crawl-config-state';
import type { CrawlConfigScreenModel } from './crawl-config-screen';

export function FieldConfiguration({ model }: { model: CrawlConfigScreenModel }) {
  const {
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
    localDispatch,
    activeFieldTestId,
    targetUrl,
    testFieldRow,
  } = model;
  if (model.studioMode !== 'advanced') return null;
  return (
    <Card className="section-card overflow-hidden p-0 xl:col-span-2">
      <header className="border-border flex h-10 items-center justify-between border-b bg-[color-mix(in_srgb,var(--bg-alt)_40%,var(--bg-panel))] px-6">
        <span className="type-heading-3">Field Configuration</span>
        <div className="flex items-center gap-2">
          <Button
            variant="quiet"
            type="button"
            size="sm"
            onClick={() => void generateFieldSelectors()}
            disabled={generatingSelectors}
          >
            <Sparkles className="size-3" />
            {generatingSelectors ? 'Generating...' : 'Generate'}
          </Button>
          <Button variant="quiet" type="button" size="sm" onClick={addManualField}>
            <Plus className="size-3" />
            New Field
          </Button>
          <Button
            variant="action"
            type="button"
            size="sm"
            onClick={() => void saveToDomainMemory()}
            disabled={
              savingDomainMemory ||
              !fieldRows.some(
                (row) =>
                  normalizeField(row.fieldName) &&
                  (row.cssSelector.trim() || row.xpath.trim() || row.regex.trim()),
              )
            }
          >
            {savingDomainMemory ? 'Saving...' : 'Save to Memory'}
          </Button>
        </div>
      </header>
      <div className="space-y-4 px-6 pt-6 pb-6">
        {fieldConfigMessage ? (
          <p className="text-success type-body leading-relaxed">{fieldConfigMessage}</p>
        ) : null}
        {fieldConfigError ? <InlineAlert message={fieldConfigError} /> : null}
        <div className="flex flex-col gap-2">
          {fieldRows.length ? (
            <>
              <FieldEditorHeader />
              {fieldRows.map((row) => (
                <ManualFieldEditor
                  key={row.id}
                  row={row}
                  showLabels={false}
                  message={fieldRowMessages[row.id]?.message}
                  messageTone={fieldRowMessages[row.id]?.tone}
                  onChange={(patch) => {
                    setFieldRows((current) =>
                      current.map((entry) =>
                        entry.id === row.id ? { ...entry, ...patch } : entry,
                      ),
                    );
                    localDispatch.setFieldRowMessages((current) => {
                      if (!current[row.id]) {
                        return current;
                      }
                      const next = { ...current };
                      delete next[row.id];
                      return next;
                    });
                  }}
                  onDelete={() => {
                    setFieldRows((current) => current.filter((entry) => entry.id !== row.id));
                    localDispatch.setFieldRowMessages((current) => {
                      if (!current[row.id]) {
                        return current;
                      }
                      const next = { ...current };
                      delete next[row.id];
                      return next;
                    });
                  }}
                  onTest={() => void testFieldRow(row)}
                  testing={activeFieldTestId === row.id}
                  testDisabled={
                    !targetUrl.trim() ||
                    (!row.cssSelector.trim() && !row.xpath.trim() && !row.regex.trim())
                  }
                />
              ))}
            </>
          ) : (
            <div className="surface-muted text-secondary type-body rounded-md border-dashed px-4 py-6 leading-relaxed">
              No selector rows yet.
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}

export function AdvancedSettings({ model }: { model: CrawlConfigScreenModel }) {
  const {
    runProfile,
    markProfileDirty,
    respectRobotsTxt,
    localDispatch,
    maxRecords,
    setValue,
    diagnosticsPreset,
  } = model;
  if (model.studioMode !== 'advanced') return null;
  return (
    <Card className="section-card overflow-visible p-0 xl:col-span-2">
      <header className="border-border flex h-10 items-center justify-between border-b bg-[color-mix(in_srgb,var(--bg-alt)_40%,var(--bg-panel))] px-6">
        <span className="type-heading-3 flex items-center gap-1.5">
          <SlidersHorizontal className="size-3.5" /> Advanced Settings
        </span>
        <Tooltip content="Fine-tune fetch, limits, locality, and diagnostics for this exploratory run.">
          <Info className="text-muted hover:text-secondary size-3.5 cursor-help transition-colors" />
        </Tooltip>
      </header>
      <div className="grid gap-0 p-6 xl:grid-cols-3 xl:divide-x xl:divide-[var(--border)]">
        <section className={cn(ADVANCED_COLUMN_CLASS, 'xl:pr-6')}>
          <div className={ADVANCED_SECTION_TITLE_CLASS}>
            <h3>Execution</h3>
            <Tooltip content="Control how the crawler fetches, renders, and traverses the target.">
              <Info className="text-muted hover:text-secondary size-3 cursor-help transition-colors" />
            </Tooltip>
          </div>
          <div className={ADVANCED_SUBSECTION_CLASS}>
            <div className={ADVANCED_CONTROL_ROW_CLASS}>
              <div className="type-body-sm text-foreground font-semibold">Fetch Mode</div>
              <Dropdown<FetchMode>
                ariaLabel="Fetch mode"
                value={runProfile.fetch_profile.fetch_mode}
                onChange={(next) => {
                  if (FETCH_MODE_OPTIONS.has(next)) {
                    markProfileDirty((current) => ({
                      ...current,
                      fetch_profile: {
                        ...current.fetch_profile,
                        fetch_mode: next,
                      },
                      acquisition_contract:
                        next === 'browser_only'
                          ? {
                              ...current.acquisition_contract,
                              prefer_browser: true,
                              prefer_curl_handoff: false,
                              handoff_cookie_engine: 'auto',
                            }
                          : current.acquisition_contract,
                    }));
                  }
                }}
                options={[
                  { value: 'auto', label: 'Auto' },
                  { value: 'http_only', label: 'HTTP Only' },
                  { value: 'browser_only', label: 'Browser Only' },
                  { value: 'http_then_browser', label: 'HTTP Then Browser' },
                ]}
              />
            </div>
            <div className={ADVANCED_CONTROL_ROW_CLASS}>
              <div className="type-body-sm text-foreground font-semibold">Browser Engine</div>
              <Dropdown<BrowserEngine>
                ariaLabel="Browser engine"
                value={runProfile.acquisition_contract.preferred_browser_engine}
                onChange={(next) => {
                  if (BROWSER_ENGINE_OPTIONS.has(next)) {
                    markProfileDirty((current) => ({
                      ...current,
                      acquisition_contract: {
                        ...current.acquisition_contract,
                        preferred_browser_engine: next,
                        prefer_browser: next === 'auto' ? false : true,
                        prefer_curl_handoff: false,
                        handoff_cookie_engine: next === 'auto' ? 'auto' : next,
                      },
                    }));
                  }
                }}
                options={[
                  { value: 'auto', label: 'Auto' },
                  { value: 'patchright', label: 'Patchright' },
                  { value: 'real_chrome', label: 'Real Chrome' },
                ]}
              />
            </div>
            <div className={ADVANCED_CONTROL_ROW_CLASS}>
              <div className="type-body-sm text-foreground font-semibold">Extraction</div>
              <Dropdown<ExtractionSource>
                ariaLabel="Extraction source"
                value={runProfile.fetch_profile.extraction_source}
                onChange={(next) => {
                  if (EXTRACTION_SOURCE_OPTIONS.has(next)) {
                    markProfileDirty((current) => ({
                      ...current,
                      fetch_profile: {
                        ...current.fetch_profile,
                        extraction_source: next,
                      },
                    }));
                  }
                }}
                options={[
                  { value: 'raw_html', label: 'Raw HTML' },
                  { value: 'rendered_dom', label: 'Rendered DOM' },
                  { value: 'rendered_dom_visual', label: 'Rendered + Visual' },
                  { value: 'network_payload_first', label: 'Network Payload First' },
                ]}
              />
            </div>
            <div className={ADVANCED_CONTROL_ROW_CLASS}>
              <div className="type-body-sm text-foreground font-semibold">JS Mode</div>
              <Dropdown<JsMode>
                ariaLabel="JavaScript mode"
                value={runProfile.fetch_profile.js_mode}
                onChange={(next) => {
                  if (JS_MODE_OPTIONS.has(next)) {
                    markProfileDirty((current) => ({
                      ...current,
                      fetch_profile: {
                        ...current.fetch_profile,
                        js_mode: next,
                      },
                    }));
                  }
                }}
                options={[
                  { value: 'auto', label: 'Auto' },
                  { value: 'enabled', label: 'Enabled' },
                  { value: 'disabled', label: 'Disabled' },
                ]}
              />
            </div>
            <div className={ADVANCED_CONTROL_ROW_CLASS}>
              <div className="type-body-sm text-foreground font-semibold">Traversal</div>
              <Dropdown<TraversalDropdownValue>
                ariaLabel="Traversal mode"
                value={runProfile.fetch_profile.traversal_mode ?? 'off'}
                onChange={(next) => {
                  if (next === 'off') {
                    markProfileDirty((current) => ({
                      ...current,
                      fetch_profile: {
                        ...current.fetch_profile,
                        traversal_mode: null,
                      },
                    }));
                    return;
                  }
                  if (TRAVERSAL_MODE_OPTIONS.has(next)) {
                    markProfileDirty((current) => ({
                      ...current,
                      fetch_profile: {
                        ...current.fetch_profile,
                        traversal_mode: next,
                      },
                    }));
                  }
                }}
                options={[
                  { value: 'off', label: 'Off' },
                  { value: 'paginate', label: 'Paginate' },
                  { value: 'scroll', label: 'Scroll' },
                  { value: 'load_more', label: 'Load More' },
                  { value: 'view_all', label: 'View All' },
                ]}
              />
            </div>
          </div>
          <div className={ADVANCED_SUBSECTION_CLASS}>
            <SettingSection
              label="Include iframes"
              description="Allow iframe content to participate in extraction and selector recovery."
              checked={runProfile.fetch_profile.include_iframes}
              onChange={(next) =>
                markProfileDirty((current) => ({
                  ...current,
                  fetch_profile: {
                    ...current.fetch_profile,
                    include_iframes: next,
                  },
                }))
              }
            />
            <SettingSection
              label="Respect robots.txt"
              description="Skip disallowed paths and honor crawl-delay."
              checked={respectRobotsTxt}
              onChange={localDispatch.setRespectRobotsTxt}
            />
          </div>
        </section>
        <section className={cn(ADVANCED_COLUMN_CLASS, 'xl:px-6')}>
          <div className={ADVANCED_SECTION_TITLE_CLASS}>
            <h3>Limits &amp; Locales</h3>
            <Tooltip content="Set repeat-run bounds and regional hints before dispatch.">
              <Info className="text-muted hover:text-secondary size-3 cursor-help transition-colors" />
            </Tooltip>
          </div>
          <div className={ADVANCED_SUBSECTION_CLASS}>
            <SliderRow
              label="Request Delay"
              description="Wait time between requests to the same target."
              value={String(runProfile.fetch_profile.request_delay_ms)}
              min={CRAWL_LIMITS.MIN_REQUEST_DELAY_MS}
              max={CRAWL_LIMITS.MAX_REQUEST_DELAY_MS}
              step={100}
              onChange={(next) =>
                markProfileDirty((current) => ({
                  ...current,
                  fetch_profile: {
                    ...current.fetch_profile,
                    request_delay_ms: clampNumber(
                      next,
                      CRAWL_LIMITS.MIN_REQUEST_DELAY_MS,
                      CRAWL_LIMITS.MAX_REQUEST_DELAY_MS,
                      CRAWL_DEFAULTS.REQUEST_DELAY_MS,
                    ),
                  },
                }))
              }
              onReset={() =>
                markProfileDirty((current) => ({
                  ...current,
                  fetch_profile: {
                    ...current.fetch_profile,
                    request_delay_ms: CRAWL_DEFAULTS.REQUEST_DELAY_MS,
                  },
                }))
              }
            />
            <SliderRow
              label="Max Records"
              description="Target record count. The crawler stops after a page reaches this target; it does not trim extra rows from that page."
              value={maxRecords}
              min={CRAWL_LIMITS.MIN_RECORDS}
              max={CRAWL_LIMITS.MAX_RECORDS}
              step={10}
              onChange={(value) => setValue('maxRecords', value)}
              onReset={() => setValue('maxRecords', String(CRAWL_DEFAULTS.MAX_RECORDS))}
            />
            <div className={ADVANCED_CONTROL_ROW_CLASS}>
              <div className="flex items-center gap-2">
                <div className="type-body-sm text-foreground font-semibold">Host Memory TTL</div>
                <Tooltip
                  content={`Blank uses default ${CRAWL_DEFAULTS.HOST_MEMORY_TTL_SECONDS}s. Lower TTL forgets host block and pacing memory sooner.`}
                >
                  <Info className="text-muted hover:text-secondary size-3 cursor-help transition-colors" />
                </Tooltip>
              </div>
              <Input
                type="number"
                min={CRAWL_LIMITS.MIN_HOST_MEMORY_TTL_SECONDS}
                max={CRAWL_LIMITS.MAX_HOST_MEMORY_TTL_SECONDS}
                placeholder={String(CRAWL_DEFAULTS.HOST_MEMORY_TTL_SECONDS)}
                value={runProfile.fetch_profile.host_memory_ttl_seconds ?? ''}
                onChange={(event) =>
                  markProfileDirty((current) => ({
                    ...current,
                    fetch_profile: {
                      ...current.fetch_profile,
                      host_memory_ttl_seconds: parseOptionalClampedNumber(
                        event.target.value,
                        CRAWL_LIMITS.MIN_HOST_MEMORY_TTL_SECONDS,
                        CRAWL_LIMITS.MAX_HOST_MEMORY_TTL_SECONDS,
                      ),
                    },
                  }))
                }
                aria-label="Host memory TTL seconds"
              />
            </div>
          </div>
          <div className={ADVANCED_SUBSECTION_CLASS}>
            <div className={ADVANCED_CONTROL_ROW_CLASS}>
              <div className="type-body-sm text-foreground font-semibold">Geo Country</div>
              <Input
                value={runProfile.locality_profile.geo_country}
                onChange={(event) =>
                  markProfileDirty((current) => ({
                    ...current,
                    locality_profile: {
                      ...current.locality_profile,
                      geo_country: event.target.value.trim() || 'auto',
                    },
                  }))
                }
                aria-label="Geo country"
              />
            </div>
            <div className={ADVANCED_CONTROL_ROW_CLASS}>
              <div className="type-body-sm text-foreground font-semibold">Language Hint</div>
              <Input
                value={runProfile.locality_profile.language_hint ?? ''}
                onChange={(event) =>
                  markProfileDirty((current) => ({
                    ...current,
                    locality_profile: {
                      ...current.locality_profile,
                      language_hint: event.target.value.trim() || null,
                    },
                  }))
                }
                aria-label="Language hint"
              />
            </div>
            <div className={ADVANCED_CONTROL_ROW_CLASS}>
              <div className="type-body-sm text-foreground font-semibold">Currency Hint</div>
              <Input
                value={runProfile.locality_profile.currency_hint ?? ''}
                onChange={(event) =>
                  markProfileDirty((current) => ({
                    ...current,
                    locality_profile: {
                      ...current.locality_profile,
                      currency_hint: event.target.value.trim() || null,
                    },
                  }))
                }
                aria-label="Currency hint"
              />
            </div>
          </div>
        </section>
        <section className={cn(ADVANCED_COLUMN_CLASS, 'xl:pl-6')}>
          <div className={ADVANCED_SECTION_TITLE_CLASS}>
            <h3>Output &amp; Diagnostics</h3>
            <Tooltip content="Choose what evidence and artifacts stay attached to this run.">
              <Info className="text-muted hover:text-secondary size-3 cursor-help transition-colors" />
            </Tooltip>
          </div>
          <div className={ADVANCED_SUBSECTION_CLASS}>
            <div className={ADVANCED_CONTROL_ROW_CLASS}>
              <div className="type-body-sm text-foreground font-semibold">Diagnostics</div>
              <Dropdown<DiagnosticsPreset>
                ariaLabel="Diagnostics preset"
                value={diagnosticsPreset}
                onChange={(next) => {
                  if (next === 'lean' || next === 'standard' || next === 'deep_debug') {
                    markProfileDirty((current) => applyDiagnosticsPreset(current, next));
                  }
                }}
                options={[
                  { value: 'lean', label: 'Lean' },
                  { value: 'standard', label: 'Standard' },
                  { value: 'deep_debug', label: 'Deep Debug' },
                ]}
              />
            </div>
            <div className={ADVANCED_CONTROL_ROW_CLASS}>
              <div className="type-body-sm text-foreground font-semibold">Network Capture</div>
              <Dropdown<CaptureNetworkMode>
                ariaLabel="Network capture"
                value={runProfile.diagnostics_profile.capture_network}
                onChange={(next) => {
                  if (CAPTURE_NETWORK_OPTIONS.has(next)) {
                    markProfileDirty((current) => ({
                      ...current,
                      diagnostics_profile: {
                        ...current.diagnostics_profile,
                        capture_network: next,
                      },
                    }));
                  }
                }}
                options={[
                  { value: 'off', label: 'Off' },
                  { value: 'matched_only', label: 'Matched Only' },
                  { value: 'all_small_json', label: 'All Small JSON' },
                ]}
              />
            </div>
          </div>
          <div className={ADVANCED_SUBSECTION_CLASS}>
            <SettingSection
              label="Capture HTML"
              description="Persist the page HTML artifact for this run."
              checked={runProfile.diagnostics_profile.capture_html}
              onChange={(next) =>
                markProfileDirty((current) => ({
                  ...current,
                  diagnostics_profile: {
                    ...current.diagnostics_profile,
                    capture_html: next,
                  },
                }))
              }
            />
            <SettingSection
              label="Capture Screenshot"
              description="Store browser screenshots when available."
              checked={runProfile.diagnostics_profile.capture_screenshot}
              onChange={(next) =>
                markProfileDirty((current) => ({
                  ...current,
                  diagnostics_profile: {
                    ...current.diagnostics_profile,
                    capture_screenshot: next,
                  },
                }))
              }
            />
            <SettingSection
              label="Capture Response Headers"
              description="Preserve response-header diagnostics."
              checked={runProfile.diagnostics_profile.capture_response_headers}
              onChange={(next) =>
                markProfileDirty((current) => ({
                  ...current,
                  diagnostics_profile: {
                    ...current.diagnostics_profile,
                    capture_response_headers: next,
                  },
                }))
              }
            />
            <SettingSection
              label="Capture Browser Diagnostics"
              description="Keep detailed browser-attempt diagnostics for debugging."
              checked={runProfile.diagnostics_profile.capture_browser_diagnostics}
              onChange={(next) =>
                markProfileDirty((current) => ({
                  ...current,
                  diagnostics_profile: {
                    ...current.diagnostics_profile,
                    capture_browser_diagnostics: next,
                  },
                }))
              }
            />
          </div>
        </section>
      </div>
    </Card>
  );
}
