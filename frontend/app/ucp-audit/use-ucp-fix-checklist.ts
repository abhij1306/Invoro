'use client';

import { useMemo, useState } from 'react';

import type { UcpAuditReport } from '../../lib/api/types';
import { evidenceToLines, formatUnknownText, type UcpRoadmapItem } from './ucp-report-normalizers';

type UseUcpFixChecklistArgs = {
  report: UcpAuditReport | null;
  roadmap: UcpRoadmapItem[];
};

function readChecklist(storageKey: string | null): Record<string, boolean> {
  if (!storageKey || typeof globalThis.window === 'undefined') return {};
  try {
    const stored = globalThis.window.localStorage.getItem(storageKey);
    if (!stored) return {};
    const parsed: unknown = JSON.parse(stored);
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? (parsed as Record<string, boolean>)
      : {};
  } catch {
    return {};
  }
}

export function buildChecklistExport(
  report: UcpAuditReport | null,
  roadmap: UcpRoadmapItem[],
  done: Record<string, boolean>,
): string {
  const lines = roadmap.map((item, index) => {
    const checked = done[item.id] ? 'x' : ' ';
    const evidenceLines = evidenceToLines(item.evidence)
      .map((line) => `   - ${line}`)
      .join('\n');
    const evidenceBlock = evidenceLines ? `\n${evidenceLines}` : '';
    return `- [${checked}] ${index + 1}. [${item.subSkill}] ${item.action} (${item.priority}, ${item.effort})\n   Source: ${item.source}${evidenceBlock}`;
  });
  const domain = formatUnknownText(report?.report_json?.domain, 'Audit Store');
  return `# AI Discoverability Repair Roadmap\n\nTarget Domain: ${domain}\nOverall Score: ${report?.overall_score ?? 0}/100\n\n${lines.join('\n\n')}\n`;
}

export function useUcpFixChecklist({ report, roadmap }: UseUcpFixChecklistArgs) {
  const storageKey = report?.job_id ? `ucp-fix-sequence-${report.job_id}` : null;
  const [checklists, setChecklists] = useState<Record<string, Record<string, boolean>>>(() =>
    storageKey ? { [storageKey]: readChecklist(storageKey) } : {},
  );

  const done = useMemo(
    () => (storageKey ? (checklists[storageKey] ?? readChecklist(storageKey)) : {}),
    [checklists, storageKey],
  );

  const doneCount = useMemo(() => roadmap.filter((item) => done[item.id]).length, [done, roadmap]);
  const progressPercent = roadmap.length ? Math.round((doneCount / roadmap.length) * 100) : 0;

  function toggle(id: string) {
    if (!storageKey) return;
    const next = { ...done, [id]: !done[id] };
    setChecklists((current) => ({ ...current, [storageKey]: next }));
    if (typeof globalThis.window === 'undefined') return;
    try {
      globalThis.window.localStorage.setItem(storageKey, JSON.stringify(next));
    } catch {
      // The in-memory update remains authoritative when storage is unavailable.
    }
  }

  function exportPlan() {
    const content = buildChecklistExport(report, roadmap, done);
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `aid-repair-roadmap-${report?.job_id ?? 'audit'}.md`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return { done, doneCount, progressPercent, toggle, exportPlan };
}
