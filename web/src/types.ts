export interface MapStats {
  lit_cities: number
  memories: number
  photos: number
  vlog_minutes: number
}

export interface VisitedCity {
  adcode: string
  name_zh: string
  name_en: string
  province_zh: string
  longitude: number
  latitude: number
  first_visited_at: string
  last_visited_at: string
  memory_count: number
  check_in_source: 'device' | 'ip' | 'manual'
}

export interface MapOverview {
  username: string
  map_center: [number, number]
  default_zoom: number
  stats: MapStats
  visited_cities: VisitedCity[]
}

export interface CheckInCoordinates {
  username: string
  longitude: number
  latitude: number
  accuracy_meters: number | null
  coordinate_system: 'WGS84'
}

export interface ManualCityCheckIn {
  username: string
  adcode: string
  city_name: string
  province_name: string
  longitude: number
  latitude: number
  source: 'ip' | 'manual'
}

export interface CityCandidate {
  adcode: string
  city_name: string
  province_name: string
  longitude: number
  latitude: number
  source: 'ip' | 'manual'
}

export interface CheckInPreview {
  adcode: string
  city_name: string
  province_name: string
  city_center: [number, number]
  map_position: [number, number]
  formatted_address: string
  accuracy_meters: number | null
  already_lit: boolean
  location_source: 'device' | 'ip' | 'manual'
  privacy_notice: string
}

export interface CheckInConfirmResult {
  status: 'created' | 'updated'
  city: VisitedCity
}

export interface MemoryMediaAsset {
  id: string
  kind: 'photo' | 'vlog'
  original_filename: string
  mime_type: string
  width: number | null
  height: number | null
  duration_seconds: number | null
  visibility: 'private'
  upload_status: 'ready'
  exif_status: 'removed' | 'not_applicable'
  scan_status: 'clean' | 'not_scanned'
  thumbnail_url: string | null
  content_url: string | null
  thumbnail_width: number | null
  thumbnail_height: number | null
  created_at: string
}

export interface CityMemoryItem {
  id: string
  title: string
  body: string | null
  occurred_at: string
  visibility: 'private' | 'shared'
  media: MemoryMediaAsset[]
}

export interface CityMemoryDetail {
  city: VisitedCity
  visit_note: string | null
  stats: {
    memories: number
    photos: number
    vlogs: number
    vlog_minutes: number
  }
  memories: CityMemoryItem[]
}

export interface NewMemoryInput {
  title: string
  body: string | null
  occurred_at: string
  visibility: 'private' | 'shared'
}

export interface CityMemoryDraft extends NewMemoryInput {
  username: string
  client_request_id: string
}

export interface CityMemoryPreview extends NewMemoryInput {
  city_adcode: string
  city_name: string
  confirmation_notice: string
}

export interface CityMemoryConfirmResult {
  status: 'created' | 'existing'
  memory: CityMemoryItem
}

export interface CityMemoryUpdatePreview extends CityMemoryPreview {
  memory_id: string
}

export interface CityMemoryUpdateConfirmResult {
  status: 'updated' | 'existing'
  memory: CityMemoryItem
}

export interface CityMemoryDeleteDraft {
  username: string
  client_request_id: string
}

export interface CityMemoryDeletePreview {
  memory_id: string
  city_adcode: string
  city_name: string
  title: string
  occurred_at: string
  media_count: number
  confirmation_notice: string
}

export interface CityMemoryDeleteConfirmResult {
  status: 'deleted' | 'existing'
  memory_id: string
  city_adcode: string
}

export interface MediaUploadDraft {
  username: string
  client_request_id: string
  kind: 'photo' | 'vlog'
  filename: string
  mime_type: string
  byte_size: number
  visibility: 'private'
}

export interface MediaUploadPreview {
  kind: 'photo' | 'vlog'
  filename: string
  mime_type: string
  byte_size: number
  quota_remaining_bytes: number
  visibility: 'private'
  confirmation_notice: string
}

export interface MediaUploadIntent {
  status: 'created' | 'existing'
  asset_id: string
  upload_url: string
  method: 'PUT'
  required_headers: Record<string, string>
  expires_at: string
}

export interface MediaUploadProgress {
  loaded: number
  total: number
  percent: number
}

export interface MediaUploadCompleteResult {
  status: 'processing' | 'ready' | 'existing'
  asset_id: string
  asset: MemoryMediaAsset | null
  processing_notice: string
}

export interface MediaProcessingStatus {
  status: 'pending' | 'processing' | 'ready' | 'failed'
  asset_id: string
  scan_status: 'not_scanned' | 'pending' | 'scanning' | 'clean' | 'infected' | 'error'
  failure_code: string | null
  failure_message: string | null
  retryable: boolean
  asset: MemoryMediaAsset | null
}

export interface MediaTaskItem {
  asset_id: string
  memory_id: string
  memory_title: string
  kind: 'photo' | 'vlog'
  original_filename: string
  byte_size: number
  upload_status: 'pending' | 'processing' | 'failed'
  scan_status: 'not_scanned' | 'pending' | 'scanning' | 'clean' | 'infected' | 'error'
  failure_code: string | null
  failure_message: string | null
  retryable: boolean
  expired: boolean
  upload_expires_at: string | null
  created_at: string
}

export interface MediaTaskList {
  items: MediaTaskItem[]
}

export interface MediaDeleteDraft {
  username: string
  client_request_id: string
}

export interface MediaDeletePreview {
  asset_id: string
  memory_id: string
  city_adcode: string
  city_name: string
  memory_title: string
  kind: 'photo' | 'vlog'
  original_filename: string
  byte_size: number
  upload_status: 'pending' | 'ready' | 'failed'
  confirmation_notice: string
}

export interface MediaDeleteConfirmResult {
  status: 'deleted' | 'existing'
  asset_id: string
  memory_id: string
  city_adcode: string
}

export interface AppErrorInfo {
  code: string
  message: string
  details: Record<string, unknown>
  retryable: boolean
  requestId?: string
}

export interface MapIssue {
  code: string
  message: string
  suggestion: string
}

export type AppView = 'map' | 'journeys' | 'memories' | 'studio' | 'profile'
