import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  retries: 1,
  use: {
    baseURL: 'http://127.0.0.1:4000',
    trace: 'on-first-retry',
  },
  webServer: {
    command: 'pnpm run dev',
    url: 'http://127.0.0.1:4000',
    reuseExistingServer: true,
    env: {
      NEXT_PUBLIC_API_BASE_URL: 'http://127.0.0.1:9000',
    },
  },
});
