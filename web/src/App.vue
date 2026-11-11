<script setup lang="ts">
import { Bell, MessageCircle, Send, Sparkles, X } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import {
  ApiClientError,
  confirmCheckIn,
  confirmCityMemory,
  confirmCityMemoryDelete,
  confirmCityMemoryUpdate,
  confirmMediaDelete,
  completeMediaUpload,
  confirmManualCheckIn,
  createMediaUploadIntent,
  emptyOverview,
  getCityMemories,
  getCityMediaTasks,
  getMediaProcessingStatus,
  getMapOverview,
  previewCheckIn,
  previewCityMemory,
  previewCityMemoryDelete,
  previewCityMemoryUpdate,
  previewMediaUpload,
  previewManualCheckIn,
  previewMediaDelete,
  uploadMediaFile,
} from './api/client'
import AppNavigation from './components/AppNavigation.vue'
import CheckInDialog from './components/CheckInDialog.vue'
import CityMemoryPanel from './components/CityMemoryPanel.vue'
import MemoryComposerDialog from './components/MemoryComposerDialog.vue'
import MemoryDeleteDialog from './components/MemoryDeleteDialog.vue'
import MediaDeleteDialog from './components/MediaDeleteDialog.vue'
import MediaUploadDialog from './components/MediaUploadDialog.vue'
import { locateCityByIp, searchCities } from './location/amapCity'
import type {
  AppErrorInfo,
  AppView,
  CheckInCoordinates,
  CheckInPreview,
  CityCandidate,
  CityMemoryDeleteDraft,
  CityMemoryDeletePreview,
  CityMemoryDetail,
  CityMemoryDraft,
  CityMemoryItem,
  CityMemoryPreview,
  CityMemoryUpdatePreview,
  ManualCityCheckIn,
  MapOverview,
  MediaDeleteDraft,
  MediaDeletePreview,
  MediaTaskItem,
  MediaUploadDraft,
  MediaUploadIntent,
  MediaUploadPreview,
  MediaUploadProgress,
  MemoryMediaAsset,
  NewMemoryInput,
  VisitedCity,
} from './types'
import EmptyView from './views/EmptyView.vue'
import MapHomeView from './views/MapHomeView.vue'

const activeView = ref<AppView>('map')
const overview = ref<MapOverview>(emptyOverview)
const apiConnected = ref(false)
const xiaoxiOpen = ref(false)
const composer = ref('')
const checkInPhase = ref<'idle' | 'locating' | 'manual' | 'preview' | 'confirming' | 'success' | 'error'>('idle')
const checkInPayload = ref<CheckInCoordinates | ManualCityCheckIn | null>(null)
const checkInPreview = ref<CheckInPreview | null>(null)
const checkInError = ref<AppErrorInfo | null>(null)
const locationMode = ref<'device-high' | 'device-fallback' | 'ip'>('device-high')
const manualResults = ref<CityCandidate[]>([])
const manualBusy = ref(false)
const manualError = ref<AppErrorInfo | null>(null)
const focusPoint = ref<[number, number] | null>(null)
const selectedCity = ref<VisitedCity | null>(null)
const cityMemoryPhase = ref<'loading' | 'ready' | 'error'>('loading')
const cityMemoryDetail = ref<CityMemoryDetail | null>(null)
const cityMemoryError = ref<AppErrorInfo | null>(null)
const cityMediaTasks = ref<MediaTaskItem[]>([])
const mediaTaskBusyId = ref<string | null>(null)
const mediaTaskError = ref<AppErrorInfo | null>(null)
const memoryComposerCity = ref<VisitedCity | null>(null)
const memoryComposerMode = ref<'create' | 'edit'>('create')
const memoryTarget = ref<CityMemoryItem | null>(null)
const memoryComposerPhase = ref<'editing' | 'preview' | 'saving' | 'success' | 'error'>('editing')
const memoryDraft = ref<CityMemoryDraft | null>(null)
const memoryPreview = ref<CityMemoryPreview | CityMemoryUpdatePreview | null>(null)
const memoryError = ref<AppErrorInfo | null>(null)
const memoryDeleteCity = ref<VisitedCity | null>(null)
const memoryDeleteTarget = ref<CityMemoryItem | null>(null)
const memoryDeletePhase = ref<'loading' | 'preview' | 'deleting' | 'success' | 'error'>('loading')
const memoryDeleteDraft = ref<CityMemoryDeleteDraft | null>(null)
const memoryDeletePreview = ref<CityMemoryDeletePreview | null>(null)
const memoryDeleteError = ref<AppErrorInfo | null>(null)
const mediaDeleteCity = ref<VisitedCity | null>(null)
const mediaDeleteTarget = ref<{ memoryId: string, assetId: string } | null>(null)
const mediaDeletePhase = ref<'loading' | 'preview' | 'deleting' | 'success' | 'error'>('loading')
const mediaDeleteDraft = ref<MediaDeleteDraft | null>(null)
const mediaDeletePreview = ref<MediaDeletePreview | null>(null)
const mediaDeleteError = ref<AppErrorInfo | null>(null)
const mediaUploadCity = ref<VisitedCity | null>(null)
const mediaUploadMemory = ref<CityMemoryItem | null>(null)
const mediaUploadPhase = ref<'selecting' | 'preview' | 'uploading' | 'processing' | 'success' | 'error'>('selecting')
const mediaUploadFile = ref<File | null>(null)
const mediaUploadDraft = ref<MediaUploadDraft | null>(null)
const mediaUploadPreview = ref<MediaUploadPreview | null>(null)
const mediaUploadIntent = ref<MediaUploadIntent | null>(null)
const mediaUploadTransferred = ref(false)
const mediaUploadCompleted = ref(false)
const mediaUploadError = ref<AppErrorInfo | null>(null)
const mediaUploadProgress = ref<MediaUploadProgress>({ loaded: 0, total: 0, percent: 0 })
let mediaUploadAbortController: AbortController | null = null
let mediaUploadPollVersion = 0
const checkInBusy = computed(() => checkInPhase.value === 'locating' || checkInPhase.value === 'confirming')

