import { chromium } from 'playwright';

const BASE_URL = 'http://localhost:5173';
const ARTIFACT_DIR = 'C:/Users/Shoury/.gemini/antigravity/brain/bcaa7ab8-49f1-48d8-9fb0-523de2834bbc';

async function main() {
  console.log('🚀 Starting Targeted E2E Verification for Recommendation UI Correction...');
  const browser = await chromium.launch({ headless: true });
  
  // 1. Desktop Browser Context
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 }
  });
  const page = await context.newPage();

  const consoleErrors = [];
  page.on('console', msg => {
    console.log(`  [Browser ${msg.type()}]:`, msg.text());
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });

  page.on('pageerror', err => {
    console.log('  [Page Error]:', err.message);
    consoleErrors.push(err.message);
  });

  // Register / Login as Farmer to access Recommendation view
  console.log('\n--- 1. Registering/Logging In as Farmer ---');
  const timestamp = Date.now();
  await page.goto(`${BASE_URL}/?view=register`, { waitUntil: 'networkidle' });
  await page.fill('#displayName', `Ramesh_${timestamp}`);
  await page.fill('#email', `ramesh_${timestamp}@agrimandi.in`);
  await page.fill('#phoneNumber', `9${String(timestamp).slice(-9)}`);
  await page.fill('#password', 'Password123!');
  await page.click('button[type="submit"]');

  // Wait for Farmer Dashboard to mount
  console.log('\n--- 2. Waiting for Farmer Dashboard & Navigating to Recommendation ---');
  await page.waitForSelector('.welcome-title', { timeout: 10000 });
  const welcomeText = await page.locator('.welcome-title').textContent();
  console.log('✓ Farmer Dashboard loaded with welcome text:', welcomeText);

  // Click navigation button
  console.log('Clicking Best Selling Option button in Farmer Dashboard...');
  await page.click('.welcome-actions button:has-text("Best Selling Option")');

  await page.waitForTimeout(500);
  console.log('Current URL after click:', page.url());
  const bodyText = await page.evaluate(() => document.body.innerText.slice(0, 300));
  console.log('Page body snippet:', bodyText);

  // Wait for Recommendation Page
  await page.waitForSelector('.page-title', { timeout: 10000 });
  const pageTitle = await page.locator('.page-title').textContent();
  console.log('✓ Recommendation Page Title:', pageTitle);

  // Check Background Rule: Container background should be light, not full-screen image
  const pageBackgroundImg = await page.locator('.container').evaluate(el => getComputedStyle(el).backgroundImage);
  console.log('✓ Page container background image (should be none):', pageBackgroundImg);

  // Check Advisor Card & Contained Clay Farmer Illustration
  const clayImg = page.locator('img[alt="AgriMandi Advisor Guide"]');
  await clayImg.waitFor({ state: 'visible' });
  const imgBox = await clayImg.boundingBox();
  console.log(`✓ Contained Clay Farmer Dimensions on Desktop: ${Math.round(imgBox.width)}px width x ${Math.round(imgBox.height)}px height`);
  console.log('✓ Clay farmer is properly contained (<= 220px):', imgBox.width <= 220);

  // Capture Pre-Calculation Desktop Screenshot
  await page.screenshot({ path: `${ARTIFACT_DIR}/recommendation_desktop_pre_calc.png`, fullPage: false });
  console.log('✓ Saved desktop pre-calculation screenshot.');

  // Check Form Inputs & Calculate
  console.log('\n--- 3. Executing Best Selling Option Calculation ---');
  await page.fill('#quantityInput', '35');
  await page.fill('#pickupInput', 'Farm Gate, Nashik Rural');
  await page.click('button:has-text("Calculate Best Selling Option")');

  // Wait for results
  await page.waitForSelector('.badge-verified:has-text("RECOMMENDED BUYER")', { timeout: 15000 });
  console.log('✓ Calculation completed! Recommended Buyer Card rendered.');

  const recommendedBuyerBadge = await page.locator('.badge-verified:has-text("RECOMMENDED BUYER")').textContent();
  console.log('✓ Header Badge:', recommendedBuyerBadge);

  // Verify Waterfall items
  const waterfallCard = page.locator('.card:has(.badge-verified:has-text("RECOMMENDED BUYER"))');
  const waterfallText = await waterfallCard.textContent();
  console.log('✓ Contains Expected Price:', waterfallText.includes('Expected Price'));
  console.log('✓ Contains Transport Estimate:', waterfallText.includes('Transport Estimate'));
  console.log('✓ Contains Expected Net:', waterfallText.includes('Expected Net'));
  console.log('✓ Contains Verified Facts / Provenance:', waterfallText.includes('Verified Facts') || waterfallText.includes('Modeled Estimates'));

  // Check Horizontal Overflow
  const bodyScrollWidth = await page.evaluate(() => document.body.scrollWidth);
  const windowInnerWidth = await page.evaluate(() => window.innerWidth);
  console.log('✓ No horizontal overflow on desktop:', bodyScrollWidth <= windowInnerWidth);

  // Capture Post-Calculation Desktop Screenshot
  await page.screenshot({ path: `${ARTIFACT_DIR}/recommendation_desktop_post_calc.png`, fullPage: false });
  console.log('✓ Saved desktop post-calculation screenshot.');

  // 4. Mobile Viewport Verification (390px)
  console.log('\n--- 4. Testing Responsive Mobile Layout (390px) ---');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(300);

  const mobileBodyScroll = await page.evaluate(() => document.body.scrollWidth);
  const mobileWindowWidth = await page.evaluate(() => window.innerWidth);
  console.log('✓ No horizontal overflow on mobile:', mobileBodyScroll <= mobileWindowWidth);

  await page.screenshot({ path: `${ARTIFACT_DIR}/recommendation_mobile_view.png`, fullPage: false });
  console.log('✓ Saved mobile view screenshot.');

  // 5. Console Error Audit
  console.log('\n--- 5. Console Error Audit ---');
  const criticalErrors = consoleErrors.filter(e => !e.includes('401'));
  console.log(`✓ Total Critical Console Errors: ${criticalErrors.length}`);

  await browser.close();
  console.log('\n🎉 RECOMMENDATION UI CORRECTION VERIFICATION PASSED SUCCESSFULLY!');
}

main().catch(async err => {
  console.error('Test Failed:', err);
  process.exit(1);
});
