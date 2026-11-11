import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import MemoryComposerDialog from './MemoryComposerDialog.vue'
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
  memory_count: 0,
  check_in_source: 'manual',
}

describe('MemoryComposerDialog', () => {
  it('collects a private text memory for preview', async () => {
    const wrapper = mount(MemoryComposerDialog, {
      props: {
        city,
        mode: 'create',
        initialMemory: null,
        phase: 'editing',
        preview: null,
        error: null,
      },
    })

    await wrapper.get('input[placeholder="给这段记忆一个名字"]').setValue('珠江边的晚风')
    await wrapper.get('textarea').setValue('记下当时的风。')
    await wrapper.get('form').trigger('submit')

    const input = wrapper.emitted('preview')?.[0]?.[0] as Record<string, unknown>
    expect(input.title).toBe('珠江边的晚风')
    expect(input.body).toBe('记下当时的风。')
    expect(input.visibility).toBe('private')
  })

  it('requires a final confirmation from the preview', async () => {
    const wrapper = mount(MemoryComposerDialog, {
      props: {
        city,
        mode: 'create',
        initialMemory: null,
        phase: 'preview',
        error: null,
        preview: {
          city_adcode: city.adcode,
          city_name: city.name_zh,
          title: '珠江边的晚风',
          body: null,
          occurred_at: '2026-11-10T04:00:00Z',
          visibility: 'private',
          confirmation_notice: '确认后保存。',
        },
      },
    })

    await wrapper.get('.memory-composer-actions .primary').trigger('click')
    expect(wrapper.emitted('confirm')).toHaveLength(1)
  })

  it('prefills an existing memory for editing', () => {
    const wrapper = mount(MemoryComposerDialog, {
      props: {
        city,
        mode: 'edit',
        initialMemory: {
          id: 'memory-1',
          title: '沙面散步',
          body: '树影落在旧建筑上。',
          occurred_at: '2026-11-08T04:00:00Z',
          visibility: 'shared',
          media: [],
        },
        phase: 'editing',
        preview: null,
        error: null,
      },
    })

    expect((wrapper.get('input[placeholder="给这段记忆一个名字"]').element as HTMLInputElement).value).toBe('沙面散步')
    expect((wrapper.get('textarea').element as HTMLTextAreaElement).value).toBe('树影落在旧建筑上。')
    expect((wrapper.get('input[type="checkbox"]').element as HTMLInputElement).checked).toBe(true)
    expect(wrapper.text()).toContain('预览修改')
  })
})
