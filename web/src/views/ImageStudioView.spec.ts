import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ImageStudioView from './ImageStudioView.vue'
import type { ImageJob, ImageStyleCatalog } from '../types'

const job: ImageJob = {
  id: 'job-1',
  status: 'succeeded',
  source_asset_id: 'asset-1',
  source_filename: 'pearl-river.jpg',
  source_url: 'http://storage.test/source.jpg',
  source_thumbnail_url: 'http://storage.test/thumb.webp',
  city_adcode: '440100',
  city_name: '广州市',
  memory_id: 'memory-1',
  memory_title: '珠江夜色',
  style_id: 'retro_film',
  provider: 'comfyui',
  provider_job_id: 'prompt-1',
  prompt: 'retro travel film photography, pearl river at night',
  negative_prompt: 'blurry',
  preservation_level: 'balanced',
  recipe: {
    version: 'voyaura-1',
    aspect_ratio: 'source',
    layout: 'full-frame photograph',
    focal_element: 'recognizable source subject',
    typography: 'none',
    color: 'warm film palette',
    texture: 'fine grain',
    default_preservation: 'balanced',
    preservation_level: 'balanced',
  },
  style_source: null,
  model_names: ['voyaura-test-model.safetensors'],
  caption_mode: 'travel_stamp',
  caption: {
    title: '珠江夜色',
    location: '广州市',
    date: '2026-11-10',
    layout: 'archive_band',
    palette: 'coral',
    font_style: 'sans',
  },
  companion: {
    asset_version: 'xiaoxi-v1',
    pose: 'default',
    expression: 'warm',
    position: 'right',
    scale: 'medium',
    method: 'deterministic_alpha_composite',
    disclosure: '小曦角色使用经授权透明素材进行确定性合成。',
  },
  is_favorite: false,
  output_url: 'http://storage.test/result.webp',
  download_url: 'http://storage.test/result.webp?download=1',
  output_mime_type: 'image/webp',
  output_width: 1280,
  output_height: 960,
  failure_code: null,
  failure_message: null,
  retryable: false,
  created_at: '2026-11-10T08:00:00Z',
  completed_at: '2026-11-10T08:01:00Z',
}

const catalog: ImageStyleCatalog = {
  provider: 'comfyui',
  available: true,
  missing_settings: [],
  companion: {
    available: true,
    missing_settings: [],
    asset_version: 'xiaoxi-v1',
    positions: ['left', 'right'],
    scales: ['small', 'medium', 'large'],
    poses: ['default'],
    expressions: ['warm'],
  },
  styles: [{
    id: 'retro_film',
    name: '复古胶片',
    description: '旅行底片质感',
    swatch: '#e9583e',
    recipe: { ...job.recipe, preservation_level: null },
    source: null,
  }],
}

const {
  getImageJobs,
  getImageStyles,
  setImageJobFavorite,
  previewImageJobDelete,
  confirmImageJobDelete,
} = vi.hoisted(() => ({
  getImageJobs: vi.fn(),
  getImageStyles: vi.fn(),
  setImageJobFavorite: vi.fn(),
  previewImageJobDelete: vi.fn(),
  confirmImageJobDelete: vi.fn(),
}))

vi.mock('../api/client', () => ({
  ApiClientError: class extends Error {},
  getImageJobs,
  getImageStyles,
  setImageJobFavorite,
  previewImageJobDelete,
  confirmImageJobDelete,
}))

describe('ImageStudioView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getImageJobs.mockResolvedValue({ items: [job] })
    getImageStyles.mockResolvedValue(catalog)
    setImageJobFavorite.mockResolvedValue({ ...job, is_favorite: true })
  })

  it('shows generation history, comparison and download action', async () => {
    const wrapper = mount(ImageStudioView)
    await flushPromises()

    expect(wrapper.text()).toContain('旅行影像工作台')
    expect(wrapper.text()).toContain('广州市')
    expect(wrapper.text()).toContain('复古胶片')
    expect(wrapper.text()).toContain('voyaura-test-model.safetensors')
    expect(wrapper.text()).toContain('voyaura-1')
    expect(wrapper.text()).toContain('珠江夜色 · 广州市 · 2026-11-10')
    expect(wrapper.text()).toContain('档案横带 · 珊瑚红 · 现代黑体')
    expect(wrapper.text()).toContain('小曦角色使用经授权透明素材进行确定性合成')
    expect(wrapper.find('.image-compare-slider').exists()).toBe(true)
    expect(wrapper.get('.studio-actions a').attributes('href')).toContain('download=1')

    await wrapper.get('.studio-inspector-heading button').trigger('click')
    await flushPromises()
    expect(setImageJobFavorite).toHaveBeenCalledWith('job-1', true)
  })
})
