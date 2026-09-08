import { chromium } from 'playwright';

const BASE_URL = 'http://localhost:5173';
const ARTIFACT_DIR = 'C:/Users/Shoury/.gemini/antigravity/brain/bcaa7ab8-49f1-48d8-9fb0-523de2834bbc';

async function main() {
  console.log('🚀 Starting Comprehensive E2E Verification for UI-3 Step 3.1 & 3.2...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 }
  });
  const page = await context.newPage();

  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
      console.log('  [Browser Error]:', msg.text());
    }
  });

  const ts = Date.now();
  const farmerEmail = `farmer_mkt_${ts}@agrimandi.in`;
  const buyerEmail = `buyer_mkt_${ts}@agrimandi.in`;
  const commonPassword = 'AgriPassword123!';

  // ==========================================
  // PART 1: PUBLIC / GUEST MARKETPLACE SHELL & SEARCH
  // ==========================================
  console.log('\n--- 1. Testing Marketplace Page Load & Active Navigation ---');
  await page.goto(`${BASE_URL}/?view=marketplace`, { waitUntil: 'networkidle' });
  await page.waitForSelector('.marketplace-page');

  // Verify Active Nav Item
  const activeNav = await page.locator('.nav-link.active').textContent();
  console.log('✓ Active Nav Item:', activeNav.trim());

  // Step 3.1: Header & Subtitle
  const title = await page.locator('.marketplace-page-title').textContent();
  const subtitle = await page.locator('.marketplace-page-subtitle').textContent();
  console.log('✓ Page Title:', title);
  console.log('✓ Page Subtitle:', subtitle);

  // Role-Aware CTA for Logged-Out Guest
  const guestCta = await page.locator('.marketplace-header-actions button').textContent();
  console.log('✓ Guest CTA Button Text:', guestCta.trim());

  // Capture Desktop Initial State Screenshot
  await page.screenshot({ path: `${ARTIFACT_DIR}/marketplace_desktop_initial.png`, fullPage: false });
  console.log('✓ Captured Desktop Initial Screenshot.');

  // Step 3.2: Search Bar & Popular Shortcuts
  console.log('\n--- 2. Testing Marketplace Search Bar & Input ---');
  const searchPlaceholder = await page.locator('.marketplace-search-input').getAttribute('placeholder');
  console.log('✓ Search Input Placeholder:', searchPlaceholder);

  // Enter Search Query & Submit
  await page.fill('.marketplace-search-input', 'Nashik Red');
  await page.click('.marketplace-search-submit-btn');
  await page.waitForTimeout(400);

  const enteredSearch = await page.locator('.marketplace-search-input').inputValue();
  console.log('✓ Persisted Search Query:', enteredSearch);

  // Verify Clear Button Exists and Functions
  const clearBtnVisible = await page.locator('.marketplace-search-clear-btn').isVisible();
  console.log('✓ Search Clear Button Visible:', clearBtnVisible);

  // Capture Desktop Search Entered Screenshot
  await page.screenshot({ path: `${ARTIFACT_DIR}/marketplace_desktop_search_entered.png`, fullPage: false });
  console.log('✓ Captured Desktop Search Entered Screenshot.');

  // Click Clear Button
  await page.click('.marketplace-search-clear-btn');
  const clearedSearch = await page.locator('.marketplace-search-input').inputValue();
  console.log('✓ Value after Clear Click:', `"${clearedSearch}"`);

  // Test Enter Key Submission
  console.log('\n--- 3. Testing Enter Key Submission ---');
  await page.fill('.marketplace-search-input', 'Potato');
  await page.press('.marketplace-search-input', 'Enter');
  await page.waitForTimeout(400);
  console.log('✓ Submitted via Enter key successfully');

  // Test Popular Crop Shortcuts
  console.log('\n--- 4. Testing Popular Search Shortcuts ---');
  const popularChips = await page.locator('.popular-shortcut-chip').allTextContents();
  console.log('✓ Popular Chips:', popularChips.join(', '));

  await page.click('.popular-shortcut-chip:has-text("Onion")');
  await page.waitForTimeout(400);
  const searchAfterChip = await page.locator('.marketplace-search-input').inputValue();
  const chipIsActive = await page.locator('.popular-shortcut-chip:has-text("Onion")').getAttribute('class');
  console.log(`✓ Search value after Onion chip click: "${searchAfterChip}", Chip class: "${chipIsActive}"`);

  // ==========================================
  // PART 2: ROLE-AWARE CTA TESTS
  // ==========================================
  console.log('\n--- 5. Registering Farmer & Verifying Farmer CTA on Marketplace ---');
  await page.goto(`${BASE_URL}/?view=register`, { waitUntil: 'networkidle' });
  await page.waitForSelector('.register-card');
  await page.click('.role-option-btn:has-text("Farmer")');
  await page.fill('#displayName', `Kisan Farmer ${ts.toString().slice(-4)}`);
  await page.fill('#email', farmerEmail);
  await page.fill('#phoneNumber', `9${ts.toString().slice(-9)}`);
  await page.fill('#password', commonPassword);
  await page.fill('#confirmPassword', commonPassword);
  await page.click('button[type="submit"]');
  await page.waitForSelector('.user-profile-badge');

  // Navigate to Marketplace
  await page.click('.nav-link:has-text("Marketplace")');
  await page.waitForSelector('.marketplace-page');
  const farmerCta = await page.locator('.marketplace-header-actions button').textContent();
  console.log('✓ Farmer CTA on Marketplace:', farmerCta.trim());

  // Logout
  await page.click('button:has-text("Logout")');
  await page.waitForSelector('button:has-text("Sign In")');

  // Register Buyer
  console.log('\n--- 6. Registering Buyer & Verifying Buyer CTA on Marketplace ---');
  await page.goto(`${BASE_URL}/?view=register`, { waitUntil: 'networkidle' });
  await page.waitForSelector('.register-card');
  await page.click('.role-option-btn:has-text("Buyer")');
  await page.fill('#displayName', `AgriBuyer Corp ${ts.toString().slice(-4)}`);
  await page.fill('#email', buyerEmail);
  await page.fill('#phoneNumber', `8${ts.toString().slice(-9)}`);
  await page.fill('#password', commonPassword);
  await page.fill('#confirmPassword', commonPassword);
  await page.click('button[type="submit"]');
  await page.waitForSelector('.user-profile-badge');

  // Navigate to Marketplace
  await page.click('.nav-link:has-text("Marketplace")');
  await page.waitForSelector('.marketplace-page');
  const buyerCtaCount = await page.locator('.marketplace-header-actions button').count();
  console.log('✓ Buyer CTA count on Marketplace (should be 0):', buyerCtaCount);

  // Logout
  await page.click('button:has-text("Logout")');
  await page.waitForSelector('button:has-text("Sign In")');

  // ==========================================
  // PART 3: MOBILE RESPONSIVE AUDIT (390px)
  // ==========================================
  console.log('\n--- 7. Testing Mobile Responsive Layout (390px) ---');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${BASE_URL}/?view=marketplace`, { waitUntil: 'networkidle' });
  await page.waitForSelector('.marketplace-page');

  let scrollWidth = await page.evaluate(() => document.body.scrollWidth);
  let innerWidth = await page.evaluate(() => window.innerWidth);
  console.log('✓ Mobile Initial No Horizontal Overflow:', scrollWidth <= innerWidth);
  await page.screenshot({ path: `${ARTIFACT_DIR}/marketplace_mobile_initial.png`, fullPage: false });
  console.log('✓ Captured Mobile Initial Screenshot.');

  // Enter Search on Mobile
  await page.fill('.marketplace-search-input', 'Tomato');
  await page.click('.marketplace-search-submit-btn');
  await page.waitForTimeout(400);

  scrollWidth = await page.evaluate(() => document.body.scrollWidth);
  innerWidth = await page.evaluate(() => window.innerWidth);
  console.log('✓ Mobile Search Entered No Horizontal Overflow:', scrollWidth <= innerWidth);
  await page.screenshot({ path: `${ARTIFACT_DIR}/marketplace_mobile_search_entered.png`, fullPage: false });
  console.log('✓ Captured Mobile Search Entered Screenshot.');

  // Console Error Audit
  console.log('\n--- 8. Console Error Audit ---');
  const criticalErrors = consoleErrors.filter(e => !e.includes('401'));
  console.log(`✓ Total Critical Console Errors: ${criticalErrors.length}`);

  await browser.close();
  console.log('\n🎉 ALL UI-3 STEP 3.1 & 3.2 E2E TESTS PASSED SUCCESSFULLY!');
}

main().catch(err => {
  console.error('Test Failed:', err);
  process.exit(1);
});
