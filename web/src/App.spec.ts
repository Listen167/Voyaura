import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import App from './App.vue'

vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('API offline')))

describe('Voyaura shell', () => {
  it('opens on the map and exposes Xiaoxi', () => {
    const wrapper = mount(App)
    expect(wrapper.text()).toContain('你好，Aurora')
    expect(wrapper.text()).toContain('小曦')
    expect(wrapper.find('[aria-label="中国旅行地图"]').exists()).toBe(true)
  })
})
