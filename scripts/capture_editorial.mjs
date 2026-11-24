import { chromium } from '../web/node_modules/playwright/index.mjs'
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import assert from 'node:assert/strict'

// Use only a dedicated empty profile or the isolated E2E database.
// Never pass an access token through the URL or commit it to this repository.
const phase = process.env.VOYAURA_CAPTURE_PHASE ?? 'after'
if (!['before','after'].includes(phase)) throw new Error('Invalid VOYAURA_CAPTURE_PHASE')
const url = process.env.VOYAURA_CAPTURE_URL
const tokenFile = process.env.VOYAURA_CAPTURE_TOKEN_FILE
if (!url || !tokenFile) throw new Error('Set VOYAURA_CAPTURE_URL and VOYAURA_CAPTURE_TOKEN_FILE for a dedicated empty profile')
const target = new URL(url)
if (!['localhost','127.0.0.1'].includes(target.hostname)) throw new Error('Capture is restricted to localhost')
const config = { root: fileURLToPath(new URL('..', import.meta.url)), [phase + '_url']: url }
const token = readFileSync(tokenFile, 'utf8').trim()
const folder = join(process.env.VOYAURA_CAPTURE_DIR || join(config.root, '.local', 'screenshots'), phase)
mkdirSync(folder, { recursive: true })
const views = [['discover', '/'], ['plan', '/plan'], ['atlas', '/journey/map'], ['memories', '/journey/stories'], ['story', '/journey/stories?compose=story&city=440100'], ['studio', '/studio'], ['account', '/account']]
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const errors = [], writes = [], checks = [], externalRequests = []
try {
  for (const [kind, width, height] of [['desktop', 1440, 1000], ['mobile', 390, 844]]) {
    const context = await browser.newContext({ viewport: { width, height }, reducedMotion: 'reduce', serviceWorkers: 'block' })
    await context.addInitScript(value => sessionStorage.setItem('voyaura.access-token', value), token)
    const page = await context.newPage()
    await page.route('**/api/**', route => ['GET', 'HEAD', 'OPTIONS'].includes(route.request().method()) ? route.continue() : route.abort())
    page.on('pageerror', error => errors.push({ kind, message: error.message }))
    page.on('request', request => {
      const url = new URL(request.url())
      if (url.pathname.startsWith('/api/') && !['GET', 'HEAD', 'OPTIONS'].includes(request.method())) writes.push(request.method())
      if (['http:', 'https:'].includes(url.protocol) && !['localhost', '127.0.0.1'].includes(url.hostname)) externalRequests.push(url.origin)
    })
    for (const [view, path] of views) {
      await page.goto(config[phase + '_url'] + path)
      await page.waitForLoadState('networkidle')
      assert.ok(!/演练|虚拟地点|验收夹具/.test(await page.locator('body').innerText()))
      await page.screenshot({ path: join(folder, `${view}-${kind}.png`), mask: [page.locator('.account-identity h2')], maskColor: '#d9dfd3' })
      const layout = await page.evaluate(() => ({ width: innerWidth, documentWidth: document.documentElement.scrollWidth, scroll: [...document.querySelectorAll('.discover-page,.workspace-scroll,.journey-scroll,.studio-scroll,.account-scroll')].map(el => ({ width: el.clientWidth, scrollWidth: el.scrollWidth })) }))
      assert.ok(layout.documentWidth <= width)
      assert.ok(layout.scroll.every(s => s.scrollWidth <= s.width + 1))
      // Expand only the viewport height to include the entire existing scroll area.
      // This makes long forms reviewable without changing the application DOM or data.
      const fullHeight = await page.evaluate(() => Math.ceil(Math.max(...[...document.querySelectorAll('.discover-page,.workspace-scroll,.journey-scroll,.studio-scroll,.account-scroll')].map(el => el.scrollHeight), innerHeight) + 72 + (innerWidth < 900 ? 68 : 0)))
      await page.setViewportSize({ width, height: Math.min(fullHeight, 8000) })
      await page.waitForLoadState('networkidle')
      await page.evaluate(() => document.fonts.ready)
      await page.screenshot({ path: join(folder, `${view}-${kind}-full.png`), mask: [page.locator('.account-identity h2')], maskColor: '#d9dfd3' })
      await page.setViewportSize({ width, height })
      checks.push({ view, kind, fullHeight, ...layout })
    }
    await context.close()
  }
} finally { await browser.close() }
assert.deepEqual(errors, [])
assert.deepEqual(writes, [])
assert.deepEqual(externalRequests, [])
writeFileSync(join(folder, 'checks.json'), JSON.stringify({ phase, checks, errors, writes, externalRequests }, null, 2), 'utf8')
console.log(JSON.stringify({ phase, pages: checks.length, errors: 0, writes: 0, externalRequests: 0 }))
