<script setup lang="ts">
import {
  AlertTriangle,
  ArrowLeft,
  Download,
  Heart,
  Image as ImageIcon,
  LoaderCircle,
  MapPin,
  RefreshCw,
  Trash2,
} from 'lucide-vue-next'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  ApiClientError,
  confirmImageJobDelete,
  getImageJobs,
  getImageStyles,
  previewImageJobDelete,
  setImageJobFavorite,
} from '../api/client'
import ImageCompareSlider from '../components/ImageCompareSlider.vue'
import ImageJobDeleteDialog from '../components/ImageJobDeleteDialog.vue'
import type {
  AppErrorInfo,
  ImageJob,
  ImageJobDeletePreview,
  ImageStyleCatalog,
} from '../types'

const emit = defineEmits<{ back: [] }>()

const jobs = ref<ImageJob[]>([])
const selectedId = ref<string | null>(null)
const catalog = ref<ImageStyleCatalog | null>(null)
const favoriteOnly = ref(false)
const loading = ref(true)
const error = ref<AppErrorInfo | null>(null)
const favoriteBusyId = ref<string | null>(null)
const deleteTarget = ref<ImageJob | null>(null)
const deletePreview = ref<ImageJobDeletePreview | null>(null)
const deletePhase = ref<'loading' | 'ready' | 'deleting' | 'error'>('loading')
const deleteError = ref<AppErrorInfo | null>(null)
const deleteRequestId = ref('')
let pollTimer: number | undefined

const selectedJob = computed(() => jobs.value.find((job) => job.id === selectedId.value) ?? jobs.value[0] ?? null)
const styleName = computed(() => {
  const job = selectedJob.value
  return catalog.value?.styles.find((style) => style.id === job?.style_id)?.name ?? job?.style_id ?? ''
})

const statusText: Record<ImageJob['status'], string> = {
  queued: '等待处理',
  running: '正在生成',
  succeeded: '生成完成',
  failed: '生成失败',
}
const captionLayoutLabels = {
  archive_band: '档案横带',
  postcard_corner: '明信片角标',
  vertical_stamp: '竖排印章',
} as const
const captionPaletteLabels = { coral: '珊瑚红', forest: '森林绿', ink: '墨黑' } as const
const captionFontLabels = { sans: '现代黑体', serif: '旅行宋体' } as const

function asError(value: unknown): AppErrorInfo {
  if (value instanceof ApiClientError) return value
  return { code: 'IMAGE_STUDIO_UNKNOWN_ERROR', message: '视觉工作台遇到了未知错误。', details: {}, retryable: true }
}

