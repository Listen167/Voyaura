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
        uploadProgress: { loaded: 0, total: 0, percent: 0 },
        error: null,
      },
    })

    expect(wrapper.text()).toContain('riverside.jpg')
    expect(wrapper.text()).toContain('移除 EXIF')
    await wrapper.get('.media-upload-preview .primary').trigger('click')
    expect(wrapper.emitted('confirm')).toHaveLength(1)
  })

  it('explains the asynchronous safety and preview processing state', () => {
    const wrapper = mount(MediaUploadDialog, {
      props: {
        city,
        memory,
        phase: 'processing',
        file: null,
        preview: null,
        uploadProgress: { loaded: 0, total: 0, percent: 0 },
        error: null,
      },
    })

    expect(wrapper.text()).toContain('正在安全扫描并生成预览')
    expect(wrapper.text()).toContain('视频封面')
  })

  it('provides camera, video and library sources on mobile', async () => {
    const wrapper = mount(MediaUploadDialog, {
      props: {
        city,
        memory,
        phase: 'selecting',
        file: null,
        preview: null,
        uploadProgress: { loaded: 0, total: 0, percent: 0 },
        error: null,
      },
    })

    const inputs = wrapper.findAll('input[type="file"]')
    expect(inputs).toHaveLength(3)
    expect(inputs[0].attributes('capture')).toBe('environment')
    expect(inputs[0].attributes('accept')).toContain('image/jpeg')
    expect(inputs[1].attributes('capture')).toBe('environment')
    expect(inputs[1].attributes('accept')).toContain('video/mp4')
    expect(inputs[2].attributes('capture')).toBeUndefined()
    expect(wrapper.text()).toContain('拍照')
    expect(wrapper.text()).toContain('录像')

    const file = new File(['photo'], 'camera.jpg', { type: 'image/jpeg' })
    Object.defineProperty(inputs[0].element, 'files', { value: [file], configurable: true })
    await inputs[0].trigger('change')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('preview')?.[0]).toEqual([file])
  })

  it('shows byte progress and emits a real upload cancellation command', async () => {
    const wrapper = mount(MediaUploadDialog, {
      props: {
        city,
        memory,
        phase: 'uploading',
        file: null,
        preview: null,
        uploadProgress: { loaded: 5, total: 10, percent: 50 },
        error: null,
      },
    })

    const progress = wrapper.get('[role="progressbar"]')
    expect(progress.attributes('aria-valuenow')).toBe('50')
    expect(progress.get('span').attributes('style')).toContain('50%')
    expect(wrapper.text()).toContain('50%')
    await wrapper.get('.media-upload-cancel').trigger('click')
    expect(wrapper.emitted('cancelUpload')).toHaveLength(1)
  })
})
