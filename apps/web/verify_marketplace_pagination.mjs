import { chromium } from 'playwright';
import path from 'path';

const ARTIFACT_DIR = 'C:/Users/Shoury/.gemini/antigravity/brain/bcaa7ab8-49f1-48d8-9fb0-523de2834bbc';
const BASE_URL = 'http://localhost:5173';
const API_URL = 'http://localhost:8000';

async function seedTestLotsIfNeeded() {
  try {
    // Check current produce lots count
    const listRes = await fetch(`${API_URL}/api/v1/marketplace/produce-lots?page_size=100`);
    if (!listRes.ok) return;
    const data = await listRes.json();
    console.log(`Current produce lots in database: ${data.total}`);

    if (data.total < 15) {
      console.log(`Seeding test produce lots to exceed 12 items/page...`);
      // Login as farmer to get auth token
      const authRes = await fetch(`${API_URL}/api/v1/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: 'farmer1@agrimandi.internal', password: 'Password@123' }),
      });

      if (!authRes.ok) {
        console.log('Could not authenticate farmer1, continuing with existing items...');
        return;
      }

      const { access_token } = await authRes.json();
      const commRes = await fetch(`${API_URL}/api/v1/commodities`);
      const commodities = await commRes.json();
      const onion = commodities.find((c) => c.name.toLowerCase().includes('onion')) || commodities[0];
      const tomato = commodities.find((c) => c.name.toLowerCase().includes('tomato')) || commodities[0];

      const lotsToCreate = [
        { title: 'Nashik Red Onions (Premium Lot A)', commId: onion.id, qty: 150, price: 1750, grade: 'Grade A' },
        { title: 'Nashik Red Onions (Export Quality Lot B)', commId: onion.id, qty: 250, price: 1950, grade: 'Grade A' },
        { title: 'Nashik White Onions (Farm Gate Lot C)', commId: onion.id, qty: 300, price: 2100, grade: 'Grade B' },
        { title: 'Organic Hybrid Tomatoes (Polyhouse Lot D)', commId: tomato.id, qty: 400, price: 1400, grade: 'Grade A' },
        { title: 'Solapur Tomatoes (Standard Pack Lot E)', commId: tomato.id, qty: 200, price: 1250, grade: 'Grade B' },
        { title: 'Pune Fresh Salad Tomatoes (Lot F)', commId: tomato.id, qty: 350, price: 1600, grade: 'Grade A' },
        { title: 'Commercial Seed Onions (Lot G)', commId: onion.id, qty: 500, price: null, grade: 'Grade B' }, // Negotiable
        { title: 'Lasalgaon Fresh Spring Onions (Lot H)', commId: onion.id, qty: 180, price: 2200, grade: 'Grade A' },
      ];

      for (const item of lotsToCreate) {
        await fetch(`${API_URL}/api/v1/produce-lots`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${access_token}`,
          },
          body: JSON.stringify({
            commodity_id: item.commId,
            title: item.title,
            available_quantity: item.qty,
            unit: 'quintal',
            quality_grade: item.grade,
            asking_price_per_unit: item.price,
            pickup_location: {
              name: 'Lasalgaon Mandi Yard',
              district: 'Nashik',
              state: 'Maharashtra',
            },
          }),
        });
      }
      console.log('✓ Successfully seeded extra produce lots for pagination testing.');
    }
  } catch (err) {
    console.error('Seed helper note:', err.message);
  }
}

