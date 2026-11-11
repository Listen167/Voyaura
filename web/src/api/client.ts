import type {
  AppErrorInfo,
  CityMemoryDetail,
  CityMemoryDeleteConfirmResult,
  CityMemoryDeleteDraft,
  CityMemoryDeletePreview,
  CityMemoryDraft,
  CityMemoryPreview,
  CityMemoryConfirmResult,
  CityMemoryUpdateConfirmResult,
  CityMemoryUpdatePreview,
  CheckInConfirmResult,
  CheckInCoordinates,
  CheckInPreview,
  ManualCityCheckIn,
  MapOverview,
  MediaUploadCompleteResult,
  MediaUploadDraft,
  MediaUploadIntent,
  MediaUploadPreview,
} from '../types'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8001/api/v1'

export const emptyOverview: MapOverview = {
  username: 'AuroraRovella',
  map_center: [104.1954, 35.8617],
  default_zoom: 4.7,
  stats: { lit_cities: 0, memories: 0, photos: 0, vlog_minutes: 0 },
  visited_cities: [],
}

interface ApiErrorEnvelope {
  error?: {
    code?: string
    message?: string
    details?: Record<string, unknown>
    retryable?: boolean
    request_id?: string
  }
}

export class ApiClientError extends Error implements AppErrorInfo {
  code: string
  details: Record<string, unknown>
  retryable: boolean
  requestId?: string

  constructor(info: AppErrorInfo) {
    super(info.message)
    this.name = 'ApiClientError'
    this.code = info.code
    this.details = info.details
    this.retryable = info.retryable
    this.requestId = info.requestId
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new ApiClientError({
      code: 'API_NETWORK_ERROR',
      message: '无法连接 Voyaura 服务。',
      details: { api_base_url: apiBaseUrl },
      retryable: true,
    })
  }

  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as ApiErrorEnvelope
    throw new ApiClientError({
      code: payload.error?.code ?? `HTTP_${response.status}`,
      message: payload.error?.message ?? '服务返回了无法识别的错误。',
      details: payload.error?.details ?? {},
      retryable: payload.error?.retryable ?? response.status >= 500,
      requestId: payload.error?.request_id ?? response.headers.get('X-Request-ID') ?? undefined,
    })
  }
  return response.json() as Promise<T>
}

export function getMapOverview(username = 'AuroraRovella'): Promise<MapOverview> {
  return request(`/map/overview?username=${encodeURIComponent(username)}`)
}

export function previewCheckIn(payload: CheckInCoordinates): Promise<CheckInPreview> {
  return request('/check-ins/preview', { method: 'POST', body: JSON.stringify(payload) })
}

export function confirmCheckIn(payload: CheckInCoordinates): Promise<CheckInConfirmResult> {
  return request('/check-ins/confirm', { method: 'POST', body: JSON.stringify(payload) })
}

export function previewManualCheckIn(payload: ManualCityCheckIn): Promise<CheckInPreview> {
  return request('/check-ins/manual-preview', { method: 'POST', body: JSON.stringify(payload) })
}

export function confirmManualCheckIn(payload: ManualCityCheckIn): Promise<CheckInConfirmResult> {
  return request('/check-ins/manual-confirm', { method: 'POST', body: JSON.stringify(payload) })
}

export function getCityMemories(
  adcode: string,
  username = 'AuroraRovella',
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

export function previewMediaUpload(
  adcode: string,
  memoryId: string,
  payload: MediaUploadDraft,
): Promise<MediaUploadPreview> {
  return request(
    `/cities/${encodeURIComponent(adcode)}/memories/${encodeURIComponent(memoryId)}/media/upload-preview`,
    { method: 'POST', body: JSON.stringify(payload) },
  )
}

export function createMediaUploadIntent(
  adcode: string,
  memoryId: string,
  payload: MediaUploadDraft,
): Promise<MediaUploadIntent> {
  return request(
    `/cities/${encodeURIComponent(adcode)}/memories/${encodeURIComponent(memoryId)}/media/upload-intents`,
    { method: 'POST', body: JSON.stringify(payload) },
  )
}

export async function uploadMediaFile(intent: MediaUploadIntent, file: File): Promise<void> {
  let response: Response
  try {
    response = await fetch(intent.upload_url, {
      method: intent.method,
      headers: intent.required_headers,
      body: file,
    })
  } catch {
    throw new ApiClientError({
      code: 'MEDIA_DIRECT_UPLOAD_NETWORK_ERROR',
      message: '无法连接对象存储，请检查 MinIO 和网络后重试。',
      details: {},
      retryable: true,
    })
  }
  if (!response.ok) {
    throw new ApiClientError({
      code: 'MEDIA_DIRECT_UPLOAD_FAILED',
      message: '对象存储拒绝了文件上传。',
      details: { status: response.status },
      retryable: response.status >= 500,
    })
  }
}

export function completeMediaUpload(
  adcode: string,
  memoryId: string,
  assetId: string,
  username = 'AuroraRovella',
): Promise<MediaUploadCompleteResult> {
  return request(
    `/cities/${encodeURIComponent(adcode)}/memories/${encodeURIComponent(memoryId)}/media/${encodeURIComponent(assetId)}/complete`,
    { method: 'POST', body: JSON.stringify({ username }) },
  )
}
