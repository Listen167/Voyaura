import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import MediaUploadDialog from './MediaUploadDialog.vue'
import type { CityMemoryItem, VisitedCity } from '../types'

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

const memory: CityMemoryItem = {
  id: 'memory-1',
  title: '珠江边的晚风',
  body: null,
  occurred_at: '2026-11-10T08:00:00Z',
  visibility: 'private',
  media: [],
}

describe('MediaUploadDialog', () => {
  it('requires final confirmation after a private upload preview', async () => {
    const wrapper = mount(MediaUploadDialog, {
      props: {
        city,
        memory,
        phase: 'preview',
        file: null,
        preview: {
          kind: 'photo',
          filename: 'riverside.jpg',
          mime_type: 'image/jpeg',
          byte_size: 2048,
          quota_remaining_bytes: 1024 * 1024,
          visibility: 'private',
          confirmation_notice: '确认后上传并移除 EXIF。',
        },
        error: null,
      },
    })

    expect(wrapper.text()).toContain('riverside.jpg')
    expect(wrapper.text()).toContain('移除 EXIF')
    await wrapper.get('.media-upload-preview .primary').trigger('click')
    expect(wrapper.emitted('confirm')).toHaveLength(1)
  })
})
