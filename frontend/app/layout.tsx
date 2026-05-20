import type { Metadata } from 'next';
import Script from 'next/script';
import './globals.css';

// Next.js App Router root layout; invoked by file-system routing.
import { Inconsolata, Manrope } from 'next/font/google';

import { AppShell } from '../components/layout/app-shell';
import { QueryProvider } from '../components/ui/query-provider';

// Primary UI font — Manrope for premium SaaS aesthetic
const mainFont = Manrope({
  subsets: ['latin'],
  weight: ['300', '400', '500', '600', '700', '800'],
  variable: '--font-primary-source',
  display: 'swap',
});

const monoFont = Inconsolata({
  subsets: ['latin'],
  variable: '--font-inconsolata',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'CrawlerAI',
  description: 'Web crawling and structured data extraction platform.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <Script src="/theme-init.js" strategy="beforeInteractive" />
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
