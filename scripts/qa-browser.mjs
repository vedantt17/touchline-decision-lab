import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import assert from 'node:assert/strict';

const url = process.env.BASE_URL || 'http://127.0.0.1:8788/';
const out = 'output/playwright';
await mkdir(out, { recursive: true });
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
const page = await context.newPage();
const errors = [];
page.on('pageerror', error => errors.push(error.message));
page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
page.setDefaultTimeout(12000);
const result = { url, screens: [], interactions: [] };
async function screen(name) {
  try {
    await page.waitForFunction(() => document.documentElement.scrollWidth <= window.innerWidth + 1, null, { timeout: 2000 });
  } catch (error) {
    console.log(JSON.stringify(await page.evaluate(() => ({width: innerWidth, scrollWidth: document.documentElement.scrollWidth, elements: [...document.querySelectorAll('body *')].map(e => ({tag: e.tagName, class: e.getAttribute('class'), right: e.getBoundingClientRect().right, width: e.getBoundingClientRect().width})).filter(e => e.right > innerWidth + 2).slice(0, 25)})), null, 2));
    await page.screenshot({ path: `${out}/overflow-${name}.png`, fullPage: true });
    throw error;
  }
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1), false, `${name}: page overflows`);
  await page.screenshot({ path: `${out}/${name}.png`, fullPage: true, animations: 'disabled', timeout: 15000 });
  result.screens.push(name);
}
async function view(name) {
  const menu = page.getByRole('button', { name: 'Open navigation', exact: true });
  if (await menu.isVisible()) await menu.click();
  await page.getByRole('button', { name, exact: true }).click();
}
try {
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  await page.getByRole('heading', { name: 'Workspace overview', exact: true }).waitFor();
  await screen('overview-desktop');
  await page.getByRole('combobox', { name: 'Metric', exact: true }).selectOption('npxg90');
  await page.getByRole('combobox', { name: 'Minimum minutes', exact: true }).selectOption('450');
  const save = page.getByRole('button', { name: /^Save .* to watchlist$/ }).first();
  await save.click();
  assert.equal(await page.getByRole('button', { name: /^Remove .* from watchlist$/ }).first().getAttribute('aria-pressed'), 'true');
  await page.getByRole('button', { name: /Saved players/ }).click();
  assert.equal(await page.getByRole('button', { name: /Watchlist/ }).getAttribute('aria-pressed'), 'true');
  await view('Overview');
  const [report] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: 'Export report', exact: true }).click()]);
  await report.saveAs(`${out}/overview.csv`);
  await page.getByRole('button', { name: 'Inspect match', exact: true }).click();
  assert.equal(await page.getByRole('combobox', { name: 'Historical match', exact: true }).inputValue(), '3869685');
  await view('Overview');
  await page.getByRole('textbox', { name: 'Find a player across the workspace' }).fill('Amrabat');
  await page.getByRole('button', { name: /Sofyan Amrabat/ }).click();
  assert.equal(await page.getByRole('combobox', { name: 'Reference player', exact: true }).inputValue(), '5234');
  result.interactions.push('overview metrics, exposure filter, overview CSV, spotlight match deep link, global player search');
  await page.getByRole('heading', { name: 'Player recruitment', exact: true }).waitFor();
  await page.getByRole('combobox', { name: 'Reference player', exact: true }).selectOption('5234');
  await page.getByRole('combobox', { name: 'Comparison model', exact: true }).selectOption('spatial');
  assert.equal(await page.getByLabel('Progression weight', { exact: true }).isDisabled(), true);
  await page.getByRole('combobox', { name: 'Comparison model', exact: true }).selectOption('metric');
  await page.getByLabel('Progression weight', { exact: true }).fill('2');
  await page.getByPlaceholder('Search player or team').fill('Modri');
  assert.ok(await page.locator('main div:not([hidden]) table').first().innerText());
  await page.getByPlaceholder('Search player or team').fill('');
  const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: 'Export CSV', exact: true }).click()]);
  await download.saveAs(`${out}/shortlist.csv`);
  result.interactions.push('reference, spatial mode, inactive weights, metric reweighting, player search, CSV download');
  await screen('recruitment-desktop');
  await view('Match lab');
  await page.getByRole('combobox', { name: 'Historical match', exact: true }).selectOption({ label: 'Argentina 3-3 France · 2022-12-18' });
  await page.getByRole('combobox', { name: 'Team', exact: true }).selectOption('France');
  await page.getByRole('combobox', { name: 'Lane type', exact: true }).selectOption('pass');
  await screen('match-desktop');
  result.interactions.push('different match, away-team filter, lane-type filter');
  await view('Tracking');
  const timeline = page.getByRole('slider', { name: /Tracking timeline/ });
  assert.equal(await timeline.inputValue(), '0');
  await page.getByRole('button', { name: 'Next tracking frame', exact: true }).click();
  assert.equal(await timeline.inputValue(), '1');
  await page.getByRole('button', { name: 'Play tracking playback', exact: true }).click();
  await page.waitForTimeout(1200);
  assert.ok(Number(await timeline.inputValue()) > 1);
  await page.getByRole('button', { name: 'Pause tracking playback', exact: true }).click();
  await page.getByRole('checkbox', { name: 'Velocity', exact: true }).check();
  await screen('tracking-desktop');
  result.interactions.push('tracking frame step, timed playback, pause, velocity overlay');
  await view('Evidence');
  await page.getByRole('button', { name: 'Support', exact: true }).click();
  await screen('evidence-desktop');
  for (const width of [320, 390, 768]) {
    await page.setViewportSize({ width, height: 844 });
    for (const label of ['Overview', 'Recruitment', 'Match lab', 'Tracking', 'Evidence']) {
      await view(label);
      await screen(`${label.toLowerCase().replaceAll(' ', '-')}-${width}`);
    }
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await view('Recruitment');
  await page.getByPlaceholder('Search player or team').fill('not-a-real-player-92714');
  await page.getByRole('heading', { name: 'No profiles meet these filters', exact: true }).waitFor();
  result.interactions.push('mobile views, empty search result, evidence support grid');
  assert.deepEqual(errors, [], 'Browser errors');
  const failed = await context.newPage();
  await failed.route('**/data/workspace.json', route => route.abort());
  await failed.goto(url, { waitUntil: 'domcontentloaded' });
  await failed.getByRole('heading', { name: 'Workspace not available', exact: true }).waitFor();
  await failed.unroute('**/data/workspace.json');
  await failed.getByRole('button', { name: 'Retry workspace', exact: true }).click();
  await failed.getByRole('heading', { name: 'Workspace overview', exact: true }).waitFor();
  await failed.close();
  result.interactions.push('missing dataset shows explicit error; retry loads real artifact without fabricated fallback');
  result.errors = errors;
  result.passed = true;
  await writeFile(`${out}/checks.json`, JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
} finally {
  await browser.close();
}
