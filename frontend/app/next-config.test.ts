import { describe, expect, it } from 'vitest';

import nextConfig, { buildSecurityHeaders } from '../next.config';

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
      value: 'max-age=31536000; includeSubDomains',
    });
    expect(productionHeaders.some((header) => header.key === 'Content-Security-Policy')).toBe(false);
  });
});
