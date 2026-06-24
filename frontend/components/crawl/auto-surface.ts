import type { CrawlSurface } from '../../lib/api/types';
import type { CrawlTab } from './shared';

export type AutoSurfaceResolution = {
  surface: Exclude<CrawlSurface, 'auto'>;
  confidence: number;
  evidence: string[];
};

const ARTICLE_HOSTS = new Set(['codeforces.com']);
const ARTICLE_DETAIL_TOKENS = ['/blog/entry/', '/article/', '/post/'];
const ARTICLE_TOKENS = [
  '/blog/',
  '/blog/entry/',
  '/article/',
  '/articles/',
  '/news/',
  '/post/',
  '/posts/',
];
const FORUM_TOKENS = [
  '/thread/',
  '/threads/',
  '/forum/',
  '/forums/',
  '/discussion/',
  '/discussions/',
  '/questions/',
  '/answers/',
  '/comments/',
];
const FORUM_HOST_TOKENS = ['forum', 'discuss', 'community'];
const JOB_TOKENS = ['/job/', '/jobs/', '/careers/', '/positions/', '/openings/'];
const ECOMMERCE_LISTING_TOKENS = [
  '/collections/',
  '/collection/',
  '/category/',
  '/categories/',
  '/search',
  '/shop/',
];
const ECOMMERCE_DETAIL_TOKENS = ['/product/', '/products/', '/p/', '/item/', '/dp/'];
const LISTING_PATHS = new Set([
  '/archive',
  '/archives',
  '/blog',
  '/blogs',
  '/docs',
  '/documentation',
  '/events',
  '/forum',
  '/forums',
  '/news',
  '/posts',
  '/resources',
  '/topics',
]);

export function resolveAutoSurface(url: string, module: CrawlTab): AutoSurfaceResolution {
  const parsed = parseHttpUrl(url);
  const isListing = module === 'category';
  if (!parsed) {
    return fallback(isListing, ['fallback_content_surface']);
  }
  const { host, path } = parsed;
  const evidence = ['requested_surface:auto'];
  if (
    hasAny(path, ARTICLE_TOKENS) ||
    (ARTICLE_HOSTS.has(host) && hasAny(path, ARTICLE_DETAIL_TOKENS))
  ) {
    return {
      surface: 'article_detail',
      confidence: 0.9,
      evidence: [...evidence, 'article_detail_url_signal'],
    };
  }
  if (
    FORUM_HOST_TOKENS.some((token) => host.includes(token)) ||
    FORUM_TOKENS.some((token) => path.includes(token))
  ) {
    return {
      surface: 'forum_detail',
      confidence: 0.7,
      evidence: [...evidence, 'forum_url_signal'],
    };
  }
  if (hasAny(path, JOB_TOKENS)) {
    return {
      surface: isListing ? 'job_listing' : 'job_detail',
      confidence: 0.7,
      evidence: [...evidence, 'job_url_signal'],
    };
  }
  if (hasAny(path, ECOMMERCE_LISTING_TOKENS)) {
    return {
      surface: 'ecommerce_listing',
      confidence: 0.7,
      evidence: [...evidence, 'ecommerce_listing_url_signal'],
    };
  }
  if (hasAny(path, ECOMMERCE_DETAIL_TOKENS)) {
    return {
      surface: 'ecommerce_detail',
      confidence: 0.7,
      evidence: [...evidence, 'ecommerce_detail_url_signal'],
    };
  }
  return fallback(isListing && hasListingUrlShape(path), [...evidence, 'fallback_content_surface']);
}

function fallback(isListing: boolean, evidence: string[]): AutoSurfaceResolution {
  return {
    surface: isListing ? 'content_listing' : 'content_detail',
    confidence: 0.4,
    evidence,
  };
}

function parseHttpUrl(value: string): { host: string; path: string } | null {
  try {
    const parsed = new URL(value.trim());
    if (!['http:', 'https:'].includes(parsed.protocol)) {
      return null;
    }
    return {
      host: parsed.hostname.replace(/^www\./, '').toLowerCase(),
      path: parsed.pathname.toLowerCase(),
    };
  } catch {
    return null;
  }
}

function hasAny(value: string, tokens: string[]) {
  return tokens.some((token) => value.includes(token));
}

function hasListingUrlShape(path: string) {
  const normalized = path.trim().toLowerCase().replace(/\/$/, '');
  return LISTING_PATHS.has(normalized);
}
