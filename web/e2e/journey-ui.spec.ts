/** Real HTTP in the runner's isolated DB. All written text is explicitly a software fixture. */
import { test, expect } from '@playwright/test'
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
const token =
  process.env.VOYAURA_E2E_TOKEN ??
  readFileSync(
    new URL('../../.local/access-token.txt', import.meta.url),
    'utf8',
  ).trim()
const apiUrl = process.env.VOYAURA_E2E_API_URL ?? 'http://127.0.0.1:8018/api/v1'
const headers = { Authorization: `Bearer ${token}` }
const folder = new URL(
  '../../.local/e2e-evidence/journey-screenshots/',
  import.meta.url,
)
mkdirSync(folder, { recursive: true })

test('第三轮：手动抵达预览与确认→真实文字记忆→带入日期整理故事→返回书架与创作', async ({
  page,
  request,
}, info) => {
  test.setTimeout(90000)
  page.setDefaultTimeout(15000)
  const errors: string[] = [],
    external: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('request', (r) => {
    const url = new URL(r.url())
    if (
      url.protocol.startsWith('http') &&
      !['localhost', '127.0.0.1'].includes(url.hostname)
    )
      external.push(url.origin)
  })
  const overview = async () =>
    (await request.get(`${apiUrl}/map/overview`, { headers })).json()
  const before = await overview()
  await page.goto('/')
  await page.getByRole('button', { name: '我的私人档案', exact: true }).click()
  await page.getByLabel('访问令牌', { exact: true }).fill(token)
  await page.getByRole('button', { name: '连接 Voyaura', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await page.getByRole('button', { name: '旅程', exact: true }).click()
  await expect(page.getByRole('main', { name: '我的旅行足迹' })).toBeVisible()
  await expect(page.locator('.offline-atlas-label')).toContainText('非导航底图')
  await page
    .locator('.journey-hero')
    .getByRole('button', { name: '记录一次抵达', exact: true })
    .click()
  await expect(page.locator('.manual-city-intro')).toContainText(
    '不验证你当前的位置',
  )
  await expect(page.locator('.manual-city-results > button')).toHaveCount(6)
  expect((await overview()).stats).toEqual(before.stats)
  await page
    .locator('.manual-city-results > button')
    .filter({ hasText: '厦门市' })
    .click()
  await expect(page.locator('.check-in-preview')).toContainText('手动选城')
  expect((await overview()).stats).toEqual(before.stats)
  await page.screenshot({
    path: fileURLToPath(
      new URL(`arrival-preview-${info.project.name}.png`, folder),
    ),
  })
  await page.getByRole('button', { name: '确认点亮', exact: true }).click()
  await expect(page.locator('.dialog-result')).toContainText(
    '厦门市 已加入旅行图鉴',
  )
  expect(
    (await overview()).visited_cities.find(
      (c: { adcode: string }) => c.adcode === '350200',
    ).check_in_source,
  ).toBe('manual')
  await page.getByRole('button', { name: '查看城市档案', exact: true }).click()
  const archive = page.getByRole('dialog', { name: '我与厦门市' })
  await expect(archive).toBeVisible()
  await expect(archive.locator('.city-source-label')).toContainText(
    '手动到访记录',
  )
  const memoryCount = (
    await (
      await request.get(`${apiUrl}/cities/350200/memories`, { headers })
    ).json()
  ).memories.length
  await archive.getByRole('button', { name: '写一段记忆', exact: true }).click()
  const editor = page.getByRole('dialog', { name: '写给厦门市的记忆' })
  await expect(editor.getByLabel('标题', { exact: true })).toBeFocused()
  const title = `[本地验收·非真实旅行] 第三轮${info.project.name}`
  await editor.getByLabel('标题', { exact: true }).fill(title)
  await editor.getByLabel('发生日期', { exact: true }).fill('2026-06-08')
  await editor
    .getByLabel('正文', { exact: true })
    .fill(
      '这是一条软件验收时手动录入的文字，不是真实旅行记录。验证城市档案、来源与故事确认流程。',
    )
  await editor.getByRole('button', { name: '预览记忆', exact: true }).click()
  await expect(editor.locator('.memory-confirmation')).toContainText(title)
  expect(
    (
      await (
        await request.get(`${apiUrl}/cities/350200/memories`, { headers })
      ).json()
    ).memories.length,
  ).toBe(memoryCount)
  await editor.getByRole('button', { name: '确认保存', exact: true }).click()
  await expect(editor).toContainText('记忆已经收进城市档案')
  await editor
    .getByRole('button', { name: '回到城市档案', exact: true })
    .click()
  await expect(page.locator('.memory-composer-backdrop')).toHaveCount(0)
  await expect(archive).toContainText(title)

  // Opening the action menu is read-only; deletion still requires its own preview.
  const more = archive.locator('.memory-actions-more').first()
  await more.locator('summary').click()
  await expect(page.locator('.memory-delete-backdrop')).toHaveCount(0)
  await more.getByRole('button', { name:'删除记忆', exact:true }).click()
  const deletePreview = page.getByRole('alertdialog', { name:'删除城市记忆', exact:true })
  await expect(deletePreview).toBeVisible()
  await expect(page.locator('.memory-delete-backdrop')).toHaveCSS('opacity','1')
  const destructive = deletePreview.getByRole('button', { name:'确认删除', exact:true })
  const destructiveStyle = await destructive.evaluate(el => {
    const surface = document.createElement('span')
    surface.style.backgroundColor = 'var(--surface)'
    el.append(surface)
    const result = { color:getComputedStyle(el).color, background:getComputedStyle(el).backgroundColor, surface:getComputedStyle(surface).backgroundColor, height:el.getBoundingClientRect().height }
    surface.remove()
    return result
  })
  expect(destructiveStyle.color).toBe('rgb(180, 35, 47)')
  expect(destructiveStyle.background).toBe(destructiveStyle.surface)
  expect(destructiveStyle.height).toBeGreaterThanOrEqual(44)
  await page.screenshot({ animations:'disabled', path:fileURLToPath(new URL('delete-preview-' + info.project.name + '.png',folder)) })
  await deletePreview.getByRole('button', { name:'保留记忆', exact:true }).click()
  await expect(deletePreview).toHaveCount(0)
  expect((await (await request.get(apiUrl + '/cities/350200/memories', {headers})).json()).memories.length).toBe(memoryCount + 1)
  const archiveTabs = archive.getByRole('tab')
  await archiveTabs.first().focus()
  await page.keyboard.press('ArrowRight')
  await expect(archiveTabs.nth(1)).toBeFocused()
  await expect(archiveTabs.nth(1)).toHaveAttribute('aria-selected','true')
  await page.keyboard.press('Home')
  await expect(archiveTabs.first()).toBeFocused()
  await page.screenshot({
    path: fileURLToPath(new URL(`archive-${info.project.name}.png`, folder)),
  })
  await archive
    .getByRole('button', { name: '整理这座城的故事', exact: true })
    .click()
  await expect(page).toHaveURL(/compose=story.*city=350200.*date=2026-06-08/)
  await expect(page.locator('.city-archive-layer')).toHaveCount(0)
  await expect(page.getByRole('button', { name: '返回城市记忆', exact: true })).toBeVisible()
  await expect(page.getByLabel('回忆开始日期', { exact: true })).toHaveValue(
    '2026-06-08',
  )
  const consent = page.locator('.story-consent input')
  await expect(consent).not.toBeChecked()
  await page
    .getByLabel('想留下一段怎样的回忆？', { exact: true })
    .fill('[本地验收·非真实旅行] 仅整理本次测试文字')
  await page.screenshot({
    path: fileURLToPath(
      new URL(`story-input-${info.project.name}.png`, folder),
    ),
  })
  await consent.check()
  await page
    .getByRole('button', { name: '整理我的旅行故事', exact: true })
    .click()
  await expect(page.locator('.story-paper textarea')).toHaveValue(
    /不是真实旅行记录/,
  )
  await page.locator('.source-records summary').click()
  await expect(page.locator('.source-records')).toContainText(title)
  await page
    .getByRole('button', { name: '核对并保存当前草案', exact: true })
    .click()
  await expect(page.locator('.confirmation-card')).toBeVisible()
  const acknowledgement = page.locator(
    '.confirmation-card input[type=checkbox]',
  )
  if (await acknowledgement.count()) await acknowledgement.check()
  await page
    .getByRole('button', { name: '确认保存到私人档案', exact: true })
    .click()
  await expect(page.locator('.saved-card')).toContainText('已妥善收藏')
  await page.locator('.story-paper').scrollIntoViewIfNeeded()
  await page.screenshot({
    path: fileURLToPath(
      new URL(`story-result-${info.project.name}.png`, folder),
    ),
  })
  await page.getByRole('button', { name: '返回城市记忆', exact: true }).click()
  await expect(page).toHaveURL(/\/journey\/stories$/)
  await expect(page.getByRole('main', { name: '旅行记忆书架' })).toBeVisible()
  const card = page.getByRole('button', {
    name: '打开厦门市的城市记忆',
    exact: true,
  })
  await card.click()
  await expect(page.getByRole('button', { name: '整理这座城的故事', exact: true })).toBeVisible()
  await expect(
    page.getByRole('button', { name: '关闭城市记忆', exact: true }),
  ).toBeFocused()
  await page.keyboard.press('Shift+Tab')
  await expect(
    page.getByRole('button', { name: '整理这座城的故事', exact: true }),
  ).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(
    page.getByRole('button', { name: '关闭城市记忆', exact: true }),
  ).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(page.locator('.city-archive-layer')).toHaveCount(0)
  await expect(card).toBeFocused()

  // Review populated pages at all supported widths; GET only during this part.
  const checks = []
  const widths = info.project.name === 'desktop' ? [1440, 768, 320] : [390]
  for (const width of widths) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 })
    for (const [view, path] of [
      ['atlas', '/journey/map'],
      ['library', '/journey/stories'],
      ['studio', '/studio'],
    ] as const) {
      await page.goto(path)
      await expect(
        page.locator(
          view === 'studio' ? '.studio-filter-bar' : '.journey-section-tabs',
        ),
      ).toBeVisible()
      if (view === 'studio')
        await expect(page.locator('.studio-availability')).toContainText(
          '暂未连接',
        )
      const sizes = await page.evaluate(() => ({
        viewport: innerWidth,
        documentWidth: document.documentElement.scrollWidth,
        scroll: [
          ...document.querySelectorAll('.journey-scroll,.studio-scroll'),
        ].map((el) => ({ width: el.clientWidth, scrollWidth: el.scrollWidth })),
      }))
      expect(sizes.documentWidth).toBeLessThanOrEqual(width)
      for (const item of sizes.scroll)
        expect(item.scrollWidth).toBeLessThanOrEqual(item.width)
      await page.screenshot({
        path: fileURLToPath(new URL(`${view}-${width}.png`, folder)),
      })
      checks.push({ view, width, sizes })
    }
  }
  await page
    .getByRole('button', { name: '从旅行记忆选照片', exact: true })
    .click()
  await expect(page.getByRole('main', { name: '旅行记忆书架' })).toBeVisible()
  expect(errors).toEqual([])
  expect(external).toEqual([])
  writeFileSync(
    new URL(`checks-${info.project.name}.json`, folder),
    JSON.stringify({ checks, errors, external }, null, 2),
  )
})
