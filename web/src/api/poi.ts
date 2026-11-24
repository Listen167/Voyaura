import type { PoiDetailResult, PoiSearchDraft, PoiSearchResult } from '../types'
import { request } from './http'

export function searchPois(payload: PoiSearchDraft): Promise<PoiSearchResult> {
  return request('/tools/poi/search', { method: 'POST', body: JSON.stringify(payload) })
}

export function searchAttractions(payload: PoiSearchDraft): Promise<PoiSearchResult> {
  return request('/agent/attractions/search', { method: 'POST', body: JSON.stringify(payload) })
}

export function getPoiDetail(poiId: string): Promise<PoiDetailResult> {
  return request(`/tools/poi/${encodeURIComponent(poiId)}`)
}
