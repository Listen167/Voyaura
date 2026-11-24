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

const planningCapability = {
  provider: 'deepseek', model: 'deepseek-chat', available: true,
  state: 'available', structured_output: true,
  notice: 'DeepSeek 已配置。',
}

const planningPreview = {
  status: 'ready_for_poi_search',
  assistant_message: '我先整理杭州三天的摄影候选，再交给高德核验。',
  requirements: {
    city_name: '杭州市', day_count: 3, party_type: 'solo', pace: 'relaxed',
    interests: ['摄影'], must_visit_names: [], avoid_names: [],
    dietary_constraints: [], transport_modes: ['transit'],
    daily_start_time: null, daily_end_time: null, total_budget_yuan: null,
  },
  city_adcode: null,
  missing_fields: [],
  clarification_questions: [],
  candidate_target_count: 30,
  recommended_daily_attractions: { min: 2, max: 3 },
  attraction_hypotheses: [{
    name: '西湖风景名胜区', category: 'photography',
    reason: '适合作为摄影主题候选，具体信息待核验。', priority: 5,
  }],
  search_themes: [{
    keyword: '杭州 摄影景点', category: 'photography',
    reason: '扩展摄影地点。', desired_count: 10,
  }],
  assumptions: [],
  warnings: ['模型建议仅用于候选检索，不代表地点已存在或适合最终行程。'],
  provider: 'deepseek', model: 'deepseek-chat', generated_at: '2026-11-13T06:00:00Z',
}

function jsonResponse(payload: unknown) {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

afterEach(() => vi.unstubAllGlobals())

describe('JourneyPlannerView', () => {
  it('builds a truthful planning draft before AMap verification', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/tools/routes/capabilities')) return jsonResponse(capabilities)
      if (url.endsWith('/xiaoxi/planning/capability')) return jsonResponse(planningCapability)
      if (url.endsWith('/xiaoxi/planning/preview')) return jsonResponse(planningPreview)
      throw new Error(`Unexpected URL: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)
    const wrapper = mount(JourneyPlannerView, { props: { overview } })
    await flushPromises()

    expect(wrapper.text()).toContain('智能规划')
    expect(wrapper.text()).toContain('DeepSeek 就绪')
    await wrapper.get('[aria-label="描述旅行需求"]').setValue('杭州三天，独自摄影')
    await wrapper.get('.planning-request-form').trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('杭州市 · 3 天')
    expect(wrapper.text()).toContain('候选池目标')
    expect(wrapper.text()).toContain('西湖风景名胜区')
    expect(wrapper.text()).toContain('待核验')
    expect(wrapper.text()).toContain('区域尚未分配')
    expect(wrapper.findAll('.planning-day-list article')).toHaveLength(3)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/xiaoxi/planning/preview',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('keeps licensed intercity providers and the sourced local route tool', async () => {
    const routeResult = {
      mode: 'driving',
      origin: { longitude: 113.2644, latitude: 23.1291 },
      destination: { longitude: 108.9398, latitude: 34.3416 },
      coordinate_system: 'GCJ02', provider: 'amap', queried_at: '2026-11-12T06:01:00Z',
      options: [{
        distance_meters: 1600000, duration_seconds: 72000,
        walking_distance_meters: null, tolls_yuan: 620, taxi_cost_yuan: null,
        steps: [{
          instruction: '沿高速公路向西北行驶', distance_meters: 1600000,
          duration_seconds: 72000, road_name: null, transport: 'driving',
        }],
      }],
    }
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/tools/routes/capabilities')) return jsonResponse(capabilities)
      if (url.endsWith('/xiaoxi/planning/capability')) return jsonResponse(planningCapability)
      if (url.endsWith('/tools/routes/plan')) return jsonResponse(routeResult)
      throw new Error(`Unexpected URL: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)
    const wrapper = mount(JourneyPlannerView, { props: { overview } })
    await flushPromises()

    await wrapper.get('[role="tab"][aria-selected="false"]').trigger('click')
    expect(wrapper.text()).toContain('高铁 / 动车')
    expect(wrapper.text()).toContain('待合作方授权')
    await wrapper.get('.route-query-form').trigger('submit')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/tools/routes/plan',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(wrapper.text()).toContain('20 小时')
    expect(wrapper.text()).toContain('1600.0 公里')
    expect(wrapper.text()).toContain('¥620')
  })
})
