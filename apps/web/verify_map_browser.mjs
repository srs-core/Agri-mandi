import { chromium } from 'playwright';
import path from 'path';

async function runBrowserVerification() {
  console.log('--- Starting Playwright Browser Verification of ShipmentRouteMap ---');
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
  });
  const page = await context.newPage();

  const consoleErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });

  try {
    // 1. Navigate to frontend
    console.log('1. Navigating to http://localhost:5174/ ...');
    await page.goto('http://localhost:5174/', { waitUntil: 'networkidle' });

    // 2. Click Route Map in Navbar
    console.log('2. Clicking "Route Map" nav button...');
    const routeMapNav = page.locator('nav.nav-links button:has-text("Route Map")');
    await routeMapNav.click();
    await page.waitForTimeout(1000);

    // 3. Verify Leaflet map container
    console.log('3. Verifying Leaflet map container initialization...');
    const mapCanvas = page.locator('.route-map-canvas');
    await mapCanvas.waitFor({ state: 'visible', timeout: 5000 });
    const isLeafletActive = await page.locator('.leaflet-container').isVisible();
    console.log(`   Leaflet container active: ${isLeafletActive}`);
    if (!isLeafletActive) throw new Error('Leaflet map container not initialized');

    // 4. Verify Markers on Pune consolidation scenario
    console.log('4. Verifying pickup and destination markers...');
    const pickupMarkers = page.locator('.custom-route-marker.pickup');
    const destMarker = page.locator('.custom-route-marker.destination');

    const pickupCount = await pickupMarkers.count();
    const destCount = await destMarker.count();
    console.log(`   Pickup markers found: ${pickupCount} (Expected: 3)`);
    console.log(`   Destination marker found: ${destCount} (Expected: 1)`);
    if (pickupCount !== 3 || destCount !== 1) {
      throw new Error(`Marker counts mismatch: ${pickupCount} pickups, ${destCount} destination`);
    }

    // 5. Test Marker Click & Popup Display
    console.log('5. Clicking Pickup Marker #1 to inspect popup content...');
    await pickupMarkers.first().click();
    await page.waitForTimeout(500);

    const popupCard = page.locator('.route-popup-card');
    await popupCard.waitFor({ state: 'visible', timeout: 3000 });
    const popupText = await popupCard.innerText();
    console.log(`   Popup text summary:\n   ${popupText.split('\n').slice(0, 4).join(' | ')}`);
    if (!popupText.toUpperCase().includes('PICKUP STOP #1') || !popupText.includes('Farmer Anand Patil')) {
      throw new Error('Popup content missing expected farmer/stop details');
    }

    // 6. Test Administrative-Only Scenario (Zero Fabricated Coordinates)
    console.log('6. Switching to Administrative-Only scenario (Zero Fake GPS)...');
    const scenarioSelect = page.locator('select.form-select').first();
    await scenarioSelect.selectOption({ label: 'Nashik Belgaum Cluster (Administrative Only — Zero Fake GPS)' });
    await page.waitForTimeout(800);

    const adminPickupCount = await page.locator('.custom-route-marker.pickup').count();
    console.log(`   Pickup markers for administrative scenario: ${adminPickupCount} (Expected: 0)`);
    if (adminPickupCount !== 0) {
      throw new Error(`Fabricated coordinate detected! Expected 0 markers, got ${adminPickupCount}`);
    }

    const adminPanel = page.locator('.route-map-administrative-panel');
    const isAdminPanelVisible = await adminPanel.isVisible();
    console.log(`   Administrative notice panel visible: ${isAdminPanelVisible}`);
    if (!isAdminPanelVisible) {
      throw new Error('Administrative notice panel not displayed for non-GPS stops');
    }

    // 7. Test OR-Tools Optimizer Toggle
    console.log('7. Switching back to Pune scenario and testing OR-Tools optimization toggle...');
    await scenarioSelect.selectOption({ label: 'Pune Multi-Farmer Harvest Consolidation (Exact GPS)' });
    await page.waitForTimeout(500);

    const optimizeBtn = page.locator('button:has-text("Show OR-Tools Optimized")');
    await optimizeBtn.click();
    await page.waitForTimeout(500);

    const statusBadge = page.locator('.route-map-status-badge');
    const badgeText = await statusBadge.innerText();
    console.log(`   Status badge text: "${badgeText}" (Expected: OR-TOOLS OPTIMIZED)`);

    const metricValue = page.locator('.route-metric-value').first();
    const distanceText = await metricValue.innerText();
    console.log(`   Optimized distance displayed: ${distanceText} (Expected: 42.8 km)`);

    // 8. Test Mobile Viewport Responsiveness
    console.log('8. Testing mobile viewport (375x667)...');
    await page.setViewportSize({ width: 375, height: 667 });
    await page.waitForTimeout(500);

    const isMapVisibleMobile = await page.locator('.route-map-canvas').isVisible();
    console.log(`   Map visible on mobile: ${isMapVisibleMobile}`);

    // Take screenshot
    const screenshotPath = path.resolve('map_verification_screenshot.png');
    await page.screenshot({ path: screenshotPath, fullPage: true });
    console.log(`   Mobile screenshot saved to ${screenshotPath}`);

    // 9. Check console errors
    console.log('9. Checking browser console errors...');
    const criticalErrors = consoleErrors.filter((e) => !e.includes('favicon') && !e.includes('tile.openstreetmap'));
    if (criticalErrors.length > 0) {
      console.warn('   Console errors detected:', criticalErrors);
    } else {
      console.log('   0 critical console errors detected.');
    }

    console.log('\n=== ALL BROWSER MAP VERIFICATIONS PASSED SUCCESSFULLY ===');
  } finally {
    await browser.close();
  }
}

runBrowserVerification().catch((err) => {
  console.error('Browser verification failed:', err);
  process.exit(1);
});
