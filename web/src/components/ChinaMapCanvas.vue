<script setup lang="ts">
import AMapLoader from '@amap/amap-jsapi-loader'
import { AlertTriangle, LoaderCircle, LocateFixed, Minus, Plus, RefreshCw } from 'lucide-vue-next'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { MapIssue, MapOverview, VisitedCity } from '../types'

const props = defineProps<{
  overview: MapOverview
  focusPoint?: [number, number] | null
}>()

const emit = defineEmits<{
  requestCheckIn: []
  selectCity: [city: VisitedCity]
  issue: [issue: MapIssue | null]
}>()

type MapStatus = 'loading' | 'ready' | 'error'
type AMapRuntime = typeof AMap & {
  DistrictLayer?: {
    Country: new (options: Record<string, unknown>) => AMap.TileLayer
  }
}

const mapHost = ref<HTMLDivElement | null>(null)
const mapStatus = ref<MapStatus>('loading')
const mapIssue = ref<MapIssue | null>(null)

let amap: AMapRuntime | null = null
let map: AMap.Map | null = null
let countryLayer: AMap.TileLayer | null = null
let cityMarkers: AMap.Marker[] = []
let focusMarker: AMap.Marker | null = null
let focusCircle: AMap.Circle | null = null
let locaContainer: InstanceType<NonNullable<Window['Loca']>['Container']> | null = null

function setIssue(issue: MapIssue | null) {
  mapIssue.value = issue
  emit('issue', issue)
}

function destroyMap() {
  locaContainer?.destroy()
  locaContainer = null
  cityMarkers = []
  focusMarker = null
  focusCircle = null
  countryLayer = null
  map?.destroy()
  map = null
  amap = null
}

function addCountryLayer() {
  if (!map || !amap?.DistrictLayer?.Country) return

  countryLayer = new amap.DistrictLayer.Country({
    SOC: 'CHN',
    depth: 1,
    zIndex: 8,
    styles: {
      fill: '#e9eee9',
      'nation-stroke': '#667c6c',
      'coastline-stroke': '#7e9183',
      'province-stroke': '#aab5ab',
    },
  })
  map.add(countryLayer)
}

function renderCityPoints() {
  if (!map || !amap) return

  if (cityMarkers.length) map.remove(cityMarkers)
  cityMarkers = []
  locaContainer?.destroy()
  locaContainer = null

  const features: GeoJSON.Feature[] = props.overview.visited_cities.map((city) => ({
    type: 'Feature',
    properties: { adcode: city.adcode, name: city.name_zh, memories: city.memory_count },
    geometry: { type: 'Point', coordinates: [city.longitude, city.latitude] },
  }))

  if (features.length && window.Loca) {
    try {
      locaContainer = new window.Loca.Container({ map })
      const source = new window.Loca.GeoJSONSource({
        data: { type: 'FeatureCollection', features },
      })
      const layer = new window.Loca.PointLayer({
        loca: locaContainer,
        zIndex: 120,
        opacity: 1,
        blend: 'normal',
      })
      layer.setSource(source)
      layer.setStyle({
        radius: 8,
        color: '#e9583e',
        borderWidth: 3,
        borderColor: '#fff8ec',
        unit: 'px',
      })
      locaContainer.add(layer)
    } catch {
      setIssue({
        code: 'LOCA_LAYER_FAILED',
        message: '城市数据图层加载失败，底图仍可继续使用。',
        suggestion: '刷新页面；若持续出现，请检查 Loca 2.0 的调用权限。',
      })
    }
  }

  cityMarkers = props.overview.visited_cities.map((city) => {
    const content = document.createElement('button')
    content.type = 'button'
    content.className = 'amap-city-marker'
    content.title = `打开 ${city.name_zh} 的城市记忆`
    const dot = document.createElement('span')
    const label = document.createTextNode(city.name_zh)
    content.append(dot, label)
    content.addEventListener('click', () => emit('selectCity', city))

    const marker = new amap!.Marker({
      position: [city.longitude, city.latitude],
      title: city.name_zh,
      content,
      offset: new amap!.Pixel(-14, -28),
      zIndex: 130,
    })
    map!.add(marker)
    return marker
  })
}

