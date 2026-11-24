/** Real HTTP on verify_e2e.py's isolated DB; every written input is an explicit software fixture. */
import { test, expect, type Page } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { practiceBrief } from '../src/content/plannerPractice'
const token = process.env.VOYAURA_E2E_TOKEN!
const api = process.env.VOYAURA_E2E_API_URL!
const headers = { Authorization: `Bearer ${token}` }
const folder = new URL(
  '../../.local/e2e-evidence/account-screenshots/',
  import.meta.url,
)
mkdirSync(folder, { recursive: true })
async function connect(page: Page) {
  await page.getByLabel('访问令牌', { exact: true }).fill(token)
  await page.getByRole('button', { name: '连接 Voyaura', exact: true }).click()
  await expect(page.locator('.connection-card')).toHaveCount(0)
}
async function shot(page: Page, name: string, project: string) {
  await page.screenshot({
    path: fileURLToPath(new URL(`${name}-${project}.png`, folder)),
  })
}
test('第四轮：访客引导无私人读取→登录恢复城市日期→档案打开原任务，仅GET并可刷新', async ({
  page,
  request,
}, info) => {
  test.setTimeout(90000)
  page.setDefaultTimeout(15000)
  const errors: string[] = [],
    mutations: string[] = [],
    reads: string[] = [],
    external: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('request', (r) => {
    const url = new URL(r.url())
    if (url.pathname.startsWith('/api/')) {
      if (r.method() === 'GET') reads.push(url.pathname)
      else mutations.push(`${r.method()} ${url.pathname}`)
    }
    if (
      url.protocol.startsWith('http') &&
      !['localhost', '127.0.0.1'].includes(url.hostname)
    )
      external.push(url.origin)
  })
  await page.goto('/account')
  await expect(page.getByRole('main', { name: '我的旅行档案' })).toBeVisible()
  await expect(page.locator('.account-identity')).toHaveCount(0)
  expect(reads).toEqual([])
  await shot(page, 'guest', info.project.name)
  await page.goto('/journey/stories?compose=story&city=350200&date=2026-06-08')
  await expect(page.locator('.connection-return')).toContainText(
    '旅行记忆与故事',
  )
  expect(reads).toEqual([])
  await shot(page, 'return-context', info.project.name)
  await connect(page)
  await expect(page.getByLabel('目的地', { exact: true })).toHaveValue('350200')
  await expect(page.getByLabel('回忆开始日期', { exact: true })).toHaveValue(
    '2026-06-08',
  )
  await expect(page.locator('.story-consent input')).not.toBeChecked()

  // Explicit labelled task in the separate test DB, not a model or online map response.
  const sample = practiceBrief()
  const response = await request.post(`${api}/agent/runs`, {
    headers,
    data: {
      client_request_id: crypto.randomUUID(),
      kind: 'plan',
      goal: '[本地验收·非真实旅行] 第四轮历史恢复',
      city_adcode: '440100',
      city_name: '广州市',
      start_date: '2026-11-23',
      days: 2,
      daily_start: '09:00',
      daily_end: '18:00',
      budget_yuan: null,
      pace: 'relaxed',
      transport: 'walking',
      interests: [],
      must_visit: [],
      candidates: sample.candidates,
      allow_external: false,
      allow_model: false,
      allow_memory_access: false,
      memory_ids: [],
    },
  })
  expect(response.ok()).toBeTruthy()
  const created = await response.json()
  const title = `[本地验收·非真实旅行] 第四轮${info.project.name}任务`
  const marked = await request.patch(`${api}/agent/runs/${created.id}/draft`, {
    headers,
    data: { expected_revision: created.revision, title },
  })
  expect(marked.ok()).toBeTruthy()
  const original = await marked.json()
  await page.getByRole('button', { name: '我的私人档案', exact: true }).click()
  await expect(page).toHaveURL(/\/account$/)
  await expect(page.locator('.account-identity')).toContainText('AuroraRovella')
  await expect(page.locator('.account-capabilities')).toContainText('尚未连接')
  const task = page.getByRole('button', {
    name: `打开行程：${title}`,
    exact: true,
  })
  await expect(task).toBeVisible()
  await shot(page, 'account', info.project.name)
  await task.click()
  await expect(page).toHaveURL(new RegExp(`/plan\\?run=${created.id}`))
  await expect(page.locator('.result-heading h2')).toHaveText(title)
  await expect(page.locator('.revision-label')).toContainText(
    String(original.revision),
  )
  expect(mutations).toEqual([])
  await page.reload()
  await expect(page.locator('.result-heading h2')).toHaveText(title)
  await expect(page.locator('.saved-card')).toHaveCount(0)
  const restored = await (
    await request.get(`${api}/agent/runs/${created.id}`, { headers })
  ).json()
  expect(restored.revision).toBe(original.revision)
  expect(restored.saved_artifact_id).toBeNull()
  await shot(page, 'restored-task', info.project.name)

  const checks = []
  for (const width of info.project.name === 'desktop'
    ? [1440, 768, 320]
    : [390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 })
    await page.goto('/account')
    await expect(page.locator('.account-task-list')).toBeVisible()
    const sizes = await page.evaluate(() => {
      const el = document.querySelector('.account-scroll')!
      return {
        viewport: innerWidth,
        documentWidth: document.documentElement.scrollWidth,
        client: el.clientWidth,
        scroll: el.scrollWidth,
      }
    })
    expect(sizes.documentWidth).toBeLessThanOrEqual(width)
    expect(sizes.scroll).toBeLessThanOrEqual(sizes.client)
    await page.screenshot({
      path: fileURLToPath(new URL(`account-${width}.png`, folder)),
    })
    checks.push(sizes)
  }
  expect(errors).toEqual([])
  expect(external).toEqual([])
  expect(mutations).toEqual([])
  writeFileSync(
    new URL(`checks-${info.project.name}.json`, folder),
    JSON.stringify({ checks, errors, mutations, external }, null, 2),
  )
})

