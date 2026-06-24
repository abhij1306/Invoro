'use client';

import { create } from 'zustand';

import { CRAWL_DEFAULTS } from '../../lib/constants/crawl-defaults';
import type { OutputTabKey } from './shared';

type Updater<T> = T | ((current: T) => T);

type CrawlRunUiState = {
  selectedIds: number[];
  outputTab: OutputTabKey;
  tablePage: number;
  jsonVisibleCount: number;
  alertBuilderOpen: boolean;
  historyOpen: boolean;
  setSelectedIds: (next: Updater<number[]>) => void;
  setOutputTab: (next: OutputTabKey) => void;
  setTablePage: (next: Updater<number>) => void;
  setJsonVisibleCount: (next: Updater<number>) => void;
  setAlertBuilderOpen: (open: boolean) => void;
  setHistoryOpen: (open: boolean) => void;
  resetWorkspaceUi: () => void;
};

function resolveUpdater<T>(current: T, next: Updater<T>) {
  return typeof next === 'function' ? (next as (value: T) => T)(current) : next;
}

const initialState = {
  selectedIds: [],
  outputTab: 'table' as OutputTabKey,
  tablePage: 1,
  jsonVisibleCount: CRAWL_DEFAULTS.TABLE_PAGE_SIZE * 4,
  alertBuilderOpen: false,
  historyOpen: false,
};

export const useCrawlRunStore = create<CrawlRunUiState>((set) => ({
  ...initialState,
  setSelectedIds: (next) =>
    set((state) => ({ selectedIds: resolveUpdater(state.selectedIds, next) })),
  setOutputTab: (outputTab) => set({ outputTab }),
  setTablePage: (next) => set((state) => ({ tablePage: resolveUpdater(state.tablePage, next) })),
  setJsonVisibleCount: (next) =>
    set((state) => ({ jsonVisibleCount: resolveUpdater(state.jsonVisibleCount, next) })),
  setAlertBuilderOpen: (alertBuilderOpen) => set({ alertBuilderOpen }),
  setHistoryOpen: (historyOpen) => set({ historyOpen }),
  resetWorkspaceUi: () => set(initialState),
}));
