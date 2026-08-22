import type { PlaygroundSessionResponse } from '../../lib/api/types';
import {
  objectOrNull,
  stringList,
  stringOrUndefined,
  type UnknownRecord,
} from '../../lib/utils/type-guards';

export type PlaygroundSessionState =
  | 'created'
  | 'sitemap_listed'
  | 'discovering'
  | 'discovered'
  | 'extracting'
  | 'extracted'
  | 'running_pipeline'
  | 'complete';

export type DiscoveredProduct = {
  url: string;
  title?: string;
  brand?: string;
  price?: string;
  image?: string;
};

export type ExtractedRecord = {
  id: number;
  run_id: number;
  source_url: string;
  data: Record<string, unknown>;
};

export type SitemapGroup = {
  inputUrl: string;
  urls: string[];
  source: string;
  error?: string;
};

export type NavNode = {
  label: string;
  url?: string;
  children: NavNode[];
};

export type NavTreeGroup = {
  inputUrl: string;
  source: string;
  error?: string;
  tree: NavNode[];
};

export function collectNodeUrls(node: NavNode): string[] {
  const urls = node.url ? [node.url] : [];
  for (const child of node.children) {
    urls.push(...collectNodeUrls(child));
  }
  return Array.from(new Set(urls));
}

export function collectTreeUrls(tree: NavNode[]): string[] {
  return Array.from(new Set(tree.flatMap(collectNodeUrls)));
}

function isNavNode(value: unknown): value is NavNode {
  const data = objectOrNull(value);
  if (!data || typeof data.label !== 'string') return false;
  if (data.url !== undefined && typeof data.url !== 'string') return false;
  return Array.isArray(data.children) && data.children.every(isNavNode);
}

export function normalizeNavTree(value: unknown): NavNode[] {
  return Array.isArray(value) ? value.filter(isNavNode) : [];
}

function normalizeDiscoveredProduct(value: unknown): DiscoveredProduct | null {
  const data = objectOrNull(value);
  if (!data || typeof data.url !== 'string') return null;
  return {
    url: data.url,
    title: stringOrUndefined(data.title),
    brand: stringOrUndefined(data.brand),
    price: stringOrUndefined(data.price),
    image: stringOrUndefined(data.image),
  };
}

function normalizeExtractedRecord(value: unknown): ExtractedRecord | null {
  const data = objectOrNull(value);
  if (
    !data ||
    typeof data.id !== 'number' ||
    typeof data.run_id !== 'number' ||
    typeof data.source_url !== 'string'
  ) {
    return null;
  }
  return {
    id: data.id,
    run_id: data.run_id,
    source_url: data.source_url,
    data: objectOrNull(data.data) ?? {},
  };
}

function step(session: PlaygroundSessionResponse | undefined, key: string): UnknownRecord | null {
  return objectOrNull(session?.step_data?.[key]);
}

export function normalizeDiscoveredProducts(
  session: PlaygroundSessionResponse | undefined,
): DiscoveredProduct[] {
  return Array.isArray(step(session, 'discover')?.products)
    ? (step(session, 'discover')?.products as unknown[])
        .map(normalizeDiscoveredProduct)
        .filter((item): item is DiscoveredProduct => item !== null)
    : [];
}

export function normalizeSitemap(session: PlaygroundSessionResponse | undefined) {
  const sitemap = step(session, 'sitemap');
  const sources = objectOrNull(sitemap?.sources) ?? {};
  const errors = objectOrNull(sitemap?.errors) ?? {};
  return {
    urls: stringList(sitemap?.urls),
    sourceLabel: sitemapSourceLabel(sitemap?.source),
    groups: normalizeSitemapGroups(sitemap?.groups, sources, errors),
    navTreeGroups: normalizeNavTreeGroups(sitemap, sources, errors, session),
  };
}

function sitemapSourceLabel(source: unknown) {
  if (source === 'homepage') return 'homepage';
  if (source === 'rendered_site_links') return 'rendered site links';
  if (source === 'mixed' || String(source ?? '').includes('rendered_site_links')) {
    return 'mixed discovery';
  }
  return 'sitemap';
}

function normalizeSitemapGroups(
  value: unknown,
  sources: UnknownRecord,
  errors: UnknownRecord,
): SitemapGroup[] {
  const groups = objectOrNull(value);
  return groups
    ? Object.entries(groups).map(([inputUrl, urls]) => ({
        inputUrl,
        urls: stringList(urls),
        source: stringOrUndefined(sources[inputUrl]) ?? 'unknown',
        error: stringOrUndefined(errors[inputUrl]),
      }))
    : [];
}

function normalizeNavTreeGroups(
  sitemap: UnknownRecord | null,
  sources: UnknownRecord,
  errors: UnknownRecord,
  session: PlaygroundSessionResponse | undefined,
): NavTreeGroup[] {
  const trees = objectOrNull(sitemap?.trees);
  const groups = trees
    ? Object.entries(trees)
        .map(([inputUrl, tree]) => ({
          inputUrl,
          tree: normalizeNavTree(tree),
          source: stringOrUndefined(sources[inputUrl]) ?? 'unknown',
          error: stringOrUndefined(errors[inputUrl]),
        }))
        .filter((group) => group.tree.length > 0)
    : [];
  if (groups.length || !session) return groups;
  const tree = normalizeNavTree(sitemap?.nav_tree);
  return tree.length
    ? [
        {
          inputUrl: session.input_url,
          source: stringOrUndefined(sitemap?.source) ?? 'unknown',
          error: stringOrUndefined(sitemap?.error),
          tree,
        },
      ]
    : [];
}

export function normalizePlaygroundResults(payload: unknown) {
  const steps = objectOrNull(objectOrNull(payload)?.steps);
  const extract = objectOrNull(steps?.extract);
  const records = Array.isArray(extract?.records)
    ? extract.records
        .map(normalizeExtractedRecord)
        .filter((item): item is ExtractedRecord => item !== null)
    : [];
  const runIds = Array.isArray(extract?.run_ids)
    ? extract.run_ids.filter((value): value is number => typeof value === 'number')
    : [];
  return { steps: steps ?? undefined, records, runIds };
}

export function playgroundStepIndex(state: PlaygroundSessionState): number {
  if (state === 'created' || state === 'sitemap_listed' || state === 'discovering') return 0;
  if (state === 'discovered') return 1;
  if (state === 'extracting') return 2;
  if (state === 'extracted') return 3;
  return 4;
}

export function sessionNeedsPolling(session: PlaygroundSessionResponse | undefined): boolean {
  const state = session?.state;
  if (state === 'discovering' || state === 'extracting' || state === 'running_pipeline')
    return true;
  return objectOrNull(session?.step_data?.audit)?.status === 'running';
}
