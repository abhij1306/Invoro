import { expect, test } from '@playwright/test';

const now = '2026-05-19T10:00:00Z';

test('projects: create project, launch workflow, view results, and promote', async ({ page }) => {
  const project = {
    id: 501,
    user_id: 1,
    name: 'Competitive pricing watch',
    description: '',
    competitors: ['myntra.com'],
    category: 'jeans',
    tracked_fields: ['price', 'was_price', 'availability', 'title'],
    archived: false,
    created_at: now,
    updated_at: now,
  };
  const workflow = {
    id: 701,
    user_id: 1,
    project_id: project.id,
    template_id: 'competitive_pricing_snapshot',
    template_version: 'v1',
    label: project.name,
    status: 'completed',
    intent_inputs: {},
    advanced_overrides: {},
    pipeline_config: {},
    summary: {},
    monitor_id: null,
    completed_at: now,
    created_at: now,
    updated_at: now,
    steps: [
      {
        id: 801,
        workflow_id: 701,
        step_id: 'listing_run',
        step_type: 'crawl',
        status: 'completed',
        run_id: 901,
        inputs: {},
        outputs: {},
        error: null,
        created_at: now,
        updated_at: now,
      },
      {
        id: 802,
        workflow_id: 701,
        step_id: 'detail_run',
        step_type: 'crawl',
        status: 'completed',
        run_id: 902,
        inputs: {},
        outputs: {},
        error: null,
        created_at: now,
        updated_at: now,
      },
      {
        id: 803,
        workflow_id: 701,
        step_id: 'comparison_view',
        step_type: 'view',
        status: 'completed',
        run_id: null,
        inputs: {},
        outputs: {},
        error: null,
        created_at: now,
        updated_at: now,
      },
    ],
  };

  await page.route('**/api/auth/me', async (route) => {
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
  });
  await page.route('**/api/orchestration/projects', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify(project),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([project]),
    });
  });
  await page.route('**/api/orchestration/projects/501', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(project),
    });
  });
  await page.route('**/api/orchestration/workflows?project_id=501', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([workflow]),
    });
  });
  await page.route('**/api/orchestration/workflows', async (route) => {
    const payload = route.request().postDataJSON();
    expect(payload.intent_inputs.listing_url).toBe('https://www.myntra.com/men-jeans');
    expect(payload.intent_inputs.competitors).toBeUndefined();
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify(workflow),
    });
  });
  await page.route('**/api/orchestration/workflows/701/status', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(workflow),
    });
  });
  await page.route('**/api/orchestration/workflows/701/results/price-comparison', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        workflow_id: 701,
        project_id: 501,
        detail_run_id: 902,
        rows: [
          {
            record_id: 1,
            run_id: 902,
            product: 'Slim jeans',
            brand: 'Demo',
            domain: 'myntra.com',
            price: '1299',
            was_price: '1599',
            currency: 'INR',
            availability: 'in_stock',
            source_url: 'https://www.myntra.com/jeans/demo/demo-slim-jeans/12345/buy',
          },
        ],
        export_csv_url: '/api/crawls/902/export.csv',
        export_json_url: '/api/crawls/902/export.json',
        crawl_studio_url: '/crawl?run_id=902',
      }),
    });
  });
  await page.route('**/api/orchestration/workflows/701/promote', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        workflow_id: 701,
        monitor_id: 601,
        url_count: 1,
        tracked_fields: project.tracked_fields,
      }),
    });
  });

  await page.goto('/projects/new');
  await page.getByLabel('Listing URL').fill('https://www.myntra.com/men-jeans');
  await page.getByRole('button', { name: 'Launch Project' }).click();

  await expect(page).toHaveURL(/\/projects\/501$/);
  await expect(page.getByText('Workflow')).toBeVisible();
  await expect(page.getByText('Slim jeans')).toBeVisible();
  await expect(page.getByText('1299')).toBeVisible();
  await expect(
    page.getByRole('banner').getByRole('link', { name: 'Crawl Studio' }),
  ).toHaveAttribute('href', '/crawl?run_id=902');

  await page.getByRole('button', { name: 'Promote' }).click();
  await expect(page.getByText('Monitor created - monitor_id: 601')).toBeVisible();
});
