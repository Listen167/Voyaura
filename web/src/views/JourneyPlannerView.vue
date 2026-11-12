<script setup lang="ts">
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BusFront,
  CarFront,
  Clock3,
  ExternalLink,
  Footprints,
  LoaderCircle,
  MapPin,
  Plane,
  Route,
  Search,
  TrainFront,
} from 'lucide-vue-next'
import { computed, onMounted, ref, watch } from 'vue'
import { ApiClientError, getRouteCapabilities, planLocalRoute } from '../api/client'
import type {
  AppErrorInfo,
  LocalRouteMode,
  LocalRouteResult,
  MapOverview,
  RouteCapabilities,
  RouteProviderCapability,
} from '../types'

const props = defineProps<{ overview: MapOverview }>()
const emit = defineEmits<{ back: [] }>()

const capabilities = ref<RouteCapabilities | null>(null)
const capabilityError = ref<AppErrorInfo | null>(null)
const originAdcode = ref('')
const destinationAdcode = ref('')
const routeMode = ref<LocalRouteMode>('driving')
const routePhase = ref<'idle' | 'loading' | 'ready' | 'error'>('idle')
const routeResult = ref<LocalRouteResult | null>(null)
const routeError = ref<AppErrorInfo | null>(null)

const localModes: Array<{ mode: LocalRouteMode; label: string; icon: typeof CarFront }> = [
  { mode: 'walking', label: '步行', icon: Footprints },
  { mode: 'transit', label: '公交地铁', icon: BusFront },
  { mode: 'driving', label: '驾车', icon: CarFront },
]

const selectedOrigin = computed(() => (
  props.overview.visited_cities.find((city) => city.adcode === originAdcode.value) ?? null
))
const selectedDestination = computed(() => (
  props.overview.visited_cities.find((city) => city.adcode === destinationAdcode.value) ?? null
))
const canPlan = computed(() => (
  selectedOrigin.value !== null
  && selectedDestination.value !== null
  && originAdcode.value !== destinationAdcode.value
  && routePhase.value !== 'loading'
))
const bestRoute = computed(() => routeResult.value?.options[0] ?? null)

watch(
  () => props.overview.visited_cities.map((city) => city.adcode),
  () => {
    const cities = props.overview.visited_cities
    if (!cities.some((city) => city.adcode === originAdcode.value)) {
      originAdcode.value = cities[0]?.adcode ?? ''
    }
    if (!cities.some((city) => city.adcode === destinationAdcode.value)) {
      destinationAdcode.value = cities[1]?.adcode ?? cities[0]?.adcode ?? ''
    }
  },
  { immediate: true },
)

onMounted(async () => {
  try {
    capabilities.value = await getRouteCapabilities()
  } catch (error) {
    capabilityError.value = normalizeError(error)
  }
})

function normalizeError(error: unknown): AppErrorInfo {
  if (error instanceof ApiClientError) return error
  return { code: 'UNKNOWN_CLIENT_ERROR', message: '路线服务出现未知错误。', details: {}, retryable: false }
}

async function submitRoute() {
  const origin = selectedOrigin.value
  const destination = selectedDestination.value
  if (!origin || !destination || !canPlan.value) return
  routePhase.value = 'loading'
  routeResult.value = null
  routeError.value = null
  try {
    routeResult.value = await planLocalRoute({
      mode: routeMode.value,
      origin: { longitude: origin.longitude, latitude: origin.latitude },
      destination: { longitude: destination.longitude, latitude: destination.latitude },
      origin_adcode: origin.adcode,
      destination_adcode: destination.adcode,
    })
    routePhase.value = 'ready'
  } catch (error) {
    routeError.value = normalizeError(error)
    routePhase.value = 'error'
  }
}

function swapCities() {
  const currentOrigin = originAdcode.value
  originAdcode.value = destinationAdcode.value
  destinationAdcode.value = currentOrigin
  routePhase.value = 'idle'
  routeResult.value = null
}

function formatDuration(seconds: number) {
  const minutes = Math.max(1, Math.round(seconds / 60))
  if (minutes < 60) return `${minutes} 分钟`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return rest ? `${hours} 小时 ${rest} 分钟` : `${hours} 小时`
}

function formatDistance(meters: number) {
  return meters < 1000 ? `${meters} 米` : `${(meters / 1000).toFixed(1)} 公里`
}

function intercityLabel(mode: RouteProviderCapability['mode']) {
  const labels: Partial<Record<RouteProviderCapability['mode'], string>> = {
    high_speed_rail: '高铁 / 动车',
    train: '普通火车',
    flight: '飞机',
  }
  return labels[mode] ?? mode
}

function intercityIcon(mode: RouteProviderCapability['mode']) {
  return mode === 'flight' ? Plane : TrainFront
}

function providerLabel(provider: string) {
  return {
    licensed_rail_partner: '正式铁路合作方',
    amadeus_or_china_licensed_partner: 'Amadeus / 国内授权源',
  }[provider] ?? provider
}

function dataFieldLabel(field: string) {
  return {
    train_number: '车次',
    flight_number: '航班号',
    schedule: '时刻',
    seat_class: '席别',
    price: '价格',
    fare: '票价',
    cabin: '舱位',
    availability: '余量',
  }[field] ?? field
}
</script>