test('第四轮：取消离开保留规划文字；记忆编辑关闭也需选择，未提交正文不入库', async ({
  page,
  request,
}, info) => {
  test.setTimeout(90000)
  page.setDefaultTimeout(15000)
  const errors: string[] = [],
    memoryWrites: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('request', (r) => {
    if (
      r.method() !== 'GET' &&
      /\/memories\/(preview|confirm)$/.test(new URL(r.url()).pathname)
    )
      memoryWrites.push(r.method())
  })
  await page.goto('/')
  await page.getByRole('button', { name: '我的私人档案', exact: true }).click()
  await connect(page)
  await page.getByRole('button', { name: '计划', exact: true }).click()
  const goal = page.getByLabel('这次想怎样旅行？', { exact: true })
  await goal.fill('[本地验收·未提交] 取消离开后保留这段输入')
  await page.getByRole('button', { name: '我的', exact: true }).click()
  const prompt = page.getByRole('dialog', {
    name: '还有未保存的编辑。',
    exact: true,
  })
  await expect(
    prompt.getByRole('button', { name: '继续编辑', exact: true }),
  ).toBeFocused()
  await shot(page, 'unsaved-plan', info.project.name)
  await prompt.getByRole('button', { name: '继续编辑', exact: true }).click()
  await expect(prompt).toHaveCount(0)
  await expect(page).toHaveURL(/\/plan$/)
  await expect(goal).toHaveValue('[本地验收·未提交] 取消离开后保留这段输入')
  await page.getByRole('button', { name: '我的', exact: true }).click()
  await prompt
    .getByRole('button', { name: '放弃编辑并离开', exact: true })
    .click()
  await expect(page).toHaveURL(/\/account$/)
  await page.getByRole('button', { name: '旅程', exact: true }).click()
  await page
    .locator('.journey-hero')
    .getByRole('button', { name: '记录一次抵达', exact: true })
    .click()
  await page
    .locator('.manual-city-results > button')
    .filter({ hasText: '厦门市' })
    .click()
  await page.getByRole('button', { name: '确认点亮', exact: true }).click()
  await page.getByRole('button', { name: '查看城市档案', exact: true }).click()
  const before = await (
    await request.get(`${api}/cities/350200/memories`, { headers })
  ).json()
  await page.getByRole('button', { name: '写一段记忆', exact: true }).click()
  const editor = page.getByRole('dialog', {
    name: '写给厦门市的记忆',
    exact: true,
  })
  await editor
    .getByLabel('标题', { exact: true })
    .fill('[本地验收·未提交] 不应写入档案')
  await editor
    .getByLabel('正文', { exact: true })
    .fill('这是尚未预览或保存的测试输入。')
  await editor
    .getByRole('button', { name: '关闭记忆编辑器', exact: true })
    .click()
  await expect(prompt).toBeVisible()
  await shot(page, 'unsaved-memory', info.project.name)
  await page.keyboard.press('Escape')
  await expect(prompt).toHaveCount(0)
  await expect(editor.getByLabel('正文', { exact: true })).toHaveValue(
    '这是尚未预览或保存的测试输入。',
  )
  await editor
    .getByRole('button', { name: '关闭记忆编辑器', exact: true })
    .click()
  await prompt
    .getByRole('button', { name: '放弃编辑并离开', exact: true })
    .click()
  await expect(page.locator('.memory-composer-backdrop')).toHaveCount(0)
  const after = await (
    await request.get(`${api}/cities/350200/memories`, { headers })
  ).json()
  expect(after.memories.length).toBe(before.memories.length)
  expect(memoryWrites).toEqual([])
  expect(errors).toEqual([])
})
