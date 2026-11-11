import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import CityMemoryPanel from './CityMemoryPanel.vue'
import type { CityMemoryDetail, VisitedCity } from '../types'

const city: VisitedCity = {
  adcode: '440100',
  name_zh: '广州市',
  name_en: 'Guangzhou',
  province_zh: '广东省',
  longitude: 113.2644,
  latitude: 23.1291,
  first_visited_at: '2026-11-01T08:00:00Z',
  last_visited_at: '2026-11-10T08:00:00Z',
  memory_count: 0,
  check_in_source: 'device',
}

const detail: CityMemoryDetail = {
  city,
  visit_note: null,
  stats: { memories: 0, photos: 0, vlogs: 0, vlog_minutes: 0 },
  memories: [],
}

describe('CityMemoryPanel', () => {
  it('shows a truthful empty city archive and opens Xiaoxi', async () => {
    const wrapper = mount(CityMemoryPanel, {
      props: { city, phase: 'ready', detail, error: null },
    })

    expect(wrapper.text()).toContain('我与广州市')
    expect(wrapper.text()).toContain('这里还没有旅行记忆')
    await wrapper.get('footer button:last-child').trigger('click')
    expect(wrapper.emitted('askXiaoxi')?.[0]).toEqual([city])
  })

  it('shows the stable error code and request id', () => {
    const wrapper = mount(CityMemoryPanel, {
      props: {
        city,
        phase: 'error',
        detail: null,
        error: {
          code: 'CITY_MEMORY_LOAD_FAILED',
          message: '读取失败。',
          details: {},
          retryable: true,
          requestId: 'request-123',
        },
      },
    })

    expect(wrapper.text()).toContain('CITY_MEMORY_LOAD_FAILED')
    expect(wrapper.text()).toContain('request-123')
  })

  it('emits the selected memory for edit and delete actions', async () => {
    const memory = {
      id: 'memory-1',
      title: '珠江边的晚风',
      body: '真实记录。',
      occurred_at: '2026-11-10T08:00:00Z',
      visibility: 'private' as const,
      media: [],
    }
    const wrapper = mount(CityMemoryPanel, {
      props: {
        city,
        phase: 'ready',
        detail: {
          ...detail,
          stats: { ...detail.stats, memories: 1 },
          memories: [memory],
        },
        error: null,
      },
    })

    await wrapper.get('button[aria-label="编辑记忆"]').trigger('click')
    await wrapper.get('button[aria-label="删除记忆"]').trigger('click')
    await wrapper.get('button[aria-label="添加照片或 Vlog"]').trigger('click')

    expect(wrapper.emitted('editMemory')?.[0]).toEqual([memory])
    expect(wrapper.emitted('deleteMemory')?.[0]).toEqual([memory])
    expect(wrapper.emitted('uploadMedia')?.[0]).toEqual([memory])
  })
})
