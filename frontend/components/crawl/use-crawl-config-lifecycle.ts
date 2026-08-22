'use client';

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  type Dispatch,
  type SetStateAction,
} from 'react';
import { api } from '../../lib/api';
import type { CrawlSurface, DomainRunProfile } from '../../lib/api/types';
import { getNormalizedDomain } from '../../lib/format/domain';
import { STORAGE_KEYS } from '../../lib/constants/storage-keys';
import { UI_DELAYS } from '../../lib/constants/timing';
import {
  buildFieldRowFromSelectorRecord,
  cloneRunProfile,
  defaultRunProfile,
  mergeFieldRows,
  selectRelevantSelectorRecords,
  stripDomainMemoryFieldRows,
  surfaceLabel,
} from './crawl-config-logic';
import {
  bindCrawlConfigLocalDispatch,
  isBulkPrefill,
  type CrawlRouteAction,
} from './crawl-config-state';
import { DOMAIN_OPTIONS } from './domain-surface-config';
import { uniqueRequestedFields, type FieldRow } from './shared';

type LocalDispatch = ReturnType<typeof bindCrawlConfigLocalDispatch>;

type Options = {
  profileLookupKey: string;
  domainMemoryLookupKey: string;
  targetUrl: string;
  normalizedTargetDomain: string;
  effectiveSurface: CrawlSurface;
  bulkPrefillRouteSyncGuardRef: { current: boolean };
  dispatchRoute: Dispatch<CrawlRouteAction>;
  localDispatch: LocalDispatch;
  setTargetUrl: (value: string) => void;
  setBulkUrls: (value: string) => void;
  setFieldRows: Dispatch<SetStateAction<FieldRow[]>>;
};

