import { createServer } from 'node:http';

createServer((req, res) => res.end('ok')).listen(3000);


import { test, expect } from '@playwright/test';

test('checkout', async ({ page }) => {
  await page.goto('/cart');
  await expect(page.getByText('Total')).toBeVisible();
});
