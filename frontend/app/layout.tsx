import type { Metadata } from 'next';
import Script from 'next/script';
import './globals.css';

// Next.js App Router root layout; invoked by file-system routing.
import { Figtree } from 'next/font/google';
import localFont from 'next/font/local';

import { AppShell } from '../components/layout/app-shell';
import { QueryProvider } from '../components/ui/query-provider';

// Primary UI font — Figtree for premium SaaS aesthetic
const mainFont = Figtree({
  subsets: ['latin'],
  weight: ['300', '400', '500', '600', '700', '800'],
  variable: '--font-primary-source',
  display: 'swap',
});

const monoFont = localFont({
  src: [
    { path: '../public/fonts/Consolas-Regular.ttf', weight: '400', style: 'normal' },
    { path: '../public/fonts/Consolas-Bold.ttf',    weight: '700', style: 'normal' },
  ],
  variable: '--font-consolas',
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
