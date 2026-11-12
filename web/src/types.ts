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

export interface MapYearCityActivity {
  adcode: string
  memory_count: number
}

export interface MapYearSummary {
  year: number
  stats: MapStats
  cities: MapYearCityActivity[]
}

export interface MapOverview {
  username: string
  map_center: [number, number]
  default_zoom: number
  stats: MapStats
  visited_cities: VisitedCity[]
  year_summaries: MapYearSummary[]
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

export interface PoiSearchDraft {
  keywords: string
  city_adcode: string
  category: string
  page: number
  page_size: number
}

export interface PoiItem {
  id: string
  name: string
  category: string
  typecode: string
  address: string
  province: string
  city: string
  district: string
  adcode: string
  longitude: number
  latitude: number
  coordinate_system: 'GCJ02'
  telephone: string | null
  rating: string | null
  average_cost: string | null
  opening_hours: string | null
  navigation_url: string
}

export interface PoiSearchResult {
  keywords: string
  city_adcode: string
  total: number
  page: number
  page_size: number
  items: PoiItem[]
  provider: 'amap'
  queried_at: string
}

export interface PoiDetailResult {
  item: PoiItem
  provider: 'amap'
  queried_at: string
}

export type LocalRouteMode = 'walking' | 'transit' | 'driving'
export type IntercityRouteMode = 'train' | 'high_speed_rail' | 'flight'

export interface RouteCoordinate {
  longitude: number
  latitude: number
}

export interface LocalRouteDraft {
  mode: LocalRouteMode
  origin: RouteCoordinate
  destination: RouteCoordinate
  origin_adcode: string
  destination_adcode: string
}

export interface RouteStep {
  instruction: string
  distance_meters: number
  duration_seconds: number | null
  road_name: string | null
  transport: string
}

export interface RouteOption {
  distance_meters: number
  duration_seconds: number
  walking_distance_meters: number | null
  tolls_yuan: number | null
  taxi_cost_yuan: number | null
  steps: RouteStep[]
}

export interface LocalRouteResult {
  mode: LocalRouteMode
  origin: RouteCoordinate
  destination: RouteCoordinate
  coordinate_system: 'GCJ02'
  provider: 'amap'
  queried_at: string
  options: RouteOption[]
}

export interface RouteProviderCapability {
  mode: LocalRouteMode | IntercityRouteMode
  provider: string
  available: boolean
  state: 'available' | 'configuration_required' | 'partner_required'
  data_scope: string[]
  application_url: string | null
  notice: string
}

export interface RouteCapabilities {
  local: RouteProviderCapability[]
  intercity: RouteProviderCapability[]
  queried_at: string
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

export type ImagePreservationLevel = 'balanced' | 'high'
export type ImageCaptionLayout = 'archive_band' | 'postcard_corner' | 'vertical_stamp'
export type ImageCaptionPalette = 'coral' | 'forest' | 'ink'
export type ImageCaptionFontStyle = 'sans' | 'serif'

export interface ImageStyleRecipe {
  version: string
  aspect_ratio: string
  layout: string
  focal_element: string
  typography: string
  color: string
  texture: string
  default_preservation: ImagePreservationLevel
  preservation_level: ImagePreservationLevel | null
}

export interface ImageStyleSource {
  name: string
  version: string
  url: string
  license: string
}

export interface ImageCaption {
  title: string
  location: string
  date: string
  layout: ImageCaptionLayout
  palette: ImageCaptionPalette
  font_style: ImageCaptionFontStyle
}

export interface XiaoxiPhotoCapability {
  available: boolean
  missing_settings: string[]
  asset_version: string | null
  positions: Array<'left' | 'right'>
  scales: Array<'small' | 'medium' | 'large'>
  poses: string[]
  expressions: string[]
}

export interface ImageCompanion {
  asset_version: string | null
  pose: string
  expression: string
  position: 'left' | 'right'
  scale: 'small' | 'medium' | 'large'
  method: string
  disclosure: string
}

export interface ImageStyle {
  id: string
  name: string
  description: string
  swatch: string
  recipe: ImageStyleRecipe
  source: ImageStyleSource | null
}

export interface ImageStyleCatalog {
  provider: string
  available: boolean
  missing_settings: string[]
  styles: ImageStyle[]
  companion: XiaoxiPhotoCapability
}

export interface ImageJobDraft {
  username: string
  source_asset_id: string
  style_id: string
  prompt: string
  negative_prompt: string | null
  preservation_level: ImagePreservationLevel
  caption_mode: 'none' | 'travel_stamp'
  caption_layout: ImageCaptionLayout
  caption_palette: ImageCaptionPalette
  caption_font_style: ImageCaptionFontStyle
  companion_enabled: boolean
  companion_position: 'left' | 'right'
  companion_scale: 'small' | 'medium' | 'large'
}

export interface ImageJobCreateDraft extends ImageJobDraft {
  client_request_id: string
}

export interface ImageJobPreview {
  source_asset_id: string
  source_filename: string
  city_adcode: string
  city_name: string
  memory_id: string
  memory_title: string
  style: ImageStyle
  recipe: ImageStyleRecipe
  effective_prompt: string
  negative_prompt: string
  preservation_level: ImagePreservationLevel
  caption_mode: 'none' | 'travel_stamp'
  caption: ImageCaption | null
  companion: ImageCompanion | null
  companion_available: boolean
  companion_missing_settings: string[]
  provider: string
  provider_available: boolean
  confirmation_notice: string
}

export interface ImageJob {
  id: string
  status: 'queued' | 'running' | 'succeeded' | 'failed'
  source_asset_id: string
  source_filename: string
  source_url: string | null
  source_thumbnail_url: string | null
  city_adcode: string
  city_name: string
  memory_id: string
  memory_title: string
  style_id: string
  provider: string
  provider_job_id: string | null
  prompt: string
  negative_prompt: string | null
  preservation_level: ImagePreservationLevel
  recipe: ImageStyleRecipe
  style_source: ImageStyleSource | null
  model_names: string[]
  caption_mode: 'none' | 'travel_stamp'
  caption: ImageCaption | null
  companion: ImageCompanion | null
  is_favorite: boolean
  output_url: string | null
  download_url: string | null
  output_mime_type: string | null
  output_width: number | null
  output_height: number | null
  failure_code: string | null
  failure_message: string | null
  retryable: boolean
  created_at: string
  completed_at: string | null
}

export interface ImageJobCreateResult {
  status: 'created' | 'existing'
  job: ImageJob
}

export interface ImageJobList {
  items: ImageJob[]
}

export interface ImageJobDeleteDraft {
  username?: string
  client_request_id: string
}

export interface ImageJobDeletePreview {
  job_id: string
  source_filename: string
  city_name: string
  memory_title: string
  style: ImageStyle
  status: ImageJob['status']
  has_output: boolean
  confirmation_notice: string
}

export interface ImageJobDeleteResult {
  status: 'deleted' | 'existing'
  job_id: string
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
