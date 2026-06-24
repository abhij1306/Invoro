import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { DomainRunProfile } from '../../lib/api/types';
import { UI_DELAYS } from '../../lib/constants/timing';
import { TopBarProvider } from '../layout/top-bar-context';
import { CrawlConfigScreen } from './crawl-config-screen';

const { replaceMock, refreshMock, createCrawlMock, getDomainRunProfileMock, listSelectorsMock } =
  vi.hoisted(() => ({
    replaceMock: vi.fn(),
    refreshMock: vi.fn(),
    createCrawlMock: vi.fn(),
    getDomainRunProfileMock: vi.fn(),
    listSelectorsMock: vi.fn(),
  }));

vi.mock('next/navigation', () => ({
  usePathname: () => '/crawl',
  useRouter: () => ({
    replace: replaceMock,
    refresh: refreshMock,
  }),
}));

vi.mock('../../lib/api', () => ({
  api: {
    createCrawl: createCrawlMock,
    getDomainRunProfile: getDomainRunProfileMock,
    listSelectors: listSelectorsMock,
  },
}));

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
}

function runProfile(fetchMode: DomainRunProfile['fetch_profile']['fetch_mode']): DomainRunProfile {
  return {
    version: 1,
    fetch_profile: {
      fetch_mode: fetchMode,
      extraction_source: 'raw_html',
      js_mode: 'auto',
      include_iframes: false,
      traversal_mode: null,
      request_delay_ms: 1200,
      host_memory_ttl_seconds: 600,
    },
    locality_profile: {
      geo_country: 'auto',
      language_hint: null,
      currency_hint: null,
    },
    diagnostics_profile: {
      capture_html: true,
      capture_screenshot: false,
      capture_network: 'matched_only',
      capture_response_headers: true,
      capture_browser_diagnostics: true,
    },
    acquisition_contract: {
      preferred_browser_engine: 'auto',
      prefer_browser: fetchMode === 'browser_only',
      prefer_curl_handoff: false,
      handoff_cookie_engine: 'auto',
      last_quality_success: null,
      stale_after_failures: {
        failure_count: 0,
        stale: false,
      },
    },
    source_run_id: 17,
    saved_at: '2026-06-20T00:00:00Z',
  };
}

function renderScreen(
  props: {
    requestedTab?: 'category' | 'pdp' | null;
    requestedCategoryMode?: 'single' | 'sitemap' | 'bulk' | null;
    requestedPdpMode?: 'single' | 'batch' | 'csv' | null;
  } = {},
) {
  return render(
    <TopBarProvider>
      <CrawlConfigScreen
        requestedTab={props.requestedTab ?? null}
        requestedCategoryMode={props.requestedCategoryMode ?? null}
        requestedPdpMode={props.requestedPdpMode ?? null}
      />
    </TopBarProvider>,
  );
}

function enterTargetUrl(url: string) {
  fireEvent.change(screen.getByLabelText('Target URL input'), {
    target: { value: url },
  });
}

async function waitForProfileLookup(url: string, surface: string) {
  await waitFor(
    () => {
      expect(getDomainRunProfileMock).toHaveBeenCalledWith({ url, surface });
    },
    { timeout: UI_DELAYS.DEBOUNCE_MS * 6 },
  );
}

function openAdvancedSettings() {
  fireEvent.click(screen.getByRole('button', { name: 'Advanced' }));
}

function selectFetchMode(label: string) {
  fireEvent.click(screen.getByRole('combobox', { name: 'Fetch mode' }));
  fireEvent.click(screen.getByRole('option', { name: label }));
}

function selectCommerceCategory() {
  fireEvent.click(screen.getByRole('combobox', { name: 'Domain' }));
  fireEvent.click(screen.getByRole('option', { name: 'Commerce' }));
  fireEvent.click(screen.getByRole('button', { name: 'Category Crawl' }));
}

