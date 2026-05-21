import type { NextConfig } from 'next';

export function buildSecurityHeaders(isProduction: boolean) {
  const headers = [
    { key: 'X-Content-Type-Options', value: 'nosniff' },
    { key: 'X-Frame-Options', value: 'DENY' },
    { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
    { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
  ];
  if (isProduction) {
    headers.push({
      key: 'Content-Security-Policy',
      value:
        "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; base-uri 'self'; frame-ancestors 'none'; object-src 'none'",
    });
    headers.push({
      key: 'Strict-Transport-Security',
      value: 'max-age=31536000; includeSubDomains; preload',
    });
  }
  return headers;
}

const nextConfig: NextConfig = {
  allowedDevOrigins: ['127.0.0.1', 'localhost'],
  typedRoutes: true,
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: buildSecurityHeaders(process.env.NODE_ENV === 'production'),
      },
    ];
  },
};

export default nextConfig;