function renderFocusPoint() {
  if (!map || !amap) return
  if (focusMarker) map.remove(focusMarker)
  if (focusCircle) map.remove(focusCircle)
  focusMarker = null
  focusCircle = null

  if (!props.focusPoint) return
  focusCircle = new amap.Circle({
    center: props.focusPoint,
    radius: 700,
    strokeColor: '#e9583e',
    strokeOpacity: 0.55,
    strokeWeight: 1,
    fillColor: '#e9583e',
    fillOpacity: 0.12,
  })
  focusMarker = new amap.Marker({ position: props.focusPoint, anchor: 'bottom-center' })
  map.add([focusCircle, focusMarker])
  map.setZoomAndCenter(11, props.focusPoint)
}

async function loadMap() {
  const key = import.meta.env.VITE_AMAP_KEY?.trim()
  const securityCode = import.meta.env.VITE_AMAP_SECURITY_CODE?.trim()
  if (!key || !securityCode) {
    mapStatus.value = 'error'
    setIssue({
      code: 'AMAP_CONFIG_MISSING',
      message: '高德前端地图配置不完整。',
      suggestion: '请检查 web/.env.local 中的 JS API Key 与 securityJsCode，然后重启前端。',
    })
    return
  }

  destroyMap()
  mapStatus.value = 'loading'
  setIssue(null)
  window._AMapSecurityConfig = { securityJsCode: securityCode }

  try {
    amap = (await AMapLoader.load({
      key,
      version: '2.0',
      plugins: ['AMap.ToolBar', 'AMap.DistrictLayer'],
      Loca: { version: '2.0.0' },
    })) as AMapRuntime
    if (!mapHost.value) return

    map = new amap.Map(mapHost.value, {
      center: props.overview.map_center,
      zoom: props.overview.default_zoom,
      mapStyle: 'amap://styles/whitesmoke',
      showLabel: true,
      viewMode: '2D',
    })
    addCountryLayer()
    renderCityPoints()
    renderFocusPoint()
    mapStatus.value = 'ready'
  } catch (error) {
    const detail = error instanceof Error ? error.message : 'unknown'
    mapStatus.value = 'error'
    setIssue({
      code: 'AMAP_JS_LOAD_FAILED',
      message: '真实高德地图加载失败。',
      suggestion: `检查 JS API Key、安全密钥、域名白名单和网络后重试。诊断：${detail}`,
    })
  }
}

function zoom(delta: number) {
  if (map) map.setZoom(map.getZoom() + delta)
}

watch(() => props.overview.visited_cities, renderCityPoints, { deep: true })
watch(() => props.focusPoint, renderFocusPoint, { deep: true })

onMounted(loadMap)
onBeforeUnmount(destroyMap)
</script>

<template>
  <section class="map-canvas" aria-label="中国旅行地图">
    <div ref="mapHost" class="amap-host" :class="{ visible: mapStatus === 'ready' }"></div>

    <div v-if="mapStatus !== 'ready'" class="map-service-state" :class="mapStatus">
      <template v-if="mapStatus === 'loading'">
        <LoaderCircle class="spin" :size="32" />
        <strong>正在连接高德地图</strong>
        <p>加载真实中国底图与行政区边界</p>
      </template>
      <template v-else-if="mapIssue">
        <AlertTriangle :size="30" />
        <strong>{{ mapIssue.message }}</strong>
        <code>{{ mapIssue.code }}</code>
        <p>{{ mapIssue.suggestion }}</p>
        <button type="button" @click="loadMap"><RefreshCw :size="16" />重新加载</button>
      </template>
    </div>

    <div v-if="mapStatus === 'ready' && mapIssue" class="map-warning" role="status">
      <AlertTriangle :size="15" />
      <span>{{ mapIssue.message }}</span>
      <code>{{ mapIssue.code }}</code>
    </div>

    <div class="map-watermark">
      <span>CHINA · 旅行图鉴</span>
      <small>AMAP · LOCA 2.0</small>
    </div>

    <div class="map-controls" aria-label="地图控制">
      <button type="button" title="放大" aria-label="放大" :disabled="!map" @click="zoom(1)"><Plus :size="19" /></button>
      <button type="button" title="缩小" aria-label="缩小" :disabled="!map" @click="zoom(-1)"><Minus :size="19" /></button>
      <button type="button" title="定位并点亮城市" aria-label="定位并点亮城市" @click="emit('requestCheckIn')"><LocateFixed :size="19" /></button>
    </div>
  </section>
</template>
