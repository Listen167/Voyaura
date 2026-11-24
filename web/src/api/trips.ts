import { getOwnerUsername } from './session'
import type { TripCreateDraft, TripCreateResult, TripDetail, TripList, TripStatus } from '../types'
import { request } from './http'

export function createTrip(payload: TripCreateDraft): Promise<TripCreateResult> {
  return request('/trips', { method: 'POST', body: JSON.stringify(payload) })
}

export function getTrips(
  username = getOwnerUsername(),
  options: { status?: TripStatus; limit?: number; offset?: number } = {},
): Promise<TripList> {
  const params = new URLSearchParams({
    username,
    limit: String(options.limit ?? 20),
    offset: String(options.offset ?? 0),
  })
  if (options.status) params.set('status', options.status)
  return request(`/trips?${params.toString()}`)
}

export function getTrip(tripId: string, username = getOwnerUsername()): Promise<TripDetail> {
  const params = new URLSearchParams({ username })
  return request(`/trips/${encodeURIComponent(tripId)}?${params.toString()}`)
}
