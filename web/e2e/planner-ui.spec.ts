/** Real HTTP acceptance on the runner's isolated database. These are labelled test inputs, never real trips. */
import { test, expect } from '@playwright/test'
import { readFileSync, mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
const token =
  process.env.VOYAURA_E2E_TOKEN ??
  readFileSync(new URL('../../.local/access-token.txt', import.meta.url), 'utf8').trim()
test('规划：兴趣限制与信息不足恢复，不把未完成步骤或空草案当成功', async ({ page }, testInfo) => {
  const errors: string[] = []
  page.on('pageerror', (e) => errors.push(e.message))
  await page.goto('/')
  await page.getByRole('button', { name: '我的私人档案', exact: true }).click()
  await page.getByLabel('访问令牌', { exact: true }).fill(token)
  await page.getByRole('button', { name: '连接 Voyaura', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await page.getByRole('button', { name: '计划', exact: true }).click()
  await page
    .getByLabel('这次想怎样旅行？', { exact: true })
    .fill('[本地验收输入] 验证无地点时要求补充，不编造攻略')
  for (const name of ['博物馆', '美食', '海边'])
    await page
      .getByRole('group', { name: '旅行兴趣', exact: true })
      .getByRole('button', { name, exact: true })
      .click()
  const nature = page
    .getByRole('group', { name: '旅行兴趣', exact: true })
    .getByRole('button', { name: '自然风光', exact: true })
  await expect(nature).toBeDisabled()
  await page
    .getByRole('group', { name: '旅行兴趣', exact: true })
    .getByRole('button', { name: '美食', exact: true })
    .click()
  await expect(nature).toBeEnabled()
  await nature.click()
  await expect(page.getByLabel('想逛什么', { exact: true })).toHaveValue('博物馆，海边，自然风光')
  await expect(page.locator('.permission-card input[type=checkbox]').first()).not.toBeChecked()
  await page.getByRole('button', { name: '一起安排这段旅程', exact: true }).click()
  await expect(page.locator('.result-status')).toContainText('信息不足')
  await expect(page.locator('.save-preview')).toHaveCount(0)
  await expect(page.locator('.workflow-steps [aria-current=step]')).toContainText('整理草案')
  await expect(page.locator('.workflow-steps .complete')).toHaveCount(1)
  await expect(page.getByLabel('这次想怎样旅行？', { exact: true })).toHaveValue(
    '[本地验收输入] 验证无地点时要求补充，不编造攻略',
  )
  await expect(page.locator('.travel-brief')).toBeVisible()
  const folder = new URL('../../.local/e2e-evidence/flow-screenshots/', import.meta.url)
  mkdirSync(folder, { recursive: true })
  await page
    .locator('.result-column')
    .evaluate((el) => el.scrollIntoView({ block: 'start', behavior: 'instant' }))
  await page.screenshot({
    path: fileURLToPath(new URL(`missing-input-${testInfo.project.name}.png`, folder)),
  })
  await page.getByRole('button', { name: '补充想去的地点', exact: true }).last().click()
  await expect(page.locator('.candidate-input')).toHaveAttribute('open', '')
  await expect(page.getByRole('button', { name: '添加地点', exact: true })).toBeVisible()
  expect(errors).toEqual([])
})
