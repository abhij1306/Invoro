import { httpErrorStatus } from '../../lib/api/client';
import type { SelectorRecord, SelectorSuggestion } from '../../lib/api/types';
import {
  normalizeField,
  type RowState,
  type SelectorKind,
  type SelectorRow,
} from './selector-page-utils';

type StatusTone = 'success' | 'warning' | 'danger';
export type RowMessage = { tone: StatusTone; message: string };
export type SelectorsPageState = {
  url: string;
  loadedUrl: string;
  previewUrl: string;
  resolvedSurface: string;
  iframePromoted: boolean;
  expectedColumns: string;
  rows: SelectorRow[];
  rowMessages: Record<string, RowMessage>;
  loadError: string;
  loadingSuggestions: boolean;
  savingAccepted: boolean;
  activeTestKey: string | null;
  activeDetectKey: string | null;
};
export type SelectorsPageAction =
  | { type: 'urlChanged'; value: string }
  | { type: 'expectedColumnsChanged'; value: string }
  | { type: 'loadFailed'; message: string }
  | { type: 'suggestionsStarted' }
  | {
      type: 'suggestionsLoaded';
      loadedUrl: string;
      previewUrl: string;
      resolvedSurface: string;
      iframePromoted: boolean;
      rows: SelectorRow[];
    }
  | { type: 'suggestionsFinished' }
  | { type: 'rowPatched'; key: string; patch: Partial<SelectorRow> }
  | { type: 'rowAdded' }
  | { type: 'rowRemoved'; key: string }
  | { type: 'rowMessageSet'; key: string; message: RowMessage }
  | { type: 'detectStarted'; key: string }
  | { type: 'detectFinished' }
  | { type: 'testStarted'; key: string }
  | { type: 'testFinished' }
  | { type: 'saveStarted' }
  | { type: 'saveFinished' }
  | {
      type: 'rowsSaved';
      savedRows: Map<string, number>;
      resolvedSurface: string;
      nextMessages: Record<string, RowMessage>;
    };

export const INITIAL_SELECTORS_PAGE_STATE: SelectorsPageState = {
  url: '',
  loadedUrl: '',
  previewUrl: '',
  resolvedSurface: 'generic',
  iframePromoted: false,
  expectedColumns: '',
  rows: [],
  rowMessages: {},
  loadError: '',
  loadingSuggestions: false,
  savingAccepted: false,
  activeTestKey: null,
  activeDetectKey: null,
};

export function selectorsPageReducer(
  state: SelectorsPageState,
  action: SelectorsPageAction,
): SelectorsPageState {
  return (
    reduceLifecycle(state, action) ??
    reduceRows(state, action) ??
    reduceActivity(state, action) ??
    state
  );
}

function reduceLifecycle(
  state: SelectorsPageState,
  action: SelectorsPageAction,
): SelectorsPageState | null {
  switch (action.type) {
    case 'urlChanged':
      return { ...state, url: action.value };
    case 'expectedColumnsChanged':
      return { ...state, expectedColumns: action.value };
    case 'loadFailed':
      return { ...state, loadError: action.message };
    case 'suggestionsStarted':
      return { ...state, loadError: '', loadingSuggestions: true };
    case 'suggestionsLoaded':
      return {
        ...state,
        loadedUrl: action.loadedUrl,
        previewUrl: action.previewUrl,
        resolvedSurface: action.resolvedSurface,
        iframePromoted: action.iframePromoted,
        rows: action.rows,
        rowMessages: {},
      };
    case 'suggestionsFinished':
      return { ...state, loadingSuggestions: false };
    default:
      return null;
  }
}

function reduceRows(
  state: SelectorsPageState,
  action: SelectorsPageAction,
): SelectorsPageState | null {
  switch (action.type) {
    case 'rowPatched':
      return {
        ...state,
        rows: state.rows.map((row) => (row.key === action.key ? { ...row, ...action.patch } : row)),
      };
    case 'rowAdded':
      return { ...state, rows: [...state.rows, createEmptyRow()] };
    case 'rowRemoved':
      return removeRow(state, action.key);
    case 'rowMessageSet':
      return { ...state, rowMessages: { ...state.rowMessages, [action.key]: action.message } };
    case 'rowsSaved':
      return saveRows(state, action);
    default:
      return null;
  }
}

function reduceActivity(
  state: SelectorsPageState,
  action: SelectorsPageAction,
): SelectorsPageState | null {
  switch (action.type) {
    case 'detectStarted':
      return { ...state, activeDetectKey: action.key };
    case 'detectFinished':
      return { ...state, activeDetectKey: null };
    case 'testStarted':
      return { ...state, activeTestKey: action.key };
    case 'testFinished':
      return { ...state, activeTestKey: null };
    case 'saveStarted':
      return { ...state, savingAccepted: true, loadError: '' };
    case 'saveFinished':
      return { ...state, savingAccepted: false };
    default:
      return null;
  }
}

