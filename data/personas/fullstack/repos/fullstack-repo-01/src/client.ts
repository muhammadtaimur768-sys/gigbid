import { test, expect } from '@playwright/test';

test('checkout', async ({ page }) => {
  await page.goto('/cart');
  await expect(page.getByText('Total')).toBeVisible();
});


// docker compose up -d db cache api
export const SERVICES = ['db', 'cache', 'api'];
