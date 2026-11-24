import { getOwnerUsername } from './session'
import type {
  AppErrorInfo,
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
} from '../types'
import { ApiClientError, request } from './http'

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

export interface MediaUploadOptions {
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
  username = getOwnerUsername(),
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
  username = getOwnerUsername(),
): Promise<MediaProcessingStatus> {
  const params = new URLSearchParams({ username })
  return request(
    `/cities/${encodeURIComponent(adcode)}/memories/${encodeURIComponent(memoryId)}/media/${encodeURIComponent(assetId)}/status?${params.toString()}`,
  )
}

export function getCityMediaTasks(
  adcode: string,
  username = getOwnerUsername(),
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