onMounted(async () => {
  try {
    overview.value = await getMapOverview()
    apiConnected.value = true
  } catch {
    apiConnected.value = false
  }
})

function localError(code: string, message: string, retryable = true): AppErrorInfo {
  return { code, message, details: {}, retryable }
}

function normalizeError(error: unknown): AppErrorInfo {
  if (error instanceof ApiClientError) return error
  return localError('UNKNOWN_CLIENT_ERROR', '发生了未识别的客户端错误。', false)
}

function geolocationError(error: GeolocationPositionError): AppErrorInfo {
  const errors: Record<number, AppErrorInfo> = {
    1: localError('LOCATION_PERMISSION_DENIED', '浏览器没有获得位置权限。', false),
    2: localError('LOCATION_UNAVAILABLE', '设备暂时无法取得当前位置。'),
    3: localError('LOCATION_TIMEOUT', '获取位置超时。'),
  }
  return errors[error.code] ?? localError('LOCATION_UNKNOWN_ERROR', error.message)
}

function isGeolocationError(error: unknown): error is GeolocationPositionError {
  return typeof error === 'object'
    && error !== null
    && 'code' in error
    && typeof error.code === 'number'
}

function getBrowserPosition(options: PositionOptions): Promise<GeolocationPosition> {
  return new Promise((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(resolve, reject, options)
  })
}

async function previewDevicePosition(position: GeolocationPosition) {
  const { coords } = position
  const payload: CheckInCoordinates = {
    username: 'AuroraRovella',
    longitude: coords.longitude,
    latitude: coords.latitude,
    accuracy_meters: Number.isFinite(coords.accuracy) ? coords.accuracy : null,
    coordinate_system: 'WGS84',
  }
  checkInPayload.value = payload
  checkInPreview.value = await previewCheckIn(payload)
  focusPoint.value = checkInPreview.value.map_position
  checkInPhase.value = 'preview'
}

async function startCheckIn() {
  checkInError.value = null
  checkInPreview.value = null
  checkInPayload.value = null
  manualError.value = null
  if (!navigator.geolocation) {
    checkInError.value = localError('LOCATION_NOT_SUPPORTED', '当前浏览器不支持位置服务。', false)
    checkInPhase.value = 'error'
    return
  }

  checkInPhase.value = 'locating'
  locationMode.value = 'device-high'
  try {
    const position = await getBrowserPosition({
      enableHighAccuracy: true,
      timeout: 12_000,
      maximumAge: 0,
    })
    await previewDevicePosition(position)
  } catch (firstError) {
    if (isGeolocationError(firstError) && firstError.code === 1) {
      checkInError.value = geolocationError(firstError)
      checkInPhase.value = 'error'
      return
    }
    if (firstError instanceof ApiClientError) {
      checkInError.value = firstError
      checkInPhase.value = 'error'
      return
    }

    locationMode.value = 'device-fallback'
    try {
      const position = await getBrowserPosition({
        enableHighAccuracy: false,
        timeout: 25_000,
        maximumAge: 300_000,
      })
      await previewDevicePosition(position)
    } catch (fallbackError) {
      checkInError.value = isGeolocationError(fallbackError)
        ? geolocationError(fallbackError)
        : normalizeError(fallbackError)
      checkInPhase.value = 'error'
    }
  }
}