function removeRow(state: SelectorsPageState, key: string) {
  const rowMessages = { ...state.rowMessages };
  delete rowMessages[key];
  return { ...state, rows: state.rows.filter((row) => row.key !== key), rowMessages };
}

function saveRows(
  state: SelectorsPageState,
  action: Extract<SelectorsPageAction, { type: 'rowsSaved' }>,
) {
  const rowMessages = Object.fromEntries(
    Object.entries(state.rowMessages).filter(([key]) => !action.savedRows.has(key)),
  ) as Record<string, RowMessage>;
  const rows = state.rows.map((entry) =>
    action.savedRows.has(entry.key)
      ? {
          ...entry,
          selectorId: action.savedRows.get(entry.key) ?? entry.selectorId,
          surface: action.resolvedSurface,
          state: 'saved' as const,
        }
      : entry,
  );
  return { ...state, rows, rowMessages: { ...rowMessages, ...action.nextMessages } };
}

export function parseExpectedColumns(value: string) {
  return Array.from(
    new Set(
      value.split(/[\n,]/).flatMap((item) => {
        const field = normalizeField(item);
        return field ? [field] : [];
      }),
    ),
  );
}
export function selectorPlaceholder(kind: SelectorKind) {
  return kind === 'xpath'
    ? "//span[@class='price']"
    : kind === 'css_selector'
      ? '.price'
      : '\\$[\\d,.]+';
}
export function selectorSource(kind: SelectorKind) {
  return kind === 'xpath' ? 'llm_xpath' : kind === 'css_selector' ? 'llm_css' : 'llm_regex';
}
export function formatSelectorMatchMessage(count: number) {
  return count <= 0 ? 'No matches.' : `Matched ${count} result${count === 1 ? '' : 's'}.`;
}
export function nextSelectorRowState(state: RowState): RowState {
  return state === 'saved' ? 'saved' : state === 'accepted' ? 'idle' : 'accepted';
}
export function selectorStateLabel(state: RowState) {
  return state === 'saved' ? 'Saved' : state === 'accepted' ? 'Accepted' : 'Accept';
}
export function selectorStateTone(state: RowState) {
  return state === 'saved'
    ? ('success' as const)
    : state === 'accepted'
      ? ('warning' as const)
      : ('neutral' as const);
}
export function nextEditedState(state: RowState): RowState {
  return state === 'saved' ? 'accepted' : state;
}

export function buildRowFromSelectorRecord(record: SelectorRecord): SelectorRow {
  const [kind, selectorValue] = record.xpath
    ? ['xpath', record.xpath]
    : record.css_selector
      ? ['css_selector', record.css_selector]
      : ['regex', record.regex || ''];
  return {
    key: `selector:${record.id}`,
    selectorId: record.id,
    surface: record.surface,
    fieldName: record.field_name,
    kind: kind as SelectorKind,
    selectorValue,
    extractedValue: record.sample_value || '',
    source: record.source || 'domain_memory',
    state: 'saved',
  };
}

export function buildRowFromSuggestion(
  fieldName: string,
  suggestion?: SelectorSuggestion,
  surface?: string | null,
): SelectorRow {
  const candidates: Array<[SelectorKind, string | null | undefined, string]> = [
    ['xpath', suggestion?.xpath, 'llm_xpath'],
    ['css_selector', suggestion?.css_selector, 'llm_css'],
    ['regex', suggestion?.regex, 'llm_regex'],
  ];
  const selected = candidates.find(([, value]) => Boolean(value));
  return {
    key: createRowKey(),
    selectorId: null,
    surface: surface ?? null,
    fieldName,
    kind: selected?.[0] ?? 'xpath',
    selectorValue: selected?.[1] ?? '',
    extractedValue: suggestion?.sample_value || '',
    source: suggestion?.source || selected?.[2] || 'manual',
    state: 'idle',
  };
}

export function createEmptyRow(): SelectorRow {
  return {
    key: createRowKey(),
    selectorId: null,
    surface: null,
    fieldName: '',
    kind: 'xpath',
    selectorValue: '',
    extractedValue: '',
    source: 'manual',
    state: 'idle',
  };
}
function createRowKey() {
  return `selector:${Date.now()}:${Math.random().toString(36).slice(2, 8)}`;
}
export function isDuplicateSelectorError(error: unknown): boolean {
  if (httpErrorStatus(error) === 409) return true;
  const errorBody =
    typeof error === 'object' && error !== null && 'body' in error
      ? (error as { body?: unknown }).body
      : null;
  const fragments = [
    error instanceof Error ? error.message : '',
    typeof errorBody === 'string' ? errorBody : '',
  ];
  const message = fragments.join('').toLowerCase();
  return message.includes('already exists') || message.includes('duplicate');
}
