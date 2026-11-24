import { getOwnerUsername } from './session'
import type { MapOverview } from '../types'
import { request } from './http'

export const emptyOverview: MapOverview = {
  username: 'AuroraRovella',
  map_center: [104.1954, 35.8617],
  default_zoom: 4.7,
  stats: { lit_cities: 0, memories: 0, photos: 0, vlog_minutes: 0 },
  visited_cities: [],
  year_summaries: [],
}

export function getMapOverview(username = getOwnerUsername()): Promise<MapOverview> {
  return request(`/map/overview?username=${encodeURIComponent(username)}`)
}