function manualPayload(candidate: CityCandidate): ManualCityCheckIn {
  return { username: 'AuroraRovella', ...candidate }
}

async function previewCityCandidate(candidate: CityCandidate) {
  const payload = manualPayload(candidate)
  checkInPayload.value = payload
  checkInPreview.value = await previewManualCheckIn(payload)
  focusPoint.value = checkInPreview.value.map_position
  checkInPhase.value = 'preview'
}

async function useIpCity() {
  checkInError.value = null
  locationMode.value = 'ip'
  checkInPhase.value = 'locating'
  try {
    await previewCityCandidate(await locateCityByIp())
  } catch (error) {
    const code = error instanceof Error ? error.message : 'AMAP_IP_CITY_FAILED'
    checkInError.value = localError(
      code.startsWith('AMAP_') ? code : 'AMAP_IP_CITY_FAILED',
      '无法根据当前网络判断城市，请使用手动选城。',
    )
    checkInPhase.value = 'error'
  }
}

function openManualCitySearch() {
  manualResults.value = []
  manualError.value = null
  checkInPhase.value = 'manual'
}

async function searchManualCity(query: string) {
  manualBusy.value = true
  manualError.value = null
  try {
    manualResults.value = await searchCities(query)
    if (!manualResults.value.length) {
      manualError.value = localError('CITY_SEARCH_EMPTY', '没有找到对应城市，请输入完整城市名。', false)
    }
  } catch (error) {
    const code = error instanceof Error ? error.message : 'AMAP_CITY_SEARCH_FAILED'
    manualError.value = localError(
      code.startsWith('AMAP_') ? code : 'AMAP_CITY_SEARCH_FAILED',
      '城市搜索暂时不可用，请检查高德 JS API 配置。',
    )
  } finally {
    manualBusy.value = false
  }
}

async function selectManualCity(candidate: CityCandidate) {
  manualBusy.value = true
  manualError.value = null
  try {
    await previewCityCandidate(candidate)
  } catch (error) {
    manualError.value = normalizeError(error)
  } finally {
    manualBusy.value = false
  }
}

async function confirmCurrentCity() {
  if (!checkInPayload.value) {
    checkInError.value = localError('LOCATION_CONTEXT_LOST', '定位上下文已失效，请重新定位。')
    checkInPhase.value = 'error'
    return
  }

  checkInPhase.value = 'confirming'
  try {
    const result = 'coordinate_system' in checkInPayload.value
      ? await confirmCheckIn(checkInPayload.value)
      : await confirmManualCheckIn(checkInPayload.value)
    overview.value = await getMapOverview()
    focusPoint.value = [result.city.longitude, result.city.latitude]
    checkInPhase.value = 'success'
  } catch (error) {
    checkInError.value = normalizeError(error)
    checkInPhase.value = 'error'
  }
}

function closeCheckIn() {
  checkInPhase.value = 'idle'
  checkInError.value = null
  manualError.value = null
}

async function selectCity(city: VisitedCity) {
  focusPoint.value = [city.longitude, city.latitude]
  selectedCity.value = city
  cityMemoryDetail.value = null
  cityMemoryError.value = null
  cityMediaTasks.value = []
  mediaTaskError.value = null
  cityMemoryPhase.value = 'loading'
  xiaoxiOpen.value = false
  const [detailResult, tasksResult] = await Promise.allSettled([
    getCityMemories(city.adcode),
    getCityMediaTasks(city.adcode),
  ])
  if (selectedCity.value?.adcode !== city.adcode) return
  if (detailResult.status === 'rejected') {
    cityMemoryError.value = normalizeError(detailResult.reason)
    cityMemoryPhase.value = 'error'
    return
  }
  cityMemoryDetail.value = detailResult.value
  cityMemoryPhase.value = 'ready'
  if (tasksResult.status === 'fulfilled') {
    cityMediaTasks.value = tasksResult.value.items
  } else {
    mediaTaskError.value = normalizeError(tasksResult.reason)
  }
}

function closeCityMemory() {
  selectedCity.value = null
  cityMemoryDetail.value = null
  cityMemoryError.value = null
  cityMediaTasks.value = []
  mediaTaskError.value = null
}

