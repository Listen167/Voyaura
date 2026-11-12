import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import type { PoiSearchResult, VisitedCity } from '../types'
import PoiSearchDialog from './PoiSearchDialog.vue'

const city: VisitedCity = {
  adcode: '440100',
  name_zh: '广州市',
  name_en: 'Guangzhou',
  province_zh: '广东省',
  longitude: 113.2644,
  latitude: 23.1291,
  first_visited_at: '2026-05-01T08:00:00Z',
  last_visited_at: '2026-05-01T08:00:00Z',
  memory_count: 1,
  check_in_source: 'manual',
}

const result: PoiSearchResult = {
  keywords: '博物馆',
  city_adcode: '440100',
  total: 1,
  page: 1,
  page_size: 10,
  provider: 'amap',
  queried_at: '2026-11-12T03:00:00Z',
  items: [{
    id: 'B0TESTMUSEUM',
    name: '广州博物馆',
    category: '科教文化服务;博物馆;博物馆',
    typecode: '140100',
    address: '镇海路99号',
    province: '广东省',
    city: '广州市',
    district: '越秀区',
    adcode: '440104',
    longitude: 113.2644,
    latitude: 23.1401,
    coordinate_system: 'GCJ02',
    telephone: '020-00000000',
    rating: '4.7',
    average_cost: null,
    opening_hours: '09:00-17:00',
    navigation_url: 'https://uri.amap.com/marker?position=113.264400%2C23.140100',
  }],
}

describe('PoiSearchDialog', () => {
  it('submits a normalized search for the selected city', async () => {
    const wrapper = mount(PoiSearchDialog, {
      props: { cities: [city], phase: 'editing', result: null, error: null },
    })

    await wrapper.get('input[type="search"]').setValue('  博物馆  ')
    await wrapper.get('form').trigger('submit')

    expect(wrapper.emitted('search')?.[0]).toEqual([{
      keywords: '博物馆',
      city_adcode: '440100',
      category: '',
      page: 1,
      page_size: 10,
    }])
  })

  it('renders sourced POI details and an official navigation link', () => {
    const wrapper = mount(PoiSearchDialog, {
      props: { cities: [city], phase: 'results', result, error: null },
    })

    expect(wrapper.text()).toContain('广州博物馆')
    expect(wrapper.text()).toContain('高德 · GCJ-02')
    expect(wrapper.text()).toContain('09:00-17:00')
    const link = wrapper.get('.poi-search-results a')
    expect(link.attributes('href')).toBe(result.items[0].navigation_url)
    expect(link.attributes('target')).toBe('_blank')
  })

  it('shows the actionable AMap signature error and request id', () => {
    const wrapper = mount(PoiSearchDialog, {
      props: {
        cities: [city],
        phase: 'error',
        result: null,
        error: {
          code: 'AMAP_INVALID_SIGNATURE',
          message: '高德 Web 服务签名验证失败。',
          details: { provider_infocode: '10007' },
          retryable: false,
          requestId: 'request-poi-10007',
        },
      },
    })

    expect(wrapper.text()).toContain('关闭 Web 服务 Key 的数字签名')
    expect(wrapper.text()).toContain('request-poi-10007')
  })
})
