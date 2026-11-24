/** Real local HTTP + browser tests. All seeded content is explicitly labelled test input. No API mocks or cloud requests. */
import { test, expect } from '@playwright/test'
import type { Page, APIRequestContext } from '@playwright/test'
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs'
import { randomUUID } from 'node:crypto'
import { fileURLToPath } from 'node:url'

const token =
  process.env.VOYAURA_E2E_TOKEN ??
  readFileSync(new URL('../../.local/access-token.txt', import.meta.url), 'utf8').trim()
const apiUrl = process.env.VOYAURA_E2E_API_URL ?? 'http://127.0.0.1:8018/api/v1'
const headers = { Authorization: `Bearer ${token}` }
async function login(page: Page) {
  await page.goto('/')
  await page.getByRole('button', { name: '我的私人档案', exact: true }).click()
  await page.getByLabel('访问令牌', { exact: true }).fill(token)
  await page.getByRole('button', { name: '连接 Voyaura', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
}
async function post(request: APIRequestContext, path: string, data: object) {
  const response = await request.post(`${apiUrl}${path}`, { headers, data })
  expect(response.ok(), `${path}: ${response.status()} ${await response.text()}`).toBeTruthy()
  return response.json()
}
function screenshots() {
  const path = new URL('../../docs/design/governance/flow-screenshots/', import.meta.url)
  mkdirSync(path, { recursive: true })
  return path
}

test('行程：用户输入→真实规划→修改→主动确认→刷新恢复，且不虚构城市足迹', async ({
  page,
  request,
}, testInfo) => {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  const before = await (await request.get(`${apiUrl}/map/overview`, { headers })).json()
  await login(page)
  await page.getByRole('button', { name: '计划', exact: true }).click()
  await page
    .getByLabel('这次想怎样旅行？', { exact: true })
    .fill('[本地验收输入，非真实旅行] 两天轻松逛博物馆与公园')
  await page.getByLabel('出发日期', { exact: true }).fill('2026-12-01')
  await page.locator('.candidate-input > summary').click()
  await page.locator('.manual-coordinate-entry > summary').click()
  const candidates = [
    ['[验收输入] 博物馆A', '113.32', '23.11'],
    ['[验收输入] 公园B', '113.30', '23.12'],
    ['[验收输入] 街区C', '113.31', '23.13'],
    ['[验收输入] 展馆D', '113.29', '23.15'],
  ]
  for (const [i, values] of candidates.entries()) {
    await page.getByRole('button', { name: '添加地点', exact: true }).click()
    await page.getByLabel('地点名称', { exact: true }).nth(i).fill(values[0]!)
    await page.getByLabel('GCJ-02经度', { exact: true }).nth(i).fill(values[1]!)
    await page.getByLabel('GCJ-02纬度', { exact: true }).nth(i).fill(values[2]!)
  }
  await page.getByRole('button', { name: '一起安排这段旅程', exact: true }).click()
  await expect(page.locator('.result-status')).toContainText('条件草案')
  await expect(page.locator('.day-tabs button')).toHaveCount(2)
  await page.locator('.day-tabs button').nth(1).click()
  await expect(page.locator('.day-heading')).toContainText('第 2 天')
  await page.locator('.day-tabs button').first().click()
  if (testInfo.project.name === 'desktop') {
    await expect(page.locator('.plan-panels.is-split')).toBeVisible()
    await expect(page.locator('#schedule-panel')).toBeVisible()
    await expect(page.locator('#map-panel')).toBeVisible()
  }
  // One map follows the same day and stop as the itinerary, on desktop and phone.
  await page.locator('.day-timeline .stop-dot').first().click()
  await expect(page.locator('.agent-map')).toBeVisible()
  await expect(page.locator('.agent-map')).toHaveCount(1)
  await expect(page.locator('.map-selection h4')).toContainText('博物馆A')
  const secondDayPoint = page
    .locator('.agent-map')
    .getByRole('button', { name: /^地图地点：第2天第1站/ })
  const secondDayName = (await secondDayPoint.getAttribute('aria-label'))!.split('站 ')[1]!
  await secondDayPoint.focus()
  await page.keyboard.press('Enter')
  await expect(secondDayPoint).toHaveAttribute('aria-pressed', 'true')
  await expect(page.locator('.map-selection h4')).toHaveText(secondDayName)
  await page.getByRole('button', { name: '查看对应行程', exact: true }).click()
  await expect(page.locator('.day-heading')).toContainText('第 2 天')
  await expect(page.locator('.day-timeline li.is-selected h3')).toHaveText(secondDayName)
  await page.locator('.day-tabs button').first().click()
  await expect(page.locator('.map-selection')).toHaveCount(0)
  await expect(page.locator('.day-timeline')).toContainText('你提供的地点')
  await expect(page.locator('.unknown-card')).toContainText('未知')
  await page.getByRole('tab', { name: '地点地图', exact: true }).click()
  await expect(page.locator('.agent-map')).toContainText('非导航底图')
  await page.getByRole('tab', { name: '每日安排', exact: true }).click()
  await page.locator('.replan-form input').fill('16:00')
  await page.getByRole('button', { name: '重新安排并检查', exact: true }).click()
  await expect(page.locator('.revision-label')).toContainText('2')
  await page.locator('.day-timeline .stop-dot').first().click()
  await page.getByRole('button', { name: '查看对应行程', exact: true }).click()
  await page.locator('.replan-form input').blur()
  await page
    .locator('.workspace-scroll')
    .evaluate((el) => el.scrollTo({ top: 0, behavior: 'instant' }))
  await page.screenshot({
    path: fileURLToPath(new URL(`overview-${testInfo.project.name}.png`, screenshots())),
  })
  const originalViewport = page.viewportSize()!
  const viewports =
    testInfo.project.name === 'desktop'
      ? ([
          ['wide', 1600, 1000],
          ['desktop', 1440, 1000],
          ['threshold', 1280, 1000],
          ['below-threshold', 1279, 1000],
          ['tablet', 768, 1024],
          ['narrow', 320, 812],
        ] as const)
      : ([['mobile', 390, 844]] as const)
  const checks = []
  for (const [name, width, height] of viewports) {
    await page.setViewportSize({ width, height })
    if (width >= 1280) {
      await expect(page.locator('.plan-panels.is-split')).toBeVisible()
      await expect(page.locator('.agent-map')).toHaveCount(1)
    } else {
      await expect(page.locator('.plan-panels.is-split')).toHaveCount(0)
      await expect(page.locator('.agent-map')).toHaveCount(0)
    }
    await page
      .locator('.result-column')
      .evaluate((el) => el.scrollIntoView({ block: 'start', behavior: 'instant' }))
    const layout = await page.evaluate(() => {
      const scroll = document.querySelector('.workspace-scroll')!
      return {
        documentWidth: document.documentElement.scrollWidth,
        viewport: innerWidth,
        scrollWidth: scroll.scrollWidth,
        clientWidth: scroll.clientWidth,
      }
    })
    expect(layout.scrollWidth, `result ${name} overflow`).toBeLessThanOrEqual(layout.clientWidth)
    expect(layout.documentWidth).toBeLessThanOrEqual(width)
    const scheduleBox = await page.locator('#schedule-panel').boundingBox()
    const mapBox = width >= 1280 ? await page.locator('#map-panel').boundingBox() : null
    if (mapBox && scheduleBox) {
      expect(mapBox.x).toBeGreaterThanOrEqual(scheduleBox.x + scheduleBox.width + 15)
      expect(Math.abs(mapBox.y - scheduleBox.y)).toBeLessThanOrEqual(2)
      expect(mapBox.x + mapBox.width).toBeLessThanOrEqual(width)
    }
    await page.screenshot({ path: fileURLToPath(new URL(`journey-${name}.png`, screenshots())) })
    checks.push({
      name,
      width,
      height,
      mode: width >= 1280 ? 'split' : 'tabs',
      layout,
      scheduleBox,
      mapBox,
    })
  }
  writeFileSync(
    new URL(
      `../../docs/design/governance/result-${testInfo.project.name}-viewport-check.json`,
      import.meta.url,
    ),
    JSON.stringify(checks, null, 2),
  )
  await page.setViewportSize(originalViewport)
  await page.getByRole('tab', { name: '地点地图', exact: true }).click()
  await page
    .locator('.result-column')
    .evaluate((el) => el.scrollIntoView({ block: 'start', behavior: 'instant' }))
  await expect(page.locator('.agent-map')).toBeVisible()
  await page.screenshot({
    path: fileURLToPath(new URL(`map-${testInfo.project.name}.png`, screenshots())),
  })
  await page.getByRole('tab', { name: /执行记录/ }).click()
  await expect(page.locator('.execution-card')).toBeVisible()
  expect(await page.locator('.execution-card li').count()).toBeGreaterThan(0)
  await page
    .locator('.execution-card')
    .evaluate((el) => el.scrollIntoView({ block: 'start', behavior: 'instant' }))
  await page.screenshot({
    path: fileURLToPath(new URL(`execution-${testInfo.project.name}.png`, screenshots())),
  })
  // Keyboard switches the actual panels and moves focus together.
  await page.getByRole('tab', { name: /执行记录/ }).focus()
  await page.keyboard.press('Home')
  await expect(page.getByRole('tab', { name: '每日安排', exact: true })).toBeFocused()
  await expect(page.locator('#schedule-panel')).toBeVisible()
  await page.getByRole('button', { name: '核对并保存当前草案', exact: true }).click()
  await expect(page.locator('.confirmation-card')).toBeFocused()
  const save = page.getByRole('button', { name: '确认保存到私人档案', exact: true })
  await expect(save).toBeDisabled()
  await page
    .locator('.confirmation-card')
    .evaluate((el) => el.scrollIntoView({ block: 'start', behavior: 'instant' }))
  await expect(save).toBeInViewport()
  await page.screenshot({
    path: fileURLToPath(new URL(`confirmation-${testInfo.project.name}.png`, screenshots())),
  })
  await page.locator('.confirmation-card input[type=checkbox]').check()
  await save.click()
  await expect(page.locator('.saved-card')).toContainText('已妥善收藏')
  await expect(page.locator('.workflow-steps [aria-current=step]')).toContainText('私人收藏')
  const after = await (await request.get(`${apiUrl}/map/overview`, { headers })).json()
  expect(after.stats).toEqual(before.stats)
  await page.reload()
  await page.getByRole('button', { name: '计划', exact: true }).click()
  await page.getByRole('button', { name: /最近任务/ }).click()
  await page.locator('.history-strip > button').first().click()
  await expect(page.locator('.saved-card')).toContainText('已妥善收藏')
  expect(errors).toEqual([])
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBeTruthy()
})

test('故事：实际保存测试记录→授权读取→编辑→确认，空记录不编造', async ({
  page,
  request,
}, testInfo) => {
  await login(page)
  await page.getByRole('button', { name: /^旅行记忆/ }).click()
  await page.getByRole('button', { name: '整理旅行故事', exact: true }).click()
  await page
    .getByLabel('想留下一段怎样的回忆？', { exact: true })
    .fill('[本地验收输入] 整理测试文字记录')
  await page.getByLabel('回忆开始日期', { exact: true }).fill('2099-01-01')
  await page.locator('.travel-brief input[type=checkbox]').check()
  await page.getByRole('button', { name: '整理我的旅行故事', exact: true }).click()
  await expect(page.locator('.result-status')).toContainText('信息不足')
  expect(await page.locator('.story-paper').count()).toBe(0)
  // Explicit local test fixture. Source=manual; not evidence of physical travel.
  await post(request, '/check-ins/manual-confirm', {
    username: 'AuroraRovella',
    adcode: '440100',
    city_name: '广州市',
    province_name: '广东省',
    longitude: 113.2644,
    latitude: 23.1291,
    source: 'manual',
  })
  await post(request, '/cities/440100/memories/confirm', {
    username: 'AuroraRovella',
    client_request_id: randomUUID(),
    title: `[验收夹具·非真实旅行] ${testInfo.project.name}`,
    body: '这是一条为本地软件验收主动录入的文字，不是真实旅行经历。用于检验日期、来源和用户编辑。',
    occurred_at: '2026-12-01T02:00:00Z',
    visibility: 'private',
  })
  await page.getByLabel('回忆开始日期', { exact: true }).fill('2026-12-01')
  await page.getByRole('button', { name: '整理我的旅行故事', exact: true }).click()
  await expect(page.locator('.story-paper textarea')).toHaveValue(/非真实旅行/)
  await page.locator('.story-paper input').fill('[用户编辑·本地验收] 我的测试故事')
  const edited = '用户确认编辑的测试故事：原文明确标注这是软件验收记录，不是真实旅行。'
  await page.locator('.story-paper textarea').fill(edited)
  await expect(page.locator('.save-preview')).toBeDisabled()
  await page.getByRole('button', { name: '保存草稿修改并重新检查', exact: true }).click()
  await expect(page.locator('.revision-label')).toContainText('2')
  await page.getByRole('button', { name: '核对并保存当前草案', exact: true }).click()
  await expect(page.locator('.confirmation-card')).toBeVisible()
  if (await page.locator('.confirmation-card input[type=checkbox]').count())
    await page.locator('.confirmation-card input[type=checkbox]').check()
  await page.getByRole('button', { name: '确认保存到私人档案', exact: true }).click()
  await expect(page.locator('.saved-card')).toContainText('已妥善收藏')
  await expect(page.locator('.story-paper textarea')).toHaveValue(edited)
  await page.locator('.result-heading').scrollIntoViewIfNeeded()
  await page.screenshot({
    path: fileURLToPath(new URL(`story-${testInfo.project.name}.png`, screenshots())),
  })
})