function openXiaoxi() {
  selectedCity.value = null
  xiaoxiOpen.value = true
}

function askXiaoxiAboutCity(city: VisitedCity) {
  closeCityMemory()
  xiaoxiOpen.value = true
  composer.value = `小曦，带我回顾在${city.name_zh}的旅行记忆。`
}

function openMemoryComposer(city: VisitedCity) {
  memoryComposerCity.value = city
  memoryComposerMode.value = 'create'
  memoryTarget.value = null
  memoryComposerPhase.value = 'editing'
  memoryDraft.value = null
  memoryPreview.value = null
  memoryError.value = null
}

function openMemoryEditor(memory: CityMemoryItem) {
  if (!selectedCity.value) return
  memoryComposerCity.value = selectedCity.value
  memoryComposerMode.value = 'edit'
  memoryTarget.value = memory
  memoryComposerPhase.value = 'editing'
  memoryDraft.value = null
  memoryPreview.value = null
  memoryError.value = null
}

function closeMemoryComposer() {
  memoryComposerCity.value = null
  memoryTarget.value = null
  memoryDraft.value = null
  memoryPreview.value = null
  memoryError.value = null
}

async function previewMemory(input: NewMemoryInput) {
  if (!memoryComposerCity.value) return
  memoryError.value = null
  memoryDraft.value = {
    username: 'AuroraRovella',
    client_request_id: crypto.randomUUID(),
    ...input,
  }
  try {
    if (memoryComposerMode.value === 'edit') {
      if (!memoryTarget.value) {
        memoryError.value = localError('MEMORY_CONTEXT_LOST', '找不到要修改的记忆。', false)
        memoryComposerPhase.value = 'error'
        return
      }
      memoryPreview.value = await previewCityMemoryUpdate(
        memoryComposerCity.value.adcode,
        memoryTarget.value.id,
        memoryDraft.value,
      )
    } else {
      memoryPreview.value = await previewCityMemory(
        memoryComposerCity.value.adcode,
        memoryDraft.value,
      )
    }
    memoryComposerPhase.value = 'preview'
  } catch (error) {
    memoryError.value = normalizeError(error)
    memoryComposerPhase.value = 'error'
  }
}

async function refreshMemoryViews(adcode: string) {
  overview.value = await getMapOverview()
  if (selectedCity.value?.adcode === adcode) {
    const [detail, tasks] = await Promise.all([
      getCityMemories(adcode),
      getCityMediaTasks(adcode),
    ])
    cityMemoryDetail.value = detail
    cityMediaTasks.value = tasks.items
    mediaTaskError.value = null
    selectedCity.value = cityMemoryDetail.value.city
  }
}

async function confirmMemory() {
  if (!memoryComposerCity.value || !memoryDraft.value) {
    memoryError.value = localError('MEMORY_CONTEXT_LOST', '记忆编辑上下文已失效，请重新填写。', false)
    memoryComposerPhase.value = 'error'
    return
  }

  memoryComposerPhase.value = 'saving'
  try {
    if (memoryComposerMode.value === 'edit') {
      if (!memoryTarget.value) {
        memoryError.value = localError('MEMORY_CONTEXT_LOST', '找不到要修改的记忆。', false)
        memoryComposerPhase.value = 'error'
        return
      }
      await confirmCityMemoryUpdate(
        memoryComposerCity.value.adcode,
        memoryTarget.value.id,
        memoryDraft.value,
      )
    } else {
      await confirmCityMemory(memoryComposerCity.value.adcode, memoryDraft.value)
    }
    await refreshMemoryViews(memoryComposerCity.value.adcode)
    memoryComposerPhase.value = 'success'
  } catch (error) {
    memoryError.value = normalizeError(error)
    memoryComposerPhase.value = 'error'
  }
}

function editMemoryDraft() {
  memoryError.value = null
  memoryComposerPhase.value = 'editing'
}

async function openMemoryDelete(memory: CityMemoryItem) {
  if (!selectedCity.value) return
  memoryDeleteCity.value = selectedCity.value
  memoryDeleteTarget.value = memory
  memoryDeletePhase.value = 'loading'
  memoryDeletePreview.value = null
  memoryDeleteError.value = null
  memoryDeleteDraft.value = {
    username: 'AuroraRovella',
    client_request_id: crypto.randomUUID(),
  }
  try {
    memoryDeletePreview.value = await previewCityMemoryDelete(
      selectedCity.value.adcode,
      memory.id,
      memoryDeleteDraft.value,
    )
    memoryDeletePhase.value = 'preview'
  } catch (error) {
    memoryDeleteError.value = normalizeError(error)
    memoryDeletePhase.value = 'error'
  }
}

