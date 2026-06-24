import { act, renderHook } from '@testing-library/react';
import { useState } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { SelectorDomainSummary } from '../../lib/api/types';
import { useSelectorRecordActions } from './domain-memory/use-selector-record-actions';
import type { EditDraft, LocalRecord } from './domain-memory/types';

const apiMock = vi.hoisted(() => ({
  deleteSelector: vi.fn(),
  deleteSelectorsByDomain: vi.fn(),
  updateSelector: vi.fn(),
}));

vi.mock('../../lib/api', () => ({ api: apiMock }));

const record: LocalRecord = {
  _uid: 'selector-1',
  id: 1,
  domain: 'example.com',
  surface: 'detail',
  field_name: 'price',
  css_selector: '.price',
  xpath: null,
  regex: null,
  status: 'verified',
  sample_value: '$10',
  source: 'manual',
  source_run_id: 12,
  is_active: true,
  created_at: '2026-06-01T00:00:00Z',
  updated_at: '2026-06-01T00:00:00Z',
};

const summary: SelectorDomainSummary = {
  domain: 'example.com',
  surface: 'detail',
  selector_count: 1,
  updated_at: '2026-06-01T00:00:00Z',
};

function useHarness() {
  const [records, setRecords] = useState<LocalRecord[]>([record]);
  const [summaries, setSelectorSummaries] = useState<SelectorDomainSummary[]>([summary]);
  const [draft, setDraft] = useState<EditDraft | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [error, setError] = useState('');
  const cancelEdit = () => {
    setDraft(null);
    setEditingId(null);
  };
  const actions = useSelectorRecordActions({
    cancelEdit,
    draft,
    editingId,
    setDraft,
    setEditingId,
    setError,
    setRecords,
    setSelectorSummaries,
  });
  return { actions, draft, editingId, error, records, summaries };
}

describe('selector record actions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('updates a selector and preserves its local uid', async () => {
    apiMock.updateSelector.mockResolvedValue({ ...record, css_selector: '.sale-price' });
    const { result } = renderHook(() => useHarness());

    act(() => result.current.actions.startEdit(record));
    expect(result.current.editingId).toBe(record._uid);

    await act(async () => {
      await result.current.actions.saveEdit(record);
    });

    expect(apiMock.updateSelector).toHaveBeenCalledWith(1, {
      field_name: 'price',
      xpath: null,
      css_selector: '.price',
      regex: null,
      source: 'manual',
      is_active: true,
    });
    expect(result.current.records[0]).toMatchObject({
      _uid: record._uid,
      css_selector: '.sale-price',
    });
    expect(result.current.editingId).toBeNull();
  });

  it('keeps local state unchanged and exposes the API error when update fails', async () => {
    apiMock.updateSelector.mockRejectedValue(new Error('Selector update failed'));
    const { result } = renderHook(() => useHarness());

    await act(async () => {
      await result.current.actions.toggleActive(record);
    });

    expect(result.current.records).toEqual([record]);
    expect(result.current.error).toBe('Selector update failed');
  });

  it('deletes a selector and decrements only its matching summary', async () => {
    apiMock.deleteSelector.mockResolvedValue(undefined);
    const { result } = renderHook(() => useHarness());

    await act(async () => {
      await result.current.actions.deleteRecord(record);
    });

    expect(apiMock.deleteSelector).toHaveBeenCalledWith(1);
    expect(result.current.records).toEqual([]);
    expect(result.current.summaries[0].selector_count).toBe(0);
  });

  it('retains selector and summary state when deletion fails', async () => {
    apiMock.deleteSelector.mockRejectedValue(new Error('Delete failed'));
    const { result } = renderHook(() => useHarness());

    await act(async () => {
      await result.current.actions.deleteRecord(record);
    });

    expect(result.current.records).toEqual([record]);
    expect(result.current.summaries).toEqual([summary]);
    expect(result.current.error).toBe('Delete failed');
  });

  it('clears all selectors and summaries for a domain', async () => {
    apiMock.deleteSelectorsByDomain.mockResolvedValue(undefined);
    const { result } = renderHook(() => useHarness());

    await act(async () => {
      await result.current.actions.deleteDomainSelectors('example.com');
    });

    expect(result.current.records).toEqual([]);
    expect(result.current.summaries).toEqual([]);
  });
});
