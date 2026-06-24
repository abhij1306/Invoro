import { describe, expect, it } from 'vitest';

import nextConfig, { buildSecurityHeaders } from '../next.config';
import { buildContentSecurityPolicy } from '../proxy';

describe('next security headers', () => {
  it('includes the baseline security headers for all routes', async () => {
    const routeHeaders = await nextConfig.headers?.();

    expect(routeHeaders).toBeDefined();
    expect(routeHeaders?.[0]?.source).toBe('/(.*)');
    expect(routeHeaders?.[0]?.headers).toEqual(
      expect.arrayContaining([
        { key: 'X-Content-Type-Options', value: 'nosniff' },
        { key: 'X-Frame-Options', value: 'DENY' },
        { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
        { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
      ]),
    );
  });

  it('adds HSTS only in production builds', () => {
    const nonProductionHeaders = buildSecurityHeaders(false);
    const productionHeaders = buildSecurityHeaders(true);

    expect(nonProductionHeaders.find((header) => header.key === 'Strict-Transport-Security')).toBe(
      undefined,
    );
    expect(productionHeaders).toContainEqual({
      key: 'Strict-Transport-Security',
      value: 'max-age=31536000; includeSubDomains; preload',
    });
    expect(productionHeaders.find((header) => header.key === 'Content-Security-Policy')).toBe(
      undefined,
    );
  });

  it('builds CSP with a nonce and app runtime allowances', () => {
    const policy = buildContentSecurityPolicy('test-nonce');

    expect(policy).toContain("script-src 'self' 'nonce-test-nonce'");
    expect(policy).toContain("style-src 'self' 'nonce-test-nonce' 'unsafe-inline'");
    expect(policy).toContain('img-src ');
    expect(policy).toContain('https:');
    expect(policy).toContain('http:');
  });

  it('includes configured API origins in CSP connect-src', () => {
    const originalApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
    process.env.NEXT_PUBLIC_API_BASE_URL = 'https://api.example.com:8443/';

    try {
      const policy = buildContentSecurityPolicy('test-nonce');

      expect(policy).toContain(
        "connect-src 'self' https://api.example.com:8443 wss://api.example.com:8443",
      );
    } finally {
      if (originalApiBaseUrl) {
        process.env.NEXT_PUBLIC_API_BASE_URL = originalApiBaseUrl;
      } else {
        delete process.env.NEXT_PUBLIC_API_BASE_URL;
      }
    }
  });
});