function closeMemoryDelete() {
  memoryDeleteCity.value = null
  memoryDeleteTarget.value = null
  memoryDeleteDraft.value = null
  memoryDeletePreview.value = null
  memoryDeleteError.value = null
}

async function confirmMemoryDelete() {
  if (!memoryDeleteCity.value || !memoryDeleteTarget.value || !memoryDeleteDraft.value) {
    memoryDeleteError.value = localError(
      'MEMORY_CONTEXT_LOST',
      '删除确认上下文已失效，请重新选择记忆。',
      false,
    )
    memoryDeletePhase.value = 'error'
    return
  }
  memoryDeletePhase.value = 'deleting'
  try {
    await confirmCityMemoryDelete(
      memoryDeleteCity.value.adcode,
      memoryDeleteTarget.value.id,
      memoryDeleteDraft.value,
    )
    await refreshMemoryViews(memoryDeleteCity.value.adcode)
    memoryDeletePhase.value = 'success'
  } catch (error) {
    memoryDeleteError.value = normalizeError(error)
    memoryDeletePhase.value = 'error'
  }
}

async function openMediaDelete(
  memoryId: string,
  asset: MemoryMediaAsset | MediaTaskItem,
) {
  if (!selectedCity.value) return
  const assetId = 'asset_id' in asset ? asset.asset_id : asset.id
  mediaDeleteCity.value = selectedCity.value
  mediaDeleteTarget.value = { memoryId, assetId }
  mediaDeletePhase.value = 'loading'
  mediaDeletePreview.value = null
  mediaDeleteError.value = null
  mediaDeleteDraft.value = {
    username: 'AuroraRovella',
    client_request_id: crypto.randomUUID(),
  }
  try {
    mediaDeletePreview.value = await previewMediaDelete(
      selectedCity.value.adcode,
      memoryId,
      assetId,
      mediaDeleteDraft.value,
    )
    mediaDeletePhase.value = 'preview'
  } catch (error) {
    mediaDeleteError.value = normalizeError(error)
    mediaDeletePhase.value = 'error'
  }
}

function closeMediaDelete() {
  mediaDeleteCity.value = null
  mediaDeleteTarget.value = null
  mediaDeleteDraft.value = null
  mediaDeletePreview.value = null
  mediaDeleteError.value = null
}

async function confirmSelectedMediaDelete() {
  if (!mediaDeleteCity.value || !mediaDeleteTarget.value || !mediaDeleteDraft.value) {
    mediaDeleteError.value = localError(
      'MEDIA_DELETE_CONTEXT_LOST',
      '媒体删除上下文已失效，请重新选择文件。',
      false,
    )
    mediaDeletePhase.value = 'error'
    return
  }
  mediaDeletePhase.value = 'deleting'
  try {
    await confirmMediaDelete(
      mediaDeleteCity.value.adcode,
      mediaDeleteTarget.value.memoryId,
      mediaDeleteTarget.value.assetId,
      mediaDeleteDraft.value,
    )
    await refreshMemoryViews(mediaDeleteCity.value.adcode)
    mediaDeletePhase.value = 'success'
  } catch (error) {
    mediaDeleteError.value = normalizeError(error)
    mediaDeletePhase.value = 'error'
  }
}

async function retryMediaTask(task: MediaTaskItem) {
  const city = selectedCity.value
  if (!city || mediaTaskBusyId.value) return
  mediaTaskBusyId.value = task.asset_id
  mediaTaskError.value = null
  try {
    await completeMediaUpload(city.adcode, task.memory_id, task.asset_id)
    let ready = false
    for (let attempt = 0; attempt < 80; attempt += 1) {
      if (selectedCity.value?.adcode !== city.adcode) return
      if (attempt > 0) await wait(1500)
      const status = await getMediaProcessingStatus(
        city.adcode,
        task.memory_id,
        task.asset_id,
      )
      if (status.status === 'ready') {
        ready = true
        break
      }
      if (status.status === 'failed') {
        throw new ApiClientError({
          code: status.failure_code ?? 'MEDIA_PROCESSING_ERROR',
          message: status.failure_message ?? '媒体重新处理失败。',
          details: { asset_id: status.asset_id, scan_status: status.scan_status },
          retryable: status.retryable,
        })
      }
    }
    if (!ready) {
      throw new ApiClientError({
        code: 'MEDIA_PROCESSING_TIMEOUT',
        message: '媒体仍在处理中，可以稍后再次查看。',
        details: { asset_id: task.asset_id },
        retryable: true,
      })
    }
    await refreshMemoryViews(city.adcode)
  } catch (error) {
    mediaTaskError.value = normalizeError(error)
  } finally {
    mediaTaskBusyId.value = null
  }
}

