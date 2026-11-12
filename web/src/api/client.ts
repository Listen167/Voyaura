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
  ImageJob,
  ImageJobCreateDraft,
  ImageJobCreateResult,
  ImageJobDeleteDraft,
  ImageJobDeletePreview,
  ImageJobDeleteResult,
  ImageJobDraft,
  ImageJobList,
  ImageJobPreview,
  ImageStyleCatalog,
  MediaDeleteConfirmResult,
  MediaDeleteDraft,
  MediaDeletePreview,
  MediaProcessingStatus,
  MediaTaskList,
  MediaUploadCompleteResult,
  MediaUploadDraft,
  MediaUploadIntent,
  MediaUploadPreview,
  MediaUploadProgress,
  PoiDetailResult,
  PoiSearchDraft,
  PoiSearchResult,
  LocalRouteDraft,
  LocalRouteResult,
  RouteCapabilities,
} from '../types'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8001/api/v1'

export const emptyOverview: MapOverview = {
  username: 'AuroraRovella',
  map_center: [104.1954, 35.8617],
  default_zoom: 4.7,
  stats: { lit_cities: 0, memories: 0, photos: 0, vlog_minutes: 0 },
  visited_cities: [],
  year_summaries: [],
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

export function searchPois(payload: PoiSearchDraft): Promise<PoiSearchResult> {
  return request('/tools/poi/search', { method: 'POST', body: JSON.stringify(payload) })
}

export function getPoiDetail(poiId: string): Promise<PoiDetailResult> {
  return request(`/tools/poi/${encodeURIComponent(poiId)}`)
}

export function getRouteCapabilities(): Promise<RouteCapabilities> {
  return request('/tools/routes/capabilities')
}

export function planLocalRoute(payload: LocalRouteDraft): Promise<LocalRouteResult> {
  return request('/tools/routes/plan', { method: 'POST', body: JSON.stringify(payload) })
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

interface MediaUploadOptions {
  signal?: AbortSignal
  onProgress?: (progress: MediaUploadProgress) => void
}

export function uploadMediaFile(
  intent: MediaUploadIntent,
  file: File,
  options: MediaUploadOptions = {},
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    const rejectWith = (info: AppErrorInfo) => reject(new ApiClientError(info))
    const abortUpload = () => xhr.abort()
    const removeAbortListener = () => options.signal?.removeEventListener('abort', abortUpload)

    if (options.signal?.aborted) {
      rejectWith({
        code: 'MEDIA_UPLOAD_CANCELLED',
        message: '上传已取消。',
        details: {},
        retryable: true,
      })
      return
    }

    try {
      xhr.open(intent.method, intent.upload_url)
      Object.entries(intent.required_headers).forEach(([name, value]) => {
        xhr.setRequestHeader(name, value)
      })
    } catch {
      rejectWith({
        code: 'MEDIA_DIRECT_UPLOAD_NETWORK_ERROR',
        message: '无法建立对象存储上传连接，请检查签名地址。',
        details: {},
        retryable: true,
      })
      return
    }

    xhr.upload.onprogress = (event) => {
      const total = event.lengthComputable && event.total > 0 ? event.total : file.size
      const loaded = Math.min(event.loaded, total)
      options.onProgress?.({
        loaded,
        total,
        percent: total > 0 ? Math.min(100, Math.round((loaded / total) * 100)) : 0,
      })
    }
    xhr.onload = () => {
      removeAbortListener()
      if (xhr.status >= 200 && xhr.status < 300) {
        options.onProgress?.({ loaded: file.size, total: file.size, percent: 100 })
        resolve()
        return
      }
      rejectWith({
        code: 'MEDIA_DIRECT_UPLOAD_FAILED',
        message: '对象存储拒绝了文件上传。',
        details: { status: xhr.status },
        retryable: xhr.status >= 500,
      })
    }
    xhr.onerror = () => {
      removeAbortListener()
      rejectWith({
        code: 'MEDIA_DIRECT_UPLOAD_NETWORK_ERROR',
        message: '无法连接对象存储，请检查 MinIO 和网络后重试。',
        details: {},
        retryable: true,
      })
    }
    xhr.onabort = () => {
      removeAbortListener()
      rejectWith({
        code: 'MEDIA_UPLOAD_CANCELLED',
        message: '上传已取消。',
        details: {},
        retryable: true,
      })
    }
    options.signal?.addEventListener('abort', abortUpload, { once: true })
    xhr.send(file)
  })
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

export function getMediaProcessingStatus(
  adcode: string,
  memoryId: string,
  assetId: string,
  username = 'AuroraRovella',
): Promise<MediaProcessingStatus> {
  const params = new URLSearchParams({ username })
  return request(
    `/cities/${encodeURIComponent(adcode)}/memories/${encodeURIComponent(memoryId)}/media/${encodeURIComponent(assetId)}/status?${params.toString()}`,
  )
}

export function getCityMediaTasks(
  adcode: string,
  username = 'AuroraRovella',
): Promise<MediaTaskList> {
  const params = new URLSearchParams({ username })
  return request(`/cities/${encodeURIComponent(adcode)}/media/tasks?${params.toString()}`)
}

export function previewMediaDelete(
  adcode: string,
  memoryId: string,
  assetId: string,
  payload: MediaDeleteDraft,
): Promise<MediaDeletePreview> {
  return request(
    `/cities/${encodeURIComponent(adcode)}/memories/${encodeURIComponent(memoryId)}/media/${encodeURIComponent(assetId)}/delete-preview`,
    { method: 'POST', body: JSON.stringify(payload) },
  )
}

export function confirmMediaDelete(
  adcode: string,
  memoryId: string,
  assetId: string,
  payload: MediaDeleteDraft,
): Promise<MediaDeleteConfirmResult> {
  return request(
    `/cities/${encodeURIComponent(adcode)}/memories/${encodeURIComponent(memoryId)}/media/${encodeURIComponent(assetId)}/delete-confirm`,
    { method: 'POST', body: JSON.stringify(payload) },
  )
}

export function getImageStyles(): Promise<ImageStyleCatalog> {
  return request('/image-styles')
}

export function previewImageJob(payload: ImageJobDraft): Promise<ImageJobPreview> {
  return request('/image-jobs/preview', { method: 'POST', body: JSON.stringify(payload) })
}

export function createImageJob(payload: ImageJobCreateDraft): Promise<ImageJobCreateResult> {
  return request('/image-jobs', { method: 'POST', body: JSON.stringify(payload) })
}

export function getImageJob(
  jobId: string,
  username = 'AuroraRovella',
): Promise<ImageJob> {
  const params = new URLSearchParams({ username })
  return request(`/image-jobs/${encodeURIComponent(jobId)}?${params.toString()}`)
}

export function getImageJobs(
  username = 'AuroraRovella',
  favoriteOnly = false,
): Promise<ImageJobList> {
  const params = new URLSearchParams({ username, favorite_only: String(favoriteOnly) })
  return request(`/image-jobs?${params.toString()}`)
}

export function setImageJobFavorite(
  jobId: string,
  favorite: boolean,
  username = 'AuroraRovella',
): Promise<ImageJob> {
  return request(`/image-jobs/${encodeURIComponent(jobId)}/favorite`, {
    method: 'POST',
    body: JSON.stringify({ username, favorite }),
  })
}

export function previewImageJobDelete(
  jobId: string,
  payload: ImageJobDeleteDraft,
): Promise<ImageJobDeletePreview> {
  return request(`/image-jobs/${encodeURIComponent(jobId)}/delete-preview`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function confirmImageJobDelete(
  jobId: string,
  payload: ImageJobDeleteDraft,
): Promise<ImageJobDeleteResult> {
  return request(`/image-jobs/${encodeURIComponent(jobId)}/delete-confirm`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
