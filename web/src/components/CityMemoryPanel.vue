<script setup lang="ts">
import {
  AlertTriangle,
  CalendarDays,
  Camera,
  Clock3,
  FileText,
  Film,
  LoaderCircle,
  LockKeyhole,
  MessageCircle,
  ImagePlus,
  Pencil,
  PenLine,
  RefreshCw,
  Trash2,
  X,
} from 'lucide-vue-next'
import type { AppErrorInfo, CityMemoryDetail, CityMemoryItem, VisitedCity } from '../types'

defineProps<{
  city: VisitedCity
  phase: 'loading' | 'ready' | 'error'
  detail: CityMemoryDetail | null
  error: AppErrorInfo | null
}>()

defineEmits<{
  close: []
  retry: []
  askXiaoxi: [city: VisitedCity]
  createMemory: [city: VisitedCity]
  editMemory: [memory: CityMemoryItem]
  deleteMemory: [memory: CityMemoryItem]
  uploadMedia: [memory: CityMemoryItem]
}>()

const dateFormatter = new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
})

function formatDate(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '日期未知' : dateFormatter.format(date)
}
</script>

<template>
  <aside class="city-memory-panel" aria-labelledby="city-memory-title">
    <header>
      <div>
        <small>MY CITY ARCHIVE · {{ city.adcode }}</small>
        <h2 id="city-memory-title">我与{{ city.name_zh }}</h2>
        <p>{{ city.province_zh }} · {{ city.name_en }}</p>
      </div>
      <button type="button" title="关闭城市记忆" aria-label="关闭城市记忆" @click="$emit('close')">
        <X :size="20" />
      </button>
    </header>

    <div v-if="phase === 'loading'" class="city-memory-state" aria-live="polite">
      <LoaderCircle class="spin" :size="30" />
      <strong>正在翻阅城市档案</strong>
      <p>读取真实到访记录和旅行记忆</p>
    </div>

    <div v-else-if="phase === 'error' && error" class="city-memory-state error" role="alert">
      <AlertTriangle :size="30" />
      <strong>{{ error.message }}</strong>
      <code>{{ error.code }}</code>
      <small v-if="error.requestId">请求编号：{{ error.requestId }}</small>
      <button type="button" @click="$emit('retry')"><RefreshCw :size="16" />重新读取</button>
    </div>

    <template v-else-if="detail">
      <div class="city-memory-scroll">
        <section class="visit-ledger" aria-label="到访信息">
          <div>
            <CalendarDays :size="17" />
            <span>初次抵达</span>
            <strong>{{ formatDate(detail.city.first_visited_at) }}</strong>
          </div>
          <div>
            <Clock3 :size="17" />
            <span>最近到访</span>
            <strong>{{ formatDate(detail.city.last_visited_at) }}</strong>
          </div>
        </section>

        <section class="city-memory-stats" aria-label="城市记忆统计">
          <div><strong>{{ detail.stats.memories }}</strong><span>记忆</span></div>
          <div><strong>{{ detail.stats.photos }}</strong><span>照片</span></div>
          <div><strong>{{ detail.stats.vlogs }}</strong><span>Vlog</span></div>
          <div><strong>{{ detail.stats.vlog_minutes }}</strong><span>分钟</span></div>
        </section>

        <p v-if="detail.visit_note" class="visit-note"><FileText :size="16" />{{ detail.visit_note }}</p>

        <section v-if="detail.memories.length" class="memory-timeline" aria-label="城市记忆时间线">
          <article v-for="memory in detail.memories" :key="memory.id">
            <time :datetime="memory.occurred_at">{{ formatDate(memory.occurred_at) }}</time>
            <div>
              <div class="memory-item-meta">
                <span class="privacy-label"><LockKeyhole :size="12" />{{ memory.visibility === 'private' ? '仅自己可见' : '已分享' }}</span>
                <span class="memory-item-actions">
                  <button type="button" title="添加照片或 Vlog" aria-label="添加照片或 Vlog" @click="$emit('uploadMedia', memory)"><ImagePlus :size="15" /></button>
                  <button type="button" title="编辑记忆" aria-label="编辑记忆" @click="$emit('editMemory', memory)"><Pencil :size="14" /></button>
                  <button class="danger" type="button" title="删除记忆" aria-label="删除记忆" @click="$emit('deleteMemory', memory)"><Trash2 :size="14" /></button>
                </span>
              </div>
              <h3>{{ memory.title }}</h3>
              <p v-if="memory.body">{{ memory.body }}</p>
              <ul v-if="memory.media.length" class="memory-media-list">
                <li v-for="asset in memory.media" :key="asset.id">
                  <Camera v-if="asset.kind === 'photo'" :size="15" />
                  <Film v-else :size="15" />
                  <span>{{ asset.original_filename }}</span>
                </li>
              </ul>
            </div>
          </article>
        </section>

        <section v-else class="city-memory-empty">
          <span><Camera :size="25" /></span>
          <strong>这里还没有旅行记忆</strong>
          <p>到访记录已经保存，照片、Vlog 与手记仍为空。</p>
        </section>
      </div>

      <footer>
        <button type="button" class="memory-write-button" @click="$emit('createMemory', detail.city)">
          <PenLine :size="17" />写一段记忆
        </button>
        <button type="button" @click="$emit('askXiaoxi', detail.city)">
          <MessageCircle :size="17" />和小曦回顾这座城
        </button>
      </footer>
    </template>
  </aside>
</template>