describe('CrawlConfigScreen profile loading and dispatch behavior', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.sessionStorage.clear();
    window.history.replaceState(null, '', '/crawl');
    listSelectorsMock.mockResolvedValue([]);
    getDomainRunProfileMock.mockResolvedValue({
      domain: 'example.com',
      surface: 'ecommerce_listing',
      saved_run_profile: null,
    });
    createCrawlMock.mockResolvedValue({ run_id: 321 });
  });

  it('loads a saved domain run profile into a clean configuration', async () => {
    getDomainRunProfileMock.mockResolvedValue({
      domain: 'example.com',
      surface: 'ecommerce_listing',
      saved_run_profile: runProfile('browser_only'),
    });

    renderScreen();
    enterTargetUrl('https://example.com/collections/chairs');

    await waitForProfileLookup('https://example.com/collections/chairs', 'ecommerce_listing');
    expect(
      await screen.findByText(/Saved domain profile applied for example\.com/),
    ).toBeInTheDocument();

    openAdvancedSettings();
    expect(screen.getByRole('combobox', { name: 'Fetch mode' })).toHaveTextContent('Browser Only');
    expect(screen.getByLabelText('Host memory TTL seconds')).toHaveValue(600);
  });

  it('does not let a late profile response overwrite dirty user edits', async () => {
    const lookup = deferred<{
      domain: string;
      surface: string;
      saved_run_profile: DomainRunProfile;
    }>();
    getDomainRunProfileMock.mockReturnValue(lookup.promise);

    renderScreen();
    enterTargetUrl('https://example.com/collections/chairs');
    openAdvancedSettings();
    selectFetchMode('HTTP Only');

    await waitForProfileLookup('https://example.com/collections/chairs', 'ecommerce_listing');
    lookup.resolve({
      domain: 'example.com',
      surface: 'ecommerce_listing',
      saved_run_profile: runProfile('browser_only'),
    });

    expect(
      await screen.findByText(/Your current edits are preserved for this run/),
    ).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'Fetch mode' })).toHaveTextContent('HTTP Only');
  });

  it('ignores stale profile responses after rapid route tab changes', async () => {
    const listingLookup = deferred<{
      domain: string;
      surface: string;
      saved_run_profile: DomainRunProfile;
    }>();
    const detailLookup = deferred<{
      domain: string;
      surface: string;
      saved_run_profile: DomainRunProfile;
    }>();
    getDomainRunProfileMock.mockImplementation(({ surface }: { surface: string }) =>
      surface === 'ecommerce_listing' ? listingLookup.promise : detailLookup.promise,
    );

    renderScreen();
    selectCommerceCategory();
    enterTargetUrl('https://example.com/page');
    await waitForProfileLookup('https://example.com/page', 'ecommerce_listing');

    fireEvent.click(screen.getByRole('button', { name: 'PDP Crawl' }));
    await waitForProfileLookup('https://example.com/page', 'ecommerce_detail');

    detailLookup.resolve({
      domain: 'example.com',
      surface: 'ecommerce_detail',
      saved_run_profile: runProfile('http_only'),
    });
    expect(
      await screen.findByText(/Saved domain profile applied for example\.com on Commerce Detail/),
    ).toBeInTheDocument();

    listingLookup.resolve({
      domain: 'example.com',
      surface: 'ecommerce_listing',
      saved_run_profile: runProfile('browser_only'),
    });

    openAdvancedSettings();
    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: 'Fetch mode' })).toHaveTextContent('HTTP Only');
    });
  });

  it('ignores stale domain-memory responses after rapid route tab changes', async () => {
    const listingMemory = deferred<
      Array<{
        id: number;
        field_name: string;
        surface: string;
        is_active: boolean;
        css_selector: string;
      }>
    >();
    const detailMemory = deferred<
      Array<{
        id: number;
        field_name: string;
        surface: string;
        is_active: boolean;
        css_selector: string;
      }>
    >();
    listSelectorsMock
      .mockReturnValueOnce(listingMemory.promise)
      .mockReturnValueOnce(detailMemory.promise);

    renderScreen();
    selectCommerceCategory();
    enterTargetUrl('https://example.com/page');
    await waitFor(() => {
      expect(listSelectorsMock).toHaveBeenCalledTimes(1);
    });

    fireEvent.click(screen.getByRole('button', { name: 'PDP Crawl' }));
    await waitFor(() => {
      expect(listSelectorsMock).toHaveBeenCalledTimes(2);
    });

    detailMemory.resolve([
      {
        id: 22,
        field_name: 'detail_price',
        surface: 'ecommerce_detail',
        is_active: true,
        css_selector: '.detail-price',
      },
    ]);
    listingMemory.resolve([
      {
        id: 11,
        field_name: 'listing_price',
        surface: 'ecommerce_listing',
        is_active: true,
        css_selector: '.listing-price',
      },
    ]);

    openAdvancedSettings();
    expect(await screen.findByDisplayValue('detail_price')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByDisplayValue('listing_price')).not.toBeInTheDocument();
    });
  });

  it('retains usable defaults when profile loading fails', async () => {
    getDomainRunProfileMock.mockRejectedValue(new Error('Profile unavailable'));

    renderScreen();
    enterTargetUrl('https://example.com/collections/chairs');
    await waitForProfileLookup('https://example.com/collections/chairs', 'ecommerce_listing');

    openAdvancedSettings();
    expect(screen.getByRole('combobox', { name: 'Fetch mode' })).toHaveTextContent('Auto');
    expect(screen.getByLabelText('Host memory TTL seconds')).toHaveValue(null);
    expect(screen.queryByText(/Saved domain profile/)).not.toBeInTheDocument();
  });

  it('prevents duplicate submits while a crawl dispatch is pending', async () => {
    const dispatch = deferred<{ run_id: number }>();
    createCrawlMock.mockReturnValue(dispatch.promise);

    renderScreen();
    enterTargetUrl('https://example.com/collections/chairs');

    const submit = screen.getByRole('button', { name: 'Start Crawl' });
    fireEvent.click(submit);
    fireEvent.click(submit);

    await waitFor(() => {
      expect(createCrawlMock).toHaveBeenCalledTimes(1);
    });

    dispatch.resolve({ run_id: 321 });
    await waitFor(() => {
      expect(replaceMock).toHaveBeenCalledWith('/crawl?run_id=321');
    });
  });

  it('retains entered values and shows the existing error after failed dispatch', async () => {
    createCrawlMock.mockRejectedValue(new Error('Unable to queue crawl.'));

    renderScreen();
    enterTargetUrl('https://example.com/collections/chairs');
    fireEvent.click(screen.getByRole('button', { name: 'Start Crawl' }));

    expect(await screen.findByText('Unable to queue crawl.')).toBeInTheDocument();
    expect(screen.getByLabelText('Target URL input')).toHaveValue(
      'https://example.com/collections/chairs',
    );
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it('preserves the current dispatch payload and navigation behavior on success', async () => {
    renderScreen();
    enterTargetUrl('https://example.com/collections/chairs');
    fireEvent.click(screen.getByRole('button', { name: 'Start Crawl' }));

    await waitFor(() => {
      expect(createCrawlMock).toHaveBeenCalledWith({
        run_type: 'crawl',
        url: 'https://example.com/collections/chairs',
        urls: undefined,
        surface: 'auto',
        additional_fields: [],
        settings: expect.objectContaining({
          advanced_enabled: false,
          advanced_mode: null,
          crawl_module: 'category',
          crawl_mode: 'single',
          additional_fields: [],
          fetch_profile: expect.objectContaining({
            fetch_mode: 'auto',
            traversal_mode: null,
          }),
        }),
      });
      expect(replaceMock).toHaveBeenCalledWith('/crawl?run_id=321');
      expect(refreshMock).toHaveBeenCalledTimes(1);
    });
  });

  it('initializes the route-requested PDP batch tab', () => {
    renderScreen({ requestedTab: 'pdp', requestedPdpMode: 'batch' });

    expect(screen.getByLabelText('Bulk URLs input')).toBeInTheDocument();
    expect(screen.queryByLabelText('Target URL input')).not.toBeInTheDocument();
  });
});
