import { createClient } from 'redis';

const cache = createClient({ url: process.env.REDIS_URL });
await cache.set(`sess:${id}`, token, { EX: 3600 });


import { test, expect } from '@playwright/test';

test('checkout', async ({ page }) => {
  await page.goto('/cart');
  await expect(page.getByText('Total')).toBeVisible();
});