function requestId() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`
}

async function loadJobs(silent = false) {
  if (!silent) loading.value = true
  error.value = null
  try {
    const [history, styles] = await Promise.all([
      getImageJobs('AuroraRovella', favoriteOnly.value),
      catalog.value ? Promise.resolve(catalog.value) : getImageStyles(),
    ])
    jobs.value = history.items
    catalog.value = styles
    if (!jobs.value.some((job) => job.id === selectedId.value)) selectedId.value = jobs.value[0]?.id ?? null
  } catch (value) {
    error.value = asError(value)
  } finally {
    loading.value = false
  }
  schedulePoll()
}

function schedulePoll() {
  if (pollTimer) window.clearTimeout(pollTimer)
  if (jobs.value.some((job) => job.status === 'queued' || job.status === 'running')) {
    pollTimer = window.setTimeout(() => void loadJobs(true), 2500)
  }
}

async function toggleFavorite(job: ImageJob) {
  favoriteBusyId.value = job.id
  error.value = null
  try {
    const updated = await setImageJobFavorite(job.id, !job.is_favorite)
    if (favoriteOnly.value && !updated.is_favorite) {
      jobs.value = jobs.value.filter((item) => item.id !== updated.id)
      selectedId.value = jobs.value[0]?.id ?? null
    } else {
      jobs.value = jobs.value.map((item) => item.id === updated.id ? updated : item)
    }
  } catch (value) {
    error.value = asError(value)
  } finally {
    favoriteBusyId.value = null
  }
}

async function openDelete(job: ImageJob) {
  deleteTarget.value = job
  deletePreview.value = null
  deleteError.value = null
  deletePhase.value = 'loading'
  deleteRequestId.value = requestId()
  try {
    deletePreview.value = await previewImageJobDelete(job.id, {
      username: 'AuroraRovella',
      client_request_id: deleteRequestId.value,
    })
    deletePhase.value = 'ready'
  } catch (value) {
    deleteError.value = asError(value)
    deletePhase.value = 'error'
  }
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  deletePhase.value = 'deleting'
  try {
    const deletedId = deleteTarget.value.id
    await confirmImageJobDelete(deletedId, {
      username: 'AuroraRovella',
      client_request_id: deleteRequestId.value,
    })
    jobs.value = jobs.value.filter((job) => job.id !== deletedId)
    selectedId.value = jobs.value[0]?.id ?? null
    closeDelete()
  } catch (value) {
    deleteError.value = asError(value)
    deletePhase.value = 'error'
  }
}

function closeDelete() {
  deleteTarget.value = null
  deletePreview.value = null
  deleteError.value = null
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}

onMounted(() => void loadJobs())
onBeforeUnmount(() => { if (pollTimer) window.clearTimeout(pollTimer) })
</script>

<template>
  <main class="image-studio-view">
    <header class="studio-header">
      <button type="button" title="返回旅行地图" aria-label="返回旅行地图" @click="emit('back')"><ArrowLeft :size="19" /></button>
      <div><p class="eyebrow">VOYAURA VISUAL LAB</p><h1>旅行影像工作台</h1></div>
      <button type="button" title="刷新生成历史" aria-label="刷新生成历史" :disabled="loading" @click="loadJobs()"><RefreshCw :size="18" :class="{ spin: loading }" /></button>
    </header>

    <div class="studio-filter-bar">
      <span>{{ jobs.length }} 项创作</span>
      <label><input v-model="favoriteOnly" type="checkbox" @change="loadJobs()" /><Heart :size="14" :fill="favoriteOnly ? 'currentColor' : 'none'" />只看收藏</label>
    </div>

    <section v-if="loading && !jobs.length" class="studio-page-state" aria-live="polite">
      <LoaderCircle class="spin" :size="31" /><strong>正在整理旅行影像</strong>
    </section>

    <section v-else-if="error && !jobs.length" class="studio-page-state error" role="alert">
      <AlertTriangle :size="31" /><strong>{{ error.message }}</strong><code>{{ error.code }}</code>
      <button type="button" @click="loadJobs()">重新加载</button>
    </section>

    <section v-else-if="!jobs.length" class="studio-page-state empty">
      <span><ImageIcon :size="29" /></span><strong>{{ favoriteOnly ? '还没有收藏的作品' : '第一张旅行作品正等着你' }}</strong>
      <p>{{ favoriteOnly ? '取消“只看收藏”可查看全部生成记录。' : '从地图进入一座城市，在照片上选择“风格创作”。' }}</p>
      <button v-if="!favoriteOnly" type="button" @click="emit('back')"><MapPin :size="15" />返回旅行地图</button>
    </section>

    <div v-else class="studio-workspace">
      <aside class="studio-history" aria-label="生成历史">
        <button
          v-for="job in jobs"
          :key="job.id"
          type="button"
          :class="{ active: selectedJob?.id === job.id }"
          @click="selectedId = job.id"
        >
          <span class="studio-history-thumb">
            <img v-if="job.output_url || job.source_thumbnail_url || job.source_url" :src="job.output_url || job.source_thumbnail_url || job.source_url || ''" :alt="job.source_filename" />
            <ImageIcon v-else :size="20" />
            <i :class="`status-${job.status}`"></i>
          </span>
          <span class="studio-history-copy"><strong>{{ job.city_name }}</strong><small>{{ job.memory_title }}</small><time>{{ formatDate(job.created_at) }}</time></span>
          <Heart v-if="job.is_favorite" :size="13" fill="currentColor" />
        </button>
      </aside>

      <section v-if="selectedJob" class="studio-canvas">
        <ImageCompareSlider
          v-if="selectedJob.status === 'succeeded' && selectedJob.source_url && selectedJob.output_url"
          :source-url="selectedJob.source_url"
          :result-url="selectedJob.output_url"
          :source-alt="`原图 ${selectedJob.source_filename}`"
          :result-alt="`${styleName} 生成图`"
        />
        <div v-else class="studio-canvas-state" :class="selectedJob.status">
          <LoaderCircle v-if="selectedJob.status === 'queued' || selectedJob.status === 'running'" class="spin" :size="32" />
          <AlertTriangle v-else-if="selectedJob.status === 'failed'" :size="32" />
          <ImageIcon v-else :size="32" />
          <strong>{{ statusText[selectedJob.status] }}</strong>
          <p v-if="selectedJob.failure_message">{{ selectedJob.failure_message }}</p>
          <p v-else>任务状态会自动刷新，也可以稍后回到这里查看。</p>
        </div>
      </section>

      <aside v-if="selectedJob" class="studio-inspector">
        <div class="studio-inspector-heading">
          <div><span :class="`studio-status status-${selectedJob.status}`">{{ statusText[selectedJob.status] }}</span><h2>{{ styleName }}</h2></div>
          <button type="button" :title="selectedJob.is_favorite ? '取消收藏' : '收藏作品'" :aria-label="selectedJob.is_favorite ? '取消收藏' : '收藏作品'" :disabled="favoriteBusyId === selectedJob.id" @click="toggleFavorite(selectedJob)"><Heart :size="19" :fill="selectedJob.is_favorite ? 'currentColor' : 'none'" /></button>
        </div>
        <dl class="studio-meta">
          <div><dt>城市</dt><dd>{{ selectedJob.city_name }}</dd></div>
          <div><dt>旅行记忆</dt><dd>{{ selectedJob.memory_title }}</dd></div>
          <div><dt>生成时间</dt><dd>{{ formatDate(selectedJob.created_at) }}</dd></div>
          <div v-if="selectedJob.output_width"><dt>尺寸</dt><dd>{{ selectedJob.output_width }} × {{ selectedJob.output_height }}</dd></div>
          <div><dt>原图保真</dt><dd>{{ selectedJob.preservation_level === 'high' ? '高保真' : '平衡' }}</dd></div>
          <div><dt>Recipe</dt><dd>{{ selectedJob.recipe.version }} · {{ selectedJob.recipe.aspect_ratio }}</dd></div>
          <div v-if="selectedJob.model_names.length"><dt>模型</dt><dd>{{ selectedJob.model_names.join('、') }}</dd></div>
          <div v-if="selectedJob.caption"><dt>旅行印记</dt><dd>{{ selectedJob.caption.title }} · {{ selectedJob.caption.location }} · {{ selectedJob.caption.date }} · {{ captionLayoutLabels[selectedJob.caption.layout] }} · {{ captionPaletteLabels[selectedJob.caption.palette] }} · {{ captionFontLabels[selectedJob.caption.font_style] }}</dd></div>
          <div v-if="selectedJob.companion"><dt>小曦合照</dt><dd>{{ selectedJob.companion.position === 'left' ? '左侧' : '右侧' }} · {{ selectedJob.companion.scale }}</dd></div>
        </dl>
        <section class="studio-recipe"><span>创作配方</span><p>{{ selectedJob.recipe.layout }}</p><small>{{ selectedJob.recipe.focal_element }} · {{ selectedJob.recipe.texture }}</small></section>
        <a v-if="selectedJob.style_source" class="studio-source-credit" :href="selectedJob.style_source.url" target="_blank" rel="noreferrer">{{ selectedJob.style_source.name }} {{ selectedJob.style_source.version }} · {{ selectedJob.style_source.license }}</a>
        <p v-if="selectedJob.companion" class="studio-disclosure">{{ selectedJob.companion.disclosure }}</p>
        <section class="studio-prompt"><span>生成提示词</span><p>{{ selectedJob.prompt }}</p></section>
        <section v-if="selectedJob.negative_prompt" class="studio-prompt negative"><span>避免内容</span><p>{{ selectedJob.negative_prompt }}</p></section>
        <p v-if="error" class="studio-inline-error" role="alert"><AlertTriangle :size="14" />{{ error.message }}（{{ error.code }}）</p>
        <footer class="studio-actions">
          <a v-if="selectedJob.download_url" :href="selectedJob.download_url"><Download :size="16" />下载</a>
          <button type="button" class="delete" :disabled="selectedJob.status === 'running'" @click="openDelete(selectedJob)"><Trash2 :size="16" />删除</button>
        </footer>
      </aside>
    </div>

    <ImageJobDeleteDialog v-if="deleteTarget" :phase="deletePhase" :preview="deletePreview" :error="deleteError" @cancel="closeDelete" @confirm="confirmDelete" />
  </main>
</template>
