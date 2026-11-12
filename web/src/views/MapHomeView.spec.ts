import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { describe, expect, it } from 'vitest'
import type { MapOverview } from '../types'
import MapHomeView from './MapHomeView.vue'

const ChinaMapStub = defineComponent({
  name: 'ChinaMapCanvas',
  props: {
    overview: { type: Object, required: true },
    focusPoint: { type: Array, default: null },
  },
  template: '<div class="china-map-stub"></div>',
})

const overview: MapOverview = {
  username: 'AuroraRovella',
  map_center: [104.1954, 35.8617],
  default_zoom: 4.7,
  stats: { lit_cities: 2, memories: 3, photos: 2, vlog_minutes: 4 },
  visited_cities: [
    {
      adcode: '440100',
      name_zh: '广州市',
      name_en: 'Guangzhou',
      province_zh: '广东省',
      longitude: 113.2644,
      latitude: 23.1291,
      first_visited_at: '2024-05-01T08:00:00Z',
      last_visited_at: '2026-05-01T08:00:00Z',
      memory_count: 2,
      check_in_source: 'device',
    },
    {
      adcode: '610100',
      name_zh: '西安市',
      name_en: "Xi'an",
      province_zh: '陕西省',
      longitude: 108.9398,
      latitude: 34.3416,
      first_visited_at: '2025-04-01T08:00:00Z',
      last_visited_at: '2025-04-01T08:00:00Z',
      memory_count: 1,
      check_in_source: 'manual',
    },
  ],
  year_summaries: [
    {
      year: 2026,
      stats: { lit_cities: 1, memories: 1, photos: 1, vlog_minutes: 0 },
      cities: [{ adcode: '440100', memory_count: 1 }],
    },
    {
      year: 2025,
      stats: { lit_cities: 1, memories: 1, photos: 0, vlog_minutes: 4 },
      cities: [{ adcode: '610100', memory_count: 1 }],
    },
    {
      year: 2024,
      stats: { lit_cities: 1, memories: 1, photos: 1, vlog_minutes: 0 },
      cities: [{ adcode: '440100', memory_count: 1 }],
    },
  ],
}

describe('MapHomeView', () => {
  it('opens city POI search from the map', async () => {
    const wrapper = mount(MapHomeView, {
      props: {
        overview,
        apiConnected: true,
        focusPoint: null,
        checkInBusy: false,
      },
      global: { stubs: { ChinaMapCanvas: ChinaMapStub } },
    })

    await wrapper.get('.poi-search-entry').trigger('click')

    expect(wrapper.emitted('searchPoi')).toHaveLength(1)
  })

  it('filters map cities and footprint statistics by year', async () => {
    const wrapper = mount(MapHomeView, {
      props: {
        overview,
        apiConnected: true,
        focusPoint: null,
        checkInBusy: false,
      },
      global: { stubs: { ChinaMapCanvas: ChinaMapStub } },
    })

    expect(wrapper.get('#journey-summary-title').text()).toBe('我的中国旅程')
    expect(wrapper.findAll('.stats-grid strong').map((item) => item.text())).toEqual([
      '2', '3', '2', '4',
    ])

    await wrapper.get('button[data-year="2025"]').trigger('click')

    expect(wrapper.get('#journey-summary-title').text()).toBe('2025 年旅程')
    expect(wrapper.findAll('.stats-grid strong').map((item) => item.text())).toEqual([
      '1', '1', '0', '4',
    ])
    const mapOverview = wrapper.findComponent(ChinaMapStub).props('overview') as MapOverview
    expect(mapOverview.visited_cities.map((city) => city.adcode)).toEqual(['610100'])
    expect(mapOverview.visited_cities[0].memory_count).toBe(1)

    await wrapper.get('button[data-year="all"]').trigger('click')
    expect(wrapper.findComponent(ChinaMapStub).props('overview')).toEqual(overview)
  })
})
