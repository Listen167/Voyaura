import { getOwnerUsername } from './session'
import type {
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
} from '../types'
import { request } from './http'

export function getImageStyles(): Promise<ImageStyleCatalog> {
  return request('/image-styles')
}

export function previewImageJob(payload: ImageJobDraft): Promise<ImageJobPreview> {
  return request('/image-jobs/preview', { method: 'POST', body: JSON.stringify(payload) })
}

export function createImageJob(payload: ImageJobCreateDraft): Promise<ImageJobCreateResult> {
  return request('/image-jobs', { method: 'POST', body: JSON.stringify(payload) })
}

export function getImageJob(jobId: string, username = getOwnerUsername()): Promise<ImageJob> {
  const params = new URLSearchParams({ username })
  return request(`/image-jobs/${encodeURIComponent(jobId)}?${params.toString()}`)
}

export function getImageJobs(
  username = getOwnerUsername(),
  favoriteOnly = false,
): Promise<ImageJobList> {
  const params = new URLSearchParams({ username, favorite_only: String(favoriteOnly) })
  return request(`/image-jobs?${params.toString()}`)
}

export function setImageJobFavorite(
  jobId: string,
  favorite: boolean,
  username = getOwnerUsername(),
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
