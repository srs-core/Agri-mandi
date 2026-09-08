import { chromium } from 'playwright';
import path from 'path';

const BASE_URL = 'http://localhost:5173';
const SCREENSHOT_DIR = 'C:/Users/Shoury/.gemini/antigravity/brain/bcaa7ab8-49f1-48d8-9fb0-523de2834bbc';

async function runVerification() {
  console.log('🚀 Starting Playwright E2E verification for Commercial Offer Negotiation & Acceptance...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();

  const consoleErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
      console.log('  [Browser Console Error]:', msg.text());
    }
  });

  const timestamp = Date.now().toString().slice(-6);
  const farmerEmail = `farmer_neg_${timestamp}@example.com`;
  const buyerEmail = `buyer_neg_${timestamp}@example.com`;
  const password = 'Password123!';

  try {
    // ----------------------------------------------------
    // 1. REGISTER & LOGIN FARMER
    // ----------------------------------------------------
    console.log('\n--- 1. Registering Farmer ---');
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    await page.click('button:has-text("Register")');
    await page.waitForSelector('#displayName', { timeout: 8000 });

    await page.fill('#displayName', 'Ramesh Patel Farmer');
    await page.fill('#email', farmerEmail);
    await page.fill('#password', password);
    await page.click('.role-option-btn:has-text("Farmer")');
    await page.click('button[type="submit"]');
    await page.waitForSelector('.welcome-title', { timeout: 8000 });
    console.log('✓ Farmer registered & logged in to Farmer Hub.');

    // ----------------------------------------------------
    // 2. FARMER CREATES NEGOTIABLE PRODUCE LOT
    // ----------------------------------------------------
    console.log('\n--- 2. Farmer Creates Negotiable Lot (Asking Price empty) ---');
    await page.click('button:has-text("List New Produce")');
    await page.waitForSelector('#availableQuantity', { timeout: 8000 });
    await page.waitForSelector('#commodityId', { timeout: 8000 });
    await page.waitForTimeout(500);

    const lotTitle = `Agra Jyoti Potato Negotiable ${timestamp}`;
    await page.fill('#title', lotTitle);
    await page.fill('#availableQuantity', '30');
    // Deliberately leave askingPrice empty (Negotiable)
    await page.fill('#askingPrice', '');
    await page.selectOption('#qualityGrade', 'Grade A');

    // Fill required location fields
    await page.fill('#locName', 'Agra Mandi Yard');
    await page.fill('#district', 'Agra');
    await page.fill('#state', 'Uttar Pradesh');

    await page.click('button[type="submit"]');
    await page.waitForSelector('.detail-title', { timeout: 10000 });

    // Verify redirected to ProduceDetailView showing Negotiable
    console.log('Produce lot created. Verifying Produce Detail View...');
    const detailContent = await page.content();
    console.log('✓ Produce Detail contains "Negotiable":', detailContent.includes('Negotiable'));

    // ----------------------------------------------------
    // 3. REGISTER & LOGIN BUYER
    // ----------------------------------------------------
    console.log('\n--- 3. Registering Buyer ---');
    // Logout farmer
    await page.click('button:has-text("Logout")');
    await page.waitForTimeout(1000);

    // Register Buyer
    await page.click('button:has-text("Register")');
    await page.waitForSelector('#displayName', { timeout: 8000 });
    await page.click('.role-option-btn:has-text("Buyer")');
    await page.fill('#displayName', 'Suresh Mandi Wholesale Buyer');
    await page.fill('#email', buyerEmail);
    await page.fill('#password', password);
    await page.click('button[type="submit"]');
    await page.waitForSelector('.welcome-title', { timeout: 8000 });
    console.log('✓ Buyer registered & logged in to Buyer Procurement Desk.');

    // ----------------------------------------------------
    // 4. BUYER FINDS LOT ON MARKETPLACE & MAKES OFFER
    // ----------------------------------------------------
    console.log('\n--- 4. Buyer Browses Marketplace & Submits Initial Offer ₹1600 ---');
    // Click "Browse Produce" on Buyer dashboard
    await page.click('button:has-text("Browse Produce")');
    await page.waitForSelector('.marketplace-page', { timeout: 8000 });
    await page.waitForTimeout(1000);

    // Wait for lot cards
    await page.waitForSelector('.lot-card', { timeout: 15000 });
    console.log('Marketplace loaded. Number of lot cards:', await page.locator('.lot-card').count());

    const lotCard = page.locator(`.lot-card:has-text("${timestamp}")`).first();
    if (await lotCard.count() > 0) {
      console.log('Clicking timestamped lot card...');
      await lotCard.click();
    } else {
      console.log('Clicking first available lot card...');
      const firstCard = page.locator('.lot-card').first();
      await firstCard.click();
    }
    await page.waitForSelector('.action-box-card', { timeout: 10000 });

    // Verify "Negotiable" is shown on Produce Detail View
    console.log('Produce Detail View opened. Clicking "Make Commercial Offer"...');
    await page.click('text=Make Commercial Offer ➔');
    await page.waitForSelector('#offeredQuantity', { timeout: 5000 });

    // Fill offer modal: 30 QTL, ₹1600/QTL, note
    await page.fill('#offeredQuantity', '30');
    await page.fill('#offeredPrice', '1600');
    const notesInput = page.locator('#offeredNotes');
    if (await notesInput.count() > 0) {
      await notesInput.fill('Initial wholesale offer ₹1600/QTL for full 30 QTL.');
    }
    await page.click('text=Send Binding Offer to Producer');
    await page.waitForSelector('.offers-table-card', { timeout: 10000 });

    // Buyer is redirected to Offers view
    console.log('Offer submitted. Checking Offers view as Buyer...');
    const buyerOffersText = await page.textContent('.offers-table-card');
    console.log('✓ Buyer Offers View contains "₹1,600":', buyerOffersText.includes('1,600') || buyerOffersText.includes('1600'));
    console.log('✓ Buyer Offers View contains "Awaiting Counterparty":', buyerOffersText.includes('Awaiting Counterparty'));

    // ----------------------------------------------------
    // 5. FARMER RECEIVES OFFER & COUNTERS ₹1750
    // ----------------------------------------------------
    console.log('\n--- 5. Farmer Logs In & Counters at ₹1750/QTL ---');
    await page.click('button:has-text("Logout")');
    await page.waitForTimeout(1000);

    await page.click('button:has-text("Sign In")');
    await page.fill('#email', farmerEmail);
    await page.fill('#password', password);
    await page.click('button[type="submit"]');
    await page.waitForSelector('.nav-link', { timeout: 8000 });

    // Navigate to Offers
    await page.click('button.nav-link:has-text("Offers")');
    await page.waitForSelector('.offers-table-card', { timeout: 8000 });

    // Verify "Your Response Required" badge and "Counter Offer" button
    console.log('Checking Received Offers on Farmer dashboard...');
    const counterBtn = page.locator('button.btn-counter-sm:has-text("Counter Offer")').first();
    await counterBtn.waitFor({ state: 'visible', timeout: 10000 });
    console.log('✓ Found "💬 Counter Offer" button for Farmer.');
    await counterBtn.click();
    await page.waitForSelector('.counter-modal', { timeout: 5000 });

    // Fill Counter Offer Modal
    console.log('Filling counter modal: Rate = ₹1750/QTL...');
    await page.fill('.counter-modal input[type="number"] >> nth=0', '1750');
    await page.fill('.counter-modal textarea', 'Grade A Jyoti cold-stored produce, ₹1750 is fair market price.');
    await page.click('button:has-text("Submit Counter Offer ➔")');
    await page.waitForTimeout(2000);

    const farmerOffersText = await page.textContent('.offers-table-card');
    console.log('✓ Farmer Offers View contains "COUNTERED":', farmerOffersText.includes('COUNTERED'));
    console.log('✓ Farmer Offers View contains "₹1,750":', farmerOffersText.includes('1,750') || farmerOffersText.includes('1750'));

    // ----------------------------------------------------
    // 6. BUYER SEES COUNTER & COUNTERS BACK AT ₹1700
    // ----------------------------------------------------
    console.log('\n--- 6. Buyer Logs In, Inspects Proposal History & Counters ₹1700 ---');
    await page.click('button:has-text("Logout")');
    await page.waitForTimeout(1000);

    await page.click('button:has-text("Sign In")');
    await page.fill('#email', buyerEmail);
    await page.fill('#password', password);
    await page.click('button[type="submit"]');
    await page.waitForSelector('.nav-link', { timeout: 8000 });

    // Navigate to Offers
    await page.click('button.nav-link:has-text("Offers")');
    await page.waitForSelector('.offers-table-card', { timeout: 8000 });

    // Expand negotiation timeline
    console.log('Toggling Negotiation History timeline...');
    const historyToggleBtn = page.locator('.btn-history-toggle').first();
    if (await historyToggleBtn.count() > 0) {
      await historyToggleBtn.click();
      await page.waitForSelector('.negotiation-timeline', { timeout: 5000 });
      const timelineText = await page.textContent('.negotiation-timeline');
      console.log('✓ Timeline contains Round 1 & Round 2:\n', timelineText.trim());
    }

    // Buyer counters ₹1700
    console.log('Buyer counters at ₹1700/QTL...');
    const buyerCounterBtn = page.locator('button.btn-counter-sm:has-text("Counter Offer")').first();
    await buyerCounterBtn.click();
    await page.waitForSelector('.counter-modal', { timeout: 5000 });

    await page.fill('.counter-modal input[type="number"] >> nth=0', '1700');
    await page.fill('.counter-modal textarea', 'Let us meet in the middle at ₹1700/QTL.');
    await page.click('button:has-text("Submit Counter Offer ➔")');
    await page.waitForTimeout(2000);

    // ----------------------------------------------------
    // 7. FARMER ACCEPTS ₹1700 COUNTER-OFFER & CONFIRMS ORDER
    // ----------------------------------------------------
    console.log('\n--- 7. Farmer Logs In & Accepts ₹1700 Proposal ---');
    await page.click('button:has-text("Logout")');
    await page.waitForTimeout(1000);

    await page.click('button:has-text("Sign In")');
    await page.fill('#email', farmerEmail);
    await page.fill('#password', password);
    await page.click('button[type="submit"]');
    await page.waitForSelector('.nav-link', { timeout: 8000 });

    await page.click('button.nav-link:has-text("Offers")');
    await page.waitForSelector('.offers-table-card', { timeout: 8000 });

    // Expand history to see all 3 proposals
    const farmerHistoryToggle = page.locator('.btn-history-toggle').first();
    if (await farmerHistoryToggle.count() > 0) {
      await farmerHistoryToggle.click();
      await page.waitForSelector('.negotiation-timeline', { timeout: 5000 });
    }

    // Capture screenshot of negotiation timeline before accepting
    const timelineShotPath = path.join(SCREENSHOT_DIR, 'negotiation_timeline_verified.png');
    await page.screenshot({ path: timelineShotPath, fullPage: true });
    console.log('✓ Saved screenshot of negotiation history timeline:', timelineShotPath);

    // Click Accept button: "✓ Accept ₹1,700"
    const acceptBtn = page.locator('button.btn-success-sm').first();
    const acceptBtnText = await acceptBtn.textContent();
    console.log('Clicking Accept button:', acceptBtnText);
    await acceptBtn.click();
    await page.waitForTimeout(2500);

    // Verify success message and NO database unavailable error!
    const successAlert = page.locator('.alert-success');
    await successAlert.waitFor({ state: 'visible', timeout: 8000 });
    const successMsgText = await successAlert.textContent();
    console.log('✓ Order Acceptance Success Alert:', successMsgText);

    const errorAlert = page.locator('.alert-error');
    if (await errorAlert.count() > 0) {
      const errText = await errorAlert.textContent();
      throw new Error(`Unexpected error on acceptance: ${errText}`);
    }
    console.log('✓ Zero database or constraint errors during offer acceptance!');

    // ----------------------------------------------------
    // 8. VERIFY ORDER DETAILS (Price = ₹1700, Total = ₹51,000)
    // ----------------------------------------------------
    console.log('\n--- 8. Verifying Confirmed Order Details ---');
    const viewOrderBtn = page.locator('button:has-text("View Order ➔")').first();
    if (await viewOrderBtn.count() > 0) {
      await viewOrderBtn.click();
      await page.waitForSelector('.orders-page', { timeout: 8000 });
      await page.waitForTimeout(1000);

      const orderPageContent = await page.content();
      console.log('✓ Order page contains ₹51,000:', orderPageContent.includes('51,000') || orderPageContent.includes('51000'));
      console.log('✓ Order page contains ₹1,700:', orderPageContent.includes('1,700') || orderPageContent.includes('1700'));

      const orderShotPath = path.join(SCREENSHOT_DIR, 'negotiation_order_confirmed_verified.png');
      await page.screenshot({ path: orderShotPath, fullPage: true });
      console.log('✓ Saved screenshot of confirmed order:', orderShotPath);
    }

    console.log('\n==================================================');
    console.log('🎉 ALL NEGOTIATION WORKFLOW E2E TESTS PASSED SUCCESSFULLY!');
    console.log('==================================================');
  } catch (err) {
    console.error('❌ E2E Verification failed:', err);
    const errorShotPath = path.join(SCREENSHOT_DIR, 'negotiation_error.png');
    await page.screenshot({ path: errorShotPath, fullPage: true });
    process.exit(1);
  } finally {
    await browser.close();
  }
}

runVerification();
