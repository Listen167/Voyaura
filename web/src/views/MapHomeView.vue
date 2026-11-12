<script setup lang="ts">
import { CalendarDays, Camera, ChevronRight, LoaderCircle, MapPin, Navigation, Plus, Search, Sparkles, Sun } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'
import ChinaMapCanvas from '../components/ChinaMapCanvas.vue'
import type { MapOverview, VisitedCity } from '../types'

const props = defineProps<{
  overview: MapOverview
  apiConnected: boolean
  focusPoint: [number, number] | null
  checkInBusy: boolean
}>()
const emit = defineEmits<{
  openXiaoxi: []
  requestCheckIn: []
  searchPoi: []
  selectCity: [city: VisitedCity]
}>()

const selectedYear = ref<number | null>(null)
const selectedSummary = computed(() => (
  selectedYear.value === null
    ? null
    : props.overview.year_summaries.find((summary) => summary.year === selectedYear.value) ?? null
))
const visibleOverview = computed<MapOverview>(() => {
  const summary = selectedSummary.value
  if (!summary) return props.overview
  const activities = new Map(summary.cities.map((city) => [city.adcode, city]))
  return {
    ...props.overview,
    stats: summary.stats,
    visited_cities: props.overview.visited_cities
      .filter((city) => activities.has(city.adcode))
      .map((city) => ({
        ...city,
        memory_count: activities.get(city.adcode)?.memory_count ?? 0,
      })),
  }
})

watch(
  () => props.overview.year_summaries.map((summary) => summary.year),
  (years) => {
    if (selectedYear.value !== null && !years.includes(selectedYear.value)) {
      selectedYear.value = null
    }
  },
)
</script>

<template>
  <main class="map-home">
    <ChinaMapCanvas
      :overview="visibleOverview"
      :focus-point="focusPoint"
      @request-check-in="emit('requestCheckIn')"
      @select-city="emit('selectCity', $event)"
    />

    <header class="map-header">
      <div class="eyebrow">MY TRAVEL ATLAS · {{ selectedYear ?? 'ALL YEARS' }}</div>
      <h1>你好，Aurora</h1>
      <p><span class="status-dot" :class="{ online: apiConnected }"></span>在地图上收藏每一次抵达</p>
    </header>

    <button class="location-pill" type="button" :disabled="checkInBusy" @click="emit('requestCheckIn')">
      <LoaderCircle v-if="checkInBusy" class="spin" :size="16" />
      <Navigation v-else :size="16" fill="currentColor" />
      <span>{{ checkInBusy ? '正在定位城市' : '点亮所在城市' }}</span>
      <Plus v-if="!checkInBusy" :size="16" />
    </button>

    <button class="poi-search-entry" type="button" title="搜索城市地点" @click="emit('searchPoi')">
      <Search :size="16" /><span>搜地点</span>
    </button>

    <section class="journey-tray" aria-labelledby="journey-summary-title">
      <div class="tray-heading">
        <div>
          <p class="eyebrow">YOUR FOOTPRINTS</p>
          <h2 id="journey-summary-title">{{ selectedYear ? `${selectedYear} 年旅程` : '我的中国旅程' }}</h2>
        </div>
        <span class="journey-period"><CalendarDays :size="15" aria-hidden="true" />{{ selectedYear ?? '全部' }}</span>
      </div>
      <div v-if="overview.year_summaries.length" class="year-timeline" role="group" aria-label="按年份筛选旅行足迹">
        <button type="button" :class="{ active: selectedYear === null }" :aria-pressed="selectedYear === null" data-year="all" @click="selectedYear = null">全部</button>
        <button
          v-for="summary in overview.year_summaries"
          :key="summary.year"
          type="button"
          :class="{ active: selectedYear === summary.year }"
          :aria-pressed="selectedYear === summary.year"
          :data-year="summary.year"
          @click="selectedYear = summary.year"
        >{{ summary.year }}</button>
      </div>
      <div class="stats-grid">
        <div><strong>{{ visibleOverview.stats.lit_cities }}</strong><span>点亮城市</span></div>
        <div><strong>{{ visibleOverview.stats.memories }}</strong><span>旅行记忆</span></div>
        <div><strong>{{ visibleOverview.stats.photos }}</strong><span>照片</span></div>
        <div><strong>{{ visibleOverview.stats.vlog_minutes }}</strong><span>Vlog 分钟</span></div>
      </div>
      <button class="memory-action" type="button" @click="emit('requestCheckIn')">
        <span class="action-icon"><Camera :size="20" /></span>
        <span><strong>记录此刻</strong><small>照片 · Vlog · 手记</small></span>
        <ChevronRight :size="18" />
      </button>
    </section>

    <button class="xiaoxi-entry" type="button" aria-label="打开小曦" title="打开小曦" @click="emit('openXiaoxi')">
      <span class="xiaoxi-sun"><Sun :size="25" /></span>
      <span><small>TRAVEL WITH</small><strong>小曦</strong></span>
      <Sparkles class="sparkle" :size="17" />
    </button>

    <div class="map-legend" aria-label="地图图例">
      <span><i class="legend-pin lit"><MapPin :size="13" /></i>已点亮</span>
      <span><i class="legend-pin"><MapPin :size="13" /></i>想去</span>
    </div>
  </main>
</template>
