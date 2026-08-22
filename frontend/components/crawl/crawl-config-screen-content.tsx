'use client';
import { Globe, Info, Plus, SlidersHorizontal, Sparkles } from 'lucide-react';
import { cn } from '../../lib/utils';
import { InlineAlert, TabBar } from '../ui/patterns';
import { Badge, Button, Dropdown, Card, Input, Textarea, Toggle, Tooltip } from '../ui/primitives';
import type { CrawlDomain } from '../../lib/api/types';
import { CRAWL_DEFAULTS, CRAWL_LIMITS } from '../../lib/constants/crawl-defaults';
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
  CAPTURE_NETWORK_OPTIONS,
  EXTRACTION_SOURCE_OPTIONS,
  FETCH_MODE_OPTIONS,
  JS_MODE_OPTIONS,
  parseOptionalClampedNumber,
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
import { CrawlActionButtons } from './crawl-action-buttons';
import {
  ADVANCED_COLUMN_CLASS,
  ADVANCED_CONTROL_ROW_CLASS,
  ADVANCED_SECTION_TITLE_CLASS,
  ADVANCED_SUBSECTION_CLASS,
  RUN_SETUP_CONTROL_CLASS,
  RUN_SETUP_LABEL_CLASS,
  RUN_SETUP_ROW_CLASS,
} from './crawl-config-state';
import { DOMAIN_OPTIONS } from './domain-surface-config';
import type { CrawlConfigScreenModel } from './crawl-config-screen';
import { AdvancedSettings, FieldConfiguration } from './crawl-config-advanced';

