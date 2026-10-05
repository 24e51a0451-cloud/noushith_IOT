import { chromium } from 'playwright';

const browser = await chromium.launch({
  headless: true,
  executablePath: 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  args: ['--disable-gpu', '--disable-software-rasterizer', '--disable-dev-shm-usage'],
});
const page = await browser.newPage({ viewport: { width: 1600, height: 1100 }, deviceScaleFactor: 1 });
await page.goto('http://127.0.0.1:5055/dashboard', { waitUntil: 'networkidle' });
await page.screenshot({ path: 'D:\\GALATICX\\masterhub_iot_noushith\\artifacts\\ppt_build\\dashboard-current.png', fullPage: true });
await page.locator('#hudBciSetupBtn').click();
await page.waitForTimeout(700);
await page.screenshot({ path: 'D:\\GALATICX\\masterhub_iot_noushith\\artifacts\\ppt_build\\dashboard-bci-current.png', fullPage: false });
await browser.close();
