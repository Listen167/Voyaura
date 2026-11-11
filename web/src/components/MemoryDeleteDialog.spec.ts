import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import MemoryDeleteDialog from './MemoryDeleteDialog.vue'
import type { VisitedCity } from '../types'

const city: VisitedCity = {
  adcode: '440100',
  name_zh: '广州市',
  name_en: 'Guangzhou',
  province_zh: '广东省',
  longitude: 113.2644,
  latitude: 23.1291,
  first_visited_at: '2026-11-01T08:00:00Z',
  last_visited_at: '2026-11-10T08:00:00Z',
  memory_count: 1,
  check_in_source: 'manual',
}

describe('MemoryDeleteDialog', () => {
  it('requires explicit confirmation from the delete preview', async () => {
    const wrapper = mount(MemoryDeleteDialog, {
      props: {
        city,
        phase: 'preview',
        preview: {
          memory_id: 'memory-1',
          city_adcode: city.adcode,
          city_name: city.name_zh,
          title: '珠江边的晚风',
          occurred_at: '2026-11-10T08:00:00Z',
          media_count: 0,
          confirmation_notice: '确认后删除，无法撤销。',
        },
        error: null,
      },
    })

    expect(wrapper.text()).toContain('珠江边的晚风')
    expect(wrapper.text()).toContain('无法撤销')
    await wrapper.get('.danger-primary').trigger('click')
    expect(wrapper.emitted('confirm')).toHaveLength(1)
  })
})
