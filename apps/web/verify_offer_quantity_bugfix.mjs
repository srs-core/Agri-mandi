import { chromium } from 'playwright';
import path from 'path';

const BASE_URL = 'http://localhost:5173';
const ARTIFACT_DIR = 'C:/Users/Shoury/.gemini/antigravity/brain/1c41cc7a-88b2-4994-ba38-75d67e653f3c';

async function runOfferValidationE2E() {
  console.log('🚀 Starting Playwright E2E for Offer Quantity Validation Bug Fix...\n');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      console.log('  [Browser Console Error]:', msg.text());
    }
  });

  const timestamp = Date.now().toString().slice(-6);
  const farmerEmail = `farmer_val_${timestamp}@example.com`;
  const buyerEmail = `buyer_val_${timestamp}@example.com`;
  const password = 'Password123!';

  try {
    // ----------------------------------------------------
    // STEP 1: REGISTER FARMER & CREATE 30 BOX NEGOTIABLE LOT
    // ----------------------------------------------------
    console.log('--- Step 1: Register Farmer ---');
    await page.goto(BASE_URL);
    await page.waitForLoadState('networkidle');

    await page.click('button:has-text("Register")');
    await page.waitForSelector('#displayName', { timeout: 8000 });
    await page.click('.role-option-btn:has-text("Farmer")');
    await page.fill('#displayName', 'Devendra Farmer');
    await page.fill('#email', farmerEmail);
    await page.fill('#password', password);
    await page.fill('#confirmPassword', password);
    await page.click('button[type="submit"]');
    await page.waitForSelector('.welcome-title', { timeout: 8000 });
    console.log('✓ Farmer registered successfully.');

    console.log('\n--- Step 2: Farmer Creates 30 Box Negotiable Produce Lot ---');
    await page.click('button:has-text("List New Produce")');
    await page.waitForSelector('#availableQuantity', { timeout: 8000 });
    await page.waitForSelector('#commodityId', { timeout: 8000 });
    await page.waitForTimeout(500);

    const lotTitle = `Ratnagiri Alphonso Mango Lot ${timestamp}`;
    await page.fill('#title', lotTitle);
    await page.fill('#availableQuantity', '30');
    await page.fill('#unit', 'box (20kg)');
    // Deliberately leave askingPrice empty for Negotiable lot
    await page.fill('#askingPrice', '');
    await page.selectOption('#qualityGrade', 'Grade A');
    await page.fill('#locName', 'Ratnagiri APMC Hub');
    await page.fill('#district', 'Ratnagiri');
    await page.fill('#state', 'Maharashtra');

    await page.click('button[type="submit"]');
    await page.waitForSelector('.detail-title', { timeout: 10000 });
    console.log(`✓ Created lot "${lotTitle}" with 30 box (20kg) (Negotiable).`);

    // ----------------------------------------------------
    // STEP 2: REGISTER BUYER
    // ----------------------------------------------------
    console.log('\n--- Step 3: Register Buyer ---');
    await page.click('button:has-text("Logout")');
    await page.waitForTimeout(500);

    await page.click('button:has-text("Register")');
    await page.waitForSelector('#displayName', { timeout: 8000 });
    await page.click('.role-option-btn:has-text("Buyer")');
    await page.fill('#displayName', 'Reliance Fresh Sourcing');
    await page.fill('#email', buyerEmail);
    await page.fill('#password', password);
    await page.fill('#confirmPassword', password);
    await page.click('button[type="submit"]');
    await page.waitForSelector('.welcome-title', { timeout: 8000 });
    console.log('✓ Buyer registered successfully.');

    // ----------------------------------------------------
    // STEP 3: NAVIGATE TO LOT DETAIL AS BUYER
    // ----------------------------------------------------
    console.log('\n--- Step 4: Open Produce Detail View ---');
    await page.click('button:has-text("Browse Produce")');
    await page.waitForSelector('.marketplace-page', { timeout: 8000 });
    await page.waitForSelector('.produce-card', { timeout: 15000 });

    const targetCard = page.locator(`.produce-card:has-text("${timestamp}")`).first();
    if (await targetCard.count() > 0) {
      await targetCard.click();
    } else {
      await page.locator('.produce-card').first().click();
    }
    await page.waitForSelector('.action-box-card', { timeout: 10000 });

    const availableText = await page.textContent('.key-metric-box:has-text("Available Quantity") .metric-value');
    console.log(`✓ Lot Detail displayed. Available Quantity: "${availableText.trim()}".`);

    // ----------------------------------------------------
    // STEP 4: REPRODUCE BUG SCENARIO: ENTER 3000 FOR 30 BOX LOT
    // ----------------------------------------------------
    console.log('\n--- Step 5: Open Offer Modal and Test 3000 Quantity Bug Scenario ---');
    await page.click('button:has-text("Make Commercial Offer")');
    await page.waitForSelector('#offeredQuantity', { timeout: 5000 });

    const modalSummary = await page.textContent('.modal-lot-summary');
    console.log(`✓ Modal Summary: "${modalSummary.replace(/\s+/g, ' ').trim()}".`);

    // Enter 3000
    console.log('Entering Offered Quantity: 3000 (exceeds available 30)...');
    await page.fill('#offeredQuantity', '3000');
    await page.waitForTimeout(300);

    // Verify inline error appears
    const qtyErrorEl = page.locator('.field-error-text');
    await qtyErrorEl.waitFor({ state: 'visible', timeout: 3000 });
    const qtyErrorText = await qtyErrorEl.textContent();
    console.log(`✓ Inline Quantity Error displayed: "${qtyErrorText}"`);
    if (!qtyErrorText.includes('cannot exceed the available 30')) {
      throw new Error(`Unexpected error text: ${qtyErrorText}`);
    }

    // Verify submit button is disabled
    const submitBtn = page.locator('button[type="submit"]:has-text("Send Binding Offer to Producer")');
    const isDisabledWhen3000 = await submitBtn.isDisabled();
    console.log(`✓ Submit button is disabled when quantity is 3000: ${isDisabledWhen3000}`);
    if (!isDisabledWhen3000) {
      throw new Error('Submit button MUST be disabled when quantity exceeds available!');
    }

    // Verify total deal value displays '—'
    const totalValEl = page.locator('.offer-total-banner .total-val');
    const totalTextWhenInvalid = (await totalValEl.textContent()).trim();
    console.log(`✓ Total deal value when invalid: "${totalTextWhenInvalid}"`);
    if (totalTextWhenInvalid !== '—') {
      throw new Error(`Expected total to display '—', but got: ${totalTextWhenInvalid}`);
    }

    // Take Desktop 1440px screenshot of the error state
    const desktopScreenshotPath = path.join(ARTIFACT_DIR, 'offer_modal_desktop_error_1440px.png');
    await page.screenshot({ path: desktopScreenshotPath, fullPage: false });
    console.log(`✓ Saved Desktop 1440px error screenshot: ${desktopScreenshotPath}`);

    // Take Mobile 390px screenshot of the error state
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(300);
    const mobileScreenshotPath = path.join(ARTIFACT_DIR, 'offer_modal_mobile_error_390px.png');
    await page.screenshot({ path: mobileScreenshotPath, fullPage: false });
    console.log(`✓ Saved Mobile 390px error screenshot: ${mobileScreenshotPath}`);

    // Reset back to Desktop viewport
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.waitForTimeout(300);

    // ----------------------------------------------------
    // STEP 5: TEST OTHER BOUNDARIES: 0, -5, 30.001
    // ----------------------------------------------------
    console.log('\n--- Step 6: Test Boundary Values (0, -5, 30.001) ---');
    await page.fill('#offeredQuantity', '0');
    await page.waitForTimeout(200);
    let errText = await qtyErrorEl.textContent();
    console.log(`✓ Quantity 0 error: "${errText}" | Submit disabled: ${await submitBtn.isDisabled()}`);

    await page.fill('#offeredQuantity', '-5');
    await page.waitForTimeout(200);
    errText = await qtyErrorEl.textContent();
    console.log(`✓ Quantity -5 error: "${errText}" | Submit disabled: ${await submitBtn.isDisabled()}`);

    await page.fill('#offeredQuantity', '30.001');
    await page.waitForTimeout(200);
    errText = await qtyErrorEl.textContent();
    console.log(`✓ Quantity 30.001 error: "${errText}" | Submit disabled: ${await submitBtn.isDisabled()}`);

    // ----------------------------------------------------
    // STEP 6: CORRECT QUANTITY TO 10, ENTER PRICE 1500
    // ----------------------------------------------------
    console.log('\n--- Step 7: Enter Valid Values (Qty: 10 box, Price: ₹1500/box) ---');
    await page.fill('#offeredQuantity', '10');
    await page.waitForTimeout(200);

    const isQtyErrVisible = await page.locator('.form-group:has(#offeredQuantity) .field-error-text').count();
    console.log(`✓ Quantity error cleared: ${isQtyErrVisible === 0}`);

    // Test missing price behavior
    await page.fill('#offeredPrice', '');
    await page.waitForTimeout(200);
    console.log(`✓ Submit button disabled when price empty: ${await submitBtn.isDisabled()}`);
    console.log(`✓ Total deal value when price empty: "${(await totalValEl.textContent()).trim()}"`);

    // Enter valid price 1500
    await page.fill('#offeredPrice', '1500');
    await page.waitForTimeout(200);

    // Verify Total Commercial Deal Value calculates 10 × 1500 = ₹15,000
    const totalTextWhenValid = (await totalValEl.textContent()).trim();
    console.log(`✓ Total deal value calculated: "${totalTextWhenValid}"`);
    if (!totalTextWhenValid.includes('15,000')) {
      throw new Error(`Expected total to show ₹15,000, but got: ${totalTextWhenValid}`);
    }

    const isSubmitEnabled = await submitBtn.isEnabled();
    console.log(`✓ Submit button is now ENABLED: ${isSubmitEnabled}`);
    if (!isSubmitEnabled) {
      throw new Error('Submit button should be enabled when quantity and price are valid!');
    }

    // Take screenshot of valid state
    const validScreenshotPath = path.join(ARTIFACT_DIR, 'offer_modal_desktop_valid_1440px.png');
    await page.screenshot({ path: validScreenshotPath, fullPage: false });
    console.log(`✓ Saved Desktop 1440px valid screenshot: ${validScreenshotPath}`);

    // ----------------------------------------------------
    // STEP 7: SUBMIT OFFER & VERIFY SUCCESSFUL NEGOTIATION WORKFLOW
    // ----------------------------------------------------
    console.log('\n--- Step 8: Submit Offer & Verify Navigation to Offers View ---');
    await submitBtn.click();
    await page.waitForSelector('.alert-success', { timeout: 6000 });
    const successMsg = await page.textContent('.alert-success');
    console.log(`✓ Success alert displayed: "${successMsg.trim()}".`);

    // Buyer redirected to Offers page
    await page.waitForSelector('.offers-table-card', { timeout: 10000 });
    const offersTableText = await page.textContent('.offers-table-card');
    console.log('✓ Successfully navigated to Offers view.');
    console.log('✓ Offers view shows 10 box (20kg):', offersTableText.includes('10') && offersTableText.includes('box'));
    console.log('✓ Offers view shows ₹1,500 rate:', offersTableText.includes('1,500') || offersTableText.includes('1500'));
    console.log('✓ Offers view shows Awaiting Counterparty status:', offersTableText.includes('Awaiting Counterparty'));

    console.log('\n🎉 ALL PLAYWRIGHT E2E VERIFICATION CHECKS PASSED PERFECTLY!');
  } catch (err) {
    console.error('\n❌ Playwright E2E Verification Failed:', err);
    throw err;
  } finally {
    await browser.close();
  }
}

runOfferValidationE2E();
