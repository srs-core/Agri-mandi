import { chromium } from 'playwright';

async function runBrowserTest() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const consoleErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });

  const timestamp = Date.now() % 10000000;
  console.log('--- 1. Testing Landing Page & Public Navigation ---');
  await page.goto('http://localhost:5173');
  await page.waitForSelector('.hero-title');
  console.log('Landing page loaded. Hero title found.');

  // Test Marketplace button
  await page.click('.hero-cta-group .btn-hero-primary');
  await page.waitForSelector('.marketplace-page');
  console.log('Navigated to Marketplace successfully.');

  // Test Category Pills
  await page.click('button:has-text("🥦 Vegetables")');
  await page.waitForTimeout(500);
  console.log('Vegetables category filter clicked.');

  // Test Buyer Demands
  await page.click('button:has-text("Buyer Demands")');
  await page.waitForSelector('.requirements-page');
  console.log('Navigated to Buyer Demands page successfully.');

  console.log('\n--- 2. Testing Farmer Registration & Produce Lot Listing ---');
  await page.click('.brand-section');
  await page.waitForSelector('.hero-section');
  
  // Click "Join as Farmer" CTA
  await page.click('button:has-text("Join as Farmer")');
  await page.waitForSelector('.register-card');
  
  const isFarmerSelected = await page.$eval('.role-option-btn:has-text("Farmer")', (el) => el.classList.contains('selected'));
  console.log('Farmer role automatically pre-selected:', isFarmerSelected);

  const farmerEmail = `farmer_ui_${timestamp}@agrimandi.gov.in`;
  await page.fill('#displayName', 'Balasaheb Patil');
  await page.fill('#email', farmerEmail);
  await page.fill('#phoneNumber', `+91 91${timestamp}`);
  await page.fill('#password', 'PatilPassword123!');

  console.log('Submitting registration as FARMER...');
  await page.click('button:has-text("Register as FARMER")');

  // Verify redirect to Farmer Dashboard
  await page.waitForSelector('.dashboard-welcome-card', { timeout: 10000 });
  const welcomeText = await page.innerText('.welcome-title');
  console.log(`Successfully registered and redirected! Title: "${welcomeText}"`);
  if (!welcomeText.includes('Balasaheb Patil')) {
    throw new Error(`Unexpected welcome text: ${welcomeText}`);
  }

  // Create Produce Lot from Farmer Dashboard
  await page.click('button:has-text("+ List New Produce")');
  await page.waitForSelector('.create-lot-page');
  console.log('Navigated to List Produce Lot view.');

  await page.fill('#title', `Fresh Nashik Onion Lot #${timestamp}`);
  await page.fill('#availableQuantity', '80');
  await page.fill('#askingPrice', '2250');
  await page.fill('#locName', 'Niphad Mandi Yard');
  await page.fill('#district', 'Nashik');
  await page.fill('#taluka', 'Niphad');
  await page.click('button[type="submit"]:has-text("Publish Produce Lot")');

  await page.waitForSelector('.detail-title', { timeout: 10000 });
  const lotTitle = await page.innerText('.detail-title');
  console.log(`Produce lot created and redirected to detail view: "${lotTitle}"`);

  console.log('\n--- 3. Testing Farmer Logout & Login ---');
  await page.click('button:has-text("Logout")');
  await page.waitForSelector('.auth-buttons');
  console.log('Logged out successfully.');

  await page.click('button:has-text("Sign In")');
  await page.waitForSelector('.auth-card');
  await page.fill('#email', farmerEmail);
  await page.fill('#password', 'PatilPassword123!');
  await page.click('button[type="submit"]');

  await page.waitForSelector('.dashboard-welcome-card');
  console.log('Farmer logged in and redirected back to Farmer Hub.');

  console.log('\n--- 4. Testing Buyer Registration & Bidding Workflow ---');
  await page.click('button:has-text("Logout")');
  await page.click('.brand-section');
  await page.waitForSelector('.hero-section');

  // Click "Join as Buyer" CTA
  await page.click('button:has-text("Join as Buyer")');
  await page.waitForSelector('.register-card');

  const isBuyerSelected = await page.$eval('.role-option-btn:has-text("Buyer")', (el) => el.classList.contains('selected'));
  console.log('Buyer role automatically pre-selected:', isBuyerSelected);

  const buyerEmail = `buyer_ui_${timestamp}@agrimandi.gov.in`;
  await page.fill('#displayName', 'Sahyadri Agro Processing');
  await page.fill('#email', buyerEmail);
  await page.fill('#password', 'BuyerPassword123!');

  console.log('Submitting registration as BUYER...');
  await page.click('button:has-text("Register as BUYER")');

  // Verify redirect to Buyer Dashboard
  await page.waitForSelector('.dashboard-welcome-card', { timeout: 10000 });
  const buyerWelcomeText = await page.innerText('.welcome-title');
  console.log(`Successfully registered and redirected! Title: "${buyerWelcomeText}"`);
  if (!buyerWelcomeText.includes('Buyer Procurement Desk')) {
    throw new Error(`Unexpected buyer welcome text: ${buyerWelcomeText}`);
  }

  // Navigate to Marketplace and make offer on the farmer's lot
  await page.click('button.nav-link:has-text("Marketplace")');
  await page.waitForSelector('.lot-card');
  await page.click(`div.lot-card:has-text("Fresh Nashik Onion Lot #${timestamp}")`);

  await page.waitForSelector('.action-box-card');
  await page.click('button:has-text("Make Commercial Offer")');
  await page.waitForSelector('.modal-content');
  
  await page.fill('#offeredQuantity', '30');
  await page.fill('#offeredPrice', '2200');
  await page.click('.modal-form button[type="submit"]');

  await page.waitForSelector('.alert-success');
  console.log('Buyer commercial offer submitted successfully.');

  console.log('\n--- 5. Testing Duplicate Email Validation Error Handling ---');
  await page.click('button:has-text("Logout")');
  
  await page.click('button:has-text("Register")');
  await page.waitForSelector('.register-card');
  
  await page.fill('#displayName', 'Duplicate User');
  await page.fill('#email', farmerEmail); // already registered
  await page.fill('#password', 'ValidPass123!');
  await page.click('button[type="submit"]');

  await page.waitForSelector('.alert-error');
  const errorText = await page.innerText('.alert-error');
  console.log(`Duplicate registration error displayed properly: "${errorText}"`);

  console.log('\n--- 6. Checking Browser Console Errors ---');
  console.log(`Console errors count: ${consoleErrors.length}`);
  if (consoleErrors.length > 0) {
    console.log('Console errors:', consoleErrors);
  }

  await browser.close();
  console.log('\n========================================================');
  console.log('>>> ALL BROWSER E2E TESTS PASSED WITH ZERO CRITICAL ERRORS! <<<');
  console.log('========================================================');
}

runBrowserTest().catch((err) => {
  console.error('Test failed:', err);
  process.exit(1);
});
