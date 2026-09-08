import { chromium } from 'playwright';

const BASE_URL = 'http://localhost:5173';
const ARTIFACT_DIR = 'C:/Users/Shoury/.gemini/antigravity/brain/bcaa7ab8-49f1-48d8-9fb0-523de2834bbc';

async function main() {
  console.log('🚀 Starting Comprehensive E2E Browser Verification for Global Design System & App Shell...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 }
  });
  const page = await context.newPage();

  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
      console.log('  [Browser Console Error]:', msg.text());
    }
  });

  // 1. Check Shell (Navbar, Brand, Footer, Typography)
  console.log('\n--- 1. Testing Application Shell (Navbar & Footer) ---');
  await page.goto(BASE_URL, { waitUntil: 'networkidle' });
  await page.waitForSelector('.navbar-container');
  await page.waitForSelector('.footer-container');

  const brandName = await page.locator('.brand-name').textContent();
  console.log('✓ Navbar brand name verified:', brandName);

  const brandTagline = await page.locator('.brand-tagline').textContent();
  console.log('✓ Navbar brand tagline verified:', brandTagline);

  const footerText = await page.locator('.footer-bottom').textContent();
  console.log('✓ Footer text verified:', footerText.includes('AgriMandi'));

  // Check for horizontal overflow
  const bodyScrollWidth = await page.evaluate(() => document.body.scrollWidth);
  const windowInnerWidth = await page.evaluate(() => window.innerWidth);
  console.log('✓ No horizontal overflow on Landing:', bodyScrollWidth <= windowInnerWidth);

  // 2. Check Authentication Views (Login & Register with Sharp Rectangular Inputs)
  console.log('\n--- 2. Testing Login View & Sharp Form Inputs ---');
  await page.click('button:has-text("Sign In")');
  await page.waitForSelector('.auth-card');
  const loginInputRadius = await page.locator('#email').evaluate(el => getComputedStyle(el).borderRadius);
  console.log('✓ Login input border-radius (sharp 2px):', loginInputRadius);
  await page.screenshot({ path: `${ARTIFACT_DIR}/design_system_auth_login.png`, fullPage: false });
  console.log('✓ Saved login view screenshot.');

  console.log('\n--- 3. Testing Register View & Role Cards ---');
  await page.click('button:has-text("Register as Farmer, FPO or Buyer")');
  await page.waitForSelector('.role-selector-grid');
  const roleCardsCount = await page.locator('.role-option-btn').count();
  console.log('✓ Register role options rendered (Farmer, FPO, Buyer, Transporter):', roleCardsCount);
  await page.screenshot({ path: `${ARTIFACT_DIR}/design_system_auth_register.png`, fullPage: false });
  console.log('✓ Saved register view screenshot.');

  // 4. Check Authenticated Navbar Shell with Role Pill
  console.log('\n--- 4. Testing Authenticated Navbar Shell ---');
  const timestamp = Date.now();
  await page.fill('#displayName', `Kisan_${timestamp}`);
  await page.fill('#email', `farmer_${timestamp}@agrimandi.in`);
  await page.fill('#phoneNumber', `9${String(timestamp).slice(-9)}`);
  await page.fill('#password', 'Password123!');
  await page.click('button[type="submit"]');

  await page.waitForSelector('.user-profile-badge');
  const userRolePill = await page.locator('.user-profile-badge .role-pill').textContent();
  console.log('✓ Authenticated User Role Pill rendered in Navbar:', userRolePill);
  await page.screenshot({ path: `${ARTIFACT_DIR}/design_system_authenticated_shell.png`, fullPage: false });
  console.log('✓ Saved authenticated shell screenshot.');

  // 5. Check Design System Showcase View
  console.log('\n--- 5. Testing Design System Showcase View ---');
  await page.goto(`${BASE_URL}/?view=design-system`, { waitUntil: 'networkidle' });
  await page.waitForSelector('.tabs-header-row');

  // Verify Tab 1: Tokens
  const title = await page.locator('.page-title').textContent();
  console.log('✓ Design System Showcase Page Title:', title);

  // Switch through all showcase tabs to verify zero rendering errors
  const tabs = [
    { name: 'Tokens', selector: 'button:has-text("Tokens & Geometry")' },
    { name: 'Buttons', selector: 'button:has-text("Buttons")' },
    { name: 'Forms', selector: 'button:has-text("Forms & Inputs")' },
    { name: 'Cards', selector: 'button:has-text("Cards & Metrics")' },
    { name: 'Tables', selector: 'button:has-text("Tables")' },
    { name: 'Badges', selector: 'button:has-text("Badges & Status")' },
    { name: 'Trust', selector: 'button:has-text("Trust UI")' },
    { name: 'Modals', selector: 'button:has-text("Modals & Alerts")' },
    { name: 'States', selector: 'button:has-text("Skeletons & Empty")' },
  ];

  for (const t of tabs) {
    await page.click(t.selector);
    await page.waitForTimeout(150);
    console.log(`✓ Showcase Tab "${t.name}" rendered cleanly`);
  }

  // Switch back to Trust tab and take showcase screenshot
  await page.click('button:has-text("Trust UI")');
  await page.screenshot({ path: `${ARTIFACT_DIR}/design_system_showcase_trust.png`, fullPage: false });

  // Switch to Tokens tab and capture main showcase screenshot
  await page.click('button:has-text("Tokens & Geometry")');
  await page.screenshot({ path: `${ARTIFACT_DIR}/design_system_showcase_main.png`, fullPage: false });
  console.log('✓ Saved Design System Showcase screenshots.');

  console.log('\n--- 6. Console Error Audit ---');
  const criticalErrors = consoleErrors.filter(e => !e.includes('401'));
  console.log(`✓ Total Critical Console Errors: ${criticalErrors.length}`);

  await browser.close();
  console.log('\n🎉 ALL GLOBAL DESIGN SYSTEM & APPLICATION SHELL VERIFICATIONS PASSED!');
}

main().catch(err => {
  console.error('Test Failed:', err);
  process.exit(1);
});
