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
      props: {
        city,
        phase: 'ready',
        detail,
        error: null,
        mediaTasks: [],
        mediaTaskBusyId: null,
        mediaTaskError: null,
      },
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
        mediaTasks: [],
        mediaTaskBusyId: null,
        mediaTaskError: null,
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
        mediaTasks: [],
        mediaTaskBusyId: null,
        mediaTaskError: null,
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

  it('renders a private signed thumbnail and emits its delete command', async () => {
    const memory = {
      id: 'memory-with-photo',
      title: '珠江夜色',
      body: null,
      occurred_at: '2026-11-10T08:00:00Z',
      visibility: 'private' as const,
      media: [{
        id: 'asset-1',
        kind: 'photo' as const,
        original_filename: 'riverside.jpg',
        mime_type: 'image/jpeg',
        width: 1280,
        height: 960,
        duration_seconds: null,
        visibility: 'private' as const,
        upload_status: 'ready' as const,
        exif_status: 'removed' as const,
        scan_status: 'clean' as const,
        thumbnail_url: 'http://storage.test/thumbnail.webp?signature=test',
        content_url: 'http://storage.test/original.jpg?signature=test',
        thumbnail_width: 960,
        thumbnail_height: 720,
        created_at: '2026-11-10T08:00:00Z',
      }],
    }
    const wrapper = mount(CityMemoryPanel, {
      props: {
        city,
        phase: 'ready',
        detail: {
          ...detail,
          stats: { memories: 1, photos: 1, vlogs: 0, vlog_minutes: 0 },
          memories: [memory],
        },
        mediaTasks: [],
        mediaTaskBusyId: null,
        mediaTaskError: null,
        error: null,
      },
    })

    const link = wrapper.get('a[aria-label="查看 riverside.jpg"]')
    expect(link.attributes('href')).toContain('original.jpg')
    expect(link.get('img').attributes('src')).toContain('thumbnail.webp')
    expect(wrapper.text()).toContain('安全扫描已完成')
    await wrapper.get('button[aria-label="删除 riverside.jpg"]').trigger('click')
    expect(wrapper.emitted('deleteMedia')?.[0]).toEqual(['memory-with-photo', memory.media[0]])
  })

  it('shows failed media tasks and emits retry or delete commands', async () => {
    const task = {
      asset_id: 'failed-asset',
      memory_id: 'memory-1',
      memory_title: '珠江边的晚风',
      kind: 'photo' as const,
      original_filename: 'retry.jpg',
      byte_size: 1024,
      upload_status: 'failed' as const,
      scan_status: 'error' as const,
      failure_code: 'MEDIA_SCANNER_UNAVAILABLE',
      failure_message: '扫描器暂时不可用。',
      retryable: true,
      expired: false,
      upload_expires_at: null,
      created_at: '2026-11-10T08:00:00Z',
    }
    const wrapper = mount(CityMemoryPanel, {
      props: {
        city,
        phase: 'ready',
        detail,
        error: null,
        mediaTasks: [task],
        mediaTaskBusyId: null,
        mediaTaskError: null,
      },
    })

    expect(wrapper.text()).toContain('MEDIA_SCANNER_UNAVAILABLE')
    await wrapper.get('button[aria-label="重试媒体处理"]').trigger('click')
    await wrapper.get('button[aria-label="删除媒体任务"]').trigger('click')
    expect(wrapper.emitted('retryMedia')?.[0]).toEqual([task])
    expect(wrapper.emitted('deleteMedia')?.[0]).toEqual(['memory-1', task])
  })
})
