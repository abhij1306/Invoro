import type { SelectorRecord } from '../../lib/api/types';

export type SelectorKind = 'xpath' | 'css_selector' | 'regex';
export type RowState = 'idle' | 'accepted' | 'saved';

export type SelectorRow = {
  key: string;
  selectorId: number | null;
  surface: string | null;
  fieldName: string;
  kind: SelectorKind;
  selectorValue: string;
  extractedValue: string;
  source: string;
  state: RowState;
};

export function normalizeField(value: string) {
  return value.trim().toLowerCase().replace(/\s+/g, '_');
}

export function selectRelevantSelectorRecords(records: SelectorRecord[], surface: string) {
  return records
    .filter(
      (record) => record.is_active && (record.surface === surface || record.surface === 'generic'),
    )
    .sort((left, right) => {
      const leftPriority = left.surface === surface ? 0 : 1;
      const rightPriority = right.surface === surface ? 0 : 1;
      if (leftPriority !== rightPriority) {
        return leftPriority - rightPriority;
      }
      return `${left.field_name}:${left.id}`.localeCompare(`${right.field_name}:${right.id}`);
    });
}

export function inferSelectorSurface(fields: string[], url: string) {
  const normalized = new Set(fields.map((field) => normalizeField(field)));
  if (
    ['company', 'location', 'apply_url', 'salary', 'remote'].some((field) => normalized.has(field))
  ) {
    return 'job_detail';
  }
  if (String(url).toLowerCase().includes('jobs')) {
    return 'job_detail';
  }
  return 'ecommerce_detail';
}

export function mergeSelectorRows(
  currentRows: SelectorRow[],
  incomingRows: SelectorRow[],
  options?: { preferIncoming?: boolean },
) {
  const merged = new Map<string, SelectorRow>();
  const preferIncoming = Boolean(options?.preferIncoming);
  for (const row of currentRows) {
    merged.set(normalizeField(row.fieldName || row.key), row);
  }
  for (const row of incomingRows) {
    const key = normalizeField(row.fieldName || row.key);
    const existing = merged.get(key);
    if (!existing) {
      merged.set(key, row);
      continue;
    }
    merged.set(key, mergeSelectorRow(existing, row, preferIncoming));
  }
  return Array.from(merged.values());
}

function mergeSelectorRow(existing: SelectorRow, incoming: SelectorRow, preferIncoming: boolean) {
  if (preferIncoming) {
    return {
      ...existing,
      selectorId: existing.selectorId ?? incoming.selectorId,
      surface: existing.surface ?? incoming.surface,
      fieldName: existing.fieldName || incoming.fieldName,
      kind: incoming.kind,
      selectorValue: incoming.selectorValue,
      extractedValue: incoming.extractedValue,
      source: incoming.source,
      state: incoming.state,
    };
  }
  return {
    ...existing,
    selectorId: existing.selectorId ?? incoming.selectorId,
    surface: existing.surface ?? incoming.surface,
    fieldName: existing.fieldName || incoming.fieldName,
    kind: existing.selectorValue ? existing.kind : incoming.kind,
    selectorValue: existing.selectorValue || incoming.selectorValue,
    extractedValue: existing.extractedValue || incoming.extractedValue,
    source: existing.source || incoming.source,
    state: existing.state === 'saved' ? 'saved' : incoming.state,
  };
}

export function buildXPathForElement(element: Element): string {
  const segments: string[] = [];
  let current: Element | null = element;
  while (current && current.nodeType === Node.ELEMENT_NODE) {
    const tagName = current.tagName.toLowerCase();
    const testId = current.getAttribute('data-testid');
    if (testId) {
      segments.unshift(`//${tagName}[@data-testid=${xpathLiteral(testId)}]`);
      return segments.join('');
    }
    const id = current.getAttribute('id');
    if (id) {
      segments.unshift(`//${tagName}[@id=${xpathLiteral(id)}]`);
      return segments.join('');
    }
    let index = 1;
    if (current.parentElement) {
      for (const sibling of current.parentElement.children) {
        if (sibling === current) {
          break;
        }
        if (sibling.tagName.toLowerCase() === tagName) {
          index += 1;
        }
      }
    }
    segments.unshift(`/${tagName}[${index}]`);
    current = current.parentElement;
  }
  return segments.join('') || '//*';
}

export function xpathLiteral(value: string): string {
  if (!value.includes("'")) {
    return `'${value}'`;
  }
  if (!value.includes('"')) {
    return `"${value}"`;
  }
  const parts = value.split("'");
  const args: string[] = [];
  for (let index = 0; index < parts.length; index += 1) {
    args.push(`'${parts[index]}'`);
    if (index < parts.length - 1) {
      args.push(`"'"`);
    }
  }
  return `concat(${args.join(',')})`;
}