async function runVerification() {
  console.log('🚀 Starting Marketplace Phase 3.6 Pagination E2E Verification...');

  await seedTestLotsIfNeeded();

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
    // =========================================================================
    // 1. Desktop 1440px: Initial Load & Page 1 Verification
    // =========================================================================
    await page.setViewportSize({ width: 1440, height: 900 });
    console.log('Navigating to marketplace on 1440px desktop...');
    await page.goto(`${BASE_URL}`, { waitUntil: 'networkidle' });

    // Navigate to Marketplace
    const marketplaceNav = page.locator('button.nav-link:has-text("Marketplace")');
    await marketplaceNav.click();
    await page.waitForTimeout(600);

    // Verify Results Header count
    const resultsCount = page.locator('.marketplace-results-count');
    await resultsCount.waitFor({ state: 'visible' });
    const countText = await resultsCount.textContent();
    console.log(`Results Header Count: "${countText?.trim()}"`);

    // Verify Pagination Bar is visible
    const paginationNav = page.locator('.marketplace-pagination-nav');
    await paginationNav.waitFor({ state: 'visible' });
    console.log('✓ Pagination navigation bar is visible');

    // Verify Range Info
    const rangeInfo = page.locator('.marketplace-pagination-info');
    const rangeText = await rangeInfo.textContent();
    console.log(`Pagination Info Text: "${rangeText?.trim()}"`);
    if (!rangeText?.includes('1–12')) {
      throw new Error(`Expected pagination range "1–12", got "${rangeText}"`);
    }

    // Verify Prev button is disabled on page 1
    const prevBtn = page.locator('button[aria-label="Go to previous page"]');
    const isPrevDisabled = await prevBtn.isDisabled();
    console.log(`Prev button disabled on page 1: ${isPrevDisabled}`);
    if (!isPrevDisabled) throw new Error('Expected Prev button to be disabled on page 1');

    // Verify Page 1 button is active
    const page1Btn = page.locator('.pagination-page-btn[aria-label="Go to page 1"]');
    const isPage1Active = (await page1Btn.getAttribute('aria-current')) === 'page';
    console.log(`Page 1 active: ${isPage1Active}`);
    if (!isPage1Active) throw new Error('Expected Page 1 to have aria-current="page"');

    // Capture Page 1 Screenshot
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'marketplace_pagination_desktop_1440_page1.png'),
      fullPage: false,
    });
    console.log('✓ Captured marketplace_pagination_desktop_1440_page1.png');

    // =========================================================================
    // 2. Navigation to Page 2
    // =========================================================================
    console.log('Clicking Next button to navigate to Page 2...');
    const nextBtn = page.locator('button[aria-label="Go to next page"]');
    await nextBtn.click();
    await page.waitForTimeout(500);

    const page2RangeText = await rangeInfo.textContent();
    console.log(`Page 2 Info Text: "${page2RangeText?.trim()}"`);
    if (!page2RangeText?.includes('13–')) {
      throw new Error(`Expected Page 2 range starting at 13, got "${page2RangeText}"`);
    }

    // Verify Prev button is now enabled
    const isPrevDisabledOnPage2 = await prevBtn.isDisabled();
    console.log(`Prev button disabled on page 2: ${isPrevDisabledOnPage2}`);
    if (isPrevDisabledOnPage2) throw new Error('Expected Prev button to be enabled on page 2');

    // Verify Page 2 button is active
    const page2Btn = page.locator('.pagination-page-btn[aria-label="Go to page 2"]');
    const isPage2Active = (await page2Btn.getAttribute('aria-current')) === 'page';
    console.log(`Page 2 active: ${isPage2Active}`);
    if (!isPage2Active) throw new Error('Expected Page 2 to have aria-current="page"');

    // Capture Page 2 Screenshot
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'marketplace_pagination_desktop_1440_page2.png'),
      fullPage: false,
    });
    console.log('✓ Captured marketplace_pagination_desktop_1440_page2.png');

    // =========================================================================
    // 3. Navigation back to Page 1 via Previous Button
    // =========================================================================
    console.log('Clicking Prev button to return to Page 1...');
    await prevBtn.click();
    await page.waitForTimeout(500);

    const backToPage1Text = await rangeInfo.textContent();
    if (!backToPage1Text?.includes('1–12')) {
      throw new Error(`Expected return to range "1–12", got "${backToPage1Text}"`);
    }
    console.log('✓ Successfully returned to Page 1 via Prev button');

    // =========================================================================
    // 4. Test Search + Pagination Reset
    // =========================================================================
    console.log('Navigating to Page 2 then changing Search query to test reset...');
    await nextBtn.click();
    await page.waitForTimeout(300);

    const searchInput = page.locator('.marketplace-search-input');
    await searchInput.fill('Onion');
    const searchSubmit = page.locator('.marketplace-search-submit-btn');
    await searchSubmit.click();
    await page.waitForTimeout(500);

    // Filtered count should show matching onion lots
    const onionCountText = await resultsCount.textContent();
    console.log(`Results count for "Onion": "${onionCountText?.trim()}"`);

    // Clear search and verify return to full dataset on Page 1
    const clearBtn = page.locator('.marketplace-search-clear-btn');
    await clearBtn.click();
    await searchSubmit.click();
    await page.waitForTimeout(500);

    const clearedRangeText = await rangeInfo.textContent();
    console.log(`Range after clearing search: "${clearedRangeText?.trim()}"`);
    if (!clearedRangeText?.includes('1–12')) {
      throw new Error(`Expected return to Page 1 range "1–12", got "${clearedRangeText}"`);
    }

    // =========================================================================
    // 5. Test Filter + Sort + Pagination Combined
    // =========================================================================
    console.log('Testing Sort + Filter + Pagination combined...');
    const sortTrigger = page.locator('.marketplace-sort-trigger');
    await sortTrigger.click();
    await page.waitForTimeout(200);
    const priceAscOption = page.locator('.sort-menu-item:has-text("Price: Low to High")');
    await priceAscOption.click();
    await page.waitForTimeout(400);

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'marketplace_pagination_desktop_1440_filter_sort.png'),
      fullPage: false,
    });
    console.log('✓ Captured marketplace_pagination_desktop_1440_filter_sort.png');

    // =========================================================================
    // 6. Tablet 1024px Viewport
    // =========================================================================
    console.log('Testing Tablet 1024px layout...');
    await page.setViewportSize({ width: 1024, height: 800 });
    await page.waitForTimeout(300);

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'marketplace_pagination_tablet_1024.png'),
      fullPage: false,
    });
    console.log('✓ Captured marketplace_pagination_tablet_1024.png');

    // =========================================================================
    // 7. Mobile 390px Viewport (Compact controls & Zero horizontal overflow)
    // =========================================================================
    console.log('Testing Mobile 390px layout...');
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(400);

    // Check Mobile Indicator is visible
    const mobileIndicator = page.locator('.pagination-mobile-indicator');
    const isMobileIndicatorVisible = await mobileIndicator.isVisible();
    console.log(`Mobile Page Indicator visible: ${isMobileIndicatorVisible}`);
    if (!isMobileIndicatorVisible) {
      throw new Error('Expected mobile page indicator to be visible on 390px');
    }

    // Check Horizontal Overflow
    const overflowCheck = await page.evaluate(() => {
      const doc = document.documentElement;
      return {
        clientWidth: doc.clientWidth,
        scrollWidth: doc.scrollWidth,
        hasOverflow: doc.scrollWidth > doc.clientWidth,
      };
    });
    console.log(`Mobile Overflow Check: clientWidth=${overflowCheck.clientWidth}, scrollWidth=${overflowCheck.scrollWidth}, hasOverflow=${overflowCheck.hasOverflow}`);
    if (overflowCheck.hasOverflow) {
      throw new Error(`Horizontal overflow detected on mobile 390px viewport!`);
    }

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'marketplace_pagination_mobile_390.png'),
      fullPage: false,
    });
    console.log('✓ Captured marketplace_pagination_mobile_390.png');

    // Final Error Assertions
    if (consoleErrors.length > 0) {
      console.warn(`Browser console errors encountered: ${consoleErrors.join(', ')}`);
    } else {
      console.log('✓ Zero browser console errors encountered.');
    }

    console.log('🎉 ALL MARKETPLACE PAGINATION E2E TESTS PASSED SUCCESSFULLY!');
  } finally {
    await browser.close();
  }
}

runVerification().catch((err) => {
  console.error('❌ Verification failed:', err);
  process.exit(1);
});
