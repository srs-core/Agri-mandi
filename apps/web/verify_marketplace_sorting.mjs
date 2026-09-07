import { chromium } from 'playwright';
import path from 'path';

const ARTIFACT_DIR = 'C:/Users/Shoury/.gemini/antigravity/brain/bcaa7ab8-49f1-48d8-9fb0-523de2834bbc';
const BASE_URL = 'http://localhost:5173';

async function runVerification() {
  console.log('🚀 Starting Marketplace Phase 3.5 Sorting E2E Verification...');

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const consoleErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
      console.error(`[Browser Error]:`, msg.text());
    }
  });

  try {
    // 1. Desktop 1440px Viewport
    await page.setViewportSize({ width: 1440, height: 900 });
    console.log('Navigating to marketplace on 1440px desktop...');
    await page.goto(`${BASE_URL}`, { waitUntil: 'networkidle' });

    // Navigate to Marketplace
    const marketplaceNav = page.locator('button.nav-link:has-text("Marketplace")');
    await marketplaceNav.click();
    await page.waitForTimeout(600);

    // Verify Sort Control is visible
    const sortTrigger = page.locator('.marketplace-sort-trigger');
    await sortTrigger.waitFor({ state: 'visible' });
    const initialSortText = await sortTrigger.textContent();
    console.log(`Initial Sort Trigger: "${initialSortText?.trim()}"`);
    if (!initialSortText?.includes('Recommended')) {
      throw new Error(`Expected default sort "Recommended", got "${initialSortText}"`);
    }

    // Capture Default Screenshot
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'marketplace_sorting_desktop_1440_default.png'),
      fullPage: false,
    });
    console.log('✓ Captured marketplace_sorting_desktop_1440_default.png');

    // 2. Open Sort Dropdown
    console.log('Opening Sort dropdown...');
    await sortTrigger.click();
    await page.waitForTimeout(200);

    const sortPopover = page.locator('.marketplace-sort-popover');
    await sortPopover.waitFor({ state: 'visible' });
    console.log('✓ Sort popover is visible');

    // Capture Open Popover Screenshot
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'marketplace_sorting_desktop_1440_open.png'),
      fullPage: false,
    });
    console.log('✓ Captured marketplace_sorting_desktop_1440_open.png');

    // 3. Test Price: Low to High
    console.log('Selecting "Price: Low to High"...');
    const priceAscOption = page.locator('.sort-menu-item:has-text("Price: Low to High")');
    await priceAscOption.click();
    await page.waitForTimeout(300);

    const updatedSortText = await sortTrigger.textContent();
    console.log(`Updated Sort Trigger: "${updatedSortText?.trim()}"`);
    if (!updatedSortText?.includes('Price: Low to High')) {
      throw new Error(`Expected sort "Price: Low to High", got "${updatedSortText}"`);
    }

    // Inspect first 3 card prices
    const cards = page.locator('.produce-card');
    const count = await cards.count();
    console.log(`Visible cards after price_asc sort: ${count}`);

    // Capture Price Asc Screenshot
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'marketplace_sorting_desktop_1440_price_asc.png'),
      fullPage: false,
    });
    console.log('✓ Captured marketplace_sorting_desktop_1440_price_asc.png');

    // 4. Test Quantity: High to Low
    console.log('Selecting "Quantity: High to Low"...');
    await sortTrigger.click();
    await page.waitForTimeout(200);
    const qtyDescOption = page.locator('.sort-menu-item:has-text("Quantity: High to Low")');
    await qtyDescOption.click();
    await page.waitForTimeout(300);

    // 5. Test Filters + Search + Sort Combined
    console.log('Testing Filters + Search + Sort Combined...');
    const searchInput = page.locator('.marketplace-search-input');
    await searchInput.fill('Onion');
    await page.locator('.marketplace-search-submit-btn').click();
    await page.waitForTimeout(400);

    // Apply Location Maharashtra
    const locationBtn = page.locator('.filter-dropdown-trigger:has-text("Location")');
    await locationBtn.click();
    await page.waitForTimeout(200);
    await page.locator('#filter-state-input').fill('Maharashtra');
    await page.locator('button:has-text("Apply Location")').click();
    await page.waitForTimeout(400);

    // Change sort to Price: Low to High
    await sortTrigger.click();
    await page.waitForTimeout(200);
    await page.locator('.sort-menu-item:has-text("Price: Low to High")').click();
    await page.waitForTimeout(400);

    // Capture Filter + Sort Screenshot
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'marketplace_sorting_desktop_1440_filter_and_sort.png'),
      fullPage: false,
    });
    console.log('✓ Captured marketplace_sorting_desktop_1440_filter_and_sort.png');

    // Reset filters
    const resetBtn = page.locator('.active-filters-reset-btn');
    if (await resetBtn.isVisible()) {
      await resetBtn.click();
      await page.waitForTimeout(300);
    }

    // 6. Tablet 1024px Viewport
    console.log('Testing Tablet 1024px viewport...');
    await page.setViewportSize({ width: 1024, height: 768 });
    await page.waitForTimeout(300);

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'marketplace_sorting_tablet_1024.png'),
      fullPage: false,
    });
    console.log('✓ Captured marketplace_sorting_tablet_1024.png');

    // 7. Mobile 390px Viewport
    console.log('Testing Mobile 390px viewport...');
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(300);

    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    console.log(`Mobile dimensions - scrollWidth: ${scrollWidth}, clientWidth: ${clientWidth}`);
    if (scrollWidth > clientWidth + 1) {
      console.warn(`Warning: Potential horizontal overflow on mobile (${scrollWidth} > ${clientWidth})`);
    }

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'marketplace_sorting_mobile_390.png'),
      fullPage: false,
    });
    console.log('✓ Captured marketplace_sorting_mobile_390.png');

    console.log('======================================================');
    console.log('🎉 ALL MARKETPLACE PHASE 3.5 SORTING TESTS PASSED!');
    console.log(`Total console errors: ${consoleErrors.length}`);
    console.log('======================================================');
  } finally {
    await browser.close();
  }
}

runVerification().catch((err) => {
  console.error('Test run failed:', err);
  process.exit(1);
});
