import type {
  CrawlRun,
  DomainCookieMemoryRecord,
  DomainFieldFeedbackRecord,
  DomainRunProfileRecord,
  SelectorDomainSummary,
} from '../../../lib/api/types';
import { getNormalizedDomain, isSpecialUseDomain } from '../../../lib/format/domain';
import type { DomainWorkspace, LocalRecord, SurfaceWorkspace } from './types';
import {
  feedbackSearchText,
  isInternalDomainMemoryArtifact,
  profileSearchText,
  selectorValue,
} from './utils';

type BuildDomainWorkspacesInput = {
  completedRuns: CrawlRun[];
  cookies: DomainCookieMemoryRecord[];
  feedback: DomainFieldFeedbackRecord[];
  profiles: DomainRunProfileRecord[];
  records: LocalRecord[];
  selectorSummaries: SelectorDomainSummary[];
  searchQuery: string;
  surfaceFilter: string;
};

export function buildDomainWorkspaces({
  completedRuns,
  cookies,
  feedback,
  profiles,
  records,
  selectorSummaries,
  searchQuery,
  surfaceFilter,
}: BuildDomainWorkspacesInput): DomainWorkspace[] {
  const query = searchQuery.trim().toLowerCase();
  const byDomain = new Map<string, Map<string, SurfaceWorkspace>>();
  const cookiesByDomain = new Map(cookies.map((row) => [row.domain, row] as const));
  const runsByDomain = new Map<string, Map<string, CrawlRun[]>>();
  ingestSelectorSummaries(byDomain, selectorSummaries, query, surfaceFilter);
  ingestSelectorRecords(byDomain, records, query, surfaceFilter);
  ingestProfiles(byDomain, profiles, query, surfaceFilter);
  ingestFeedback(byDomain, feedback, query, surfaceFilter);
  ingestCompletedRuns(byDomain, runsByDomain, completedRuns, query, surfaceFilter);
  return materializeWorkspaces(
    byDomain,
    runsByDomain,
    cookiesByDomain,
    cookies,
    query,
    surfaceFilter,
  ).sort(compareDomainWorkspaces);
}

type WorkspaceIndex = Map<string, Map<string, SurfaceWorkspace>>;

function ensureSurfaceWorkspace(
  index: WorkspaceIndex,
  domain: string,
  surface: string,
): SurfaceWorkspace {
  const domainEntry = index.get(domain) ?? new Map<string, SurfaceWorkspace>();
  if (!index.has(domain)) index.set(domain, domainEntry);
  const existing = domainEntry.get(surface);
  if (existing) return existing;
  const created: SurfaceWorkspace = {
    surface,
    selectorCount: 0,
    selectors: [],
    profile: null,
    learning: [],
    completedRuns: [],
  };
  domainEntry.set(surface, created);
  return created;
}

function matchesFilter(surface: string, searchable: string, query: string, surfaceFilter: string) {
  return (
    (surfaceFilter === 'all' || surface === surfaceFilter) &&
    (!query || searchable.toLowerCase().includes(query))
  );
}

function ingestSelectorSummaries(
  index: WorkspaceIndex,
  rows: SelectorDomainSummary[],
  query: string,
  filter: string,
) {
  for (const row of rows) {
    if (!matchesFilter(row.surface, `${row.domain} ${row.surface}`, query, filter)) continue;
    ensureSurfaceWorkspace(index, row.domain, row.surface).selectorCount = row.selector_count;
  }
}

function ingestSelectorRecords(
  index: WorkspaceIndex,
  rows: LocalRecord[],
  query: string,
  filter: string,
) {
  for (const row of rows) {
    const searchable = [
      row.domain,
      row.surface,
      row.field_name,
      row.source,
      selectorValue(row),
    ].join(' ');
    if (!matchesFilter(row.surface, searchable, query, filter)) continue;
    const workspace = ensureSurfaceWorkspace(index, row.domain, row.surface);
    workspace.selectors.push(row);
    workspace.selectorCount = Math.max(workspace.selectorCount, workspace.selectors.length);
  }
}

function ingestProfiles(
  index: WorkspaceIndex,
  rows: DomainRunProfileRecord[],
  query: string,
  filter: string,
) {
  for (const row of rows) {
    const searchable = `${profileSearchText(row)} ${row.domain}`;
    if (!matchesFilter(row.surface, searchable, query, filter)) continue;
    ensureSurfaceWorkspace(index, row.domain, row.surface).profile = row;
  }
}

function ingestFeedback(
  index: WorkspaceIndex,
  rows: DomainFieldFeedbackRecord[],
  query: string,
  filter: string,
) {
  for (const row of rows) {
    const searchable = `${feedbackSearchText(row)} ${row.domain}`;
    if (!matchesFilter(row.surface, searchable, query, filter)) continue;
    ensureSurfaceWorkspace(index, row.domain, row.surface).learning.push(row);
  }
}