function openMediaUpload(memory: CityMemoryItem) {
  if (!selectedCity.value) return
  mediaUploadPollVersion += 1
  mediaUploadAbortController?.abort()
  mediaUploadAbortController = null
  mediaUploadCity.value = selectedCity.value
  mediaUploadMemory.value = memory
  mediaUploadPhase.value = 'selecting'
  mediaUploadFile.value = null
  mediaUploadDraft.value = null
  mediaUploadPreview.value = null
  mediaUploadIntent.value = null
  mediaUploadTransferred.value = false
  mediaUploadCompleted.value = false
  mediaUploadError.value = null
  mediaUploadProgress.value = { loaded: 0, total: 0, percent: 0 }
}

function closeMediaUpload() {
  mediaUploadPollVersion += 1
  mediaUploadAbortController?.abort()
  mediaUploadAbortController = null
  mediaUploadCity.value = null
  mediaUploadMemory.value = null
  mediaUploadFile.value = null
  mediaUploadDraft.value = null
  mediaUploadPreview.value = null
  mediaUploadIntent.value = null
  mediaUploadTransferred.value = false
  mediaUploadCompleted.value = false
  mediaUploadError.value = null
  mediaUploadProgress.value = { loaded: 0, total: 0, percent: 0 }
}

async function previewSelectedMedia(file: File) {
  if (!mediaUploadCity.value || !mediaUploadMemory.value) return
  mediaUploadFile.value = file
  mediaUploadError.value = null
  mediaUploadIntent.value = null
  mediaUploadTransferred.value = false
  mediaUploadCompleted.value = false
  mediaUploadProgress.value = { loaded: 0, total: file.size, percent: 0 }
  mediaUploadDraft.value = {
    username: 'AuroraRovella',
    client_request_id: crypto.randomUUID(),
    kind: file.type.startsWith('image/') ? 'photo' : 'vlog',
    filename: file.name,
    mime_type: file.type || 'application/octet-stream',
    byte_size: file.size,
    visibility: 'private',
  }
  try {
    mediaUploadPreview.value = await previewMediaUpload(
      mediaUploadCity.value.adcode,
      mediaUploadMemory.value.id,
      mediaUploadDraft.value,
    )
    mediaUploadPhase.value = 'preview'
  } catch (error) {
    mediaUploadError.value = normalizeError(error)
    mediaUploadPhase.value = 'error'
  }
}

function editMediaSelection() {
  mediaUploadPollVersion += 1
  mediaUploadAbortController?.abort()
  mediaUploadAbortController = null
  mediaUploadPhase.value = 'selecting'
  mediaUploadPreview.value = null
  mediaUploadError.value = null
  mediaUploadDraft.value = null
  mediaUploadIntent.value = null
  mediaUploadTransferred.value = false
  mediaUploadCompleted.value = false
  mediaUploadProgress.value = { loaded: 0, total: 0, percent: 0 }
}

function cancelMediaUpload() {
  mediaUploadPollVersion += 1
  mediaUploadAbortController?.abort()
  mediaUploadAbortController = null
  mediaUploadTransferred.value = false
  mediaUploadCompleted.value = false
  mediaUploadError.value = null
  mediaUploadProgress.value = {
    loaded: 0,
    total: mediaUploadFile.value?.size ?? 0,
    percent: 0,
  }
  mediaUploadPhase.value = mediaUploadPreview.value ? 'preview' : 'selecting'
}

function wait(milliseconds: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds))
}

async function waitForMediaReady(
  adcode: string,
  memoryId: string,
  assetId: string,
  pollVersion: number,
): Promise<boolean> {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    if (pollVersion !== mediaUploadPollVersion) return false
    if (attempt > 0) await wait(1500)
    if (pollVersion !== mediaUploadPollVersion) return false
    const status = await getMediaProcessingStatus(adcode, memoryId, assetId)
    if (status.status === 'ready') return true
    if (status.status === 'failed') {
      throw new ApiClientError({
        code: status.failure_code ?? 'MEDIA_PROCESSING_ERROR',
        message: status.failure_message ?? '媒体安全处理失败，请重新选择文件或稍后重试。',
        details: { asset_id: status.asset_id, scan_status: status.scan_status },
        retryable: status.retryable,
      })
    }
  }
  throw new ApiClientError({
    code: 'MEDIA_PROCESSING_TIMEOUT',
    message: '媒体仍在处理中，可以稍后重试查询。',
    details: { asset_id: assetId },
    retryable: true,
  })
}

