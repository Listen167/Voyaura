import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import MediaDeleteDialog from './MediaDeleteDialog.vue'
import type { MediaDeletePreview, VisitedCity } from '../types'

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

const preview: MediaDeletePreview = {
  asset_id: 'asset-1',
  memory_id: 'memory-1',
  city_adcode: '440100',
  city_name: '广州市',
  memory_title: '珠江夜色',
  kind: 'photo',
  original_filename: 'riverside.jpg',
  byte_size: 2048,
  upload_status: 'ready',
  confirmation_notice: '确认后将永久删除原文件、预览图和媒体记录，此操作无法撤销。',
}

describe('MediaDeleteDialog', () => {
  it('requires explicit confirmation with the selected filename', async () => {
    const wrapper = mount(MediaDeleteDialog, {
      props: { city, phase: 'preview', preview, error: null },
    })

    expect(wrapper.text()).toContain('riverside.jpg')
    expect(wrapper.text()).toContain('无法撤销')
    await wrapper.get('.danger-primary').trigger('click')
    expect(wrapper.emitted('confirm')).toHaveLength(1)
  })

  it('shows stable processing-conflict diagnostics', () => {
    const wrapper = mount(MediaDeleteDialog, {
      props: {
        city,
        phase: 'error',
        preview: null,
        error: {
          code: 'MEDIA_DELETE_PROCESSING_CONFLICT',
          message: '媒体仍在安全处理中。',
          details: {},
          retryable: true,
          requestId: 'request-media-delete',
        },
      },
    })

    expect(wrapper.text()).toContain('MEDIA_DELETE_PROCESSING_CONFLICT')
    expect(wrapper.text()).toContain('request-media-delete')
  })
})