function ingestCompletedRuns(
  index: WorkspaceIndex,
  runsIndex: Map<string, Map<string, CrawlRun[]>>,
  runs: CrawlRun[],
  query: string,
  filter: string,
) {
  for (const run of runs) {
    const domain = String(run.result_summary?.domain || '').trim() || getNormalizedDomain(run.url);
    if (!domain || isSpecialUseDomain(domain)) continue;
    if (
      !matchesFilter(
        run.surface,
        `${domain} ${run.surface} ${run.url} ${run.status}`,
        query,
        filter,
      )
    )
      continue;
    const domainRuns = runsIndex.get(domain) ?? new Map<string, CrawlRun[]>();
    if (!runsIndex.has(domain)) runsIndex.set(domain, domainRuns);
    const surfaceRuns = domainRuns.get(run.surface) ?? [];
    if (!domainRuns.has(run.surface)) domainRuns.set(run.surface, surfaceRuns);
    surfaceRuns.push(run);
    ensureSurfaceWorkspace(index, domain, run.surface).completedRuns.push(run);
  }
}

function visibleDomainNames(
  index: WorkspaceIndex,
  runsIndex: Map<string, Map<string, CrawlRun[]>>,
  cookies: DomainCookieMemoryRecord[],
  query: string,
  filter: string,
) {
  const cookieDomains = cookies.flatMap((row) =>
    filter === 'all' && (!query || row.domain.toLowerCase().includes(query)) ? [row.domain] : [],
  );
  return new Set<string>([...index.keys(), ...runsIndex.keys(), ...cookieDomains]);
}

function materializeWorkspaces(
  index: WorkspaceIndex,
  runsIndex: Map<string, Map<string, CrawlRun[]>>,
  cookiesByDomain: Map<string, DomainCookieMemoryRecord>,
  cookies: DomainCookieMemoryRecord[],
  query: string,
  filter: string,
) {
  const workspaces: DomainWorkspace[] = [];
  for (const domain of visibleDomainNames(index, runsIndex, cookies, query, filter)) {
    const workspace = materializeWorkspace(domain, index, cookiesByDomain);
    if (workspace) workspaces.push(workspace);
  }
  return workspaces;
}

function materializeWorkspace(
  domain: string,
  index: WorkspaceIndex,
  cookiesByDomain: Map<string, DomainCookieMemoryRecord>,
): DomainWorkspace | null {
  const normalizedDomain = String(domain || '').trim();
  if (!normalizedDomain || isSpecialUseDomain(normalizedDomain)) return null;
  const surfaces = Array.from(
    (index.get(domain) ?? new Map<string, SurfaceWorkspace>()).values(),
  ).sort((left, right) => left.surface.localeCompare(right.surface));
  const completedRunCount = surfaces.reduce(
    (count, surface) => count + surface.completedRuns.length,
    0,
  );
  const cookieMemory = cookiesByDomain.get(domain) ?? null;
  const learning = surfaces.flatMap((surface) => surface.learning);
  if (
    isInternalDomainMemoryArtifact(
      normalizedDomain,
      surfaces.length,
      Boolean(cookieMemory),
      learning.length,
      completedRunCount,
    )
  )
    return null;
  if (!surfaces.length && !cookieMemory) return null;
  return {
    domain,
    surfaces,
    cookieMemory,
    learning,
    completedRunCount,
    latestCompletedAt: latestCompletedAtFor(surfaces),
  };
}

function latestCompletedAtFor(surfaces: SurfaceWorkspace[]) {
  let latest: string | null = null;
  let latestTime = -Infinity;
  for (const surface of surfaces) {
    for (const run of surface.completedRuns) {
      const value = run.completed_at ?? run.updated_at ?? run.created_at;
      if (!value) continue;
      const time = new Date(value).getTime();
      if (time > latestTime) {
        latestTime = time;
        latest = value;
      }
    }
  }
  return latest;
}

function compareDomainWorkspaces(left: DomainWorkspace, right: DomainWorkspace) {
  const completedDelta = right.completedRunCount - left.completedRunCount;
  if (completedDelta !== 0) return completedDelta;
  const leftTime = left.latestCompletedAt ? new Date(left.latestCompletedAt).getTime() : 0;
  const rightTime = right.latestCompletedAt ? new Date(right.latestCompletedAt).getTime() : 0;
  if (rightTime !== leftTime) return rightTime - leftTime;
  const leftMemoryScore = memoryScore(left);
  const rightMemoryScore = memoryScore(right);
  if (rightMemoryScore !== leftMemoryScore) return rightMemoryScore - leftMemoryScore;
  return left.domain.localeCompare(right.domain);
}

function memoryScore(workspace: DomainWorkspace) {
  return (
    workspace.surfaces.reduce((count, surface) => count + surface.selectorCount, 0) +
    workspace.surfaces.filter((surface) => surface.profile).length +
    workspace.learning.length +
    (workspace.cookieMemory ? 1 : 0)
  );
}
