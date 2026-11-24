/**
 * Read-only design regression on the runner's isolated database.
 * Measures rendered pages; no route mocks or generated personal history.
 * Contrast samples have solid backgrounds; this is not a full WCAG certification.
 */
import { test, expect, type Page } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
const token = process.env.VOYAURA_E2E_TOKEN!
const folder = new URL('../../.local/e2e-evidence/design-checks/', import.meta.url)
mkdirSync(folder, { recursive: true })
const pages = [
  ['discover', '/', '.hero-description', '.search-go'],
  ['plan', '/plan', '.field > span', '.brief-submit .primary-action'],
  ['story', '/journey/stories?compose=story&city=440100', '.goal-field > span', '.brief-submit .primary-action'],
  ['atlas', '/journey/map', '.journey-hero p', '.journey-hero > button'],
  ['memories', '/journey/stories', '.journey-hero p', '.journey-hero > button'],
  ['studio', '/studio', '.studio-header p', '.studio-pick-source'],
  ['account', '/account', '.account-hero p', '.account-refresh'],
] as const
async function connect(page: Page) {
  await page.addInitScript(value => sessionStorage.setItem('voyaura.access-token', value), token)
}
async function layout(page: Page) {
  return page.evaluate(() => {
    const visible = (el: Element) => el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true }) && el.getBoundingClientRect().width > 0
    const text = [...document.querySelectorAll('body *')].filter(el => !(el instanceof SVGElement) && visible(el) && [...el.childNodes].some(n => n.nodeType === Node.TEXT_NODE && n.textContent?.trim()))
    const smallText = text.filter(el => {
      const size = parseFloat(getComputedStyle(el).fontSize)
      return size > 0 && size < 12
    }).map(el => ({ tag: el.tagName, class: el.className, size: getComputedStyle(el).fontSize }))
    const smallControls = [...document.querySelectorAll('button:not(:disabled), summary, input:not([type=checkbox]):not([type=radio])')]
      .filter(visible).map(el => ({ label: el.getAttribute('aria-label') || el.textContent?.trim().slice(0, 30), width: el.getBoundingClientRect().width, height: el.getBoundingClientRect().height }))
      .filter(el => el.width < 43.9 || el.height < 43.9)
    const smallInputs = [...document.querySelectorAll('input:not([type=checkbox]):not([type=radio]),textarea,select')].filter(visible).filter(el => parseFloat(getComputedStyle(el).fontSize) < 16).map(el => el.getAttribute('aria-label'))
    const scroll = [...document.querySelectorAll('.discover-page,.workspace-scroll,.journey-scroll,.studio-scroll,.account-scroll')]
      .map(el => ({ width: el.clientWidth, scrollWidth: el.scrollWidth }))
    const header = document.querySelector('.product-header__inner')!
    return { smallText, smallControls, smallInputs, scroll, documentWidth: document.documentElement.scrollWidth, header: { width: header.clientWidth, scrollWidth: header.scrollWidth } }
  })
}
async function contrast(page: Page, selector: string) {
  return page.locator(selector).first().evaluate(el => {
    const rgb = (s: string) => s.match(/[\d.]+/g)!.map(Number)
    const lum = (s: string) => {
      const c = rgb(s).slice(0, 3).map(v => { const n = v! / 255; return n <= .04045 ? n / 12.92 : ((n + .055) / 1.055) ** 2.4 })
      return c[0]! * .2126 + c[1]! * .7152 + c[2]! * .0722
    }
    let bg: Element | null = el
    while (bg && rgb(getComputedStyle(bg).backgroundColor)[3] === 0) bg = bg.parentElement
    const fg = getComputedStyle(el).color
    const background = bg ? getComputedStyle(bg).backgroundColor : 'rgb(250,249,246)'
    const a = lum(fg), b = lum(background)
    return { fg, background, ratio: (Math.max(a, b) + .05) / (Math.min(a, b) + .05) }
  })
}
test('设计治理：真实七页五种屏宽、字号、触控、对比和任务入口，检查阶段仅GET', async ({ page }, info) => {
  test.setTimeout(150000)
  await connect(page)
  const errors: string[] = [], writes: string[] = [], checks: object[] = []
  page.on('pageerror', e => errors.push(e.message))
  page.on('request', r => { if (new URL(r.url()).pathname.startsWith('/api/') && !['GET','HEAD','OPTIONS'].includes(r.method())) writes.push(r.method()) })
  for (const width of info.project.name === 'desktop' ? [1440,1280,768,390,320] : [390]) {
    await page.setViewportSize({ width, height: width < 768 ? 844 : 1000 })
    for (const [name,path,body,action] of pages) {
      await page.goto(path)
      await page.waitForLoadState('networkidle')
      const measured = await layout(page)
      expect(measured.smallText, name + width + ' text').toEqual([])
      expect(measured.smallControls, name + width + ' controls').toEqual([])
      expect(measured.smallInputs, name + width + ' fields').toEqual([])
      expect(measured.documentWidth).toBeLessThanOrEqual(width)
      expect(measured.header.scrollWidth).toBeLessThanOrEqual(measured.header.width)
      for (const scroll of measured.scroll) expect(scroll.scrollWidth).toBeLessThanOrEqual(scroll.width)
      const samples = []
      for (const selector of name === 'discover' ? ['.discover-section-heading h2','.discover-section-heading p',action] : ['h1',body,action]) {
        const sample = await contrast(page, selector)
        expect(sample.ratio, name + selector).toBeGreaterThanOrEqual(4.5)
        samples.push({ selector, ...sample })
      }
      const titleSize = await page.locator('h1').evaluate(el => parseFloat(getComputedStyle(el).fontSize))
      expect(titleSize).toBeGreaterThanOrEqual(28)
      if (name === 'plan') {
        const input = await page.getByLabel('这次想怎样旅行？', { exact:true }).boundingBox()
        expect(input!.y).toBeGreaterThanOrEqual(64)
        expect(input!.y + input!.height).toBeLessThanOrEqual(width < 768 ? 776 : 900)
        await expect(page.getByRole('button', { name:'最近任务', exact:true })).toContainText('最近任务')
        await page.keyboard.press('Tab')
        await page.getByLabel('这次想怎样旅行？', {exact:true}).focus()
        const inputFocus = await page.getByLabel('这次想怎样旅行？', {exact:true}).evaluate(el => ({ width:getComputedStyle(el).outlineWidth, color:getComputedStyle(el).outlineColor }))
        expect(inputFocus.width).toBe('3px')
        expect(inputFocus.color).toBe('rgb(165, 64, 35)')

      }
      if (name === 'story' && width >= 1280) {
        const workspace = await page.locator('.workspace-grid').boundingBox()
        const editor = await page.locator('.brief-column').boundingBox()
        const context = await page.locator('.story-companion').boundingBox()
        // Both sides must remain readable; a legacy planner rule must not squeeze the story context.
        expect(editor!.width).toBeGreaterThanOrEqual(workspace!.width * 0.4)
        expect(context!.width).toBeGreaterThanOrEqual(workspace!.width * 0.4)
        expect(context!.x).toBeGreaterThan(editor!.x + editor!.width)
      }
      if (name === 'studio') {
        await expect(page.locator('.studio-pick-source')).toContainText('从旅行记忆选照片')
        await page.keyboard.press('Tab')
        await page.locator('.studio-pick-source').focus()
        const outline = await page.locator('.studio-pick-source').evaluate(el => ({ width: getComputedStyle(el).outlineWidth, style: getComputedStyle(el).outlineStyle }))
        expect(parseFloat(outline.width)).toBeGreaterThanOrEqual(3)
        expect(outline.style).toBe('solid')
      }
      const text = await page.locator('body').innerText()
      expect(text).not.toMatch(/YOUR PRIVATE|YOUR TRAVEL|VISUAL STUDIO|THE MOMENTS|NO\. 001|BROWSE BY CITY/)
      checks.push({name,width,measured,samples,titleSize})
    }
  }
  expect(errors).toEqual([])
  expect(writes).toEqual([])
  writeFileSync(new URL('rendered-' + info.project.name + '.json',folder), JSON.stringify({ checks, errors, writes },null,2))
})
test('设计治理：200%文字放大仍可浏览、操作且无横向溢出', async ({ page }, info) => {
  test.setTimeout(120000)
  await connect(page)
  const checks = []
  for (const [name,path] of pages) {
    await page.goto(path)
    await page.waitForLoadState('networkidle')
    await page.addStyleTag({ content:':root { font-size:32px }' })
    const measured = await layout(page)
    const width = page.viewportSize()!.width
    expect(measured.documentWidth).toBeLessThanOrEqual(width)
    expect(measured.header.scrollWidth).toBeLessThanOrEqual(measured.header.width)
    for (const scroll of measured.scroll) expect(scroll.scrollWidth, name).toBeLessThanOrEqual(scroll.width)
    const title = await page.locator('h1').evaluate(el => parseFloat(getComputedStyle(el).fontSize))
    expect(title).toBeGreaterThanOrEqual(56)
    if (name === 'plan') {
      const goal = page.getByLabel('这次想怎样旅行？', {exact:true})
      await goal.scrollIntoViewIfNeeded()
      await goal.click()
      await expect(goal).toBeFocused()
      const box = await goal.boundingBox()
      expect(box!.y).toBeGreaterThanOrEqual(64)
      expect(box!.y + box!.height).toBeLessThanOrEqual(page.viewportSize()!.height - (info.project.name === 'mobile' ? 68 : 0))
    }
    if (['discover','plan','studio'].includes(name))
      await page.screenshot({path:fileURLToPath(new URL('text200-' + name + '-' + info.project.name + '.png',folder))})
    checks.push({ name, width, measured, title })
  }
  writeFileSync(new URL('text200-' + info.project.name + '.json',folder), JSON.stringify(checks,null,2))
})
