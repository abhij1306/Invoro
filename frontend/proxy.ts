import { NextResponse, type NextRequest } from 'next/server';

export const CSP_NONCE_HEADER = 'x-nonce';

function configuredApiCspSources() {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!configured) {
    return [];
  }

  let apiUrl: URL;
  try {
    apiUrl = new URL(configured);
  } catch {
    return [];
  }
  if (apiUrl.protocol !== 'http:' && apiUrl.protocol !== 'https:') {
    return [];
  }

  const wsProtocol = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  return [`${apiUrl.protocol}//${apiUrl.host}`, `${wsProtocol}//${apiUrl.host}`];
}

export function createNonce() {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes));
}

export function buildContentSecurityPolicy(nonce: string) {
  const connectSources = ["'self'", ...configuredApiCspSources()];
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}'`,
    `style-src 'self' 'nonce-${nonce}' 'unsafe-inline'`,
    "img-src 'self' data: blob: https: http:",
    "font-src 'self' data:",
    `connect-src ${connectSources.join(' ')}`,
    "base-uri 'self'",
    "frame-ancestors 'none'",
    "object-src 'none'",
  ].join('; ');
}

export function proxy(request: NextRequest) {
  if (process.env.NODE_ENV !== 'production') {
    return NextResponse.next();
  }

  const nonce = createNonce();
  const contentSecurityPolicy = buildContentSecurityPolicy(nonce);
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set(CSP_NONCE_HEADER, nonce);

  const response = NextResponse.next({
    request: {
      headers: requestHeaders,
    },
  });
  response.headers.set(CSP_NONCE_HEADER, nonce);
  response.headers.set('Content-Security-Policy', contentSecurityPolicy);
  return response;
}

export const config = {
  matcher: [
    {
      source: '/((?!api|_next/static|_next/image|favicon.ico).*)',
    },
  ],
};
