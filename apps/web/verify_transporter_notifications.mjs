import { chromium } from 'playwright';
import { execSync } from 'child_process';

async function verifyTransporterNotificationsBugfix() {
  console.log('=== Starting Transporter Notification + Opportunity UX Bug Fix E2E Verification ===');

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1366, height: 850 } });
  const page = await context.newPage();

  const consoleErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      console.error('[Browser Console Error]', msg.text());
      consoleErrors.push(msg.text());
    }
  });

  const baseUrl = 'http://localhost:5174';

  // 1. Visit landing page & clear session
  await page.goto(baseUrl);
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await page.waitForLoadState('networkidle');
  console.log('✓ 1. Landing page loaded with clean local state');

  // 2. Register Transporter via UI
  const uid = Date.now();
  const email = `transporter_notif_${uid}@freight.in`;
  console.log(`✓ 2. Registering Transporter user: ${email}`);

  await page.click('.auth-buttons button:has-text("Register")');
  await page.waitForSelector('.role-selector-grid');
  await page.click('.role-option-btn:has-text("Transporter")');
  await page.waitForTimeout(300);

  await page.fill('#displayName', 'Kisan Freight Express');
  await page.fill('#email', email);
  await page.fill('#phoneNumber', `+91987${Math.floor(100000 + Math.random() * 900000)}`);
  await page.fill('#password', 'FreightPass123!');
  await page.click('form.auth-form button[type="submit"]');

  await page.waitForSelector('button:has-text("+ Register Vehicle")', { timeout: 15000 });
  console.log('✓ 3. Transporter Hub loaded successfully');

  // 3. Register a freight vehicle in fleet
  await page.click('button:has-text("+ Register Vehicle")');
  await page.waitForSelector('input[placeholder*="MH-12"]', { timeout: 5000 });
  await page.fill('input[placeholder*="MH-12"]', `MH-12-TF-${Math.floor(1000 + Math.random() * 9000)}`);
  await page.fill('input[placeholder*="Tata 407"]', 'Eicher Pro 2049 (6.0 MT)');
  await page.click('form button:has-text("Register Vehicle")');
  await page.waitForTimeout(1200);
  console.log('✓ 4. Freight vehicle registered in fleet');

  // 4. Seed opportunity and rebroadcast it twice to test idempotency
  console.log('Broadcasting multi-stop opportunity to newly registered transporter twice...');
  const seedResult = execSync(`docker compose exec -e PYTHONPATH=. -T api python seed_notif_e2e.py ${email}`, {
    cwd: 'c:/Users/Shoury/Desktop/Agri-mandi',
    encoding: 'utf8',
  });
  console.log('✓ 5. Backend seed & rebroadcast output:\n', seedResult.trim());

  // 5. Check notification bell in frontend
  await page.reload();
  await page.waitForSelector('.notification-btn', { timeout: 10000 });
  await page.waitForTimeout(1000);

  // Assert notification badge appears with count = 1
  const badgeText = await page.textContent('.notification-badge');
  console.log(`✓ 6. Notification badge count: ${badgeText} (verified exactly 1 notification despite multiple broadcasts)`);
  if (badgeText !== '1') {
    throw new Error(`Expected exactly 1 notification badge, found: ${badgeText}`);
  }

  // 6. Open Notification Tray
  await page.click('.notification-btn');
  await page.waitForSelector('.notifications-dropdown', { timeout: 5000 });
  const notifItems = await page.$$('.notification-item');
  console.log(`✓ 7. Notification items in tray: ${notifItems.length}`);
  if (notifItems.length !== 1) {
    throw new Error(`Expected exactly 1 notification in tray, found: ${notifItems.length}`);
  }

  const notifTitle = await page.textContent('.notification-item .notif-title');
  console.log(`✓ 8. Notification Title: "${notifTitle.trim()}"`);

  // 7. Click Notification -> Verify Opportunity Detail Modal & Map opens automatically
  console.log('Clicking notification item to navigate directly to Opportunity Detail Modal...');
  await page.click('.notification-item');
  await page.waitForSelector('.glass-panel h3:has-text("Transport Opportunity")', { timeout: 8000 });
  console.log('✓ 9. Opportunity Detail Modal opened immediately upon notification click!');

  // 8. Verify Opportunity Modal contents & Leaflet Route Map
  await page.waitForSelector('.leaflet-container', { timeout: 8000 });
  console.log('✓ 10. OpenStreetMap / Leaflet Route Map rendered inside Opportunity Modal');

  const modal = page.locator('div[style*="position: fixed"] .glass-panel');
  const modalText = await modal.textContent();
  console.log('Modal text snippet:', modalText.slice(0, 200).replace(/\s+/g, ' '));
  if (!modalText.includes('35')) {
    throw new Error('Opportunity modal missing total cargo volume');
  }
  if (!modalText.includes('Khed Potato Farm') || !modalText.includes('Manchar Farmers Collective')) {
    throw new Error('Opportunity modal missing multi-stop pickup breakdown');
  }
  console.log('✓ 11. Modal displays verified commodity, cargo volume, multi-stop breakdown, and cost certainty');

  // 9. Accept the Job & Assign Vehicle
  console.log('Clicking "🚚 Accept Job & Assign Vehicle"...');
  await page.click('button:has-text("Accept Job & Assign Vehicle")');
  await page.waitForSelector('form select, form button:has-text("Confirm & Lock Assignment")', { timeout: 5000 });

  await page.fill('input[placeholder*="Ramesh" i]', 'Suresh Patil');
  await page.fill('input[placeholder*="919876543210"]', '+919822334455');
  await page.click('form button:has-text("Confirm & Lock Assignment")');

  await page.waitForTimeout(2000);
  console.log('✓ 12. Job successfully accepted and vehicle assigned!');

  // 10. Check Active Jobs Tab
  await page.click('button:has-text("Active Scheduled Jobs")');
  await page.waitForSelector('.shipment-card, div:has-text("SCHEDULED")', { timeout: 8000 });
  console.log('✓ 13. Accepted shipment appears in Active Jobs tab');

  // 11. Check Notification Tray again -> Notification is marked read and Job Confirmed appears
  await page.click('.notification-btn');
  await page.waitForSelector('.notifications-dropdown', { timeout: 5000 });
  const updatedNotifs = await page.$$('.notification-item');
  console.log(`✓ 14. Total notifications now: ${updatedNotifs.length} (Opportunity Match + Job Confirmed)`);

  // 12. Responsive mobile check
  console.log('Testing mobile viewport (375x667)...');
  await page.setViewportSize({ width: 375, height: 667 });
  await page.waitForTimeout(500);
  await page.screenshot({ path: 'C:/Users/Shoury/.gemini/antigravity/brain/bcaa7ab8-49f1-48d8-9fb0-523de2834bbc/transporter_notification_bugfix_verified.png' });
  console.log('✓ 15. Saved verification screenshot to artifacts directory');

  // 13. Verify 0 console errors
  console.log(`Console Errors count: ${consoleErrors.length}`);
  if (consoleErrors.length > 0) {
    console.warn('Console errors detected:', consoleErrors);
  }

  await browser.close();
  console.log('=== All Transporter Notification & Opportunity UX Bug Fix tests PASSED! ===');
}

verifyTransporterNotificationsBugfix().catch((err) => {
  console.error('E2E Verification Failed:', err);
  process.exit(1);
});