export function CrawlConfigScreenContent({ model }: { model: CrawlConfigScreenModel }) {
  const { handleSubmit, startCrawl, configError } = model;
  return (
    <div className="page-stack gap-4">
      <form
        className="grid gap-5 xl:grid-cols-[minmax(0,1.45fr)_380px] xl:items-stretch"
        onSubmit={(event) => void handleSubmit(startCrawl)(event)}
      >
        <CrawlTargetCard model={model} />

        <CrawlSettingsCard model={model} />

        <FieldConfiguration model={model} />

        {configError ? (
          <div className="xl:col-span-2">
            <InlineAlert message={configError} />
          </div>
        ) : null}

        <AdvancedSettings model={model} />
      </form>
    </div>
  );
}
function CrawlTargetCard({ model }: { model: CrawlConfigScreenModel }) {
  const {
    activeTabLabel,
    showSurfaceTabs,
    crawlTab,
    dispatchRoute,
    domainTabs,
    showModePicker,
    categoryMode,
    pdpMode,
    canSubmit,
    isSubmitting,
    bulkUrls,
    setValue,
    csvFile,
    localDispatch,
    activeMode,
    sitemapDomain,
    sitemapFilterKeyword,
    sitemapMaxUrls,
    targetUrl,
    savedProfileMessage,
    additionalDraft,
    additionalFields,
  } = model;
  return (
    <Card className="section-card overflow-hidden p-0">
      <header className="border-border flex h-10 items-center justify-between border-b bg-[color-mix(in_srgb,var(--bg-alt)_40%,var(--bg-panel))] px-6">
        <span className="type-heading-3">Target URL</span>
        <Badge tone="accent" className="h-5 px-1.5 text-xs font-medium">
          {activeTabLabel}
        </Badge>
      </header>
      <div className="space-y-5 px-6 pt-4 pb-6">
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-start">
          <div className="ml-[-4px] flex flex-wrap items-center gap-2.5">
            {showSurfaceTabs ? (
              <TabBar
                value={crawlTab}
                onChange={(value) => {
                  const parsed = parseRequestedCrawlTab(value);
                  if (parsed) {
                    dispatchRoute({ type: 'setTab', tab: parsed });
                  }
                }}
                options={domainTabs}
              />
            ) : null}
            {showModePicker ? (
              <div className="ml-[-4px] flex flex-wrap items-center gap-2.5">
                {crawlTab === 'category' ? (
                  <TabBar
                    value={categoryMode}
                    compact
                    onChange={(value) => {
                      const parsed = parseRequestedCategoryMode(value);
                      if (parsed) {
                        dispatchRoute({ type: 'setCategoryMode', mode: parsed });
                      }
                    }}
                    options={[
                      { value: 'single', label: 'Single' },
                      { value: 'sitemap', label: 'Sitemap' },
                      { value: 'bulk', label: 'Bulk' },
                    ]}
                  />
                ) : (
                  <TabBar
                    value={pdpMode}
                    compact
                    onChange={(value) => {
                      const parsed = parseRequestedPdpMode(value);
                      if (parsed) {
                        dispatchRoute({ type: 'setPdpMode', mode: parsed });
                      }
                    }}
                    options={[
                      { value: 'single', label: 'Single' },
                      { value: 'batch', label: 'Batch' },
                      { value: 'csv', label: 'CSV Upload' },
                    ]}
                  />
                )}
              </div>
            ) : null}
          </div>
          <CrawlActionButtons canSubmit={canSubmit} isSubmitting={isSubmitting} />
        </div>

        {(crawlTab === 'category' && categoryMode === 'bulk') ||
        (crawlTab === 'pdp' && pdpMode === 'batch') ? (
          <label className="grid gap-2">
            <span className="type-control font-medium">URLs (one per line)</span>
            <div className="relative">
              <Textarea
                value={bulkUrls}
                onChange={(event) => setValue('bulkUrls', event.target.value)}
                placeholder={'https://example.com/page-1\nhttps://example.com/page-2'}
                className="min-h-[420px] font-mono"
                aria-label="Bulk URLs input"
              />
              {bulkUrls.trim() ? (
                <div className="bg-background/80 text-foreground type-caption absolute right-2 bottom-2 rounded-sm px-2 py-1 backdrop-blur-sm">
                  {parseLines(bulkUrls).length} URLs
                </div>
              ) : null}
            </div>
          </label>
        ) : crawlTab === 'pdp' && pdpMode === 'csv' ? (
          <CsvFileField file={csvFile} onChange={localDispatch.setCsvFile} />
        ) : crawlTab === 'category' && activeMode === 'sitemap' ? (
          <SitemapConfigFields
            domain={sitemapDomain}
            filterKeyword={sitemapFilterKeyword}
            maxUrls={sitemapMaxUrls}
            onDomainChange={localDispatch.setSitemapDomain}
            onFilterKeywordChange={localDispatch.setSitemapFilterKeyword}
            onMaxUrlsChange={localDispatch.setSitemapMaxUrls}
          />
        ) : (
          <TargetUrlField
            value={targetUrl}
            onChange={(value) => setValue('targetUrl', value)}
            placeholder={
              crawlTab === 'category' ? 'https://example.com/list' : 'https://example.com/page'
            }
          />
        )}

        {savedProfileMessage ? (
          <div className="border-subtle-panel-border bg-subtle-panel text-secondary type-body rounded-md border px-3 py-2 leading-relaxed">
            {savedProfileMessage}
          </div>
        ) : null}

        <AdditionalFieldInput
          value={additionalDraft}
          fields={additionalFields}
          onChange={localDispatch.setAdditionalDraft}
          onCommit={(value) =>
            localDispatch.setAdditionalFields((current) =>
              uniqueRequestedFields([...current, value]),
            )
          }
          onRemove={(value) =>
            localDispatch.setAdditionalFields((current) =>
              current.filter((field) => field !== value),
            )
          }
        />
      </div>
    </Card>
  );
}