async function confirmMediaUpload() {
  if (
    !mediaUploadCity.value
    || !mediaUploadMemory.value
    || !mediaUploadFile.value
    || !mediaUploadDraft.value
  ) {
    mediaUploadError.value = localError(
      'MEDIA_UPLOAD_CONTEXT_LOST',
      '上传上下文已失效，请重新选择文件。',
      false,
    )
    mediaUploadPhase.value = 'error'
    return
  }
  mediaUploadPhase.value = 'uploading'
  mediaUploadError.value = null
  mediaUploadProgress.value = mediaUploadTransferred.value
    ? { loaded: mediaUploadFile.value.size, total: mediaUploadFile.value.size, percent: 100 }
    : { loaded: 0, total: mediaUploadFile.value.size, percent: 0 }
  const pollVersion = ++mediaUploadPollVersion
  try {
    if (!mediaUploadCompleted.value) {
      if (!mediaUploadIntent.value) {
        mediaUploadIntent.value = await createMediaUploadIntent(
          mediaUploadCity.value.adcode,
          mediaUploadMemory.value.id,
          mediaUploadDraft.value,
        )
        if (pollVersion !== mediaUploadPollVersion) return
      }
      if (!mediaUploadTransferred.value) {
        const uploadController = new AbortController()
        mediaUploadAbortController = uploadController
        try {
          await uploadMediaFile(mediaUploadIntent.value, mediaUploadFile.value, {
            signal: uploadController.signal,
            onProgress: (progress) => {
              if (pollVersion === mediaUploadPollVersion) mediaUploadProgress.value = progress
            },
          })
        } finally {
          if (mediaUploadAbortController === uploadController) {
            mediaUploadAbortController = null
          }
        }
        if (pollVersion !== mediaUploadPollVersion) return
        mediaUploadTransferred.value = true
      }
      await completeMediaUpload(
        mediaUploadCity.value.adcode,
        mediaUploadMemory.value.id,
        mediaUploadIntent.value.asset_id,
      )
      if (pollVersion !== mediaUploadPollVersion) return
      mediaUploadCompleted.value = true
    }
    const intent = mediaUploadIntent.value
    if (!intent) {
      throw new ApiClientError({
        code: 'MEDIA_UPLOAD_CONTEXT_LOST',
        message: '上传任务信息已失效，请重新选择文件。',
        details: {},
        retryable: false,
      })
    }
    mediaUploadPhase.value = 'processing'
    const ready = await waitForMediaReady(
      mediaUploadCity.value.adcode,
      mediaUploadMemory.value.id,
      intent.asset_id,
      pollVersion,
    )
    if (!ready) return
    await refreshMemoryViews(mediaUploadCity.value.adcode)
    mediaUploadPhase.value = 'success'
  } catch (error) {
    if (pollVersion !== mediaUploadPollVersion) return
    mediaUploadCompleted.value = false
    mediaUploadError.value = normalizeError(error)
    mediaUploadPhase.value = 'error'
  }
}
</script>