export function useCrawlConfigLifecycle(options: Options) {
  const {
    profileLookupKey,
    domainMemoryLookupKey,
    targetUrl,
    normalizedTargetDomain,
    effectiveSurface,
    bulkPrefillRouteSyncGuardRef,
    dispatchRoute,
    localDispatch,
    setTargetUrl,
    setBulkUrls,
    setFieldRows,
  } = options;
  const profileRequestRef = useRef(0);
  const memoryRequestRef = useRef(0);
  const profileTargetUrlRef = useRef('');
  const profileDirtyRef = useRef(false);

  useLayoutEffect(() => {
    const stored = window.sessionStorage.getItem(STORAGE_KEYS.BULK_PREFILL);
    if (!stored) return;
    try {
      const parsed = JSON.parse(stored) as unknown;
      if (isBulkPrefill(parsed) && parsed.urls.length) {
        bulkPrefillRouteSyncGuardRef.current = true;
        const domain =
          parsed.domain && DOMAIN_OPTIONS.some((option) => option.value === parsed.domain)
            ? parsed.domain
            : undefined;
        dispatchRoute({ type: 'applyBulkPrefill', domain });
        setBulkUrls(parsed.urls.join('\n'));
        if (parsed.additional_fields) {
          localDispatch.setAdditionalFields(uniqueRequestedFields(parsed.additional_fields));
        }
        const nextUrl = '/crawl?module=pdp&mode=batch';
        if (`${window.location.pathname}${window.location.search}` !== nextUrl) {
          window.history.replaceState(null, '', nextUrl);
        }
      }
    } catch {
      // Ignore malformed one-shot prefill.
    } finally {
      window.sessionStorage.removeItem(STORAGE_KEYS.BULK_PREFILL);
    }
  }, [bulkPrefillRouteSyncGuardRef, dispatchRoute, localDispatch, setBulkUrls]);

  useEffect(() => {
    profileTargetUrlRef.current = profileLookupKey ? targetUrl.trim() : '';
  }, [profileLookupKey, targetUrl]);

  useLayoutEffect(() => {
    profileRequestRef.current += 1;
    profileDirtyRef.current = false;
    if (!profileLookupKey) {
      localDispatch.setSavedProfileLoaded(false);
      localDispatch.setSavedProfileDomain('');
      localDispatch.setSavedProfileMessage('');
      localDispatch.setRunProfile(defaultRunProfile());
    }
  }, [localDispatch, profileLookupKey]);

  useLayoutEffect(() => {
    memoryRequestRef.current += 1;
    localDispatch.setFieldConfigError('');
    localDispatch.setFieldConfigMessage('');
    localDispatch.setFieldRowMessages({});
    setFieldRows((current) => stripDomainMemoryFieldRows(current));
  }, [domainMemoryLookupKey, localDispatch, setFieldRows]);

  useEffect(() => {
    if (!profileLookupKey) return;
    const requestId = profileRequestRef.current + 1;
    profileRequestRef.current = requestId;
    const timer = window.setTimeout(async () => {
      try {
        const response = await api.getDomainRunProfile({
          url: profileTargetUrlRef.current,
          surface: effectiveSurface,
        });
        if (profileRequestRef.current !== requestId) return;
        const savedProfile = response.saved_run_profile;
        localDispatch.setSavedProfileDomain(response.domain);
        if (savedProfile && !profileDirtyRef.current) {
          localDispatch.setRunProfile(cloneRunProfile(savedProfile));
          localDispatch.setSavedProfileLoaded(true);
          localDispatch.setSavedProfileMessage(
            `Saved domain profile applied for ${response.domain} on ${surfaceLabel(response.surface)}. Explicit edits below override it for this run.`,
          );
        } else {
          localDispatch.setSavedProfileLoaded(Boolean(savedProfile));
          localDispatch.setSavedProfileMessage(
            savedProfile
              ? `Saved domain profile found for ${response.domain}. Your current edits are preserved for this run.`
              : '',
          );
          if (!savedProfile && !profileDirtyRef.current) {
            localDispatch.setRunProfile(defaultRunProfile());
          }
        }
      } catch {
        if (profileRequestRef.current === requestId) {
          localDispatch.setSavedProfileLoaded(false);
          localDispatch.setSavedProfileDomain('');
          localDispatch.setSavedProfileMessage('');
        }
      }
    }, UI_DELAYS.DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [effectiveSurface, localDispatch, profileLookupKey]);

  useEffect(() => {
    if (!domainMemoryLookupKey) return;
    const requestId = memoryRequestRef.current + 1;
    memoryRequestRef.current = requestId;
    const timer = window.setTimeout(async () => {
      localDispatch.setFieldConfigError('');
      try {
        const records = await api.listSelectors({ domain: normalizedTargetDomain });
        if (memoryRequestRef.current !== requestId) return;
        const count = applyMemoryRows(records, effectiveSurface, setFieldRows);
        if (count) {
          localDispatch.setFieldRowMessages({});
        }
      } catch (error) {
        if (memoryRequestRef.current === requestId) {
          localDispatch.setFieldConfigError(
            error instanceof Error ? error.message : 'Unable to load domain memory.',
          );
        }
      }
    }, UI_DELAYS.DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [
    domainMemoryLookupKey,
    effectiveSurface,
    localDispatch,
    normalizedTargetDomain,
    setFieldRows,
  ]);

  const markProfileDirty = useCallback(
    (updater: (current: DomainRunProfile) => DomainRunProfile) => {
      profileDirtyRef.current = true;
      localDispatch.setRunProfile((current) => cloneRunProfile(updater(current)));
    },
    [localDispatch],
  );

  const loadDomainMemoryForUrl = useCallback(
    async (rawUrl: string) => {
      const target = rawUrl.trim();
      const domain = getNormalizedDomain(target);
      if (!target || !domain) return;
      const requestId = memoryRequestRef.current + 1;
      memoryRequestRef.current = requestId;
      localDispatch.setFieldConfigError('');
      try {
        const records = await api.listSelectors({ domain });
        if (memoryRequestRef.current !== requestId) return;
        const count = applyMemoryRows(records, effectiveSurface, setFieldRows);
        if (count) {
          localDispatch.setFieldRowMessages({});
        }
        localDispatch.setFieldConfigMessage(
          count
            ? `Loaded ${count} saved selector${count === 1 ? '' : 's'} from domain memory.`
            : 'No saved domain memory found for this URL.',
        );
      } catch (error) {
        if (memoryRequestRef.current === requestId) {
          localDispatch.setFieldConfigError(
            error instanceof Error ? error.message : 'Unable to load domain memory.',
          );
        }
      }
    },
    [effectiveSurface, localDispatch, setFieldRows],
  );

  return { loadDomainMemoryForUrl, markProfileDirty };
}

function applyMemoryRows(
  records: Awaited<ReturnType<typeof api.listSelectors>>,
  surface: string,
  setFieldRows: Dispatch<SetStateAction<FieldRow[]>>,
) {
  const matchingRecords = selectRelevantSelectorRecords(records, surface);
  if (!matchingRecords.length) {
    setFieldRows((current) => stripDomainMemoryFieldRows(current));
    return 0;
  }
  const incomingRows = matchingRecords.map(buildFieldRowFromSelectorRecord);
  setFieldRows((current) => mergeFieldRows(stripDomainMemoryFieldRows(current), incomingRows));
  return matchingRecords.length;
}
