<script setup lang="ts">
import { Camera, ChevronRight, LoaderCircle, MapPin, Navigation, Plus, Sparkles, Sun } from 'lucide-vue-next'
import ChinaMapCanvas from '../components/ChinaMapCanvas.vue'
import type { MapOverview, VisitedCity } from '../types'

defineProps<{
  overview: MapOverview
  apiConnected: boolean
  focusPoint: [number, number] | null
  checkInBusy: boolean
}>()
const emit = defineEmits<{
  openXiaoxi: []
  requestCheckIn: []
  selectCity: [city: VisitedCity]
}>()
</script>

<template>
  <main class="map-home">
    <ChinaMapCanvas
      :overview="overview"
      :focus-point="focusPoint"
      @request-check-in="emit('requestCheckIn')"
      @select-city="emit('selectCity', $event)"
    />

    <header class="map-header">
      <div class="eyebrow">MY TRAVEL ATLAS · 2026</div>
      <h1>你好，Aurora</h1>
      <p><span class="status-dot" :class="{ online: apiConnected }"></span>在地图上收藏每一次抵达</p>
    </header>

    <button class="location-pill" type="button" :disabled="checkInBusy" @click="emit('requestCheckIn')">
      <LoaderCircle v-if="checkInBusy" class="spin" :size="16" />
      <Navigation v-else :size="16" fill="currentColor" />
      <span>{{ checkInBusy ? '正在定位城市' : '点亮所在城市' }}</span>
      <Plus v-if="!checkInBusy" :size="16" />
    </button>

    <section class="journey-tray" aria-labelledby="journey-summary-title">
      <div class="tray-heading">
        <div>
          <p class="eyebrow">YOUR FOOTPRINTS</p>
          <h2 id="journey-summary-title">我的中国旅程</h2>
        </div>
        <button type="button" aria-label="查看旅程详情" title="查看旅程详情"><ChevronRight :size="20" /></button>
      </div>
      <div class="stats-grid">
        <div><strong>{{ overview.stats.lit_cities }}</strong><span>点亮城市</span></div>
        <div><strong>{{ overview.stats.memories }}</strong><span>旅行记忆</span></div>
        <div><strong>{{ overview.stats.photos }}</strong><span>照片</span></div>
        <div><strong>{{ overview.stats.vlog_minutes }}</strong><span>Vlog 分钟</span></div>
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