<template>
  <div class="app-shell">
    <aside class="brand-rail">
      <button class="brand-mark" type="button" title="Voyaura 地图" aria-label="Voyaura 地图" @click="activeView = 'map'">V</button>
      <AppNavigation :active-view="activeView" @select="activeView = $event" />
      <button class="notification-button" type="button" title="通知" aria-label="通知"><Bell :size="20" /></button>
      <span class="avatar" title="AuroraRovella">AR</span>
    </aside>

    <MapHomeView
      v-if="activeView === 'map'"
      :overview="overview"
      :api-connected="apiConnected"
      :focus-point="focusPoint"
      :check-in-busy="checkInBusy"
      @open-xiaoxi="openXiaoxi"
      @request-check-in="startCheckIn"
      @select-city="selectCity"
    />
    <EmptyView v-else :view="activeView" @back="activeView = 'map'" />

    <AppNavigation class="mobile-nav" :active-view="activeView" @select="activeView = $event" />

    <Transition name="dialog">
      <CheckInDialog
        v-if="checkInPhase !== 'idle'"
        :phase="checkInPhase"
        :preview="checkInPreview"
        :error="checkInError"
        :location-mode="locationMode"
        :manual-results="manualResults"
        :manual-busy="manualBusy"
        :manual-error="manualError"
        @cancel="closeCheckIn"
        @confirm="confirmCurrentCity"
        @retry="startCheckIn"
        @use-ip="useIpCity"
        @open-manual="openManualCitySearch"
        @search-manual="searchManualCity"
        @select-manual="selectManualCity"
      />
    </Transition>

    <Transition name="panel">
      <CityMemoryPanel
        v-if="selectedCity"
        :city="selectedCity"
        :phase="cityMemoryPhase"
        :detail="cityMemoryDetail"
        :error="cityMemoryError"
        :media-tasks="cityMediaTasks"
        :media-task-busy-id="mediaTaskBusyId"
        :media-task-error="mediaTaskError"
        @close="closeCityMemory"
        @retry="selectCity(selectedCity)"
        @ask-xiaoxi="askXiaoxiAboutCity"
        @create-memory="openMemoryComposer"
        @edit-memory="openMemoryEditor"
        @delete-memory="openMemoryDelete"
        @upload-media="openMediaUpload"
        @retry-media="retryMediaTask"
        @delete-media="openMediaDelete"
      />
    </Transition>

    <Transition name="dialog">
      <MediaUploadDialog
        v-if="mediaUploadCity && mediaUploadMemory"
        :city="mediaUploadCity"
        :memory="mediaUploadMemory"
        :phase="mediaUploadPhase"
        :file="mediaUploadFile"
        :preview="mediaUploadPreview"
        :upload-progress="mediaUploadProgress"
        :error="mediaUploadError"
        @cancel="closeMediaUpload"
        @preview="previewSelectedMedia"
        @confirm="confirmMediaUpload"
        @cancel-upload="cancelMediaUpload"
        @retry="confirmMediaUpload"
        @edit="editMediaSelection"
      />
    </Transition>

    <Transition name="dialog">
      <MediaDeleteDialog
        v-if="mediaDeleteCity"
        :city="mediaDeleteCity"
        :phase="mediaDeletePhase"
        :preview="mediaDeletePreview"
        :error="mediaDeleteError"
        @cancel="closeMediaDelete"
        @confirm="confirmSelectedMediaDelete"
      />
    </Transition>

    <Transition name="dialog">
      <MemoryComposerDialog
        v-if="memoryComposerCity"
        :key="`${memoryComposerMode}:${memoryTarget?.id ?? 'new'}`"
        :city="memoryComposerCity"
        :mode="memoryComposerMode"
        :initial-memory="memoryTarget"
        :phase="memoryComposerPhase"
        :preview="memoryPreview"
        :error="memoryError"
        @cancel="closeMemoryComposer"
        @preview="previewMemory"
        @confirm="confirmMemory"
        @edit="editMemoryDraft"
      />
    </Transition>

    <Transition name="dialog">
      <MemoryDeleteDialog
        v-if="memoryDeleteCity && memoryDeleteTarget"
        :city="memoryDeleteCity"
        :phase="memoryDeletePhase"
        :preview="memoryDeletePreview"
        :error="memoryDeleteError"
        @cancel="closeMemoryDelete"
        @confirm="confirmMemoryDelete"
      />
    </Transition>

    <Transition name="panel">
      <aside v-if="xiaoxiOpen" class="xiaoxi-panel" aria-label="小曦旅行助手">
        <header>
          <span class="xiaoxi-sun"><Sparkles :size="20" /></span>
          <div><small>VOYAURA COMPANION</small><strong>小曦</strong></div>
          <button type="button" title="关闭" aria-label="关闭" @click="xiaoxiOpen = false"><X :size="20" /></button>
        </header>
        <div class="chat-body">
          <p class="date-stamp">NOV · 10 · 2026</p>
          <div class="xiaoxi-message">
            <span>曦</span>
            <p>晚上好，Aurora。今天想去哪里，还是要把刚刚抵达的城市收藏起来？</p>
          </div>
          <div class="chat-suggestions">
            <button type="button" @click="composer = '帮我规划一个三天两夜的城市旅程'">规划新旅程</button>
            <button type="button" @click="composer = '介绍一下我现在所在的城市'">认识这座城</button>
            <button type="button" @click="composer = '帮我整理今天拍摄的照片'">整理旅行照片</button>
          </div>
        </div>
        <form class="chat-composer" @submit.prevent="composer = ''">
          <MessageCircle :size="18" />
          <input v-model="composer" aria-label="给小曦发消息" placeholder="问问小曦..." />
          <button type="submit" title="发送" aria-label="发送"><Send :size="18" /></button>
        </form>
      </aside>
    </Transition>
  </div>
</template>
