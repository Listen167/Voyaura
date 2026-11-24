import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory } from 'vue-router'
import { createProductRouter } from './router'
import App from './App.vue'
enableAutoUnmount(afterEach)
const fetchMock = vi.fn()
vi.stubGlobal('fetch', fetchMock)
beforeEach(() => {
  sessionStorage.clear()
  fetchMock.mockReset()
  fetchMock.mockRejectedValue(new Error('explicit offline test'))
})
async function setup(path = '/') {
  const router = createProductRouter(createMemoryHistory())
  await router.push(path)
  await router.isReady()
  const wrapper = mount(App, { global: { plugins: [router] } })
  await flushPromises()
  return { wrapper, router }
}
describe('Voyaura发现入口与按需身份连接', () => {
  it('我的页面可先阅读引导，未连接不读取私人API', async () => {
    const { wrapper, router } = await setup('/account')
    expect(router.currentRoute.value.path).toBe('/account')
    expect(wrapper.find('[aria-label="我的旅行档案"]').exists()).toBe(true)
    expect(wrapper.find('[role=dialog]').exists()).toBe(false)
    expect(fetchMock).not.toHaveBeenCalled()
  })
  it('首次打开可浏览发现，不弹连接框也不读取私人API', async () => {
    const { wrapper } = await setup()
    expect(wrapper.find('[aria-label="旅行发现首页"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('下一段旅程')
    expect(wrapper.find('[role=dialog]').exists()).toBe(false)
    expect(fetchMock).not.toHaveBeenCalled()
  })
  it('点击目的地后才请求连接，关闭后仍可继续浏览', async () => {
    const { wrapper, router } = await setup()
    await wrapper.find('[aria-label="规划厦门旅行"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[role=dialog]').exists()).toBe(true)
    expect(router.currentRoute.value.path).toBe('/')
    expect(fetchMock).not.toHaveBeenCalled()
    await wrapper.find('[aria-label="关闭连接窗口"]').trigger('click')
    expect(wrapper.find('[role=dialog]').exists()).toBe(false)
    expect(wrapper.find('[aria-label="旅行发现首页"]').exists()).toBe(true)
  })
  it('直接进入私人计划路由时先连接，发现首页保留可见', async () => {
    const { wrapper, router } = await setup('/plan')
    expect(router.currentRoute.value.path).toBe('/')
    expect(wrapper.find('[role=dialog]').exists()).toBe(true)
    expect(wrapper.find('[aria-label="旅行发现首页"]').exists()).toBe(true)
    expect(fetchMock).not.toHaveBeenCalled()
  })
})

function connectedResponses() {
  fetchMock.mockImplementation(async (input: string) => {
    const path = new URL(input, 'http://local.test').pathname
    const body = path.endsWith('/auth/me')
      ? { username: 'explicit-unit-owner' }
      : path.endsWith('/map/overview')
        ? {
            username: 'explicit-unit-owner',
            map_center: [104, 35],
            default_zoom: 4,
            stats: { lit_cities: 0, memories: 0, photos: 0, vlog_minutes: 0 },
            visited_cities: [],
            year_summaries: [],
          }
        : path.endsWith('/agent/capabilities')
          ? {
              amap_configured: false,
              model_configured: false,
              tools: [],
              limits: {},
            }
          : path.endsWith('/agent/runs')
            ? { items: [] }
            : { available: false, styles: [] }
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  })
}
describe('第四轮导航与未保存编辑', () => {
  it('验证后恢复故事直达链接的城市和日期，验证前不读取私人接口', async () => {
    connectedResponses()
    const { wrapper, router } = await setup(
      '/journey/stories?compose=story&city=350200&date=2026-06-08',
    )
    expect(fetchMock).not.toHaveBeenCalled()
    await wrapper
      .get('#access-token')
      .setValue('explicit-unit-token-at-least-thirty-two-characters')
    await wrapper.get('.connection-card form').trigger('submit')
    await flushPromises()
    expect(router.currentRoute.value.query).toEqual({
      compose: 'story',
      city: '350200',
      date: '2026-06-08',
    })
    expect(
      wrapper.get<HTMLSelectElement>('[aria-label="目的地"]').element.value,
    ).toBe('350200')
    expect(
      wrapper.get<HTMLInputElement>('[aria-label="回忆开始日期"]').element
        .value,
    ).toBe('2026-06-08')
    expect(
      wrapper.get<HTMLInputElement>('.story-consent input').element.checked,
    ).toBe(false)
  })
  it('取消导航保留输入，主动放弃后离开；刷新保护随脏状态解除', async () => {
    connectedResponses()
    sessionStorage.setItem('voyaura.access-token', 'explicit-unit-session')
    const { wrapper, router } = await setup('/plan')
    await wrapper
      .get('textarea[aria-label="这次想怎样旅行？"]')
      .setValue('明确的未保存输入')
    const unload = new Event('beforeunload', { cancelable: true })
    window.dispatchEvent(unload)
    expect(unload.defaultPrevented).toBe(true)
    const first = router.push('/account')
    await flushPromises()
    expect(wrapper.get('.unsaved-dialog').text()).toContain('未保存')
    await wrapper.get('[data-stay]').trigger('click')
    await first
    expect(router.currentRoute.value.path).toBe('/plan')
    expect(
      wrapper.get<HTMLTextAreaElement>(
        'textarea[aria-label="这次想怎样旅行？"]',
      ).element.value,
    ).toBe('明确的未保存输入')
    const second = router.push('/account')
    await flushPromises()
    await wrapper.get('.unsaved-dialog .journey-secondary').trigger('click')
    await second
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/account')
    const cleanUnload = new Event('beforeunload', { cancelable: true })
    window.dispatchEvent(cleanUnload)
    expect(cleanUnload.defaultPrevented).toBe(false)
    expect(
      fetchMock.mock.calls.every(
        ([, init]) => !init?.method || init.method === 'GET',
      ),
    ).toBe(true)
  })

})
