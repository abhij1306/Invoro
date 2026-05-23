import type { Metadata } from 'next';
import { headers } from 'next/headers';
import Script from 'next/script';
import './globals.css';

// Next.js App Router root layout; invoked by file-system routing.
import { Inter, JetBrains_Mono } from 'next/font/google';

import { AppShell } from '../components/layout/app-shell';
import { QueryProvider } from '../components/ui/query-provider';

const mainFont = Inter({
  subsets: ['latin'],
  weight: ['300', '400', '500', '600', '700', '800'],
  variable: '--font-primary-source',
  display: 'swap',
});

const monoFont = JetBrains_Mono({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-mono-source',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'CrawlerAI',
  description: 'Web crawling and structured data extraction platform.',
};

export default async function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const nonce = (await headers()).get('x-nonce') ?? undefined;

  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <Script src="/theme-init.js" strategy="beforeInteractive" nonce={nonce} />
      </head>
      {/*
        Only apply font variables here, NOT mainFont.className.
        mainFont.className hardcodes a font-family class directly on body,
        bypassing the CSS variable cascade in globals.css entirely.
        The variables are picked up by --font-primary-family and --font-mono-family.
      */}
      <body className={`${mainFont.variable} ${monoFont.variable}`}>
        <div className="noise-overlay" aria-hidden="true" />
        <QueryProvider>
          <AppShell>{children}</AppShell>
        </QueryProvider>
      </body>
    </html>
  );
}