<template>
  <main class="journey-planner-view">
    <header class="journey-planner-header">
      <button type="button" title="返回地图" aria-label="返回地图" @click="emit('back')"><ArrowLeft :size="20" /></button>
      <div><p class="eyebrow">MULTIMODAL JOURNEY DESK</p><h1>行程路线</h1></div>
      <span><Route :size="17" />GCJ-02</span>
    </header>

    <div class="journey-planner-scroll">
      <section class="route-query-band" aria-labelledby="local-route-title">
        <div class="route-section-heading">
          <div><p class="eyebrow">LOCAL & FIRST / LAST MILE</p><h2 id="local-route-title">市内与接驳路线</h2></div>
          <small>高德 · 实时查询</small>
        </div>

        <form class="route-query-form" @submit.prevent="submitRoute">
          <label><span>起点城市中心</span><select v-model="originAdcode"><option v-for="city in overview.visited_cities" :key="city.adcode" :value="city.adcode">{{ city.name_zh }}</option></select></label>
          <button class="route-swap" type="button" title="交换起终点" aria-label="交换起终点" @click="swapCities"><ArrowRight :size="18" /></button>
          <label><span>终点城市中心</span><select v-model="destinationAdcode"><option v-for="city in overview.visited_cities" :key="city.adcode" :value="city.adcode">{{ city.name_zh }}</option></select></label>
          <div class="route-mode-control" role="group" aria-label="路线方式">
            <button v-for="item in localModes" :key="item.mode" type="button" :class="{ active: routeMode === item.mode }" :aria-pressed="routeMode === item.mode" @click="routeMode = item.mode"><component :is="item.icon" :size="16" /><span>{{ item.label }}</span></button>
          </div>
          <button class="route-submit" type="submit" :disabled="!canPlan">
            <LoaderCircle v-if="routePhase === 'loading'" class="spin" :size="17" />
            <Search v-else :size="17" />
            <span>查询路线</span>
          </button>
        </form>

        <div v-if="overview.visited_cities.length < 2" class="route-state"><MapPin :size="26" /><strong>至少需要两座已点亮城市</strong></div>
        <div v-else-if="routePhase === 'idle'" class="route-state"><Route :size="28" /><strong>选择两座城市与交通方式</strong><p>当前以城市中心作为路线端点，后续可接入具体车站、机场与 POI。</p></div>
        <div v-else-if="routePhase === 'loading'" class="route-state"><LoaderCircle class="spin" :size="28" /><strong>正在查询高德路线</strong></div>
        <div v-else-if="routePhase === 'error' && routeError" class="route-state error" role="alert"><AlertTriangle :size="28" /><strong>{{ routeError.message }}</strong><code>{{ routeError.code }}</code><p v-if="routeError.code === 'AMAP_INVALID_SIGNATURE'">请关闭 Web 服务 Key 的数字签名，或在 API 环境中配置对应私钥。</p><small v-if="routeError.requestId">请求编号：{{ routeError.requestId }}</small></div>
        <div v-else-if="bestRoute" class="route-result">
          <header><div><strong>{{ selectedOrigin?.name_zh }}</strong><ArrowRight :size="16" /><strong>{{ selectedDestination?.name_zh }}</strong></div><small>高德 · {{ routeResult?.coordinate_system }}</small></header>
          <div class="route-result-metrics"><span><Clock3 :size="16" /><strong>{{ formatDuration(bestRoute.duration_seconds) }}</strong></span><span><Route :size="16" /><strong>{{ formatDistance(bestRoute.distance_meters) }}</strong></span><span v-if="bestRoute.tolls_yuan !== null">过路费 <strong>¥{{ bestRoute.tolls_yuan }}</strong></span></div>
          <ol><li v-for="(step, index) in bestRoute.steps" :key="`${index}-${step.instruction}`"><i>{{ index + 1 }}</i><div><strong>{{ step.instruction }}</strong><small>{{ formatDistance(step.distance_meters) }}<template v-if="step.duration_seconds"> · {{ formatDuration(step.duration_seconds) }}</template></small></div></li></ol>
        </div>
      </section>

      <section class="intercity-band" aria-labelledby="intercity-title">
        <div class="route-section-heading"><div><p class="eyebrow">INTERCITY PROVIDERS</p><h2 id="intercity-title">跨城铁路与航班</h2></div><small>班次 · 票价 · 余量</small></div>
        <div v-if="capabilityError" class="route-inline-error"><AlertTriangle :size="17" /><span>{{ capabilityError.message }} · {{ capabilityError.code }}</span></div>
        <div v-else-if="!capabilities" class="intercity-loading"><LoaderCircle class="spin" :size="22" />正在读取 Provider</div>
        <div v-else class="intercity-grid">
          <article v-for="item in capabilities.intercity" :key="item.mode">
            <span class="intercity-icon"><component :is="intercityIcon(item.mode)" :size="23" /></span>
            <div><small>{{ providerLabel(item.provider) }}</small><h3>{{ intercityLabel(item.mode) }}</h3></div>
            <span class="provider-state">待合作方授权</span>
            <p>{{ item.notice }}</p>
            <div class="provider-fields"><span v-for="field in item.data_scope" :key="field">{{ dataFieldLabel(field) }}</span></div>
            <a v-if="item.application_url" :href="item.application_url" target="_blank" rel="noreferrer">申请接口<ExternalLink :size="14" /></a>
          </article>
        </div>
      </section>
    </div>
  </main>
</template>
