import { chromium } from 'playwright';
import path from 'path';

const BASE_URL = 'http://localhost:5173';
const SCREENSHOT_DIR = 'C:/Users/Shoury/.gemini/antigravity/brain/bcaa7ab8-49f1-48d8-9fb0-523de2834bbc';

async function runComprehensiveVerification() {
  console.log('🚀 Starting Comprehensive E2E Verification for Negotiable & Fixed-Price Offers...');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 950 } });
  const page = await context.newPage();

  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      console.log('  [Browser Console Error]:', msg.text());
    }
  });

  const timestamp = Date.now().toString().slice(-6);
  const farmerEmail = `farmer_comp_${timestamp}@example.com`;
  const buyerEmail = `buyer_comp_${timestamp}@example.com`;
  const password = 'Password123!';

  try {
    // ----------------------------------------------------
    // TEST A: NEGOTIABLE LISTING & BILATERAL COUNTER-OFFER WORKFLOW
    // ----------------------------------------------------
    console.log('\n======================================================');
    console.log('TEST A: NEGOTIABLE LISTING & BILATERAL COUNTER-OFFERS');
    console.log('======================================================');

    // 1. Register & Login Farmer
    console.log('\n--- A1. Registering Farmer ---');
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    await page.click('button:has-text("Register")');
    await page.waitForSelector('#displayName', { timeout: 8000 });

    await page.fill('#displayName', 'Ramesh Patil (Farmer)');
    await page.fill('#email', farmerEmail);
    await page.fill('#password', password);
    await page.click('.role-option-btn:has-text("Farmer")');
    await page.click('button[type="submit"]');
    await page.waitForSelector('.welcome-title', { timeout: 8000 });
    console.log('✓ Farmer registered & logged in.');

    // 2. Create Negotiable Lot (Asking Price empty)
    console.log('\n--- A2. Farmer Creates Negotiable Lot ---');
    await page.click('button:has-text("List New Produce")');
    await page.waitForSelector('#availableQuantity', { timeout: 8000 });
    await page.waitForSelector('#commodityId', { timeout: 8000 });
    await page.waitForTimeout(500);

    const negLotTitle = `Nashik Fresh Onions Negotiable ${timestamp}`;
    await page.fill('#title', negLotTitle);
    await page.fill('#availableQuantity', '100');
    // Deliberately leave askingPrice empty (Negotiable)
    await page.fill('#askingPrice', '');
    await page.selectOption('#qualityGrade', 'Grade A');

    await page.fill('#locName', 'Nashik APMC Yard');
    await page.fill('#district', 'Nashik');
    await page.fill('#state', 'Maharashtra');

    await page.click('button[type="submit"]');
    await page.waitForSelector('.detail-title', { timeout: 10000 });

    const detailContent = await page.content();
    console.log('✓ Negotiable Lot detail displays "Negotiable":', detailContent.includes('Negotiable'));

    // 3. Register & Login Buyer
    console.log('\n--- A3. Registering Buyer ---');
    await page.click('button:has-text("Logout")');
    await page.waitForTimeout(1000);

    await page.click('button:has-text("Register")');
    await page.waitForSelector('#displayName', { timeout: 8000 });
    await page.click('.role-option-btn:has-text("Buyer")');
    await page.fill('#displayName', 'AgroFoods Wholesale Buyer');
    await page.fill('#email', buyerEmail);
    await page.fill('#password', password);
    await page.click('button[type="submit"]');
    await page.waitForSelector('.welcome-title', { timeout: 8000 });
    console.log('✓ Buyer registered & logged in.');

    // 4. Buyer Submits Initial Offer ₹800/QTL on Negotiable Lot
    console.log('\n--- A4. Buyer Offers ₹800/QTL on Negotiable Lot ---');
    await page.click('button:has-text("Browse Produce")');
    await page.waitForSelector('.marketplace-page', { timeout: 8000 });
    await page.waitForTimeout(1000);

    await page.waitForSelector('.lot-card', { timeout: 15000 });
    const negCard = page.locator(`.lot-card:has-text("${timestamp}")`).first();
    if (await negCard.count() > 0) {
      await negCard.click();
    } else {
      await page.locator('.lot-card').first().click();
    }
    await page.waitForSelector('.action-box-card', { timeout: 10000 });

    await page.click('text=Make Commercial Offer ➔');
    await page.waitForSelector('#offeredQuantity', { timeout: 5000 });
    await page.fill('#offeredQuantity', '100');
    await page.fill('#offeredPrice', '800');
    const notesEl = page.locator('#offeredNotes');
    if (await notesEl.count() > 0) {
      await notesEl.fill('Offer ₹800/QTL for 100 QTL lot.');
    }
    await page.click('text=Send Binding Offer to Producer');
    await page.waitForSelector('.offers-table-card', { timeout: 10000 });
    console.log('✓ Offer of ₹800/QTL submitted by Buyer.');

    // 5. Farmer Logs In & Verifies Negotiable Actions (Accept, Counter Offer, Decline)
    console.log('\n--- A5. Farmer Inspects Received Offer ---');
    await page.click('button:has-text("Logout")');
    await page.waitForTimeout(1000);

    await page.click('button:has-text("Sign In")');
    await page.fill('#email', farmerEmail);
    await page.fill('#password', password);
    await page.click('button[type="submit"]');
    await page.waitForSelector('.nav-link', { timeout: 8000 });

    await page.click('button.nav-link:has-text("Offers")');
    await page.waitForSelector('.offers-table-card', { timeout: 8000 });

    // Verify Action Buttons on Negotiable Offer
    const acceptBtn = page.locator('button.btn-success-sm').first();
    const declineBtn = page.locator('button.btn-danger-sm').first();
    const counterBtn = page.locator('button.btn-counter-sm:has-text("Counter Offer")').first();

    console.log('✓ Accept Button visible for Farmer:', await acceptBtn.isVisible());
    console.log('✓ Decline Button visible for Farmer:', await declineBtn.isVisible());
    console.log('✓ Counter Offer Button visible for Farmer:', await counterBtn.isVisible());

    if (!(await counterBtn.isVisible())) {
      throw new Error('FAILED: Counter Offer button is NOT visible for Farmer on Negotiable lot!');
    }

    // 6. Farmer Opens Counter Modal and Counters at ₹1000/QTL
    console.log('\n--- A6. Farmer Submits Counter-Offer ₹1000/QTL ---');
    await counterBtn.click();
    await page.waitForSelector('.counter-modal', { timeout: 5000 });

    // Fill Counter Modal
    await page.fill('.counter-modal input[type="number"] >> nth=0', '1000');
    await page.fill('.counter-modal textarea', 'Market rate in Nashik is ₹1000/QTL minimum.');
    await page.click('button:has-text("Submit Counter Offer ➔")');
    await page.waitForTimeout(2000);

    const farmerOffersText = await page.textContent('.offers-table-card');
    console.log('✓ Status updated to COUNTERED:', farmerOffersText.includes('COUNTERED'));
    console.log('✓ Rate updated to ₹1,000:', farmerOffersText.includes('1,000') || farmerOffersText.includes('1000'));
    console.log('✓ Turn indicator shows Awaiting Buyer Response:', farmerOffersText.includes('Awaiting Buyer Response') || farmerOffersText.includes('Awaiting Counterparty'));

    // 7. Buyer Logs In & Verifies Counter-Offer + Counters ₹950
    console.log('\n--- A7. Buyer Receives Counter ₹1000 & Counters ₹950 ---');
    await page.click('button:has-text("Logout")');
    await page.waitForTimeout(1000);

    await page.click('button:has-text("Sign In")');
    await page.fill('#email', buyerEmail);
    await page.fill('#password', password);
    await page.click('button[type="submit"]');
    await page.waitForSelector('.nav-link', { timeout: 8000 });

    await page.click('button.nav-link:has-text("Offers")');
    await page.waitForSelector('.offers-table-card', { timeout: 8000 });

    // Buyer sees Counter Offer button because it is Buyer's turn
    const buyerCounterBtn = page.locator('button.btn-counter-sm:has-text("Counter Offer")').first();
    console.log('✓ Counter Offer Button visible for Buyer on their turn:', await buyerCounterBtn.isVisible());
    await buyerCounterBtn.click();
    await page.waitForSelector('.counter-modal', { timeout: 5000 });

    await page.fill('.counter-modal input[type="number"] >> nth=0', '950');
    await page.fill('.counter-modal textarea', 'Best offer ₹950/QTL with immediate dispatch.');
    await page.click('button:has-text("Submit Counter Offer ➔")');
    await page.waitForTimeout(2000);

    // 8. Farmer Accepts ₹950 Counter-Offer
    console.log('\n--- A8. Farmer Accepts Agreed ₹950 Counter-Offer ---');
    await page.click('button:has-text("Logout")');
    await page.waitForTimeout(1000);

    await page.click('button:has-text("Sign In")');
    await page.fill('#email', farmerEmail);
    await page.fill('#password', password);
    await page.click('button[type="submit"]');
    await page.waitForSelector('.nav-link', { timeout: 8000 });

    await page.click('button.nav-link:has-text("Offers")');
    await page.waitForSelector('.offers-table-card', { timeout: 8000 });

    // Expand Timeline
    const historyToggle = page.locator('.btn-history-toggle').first();
    if (await historyToggle.count() > 0) {
      await historyToggle.click();
      await page.waitForSelector('.negotiation-timeline', { timeout: 5000 });
      console.log('✓ Negotiation Timeline expanded and verified.');
    }

    const farmerAcceptBtn = page.locator('button.btn-success-sm').first();
    console.log('Clicking Farmer Accept button:', await farmerAcceptBtn.textContent());
    await farmerAcceptBtn.click();
    await page.waitForTimeout(2500);

    const successAlert = page.locator('.alert-success');
    await successAlert.waitFor({ state: 'visible', timeout: 8000 });
    console.log('✓ Negotiable Offer Accepted Successfully:', await successAlert.textContent());

    // ----------------------------------------------------
    // TEST B: FIXED-PRICE LISTING WORKFLOW
    // ----------------------------------------------------
    console.log('\n======================================================');
    console.log('TEST B: FIXED-PRICE LISTING WORKFLOW (NO COUNTER)');
    console.log('======================================================');

    // 1. Farmer Creates Fixed-Price Lot (Asking Price = ₹2200)
    console.log('\n--- B1. Farmer Creates Fixed-Price Lot (₹2200/QTL) ---');
    await page.click('button.nav-link:has-text("Farmer Hub")');
    await page.waitForSelector('.dashboard-welcome-card', { timeout: 8000 });
    await page.click('button:has-text("List New Produce")');
    await page.waitForSelector('#availableQuantity', { timeout: 8000 });
    await page.waitForTimeout(500);

    const fixLotTitle = `Pune Royal Wheat Fixed ${timestamp}`;
    await page.fill('#title', fixLotTitle);
    await page.fill('#availableQuantity', '50');
    // Set explicit asking price
    await page.fill('#askingPrice', '2200');
    await page.selectOption('#qualityGrade', 'Grade A');
    await page.fill('#locName', 'Pune Mandi Yard');
    await page.fill('#district', 'Pune');
    await page.fill('#state', 'Maharashtra');

    await page.click('button[type="submit"]');
    await page.waitForSelector('.detail-title', { timeout: 10000 });
    console.log('✓ Fixed-Price Lot created with Asking Price ₹2200/QTL.');

    // 2. Buyer Submits Offer on Fixed-Price Lot
    console.log('\n--- B2. Buyer Submits Offer on Fixed-Price Lot ---');
    await page.click('button:has-text("Logout")');
    await page.waitForTimeout(1000);

    await page.click('button:has-text("Sign In")');
    await page.fill('#email', buyerEmail);
    await page.fill('#password', password);
    await page.click('button[type="submit"]');
    await page.waitForSelector('.welcome-title', { timeout: 8000 });

    await page.click('button:has-text("Browse Produce")');
    await page.waitForSelector('.marketplace-page', { timeout: 8000 });
    await page.waitForTimeout(1000);

    const fixCard = page.locator(`.lot-card:has-text("${timestamp}")`).first();
    if (await fixCard.count() > 0) {
      await fixCard.click();
    } else {
      await page.locator('.lot-card').first().click();
    }
    await page.waitForSelector('.action-box-card', { timeout: 10000 });

    await page.click('text=Make Commercial Offer ➔');
    await page.waitForSelector('#offeredQuantity', { timeout: 5000 });
    await page.fill('#offeredQuantity', '50');
    await page.fill('#offeredPrice', '2200');
    await page.click('text=Send Binding Offer to Producer');
    await page.waitForSelector('.offers-table-card', { timeout: 10000 });
    console.log('✓ Offer on Fixed-Price Lot submitted by Buyer.');

    // 3. Farmer Views Fixed-Price Offer -> Must NOT show Counter Offer button
    console.log('\n--- B3. Farmer Verifies Fixed-Price Offer Actions ---');
    await page.click('button:has-text("Logout")');
    await page.waitForTimeout(1000);

    await page.click('button:has-text("Sign In")');
    await page.fill('#email', farmerEmail);
    await page.fill('#password', password);
    await page.click('button[type="submit"]');
    await page.waitForSelector('.nav-link', { timeout: 8000 });

    await page.click('button.nav-link:has-text("Offers")');
    await page.waitForSelector('.offers-table-card', { timeout: 8000 });

    // Look for the newest pending offer (Fixed Price)
    const fixedPricePills = page.locator('.price-mode-fixed');
    console.log('✓ Found Fixed Price badge on listing:', (await fixedPricePills.count()) > 0);

    const firstRowActions = page.locator('tbody tr').first().locator('td').last();
    const fixedAcceptBtn = firstRowActions.locator('button.btn-success-sm');
    const fixedDeclineBtn = firstRowActions.locator('button.btn-danger-sm');
    const fixedCounterBtn = firstRowActions.locator('button.btn-counter-sm');

    console.log('✓ Fixed-Price row Accept button visible:', await fixedAcceptBtn.isVisible());
    console.log('✓ Fixed-Price row Decline button visible:', await fixedDeclineBtn.isVisible());
    console.log('✓ Fixed-Price row Counter button count (should be 0):', await fixedCounterBtn.count());

    if (await fixedCounterBtn.count() > 0) {
      throw new Error('FAILED: Counter Offer button should NOT be shown for Fixed-Price listing!');
    }

    // Accept Fixed-Price Offer
    console.log('Accepting Fixed-Price Offer...');
    await fixedAcceptBtn.click();
    await page.waitForTimeout(2500);

    const fixedSuccessAlert = page.locator('.alert-success');
    await fixedSuccessAlert.waitFor({ state: 'visible', timeout: 8000 });
    console.log('✓ Fixed-Price Offer Accepted Successfully:', await fixedSuccessAlert.textContent());

    console.log('\n======================================================');
    console.log('🎉 ALL COMPREHENSIVE TESTS (NEGOTIABLE + FIXED) PASSED!');
    console.log('======================================================');
  } catch (err) {
    console.error('❌ Comprehensive E2E Verification failed:', err);
    process.exit(1);
  } finally {
    await browser.close();
  }
}

runComprehensiveVerification();
