import { getOwnerUsername } from './session'
import type {
  CityMemoryConfirmResult,
  CityMemoryDeleteConfirmResult,
  CityMemoryDeleteDraft,
  CityMemoryDeletePreview,
  CityMemoryDetail,
  CityMemoryDraft,
  CityMemoryPreview,
  CityMemoryUpdateConfirmResult,
  CityMemoryUpdatePreview,
} from '../types'
import { request } from './http'

export function getCityMemories(
  adcode: string,
  username = getOwnerUsername(),
): Promise<CityMemoryDetail> {
  return request(
    `/cities/${encodeURIComponent(adcode)}/memories?username=${encodeURIComponent(username)}`,
  )
}

export function previewCityMemory(
  adcode: string,
  payload: CityMemoryDraft,
): Promise<CityMemoryPreview> {
  return request(`/cities/${encodeURIComponent(adcode)}/memories/preview`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function confirmCityMemory(
  adcode: string,
  payload: CityMemoryDraft,
): Promise<CityMemoryConfirmResult> {
  return request(`/cities/${encodeURIComponent(adcode)}/memories/confirm`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function previewCityMemoryUpdate(
  adcode: string,
  memoryId: string,
  payload: CityMemoryDraft,
): Promise<CityMemoryUpdatePreview> {
  return request(
    `/cities/${encodeURIComponent(adcode)}/memories/${encodeURIComponent(memoryId)}/update-preview`,
    { method: 'POST', body: JSON.stringify(payload) },
  )
}

export function confirmCityMemoryUpdate(
  adcode: string,
  memoryId: string,
  payload: CityMemoryDraft,
): Promise<CityMemoryUpdateConfirmResult> {
  return request(
    `/cities/${encodeURIComponent(adcode)}/memories/${encodeURIComponent(memoryId)}/update-confirm`,
    { method: 'POST', body: JSON.stringify(payload) },
  )
}

export function previewCityMemoryDelete(
  adcode: string,
  memoryId: string,
  payload: CityMemoryDeleteDraft,
): Promise<CityMemoryDeletePreview> {
  return request(
    `/cities/${encodeURIComponent(adcode)}/memories/${encodeURIComponent(memoryId)}/delete-preview`,
    { method: 'POST', body: JSON.stringify(payload) },
  )
}

export function confirmCityMemoryDelete(
  adcode: string,
  memoryId: string,
  payload: CityMemoryDeleteDraft,
): Promise<CityMemoryDeleteConfirmResult> {
  return request(
    `/cities/${encodeURIComponent(adcode)}/memories/${encodeURIComponent(memoryId)}/delete-confirm`,
    { method: 'POST', body: JSON.stringify(payload) },
  )
}
