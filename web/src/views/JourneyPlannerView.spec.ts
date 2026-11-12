import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { MapOverview } from '../types'
import JourneyPlannerView from './JourneyPlannerView.vue'

const overview: MapOverview = {
  username: 'AuroraRovella',
  map_center: [104.1954, 35.8617],
  default_zoom: 4.7,
  stats: { lit_cities: 2, memories: 0, photos: 0, vlog_minutes: 0 },
  visited_cities: [
    {
      adcode: '440100', name_zh: '广州市', name_en: 'Guangzhou', province_zh: '广东省',
      longitude: 113.2644, latitude: 23.1291, first_visited_at: '2026-01-01T00:00:00Z',
      last_visited_at: '2026-01-01T00:00:00Z', memory_count: 0, check_in_source: 'manual',
    },
    {
      adcode: '610100', name_zh: '西安市', name_en: "Xi'an", province_zh: '陕西省',
      longitude: 108.9398, latitude: 34.3416, first_visited_at: '2026-02-01T00:00:00Z',
      last_visited_at: '2026-02-01T00:00:00Z', memory_count: 0, check_in_source: 'manual',
    },
  ],
  year_summaries: [],
}

const capabilities = {
  local: [],
  intercity: [
    {
      mode: 'high_speed_rail', provider: 'licensed_rail_partner', available: false,
      state: 'partner_required', data_scope: ['train_number', 'price', 'availability'],
      application_url: 'https://open.ctrip.com/', notice: '需要正式合作接口。',
    },
    {
      mode: 'flight', provider: 'amadeus_or_china_licensed_partner', available: false,
      state: 'partner_required', data_scope: ['flight_number', 'fare'],
      application_url: 'https://developers.amadeus.com/', notice: '需要航班 Provider。',
    },
  ],
  queried_at: '2026-11-12T06:00:00Z',
}

afterEach(() => vi.unstubAllGlobals())

describe('JourneyPlannerView', () => {
  it('shows licensed intercity providers and submits a sourced local route', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(capabilities), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        mode: 'driving',
        origin: { longitude: 113.2644, latitude: 23.1291 },
        destination: { longitude: 108.9398, latitude: 34.3416 },
        coordinate_system: 'GCJ02',
        provider: 'amap',
        queried_at: '2026-11-12T06:01:00Z',
        options: [{
          distance_meters: 1600000,
          duration_seconds: 72000,
          walking_distance_meters: null,
          tolls_yuan: 620,
          taxi_cost_yuan: null,
          steps: [{
            instruction: '沿高速公路向西北行驶', distance_meters: 1600000,
            duration_seconds: 72000, road_name: null, transport: 'driving',
          }],
        }],
      }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(JourneyPlannerView, { props: { overview } })
    await flushPromises()

    expect(wrapper.text()).toContain('高铁 / 动车')
    expect(wrapper.text()).toContain('飞机')
    expect(wrapper.text()).toContain('待合作方授权')
    expect(wrapper.text()).toContain('正式铁路合作方')
    expect(wrapper.text()).toContain('车次')

    await wrapper.get('.route-query-form').trigger('submit')
    await flushPromises()

    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      'http://127.0.0.1:8001/api/v1/tools/routes/plan',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(wrapper.text()).toContain('20 小时')
    expect(wrapper.text()).toContain('1600.0 公里')
    expect(wrapper.text()).toContain('¥620')
  })
})
