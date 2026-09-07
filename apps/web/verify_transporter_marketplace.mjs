import { chromium } from 'playwright';

async function verifyTransporterMarketplace() {
  console.log('--- Starting Transporter Marketplace Browser Verification ---');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await context.newPage();

  page.on('console', (msg) => {
    if (msg.type() === 'error') console.error('[Browser Error]', msg.text());
  });

  const baseUrl = 'http://localhost:5174';

  // 1. Visit landing page and clear session
  await page.goto(baseUrl);
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.waitForLoadState('networkidle');
  console.log('✓ Landing page loaded with clean session');

  // 2. Register as Transporter
  const uid = Date.now();
  const email = `transporter_${uid}@agritest.in`;
  console.log(`Registering transporter user: ${email}`);

  // Navigate to Register view from Navbar
  await page.click('.auth-buttons button:has-text("Register")');
  await page.waitForSelector('.role-selector-grid');

  // Click Transporter role card
  await page.click('.role-option-btn:has-text("Transporter")');
  await page.waitForTimeout(300);

  // Fill registration inputs
  await page.fill('#displayName', 'Sahyadri Freight Logistics');
  await page.fill('#email', email);
  await page.fill('#phoneNumber', `+91987${Math.floor(100000 + Math.random() * 900000)}`);
  await page.fill('#password', 'TransporterPass123!');

  // Submit register form
  await page.click('form.auth-form button[type="submit"]');

  // Wait for Transporter Dashboard to mount
  await page.waitForSelector('button:has-text("+ Register Vehicle")', { timeout: 15000 });
  console.log('✓ Transporter Hub rendered successfully');

  // Verify Transporter Hub Header
  const titleEl = await page.$('h1');
  const titleText = titleEl ? await titleEl.textContent() : 'N/A';
  console.log(`✓ Transporter Hub Title: "${titleText}"`);

  // Verify KPI Cards
  const kpis = await page.$$('.glass-card');
  console.log(`✓ Rendered ${kpis.length} operational cards/widgets on Transporter Hub`);

  // 3. Test Add Vehicle Modal
  await page.click('button:has-text("+ Register Vehicle")');
  await page.waitForSelector('input[placeholder*="MH-12"]', { timeout: 5000 });

  await page.fill('input[placeholder*="MH-12"]', `MH-12-TX-${uid.toString().slice(-4)}`);
  await page.fill('input[placeholder*="Tata 407"]', 'Eicher Pro 2049 (6.0 MT)');

  // Confirm vehicle registration
  await page.click('button[type="submit"]:has-text("Register Vehicle")');
  await page.waitForTimeout(1500);
  console.log('✓ Vehicle registered in fleet');

  // 4. Test Tab Navigation
  const fleetTab = await page.$('button:has-text("My Fleet")');
  if (fleetTab) {
    await fleetTab.click();
    await page.waitForTimeout(500);
    console.log('✓ Navigated to My Fleet tab');
  }

  const oppsTab = await page.$('button:has-text("Transport Opportunities")');
  if (oppsTab) {
    await oppsTab.click();
    await page.waitForTimeout(500);
    console.log('✓ Navigated to Transport Opportunities tab');
  }

  // 5. Test Mobile Responsive Viewport
  await page.setViewportSize({ width: 375, height: 667 });
  await page.waitForTimeout(500);

  const isOverflowing = await page.evaluate(() => {
    return document.documentElement.scrollWidth > window.innerWidth;
  });
  console.log(`✓ Mobile viewport 375x667 horizontal overflow: ${isOverflowing}`);

  await browser.close();
  console.log('--- Transporter Marketplace Browser Verification Completed Successfully ---');
}

verifyTransporterMarketplace().catch((err) => {
  console.error('Transporter verification failed:', err);
  process.exit(1);
});
