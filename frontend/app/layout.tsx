import type { Metadata, Viewport } from 'next';
import { headers } from 'next/headers';
import localFont from 'next/font/local';
import Script from 'next/script';
import './globals.css';

// Next.js App Router root layout; invoked by file-system routing.
import { Geist_Mono } from 'next/font/google';

import { AppShell } from '../components/layout/app-shell';
import { QueryProvider } from '../components/ui/query-provider';

const primaryFont = localFont({
  src: [
    { path: './fonts/Switzer-Variable.woff2', style: 'normal', weight: '100 900' },
    { path: './fonts/Switzer-VariableItalic.woff2', style: 'italic', weight: '100 900' },
  ],
  variable: '--font-primary-source',
  display: 'swap',
});

const displayFont = localFont({
  src: [
    { path: './fonts/Satoshi-Variable.woff2', style: 'normal', weight: '300 900' },
    { path: './fonts/Satoshi-VariableItalic.woff2', style: 'italic', weight: '300 900' },
  ],
  variable: '--font-display-source',
  display: 'swap',
});

const monoFont = Geist_Mono({
  subsets: ['latin'],
  variable: '--font-mono-source',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Invoro',
  description: 'AI commerce intelligence and structured extraction platform.',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover',
};

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const nonce = (await headers()).get('x-nonce') ?? undefined;

  return (
    <html
      lang="en"
      className={`${primaryFont.variable} ${displayFont.variable} ${monoFont.variable}`}
      suppressHydrationWarning
    >
      <head>
        <Script src="/theme-init.js" strategy="beforeInteractive" nonce={nonce} />
      </head>
      <body>
        <div className="noise-overlay" aria-hidden="true" />
        <QueryProvider>
          <AppShell>{children}</AppShell>
        </QueryProvider>
      </body>
    </html>
  );
}
