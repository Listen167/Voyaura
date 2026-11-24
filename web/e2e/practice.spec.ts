/** Explicit virtual practice input; real HTTP, real planner and real confirmation in the isolated test DB. */
import { test, expect } from '@playwright/test'
import { readFileSync, mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
const token =
  process.env.VOYAURA_E2E_TOKEN ??
  readFileSync(new URL('../../.local/access-token.txt', import.meta.url), 'utf8').trim()
const apiUrl = process.env.VOYAURA_E2E_API_URL ?? 'http://127.0.0.1:8018/api/v1'
const headers = { Authorization: `Bearer ${token}` }
test('真实离线演练：只填表→用户生成→地图联动与执行记录→明确确认保存', async ({
  page,
  request,
}, testInfo) => {
  const before = await (await request.get(`${apiUrl}/map/overview`, { headers })).json()
  const errors: string[] = [],
    external: string[] = [],
    mutations: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  page.on('request', (r) => {
    const url = new URL(r.url())
    if (!['127.0.0.1', 'localhost'].includes(url.hostname) && url.protocol.startsWith('http'))
      external.push(url.origin)
    if (url.pathname.startsWith('/api/') && !['GET', 'HEAD', 'OPTIONS'].includes(r.method()))
      mutations.push(`${r.method()} ${url.pathname}`)
  })
  await page.goto('/')
  await page.getByRole('button', { name: '我的私人档案', exact: true }).click()
  await page.getByLabel('访问令牌', { exact: true }).fill(token)
  await page.getByRole('button', { name: '连接 Voyaura', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await page.getByRole('button', { name: '计划', exact: true }).click()
  await expect(page.getByRole('region', { name: '生成行程前的地点条件' })).toContainText('信息不足')
  const folder = new URL(
    '../../.local/e2e-evidence/practice-screenshots/',
    import.meta.url,
  )
  mkdirSync(folder, { recursive: true })
  await page
    .locator('.workspace-scroll')
    .evaluate((el) => el.scrollTo({ top: 0, behavior: 'instant' }))
  await page.screenshot({
    path: fileURLToPath(new URL(`entry-${testInfo.project.name}.png`, folder)),
  })
  await page.getByRole('button', { name: '填入离线演练条件', exact: true }).click()
  await expect(page.getByRole('region', { name: '离线演练说明' })).toBeVisible()
  await expect(page.getByLabel('这次想怎样旅行？', { exact: true })).toHaveValue(/^\[离线演练\]/)
  await expect(page.locator('.candidate-content fieldset')).toHaveCount(4)
  await expect(page.locator('.permission-card input[type=checkbox]').first()).not.toBeChecked()
  await expect(page.locator('.permission-card input[type=checkbox]').first()).toBeDisabled()
  expect(mutations).toEqual([])
  const creation = page.waitForResponse(
    (r) => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith('/agent/runs'),
  )
  await page.getByRole('button', { name: '开始演练', exact: true }).click()
  const created = await (await creation).json()
  await expect(page.locator('.result-heading h2')).toContainText('[离线演练]')
  await expect(page.locator('.result-status')).toContainText('条件草案')
  await expect(page.locator('.day-tabs button')).toHaveCount(2)
  expect(created.request.allow_external).toBe(false)
  expect(created.request.allow_model).toBe(false)
  expect(created.request.allow_memory_access).toBe(false)
  expect(
    created.request.candidates.every((c: { name: string }) => c.name.startsWith('[离线演练]')),
  ).toBeTruthy()
  const draft = await (await request.get(`${apiUrl}/agent/runs/${created.id}`, { headers })).json()
  expect(draft.title).toContain('[离线演练]')
  expect(draft.saved_artifact_id).toBeNull()
  expect(draft.status).toBe('awaiting_confirmation')
  await page.locator('.day-timeline .stop-dot').first().click()
  await expect(page.locator('.map-selection')).toContainText('[离线演练] 虚拟地点')
  await page.getByRole('button', { name: '查看对应行程', exact: true }).click()
  await page
    .locator('.result-column')
    .evaluate((el) => el.scrollIntoView({ block: 'start', behavior: 'instant' }))
  await page.screenshot({
    path: fileURLToPath(new URL(`result-${testInfo.project.name}.png`, folder)),
  })
  await page.getByRole('tab', { name: /执行记录/ }).click()
  await expect(page.locator('.execution-card')).toBeVisible()
  expect(await page.locator('.execution-card li').count()).toBeGreaterThan(0)
  await page.getByRole('button', { name: '核对并保存当前草案', exact: true }).click()
  await expect(page.locator('.confirmation-card')).toContainText('这是虚拟地点的离线演练')
  const save = page.getByRole('button', { name: '确认保存到私人档案', exact: true })
  await expect(save).toBeDisabled()
  await page.locator('.confirmation-card input[type=checkbox]').check()
  await save.click()
  await expect(page.locator('.saved-card')).toContainText('演练草案已保存')
  const saved = await (await request.get(`${apiUrl}/agent/runs/${created.id}`, { headers })).json()
  expect(saved.title).toContain('[离线演练]')
  expect(saved.saved_artifact_id).not.toBeNull()
  expect(saved.status).toBe('confirmed')
  const after = await (await request.get(`${apiUrl}/map/overview`, { headers })).json()
  expect(after.stats).toEqual(before.stats)
  expect(external).toEqual([])
  expect(errors).toEqual([])
  await page.getByRole('button', { name: '最近任务', exact: true }).click()
  await expect(page.locator('.history-strip')).toContainText('[离线演练]')
})
