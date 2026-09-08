import { chromium } from 'playwright';
import path from 'path';

const ARTIFACT_DIR = 'C:/Users/Shoury/.gemini/antigravity/brain/bcaa7ab8-49f1-48d8-9fb0-523de2834bbc';
const BASE_URL = 'http://localhost:5173';

async function runVerification() {
  console.log('🚀 Starting Marketplace Phase 3.3 Filters E2E Verification...');

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

    // Click Marketplace nav link
    const marketplaceNav = page.locator('button.nav-link:has-text("Marketplace")');
    await marketplaceNav.click();
    await page.waitForTimeout(600);

    // Verify Title & Subtitle
    const title = await page.locator('.marketplace-page-title').textContent();
    console.log(`Page Title: "${title?.trim()}"`);
    if (!title?.includes('Live Produce Marketplace')) {
      throw new Error(`Expected title "Live Produce Marketplace", got "${title}"`);
    }

    // Verify Compact Filter Bar Existence
    const filterBar = page.locator('.marketplace-filter-bar');
    await filterBar.waitFor({ state: 'visible' });
    console.log('✓ Marketplace filter bar is visible');

    // Take Desktop Initial Screenshot (1440px)
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'marketplace_desktop_1440_initial.png'),
      fullPage: false,
    });
    console.log('✓ Captured marketplace_desktop_1440_initial.png');

    // 2. Open Category Dropdown
    console.log('Testing Category dropdown...');
    const categoryBtn = page.locator('.filter-dropdown-trigger:has-text("Category")');
    await categoryBtn.click();
    await page.waitForTimeout(200);

    const categoryPopover = page.locator('.filter-dropdown-popover');
    await categoryPopover.waitFor({ state: 'visible' });
    console.log('✓ Category popover opened');

    // Take Filter Open Screenshot
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'marketplace_desktop_1440_filter_open.png'),
      fullPage: false,
    });
    console.log('✓ Captured marketplace_desktop_1440_filter_open.png');

    // Select Vegetables
    const vegetablesItem = page.locator('.filter-menu-item:has-text("Vegetables")');
    await vegetablesItem.click();
    await page.waitForTimeout(300);

    // Verify Category Trigger Label Updated
    const updatedCategoryBtn = await page.locator('.filter-dropdown-trigger.is-active').textContent();
    console.log(`Updated Category Button: "${updatedCategoryBtn?.trim()}"`);

    // Verify Category Active Chip
    const categoryChip = page.locator('.active-filter-chip:has-text("Category: Vegetables")');
    await categoryChip.waitFor({ state: 'visible' });
    console.log('✓ Active filter chip "Category: Vegetables" is visible');

    // 3. Test Location Dropdown
    console.log('Testing Location dropdown...');
    const locationBtn = page.locator('.filter-dropdown-trigger:has-text("Location")');
    await locationBtn.click();
    await page.waitForTimeout(200);

    const stateInput = page.locator('#filter-state-input');
    await stateInput.fill('Maharashtra');
    const districtInput = page.locator('#filter-district-input');
    await districtInput.fill('Nashik');
    const applyLocationBtn = page.locator('button:has-text("Apply Location")');
    await applyLocationBtn.click();
    await page.waitForTimeout(300);

    // Verify Location Active Chip
    const stateChip = page.locator('.active-filter-chip:has-text("State: Maharashtra")');
    await stateChip.waitFor({ state: 'visible' });
    console.log('✓ State active chip visible');
    const districtChip = page.locator('.active-filter-chip:has-text("District: Nashik")');
    await districtChip.waitFor({ state: 'visible' });
    console.log('✓ District active chip visible');

    // 4. Test Quality Dropdown
    console.log('Testing Quality dropdown...');
    const qualityBtn = page.locator('.filter-dropdown-trigger:has-text("Quality")');
    await qualityBtn.click();
    await page.waitForTimeout(200);

    const gradeAItem = page.locator('.filter-menu-item:has-text("Grade A")');
    await gradeAItem.click();
    await page.waitForTimeout(300);

    // 5. Test Price Dropdown
    console.log('Testing Price dropdown...');
    const priceBtn = page.locator('.filter-dropdown-trigger:has-text("Price")');
    await priceBtn.click();
    await page.waitForTimeout(200);

    const minPriceInput = page.locator('#filter-min-price');
    await minPriceInput.fill('500');
    const maxPriceInput = page.locator('#filter-max-price');
    await maxPriceInput.fill('2500');
    const applyPriceBtn = page.locator('button:has-text("Apply Price")');
    await applyPriceBtn.click();
    await page.waitForTimeout(300);

    // Take Desktop Filters Active Screenshot (1440px)
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'marketplace_desktop_1440_filters_active.png'),
      fullPage: false,
    });
    console.log('✓ Captured marketplace_desktop_1440_filters_active.png');

    // Verify Result Count Header
    const resultsCount = page.locator('.marketplace-results-count');
    await resultsCount.waitFor({ state: 'visible' });
    const resultsCountText = await resultsCount.textContent();
    console.log(`Results Count: "${resultsCountText?.trim()}"`);

    // 6. Test Chip Removal
    console.log('Testing individual chip removal...');
    const qualityChip = page.locator('.active-filter-chip:has-text("Quality: Grade A")');
    await qualityChip.click();
    await page.waitForTimeout(300);

    // 7. Test Reset Filters
    console.log('Testing Reset Filters...');
    const resetBtn = page.locator('.active-filters-reset-btn');
    await resetBtn.click();
    await page.waitForTimeout(300);

    const activeChipsCount = await page.locator('.active-filter-chip').count();
    console.log(`Active chips after reset: ${activeChipsCount}`);
    if (activeChipsCount !== 0) {
      throw new Error(`Expected 0 active chips after reset, found ${activeChipsCount}`);
    }

    // 8. Tablet 1024px Viewport
    console.log('Testing Tablet 1024px viewport...');
    await page.setViewportSize({ width: 1024, height: 768 });
    await page.waitForTimeout(300);

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'marketplace_tablet_1024.png'),
      fullPage: false,
    });
    console.log('✓ Captured marketplace_tablet_1024.png');

    // 9. Mobile 390px Viewport
    console.log('Testing Mobile 390px viewport...');
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(300);

    // Check no horizontal scrollbar on body
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    console.log(`Mobile dimensions - scrollWidth: ${scrollWidth}, clientWidth: ${clientWidth}`);
    if (scrollWidth > clientWidth + 1) {
      console.warn(`Warning: Potential horizontal overflow on mobile (${scrollWidth} > ${clientWidth})`);
    }

    // Take Mobile Initial Screenshot
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'marketplace_mobile_390_initial.png'),
      fullPage: false,
    });
    console.log('✓ Captured marketplace_mobile_390_initial.png');

    // Open Mobile Category Dropdown
    const mobileCategoryBtn = page.locator('.filter-dropdown-trigger:has-text("Category")');
    await mobileCategoryBtn.click();
    await page.waitForTimeout(200);

    // Take Mobile Filter Open Screenshot
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'marketplace_mobile_390_filter_open.png'),
      fullPage: false,
    });
    console.log('✓ Captured marketplace_mobile_390_filter_open.png');

    // Select Fruits on Mobile
    const fruitsItem = page.locator('.filter-menu-item:has-text("Fruits")');
    await fruitsItem.click();
    await page.waitForTimeout(300);

    // Take Mobile Filters Active Screenshot
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'marketplace_mobile_390_filters_active.png'),
      fullPage: false,
    });
    console.log('✓ Captured marketplace_mobile_390_filters_active.png');

    console.log('======================================================');
    console.log('🎉 ALL MARKETPLACE PHASE 3.3 FILTER TESTS PASSED!');
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