function CrawlSettingsCard({ model }: { model: CrawlConfigScreenModel }) {
  const {
    studioMode,
    crawlDomain,
    dispatchRoute,
    localDispatch,
    smartExtraction,
    proxyEnabled,
    proxyInput,
    setValue,
    singleUrlMode,
    savedProfileLoaded,
    savedProfileDomain,
    effectiveSurface,
  } = model;
  return (
    <div className="h-full xl:self-stretch">
      <div className="h-full xl:sticky xl:top-[68px]">
        <Card className="section-card h-full overflow-hidden p-0">
          <header className="border-border flex h-10 items-center justify-between border-b bg-[color-mix(in_srgb,var(--bg-alt)_40%,var(--bg-panel))] px-6">
            <span className="type-heading-3">Crawl Settings</span>
            <Badge tone="accent" className="h-5 px-1.5 text-xs font-medium">
              {studioMode === 'advanced' ? 'Advanced' : 'Quick'}
            </Badge>
          </header>
          <div className="page-stack px-6 pt-4 pb-6">
            <div className={RUN_SETUP_ROW_CLASS}>
              <div className={RUN_SETUP_LABEL_CLASS}>
                <Globe className="text-accent size-4 shrink-0" />
                <div className="type-body-sm text-foreground font-semibold">Domain</div>
              </div>
              <Dropdown<CrawlDomain>
                ariaLabel="Domain"
                value={crawlDomain}
                className={RUN_SETUP_CONTROL_CLASS}
                onChange={(value) => {
                  if (DOMAIN_OPTIONS.some((option) => option.value === value)) {
                    dispatchRoute({ type: 'setDomain', domain: value });
                  }
                }}
                options={DOMAIN_OPTIONS}
              />
            </div>
            <div className={RUN_SETUP_ROW_CLASS}>
              <div className={RUN_SETUP_LABEL_CLASS}>
                <SlidersHorizontal className="text-accent size-4 shrink-0" />
                <div className="flex items-center gap-1.5">
                  <div className="type-body-sm text-foreground font-semibold">Mode</div>
                  <Tooltip content="Advanced Mode exposes the full fetch, locality, diagnostics, and selector controls.">
                    <Info className="text-muted hover:text-secondary size-3.5 cursor-help transition-colors" />
                  </Tooltip>
                </div>
              </div>
              <TabBar
                value={studioMode}
                compact
                className={RUN_SETUP_CONTROL_CLASS}
                onChange={(value) => {
                  if (value === 'quick' || value === 'advanced') {
                    localDispatch.setStudioMode(value);
                  }
                }}
                options={[
                  { value: 'quick', label: 'Quick' },
                  { value: 'advanced', label: 'Advanced' },
                ]}
              />
            </div>

            <div className="flex h-[var(--control-height)] items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Sparkles className="text-accent size-4 shrink-0" />
                <span className="type-body-sm text-foreground font-semibold">LLM Processing</span>
                <Tooltip content="Per-run enrichment only. This does not overwrite saved domain defaults.">
                  <Info className="text-muted hover:text-secondary size-3.5 cursor-help transition-colors" />
                </Tooltip>
              </div>
              <Toggle
                checked={smartExtraction}
                onChange={localDispatch.setSmartExtraction}
                ariaLabel="LLM Processing"
              />
            </div>

            <div className="border-border border-t pt-4">
              <div className="flex h-[var(--control-height)] items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Globe className="text-accent size-4 shrink-0" />
                  <span className="type-body-sm text-foreground font-semibold">Proxy List</span>
                  <Tooltip content={'Example:\nhttp://host:port\nhttp://user:pass@host:port'}>
                    <Info className="text-muted hover:text-secondary size-3.5 cursor-help transition-colors" />
                  </Tooltip>
                </div>
                <Toggle
                  checked={proxyEnabled}
                  onChange={localDispatch.setProxyEnabled}
                  ariaLabel="Proxy List enabled"
                />
              </div>
            </div>

            {proxyEnabled ? (
              <div className="ml-8 flex flex-col gap-4">
                <div className="type-body-sm text-foreground font-semibold">Proxy URLs</div>
                <Textarea
                  value={proxyInput}
                  onChange={(event) => {
                    setValue('proxyInput', event.target.value);
                  }}
                  placeholder={'http://host:port\nhttp://user:pass@host:port'}
                  className="min-h-[104px] font-mono leading-relaxed"
                  aria-label="Proxy pool input"
                />
              </div>
            ) : null}

            {singleUrlMode && savedProfileLoaded ? (
              <div className="text-secondary type-body leading-relaxed">
                Saved domain profile active:{' '}
                <span className="type-label-mono text-foreground">{savedProfileDomain}</span> ·{' '}
                {surfaceLabel(effectiveSurface)}
              </div>
            ) : null}
          </div>
        </Card>
      </div>
    </div>
  );
}
