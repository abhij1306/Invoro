'use client';

import { CheckCircle2, Code2, ExternalLink, ImageOff, Layers, ChevronDown } from 'lucide-react';

import { Badge, Button } from '../../components/ui/primitives';
import { cn } from '../../lib/utils';
import { ExternalCandidateImage } from './product-intelligence-components';
import type { ProductIntelligenceController } from './use-product-intelligence';
import {
  candidateConfidence,
  formatExtractedPrice,
  formatPrice,
  isRecord,
  stringField,
} from './product-intelligence-utils';
import type { CandidateGroup, ProductIntelligenceCandidate } from './product-intelligence-utils';

export function CandidateGroupSection({
  group,
  groupIndex,
  controller,
}: {
  group: CandidateGroup;
  groupIndex: number;
  controller: ProductIntelligenceController;
}) {
  return (
    <details className="group" open={groupIndex === 0}>
      <summary className="hover:bg-background-alt/50 flex cursor-pointer list-none items-center gap-4 px-4 py-3 transition-colors select-none">
        <div className="border-divider bg-background text-muted group-open:bg-accent group-open:border-accent type-caption-mono flex size-6 shrink-0 items-center justify-center rounded-full border font-normal group-open:!text-white">
          {group.candidates.length}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span
              className="text-foreground type-body truncate font-semibold"
              title={group.sourceTitle}
            >
              {group.sourceTitle}
            </span>
            <Badge tone="neutral" className="type-label-mono h-4 px-1.5 uppercase opacity-60">
              Source
            </Badge>
          </div>
          <div className="mt-0.5 flex items-center gap-3">
            {group.sourceBrand && group.sourceBrand !== '--' ? (
              <span className="text-muted type-caption flex items-center gap-1.5">
                <Layers className="size-3 opacity-50" />
                {group.sourceBrand}
              </span>
            ) : null}
            {group.sourceBrand && group.sourceBrand !== '--' && group.sourcePrice ? (
              <span className="bg-divider h-1 w-1 rounded-full" />
            ) : null}
            {group.sourcePrice ? (
              <span className="text-foreground type-caption-mono font-semibold">
                {formatPrice(group.sourcePrice, group.sourceCurrency)}
              </span>
            ) : null}
            {group.sourceUrl ? (
              <>
                <span className="bg-divider h-1 w-1 rounded-full" />
                <a
                  href={group.sourceUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="link-accent type-caption truncate"
                  title={group.sourceUrl}
                >
                  Source PDP
                </a>
              </>
            ) : null}
          </div>
        </div>
        <ChevronDown className="text-muted size-4 shrink-0 transition-transform group-open:rotate-180" />
      </summary>
      <div className="bg-background-alt/30 border-divider grid grid-cols-1 gap-3 border-t p-4 md:grid-cols-2 xl:grid-cols-3">
        {group.candidates.map((candidate) => (
          <CandidateCard key={candidate.url} candidate={candidate} controller={controller} />
        ))}
      </div>
    </details>
  );
}

function CandidateCard({
  candidate,
  controller,
}: {
  candidate: ProductIntelligenceCandidate;
  controller: ProductIntelligenceController;
}) {
  const selected = controller.uniqueSelectedUrls.includes(candidate.url);
  const score = candidateConfidence(candidate);
  const intelligence = isRecord(candidate.intelligence) ? candidate.intelligence : {};
  const record = isRecord(intelligence.canonical_record) ? intelligence.canonical_record : {};
  const imageUrl = stringField(record.image_url);
  const reasons = isRecord(intelligence.score_reasons) ? intelligence.score_reasons : {};
  const provider = providerLabel(candidate.payload, intelligence);
  const sourceType = sourceTypeLabel(candidate.source_type);
  const candidatePrice = record.price;
  const priceDelta = formatPriceDelta(candidate.source_price, candidatePrice);
  return (
    <div
      className={cn(
        'group/card border-border bg-panel hover:border-accent/40 relative flex flex-col rounded-[var(--radius-md)] border p-3 transition-all hover:shadow-md',
        selected && 'border-accent/60 bg-accent-subtle/20 shadow-sm',
      )}
    >
      <div className="flex gap-4">
        <CandidateImage imageUrl={imageUrl} title={stringField(record.title)} score={score} />
        <div className="flex min-w-0 flex-1 flex-col justify-between py-0.5">
          <div className="space-y-1.5">
            <div className="flex items-start justify-between gap-3">
              <a
                href={candidate.url}
                target="_blank"
                rel="noopener noreferrer"
                className="group/link text-foreground hover:text-accent type-body-sm line-clamp-2 font-medium transition-colors"
              >
                {stringField(record.title) || candidate.url}
              </a>
              <input
                type="checkbox"
                checked={selected}
                onChange={(event) => {
                  event.stopPropagation();
                  if (candidate.url) controller.toggleUrl(candidate.url);
                }}
                aria-label={`Select product for batch crawl: ${stringField(record.title) || candidate.url}`}
                className="border-divider text-accent focus:ring-accent mt-0.5 h-4 w-4 shrink-0 cursor-pointer rounded"
              />
            </div>
            <div className="flex flex-col gap-1">
              {stringField(record.price) && stringField(record.price) !== '--' ? (
                <div className="text-foreground type-body-sm font-semibold">
                  {formatExtractedPrice(record.price, record.currency)}
                  {priceDelta ? (
                    <span className="text-muted type-caption-mono ml-2 font-normal">
                      {priceDelta}
                    </span>
                  ) : null}
                </div>
              ) : null}
              {stringField(record.brand) || candidate.source_brand ? (
                <div className="text-muted type-caption uppercase">
                  {stringField(record.brand) || candidate.source_brand}
                </div>
              ) : null}
            </div>
          </div>
          <div className="text-muted/60 type-caption-mono mt-1 truncate" title={candidate.domain}>
            {candidate.domain}
          </div>
        </div>
      </div>
      <div className="border-divider mt-3 grid grid-cols-2 gap-2 border-t pt-3">
        <ComparisonCell label="Provider" value={provider} />
        <ComparisonCell label="Type" value={sourceType} />
        <ComparisonCell label="Rank" value={`#${candidate.search_rank || 1}`} />
        <ComparisonCell label="Query" value={candidate.query_used || '--'} title={candidate.query_used} />
      </div>
      <ReasonChips reasons={reasons} score={score} />
      <div className="border-divider mt-3 flex items-center justify-between border-t pt-2.5">
        <Button
          type="button"
          variant="quiet"
          size="sm"
          onClick={() => controller.setJsonModalCandidate(candidate)}
        >
          <Code2 className="mr-1.5 size-3" /> Raw JSON
        </Button>
        {selected ? (
          <span className="text-success type-label-mono flex items-center gap-1 uppercase">
            <CheckCircle2 className="size-3" /> Selected
          </span>
        ) : null}
        <a
          href={candidate.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-accent type-label-mono flex items-center gap-1 uppercase hover:underline"
        >
          View Source <ExternalLink className="size-2.5" />
        </a>
      </div>
    </div>
  );
}

function ComparisonCell({
  label,
  value,
  title,
}: {
  label: string;
  value: string;
  title?: string;
}) {
  return (
    <div className="min-w-0">
      <div className="text-muted type-caption-mono uppercase">{label}</div>
      <div className="text-foreground type-caption truncate" title={title ?? value}>
        {value || '--'}
      </div>
    </div>
  );
}

function ReasonChips({ reasons, score }: { reasons: Record<string, unknown>; score: number }) {
  const chips = confidenceChips(reasons, score);
  if (!chips.length) return null;
  return (
    <div className="mt-3 flex flex-wrap gap-1.5">
      {chips.map((chip) => (
        <Badge key={chip.label} tone={chip.tone} className="h-5 px-1.5 text-xs">
          {chip.label}
        </Badge>
      ))}
    </div>
  );
}

function confidenceChips(reasons: Record<string, unknown>, score: number) {
  const chips: Array<{ label: string; tone: 'neutral' | 'success' | 'warning' | 'accent' }> = [];
  if (reasons.brand_match === true) chips.push({ label: 'Brand match', tone: 'success' });
  if (reasons.sku_match === true) chips.push({ label: 'SKU match', tone: 'success' });
  if (reasons.mpn_or_style_match === true) chips.push({ label: 'Style match', tone: 'success' });
  if (reasons.shopping_product_group === true)
    chips.push({ label: 'Shopping evidence', tone: 'accent' });
  if (reasons.price_band_match === true) chips.push({ label: 'Price band', tone: 'success' });
  const titleSimilarity = Number(reasons.title_similarity ?? 0);
  if (Number.isFinite(titleSimilarity) && titleSimilarity > 0) {
    chips.push({
      label: `Title ${Math.round(titleSimilarity * 100)}%`,
      tone: titleSimilarity >= 0.6 ? 'success' : 'warning',
    });
  }
  if (reasons.brand_match === false && score >= 0.4) {
    chips.push({ label: 'Brand missing', tone: 'warning' });
  }
  return chips.slice(0, 6);
}

function providerLabel(
  payload: ProductIntelligenceCandidate['payload'],
  intelligence: Record<string, unknown>,
) {
  const payloadProvider = stringField(isRecord(payload) ? payload.provider : '');
  const provider = (payloadProvider || stringField(intelligence.cleanup_source))
    .replace(/^deterministic_/, '');
  if (provider === 'serpapi_immersive') return 'SerpAPI Stores';
  if (provider === 'serpapi_shopping') return 'SerpAPI Shopping';
  if (provider === 'serpapi') return 'SerpAPI Organic';
  if (provider === 'google_native') return 'Google Native';
  return provider || 'Search';
}

function sourceTypeLabel(value: string) {
  return (
    {
      brand_dtc: 'Brand DTC',
      retailer: 'Retailer',
      marketplace: 'Marketplace',
      aggregator: 'Aggregator',
      unknown: 'Unknown',
    }[value] ?? value
  );
}

function formatPriceDelta(sourcePrice: unknown, candidatePrice: unknown) {
  const source = numericPrice(sourcePrice);
  const candidate = numericPrice(candidatePrice);
  if (source === null || candidate === null) return '';
  const delta = candidate - source;
  if (Math.abs(delta) < 0.01) return 'same price';
  const sign = delta > 0 ? '+' : '-';
  return `${sign}$${Math.abs(delta).toFixed(2)}`;
}

function numericPrice(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  const parsed = Number(String(value ?? '').replace(/[^0-9.]+/g, ''));
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function CandidateImage({
  imageUrl,
  title,
  score,
}: {
  imageUrl: string;
  title: string;
  score: number;
}) {
  return (
    <div className="border-divider relative aspect-square w-[100px] shrink-0 overflow-hidden rounded-[var(--radius-md)] border bg-white p-1.5 shadow-sm">
      {imageUrl ? (
        <ExternalCandidateImage
          src={imageUrl}
          alt={title}
          className="size-full object-contain mix-blend-multiply"
        />
      ) : (
        <div className="text-muted/30 flex size-full items-center justify-center">
          <ImageOff className="size-8" />
        </div>
      )}
      <div
        className={cn(
          'type-caption-mono absolute right-1.5 bottom-1.5 rounded-md border px-1.5 py-0.5 font-normal shadow-sm',
          score >= 0.6
            ? 'bg-success border-success text-white'
            : score >= 0.4
              ? 'bg-warning border-warning text-white'
              : 'bg-background-elevated text-muted border-divider',
        )}
      >
        {Math.round(score * 100)}%
      </div>
    </div>
  );
}
