<script setup lang="ts">
import { AlertTriangle, LoaderCircle, MapPin, Navigation, Search, Star, X } from 'lucide-vue-next'
import { ref, watch } from 'vue'
import type { AppErrorInfo, PoiSearchDraft, PoiSearchResult, VisitedCity } from '../types'

const props = defineProps<{
  cities: VisitedCity[]
  phase: 'editing' | 'loading' | 'results' | 'error'
  result: PoiSearchResult | null
  error: AppErrorInfo | null
}>()

const emit = defineEmits<{
  close: []
  search: [draft: PoiSearchDraft]
}>()

const keywords = ref('')
const cityAdcode = ref('')

watch(
  () => props.cities,
  (cities) => {
    if (!cities.some((city) => city.adcode === cityAdcode.value)) {
      cityAdcode.value = cities[0]?.adcode ?? ''
    }
  },
  { immediate: true },
)

function submit() {
  const query = keywords.value.trim()
  if (!query || !cityAdcode.value) return
  emit('search', {
    keywords: query,
    city_adcode: cityAdcode.value,
    category: '',
    page: 1,
    page_size: 10,
  })
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}
</script>

<template>
  <div class="dialog-backdrop poi-search-backdrop" role="presentation" @click.self="emit('close')">
    <section class="poi-search-dialog" role="dialog" aria-modal="true" aria-labelledby="poi-search-title">
      <header>
        <div><p class="eyebrow">AMAP CITY DISCOVERY</p><h2 id="poi-search-title">搜索城市地点</h2></div>
        <button type="button" title="关闭地点搜索" aria-label="关闭地点搜索" @click="emit('close')"><X :size="20" /></button>
      </header>

      <form class="poi-search-form" @submit.prevent="submit">
        <label>
          <span>城市</span>
          <select v-model="cityAdcode" :disabled="!cities.length">
            <option v-for="city in cities" :key="city.adcode" :value="city.adcode">{{ city.name_zh }}</option>
          </select>
        </label>
        <label class="poi-keyword-field">
          <span>关键词</span>
          <input v-model="keywords" type="search" maxlength="80" placeholder="博物馆、早茶、公园" />
        </label>
        <button type="submit" class="primary" :disabled="!keywords.trim() || !cityAdcode || phase === 'loading'" title="搜索地点">
          <LoaderCircle v-if="phase === 'loading'" class="spin" :size="17" />
          <Search v-else :size="17" />
          <span>搜索</span>
        </button>
      </form>

      <div v-if="!cities.length" class="poi-search-state">
        <MapPin :size="29" /><strong>还没有可搜索的城市</strong><p>先在地图上确认一座城市。</p>
      </div>
      <div v-else-if="phase === 'editing'" class="poi-search-state">
        <Search :size="29" /><strong>发现城市里的好去处</strong>
      </div>
      <div v-else-if="phase === 'loading'" class="poi-search-state" aria-live="polite">
        <LoaderCircle class="spin" :size="30" /><strong>正在查询高德地点</strong>
      </div>
      <div v-else-if="phase === 'error' && error" class="poi-search-state error" role="alert">
        <AlertTriangle :size="30" /><strong>{{ error.message }}</strong><code>{{ error.code }}</code>
        <p v-if="error.code === 'AMAP_INVALID_SIGNATURE'">请关闭 Web 服务 Key 的数字签名，或在 API 环境中配置对应私钥。</p>
        <small v-if="error.requestId">请求编号：{{ error.requestId }}</small>
      </div>
      <div v-else-if="result" class="poi-search-results">
        <header><span>{{ result.total }} 个地点</span><small>高德 · GCJ-02 · {{ formatTime(result.queried_at) }}</small></header>
        <ul v-if="result.items.length">
          <li v-for="item in result.items" :key="item.id">
            <div class="poi-result-copy">
              <strong>{{ item.name }}</strong>
              <p><MapPin :size="13" />{{ item.address || `${item.district}${item.category}` }}</p>
              <div>
                <span v-if="item.rating"><Star :size="12" fill="currentColor" />{{ item.rating }}</span>
                <span>{{ item.category.split(';').at(-1) || '地点' }}</span>
                <span v-if="item.opening_hours">{{ item.opening_hours }}</span>
              </div>
            </div>
            <a :href="item.navigation_url" target="_blank" rel="noreferrer" :title="`在高德地图查看 ${item.name}`"><Navigation :size="16" />导航</a>
          </li>
        </ul>
        <div v-else class="poi-search-state compact"><Search :size="24" /><strong>没有匹配地点</strong></div>
      </div>
    </section>
  </div>
</template>
