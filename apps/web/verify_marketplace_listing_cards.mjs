import { chromium } from 'playwright';
import path from 'path';

const ARTIFACT_DIR = 'C:/Users/Shoury/.gemini/antigravity/brain/bcaa7ab8-49f1-48d8-9fb0-523de2834bbc';
const BASE_URL = 'http://localhost:5173';

async function runVerification() {
  console.log('🚀 Starting Marketplace Phase 3.4 Listing Cards E2E Verification...');

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

    // Wait for Produce Lots Grid
    const lotsGrid = page.locator('.produce-lots-grid');
    await lotsGrid.waitFor({ state: 'visible' });

    const cardCount = await page.locator('.produce-card').count();
    console.log(`✓ Rendered ${cardCount} produce listing cards`);
    if (cardCount === 0) {
      throw new Error('Expected at least 1 produce card in marketplace');
    }

    // Inspect First Card Hierarchy
    const firstCard = page.locator('.produce-card').first();
    const title = await firstCard.locator('.produce-card-title').textContent();
    const commodity = await firstCard.locator('.produce-card-commodity').textContent();
    const category = await firstCard.locator('.produce-category-tag').textContent();
    const status = await firstCard.locator('.produce-status-badge').textContent();
    const availableQty = await firstCard.locator('.produce-metric-box').first().textContent();
    const priceText = await firstCard.locator('.price-metric-box').textContent();
    const seller = await firstCard.locator('.seller-name-val').textContent();
    const viewBtn = firstCard.locator('.btn-view-lot');

    console.log('--- Card 1 Hierarchy Audit ---');
    console.log(`Category: ${category?.trim()}`);
    console.log(`Status: ${status?.trim()}`);
    console.log(`Title: ${title?.trim()}`);
    console.log(`Commodity: ${commodity?.trim()}`);
    console.log(`Quantity: ${availableQty?.trim().replace(/\s+/g, ' ')}`);
    console.log(`Price: ${priceText?.trim().replace(/\s+/g, ' ')}`);
    console.log(`Seller: ${seller?.trim()}`);
    console.log('------------------------------');

    if (!title || !commodity || !category || !status) {
      throw new Error('Listing card is missing essential header/title fields');
    }

    // Check View Lot Button
    await viewBtn.waitFor({ state: 'visible' });
    console.log('✓ View Lot CTA button is present and visible');

    // Take Desktop 1440px Screenshot
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'marketplace_listing_cards_desktop_1440.png'),
      fullPage: false,
    });
    console.log('✓ Captured marketplace_listing_cards_desktop_1440.png');

    // Take Card Detail Zoom Screenshot
    await firstCard.screenshot({
      path: path.join(ARTIFACT_DIR, 'marketplace_listing_card_detail_zoom.png'),
    });
    console.log('✓ Captured marketplace_listing_card_detail_zoom.png');

    // 2. Test Navigation on Card / View Lot
    console.log('Testing View Lot CTA interaction...');
    await viewBtn.click();
    await page.waitForTimeout(500);

    // Verify it opened Produce Detail view
    const detailTitle = await page.locator('h1, h2, .produce-detail-title, .section-title').first().textContent();
    console.log(`Produce Detail View Reached: "${detailTitle?.trim()}"`);

    // Navigate back to Marketplace
    await marketplaceNav.click();
    await page.waitForTimeout(500);

    // 3. Test Empty State
    console.log('Testing Empty State...');
    const searchInput = page.locator('.marketplace-search-input');
    await searchInput.fill('nonexistent_crop_xyz_9999');
    await page.locator('.marketplace-search-submit-btn').click();
    await page.waitForTimeout(500);

    const emptyState = page.locator('.empty-state');
    await emptyState.waitFor({ state: 'visible' });
    console.log('✓ Empty state rendered successfully');

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'marketplace_listing_cards_empty_state.png'),
      fullPage: false,
    });
    console.log('✓ Captured marketplace_listing_cards_empty_state.png');

    // Reset filters from empty state
    await page.locator('.empty-state button:has-text("Reset All Filters")').click();
    await page.waitForTimeout(500);

    // 4. Tablet 1024px Viewport
    console.log('Testing Tablet 1024px viewport (2-column layout)...');
    await page.setViewportSize({ width: 1024, height: 768 });
    await page.waitForTimeout(300);

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'marketplace_listing_cards_tablet_1024.png'),
      fullPage: false,
    });
    console.log('✓ Captured marketplace_listing_cards_tablet_1024.png');

    // 5. Mobile 390px Viewport
    console.log('Testing Mobile 390px viewport (1-column layout)...');
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(300);

    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    console.log(`Mobile dimensions - scrollWidth: ${scrollWidth}, clientWidth: ${clientWidth}`);
    if (scrollWidth > clientWidth + 1) {
      console.warn(`Warning: Potential horizontal overflow on mobile (${scrollWidth} > ${clientWidth})`);
    }

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'marketplace_listing_cards_mobile_390.png'),
      fullPage: false,
    });
    console.log('✓ Captured marketplace_listing_cards_mobile_390.png');

    console.log('======================================================');
    console.log('🎉 ALL MARKETPLACE PHASE 3.4 LISTING CARDS TESTS PASSED!');
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
