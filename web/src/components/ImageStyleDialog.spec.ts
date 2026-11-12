import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ImageStyleDialog from './ImageStyleDialog.vue'
import type { CityMemoryItem, ImageJobPreview, ImageStyleCatalog, MemoryMediaAsset, VisitedCity } from '../types'

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

const asset: MemoryMediaAsset = {
  id: 'asset-1',
  kind: 'photo',
  original_filename: 'riverside.jpg',
  mime_type: 'image/jpeg',
  width: 1280,
  height: 960,
  duration_seconds: null,
  visibility: 'private',
  upload_status: 'ready',
  exif_status: 'removed',
  scan_status: 'clean',
  thumbnail_url: 'http://storage.test/thumb.webp',
  content_url: 'http://storage.test/source.jpg',
  thumbnail_width: 960,
  thumbnail_height: 720,
  created_at: '2026-11-10T08:00:00Z',
}

const memory: CityMemoryItem = {
  id: 'memory-1',
  title: '珠江夜色',
  body: null,
  occurred_at: '2026-11-10T08:00:00Z',
  visibility: 'private',
  media: [asset],
}

const catalog: ImageStyleCatalog = {
  provider: 'disabled',
  available: false,
  missing_settings: ['IMAGE_PROVIDER'],
  companion: {
    available: false,
    missing_settings: ['XIAOXI_PHOTO_ASSET_PATH'],
    asset_version: 'unconfigured',
    positions: ['left', 'right'],
    scales: ['small', 'medium', 'large'],
    poses: ['default'],
    expressions: ['warm'],
  },
  styles: [{
    id: 'retro_film',
    name: '复古胶片',
    description: '自然旅行底片质感',
    swatch: '#b94f3d',
    recipe: {
      version: 'voyaura-1',
      aspect_ratio: 'source',
      layout: 'full-frame photograph',
      focal_element: 'recognizable source subject',
      typography: 'none',
      color: 'warm film palette',
      texture: 'fine grain',
      default_preservation: 'balanced',
      preservation_level: null,
    },
    source: null,
  }, {
    id: 'minimal_zine_poster',
    name: '诗性纸感 Zine',
    description: '大面积留白与单一高彩色',
    swatch: '#e6572f',
    recipe: {
      version: 'minimal-zine-v0.3.1',
      aspect_ratio: '3:5',
      layout: 'off-axis micro editorial cluster',
      focal_element: 'recognizable travel-photo crop',
      typography: 'archive microtext',
      color: 'one high-chroma accent',
      texture: 'risograph grain',
      default_preservation: 'high',
      preservation_level: null,
    },
    source: {
      name: 'GC Minimal Zine Poster',
      version: '0.3.1',
      url: 'https://github.com/LiamGvchi/gc-minimal-zine-poster',
      license: 'MIT',
    },
  }],
}

describe('ImageStyleDialog', () => {
  it('collects a style draft and reports an unavailable provider', async () => {
    const wrapper = mount(ImageStyleDialog, {
      props: {
        city,
        memory,
        asset,
        catalog,
        phase: 'editing',
        preview: null,
        job: null,
        error: null,
      },
    })

    expect(wrapper.text()).toContain('图片 Provider 尚未配置')
    await wrapper.get('textarea').setValue('保留珠江塔轮廓')
    await wrapper.get('.style-caption-toggle input').setValue(true)
    await wrapper.get('input[value="vertical_stamp"]').setValue()
    await wrapper.get('input[value="forest"]').setValue()
    await wrapper.get('input[value="serif"]').setValue()
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('preview')?.[0]).toEqual([{
      style_id: 'retro_film',
      prompt: '保留珠江塔轮廓',
      negative_prompt: null,
      preservation_level: 'balanced',
      caption_mode: 'travel_stamp',
      caption_layout: 'vertical_stamp',
      caption_palette: 'forest',
      caption_font_style: 'serif',
      companion_enabled: false,
      companion_position: 'right',
      companion_scale: 'medium',
    }])
  })

  it('requires a configured provider before confirming generation', async () => {
    const preview: ImageJobPreview = {
      source_asset_id: asset.id,
      source_filename: asset.original_filename,
      city_adcode: city.adcode,
      city_name: city.name_zh,
      memory_id: memory.id,
      memory_title: memory.title,
      style: catalog.styles[0],
      recipe: { ...catalog.styles[0].recipe, preservation_level: 'balanced' },
      effective_prompt: 'retro travel film photography',
      negative_prompt: 'plastic skin',
      preservation_level: 'balanced',
      caption_mode: 'none',
      caption: null,
      companion: null,
      companion_available: false,
      companion_missing_settings: ['XIAOXI_PHOTO_ASSET_PATH'],
      provider: 'disabled',
      provider_available: false,
      confirmation_notice: '确认后交给私有 worker。',
    }
    const wrapper = mount(ImageStyleDialog, {
      props: {
        city,
        memory,
        asset,
        catalog,
        phase: 'preview',
        preview,
        job: null,
        error: null,
      },
    })

    const confirm = wrapper.get('button.primary')
    expect(confirm.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('需要先完成 ComfyUI 环境配置')
  })

  it('uses the attributed Minimal Zine recipe with high preservation by default', async () => {
    const wrapper = mount(ImageStyleDialog, {
      props: {
        city,
        memory,
        asset,
        catalog,
        phase: 'editing',
        preview: null,
        job: null,
        error: null,
      },
    })

    await wrapper.findAll('input[name="image-style"]')[1].setValue()
    await wrapper.get('form').trigger('submit')

    expect(wrapper.text()).toContain('GC Minimal Zine Poster · MIT')
    expect(wrapper.emitted('preview')?.[0]).toEqual([{
      style_id: 'minimal_zine_poster',
      prompt: '',
      negative_prompt: null,
      preservation_level: 'high',
      caption_mode: 'none',
      caption_layout: 'archive_band',
      caption_palette: 'coral',
      caption_font_style: 'sans',
      companion_enabled: false,
      companion_position: 'right',
      companion_scale: 'medium',
    }])
  })

  it('collects deterministic Xiaoxi placement when an authorized asset is available', async () => {
    const enabledCatalog: ImageStyleCatalog = {
      ...catalog,
      companion: {
        ...catalog.companion,
        available: true,
        missing_settings: [],
        asset_version: 'xiaoxi-v1',
      },
    }
    const wrapper = mount(ImageStyleDialog, {
      props: {
        city,
        memory,
        asset,
        catalog: enabledCatalog,
        phase: 'editing',
        preview: null,
        job: null,
        error: null,
      },
    })

    const toggles = wrapper.findAll('.style-caption-toggle input[type="checkbox"]')
    await toggles[1].setValue(true)
    await wrapper.get('input[value="left"]').setValue()
    await wrapper.get('input[value="large"]').setValue()
    await wrapper.get('form').trigger('submit')

    expect(wrapper.emitted('preview')?.[0]).toEqual([{
      style_id: 'retro_film',
      prompt: '',
      negative_prompt: null,
      preservation_level: 'balanced',
      caption_mode: 'none',
      caption_layout: 'archive_band',
      caption_palette: 'coral',
      caption_font_style: 'sans',
      companion_enabled: true,
      companion_position: 'left',
      companion_scale: 'large',
    }])
  })
})
