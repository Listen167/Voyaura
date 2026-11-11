import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { uploadMediaFile } from './client'
import type { MediaUploadIntent } from '../types'

class FakeXMLHttpRequest {
  static latest: FakeXMLHttpRequest | null = null

  upload: { onprogress: ((event: ProgressEvent) => void) | null } = { onprogress: null }
  onload: (() => void) | null = null
  onerror: (() => void) | null = null
  onabort: (() => void) | null = null
  status = 0
  headers: Record<string, string> = {}
  body: XMLHttpRequestBodyInit | null = null

  constructor() {
    FakeXMLHttpRequest.latest = this
  }

  open(_method: string, _url: string) {}

  setRequestHeader(name: string, value: string) {
    this.headers[name] = value
  }

  send(body: XMLHttpRequestBodyInit | null) {
    this.body = body
  }

  abort() {
    this.onabort?.()
  }
}

const intent: MediaUploadIntent = {
  status: 'created',
  asset_id: 'asset-1',
  upload_url: 'http://storage.test/private-object',
  method: 'PUT',
  required_headers: { 'Content-Type': 'image/jpeg' },
  expires_at: '2026-11-11T12:00:00Z',
}

describe('uploadMediaFile', () => {
  beforeEach(() => {
    FakeXMLHttpRequest.latest = null
    vi.stubGlobal('XMLHttpRequest', FakeXMLHttpRequest)
  })

  afterEach(() => vi.unstubAllGlobals())

  it('reports byte progress and resolves a successful MinIO PUT', async () => {
    const onProgress = vi.fn()
    const file = new File(['0123456789'], 'camera.jpg', { type: 'image/jpeg' })
    const result = uploadMediaFile(intent, file, { onProgress })
    const xhr = FakeXMLHttpRequest.latest
    expect(xhr).not.toBeNull()

    xhr?.upload.onprogress?.({
      lengthComputable: true,
      loaded: 5,
      total: 10,
    } as ProgressEvent)
    if (xhr) xhr.status = 200
    xhr?.onload?.()

    await expect(result).resolves.toBeUndefined()
    expect(onProgress).toHaveBeenNthCalledWith(1, { loaded: 5, total: 10, percent: 50 })
    expect(onProgress).toHaveBeenLastCalledWith({ loaded: 10, total: 10, percent: 100 })
    expect(xhr?.headers['Content-Type']).toBe('image/jpeg')
    expect(xhr?.body).toBe(file)
  })

  it('aborts the underlying upload through AbortController', async () => {
    const controller = new AbortController()
    const file = new File(['photo'], 'camera.jpg', { type: 'image/jpeg' })
    const result = uploadMediaFile(intent, file, { signal: controller.signal })

    controller.abort()

    await expect(result).rejects.toMatchObject({
      code: 'MEDIA_UPLOAD_CANCELLED',
      retryable: true,
    })
  })

  it('returns a stable error when object storage rejects the PUT', async () => {
    const file = new File(['photo'], 'camera.jpg', { type: 'image/jpeg' })
    const result = uploadMediaFile(intent, file)
    const xhr = FakeXMLHttpRequest.latest
    if (xhr) xhr.status = 403
    xhr?.onload?.()

    await expect(result).rejects.toMatchObject({
      code: 'MEDIA_DIRECT_UPLOAD_FAILED',
      details: { status: 403 },
      retryable: false,
    })
  })
})
