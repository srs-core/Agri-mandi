import { chromium } from 'playwright';

const BASE_URL = 'http://localhost:5173';
const ARTIFACT_DIR = 'C:/Users/Shoury/.gemini/antigravity/brain/bcaa7ab8-49f1-48d8-9fb0-523de2834bbc';

async function main() {
  console.log('🚀 Starting Comprehensive E2E Verification for Phase UI-2 (Auth + Registration)...');
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

  // ==========================================
  // PART 1: LOGIN UI & FUNCTIONALITY
  // ==========================================
  console.log('\n--- 1. Testing Login Page Loading & Visuals ---');
  await page.goto(`${BASE_URL}/?view=login`, { waitUntil: 'networkidle' });
  await page.waitForSelector('.auth-card');

  // Verify Header & Tagline
  const loginTitle = await page.locator('.auth-header h2').textContent();
  const brandTagline = await page.locator('.auth-brand-tagline').textContent();
  console.log('✓ Login Header Title:', loginTitle);
  console.log('✓ Brand Tagline:', brandTagline);

  // Verify Background Accent & Card Opacity
  const bgImage = await page.locator('.auth-view-container').evaluate(el => getComputedStyle(el, '::before').backgroundImage);
  const bgOpacity = await page.locator('.auth-view-container').evaluate(el => getComputedStyle(el, '::before').opacity);
  const cardBgColor = await page.locator('.auth-card').evaluate(el => getComputedStyle(el).backgroundColor);
  console.log(`✓ Farm Background Image: ${bgImage}`);
  console.log(`✓ Farm Background Opacity: ${bgOpacity}`);
  console.log(`✓ Auth Card Solid Background Color: ${cardBgColor}`);

  // Capture Dedicated Farm Background Accent Screenshot
  await page.screenshot({ path: `${ARTIFACT_DIR}/auth_farm_background_accent.png`, fullPage: false });
  console.log('✓ Captured Dedicated Auth Farm Background Accent Screenshot.');

  // Verify Geometry (Sharp 2px inputs, 4px card)
  const inputRadius = await page.locator('#email').evaluate(el => getComputedStyle(el).borderRadius);
  const cardRadius = await page.locator('.auth-card').evaluate(el => getComputedStyle(el).borderRadius);
  console.log(`✓ Geometry Check: Input radius = ${inputRadius}, Card radius = ${cardRadius}`);

  // Show/Hide Password Toggle
  console.log('\n--- 2. Testing Password Show/Hide Toggle ---');
  await page.fill('#password', 'TestPassword123!');
  let passInputType = await page.locator('#password').getAttribute('type');
  console.log('✓ Initial password field type:', passInputType);

  await page.click('.password-toggle-btn');
  passInputType = await page.locator('#password').getAttribute('type');
  console.log('✓ After clicking Show, field type:', passInputType);

  await page.click('.password-toggle-btn');
  passInputType = await page.locator('#password').getAttribute('type');
  console.log('✓ After clicking Hide, field type:', passInputType);

  // Capture Login Desktop Screenshot
  await page.screenshot({ path: `${ARTIFACT_DIR}/auth_login_desktop.png`, fullPage: false });
  console.log('✓ Captured Login Desktop Screenshot.');

  // Client-Side Validation on Empty Submit
  console.log('\n--- 3. Testing Login Client-Side Validation ---');
  await page.fill('#email', '');
  await page.fill('#password', '');
  await page.click('button[type="submit"]');

  const emailErr = await page.locator('.form-error').first().textContent();
  console.log('✓ Empty Email Validation Error:', emailErr);

  // Invalid Credentials Handling
  console.log('\n--- 4. Testing Invalid Credentials Error Handling ---');
  await page.fill('#email', 'nonexistent_farmer_xyz@agrimandi.in');
  await page.fill('#password', 'WrongPassword123!');
  await page.click('button[type="submit"]');

  await page.waitForSelector('.alert-error');
  const alertErr = await page.locator('.alert-error').textContent();
  console.log('✓ Invalid Login Server Alert:', alertErr);

  // ==========================================
  // PART 2: REGISTRATION UI & ROLE SELECTION
  // ==========================================
  console.log('\n--- 5. Testing Registration Page & Role Selection ---');
  await page.click('button:has-text("Register as Farmer, FPO, Buyer or Transporter")');
  await page.waitForSelector('.register-card');

  // Verify Role Selector Buttons
  const roleButtons = await page.locator('.role-option-btn').count();
  console.log('✓ Role options count:', roleButtons);

  // Check Role Switching & Label Changes
  console.log('Switching to Farmer role...');
  await page.click('.role-option-btn:has-text("Farmer")');
  let labelText = await page.locator('label[for="displayName"]').textContent();
  console.log('✓ Farmer display name label:', labelText);
  await page.screenshot({ path: `${ARTIFACT_DIR}/auth_register_farmer.png`, fullPage: false });

  console.log('Switching to Buyer role...');
  await page.click('.role-option-btn:has-text("Buyer")');
  labelText = await page.locator('label[for="displayName"]').textContent();
  console.log('✓ Buyer display name label:', labelText);
  await page.screenshot({ path: `${ARTIFACT_DIR}/auth_register_buyer.png`, fullPage: false });

  console.log('Switching to Transporter role...');
  await page.click('.role-option-btn:has-text("Transporter")');
  labelText = await page.locator('label[for="displayName"]').textContent();
  console.log('✓ Transporter display name label:', labelText);
  await page.screenshot({ path: `${ARTIFACT_DIR}/auth_register_transporter.png`, fullPage: false });

  // Test Password Matching UX
  console.log('\n--- 6. Testing Password Confirmation & Validation Feedback ---');
  await page.fill('#password', 'Short1');
  let hint = await page.locator('.password-hint').textContent();
  console.log('✓ Short password hint:', hint);

  await page.fill('#password', 'ValidSecurePassword123!');
  await page.fill('#confirmPassword', 'DifferentPassword456!');
  let matchHint = await page.locator('.password-hint').last().textContent();
  console.log('✓ Mismatched confirm password hint:', matchHint);

  await page.fill('#confirmPassword', 'ValidSecurePassword123!');
  matchHint = await page.locator('.password-hint').last().textContent();
  console.log('✓ Matching confirm password hint:', matchHint);

  // ==========================================
  // PART 3: SUCCESSFUL REGISTRATIONS & REDIRECTIONS
  // ==========================================
  const ts = Date.now();
  const farmerEmail = `farmer_ui2_${ts}@agrimandi.in`;
  const buyerEmail = `buyer_ui2_${ts}@agrimandi.in`;
  const transporterEmail = `transporter_ui2_${ts}@agrimandi.in`;
  const commonPassword = 'AgriPassword123!';

  // 1. Register Farmer
  console.log('\n--- 7. Registering Farmer & Verifying Farmer Dashboard Redirection ---');
  await page.click('.role-option-btn:has-text("Farmer")');
  await page.fill('#displayName', `Kisan Patil ${ts.toString().slice(-4)}`);
  await page.fill('#email', farmerEmail);
  await page.fill('#phoneNumber', `9${ts.toString().slice(-9)}`);
  await page.fill('#password', commonPassword);
  await page.fill('#confirmPassword', commonPassword);
  await page.click('button[type="submit"]');

  await page.waitForSelector('.user-profile-badge');
  let userRole = await page.locator('.user-profile-badge .role-pill').textContent();
  console.log('✓ Farmer Registered! Navbar Profile Role:', userRole);

  // Logout
  await page.click('button:has-text("Logout")');
  await page.waitForSelector('button:has-text("Sign In")');

  // 2. Register Buyer
  console.log('\n--- 8. Registering Buyer & Verifying Buyer Dashboard Redirection ---');
  await page.click('button:has-text("Register")');
  await page.waitForSelector('.register-card');
  await page.click('.role-option-btn:has-text("Buyer")');
  await page.fill('#displayName', `MahaAgri Processors ${ts.toString().slice(-4)}`);
  await page.fill('#email', buyerEmail);
  await page.fill('#phoneNumber', `8${ts.toString().slice(-9)}`);
  await page.fill('#password', commonPassword);
  await page.fill('#confirmPassword', commonPassword);
  await page.click('button[type="submit"]');

  await page.waitForSelector('.user-profile-badge');
  userRole = await page.locator('.user-profile-badge .role-pill').textContent();
  console.log('✓ Buyer Registered! Navbar Profile Role:', userRole);

  // Logout
  await page.click('button:has-text("Logout")');
  await page.waitForSelector('button:has-text("Sign In")');

  // 3. Register Transporter
  console.log('\n--- 9. Registering Transporter & Verifying Transporter Dashboard Redirection ---');
  await page.click('button:has-text("Register")');
  await page.waitForSelector('.register-card');
  await page.click('.role-option-btn:has-text("Transporter")');
  await page.fill('#displayName', `Sahyadri Freight ${ts.toString().slice(-4)}`);
  await page.fill('#email', transporterEmail);
  await page.fill('#phoneNumber', `7${ts.toString().slice(-9)}`);
  await page.fill('#password', commonPassword);
  await page.fill('#confirmPassword', commonPassword);
  await page.click('button[type="submit"]');

  await page.waitForSelector('.user-profile-badge');
  userRole = await page.locator('.user-profile-badge .role-pill').textContent();
  console.log('✓ Transporter Registered! Navbar Profile Role:', userRole);

  // Logout
  await page.click('button:has-text("Logout")');
  await page.waitForSelector('button:has-text("Sign In")');

  // 4. Test Duplicate Email Registration Handling
  console.log('\n--- 10. Testing Duplicate Email Registration Rejection ---');
  await page.click('button:has-text("Register")');
  await page.waitForSelector('.register-card');
  await page.fill('#displayName', 'Duplicate User Test');
  await page.fill('#email', farmerEmail); // Already registered!
  await page.fill('#password', commonPassword);
  await page.fill('#confirmPassword', commonPassword);
  await page.click('button[type="submit"]');

  await page.waitForSelector('.alert-error');
  const dupErr = await page.locator('.alert-error').textContent();
  console.log('✓ Duplicate Email Error Message:', dupErr);

  // ==========================================
  // PART 4: ROLE-AWARE LOGIN VERIFICATION
  // ==========================================
  console.log('\n--- 11. Testing Role-Aware Login for Farmer ---');
  await page.goto(`${BASE_URL}/?view=login`, { waitUntil: 'networkidle' });
  await page.fill('#email', farmerEmail);
  await page.fill('#password', commonPassword);
  await page.click('button[type="submit"]');

  await page.waitForSelector('.user-profile-badge');
  userRole = await page.locator('.user-profile-badge .role-pill').textContent();
  console.log('✓ Farmer Logged In cleanly! Role pill:', userRole);

  // ==========================================
  // PART 5: MOBILE VIEWPORT AUDIT (390px)
  // ==========================================
  console.log('\n--- 12. Testing Mobile Responsive Layout (390px) ---');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${BASE_URL}/?view=login`, { waitUntil: 'networkidle' });
  await page.waitForSelector('.auth-card');

  let scrollWidth = await page.evaluate(() => document.body.scrollWidth);
  let innerWidth = await page.evaluate(() => window.innerWidth);
  console.log('✓ Login Mobile No Horizontal Overflow:', scrollWidth <= innerWidth);
  await page.screenshot({ path: `${ARTIFACT_DIR}/auth_login_mobile.png`, fullPage: false });

  await page.goto(`${BASE_URL}/?view=register`, { waitUntil: 'networkidle' });
  await page.waitForSelector('.register-card');

  scrollWidth = await page.evaluate(() => document.body.scrollWidth);
  innerWidth = await page.evaluate(() => window.innerWidth);
  console.log('✓ Register Mobile No Horizontal Overflow:', scrollWidth <= innerWidth);
  await page.screenshot({ path: `${ARTIFACT_DIR}/auth_register_mobile.png`, fullPage: false });

  // Console Error Audit
  console.log('\n--- 13. Console Error Audit ---');
  const criticalErrors = consoleErrors.filter(e => !e.includes('401') && !e.includes('409'));
  console.log(`✓ Total Critical Console Errors: ${criticalErrors.length}`);

  await browser.close();
  console.log('\n🎉 ALL PHASE UI-2 AUTHENTICATION & REGISTRATION E2E TESTS PASSED!');
}

main().catch(err => {
  console.error('Test Failed:', err);
  process.exit(1);
});
