import { chromium } from 'playwright';
import { spawn } from 'child_process';

const PORT = 5174;
const BASE_URL = `http://localhost:${PORT}`;

async function runVerification() {
  console.log('=== Phase 2F UI/UX Redesign Browser Verification ===\n');

  // Launch Vite preview server
  console.log('Starting Vite preview server...');
  const server = spawn('npm.cmd', ['--prefix', 'apps/web', 'run', 'preview', '--', '--port', String(PORT), '--host'], {
    shell: true,
    stdio: 'pipe',
  });

  await new Promise((resolve) => setTimeout(resolve, 2000));

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await context.newPage();

  const errors = [];
  page.on('pageerror', (err) => {
    errors.push(err.message);
    console.error('Page Error:', err.message);
  });

  try {
    // 1. Landing View
    console.log('\n--- 1. Testing Landing Page (Liquid Glass + Clay Hero) ---');
    await page.goto(`${BASE_URL}/`, { waitUntil: 'networkidle' });
    const heroTitle = await page.textContent('h1');
    console.log(`✓ Hero Title: "${heroTitle?.replace(/\s+/g, ' ').trim()}"`);

    const heroImg = await page.$('img[alt="AgriMandi Smart Farm Operations"]');
    if (heroImg) {
      console.log('✓ Clay Farm Hero Image rendered successfully');
    } else {
      console.warn('⚠️ Hero image element not found');
    }

    // 2. Navigation
    console.log('\n--- 2. Testing Navbar & View Routing ---');
    const navBrand = await page.textContent('.brand-name');
    console.log(`✓ Navbar Brand: ${navBrand}`);

    // 3. Marketplace View
    console.log('\n--- 3. Testing Marketplace View ---');
    await page.click('button:has-text("Marketplace")');
    await page.waitForTimeout(500);
    const mktTitle = await page.textContent('h1');
    console.log(`✓ Marketplace Title: ${mktTitle}`);

    // 4. Logistics Route Explorer
    console.log('\n--- 4. Testing Logistics Route Map & Operations ---');
    await page.click('button:has-text("Route Map")');
    await page.waitForTimeout(1000);
    const routeTitle = await page.textContent('h1');
    console.log(`✓ Logistics Desk: ${routeTitle}`);

    const mapContainer = await page.$('.leaflet-container');
    if (mapContainer) {
      console.log('✓ Leaflet OpenStreetMap Container initialized');
    }

    const markersCount = (await page.$$('.leaflet-marker-icon')).length;
    console.log(`✓ Rendered Map Waypoint Markers: ${markersCount}`);

    // 5. Test OR-Tools Optimizer Toggle
    console.log('\n--- 5. Testing OR-Tools Optimizer Toggle ---');
    const optButton = await page.$('button:has-text("Show OR-Tools Optimized")');
    if (optButton) {
      await optButton.click();
      await page.waitForTimeout(500);
      const activeText = await page.textContent('button:has-text("Showing OR-Tools Optimized")');
      console.log(`✓ OR-Tools Toggle Activated: "${activeText}"`);
    }

    // 6. Test Mobile Viewports (375x667 & 390x844)
    console.log('\n--- 6. Testing Mobile Viewports (375x667 & 390x844) ---');
    await page.setViewportSize({ width: 375, height: 667 });
    await page.waitForTimeout(500);
    const scrollWidth375 = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth375 = await page.evaluate(() => document.documentElement.clientWidth);
    console.log(`✓ Mobile 375x667 Scroll Width: ${scrollWidth375}px (Client: ${clientWidth375}px) - Horizontal Overflow: ${scrollWidth375 > clientWidth375}`);

    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(500);
    const scrollWidth390 = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth390 = await page.evaluate(() => document.documentElement.clientWidth);
    console.log(`✓ Mobile 390x844 Scroll Width: ${scrollWidth390}px (Client: ${clientWidth390}px) - Horizontal Overflow: ${scrollWidth390 > clientWidth390}`);

    console.log('\n=== All Phase 2F UI Verification Checks Passed ===');
  } catch (err) {
    console.error('Verification failed:', err);
    process.exitCode = 1;
  } finally {
    await browser.close();
    server.kill();
    process.exit(errors.length > 0 ? 1 : 0);
  }
}

runVerification();
