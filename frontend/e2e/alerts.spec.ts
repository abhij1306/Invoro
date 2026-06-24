import { expect, test } from '@playwright/test';

const now = '2026-05-20T10:00:00Z';

const alert = {
  id: 42,
  url: 'https://web-scraping.dev/product/1',
  domain: 'web-scraping.dev',
  surface: 'ecommerce_detail',
  target_fields: ['price', 'availability'],
  condition: 'price < 20',
  webhook_url: 'https://agent.example/webhook',
  poll_interval_seconds: 300,
  status: 'active',
  last_checked_at: now,
  last_known_values: {
    price: '19.99',
    availability: 'in_stock',
  },
  last_error: null,
  last_crawl_method: 'test',
  created_at: now,
  updated_at: now,
};

test('alerts: create uses alert API paths and opens alert detail', async ({ page }) => {
  const apiPaths: string[] = [];

  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    apiPaths.push(url.pathname);

    if (url.pathname.includes('/watches')) {
      await route.fulfill({ status: 500, body: 'legacy watches route used' });
      return;
    }

    if (url.pathname === '/api/auth/me') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 1,
          email: 'qa@example.com',
          role: 'admin',
          is_active: true,
          created_at: now,
          updated_at: now,
        }),
      });
      return;
    }

    if (url.pathname === '/api/monitors') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
      return;
    }

    if (url.pathname === '/api/alerts' && request.method() === 'POST') {
      const payload = request.postDataJSON();
      expect(payload.url).toBe(alert.url);
      expect(payload.target_fields).toEqual(alert.target_fields);
      expect(payload.condition).toBe(alert.condition);
      expect(payload.webhook_url).toBe(alert.webhook_url);
      expect(payload.poll_interval_seconds).toBe(alert.poll_interval_seconds);
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(alert),
      });
      return;
    }

    if (url.pathname === '/api/alerts/42') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(alert),
      });
      return;
    }

    if (url.pathname === '/api/monitors/42/events') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], total: 0, page: 1, page_size: 50 }),
      });
      return;
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({}) });
  });

  await page.goto('/alerts/new');
  await page.getByLabel('URL', { exact: true }).fill(alert.url);
  await page.getByLabel('Condition').fill(alert.condition);
  await page.getByLabel('Webhook URL').fill(alert.webhook_url);
  await page.getByRole('button', { name: 'Create Alert' }).click();

  await expect(page).toHaveURL(/\/alerts\/42$/);
  await expect(page.getByText('Product Alert').first()).toBeVisible();
  await expect(page.getByText('web-scraping.dev/product/1').first()).toBeVisible();
  expect(apiPaths).toContain('/api/alerts');
  expect(apiPaths).toContain('/api/alerts/42');
  expect(apiPaths.some((path) => path.includes('/watches'))).toBe(false);
});
